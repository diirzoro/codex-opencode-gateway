"""Previously unverified recovery scope; no delivery or payment processor call."""
import os,secrets,uuid
from datetime import datetime,timedelta,timezone
from sqlalchemy import select
import pytest
from backend.tests.test_disposable_database import account
pytestmark=pytest.mark.skipif(os.getenv('AUDIT_DISPOSABLE_DB')!='1',reason='isolated database required')


def test_archived_recovery_scope_and_password_completion_do_not_reset_trial(account):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.database import SessionLocal
    from backend.app.models import User,PasswordReset,Subscription,PaymentOrder,Plan
    from backend.app.security.sessions import hash_session_token,reactivation_cookie_name
    owner,_,user,_=account
    now=datetime.now(timezone.utc);suffix=uuid.uuid4().hex;raw=secrets.token_urlsafe(32)
    with SessionLocal() as db:
        archived=User(username='recover_'+suffix[:12],email=suffix+'@example.org',password_hash='!archived!',phone='',postal_code='',status='archived',trial_started_at=now-timedelta(days=160),trial_ends_at=now-timedelta(days=130))
        db.add(archived);db.flush();uid=archived.id;trial=(archived.trial_started_at,archived.trial_ends_at)
        db.add(PasswordReset(user_id=uid,token_hash=hash_session_token(raw),expires_at=now+timedelta(minutes=10)));db.commit()
    recovery=TestClient(app,base_url='https://testserver')
    try:
        assert recovery.post('/api/auth/recovery-status',json={'token':raw}).json()['reactivation_required'] is True
        proof=recovery.post('/api/auth/reactivation/verify',json={'token':raw})
        assert proof.status_code==200 and proof.json()['payment_verified'] is False
        assert recovery.post('/api/auth/reactivation/verify',json={'token':raw}).status_code==400
        assert recovery.get('/api/profile').status_code in {401,403}
        assert recovery.get('/api/workspaces').status_code in {401,403}
        assert recovery.post('/api/auth/reactivation/password',json={'password':'Fixture!Fresh123'}).status_code==409
        # Represent an ALREADY confirmed paid entitlement in disposable data.
        # No checkout/capture/bank approval or payment implementation is invoked.
        with SessionLocal() as db:
            plan=db.scalar(select(Plan).where(Plan.active.is_(True)).limit(1));assert plan
            target=db.get(User,uid);target.status='active'
            db.add(Subscription(user_id=uid,plan_id=plan.id,status='active',started_at=now,current_period_end=now+timedelta(days=30)))
            db.add(PaymentOrder(user_id=uid,plan_id=plan.id,plan_name=plan.name,method_label='Preconfirmed fixture state',amount_cents=plan.price_cents,currency=plan.currency,duration_days=30,status='paid',paid_at=now))
            db.commit()
        assert recovery.get('/api/auth/reactivation').json()['payment_verified'] is True
        assert recovery.get('/api/profile').status_code in {401,403}
        done=recovery.post('/api/auth/reactivation/password',json={'password':'Fixture!Fresh123'});assert done.status_code==200,done.text
        assert recovery.get('/api/auth/reactivation').status_code in {401,403}
        logged=recovery.post('/api/auth/login',json={'identity':suffix+'@example.org','password':'Fixture!Fresh123'});assert logged.status_code==200,logged.text
        access=recovery.get('/api/profile/access').json()['access']
        assert access['kind']=='subscription' and access['core_trial']['active'] is False and access['core_trial']['remaining_days']==0
        with SessionLocal() as db:
            restored=db.get(User,uid)
            assert (restored.trial_started_at,restored.trial_ends_at)==trial
            assert db.get(User,uuid.UUID(user['id'])).status=='active'

    finally:recovery.close()
