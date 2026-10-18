"""Encrypted read grants and real middleware/HTTP; no vendor, Docker or live DB."""
import base64
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from types import SimpleNamespace
import uuid
from unittest.mock import Mock
import pytest
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://test:test@127.0.0.1/test')
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request
from backend.app.services import preview_access as access, preview_runner
from backend.app.routes import preview_public
from backend.app.main import browser_boundary
from backend.app.database import get_db

LEASE='a'*64
GATEWAY='https://gateway.example'
PREVIEW='https://preview.example'

@pytest.fixture
def context(monkeypatch):
    now=datetime.now(timezone.utc)
    uid,wid,pid,sid=[uuid.uuid4() for _ in range(4)]
    user=SimpleNamespace(id=uid,status='active',password_hash='hash')
    session=SimpleNamespace(id=sid,user_id=uid,user=user,revoked_at=None,
        last_seen_at=now,created_at=now,expires_at=now+timedelta(hours=1))
    project=SimpleNamespace(id=pid,user_id=uid,archived_at=None)
    workspace=SimpleNamespace(id=wid,project_id=pid,user_id=uid,status='ready',project=project)
    monkeypatch.setattr(access,'settings',SimpleNamespace(public_base_url=GATEWAY,credentials_encryption_key='test-only-master-key'))
    monkeypatch.setenv('PREVIEW_PUBLIC_ORIGIN',PREVIEW)
    worker=Mock()
    def operation(op,payload):
        assert payload['job_id']==str(wid)
        if op=='status':return {'state':'running','browser_lease':LEASE}
        assert op=='fetch'
        mime,body = ('text/css',b'body{color:green}') if payload['path'].endswith('.css') else ('text/javascript',b'window.previewCounter=1') if payload['path'].endswith('.js') else ('text/html',b'<head></head><link href="/style.css"><a href="/nested/page">Next</a>')
        return {'status':200,'type':mime,'body':base64.b64encode(body).decode()}
    worker.request.side_effect=operation
    monkeypatch.setattr(preview_runner,'_worker',lambda:worker)
    owned=Mock(return_value=workspace);monkeypatch.setattr(access.workspaces,'owned',owned)
    db=Mock();db.get.return_value=session
    return SimpleNamespace(now=now,user=user,session=session,workspace=workspace,db=db,worker=worker,owned=owned)


def request(url=None):
    from starlette.datastructures import URL
    return SimpleNamespace(url=URL(url or PREVIEW+'/preview/placeholder/'))


def grant(c):
    data=access.mint(c.workspace,c.session,c.user,now=c.now)
    return data, data['url'].split('/preview/',1)[1].split('/')[0]


def test_valid_cross_site_grant_requires_no_account_cookie(context):
    c=context;data,token=grant(c)
    assert all(str(value) not in token for value in (c.user.id,c.session.id,c.workspace.id))
    workspace,gateway,lease=access.authorize(token,request(data['url']),c.db,now=c.now)
    assert workspace is c.workspace and gateway==GATEWAY and lease==LEASE
    assert data['read_only'] is True and data['expires_at']<=int(c.now.timestamp())+300
    c.db.commit.assert_not_called()


@pytest.mark.parametrize('change',['expired','revoked','idle','inactive','foreign-session','foreign-workspace','foreign-project','archived-project','expired-workspace','changed-lease','stopped'])
def test_every_asset_rechecks_session_tenant_lifecycle_and_worker(context,change,monkeypatch):
    c=context;data,token=grant(c);at=c.now
    if change=='expired':at=c.now+timedelta(seconds=301)
    elif change=='revoked':c.session.revoked_at=c.now
    elif change=='idle':c.session.last_seen_at=c.now-timedelta(minutes=16)
    elif change=='inactive':c.user.status='archived'
    elif change=='foreign-session':c.session.user_id=uuid.uuid4()
    elif change=='foreign-workspace':c.workspace.user_id=uuid.uuid4()
    elif change=='foreign-project':c.workspace.project_id=uuid.uuid4()
    elif change=='archived-project':c.workspace.project.archived_at=c.now
    elif change=='expired-workspace':c.workspace.status='cache_expired'
    elif change=='changed-lease':monkeypatch.setattr(access,'_lease',lambda w:'b'*64)
    elif change=='stopped':monkeypatch.setattr(access,'_lease',Mock(side_effect=HTTPException(409,'Stopped')))
    with pytest.raises(HTTPException):access.authorize(token,request(data['url']),c.db,now=at)


@pytest.mark.parametrize('change',['signature','purpose','audience','workspace-id','session-id','deadline'])
def test_tampering_and_wrong_scope_fail_closed(context,change):
    c=context;data,token=grant(c)
    if change=='signature':token=token[:-5]+'wrong'
    else:
        raw=json.loads(access._cipher().decrypt(token.encode()))
        key,value={'purpose':('purpose','credentials'),'audience':('origin',GATEWAY),
            'workspace-id':('wid','../other'),'session-id':('sid','invalid'),
            'deadline':('expires',int(c.now.timestamp())-1)}[change]
        raw[key]=value
        token=access._cipher().encrypt(json.dumps(raw).encode()).decode()
    with pytest.raises(HTTPException) as err:access.authorize(token,request(data['url']),c.db,now=c.now)
    assert err.value.status_code==401


@pytest.mark.parametrize('origin',['',GATEWAY,'http://preview.example','https://user:pass@preview.example','https://preview.example/path','https://preview.example:8080','https://preview.example?secret=x'])
def test_configuration_never_falls_back_to_account_origin(context,monkeypatch,origin):
    monkeypatch.setenv('PREVIEW_PUBLIC_ORIGIN',origin)
    with pytest.raises(HTTPException) as err:access.mint(context.workspace,context.session,context.user)
    assert err.value.status_code==503
    context.worker.request.assert_not_called()


def test_old_worker_fails_closed_until_lease_support_installed(context):
    c=context;c.worker.request.side_effect=lambda *a:{'state':'running'}
    with pytest.raises(HTTPException) as err:grant(c)
    assert 'browser-lease' in err.value.detail


def test_missing_encryption_key_never_creates_unprotected_grant(context):
    access.settings.credentials_encryption_key=None
    with pytest.raises(HTTPException) as err:grant(context)
    assert err.value.status_code==503


def app_for(c):
    app=FastAPI();app.middleware('http')(browser_boundary);app.include_router(preview_public.router)
    app.dependency_overrides[get_db]=lambda:c.db
    @app.get('/api/auth/me')
    def sensitive():return {'NEVER':'ACCOUNT-DATA'}
    @app.get('/')
    def login():return {'NEVER':'LOGIN'}
    return app


def test_real_http_assets_and_nested_links_use_only_separate_read_grant(context):
    c=context;data,token=grant(c)
    app=app_for(c)
    with TestClient(app,base_url=PREVIEW) as client:
        for tail in ('','style.css','app.js','nested/page?x=1&x=2'):
            response=client.get('/preview/'+token+'/'+tail,headers={'Sec-Fetch-Site':'cross-site'})
            assert response.status_code==200
            assert 'set-cookie' not in response.headers and 'x-frame-options' not in response.headers
            assert response.headers['access-control-allow-origin']=='*'
            assert 'access-control-allow-credentials' not in response.headers
            assert response.headers['content-security-policy']=="sandbox allow-scripts; frame-ancestors "+GATEWAY
            assert response.headers['referrer-policy']=='no-referrer' and response.headers['cache-control']=='no-store'
            if tail.endswith('.css'):assert response.headers['content-type'].startswith('text/css') and 'color:green' in response.text
            elif tail.endswith('.js'):assert response.headers['content-type'].startswith('text/javascript') and 'previewCounter' in response.text
            else:assert '/preview/'+token+'/nested/page' in response.text
        assert c.worker.request.call_args.args[1]['path']=='/nested/page?x=1&x=2'
        assert c.worker.request.call_args.args[1]['browser_lease']==LEASE
    assert all(call.args[0] in {'status','fetch'} for call in c.worker.request.call_args_list)


@pytest.mark.parametrize('path,method',[('/','GET'),('/api/auth/me','GET'),('/api/workspaces/any/preview/start','POST'),('/preview/fake/','POST')])
def test_preview_host_never_serves_account_apis_or_writes(context,path,method):
    with TestClient(app_for(context),base_url=PREVIEW) as client:
        response=client.request(method,path)
    assert response.status_code==404 and 'NEVER' not in response.text


def test_grant_rejected_on_gateway_host_without_weakening_other_responses(context):
    data,token=grant(context)
    with TestClient(app_for(context),base_url=GATEWAY) as client:
        denied=client.get('/preview/'+token+'/')
        normal=client.get('/api/auth/me')
    assert denied.status_code==404 and denied.headers['x-frame-options']=='DENY'
    assert normal.status_code==200 and normal.headers['x-frame-options']=='DENY'


def test_access_log_redacts_bearer_path(context):
    data,token=grant(context)
    record=logging.LogRecord('uvicorn.access',20,'',0,'%s - "%s %s HTTP/1.1" %s',('127.0.0.1','GET','/preview/'+token+'/nested/page?private=query',200),None)
    for item in logging.getLogger('uvicorn.access').filters:item.filter(record)
    assert token not in record.getMessage() and '[redacted]' in record.getMessage()
    assert 'private=query' not in record.getMessage()


def test_grant_cannot_extend_original_login_idle_deadline(context):
    c=context;c.session.last_seen_at=c.now-timedelta(minutes=14)
    data,token=grant(c)
    assert data['expires_at']<=int(c.now.timestamp())+60
    with pytest.raises(HTTPException):access.authorize(token,request(data['url']),c.db,now=c.now+timedelta(seconds=61))



def test_unknown_or_deleted_session_never_reaches_worker(context):
    c=context;data,token=grant(c);c.worker.request.reset_mock();c.db.get.return_value=None
    with pytest.raises(HTTPException) as err:access.authorize(token,request(data['url']),c.db)
    assert err.value.status_code==401;c.worker.request.assert_not_called()


def test_public_head_is_read_only_and_returns_no_body(context):
    c=context;data,token=grant(c)
    with TestClient(app_for(c),base_url=PREVIEW) as client:
        response=client.head('/preview/'+token+'/')
    assert response.status_code==200 and response.content==b''
    assert 'set-cookie' not in response.headers


def test_expired_public_grant_does_not_fetch_or_relax_account_framing(context):
    c=context;_,token=grant(c)
    c.session.revoked_at=c.now;c.worker.request.reset_mock()
    with TestClient(app_for(c),base_url=PREVIEW) as client:
        response=client.get('/preview/'+token+'/app.js')
    assert response.status_code==401 and response.headers['x-frame-options']=='DENY'
    c.worker.request.assert_not_called()



def test_bad_same_host_configuration_cannot_hide_gateway_login(context,monkeypatch):
    monkeypatch.setenv('PREVIEW_PUBLIC_ORIGIN',GATEWAY)
    with TestClient(app_for(context),base_url=GATEWAY) as client:
        response=client.get('/api/auth/me')
    assert response.status_code==200 and response.json()=={'NEVER':'ACCOUNT-DATA'}



def test_redaction_preserves_real_uvicorn_access_formatter(context):
    from uvicorn.logging import AccessFormatter
    _,token=grant(context)
    record=logging.LogRecord('uvicorn.access',20,'',0,'%s - "%s %s HTTP/%s" %d',
        ('127.0.0.1:1234','GET','/preview/'+token+'/nested/page?private=query','1.1',200),None)
    for item in logging.getLogger('uvicorn.access').filters:item.filter(record)
    assert len(record.args)==5
    line=AccessFormatter(use_colors=False).format(record)
    assert token not in line and 'private=query' not in line and '200' in line
