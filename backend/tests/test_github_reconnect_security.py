"""Real Gateway HTTP/ORM flow, synthetic GitHub responses; never live credentials."""
import os,uuid,json,logging,io
from dataclasses import replace
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://test:test@127.0.0.1/test')
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace as NS
from urllib.parse import urlparse,parse_qs
import pytest,httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException
from backend.app import models
from backend.app.services import github
from backend.app.routes import github as routes
from backend.tests.test_native_control_plane import boundary,authenticated

@pytest.fixture
def flow(boundary,monkeypatch):
    client,owners,_,engine,config=boundary
    models.GithubAuthState.__table__.create(engine)
    models.GithubIdentityRegistry.__table__.create(engine)
    cfg=NS(github_web_base='https://github.com',github_client_id='fixture',github_client_secret='synthetic-secret',
           github_app_id=42,github_app_slug='fixture',github_callback_url=config.public_base_url+'/api/github/callback')
    monkeypatch.setattr(github.github_app_config,'effective',lambda *a:cfg)
    monkeypatch.setattr(github,'configured',lambda *a,**kw:True)
    monkeypatch.setattr(github,'require_configured',lambda *a:None)
    monkeypatch.setattr(github,'require_advanced',lambda *a,**kw:None)
    monkeypatch.setattr(routes,'require_advanced',lambda *a,**kw:None)
    monkeypatch.setattr(routes,'settings',config)
    monkeypatch.setattr(github.credentials,'encrypt',lambda text:'encrypted:'+text)
    monkeypatch.setattr(github.credentials,'decrypt',lambda text:text.removeprefix('encrypted:'))
    monkeypatch.setattr(github,'_jwt',lambda *a:'synthetic-app-jwt')
    monkeypatch.setattr(github,'exchange_code',lambda code,**kw:{'access_token':'token-'+code})
    monkeypatch.setattr(github.credentials,'settings',replace(github.credentials.settings,credentials_encryption_key='synthetic-github-email-hmac'))
    sent=[]
    monkeypatch.setattr(github,'_send_ownership_code',lambda email,code,db:sent.append({'email':email,'code':code}))
    revoked=[];vendor=[]
    monkeypatch.setattr(github,'revoke_token',lambda token,cfg,**kwargs:revoked.append(token) or 'verified')
    def api(method,path,token=None,jwt_token=None,**kw):
        vendor.append((method,path,token))
        idx=102 if token=='token-B' else 101
        if path=='/user':return {'id':idx,'login':'github-'+str(idx)}
        if path=='/user/emails':return [{'email':'github'+str(idx)+'@example.com','primary':True,'verified':True}]
        if path=='/user/installations':return {'installations':[{'id':idx+800,'app_id':42,'account':{'id':idx,'login':'github-'+str(idx),'type':'User'}}]}
        if path.startswith('/app/installations/'):
            number=int(path.rsplit('/',1)[1]);return {'app_id':42,'account':{'id':number-800,'login':'github-'+str(number-800),'type':'User'}}
        if path.endswith('/repositories'):return {'repositories':[{'id':idx,'full_name':'github-'+str(idx)+'/repo','owner':{'login':'github-'+str(idx)}}]}
        raise AssertionError(path)
    monkeypatch.setattr(github,'_api',api)
    def request(path,owner=owners[0],method='GET',body=None):return authenticated(client,path,owner,config,method,body)
    def start(owner=owners[0]):
        response=request('/api/github/connect',owner,'POST');assert response.status_code==200,response.text
        query=parse_qs(urlparse(response.json()['url']).query);assert query['prompt']==['select_account']
        return query['state'][0]
    def callback(state,owner=owners[0],code='A',**values):
        return client.post('/api/github/callback/complete',data={'state':state,'code':code,**values},
            headers={'Cookie':config.session_cookie_name+'=fixture-token-'+owner.name,'Origin':config.public_base_url},follow_redirects=False)
    def pending(owner=owners[0]):return request('/api/github/status',owner).json()['pending']
    def confirm(owner=owners[0]):
        item=pending(owner);assert item
        # Existing ownership fixtures use controlled synthetic inboxes. Exercise
        # the real send/verify endpoints; dedicated proof tests do not use this
        # convenience and separately assert cooldown, takeover and wrong codes.
        with Session(engine) as db:
            for audit in db.scalars(select(models.AccountAudit).where(models.AccountAudit.action.like('github.mail.%'))):
                audit.created_at=datetime.now(timezone.utc)-timedelta(seconds=61)
            db.commit()
        mailed=request('/api/github/pending/email/send',owner,'POST',{'connection_id':item['connection_id'],'email':'github'+str(item['github_user_id'])+'@example.com'})
        if mailed.status_code!=200:return mailed
        verified=request('/api/github/pending/email/verify',owner,'POST',{'connection_id':item['connection_id'],'code':sent[-1]['code']})
        assert verified.status_code==200,verified.text
        return request('/api/github/confirm',owner,'POST',{'connection_id':item['connection_id'],
             'github_user_id':item['github_user_id'],'installation_id':item['installations'][0]['id']})
    return NS(**locals())


def test_callback_never_connects_before_identity_confirmation(flow):
    f=flow;s=f.start();response=f.callback(s)
    assert response.status_code==303 and response.headers['location'].endswith('github=confirm')
    with Session(f.engine) as db:
        record=db.get(models.GithubAuthState,s)
        assert record.consumed and record.pending_payload, (record.consumed,record.pending_payload)
        assert record.auth_session_id==db.scalar(select(models.AuthSession).where(models.AuthSession.user_id==f.owners[0].id)).id
    status=f.request('/api/github/status').json();assert not status['connected']
    assert status['pending']['github_login']=='github-101'
    assert 'token-' not in json.dumps(status) and 'oauth_' not in json.dumps(status)
    assert f.request('/api/github/repositories').status_code==503
    result=f.confirm();assert result.status_code==200,result.text
    assert result.json()['github_login']=='github-101'
    status=f.request('/api/github/status').json();assert status['connected'] and status['pending'] is None


def test_disconnect_reconnect_same_identity_uses_new_connection_and_keeps_files(flow,monkeypatch):
    f=flow;f.callback(f.start());old=f.confirm().json()['connection_id']
    monkeypatch.setattr(github,'remove_owned_installation',lambda *a:pytest.fail('Grant disconnect must not uninstall a shared App'))
    response=f.request('/api/github/disconnect',method='POST')
    assert response.status_code==200 and response.json()['revocation']=='verified'
    assert response.json()['installation_removal']=='not-requested'
    assert response.json()['grant_revocation']=='verified'
    assert f.revoked==['token-A']
    assert (f.owners[0].root/'marker.txt').read_text()=='synthetic-marker-a'
    with Session(f.engine) as db:
        assert db.get(models.Project,f.owners[0].project) is not None
        assert db.get(models.WorkspaceSession,f.owners[0].session) is not None
        assert not list(db.scalars(select(models.GithubAuthState)))
        assert not list(db.scalars(select(models.GithubConnection)))
    f.callback(f.start());new=f.confirm().json()['connection_id'];assert new!=old


def test_same_browser_other_account_cannot_inherit_or_confirm(flow):
    f=flow;a,b=f.owners;f.callback(f.start(a),a)
    item=f.pending(a)
    assert f.pending(b) is None
    response=f.request('/api/github/confirm',b,'POST',{'connection_id':item['connection_id'],'github_user_id':101,'installation_id':901})
    assert response.status_code in (403,409)
    assert f.request('/api/github/repositories',b).status_code==503
    assert f.confirm(a).status_code==200
    # A remembered Github A identity in B's OAuth is only pending, never linked.
    rejected=f.callback(f.start(b),b,'A');assert rejected.headers['location'].endswith('account-conflict')
    assert f.pending(b) is None and not f.request('/api/github/status',b).json()['connected']
    assert f.request('/api/github/repositories',b).status_code==503
    # B deliberately chooses its different GitHub identity in a fresh transaction.
    f.callback(f.start(b),b,'B');assert f.confirm(b).status_code==200
    assert 'github-102/repo' in f.request('/api/github/repositories',b).text
    assert 'github-101/repo' not in f.request('/api/github/repositories',b).text
    assert f.request('/api/github/status',a).json()['github_login']=='github-101'


@pytest.mark.parametrize('invalid',['wrong-user','same-user-new-login','expired','used','superseded','disconnected','unknown'])
def test_stale_foreign_and_parallel_callbacks_cannot_link(flow,invalid):
    f=flow;state=f.start();owner=f.owners[0]
    if invalid=='wrong-user':owner=f.owners[1]
    elif invalid=='same-user-new-login':
        from backend.app.security.sessions import hash_session_token
        with Session(f.engine) as db:
            session=db.scalar(select(models.AuthSession).where(models.AuthSession.user_id==owner.id));session.idle_test=True
            # Rotate the actual session identity while keeping the fixture cookie.
            session.id=uuid.uuid4();db.commit()
    elif invalid=='expired':
        with Session(f.engine) as db:db.get(models.GithubAuthState,state).expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
    elif invalid=='used':assert f.callback(state).status_code==303
    elif invalid=='superseded':f.start()
    elif invalid=='disconnected':f.request('/api/github/disconnect',method='POST')
    elif invalid=='unknown':state='oauth_unknown'
    response=f.callback(state,owner)
    assert response.status_code==303
    assert not response.headers['location'].endswith('github=confirm')
    assert not f.request('/api/github/status',owner).json()['connected']


def test_confirm_rejects_tampered_identity_or_installation_and_duplicate(flow):
    f=flow;f.callback(f.start());item=f.pending()
    for changes in [{'github_user_id':999},{'installation_id':999}]:
        body={'connection_id':item['connection_id'],'github_user_id':101,'installation_id':901,**changes}
        assert f.request('/api/github/confirm',method='POST',body=body).status_code in (403,409)
    assert f.confirm().status_code==200
    assert f.request('/api/github/confirm',method='POST',body={'connection_id':item['connection_id'],'github_user_id':101,'installation_id':901}).status_code==409


def test_disconnect_clears_only_this_users_pending_and_connection(flow,monkeypatch):
    f=flow;a,b=f.owners
    f.callback(f.start(a),a,'A');f.confirm(a)
    f.callback(f.start(b),b,'B');f.confirm(b)
    assert f.request('/api/github/connect',a,'POST').status_code==409
    assert f.request('/api/github/disconnect',a,'POST').status_code==200
    assert f.request('/api/github/status',b).json()['connected']
    assert (b.root/'marker.txt').read_text()=='synthetic-marker-b'


def test_cancel_validates_state_and_current_login_and_is_single_use(flow):
    f=flow;state=f.start()
    bad=f.callback(state,f.owners[1],code='',error='access_denied')
    assert bad.headers['location'].endswith('session-mismatch')
    good=f.callback(state,code='',error='access_denied');assert good.headers['location'].endswith('denied')
    assert f.callback(state).headers['location'].endswith('transaction-expired')


def test_public_callback_is_only_safe_cookie_bridge_not_connection(flow):
    f=flow;state=f.start();page=f.client.get('/api/github/callback',params={'state':state,'code':'synthetic-code'})
    assert page.status_code==200
    assert 'form-action' in page.headers['content-security-policy'] and 'no-store' in page.headers['cache-control']
    assert 'history.replaceState' in page.text and '/api/github/callback/complete' in page.text
    assert f.pending() is None
    assert f.client.post('/api/github/callback/complete',data={'state':state,'code':'A'}).status_code==401
    assert not f.request('/api/github/status').json()['connected']


def test_vendor_failure_does_not_leave_reusable_state(flow,monkeypatch):
    f=flow;state=f.start()
    monkeypatch.setattr(github,'exchange_code',lambda *a,**kw:(_ for _ in ()).throw(HTTPException(502,'Vendor unavailable')))
    assert f.callback(state).headers['location'].endswith('error')
    with Session(f.engine) as db:assert db.get(models.GithubAuthState,state).consumed


def test_revocation_failure_is_truthful_and_still_removes_local_authority(flow,monkeypatch):
    f=flow;f.callback(f.start());f.confirm()
    monkeypatch.setattr(github,'revoke_token',lambda *a:'unconfirmed')
    monkeypatch.setattr(github,'remove_owned_installation',lambda *a:'owner-review-required')
    r=f.request('/api/github/disconnect',method='POST')
    assert r.json()['revocation']=='unconfirmed' and r.json()['local_credentials_removed']
    assert f.request('/api/github/repositories').status_code==503


def test_callback_access_log_does_not_include_code_or_state():
    record=logging.LogRecord('uvicorn.access',20,'',0,'%s %s %s %s %s',('ip','GET','/api/github/callback?code=fixture-secret&state=fixture-state','1.1',200),None)
    routes.GithubCallbackLogFilter().filter(record)
    assert 'fixture-secret' not in record.getMessage() and 'fixture-state' not in record.getMessage()


def test_token_revocation_uses_single_token_endpoint_and_verifies_404(monkeypatch):
    calls=[]
    def handle(request):
        calls.append((request.method,request.url.path))
        return httpx.Response(204 if request.method=='DELETE' else 404)
    original=httpx.Client
    monkeypatch.setattr(github.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handle),**kw))
    cfg=NS(github_client_id='fixture',github_client_secret='synthetic')
    assert github.revoke_token('synthetic-token',cfg)=='verified'
    assert calls==[('DELETE','/applications/fixture/token'),('POST','/applications/fixture/token')]


def test_migration_is_additive_postgresql_ddl_only():
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from unittest.mock import patch
    module=importlib.import_module('backend.alembic.versions.0028_github_connection_identity')
    stream=io.StringIO();context=MigrationContext.configure(dialect_name='postgresql',opts={'as_sql':True,'output_buffer':stream})
    with Operations.context(context):module.upgrade()
    ddl=stream.getvalue()
    assert 'UNIQUE INDEX' in ddl and 'auth_session_id' in ddl
    assert not any(word in ddl.upper() for word in ['DROP TABLE','DELETE FROM','TRUNCATE TABLE'])


def test_three_gateway_accounts_have_separate_connections_and_pending_state(flow):
    f=flow;a,b=f.owners
    from backend.app.security.sessions import hash_session_token
    now=datetime.now(timezone.utc);cid=uuid.uuid4()
    with Session(f.engine) as db:
        db.get(models.User,a.id).role='admin'
        db.add(models.User(id=cid,username='fixture-c',email='fixture-c@example.invalid',password_hash='fixture',phone='synthetic-c',postal_code='00000',role='customer',status='active',trial_started_at=now,trial_ends_at=now+timedelta(days=1)))
        db.add(models.AuthSession(id=uuid.uuid4(),user_id=cid,token_hash=hash_session_token('fixture-token-c'),expires_at=now+timedelta(hours=1),last_seen_at=now));db.commit()
    c=NS(id=cid,name='c')
    f.callback(f.start(a),a,'A');assert f.confirm(a).status_code==200
    f.callback(f.start(b),b,'B');assert f.confirm(b).status_code==200
    assert not f.request('/api/github/status',c).json()['connected']
    assert f.request('/api/github/repositories',c).status_code==503
    assert f.pending(c) is None
    f.start(c);assert f.pending(a) is None and f.pending(b) is None
    assert f.request('/api/github/status',a).json()['connected']
    assert f.request('/api/github/status',b).json()['connected']


def test_installation_return_reauthenticates_same_actor_and_never_trusts_installation_id(flow,monkeypatch):
    f=flow;original=github._api
    first=True
    def vendor(method,path,**kw):
        if path=='/user/installations' and vendor.empty:return {'installations':[]}
        return original(method,path,**kw)
    vendor.empty=True;monkeypatch.setattr(github,'_api',vendor)
    f.callback(f.start());item=f.pending();assert item['installations']==[]
    response=f.request('/api/github/pending/install',method='POST',body={'connection_id':item['connection_id']})
    assert response.status_code==200,response.text
    setup=parse_qs(urlparse(response.json()['url']).query)['state'][0]
    bridge=f.callback(setup,code='',installation_id='901',setup_action='install')
    assert bridge.status_code==303
    oauth=parse_qs(urlparse(bridge.headers['location']).query)['state'][0]
    vendor.empty=False
    wrong=f.callback(oauth,code='B');assert wrong.headers['location'].endswith('account-conflict')
    assert not f.request('/api/github/status').json()['connected']
    assert 'token-B' in f.revoked


def test_expired_or_revoked_gateway_session_cannot_confirm(flow):
    f=flow;f.callback(f.start());item=f.pending()
    with Session(f.engine) as db:
        session=db.scalar(select(models.AuthSession).where(models.AuthSession.user_id==f.owners[0].id))
        session.revoked_at=datetime.now(timezone.utc);db.commit()
    response=f.request('/api/github/confirm',method='POST',body={'connection_id':item['connection_id'],'github_user_id':101,'installation_id':901})
    assert response.status_code==401
    with Session(f.engine) as db:assert not list(db.scalars(select(models.GithubConnection)))


def test_concurrent_identity_claim_rolls_back_before_state_deletion(flow,monkeypatch):
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.sql.dml import Delete
    f=flow;f.callback(f.start());item=f.pending()
    assert f.request('/api/github/pending/email/send',method='POST',body={'connection_id':item['connection_id'],'email':'github101@example.com'}).status_code==200
    assert f.request('/api/github/pending/email/verify',method='POST',body={'connection_id':item['connection_id'],'code':f.sent[-1]['code']}).status_code==200
    original=Session.execute
    def execute(self,statement,*args,**kw):
        if isinstance(statement,Delete) and statement.table.name=='github_auth_states':
            raise IntegrityError('synthetic race',{},Exception('synthetic unique constraint'))
        return original(self,statement,*args,**kw)
    monkeypatch.setattr(Session,'execute',execute)
    response=f.request('/api/github/confirm',method='POST',body={'connection_id':item['connection_id'],'github_user_id':101,'installation_id':901})
    assert response.status_code==409
    with Session(f.engine) as db:assert not list(db.scalars(select(models.GithubConnection)))


@pytest.fixture
def browser_flow(flow):
    # Existing flow fixture tests router/ORM ownership. These regressions must
    # additionally exercise the real production CSRF middleware over HTTPS.
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.app.main import browser_boundary
    app = FastAPI()
    app.middleware('http')(browser_boundary)
    app.include_router(routes.router)
    app.dependency_overrides.update(flow.client.app.dependency_overrides)
    with TestClient(app, base_url=flow.config.public_base_url) as client:
        yield NS(**{**vars(flow), 'client': client})


def test_callback_bridge_preserves_origin_without_referring_oauth_query(browser_flow):
    # HTML form navigation under no-referrer sends Origin:null in browsers.
    # Keep a real Origin and origin-only Referer; never exempt this route from CSRF.
    f = browser_flow
    state = f.start()
    page = f.client.get('/api/github/callback', params={'state': state, 'code': 'A'})
    assert '<meta name="referrer" content="strict-origin">' in page.text
    assert 'no-referrer' not in page.text
    assert page.text.index('history.replaceState') < page.text.index("document.getElementById('complete').submit()")
    response = f.client.post('/api/github/callback/complete',
        data={'state': state, 'code': 'A'}, follow_redirects=False,
        headers={'Cookie': f.config.session_cookie_name + '=fixture-token-' + f.owners[0].name,
                 'Origin': f.config.public_base_url, 'Referer': f.config.public_base_url + '/',
                 'Sec-Fetch-Site': 'same-origin'})
    assert response.status_code == 303
    assert response.headers['location'].endswith('github=confirm')
    assert f.pending()['github_user_id'] == 101
    assert not f.request('/api/github/status').json()['connected']


@pytest.mark.parametrize('origin,site', [('null', 'same-origin'),
    ('https://untrusted.invalid', 'cross-site'), ('https://untrusted.invalid', 'same-origin')])
def test_callback_bridge_does_not_bypass_cross_site_protection(browser_flow, origin, site):
    f = browser_flow
    state = f.start()
    response = f.client.post('/api/github/callback/complete',
        data={'state': state, 'code': 'A'}, follow_redirects=False,
        headers={'Cookie': f.config.session_cookie_name + '=fixture-token-' + f.owners[0].name,
                 'Origin': origin, 'Sec-Fetch-Site': site})
    assert response.status_code == 403
    assert response.json()['detail'] == 'Cross-site request denied'
    with Session(f.engine) as db:
        assert not db.get(models.GithubAuthState, state).consumed
    assert not f.vendor
    assert f.pending() is None
