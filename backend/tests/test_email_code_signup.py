"""Actual signup/code/session/reset HTTP with isolated DB and captured synthetic email."""
import hashlib, importlib.util, re, uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from alembic.operations import Operations
from alembic.migration import MigrationContext
from fastapi import HTTPException
import pytest
from backend.tests.test_admin_mailbox_delivery import mail_acceptance, acceptance, boundary, configured
from backend.app import models
from backend.app.services import email_delivery, email_verification
from backend.app.routes import auth
from backend.app.security.passwords import hash_password
from backend.app.security.sessions import hash_session_token

@pytest.fixture
def signup(mail_acceptance,monkeypatch):
    f=mail_acceptance;configured(f);messages=[]
    monkeypatch.setattr(email_delivery,'send',lambda cfg,message,**kwargs:messages.append(message))
    monkeypatch.setattr(auth,'settings',f[3])
    return f,messages


def register(f,username='qa_username',email='owned-fixture@example.org'):
    return f[0].post('/api/auth/register',json={'username':username,'email':email,'password':'Synthetic8!Password','phone':'+96777700000'+('1' if username=='qa_second' else '0'),'postal_code':'+967'})


def code(messages):
    return re.search(r'\b([0-9]{6})\b',messages[-1].get_content()).group(1)


def test_signup_code_activates_once_sets_session_and_accepts_username_login(signup):
    f,messages=signup;result=register(f);assert result.status_code==201,result.text
    payload=result.json();assert payload['status']=='pending_email' and payload['username']=='qa_username'
    assert 'Set-Cookie' not in result.headers
    challenge=payload['verification_challenge'];otp=code(messages)
    assert '/verify-email?' not in messages[-1].get_content()
    assert 'code' not in payload
    with Session(f[2]) as db:
        record=db.get(models.EmailVerification,uuid.UUID(challenge));assert record.verification_method=='code'
        assert record.token_hash!=otp and record.token_hash!=hashlib.sha256(otp.encode()).hexdigest()
    verify=f[0].post('/api/auth/verify-email-code',json={'challenge_id':challenge,'code':otp})
    assert verify.status_code==200,verify.text
    assert verify.json()['status']=='active' and 'HttpOnly' in verify.headers['set-cookie']
    assert f[0].post('/api/auth/verify-email-code',json={'challenge_id':challenge,'code':otp}).status_code==400
    login=f[0].post('/api/auth/login',json={'identity':'QA_USERNAME','password':'Synthetic8!Password'})
    assert login.status_code==200 and login.json()['id']==payload['id']
    with Session(f[2]) as db:
        for actor in f[1]:assert db.get(models.User,actor.id).status=='active'


def test_wrong_codes_lock_after_five_and_expired_codes_cannot_activate(signup):
    f,messages=signup;result=register(f);challenge=result.json()['verification_challenge'];otp=code(messages)
    wrong='111111' if otp!='111111' else '222222'
    for attempt in range(5):assert f[0].post('/api/auth/verify-email-code',json={'challenge_id':challenge,'code':wrong}).status_code==400
    assert f[0].post('/api/auth/verify-email-code',json={'challenge_id':challenge,'code':otp}).status_code==400
    with Session(f[2]) as db:
        record=db.get(models.EmailVerification,uuid.UUID(challenge));assert record.code_attempts==5
        assert db.get(models.User,record.user_id).status=='pending_email'
    result=register(f,'qa_second','other-fixture@example.org');challenge=result.json()['verification_challenge'];otp=code(messages)
    with Session(f[2]) as db:db.get(models.EmailVerification,uuid.UUID(challenge)).expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
    assert f[0].post('/api/auth/verify-email-code',json={'challenge_id':challenge,'code':otp}).status_code==400


def test_resend_is_limited_rotates_challenge_and_invalidates_previous_code(signup):
    f,messages=signup;payload=register(f).json();challenge=payload['verification_challenge'];old=code(messages)
    assert f[0].post('/api/auth/resend-verification-code',json={'challenge_id':challenge}).status_code==429
    with Session(f[2]) as db:db.get(models.EmailVerification,uuid.UUID(challenge)).created_at=datetime.now(timezone.utc)-timedelta(minutes=3);db.commit()
    result=f[0].post('/api/auth/resend-verification-code',json={'challenge_id':challenge});assert result.status_code==200,result.text
    new=result.json()['verification_challenge'];assert new!=challenge and len(messages)==2
    assert f[0].post('/api/auth/verify-email-code',json={'challenge_id':challenge,'code':old}).status_code==400
    assert f[0].post('/api/auth/verify-email-code',json={'challenge_id':new,'code':code(messages)}).status_code==200


def test_old_links_are_preserved_and_password_reset_allows_fresh_username_login(signup):
    f,messages=signup;payload=register(f).json();challenge=payload['verification_challenge'];uid=uuid.UUID(payload['id'])
    with Session(f[2]) as db:
        user=db.get(models.User,uid);raw=email_verification.create_pending(db,user);db.commit()
    verified=f[0].get('/api/auth/verify-email',params={'token':raw},follow_redirects=False)
    assert verified.status_code==303 and verified.headers['location']=='/#email=verified'
    with Session(f[2]) as db:
        token='synthetic-reset-token-'+'x'*40
        db.add(models.PasswordReset(user_id=uid,token_hash=hash_session_token(token),expires_at=datetime.now(timezone.utc)+timedelta(minutes=30)));db.commit()
    reset=f[0].post('/api/auth/reset-password',json={'token':token,'password':'Fresh9!Password'})
    assert reset.status_code==200,reset.text
    assert 'Max-Age=0' in reset.headers['set-cookie']
    assert f[0].post('/api/auth/login',json={'identity':'qa_username','password':'Synthetic8!Password'}).status_code==401
    assert f[0].post('/api/auth/login',json={'identity':'qa_username','password':'Fresh9!Password'}).status_code==200


def test_0025_migration_preserves_old_link_rows(signup):
    f,_=signup
    # Separate legacy-shaped verification table on the same isolated fixture DB.
    with f[2].begin() as conn:
        conn.execute(text('DROP TABLE email_verifications'))
        conn.execute(text('CREATE TABLE email_verifications (id CHAR(32) PRIMARY KEY, user_id CHAR(32), token_hash VARCHAR(64), expires_at DATETIME, used_at DATETIME, created_at DATETIME)'))
        conn.execute(text("INSERT INTO email_verifications(id,token_hash) VALUES('legacy','legacy_hash')"))
        spec=importlib.util.spec_from_file_location('code_migration','backend/alembic/versions/0025_email_verification_codes.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with Operations.context(MigrationContext.configure(conn)):module.upgrade()
        row=conn.execute(text('SELECT token_hash,verification_method,code_attempts FROM email_verifications')).one()
        assert tuple(row)==('legacy_hash','link',0)


def test_new_registration_code_and_expired_legacy_code_have_one_minute_limit(signup):
    f,messages=signup
    response=register(f)
    assert response.status_code==201,response.text
    data=response.json()
    assert data['verification_expires_in']==60
    challenge=uuid.UUID(data['verification_challenge'])
    with Session(f[2]) as db:
        row=db.get(models.EmailVerification,challenge)
        assert 0<(row.expires_at-row.created_at).total_seconds()<=61
        # Simulate a formerly issued 10-minute OTP: deployment enforces the
        # new one-minute boundary even when the stored expires_at is longer.
        row.created_at=datetime.now(timezone.utc)-timedelta(seconds=61)
        row.expires_at=datetime.now(timezone.utc)+timedelta(minutes=9)
        db.commit()
    assert f[0].post('/api/auth/verify-email-code',json={
        'challenge_id':str(challenge),'code':code(messages)}).status_code==400


def test_password_reset_email_link_expires_in_one_minute(signup):
    f,messages=signup
    registered=register(f)
    assert registered.status_code==201,registered.text
    data=registered.json()
    assert f[0].post('/api/auth/verify-email-code',json={
        'challenge_id':data['verification_challenge'],
        'code':code(messages)}).status_code==200
    response=f[0].post('/api/auth/forgot-password',json={
        'email':'owned-fixture@example.org'})
    assert response.status_code==202,response.text
    with Session(f[2]) as db:
        record=db.scalar(select(models.PasswordReset).where(
            models.PasswordReset.user_id==uuid.UUID(data['id'])))
        assert record is not None
        assert 0<(record.expires_at-record.created_at).total_seconds()<=61
    assert 'within 1 minute' in messages[-1].get_content()


def test_hourly_code_limit_and_challenge_binding(signup):
    f,messages=signup;first=register(f).json();first_code=code(messages)
    second=register(f,'qa_second','other-fixture@example.org').json()
    # Force two distinct codes rather than rely on a one-in-a-million random equality.
    with Session(f[2]) as db:
        record=db.get(models.EmailVerification,uuid.UUID(second['verification_challenge']))
        fixed='999999' if first_code!='999999' else '888888'
        record.token_hash=email_verification.code_digest(record.id,fixed);record.code_attempts=0;db.commit()
    assert f[0].post('/api/auth/verify-email-code',json={'challenge_id':second['verification_challenge'],'code':first_code}).status_code==400
    with Session(f[2]) as db:
        user=db.get(models.User,uuid.UUID(first['id']))
        for _ in range(4):email_verification.create_code(db,user)
        db.flush()
        for record in db.scalars(select(models.EmailVerification).where(models.EmailVerification.user_id==user.id)):record.created_at=datetime.now(timezone.utc)-timedelta(minutes=3)
        db.commit()
    response=f[0].post('/api/auth/resend-verification-code',json={'challenge_id':first['verification_challenge']})
    assert response.status_code==429 and 'limit' in response.json()['detail']
    assert len(messages)==2
