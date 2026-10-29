"""HTTP integration: no account exists before the one-minute OTP succeeds."""
import importlib.util
import re
import uuid
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from sqlalchemy import select,text
from sqlalchemy.orm import Session
from alembic.operations import Operations
from alembic.migration import MigrationContext
import pytest
from backend.tests.test_admin_mailbox_delivery import mail_acceptance,acceptance,boundary,configured
from backend.app import models
from backend.app.services import email_delivery, email_verification, registration_drafts
from backend.app.routes import auth


@pytest.fixture
def signup(mail_acceptance,monkeypatch):
    f=mail_acceptance
    configured(f)
    models.PendingRegistration.__table__.create(f[2],checkfirst=True)
    messages=[]
    monkeypatch.setattr(email_delivery,'send',lambda cfg,message,**kwargs:messages.append(message))
    # Synthetic TestClient runs on http://testserver, unlike actual HTTPS TEST.
    # Keep secure cookies enabled in production; only the fixture uses HTTP.
    monkeypatch.setattr(auth,'settings',replace(f[3],cookie_secure=False))
    return f,messages


def register(f,username='qa_username',email='owned-fixture@example.org'):
    return f[0].post('/api/auth/register',json={
        'username':username,'email':email,'password':'Synthetic8!Password',
        'phone':'+96777700000'+('1' if username=='qa_second' else '0'),
        'postal_code':'+967'})


def code(messages):
    return re.search(r'\b([0-9]{6})\b',messages[-1].get_content()).group(1)


def confirm(f,messages,payload):
    return f[0].post('/api/auth/registration/confirm',json={
        'challenge_id':payload['verification_challenge'],'code':code(messages)})


def pending(db,challenge):
    return db.get(models.PendingRegistration,uuid.UUID(challenge))


def test_signup_account_created_only_after_correct_code_and_login(signup):
    f,messages=signup
    result=register(f)
    assert result.status_code==201,result.text
    data=result.json()
    assert data['status']=='pending_verification'
    assert 'id' not in data and 'password' not in result.text
    assert data['verification_expires_in']<=60
    assert 'HttpOnly' in result.headers['set-cookie']
    with Session(f[2]) as db:
        assert db.scalar(select(models.User).where(models.User.email=='owned-fixture@example.org')) is None
        row=pending(db,data['verification_challenge'])
        assert row is not None and 'Synthetic8!Password' not in row.payload_ciphertext
    # A user cannot log in or receive a trial before validating email ownership.
    assert f[0].post('/api/auth/login',json={
        'identity':'qa_username','password':'Synthetic8!Password'}).status_code==401
    wrong='111111' if code(messages)!='111111' else '222222'
    rejected=f[0].post('/api/auth/registration/confirm',json={
        'challenge_id':data['verification_challenge'],'code':wrong})
    assert rejected.status_code==400 and 'Incorrect' in rejected.json()['detail']
    verify=confirm(f,messages,data)
    assert verify.status_code==200,verify.text
    assert verify.json()['status']=='active' and 'HttpOnly' in verify.headers['set-cookie']
    assert f[0].post('/api/auth/registration/confirm',json={
        'challenge_id':data['verification_challenge'],'code':code(messages)}).status_code==404
    with Session(f[2]) as db:
        row=db.scalar(select(models.User).where(models.User.email=='owned-fixture@example.org'))
        assert row and row.trial_started_at is not None
        assert pending(db,data['verification_challenge']) is None
    login=f[0].post('/api/auth/login',json={
        'identity':'QA_USERNAME','password':'Synthetic8!Password'})
    assert login.status_code==200


def test_wrong_code_five_times_locks_draft_without_account(signup):
    f,messages=signup;data=register(f).json()
    wrong='111111' if code(messages)!='111111' else '222222'
    for _ in range(5):
        response=f[0].post('/api/auth/registration/confirm',json={
            'challenge_id':data['verification_challenge'],'code':wrong})
        assert response.status_code==400
    assert confirm(f,messages,data).status_code==400
    with Session(f[2]) as db:
        assert pending(db,data['verification_challenge']).attempts==5
        assert db.scalar(select(models.User).where(models.User.email=='owned-fixture@example.org')) is None


def test_code_expiration_and_resend_after_one_minute(signup):
    f,messages=signup;data=register(f).json();challenge=data['verification_challenge']
    assert f[0].post('/api/auth/registration/resend',json={
        'challenge_id':challenge}).status_code==429
    old=code(messages)
    with Session(f[2]) as db:
        row=pending(db,challenge)
        row.code_expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
        row.last_sent_at=datetime.now(timezone.utc)-timedelta(seconds=61)
        db.commit()
    assert confirm(f,messages,data).status_code==400
    resent=f[0].post('/api/auth/registration/resend',json={
        'challenge_id':challenge})
    assert resent.status_code==200,resent.text
    assert resent.json()['verification_challenge']==challenge
    assert resent.json()['verification_expires_in']<=60
    assert len(messages)==2
    assert confirm(f,messages,data).status_code==200


def test_edit_email_and_username_sends_code_to_new_address_only(signup):
    f,messages=signup;data=register(f).json();old_code=code(messages)
    response=f[0].patch('/api/auth/registration/update',
        params={'challenge_id':data['verification_challenge']},
        json={'email':'corrected-fixture@example.org','username':'new_username'})
    assert response.status_code==200,response.text
    assert response.json()['email_changed'] is True
    assert response.json()['email']=='corrected-fixture@example.org'
    assert messages[-1]['To']=='corrected-fixture@example.org'
    with Session(f[2]) as db:
        assert db.scalar(select(models.User).where(models.User.username=='new_username')) is None
    rejected=f[0].post('/api/auth/registration/confirm',json={
        'challenge_id':data['verification_challenge'],'code':old_code})
    assert rejected.status_code==400
    verified=confirm(f,messages,data)
    assert verified.status_code==200,verified.text
    assert verified.json()['email']=='corrected-fixture@example.org'
    assert verified.json()['username']=='new_username'


def test_edit_non_email_details_keeps_current_code_and_no_extra_email(signup):
    f,messages=signup;data=register(f).json();original=code(messages)
    response=f[0].patch('/api/auth/registration/update',
        params={'challenge_id':data['verification_challenge']},
        json={'username':'correct_user'})
    assert response.status_code==200,response.text
    assert response.json()['email_changed'] is False
    assert len(messages)==1
    result=confirm(f,messages,data)
    assert result.status_code==200 and result.json()['username']=='correct_user'


def test_cancel_registration_does_not_create_or_delete_an_account(signup):
    f,messages=signup;data=register(f).json()
    cancelled=f[0].post('/api/auth/registration/cancel',json={
        'challenge_id':data['verification_challenge']})
    assert cancelled.status_code==200,cancelled.text
    assert cancelled.json()['cancelled']
    assert confirm(f,messages,data).status_code==404
    with Session(f[2]) as db:
        assert pending(db,data['verification_challenge']) is None
        assert db.scalar(select(models.User).where(models.User.email=='owned-fixture@example.org')) is None


def test_draft_ticket_is_required_and_not_exposed_in_json(signup):
    f,messages=signup;result=register(f);data=result.json()
    assert 'ticket' not in result.text and 'password' not in result.text
    f[0].cookies.clear()
    assert confirm(f,messages,data).status_code==404
    assert f[0].post('/api/auth/registration/resend',json={
        'challenge_id':data['verification_challenge']}).status_code==404
    with Session(f[2]) as db:
        assert db.scalar(select(models.User).where(models.User.email=='owned-fixture@example.org')) is None


def test_email_identity_not_reserved_by_unverified_draft(signup):
    f,messages=signup;data=register(f).json()
    with Session(f[2]) as db:
        assert db.scalar(select(models.User).where(models.User.email=='owned-fixture@example.org')) is None
    # A second request for the same email is rate limited without creating a User.
    assert register(f,'different_user','owned-fixture@example.org').status_code==429
    with Session(f[2]) as db:
        assert db.scalar(select(models.User).where(models.User.email=='owned-fixture@example.org')) is None


def test_new_registration_code_has_one_minute_limit(signup):
    f,messages=signup;data=register(f).json();assert data['verification_expires_in']<=60
    with Session(f[2]) as db:
        row=pending(db,data['verification_challenge'])
        assert (row.code_expires_at-row.last_sent_at).total_seconds()==60
        row.code_expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
        db.commit()
    assert confirm(f,messages,data).status_code==400


def test_password_reset_email_link_expires_in_one_minute(signup):
    f,messages=signup;data=register(f).json()
    confirmed=confirm(f,messages,data)
    assert confirmed.status_code==200,confirmed.text
    reset=f[0].post('/api/auth/forgot-password',json={
        'email':'owned-fixture@example.org'})
    assert reset.status_code==202,reset.text
    with Session(f[2]) as db:
        user=db.scalar(select(models.User).where(models.User.email=='owned-fixture@example.org'))
        record=db.scalar(select(models.PasswordReset).where(models.PasswordReset.user_id==user.id))
        assert record is not None
        assert 0<(record.expires_at-record.created_at).total_seconds()<=61
    assert 'within 1 minute' in messages[-1].get_content()



def test_expired_drafts_clean_without_creating_or_deleting_users(signup,monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from backend.app import database
    f,messages=signup
    data=register(f).json()
    with Session(f[2]) as db:
        row=pending(db,data['verification_challenge'])
        row.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
        db.commit()
    monkeypatch.setattr(database,'SessionLocal',sessionmaker(bind=f[2]))
    registration_drafts.sweep()
    with Session(f[2]) as db:
        assert pending(db,data['verification_challenge']) is None
        assert db.scalar(select(models.User).where(models.User.email=='owned-fixture@example.org')) is None


def test_verification_disabled_cannot_bypass_proof_on_password_signup(signup,monkeypatch):
    f,messages=signup
    monkeypatch.setattr(email_verification,'required_for_registration',lambda db=None:False)
    result=register(f)
    assert result.status_code==201,result.text
    assert result.json()['status']=='pending_verification'
    with Session(f[2]) as db:
        assert db.scalar(select(models.User).where(models.User.email=='owned-fixture@example.org')) is None


def test_0025_migration_preserves_old_link_rows(signup):
    f,_=signup
    with f[2].begin() as conn:
        conn.execute(text('DROP TABLE email_verifications'))
        conn.execute(text('CREATE TABLE email_verifications (id CHAR(32) PRIMARY KEY, user_id CHAR(32), token_hash VARCHAR(64), expires_at DATETIME, used_at DATETIME, created_at DATETIME)'))
        conn.execute(text("INSERT INTO email_verifications(id,token_hash) VALUES('legacy','legacy_hash')"))
        spec=importlib.util.spec_from_file_location('code_migration','backend/alembic/versions/0025_email_verification_codes.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with Operations.context(MigrationContext.configure(conn)):module.upgrade()
        row=conn.execute(text('SELECT token_hash,verification_method,code_attempts FROM email_verifications')).one()
        assert tuple(row)==('legacy_hash','link',0)
