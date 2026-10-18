"""Fresh preview must stop the owned old container before staging current source."""
import os
from types import SimpleNamespace
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://test:test@127.0.0.1/test')
import pytest
from fastapi import HTTPException
from backend.app.services import preview_runner as runner,preview_snapshot
from backend.app.routes import workspaces as routes

@pytest.fixture
def setup(monkeypatch):
    calls=[]
    def request(operation,payload):
        calls.append((operation,payload))
        return {'state':{'status':'running','stop':'stopped','prepare':'ready','start':'running'}[operation]}
    monkeypatch.setattr(runner,'_worker',lambda:SimpleNamespace(request=lambda *args:request(*args)))
    monkeypatch.setattr(runner,'_job_id',lambda workspace:'owned-job')
    monkeypatch.setattr(runner,'launch_options',lambda workspace:{'framework':'node','profile_available':True,'argv':['node','server.js']})
    monkeypatch.setattr(preview_snapshot,'export',lambda workspace,spool:spool.write(b'current owned snapshot'))
    return calls,request


def test_default_start_still_reuses_owned_running_preview(setup):
    calls,_=setup
    assert runner.start(object())['reused'] is True
    assert [op for op,_ in calls]==['status']


def test_explicit_fresh_start_stages_current_snapshot_after_confirmed_stop(setup):
    import base64
    calls,_=setup
    result=runner.start(object(),fresh=True)
    assert result['state']=='running' and not result.get('reused')
    assert [op for op,_ in calls]==['status','stop','prepare','start']
    assert all(payload['job_id']=='owned-job' for _,payload in calls)
    assert base64.b64decode(calls[2][1]['archive'])==b'current owned snapshot'


def test_unconfirmed_stop_prevents_snapshot_replacement_and_launch(setup,monkeypatch):
    calls,original=setup
    def request(operation,payload):
        if operation=='stop':calls.append((operation,payload));return {'state':'running'}
        return original(operation,payload)
    monkeypatch.setattr(runner,'_worker',lambda:SimpleNamespace(request=request))
    with pytest.raises(HTTPException) as error:runner.start(object(),fresh=True)
    assert error.value.status_code==503
    assert [op for op,_ in calls]==['status','stop']


def test_fresh_route_keeps_owned_workspace_guard(monkeypatch):
    calls=[];workspace=object()
    monkeypatch.setattr(routes.manager,'owned',lambda db,model,wid,uid:calls.append(('owned',wid,uid)) or workspace)
    monkeypatch.setattr(runner,'start',lambda selected,**kw:calls.append(('start',selected,kw)) or {'state':'running'})
    routes.workspace_preview_start('workspace',SimpleNamespace(id='owner'),object(),fresh=True)
    assert calls==[('owned','workspace','owner'),('start',workspace,{'fresh':True})]


def test_foreign_workspace_denied_before_start(monkeypatch):
    def denied(*args):raise HTTPException(403,'Forbidden')
    monkeypatch.setattr(routes.manager,'owned',denied)
    monkeypatch.setattr(runner,'start',lambda *args,**kw:pytest.fail('must not start'))
    with pytest.raises(HTTPException):routes.workspace_preview_start('foreign',SimpleNamespace(id='owner'),object(),fresh=True)
