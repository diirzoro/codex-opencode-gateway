"""Real process loss, persisted history and safe non-resumption of lost tools."""
import json,os,time,uuid
from concurrent.futures import ThreadPoolExecutor
import pytest
from backend.tests.test_agent_runtime_interactions import account,agent_fixture_model
from backend.tests.test_gateway_agent_http import bridge_pool
pytestmark=pytest.mark.skipif(os.getenv('AUDIT_DISPOSABLE_DB')!='1' or os.getenv('AUDIT_RUN_OPENCODE')!='1',reason='disposable SQL and native OpenCode required')


@pytest.mark.parametrize('tool',['bash','question'])
def test_restart_marks_lost_pending_execution_failed_without_replay(account,agent_fixture_model,bridge_pool,tool):
    from backend.app.database import SessionLocal
    from backend.app.models import Workspace,WorkspaceSession,ExecutionEvent
    from backend.app.services import opencode,workspaces,session_lifecycle
    client,_,user,_=account;mode,_=agent_fixture_model
    mode.update(tool=tool,file='must-not-execute.txt')
    created=client.post('/api/projects',json={'project_name':'restart-'+uuid.uuid4().hex[:8]});assert created.status_code==201
    wid=uuid.UUID(created.json()['workspace']['id'])
    with SessionLocal() as db:
        workspace=db.get(Workspace,wid);service=opencode.for_workspace(workspace,db=db)
    pool=ThreadPoolExecutor(max_workers=1)
    try:
        native=service.request('POST','/session',{'title':'Persisted fixture','permission':[{'permission':'*','pattern':'*','action':'ask'}]})
        rid=str(uuid.uuid4());mid=session_lifecycle.new_message_id()
        with SessionLocal() as db:
            row=WorkspaceSession(workspace_id=wid,user_id=uuid.UUID(user['id']),title='Persisted fixture',opencode_session_id=native['id'],status='submitted');db.add(row);db.flush();sid=str(row.id)
            db.add_all([ExecutionEvent(session_id=row.id,kind='submission',data=json.dumps({'request_id':rid,'message_id':mid})),ExecutionEvent(session_id=row.id,kind='dispatch',data=json.dumps({'request_id':rid,'message_id':mid,'generation':service.generation}))]);db.commit()
        future=pool.submit(service.request,'POST',service.session_path(native['id'],'/message'),{'messageID':mid,'model':{'providerID':'fixture','modelID':'fixture'},'parts':[{'type':'text','text':'Wait for explicit fixture decision'}]},30)
        path='/question' if tool=='question' else '/permission';deadline=time.monotonic()+15;pending=[]
        while time.monotonic()<deadline:
            pending=service.request('GET',path)
            if pending:break
            assert not future.done()
            time.sleep(.1)
        assert pending and not future.done()
        before=service.request('GET',service.session_path(native['id'],'/message'))
        assert any(r['info']['id']==mid for r in before)
        opencode._runtimes[str(wid)].process.kill();opencode._runtimes[str(wid)].process.wait(timeout=5)
        with pytest.raises(Exception):future.result(timeout=5)
        # The Gateway worker was lost: there is no local task to finish this
        # durable dispatch. Only the actual OpenCode process is restarted here.
        response=client.get('/api/sessions/'+sid);assert response.status_code==200,response.text
        assert response.json()['execution_status']=='failed',response.json()
        new=opencode._runtimes[str(wid)].service
        assert new.generation!=service.generation
        after=new.request('GET',new.session_path(native['id'],'/message'))
        assert {r['info']['id'] for r in before}.issubset({r['info']['id'] for r in after})
        assert sum(r['info']['role']=='user' for r in after)==1
        endpoint='questions' if tool=='question' else 'permissions'
        stale=client.post(f'/api/sessions/{sid}/{endpoint}/{pending[0]["id"]}',json={'answers':[['Blue']]} if tool=='question' else {'reply':'once'})
        assert stale.status_code==404,stale.text
        assert not (workspaces.root_for(workspace)/'must-not-execute.txt').exists()
        assert client.get('/api/sessions/'+sid).json()['execution_status']=='failed'
        with SessionLocal() as db:
            events=list(db.query(ExecutionEvent).filter_by(session_id=uuid.UUID(sid),kind='runtime_interrupted'))
            assert len(events)==1
    finally:
        opencode.stop_workspace(workspace);pool.shutdown(wait=True,cancel_futures=True)


def test_completed_native_turn_is_reconciled_after_observer_loss(account,agent_fixture_model,bridge_pool):
    from backend.app.database import SessionLocal
    from backend.app.models import Workspace,WorkspaceSession,ExecutionEvent
    from backend.app.services import opencode,session_lifecycle
    client,_,user,_=account;mode,_=agent_fixture_model;mode.update(tool='question',multiple=False)
    created=client.post('/api/projects',json={'project_name':'finished-'+uuid.uuid4().hex[:8]});assert created.status_code==201
    wid=uuid.UUID(created.json()['workspace']['id'])
    with SessionLocal() as db:workspace=db.get(Workspace,wid);service=opencode.for_workspace(workspace,db=db)
    try:
        native=service.request('POST','/session',{'title':'Completed history'})
        rid=str(uuid.uuid4());mid=session_lifecycle.new_message_id()
        with SessionLocal() as db:
            row=WorkspaceSession(workspace_id=wid,user_id=uuid.UUID(user['id']),title='Completed history',opencode_session_id=native['id'],status='submitted');db.add(row);db.flush();sid=str(row.id)
            db.add_all([ExecutionEvent(session_id=row.id,kind='submission',data=json.dumps({'request_id':rid,'message_id':mid})),ExecutionEvent(session_id=row.id,kind='dispatch',data=json.dumps({'request_id':rid,'message_id':mid,'generation':service.generation}))]);db.commit()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(service.request,'POST',service.session_path(native['id'],'/message'),{'messageID':mid,'model':{'providerID':'fixture','modelID':'fixture'},'parts':[{'type':'text','text':'Complete fixture'}]},30)
            deadline=time.monotonic()+15;pending=[]
            while time.monotonic()<deadline:
                pending=service.request('GET','/question')
                if pending:break
                time.sleep(.1)
            assert pending
            # Native still has a waiter: Gateway must preserve BUSY, not cancel it.
            assert client.get('/api/sessions/'+sid).json()['execution_status']=='submitted'
            assert service.request('POST','/question/'+pending[0]['id']+'/reply',{'answers':[['Blue']]}) is True
            assert future.result(timeout=15)['info']['time']['completed']
        opencode.stop_workspace(workspace)
        response=client.get('/api/sessions/'+sid);assert response.status_code==200,response.text
        assert response.json()['execution_status']=='completed'
        service=opencode._runtimes[str(wid)].service
        messages=service.request('GET',service.session_path(native['id'],'/message'))
        assert sum(m['info']['role']=='user' for m in messages)==1
        assert sum(p.get('text')=='Fixture completed' for m in messages for p in m['parts'])==1
    finally:opencode.stop_workspace(workspace)


def test_live_native_waiter_survives_busy_credential_sync_and_idle_retry(account,agent_fixture_model,bridge_pool):
    from backend.app.database import SessionLocal
    from backend.app.models import Workspace,WorkspaceSession,UserProviderCredential
    from backend.app.services import opencode,account_provider_sync as sync,credentials
    client,_,user,_=account;mode,_=agent_fixture_model;mode.update(tool='question',multiple=False)
    uid=uuid.UUID(user['id'])
    with SessionLocal() as db:
        credential=UserProviderCredential(user_id=uid,provider_id='fixture',ciphertext=credentials.encrypt('old-fixture-key'),last4='');db.add(credential);db.commit();cid=credential.id
    created=client.post('/api/projects',json={'project_name':'live-sync-'+uuid.uuid4().hex[:8]});assert created.status_code==201
    wid=uuid.UUID(created.json()['workspace']['id'])
    with SessionLocal() as db:workspace=db.get(Workspace,wid);service=opencode.for_workspace(workspace,db=db)
    try:
        native=service.request('POST','/session',{'title':'Live sync waiter'})
        with SessionLocal() as db:
            session=WorkspaceSession(workspace_id=wid,user_id=uid,title='Live sync waiter',opencode_session_id=native['id'],status='submitted');db.add(session);db.commit();sid=session.id
        runtime=opencode._runtimes[str(wid)];pid=runtime.process.pid
        auth=opencode.settings.runtime_root/str(uid)/str(wid)/'data/opencode/auth.json'
        before=auth.read_bytes();disposals=service.call_counts.get('POST /instance/dispose',0)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(service.request,'POST',service.session_path(native['id'],'/message'),{'model':{'providerID':'fixture','modelID':'fixture'},'parts':[{'type':'text','text':'Wait while account credential changes'}]},30)
            deadline=time.monotonic()+15;pending=[]
            while time.monotonic()<deadline:
                pending=service.request('GET','/question')
                if pending:break
                time.sleep(.1)
            assert pending and not future.done()
            with SessionLocal() as db:db.get(UserProviderCredential,cid).ciphertext=credentials.encrypt('new-fixture-key');db.commit()
            sync.sweep()
            assert auth.read_bytes()==before
            assert service.call_counts.get('POST /instance/dispose',0)==disposals
            assert runtime.process.pid==pid and runtime.process.poll() is None
            assert service.request('GET','/question')[0]['id']==pending[0]['id'] and not future.done()
            assert client.post(f'/api/sessions/{sid}/questions/{pending[0]["id"]}',json={'answers':[['Blue']]}).status_code==200
            assert future.result(timeout=15)['info']['time']['completed']
        with SessionLocal() as db:db.get(WorkspaceSession,sid).status='completed';db.commit()
        sync.sweep()
        assert json.loads(auth.read_text())['fixture']['key']=='new-fixture-key'
        assert service.call_counts.get('POST /instance/dispose',0)>disposals
        assert runtime.process.pid==pid and runtime.process.poll() is None
    finally:opencode.stop_workspace(workspace)
