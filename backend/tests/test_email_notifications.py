"""Notification delivery uses real policy/receipt SQL and mocked providers only."""
from datetime import datetime,timedelta,timezone
import importlib.util
from unittest.mock import Mock
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.tests.test_native_control_plane import boundary
from backend.app import models,database
from backend.app.services import email_notifications as n,email_service_policies as p


def prepare(engine,monkeypatch):
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE email_service_policies(service_id VARCHAR(60) PRIMARY KEY,enabled BOOLEAN NOT NULL,updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)'))
        spec=importlib.util.spec_from_file_location('notification_migration','backend/alembic/versions/0027_email_notification_receipts.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        with Operations.context(MigrationContext.configure(conn)):mod.upgrade()
    monkeypatch.setattr(n.email_verification,'smtp_settings',lambda db:{'smtp_from':'no-reply@example.org'})
    monkeypatch.setattr(n.email_delivery,'ready',lambda cfg:True)
    sender=Mock();monkeypatch.setattr(n.email_delivery,'send',sender)
    monkeypatch.setattr(database,'SessionLocal',lambda:Session(engine))
    return sender


def test_policy_deduplication_recipient_and_uncertain_delivery(boundary,monkeypatch):
    _,(a,b),_,engine,_=boundary;sender=prepare(engine,monkeypatch)
    with Session(engine) as db:
        user=db.get(models.User,a.id)
        assert n.deliver(db,user,'password_changed','test')=='disabled'
        p.set_enabled(db,'password_changed',True)
        assert n.deliver(db,user,'password_changed','test')=='accepted'
        assert n.deliver(db,user,'password_changed','test')=='already_recorded'
        assert sender.call_count==1
        assert sender.call_args.args[1]['To']==user.email
        sender.side_effect=RuntimeError('secret vendor details')
        assert n.deliver(db,user,'password_changed','uncertain')=='uncertain'
        assert n.deliver(db,user,'password_changed','uncertain')=='already_recorded'
        assert sender.call_count==2
        p.set_enabled(db,'password_changed',False)
        assert n.deliver(db,user,'password_changed','disabled_again')=='disabled'
        assert sender.call_count==2


def test_sweep_uses_committed_subject_events_and_does_not_resend(boundary,monkeypatch):
    _,(a,b),_,engine,_=boundary;sender=prepare(engine,monkeypatch)
    with Session(engine) as db:
        p.set_enabled(db,'password_changed',True)
        db.add(models.AccountAudit(subject_id=b.id,action='password.changed',created_at=datetime.now(timezone.utc)+timedelta(seconds=1)));db.commit()
    n.sweep();n.sweep()
    assert sender.call_count==1
    assert sender.call_args.args[1]['To']=='fixture-b@example.invalid'


def test_trial_reminder_uses_actual_expiry_and_skips_paid_access(boundary,monkeypatch):
    _,(a,b),_,engine,_=boundary;sender=prepare(engine,monkeypatch)
    models.Plan.__table__.create(engine,checkfirst=True)
    with Session(engine) as db:
        plan=models.Plan(code='qa',name='QA',price_cents=100,currency='USD',duration_days=30,active=True,sort_order=0);db.add(plan);db.flush()
        db.add(models.Subscription(user_id=b.id,plan_id=plan.id,status='active',current_period_end=datetime.now(timezone.utc)+timedelta(days=30)))
        db.commit();p.set_enabled(db,'trial_expiring',True)
    n.sweep();n.sweep()
    assert sender.call_count==1
    assert sender.call_args.args[1]['To']=='fixture-a@example.invalid'


def test_manual_report_requires_admin_policy_and_deduplicates_event(boundary,monkeypatch):
    import uuid
    from backend.tests.test_admin_account_controls import setup
    from backend.tests.test_native_control_plane import authenticated
    client,actor,target,engine,config=setup(boundary,monkeypatch);sender=prepare(engine,monkeypatch)
    path='/api/admin/service-integrations/services/system_updates/report'
    body={'user_id':str(target.id),'event_id':str(uuid.uuid4()),'detail':'Synthetic administrator report'}
    assert authenticated(client,path,target,config,'POST',body).status_code==403
    assert authenticated(client,path,actor,config,'POST',body).status_code==409
    toggle='/api/admin/service-integrations/services/system_updates'
    assert authenticated(client,toggle,actor,config,'PUT',{'enabled':True}).status_code==200
    result=authenticated(client,path,actor,config,'POST',body)
    assert result.status_code==200 and result.json()['accepted'] is True
    assert authenticated(client,path,actor,config,'POST',body).json()['state']=='already_recorded'
    assert sender.call_count==1
    assert authenticated(client,toggle,actor,config,'PUT',{'enabled':False}).status_code==200
    with Session(engine) as db:assert p.enabled(db,'system_updates',False) is False


def test_support_notification_filters_destination_and_does_not_read_content(boundary,monkeypatch):
    import uuid
    _,(a,b),_,engine,_=boundary;sender=prepare(engine,monkeypatch)
    monkeypatch.setattr(n,'enabled_since',lambda db,s:datetime.now(timezone.utc)-timedelta(minutes=1) if s=='support_received' else None)
    from backend.app.services import admin_email_config
    monkeypatch.setattr(admin_email_config,'read',lambda db:{'inbox_api_key':'synthetic-read-key'})
    incoming=[{'id':str(uuid.uuid4()),'to':['support@opencode-gateway.codes'],'created_at':datetime.now(timezone.utc).isoformat()},{'id':str(uuid.uuid4()),'to':['other@example.org'],'created_at':datetime.now(timezone.utc).isoformat()}]
    read=Mock(return_value={'data':incoming});monkeypatch.setattr(n.email_delivery,'read_resend',read)
    with Session(engine) as db:
        db.get(models.User,a.id).role='admin';db.commit();p.set_enabled(db,'support_received',True)
        n.poll_support(db);n.poll_support(db)
    assert sender.call_count==1
    assert read.call_args.args[0]=='/emails/receiving?limit=50'
    assert sender.call_args.args[1]['To']=='fixture-a@example.invalid'
