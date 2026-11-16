"""Isolated finance regressions. No production DB or provider requests."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.database import Base
from app.models import AccountAudit, PaymentOrder, Plan, Subscription, User
from app.routes import admin, billing
from app.services import paypal
from app.services.entitlements import access_payload


@pytest.fixture
def records():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with engine.begin() as con:
        con.execute(text('CREATE TABLE admin_finance_notes (target_type TEXT, target_id TEXT, note TEXT, archived_at TEXT, updated_by TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(target_type,target_id))'))
    with Session(engine, expire_on_commit=False) as db:
        now = datetime.now(timezone.utc)
        def user(name, role):
            return User(username=name, email=name+'@example.test', password_hash='unused',
                        phone='', postal_code='', role=role, trial_started_at=now,
                        trial_ends_at=now+timedelta(days=30))
        actor, customer = user('finance-admin','admin'), user('finance-customer','customer')
        plan = Plan(code='finance_test', name='Test plan', price_cents=200, duration_days=30)
        db.add_all([actor,customer,plan]); db.flush()
        sub = Subscription(user_id=customer.id, status='trial', current_period_end=customer.trial_ends_at)
        order = PaymentOrder(user_id=customer.id, plan_id=plan.id, plan_name=plan.name,
                             method_label='PayPal Sandbox', amount_cents=200, currency='USD',
                             duration_days=30, status='awaiting_payment',
                             provider_environment='sandbox', provider_order_id='AUDIT00001')
        db.add_all([sub,order]); db.commit()
        yield db,actor,customer,sub,order,plan
    engine.dispose()


def test_missing_sandbox_order_can_be_cancelled_idempotently(records,monkeypatch):
    db,actor,customer,sub,order,plan = records
    monkeypatch.setattr(paypal,'settings',SimpleNamespace(paypal_environment='sandbox',paypal_client_id='',paypal_client_secret='',paypal_merchant_id=''))
    def missing(row,**kwargs): raise paypal.OrderNotFound()
    monkeypatch.setattr(paypal,'show_order',missing)
    assert billing.cancellation_status(order.id,customer,db)['can_cancel']
    result = billing.cancel_unpaid_order(db,order,actor)
    assert result['status']=='cancelled' and not order.paid_at and not order.provider_capture_id
    billing.cancel_unpaid_order(db,order,actor)
    audits = list(db.scalars(select(AccountAudit).where(AccountAudit.action=='billing.payment_cancelled')))
    assert len(audits)==1 and audits[0].actor_id==actor.id and audits[0].subject_id==customer.id


@pytest.mark.parametrize('remote', ['APPROVED','COMPLETED','ERROR','MISSING_LIVE'])
def test_uncertain_live_or_approved_payments_are_not_cancelled(records,monkeypatch,remote):
    db,actor,customer,sub,order,plan = records
    monkeypatch.setattr(paypal,'settings',SimpleNamespace(paypal_environment='sandbox',paypal_client_id='',paypal_client_secret='',paypal_merchant_id=''))
    if remote=='MISSING_LIVE': order.provider_environment='live'
    def show(row,**kwargs):
        if remote=='ERROR': raise HTTPException(503,'private upstream failure')
        if remote=='MISSING_LIVE': raise paypal.OrderNotFound()
        return {'status':remote}
    monkeypatch.setattr(paypal,'show_order',show)
    with pytest.raises(HTTPException) as err: billing.cancel_unpaid_order(db,order,actor)
    assert err.value.status_code==409 and order.status=='awaiting_payment'
    assert 'private upstream failure' not in str(err.value.detail)


@pytest.mark.parametrize('status',['paid','sandbox_paid'])
def test_accepted_payments_never_enter_cancellation_lookup(records,monkeypatch,status):
    db,actor,customer,sub,order,plan = records
    order.status=status
    lookup=MagicMock(); monkeypatch.setattr(paypal,'cancellation_state',lookup)
    with pytest.raises(HTTPException): billing.cancel_unpaid_order(db,order,actor)
    lookup.assert_not_called()


def test_only_order_get_404_is_classified_as_missing(monkeypatch):
    monkeypatch.setattr(paypal,'settings',SimpleNamespace(paypal_environment='sandbox',paypal_client_id='test',paypal_client_secret='unused',paypal_merchant_id='merchant',paypal_sandbox_decline=False))
    response=MagicMock(status_code=404)
    response.json.return_value={'name':'RESOURCE_NOT_FOUND','details':[{'issue':'INVALID_RESOURCE_ID'}]}
    token=MagicMock(status_code=200);token.json.return_value={'access_token':'unused'}
    client=MagicMock();client.__enter__.return_value=client;client.post.return_value=token;client.request.return_value=response
    monkeypatch.setattr(paypal.httpx,'Client',lambda **kwargs:client)
    with pytest.raises(paypal.OrderNotFound):paypal.request('GET','/v2/checkout/orders/AUDIT00001')
    with pytest.raises(HTTPException) as err:paypal.request('POST','/v2/checkout/orders/AUDIT00001/capture')
    assert not isinstance(err.value,paypal.OrderNotFound)


def test_subscription_cancel_stops_access_without_changing_payment_history(records):
    db,actor,customer,sub,order,plan = records
    end=sub.current_period_end
    data=admin.AdminFinanceConfirm(confirmation='CANCEL SUBSCRIPTION')
    admin.finance_cancel_subscription(sub.id,data,actor,db)
    admin.finance_cancel_subscription(sub.id,data,actor,db)
    assert sub.status=='cancelled' and sub.admin_suspended_at and sub.current_period_end==end
    assert not access_payload(db,customer)['allowed']
    assert db.get(PaymentOrder,order.id).status=='awaiting_payment'
    assert len(list(db.scalars(select(AccountAudit).where(AccountAudit.action=='finance.subscription_cancelled'))))==1
    admin.finance_suspend_subscription(sub.id,admin.AdminFinanceSuspend(suspended=False,confirmation='RESUME'),actor,db)
    assert sub.status=='trial' and access_payload(db,customer)['allowed']
    assert not access_payload(db,customer)['paid_access']['active']


@pytest.mark.parametrize('paid,expired,expected', [(True,False,'active'),(True,True,'expired'),(False,False,'trial')])
def test_resuming_cancelled_subscription_never_invents_paid_access(records,paid,expired,expected):
    db,actor,customer,sub,order,plan=records
    sub.status='cancelled';sub.admin_suspended_at=datetime.now(timezone.utc);sub.plan_id=plan.id
    sub.current_period_end=datetime.now(timezone.utc)+timedelta(days=-1 if expired else 2)
    if paid:order.status='paid';order.paid_at=datetime.now(timezone.utc)
    db.commit()
    admin.finance_suspend_subscription(sub.id,admin.AdminFinanceSuspend(suspended=False,confirmation='RESUME'),actor,db)
    assert sub.status==expected
    assert access_payload(db,customer)['paid_access']['active']==(paid and not expired)


def test_delete_eligibility_matches_delete_guard_and_archive_is_recoverable(records):
    db,actor,customer,sub,order,plan=records
    listed=admin.admin_subscriptions(actor,db)[0]
    assert not listed['can_delete'] and listed['can_manage']
    with pytest.raises(HTTPException):admin.finance_delete_empty_subscription(sub.id,admin.AdminFinanceConfirm(confirmation='DELETE EMPTY SUBSCRIPTION'),actor,db)
    admin.finance_save_note('subscription',sub.id,admin.AdminFinanceNote(note='test',archived=True),actor,db)
    assert admin.finance_notes(actor,db)[0]['archived_at']
    assert db.get(Subscription,sub.id) is not None and db.get(PaymentOrder,order.id) is not None
    admin.finance_save_note('subscription',sub.id,admin.AdminFinanceNote(note='test',archived=False),actor,db)
    assert admin.finance_notes(actor,db)[0]['archived_at'] is None
    db.delete(order);sub.current_period_end=None;sub.status='expired';customer.trial_ends_at=datetime.now(timezone.utc)-timedelta(days=1);db.commit()
    assert admin.admin_subscriptions(actor,db)[0]['can_delete']
    assert admin.finance_delete_empty_subscription(sub.id,admin.AdminFinanceConfirm(confirmation='DELETE EMPTY SUBSCRIPTION'),actor,db).status_code==204
    assert db.get(Subscription,sub.id) is None


def test_admin_subscription_and_wrong_confirmation_are_protected(records):
    db,actor,customer,sub,order,plan=records
    with pytest.raises(HTTPException) as err:admin.finance_cancel_subscription(sub.id,admin.AdminFinanceConfirm(confirmation='WRONG'),actor,db)
    assert err.value.status_code==422 and sub.status=='trial'
    sub.user_id=actor.id;db.commit()
    assert not admin.admin_subscriptions(actor,db)[0]['can_manage']
    with pytest.raises(HTTPException) as err:admin.finance_cancel_subscription(sub.id,admin.AdminFinanceConfirm(confirmation='CANCEL SUBSCRIPTION'),actor,db)
    assert err.value.status_code==403
