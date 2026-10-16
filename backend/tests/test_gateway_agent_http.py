"""Gateway HTTP dispatch, native waiting tools and replay, with loopback model."""
import asyncio, json, os, socket, threading, time, uuid
from pathlib import Path
from datetime import datetime,timedelta,timezone
import httpx,pytest,uvicorn
from sqlalchemy import select
from backend.tests.test_agent_runtime_interactions import account,agent_fixture_model
pytestmark=pytest.mark.skipif(os.getenv('AUDIT_DISPOSABLE_DB')!='1' or os.getenv('AUDIT_RUN_OPENCODE')!='1',reason='isolated database/OpenCode required')



@pytest.fixture
def bridge_pool():
    # PGlite multiplexes one backend; concurrent rollback protocol is not
    # PostgreSQL. Serialize only this fixture, without changing app defaults.
    from sqlalchemy import create_engine
    from backend.app.database import SessionLocal
    from backend.app.config import settings
    if os.getenv('AUDIT_DB_ENGINE')!='pglite':
        yield;return
    original=SessionLocal.kw['bind']
    bounded=create_engine(settings.database_url,pool_size=1,max_overflow=0,pool_timeout=3,pool_pre_ping=True)
    SessionLocal.configure(bind=bounded)
    try:yield
    finally:SessionLocal.configure(bind=original);bounded.dispose()


def test_gateway_dispatch_wait_resume_isolation_and_event_replay(account,agent_fixture_model,bridge_pool):
    from backend.app.main import app
    from backend.app.database import SessionLocal
    from backend.app.models import User,AuthSession,Workspace,ExecutionEvent
    from backend.app.config import settings
    from backend.app.security.sessions import new_session_token
    from backend.app.services import opencode,workspaces
    original,_,owner,_=account;mode,_=agent_fixture_model
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,lifespan='off',log_level='error'))
    thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
    client=httpx.Client(base_url=f'http://127.0.0.1:{port}',cookies=dict(original.cookies),trust_env=False,timeout=8)
    raw,hashed=new_session_token();now=datetime.now(timezone.utc)
    with SessionLocal() as db:
        other=User(username='foreign_'+uuid.uuid4().hex[:12],email=uuid.uuid4().hex+'@example.org',password_hash='fixture',phone='',postal_code='',trial_started_at=now,trial_ends_at=now+timedelta(days=30));db.add(other);db.flush()
        db.add(AuthSession(user_id=other.id,token_hash=hashed,expires_at=now+timedelta(hours=1)));db.commit()
    foreign=httpx.Client(base_url=client.base_url,cookies={settings.session_cookie_name:raw},trust_env=False,timeout=5)
    workspace=None
    def until(path,predicate,timeout=12):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            response=client.get(path);assert response.status_code==200,response.text
            value=response.json()
            if predicate(value):return value
            time.sleep(.1)
        raise AssertionError('Timed out waiting for '+path)
    try:
        deadline=time.monotonic()+5
        while not server.started and time.monotonic()<deadline:time.sleep(.05)
        assert client.get('/api/health').status_code==200
        project=client.post('/api/projects',json={'project_name':'http-agent-'+uuid.uuid4().hex[:8]});assert project.status_code==201,project.text
        wid=project.json()['workspace']['id']
        opened=client.post(f'/api/workspaces/{wid}/sessions',json={'title':'HTTP lifecycle'});assert opened.status_code==201,opened.text
        sid=opened.json()['id'];base=f'/api/sessions/{sid}'
        with SessionLocal() as db:workspace=db.get(Workspace,uuid.UUID(wid))
        expected_text=0
        for index,(tool,reply,filename) in enumerate([('question',None,'question.txt'),('bash','once','http-approved.txt'),('bash','reject','http-rejected.txt'),('question',None,'single.txt')]):
            mode.update(tool=tool,file=filename,multiple=index!=3)
            rid=str(uuid.uuid4());payload={'request_id':rid,'text':f'Fixture turn {index}','provider_id':'fixture','model_id':'fixture'}
            sent=client.post(base+'/messages',json=payload);assert sent.status_code==202,sent.text
            endpoint='questions' if tool=='question' else 'permissions'
            pending=until(base+'/'+endpoint,lambda x:bool(x['requests'] if tool=='question' else x))
            request=(pending['requests'] if tool=='question' else pending)[0]
            assert not (workspaces.root_for(workspace)/filename).exists()
            replay=client.post(base+'/messages',json=payload);assert replay.status_code==202 and replay.json()['replayed'] is True
            assert client.post(base+'/messages',json={**payload,'request_id':str(uuid.uuid4())}).status_code==409
            # Simulate page reload through a separate authenticated HTTP client.
            with httpx.Client(base_url=client.base_url,cookies=dict(original.cookies),trust_env=False) as refreshed:
                same=refreshed.get(base+'/'+endpoint).json()
                assert (same['requests'] if tool=='question' else same)[0]['id']==request['id']
            target=base+'/'+endpoint+'/'+request['id'];body={'answers':[['Blue','custom fixture'] if mode['multiple'] else ['Green']]} if tool=='question' else {'reply':reply}
            assert foreign.get(base+'/'+endpoint).status_code==404
            assert foreign.post(target,json=body).status_code==404
            if tool=='bash':
                # Allow the actual activity observer a cycle while execution waits.
                time.sleep(2.1)
                assert not (workspaces.root_for(workspace)/filename).exists()
            answered=client.post(target,json=body);assert answered.status_code==200,answered.text
            until(base+'/submissions/'+rid,lambda x:x['status'] in {'completed','failed'})
            result=client.get(base+'/submissions/'+rid).json();assert result['status']=='completed',result
            messages=client.get(base+'/messages').json()
            assert len([m for m in messages if m['role']=='user'])==index+1
            assert len({m['id'] for m in messages})==len(messages)
            # OpenCode keeps legitimate tool-only assistant steps as separate
            # rows. Verify exactly one final text reply per turn, not that the
            # native list's last row must be text.
            expected_text+=reply!='reject'
            assert sum(m['role']=='assistant' and m['text']=='Fixture completed' for m in messages)==expected_text
            if reply=='reject':assert any(a['status']=='error' for m in messages for a in m.get('activity',[]))
            if os.getenv('AUDIT_AGENT_EVIDENCE'):
                runtime=opencode._runtimes[str(workspace.id)].service
                native_rows=runtime.request('GET',runtime.session_path(opened.json().get('runtime_id') or client.get(base).json()['runtime_id'],'/message'))
                evidence={'turn':index,'gateway_origin':str(client.base_url),'opencode_origin':str(runtime.client.base_url),'messages':[{'role':r['info']['role'],'id':r['info']['id'],'parent':r['info'].get('parentID'),'created':r['info'].get('time',{}).get('created'),'text_lengths':[len(p.get('text','')) for p in r.get('parts',[]) if p.get('type')=='text']} for r in native_rows]}
                with Path(os.environ['AUDIT_AGENT_EVIDENCE']).open('a') as output:output.write(json.dumps(evidence)+'\n')
            assert (workspaces.root_for(workspace)/filename).exists()==(tool=='bash' and reply=='once')
        with SessionLocal() as db:
            events=list(db.scalars(select(ExecutionEvent).where(ExecutionEvent.session_id==uuid.UUID(sid)).order_by(ExecutionEvent.id)))
            assert any(e.kind=='activity' for e in events)
            assert sum(e.kind=='submission' for e in events)==4
        def replay_events(after=0):
            ids=[];kinds=[]
            with client.stream('GET',base+'/events',params={'after':0},headers={'Last-Event-ID':str(after)},timeout=3) as stream:
                assert stream.status_code==200
                for line in stream.iter_lines():
                    if line.startswith('id: '):ids.append(int(line[4:]))
                    if line.startswith('event: '):
                        kinds.append(line[7:])
                        if line[7:]=='completed':break
            return ids,kinds
        ids,kinds=replay_events();assert ids==sorted(set(ids)) and 'submission' in kinds
        newer,more_kinds=replay_events(ids[-1]);assert newer and min(newer)>ids[-1] and 'activity' in more_kinds
        with client.stream('GET',base+'/events',params={'after':events[-1].id},timeout=3) as stream:
            assert stream.status_code==200
            assert client.post('/api/auth/logout').status_code in {200,204}
            assert any(line=='event: authentication_expired' for line in stream.iter_lines())
    finally:
        if workspace is not None:opencode.stop_workspace(workspace)
        client.close();foreign.close();server.should_exit=True;thread.join(timeout=5);sock.close()
