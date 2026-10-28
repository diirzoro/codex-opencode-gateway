"""Independent GitHub email proof: local HTTP/ORM + vendor/mail fixtures only."""
import os,json,uuid
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://fixture:fixture@127.0.0.1/fixture')
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace as NS
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session,sessionmaker
from backend.app import models,database
from backend.app.services import github
from backend.tests.test_github_reconnect_security import flow
from backend.tests.test_native_control_plane import boundary

PRODUCTION_SEND = github._send_ownership_code


def raw_confirm(f,owner):
    item=f.pending(owner) or {'connection_id':str(uuid.uuid4()),'github_user_id':101,'installations':[{'id':901}]}
    return f.request('/api/github/confirm',owner,'POST',{'connection_id':item['connection_id'],
        'github_user_id':item['github_user_id'],'installation_id':item['installations'][0]['id']})


def send(f,owner,email=None):
    item=f.pending(owner) or {'connection_id':str(uuid.uuid4()),'github_user_id':101}
    return f.request('/api/github/pending/email/send',owner,'POST',{'connection_id':item['connection_id'],'email':email or 'github'+str(item['github_user_id'])+'@example.com'})
def verify(f,owner,code):return f.request('/api/github/pending/email/verify',owner,'POST',{'connection_id':f.pending(owner)['connection_id'],'code':code})


def age_rate(f):
    with Session(f.engine) as db:
        for row in db.scalars(select(models.AccountAudit).where(models.AccountAudit.action.like('github.mail.%'))):row.created_at=datetime.now(timezone.utc)-timedelta(seconds=61)
        db.commit()


def test_after_disconnect_other_gateway_user_needs_independent_github_email_proof(flow,monkeypatch):
    f=flow;a,b=f.owners
    monkeypatch.setattr(github.secrets,'randbelow',lambda n:123456)
    f.callback(f.start(a),a);old=f.confirm(a).json()['connection_id']
    assert f.request('/api/github/disconnect',a,'POST').json()['grant_revocation']=='verified'
    age_rate(f)
    f.callback(f.start(b),b,'A')  # A's remembered browser identity in B's fresh OAuth.
    assert raw_confirm(f,b).status_code==403
    assert f.request('/api/github/repositories',b).status_code==503
    assert verify(f,b,'123456').status_code==400  # Previous transaction's code.
    monkeypatch.setattr(github.secrets,'randbelow',lambda n:654321)
    mailed=send(f,b);assert mailed.status_code==200,mailed.text
    assert f.sent[-1]['email']=='github101@example.com'  # NOT Gateway B's address.
    assert 'github101@example.com' not in mailed.text and '654321' not in mailed.text
    assert verify(f,b,'123456').status_code==400
    assert raw_confirm(f,b).status_code==403
    # The explicitly approved transfer policy: independent inbox control + fresh
    # OAuth + confirmation. No permanent reservation or revoked token reuse.
    assert verify(f,b,'654321').status_code==200
    assert verify(f,b,'654321').status_code==400  # Single use.
    connected=raw_confirm(f,b);assert connected.status_code==200,connected.text
    assert connected.json()['connection_id']!=old
    assert f.request('/api/github/repositories',a).status_code==503
    assert 'github-101/repo' in f.request('/api/github/repositories',b).text


def test_logout_preserves_active_owner_and_other_users_cannot_inherit(flow):
    from backend.app.routes import auth
    from backend.app.security.sessions import hash_session_token
    f=flow;a,b=f.owners;f.callback(f.start(a),a);assert f.confirm(a).status_code==200
    f.client.app.include_router(auth.router)
    assert f.request('/api/auth/logout',a,'POST').status_code in (200,204)
    assert f.request('/api/github/status',a).status_code==401
    count=len(f.sent);f.callback(f.start(b),b,'A')
    assert send(f,b).status_code==409 and raw_confirm(f,b).status_code==409
    assert len(f.sent)==count and f.request('/api/github/repositories',b).status_code==503
    with Session(f.engine) as db:
        assert db.scalar(select(models.GithubConnection).where(models.GithubConnection.user_id==a.id)) is not None
        now=datetime.now(timezone.utc);c=NS(id=uuid.uuid4(),name='c')
        db.add(models.User(id=c.id,username='fixture-c',email='fixture-c@example.invalid',password_hash='fixture',phone='synthetic',postal_code='00000',status='active',role='customer',trial_started_at=now,trial_ends_at=now+timedelta(days=1)))
        db.add(models.AuthSession(id=uuid.uuid4(),user_id=c.id,token_hash=hash_session_token('fixture-token-c'),expires_at=now+timedelta(hours=1),last_seen_at=now));db.commit()
    assert f.request('/api/github/repositories',c).status_code==503


@pytest.mark.parametrize('kind',['unverified','public-only','no-permission','wrong-identity'])
def test_missing_verified_github_primary_email_never_falls_back_to_gateway(flow,monkeypatch,kind):
    f=flow;a=f.owners[0];f.callback(f.start())
    original=github._api
    def api(method,path,**kwargs):
        if path=='/user/emails':
            if kind=='no-permission':raise HTTPException(403,'Synthetic denied')
            return [{'email':'public@example.com','primary':True,'verified':kind!='unverified'}] if kind=='unverified' else []
        if path=='/user' and kind=='wrong-identity':return {'id':999,'login':'foreign'}
        return original(method,path,**kwargs)
    monkeypatch.setattr(github,'_api',api)
    assert send(f,a).status_code in (403,409,503)
    assert not f.sent and raw_confirm(f,a).status_code==403


def test_delivery_failure_is_not_reported_as_sent_or_verified(flow,monkeypatch):
    f=flow;a=f.owners[0];f.callback(f.start())
    monkeypatch.setattr(github,'_send_ownership_code',lambda *a:(_ for _ in ()).throw(HTTPException(503,'Synthetic delivery error')))
    assert send(f,a).status_code==503
    assert not f.pending()['email_verification']['sent']
    assert raw_confirm(f,a).status_code==403
    assert send(f,a).status_code==429  # Failed delivery still consumes the abuse limit.


def test_attempt_limit_and_new_oauth_do_not_remove_send_cooldown(flow,monkeypatch):
    f=flow;a=f.owners[0];monkeypatch.setattr(github.secrets,'randbelow',lambda n:123456)
    f.callback(f.start());assert send(f,a).status_code==200
    for _ in range(5):assert verify(f,a,'000000').status_code==400
    assert verify(f,a,'123456').status_code==400
    f.callback(f.start());assert send(f,a).status_code==429
    assert raw_confirm(f,a).status_code==403


def test_email_proof_expires_and_email_change_requires_new_code(flow,monkeypatch):
    f=flow;a=f.owners[0];f.callback(f.start());assert send(f,a).status_code==200
    assert verify(f,a,f.sent[-1]['code']).status_code==200
    original=github._api
    monkeypatch.setattr(github,'_api',lambda method,path,**kw:[{'email':'changed@example.com','primary':True,'verified':True}] if path=='/user/emails' else original(method,path,**kw))
    assert raw_confirm(f,a).status_code==409
    with Session(f.engine) as db:
        row=db.scalar(select(models.GithubAuthState).where(models.GithubAuthState.pending_payload.is_not(None)))
        payload=json.loads(github.credentials.decrypt(row.pending_payload));payload['email_proof']['expires_at']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
        row.pending_payload=github.credentials.encrypt(json.dumps(payload));db.commit()
    assert not f.pending()['email_verification']['verified']
    assert raw_confirm(f,a).status_code==403


def test_foreign_and_old_session_cannot_request_or_verify_ownership_code(flow):
    f=flow;a,b=f.owners;f.callback(f.start(a),a);item=f.pending(a)
    for path in ('send','verify'):
        response=f.request('/api/github/pending/email/'+path,b,'POST',{'connection_id':item['connection_id'],**({'code':'123456'} if path=='verify' else {'email':'github101@example.com'})})
        assert response.status_code in (403,409)
    assert not f.sent
    with Session(f.engine) as db:
        session=db.scalar(select(models.AuthSession).where(models.AuthSession.user_id==a.id));session.id=uuid.uuid4();db.commit()
    assert f.request('/api/github/pending/email/send',a,'POST',{'connection_id':item['connection_id'],'email':'github101@example.com'}).status_code==403


def test_maintenance_removes_only_expired_pending_secrets_and_old_rate_counters(flow,monkeypatch):
    f=flow;f.callback(f.start());send(f,f.owners[0])
    with Session(f.engine) as db:
        state=db.scalar(select(models.GithubAuthState));state.expires_at=datetime.now(timezone.utc)-timedelta(minutes=1)
        audit=db.scalar(select(models.AccountAudit).where(models.AccountAudit.action.like('github.mail.%')));audit.created_at=datetime.now(timezone.utc)-timedelta(hours=25)
        db.add(models.AccountAudit(subject_id=f.owners[0].id,action='synthetic.keep'));db.commit()
    monkeypatch.setattr(database,'SessionLocal',sessionmaker(bind=f.engine))
    github.expire_pending_authorizations()
    with Session(f.engine) as db:
        assert not list(db.scalars(select(models.GithubAuthState)))
        assert not list(db.scalars(select(models.AccountAudit).where(models.AccountAudit.action.like('github.mail.%'))))
        assert db.scalar(select(models.AccountAudit).where(models.AccountAudit.action=='synthetic.keep'))
        assert db.get(models.User,f.owners[0].id) and db.get(models.Project,f.owners[0].project)


def test_pending_and_rate_records_never_store_plain_email_or_code(flow,monkeypatch):
    f=flow;a=f.owners[0];monkeypatch.setattr(github.secrets,'randbelow',lambda n:123456)
    f.callback(f.start());response=send(f,a);assert response.status_code==200
    with Session(f.engine) as db:
        record=db.scalar(select(models.GithubAuthState));payload=json.loads(github.credentials.decrypt(record.pending_payload))
        proof=payload['email_proof'];assert proof['digest']!='123456'
        assert 'github101@example.com' not in json.dumps(proof) and '123456' not in json.dumps(proof)
        audit=db.scalar(select(models.AccountAudit).where(models.AccountAudit.action.like('github.mail.%')))
        assert '123456' not in audit.action and '@' not in audit.action
    status=f.request('/api/github/status').text
    assert 'github101@example.com' not in status and '123456' not in status and 'token-A' not in status


def test_mail_sender_reuses_existing_delivery_service_with_github_recipient(flow,monkeypatch):
    from backend.app.services import email_delivery,email_verification
    monkeypatch.setattr(email_verification,'smtp_settings',lambda db:{'smtp_from':'no-reply@example.com'})
    calls=[];monkeypatch.setattr(email_delivery,'send',lambda cfg,message,**kw:calls.append((cfg,message,kw)))
    PRODUCTION_SEND('verified-github@example.com','123456',None)
    assert calls[0][1]['To']=='verified-github@example.com'
    assert 'GitHub' in calls[0][1]['Subject']
    assert calls[0][2]['timeout']==12
