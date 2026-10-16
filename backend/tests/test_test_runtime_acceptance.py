"""Real native metadata/Todo/questions with loopback tools, no paid provider call."""
import json,os,time,uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from backend.tests.test_agent_runtime_interactions import account,agent_fixture_model
from backend.tests.test_gateway_agent_http import bridge_pool
pytestmark=pytest.mark.skipif(os.getenv('AUDIT_DISPOSABLE_DB')!='1' or os.getenv('AUDIT_RUN_OPENCODE')!='1',reason='isolated SQL/native OpenCode required')


@pytest.fixture(autouse=True)
def disable_external_catalog_refresh(monkeypatch):
    # Verified in the installed 1.18.32 binary: this flag disables populate
    # network fallback AND its hourly refresh fiber; bundled snapshot remains.
    # Fixture-only child env, not production configuration or a network bypass.
    from backend.app.services import opencode
    original=opencode.subprocess.Popen
    def spawn(args,*a,**kwargs):
        if 'serve' in args:
            kwargs['env']={**kwargs['env'],'OPENCODE_DISABLE_MODELS_FETCH':'true'}
        return original(args,*a,**kwargs)
    monkeypatch.setattr(opencode.subprocess,'Popen',spawn)


def test_real_provider_catalog_capacity_methods_and_warm_latency(account):
    from backend.app.services import opencode
    client,_,owner,_=account;uid=uuid.UUID(owner['id']);durations={}
    def get(path):
        started=time.perf_counter();r=client.get(path);elapsed=(time.perf_counter()-started)*1000
        assert r.status_code==200,(path,r.text)
        return r.json(),round(elapsed,2)
    try:
        initial,durations['cold_catalog_ms']=get('/api/opencode/catalog/providers')
        account_ref,service=opencode.for_account(uid);pid=opencode._runtimes[str(account_ref.id)].process.pid
        all_data=service._core_value('provider_data','/provider');ids={p['id'] for p in all_data['all']}
        reported={name: name in ids for name in ['deepseek','google','openai','togetherai']}
        assert all(reported.values()),reported
        seen=[];offset=0
        while offset is not None:
            page,_=get('/api/opencode/catalog/providers/page?limit=50&offset='+str(offset))
            seen.extend(p['id'] for p in page['items']);offset=page['next_offset']
        assert len(seen)==len(set(seen))==len(ids) and set(seen)==ids
        warm=[]
        for _ in range(3):_,ms=get('/api/opencode/catalog/providers');warm.append(ms)
        auth={}
        for name in reported:
            data,cold=get('/api/opencode/connections/'+name+'/options')
            again,warm_method=get('/api/opencode/connections/'+name+'/options')
            assert data['provider_id']==name and data['auth_methods'] and again==data
            auth[name]={'first_ms':cold,'warm_ms':warm_method,'methods':len(data['auth_methods'])}
        assert opencode._runtimes[str(account_ref.id)].process.pid==pid
        metrics={'environment':'disposable loopback Gateway TestClient + actual OpenCode 1.18.32; not TEST VPS',
                 'runtime_provider_count':len(ids),'initial_displayed_count':len(initial),'page_size':50,
                 'required_providers_reported':reported,**durations,'warm_catalog_ms':warm,
                 'auth_methods':auth,'upstream_ms':dict(service.timings),'frontend_browser_ms':None,
                 'targets_met_here':{'warm_catalog_under_2000ms':max(warm)<2000,'warm_methods_under_5000ms':max(a['warm_ms'] for a in auth.values())<5000}}
        if os.getenv('AUDIT_PROVIDER_PERF'):Path(os.environ['AUDIT_PROVIDER_PERF']).write_text(json.dumps(metrics,indent=2))
        print('PROVIDER_PERFORMANCE',json.dumps(metrics))
    finally:opencode.stop_workspace(opencode.account_workspace(uid))


def test_real_todo_updates_and_explicit_recommendation_continuation(account,agent_fixture_model,bridge_pool):
    from backend.app.database import SessionLocal
    from backend.app.models import Workspace,WorkspaceSession
    from backend.app.services import opencode
    client,login_data,owner,_=account;mode,_=agent_fixture_model
    created=client.post('/api/projects',json={'project_name':'todo-question-'+uuid.uuid4().hex[:8]});assert created.status_code==201
    wid=uuid.UUID(created.json()['workspace']['id'])
    with SessionLocal() as db:workspace=db.get(Workspace,wid);service=opencode.for_workspace(workspace,db=db)
    try:
        native=service.request('POST','/session',{'title':'Real task fixture','permission':[{'permission':'todowrite','pattern':'*','action':'allow'}]})
        with SessionLocal() as db:
            session=WorkspaceSession(workspace_id=wid,user_id=uuid.UUID(owner['id']),opencode_session_id=native['id'],title='Real task fixture',status='submitted');db.add(session);db.commit();sid=str(session.id)
        for statuses in [('completed','in_progress','pending','cancelled'),('completed','completed','completed','cancelled')]:
            tasks=[{'content':'Disposable task '+str(i),'status':state,'priority':'medium'} for i,state in enumerate(statuses)]
            mode.update(tool='todowrite',args={'todos':tasks})
            result=service.request('POST',service.session_path(native['id'],'/message'),{'model':{'providerID':'fixture','modelID':'fixture'},'parts':[{'type':'text','text':'Update fixture tasks'}]},30)
            assert result['info']['time']['completed']
            todo=client.get('/api/sessions/'+sid+'/todos');assert todo.status_code==200,todo.text
            assert [r['status'] for r in todo.json()['items']]==list(statuses)
        mode.update(tool='question',args={'questions':[{'header':'Test choice','question':'Choose a fixture','options':[{'label':'Blue (Recommended)','description':'Agent supplied explanation'},{'label':'Green','description':'Alternative'}],'multiple':False,'custom':True}]})
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(service.request,'POST',service.session_path(native['id'],'/message'),{'model':{'providerID':'fixture','modelID':'fixture'},'parts':[{'type':'text','text':'Ask a real fixture question'}]},30)
            end=time.monotonic()+15;requests=[]
            while time.monotonic()<end:
                response=client.get('/api/sessions/'+sid+'/questions');assert response.status_code==200,response.text
                requests=response.json()['requests']
                if requests:break
                time.sleep(.1)
            assert requests and not future.done()
            options=requests[0]['questions'][0]['options']
            assert options[0]['recommended'] is True and options[1]['recommended'] is False
            assert options[0]['description']=='Agent supplied explanation'
            path='/api/sessions/'+sid+'/questions/'+requests[0]['id']
            answer={'answers':[['Blue (Recommended)']]}
            assert client.post(path,json=answer).status_code==200
            assert future.result(timeout=15)['info']['time']['completed']
            assert client.post(path,json=answer).status_code==404
        # Login by username and email restores the same owned native conversation.
        for identity in [login_data['username'],login_data['email']]:
            assert client.post('/api/auth/logout').status_code==204
            signed=client.post('/api/auth/login',json={'identity':identity,'password':login_data['password']})
            assert signed.status_code==200,signed.text
            restored=client.get('/api/workspace-context',params={'workspace_id':str(wid),'session_id':sid})
            assert restored.status_code==200,restored.text
            assert restored.json()['workspace']['id']==str(wid) and restored.json()['session']['id']==sid
            history=client.get('/api/sessions/'+sid);assert history.status_code==200,history.text
            assert history.json()['runtime_id']==native['id']
    finally:opencode.stop_workspace(workspace)
