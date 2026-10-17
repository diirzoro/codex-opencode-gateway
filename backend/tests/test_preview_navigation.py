"""Owned preview routing regressions with real middleware/HTTP and mocked Worker."""
import os
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://test:test@127.0.0.1/test')
import base64
import uuid
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi import FastAPI,HTTPException
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from starlette.requests import Request
from backend.app.services import preview_runner
from backend.app.routes import workspaces
from backend.app.main import browser_boundary

WID=uuid.UUID('00000000-0000-0000-0000-000000000001')
PREFIX=f'/api/workspaces/{WID}/preview/live/'

@pytest.mark.parametrize('entry',['<head></head><a href="/nested/page">Go</a><script src="app.js"></script>', '<a href="nested/page">Go</a><link href="/style.css">'])
def test_base_inserted_once_after_root_links_rewritten(monkeypatch,entry):
    worker=Mock();worker.request.return_value={'status':200,'type':'text/html','body':base64.b64encode(entry.encode()).decode()}
    monkeypatch.setattr(preview_runner,'_worker',lambda:worker)
    response=preview_runner.fetch_asset(SimpleNamespace(id=WID),'/')
    body=response.body.decode()
    assert f'<base href="{PREFIX}">' in body
    assert PREFIX+'api/workspaces/' not in body
    if 'href="/nested/page"' in entry:assert f'href="{PREFIX}nested/page"' in body
    else:assert 'href="nested/page"' in body and f'href="{PREFIX}style.css"' in body
    assert response.headers['content-security-policy']=='sandbox allow-scripts'
    worker.request.assert_called_once_with('fetch',{'job_id':str(WID),'path':'/'})

@pytest.mark.parametrize('path',[PREFIX,PREFIX+'nested/page',PREFIX+'style.css'])
def test_real_middleware_allows_only_owned_sandboxed_response(monkeypatch,path):
    app=FastAPI();app.middleware('http')(browser_boundary)
    @app.get('/{path:path}')
    def endpoint(request:Request):
        request.state.owned_preview_response=True
        return HTMLResponse('<p>Preview</p>',headers={'Content-Security-Policy':'sandbox allow-scripts'})
    with TestClient(app) as client:response=client.get(path)
    assert response.status_code==200
    assert 'x-frame-options' not in response.headers
    assert response.headers['content-security-policy']=="sandbox allow-scripts; frame-ancestors 'self'"
    assert response.headers['referrer-policy']=='no-referrer'

@pytest.mark.parametrize('path,marker,csp,status',[
    ('/',True,'sandbox allow-scripts',200),
    ('/api/profile',True,'sandbox allow-scripts',200),
    (PREFIX,False,'sandbox allow-scripts',200),
    (PREFIX,False,'',401),
    (PREFIX,True,'',200),
])
def test_other_documents_and_denials_keep_frame_protection(path,marker,csp,status):
    app=FastAPI();app.middleware('http')(browser_boundary)
    @app.get('/{path:path}')
    def endpoint(request:Request):
        request.state.owned_preview_response=marker
        return HTMLResponse('Protected',status_code=status,headers={'Content-Security-Policy':csp})
    with TestClient(app) as client:response=client.get(path)
    assert response.headers['x-frame-options']=='DENY'


def test_live_route_marks_only_after_ownership_and_successful_fetch(monkeypatch):
    owner=SimpleNamespace(id='owner');db=Mock();workspace=SimpleNamespace(id=WID)
    request=Request({'type':'http','method':'GET','path':PREFIX+'nested/page','headers':[]})
    owned=Mock(return_value=workspace);monkeypatch.setattr(workspaces.manager,'owned',owned)
    fetch=Mock(return_value=HTMLResponse('OK'));monkeypatch.setattr(preview_runner,'fetch_asset',fetch)
    workspaces.workspace_preview_live(WID,'nested/page',request,owner,db)
    owned.assert_called_once_with(db,workspaces.Workspace,WID,'owner')
    fetch.assert_called_once_with(workspace,'/nested/page')
    assert request.state.owned_preview_response is True

@pytest.mark.parametrize('failure',['ownership','worker'])
def test_failed_route_never_marks_embedding_allowed(monkeypatch,failure):
    request=Request({'type':'http','method':'GET','path':PREFIX,'headers':[]})
    owned=Mock(side_effect=HTTPException(404,'Not found')) if failure=='ownership' else Mock(return_value=SimpleNamespace(id=WID))
    monkeypatch.setattr(workspaces.manager,'owned',owned)
    fetch=Mock(side_effect=HTTPException(503,'Worker unavailable'));monkeypatch.setattr(preview_runner,'fetch_asset',fetch)
    with pytest.raises(HTTPException):workspaces.workspace_preview_live(WID,'',request,SimpleNamespace(id='owner'),Mock())
    assert not getattr(request.state,'owned_preview_response',False)
    if failure=='ownership':fetch.assert_not_called()
