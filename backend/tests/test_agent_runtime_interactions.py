"""Real OpenCode tools, with a deterministic loopback model (not external AI)."""
import json, os, threading, time, uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import pytest
from backend.tests.test_disposable_database import account

pytestmark=pytest.mark.skipif(os.getenv('AUDIT_DISPOSABLE_DB')!='1' or os.getenv('AUDIT_RUN_OPENCODE')!='1',reason='isolated database and OpenCode required')


def test_real_permission_and_question_wait_resume_reject(account):
    from backend.app.services import opencode, workspaces, policy
    from backend.app.database import SessionLocal
    from backend.app.models import Workspace, WorkspaceSession
    client,_,user,_=account
    mode={'tool':'bash','file':'approved.txt'}
    class Model(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if any(m.get('role')=='tool' for m in payload['messages']):
                delta={'content':'Fixture completed'};finish='stop'
            else:
                args={'command':'printf approved > '+mode['file'],'description':'Write disposable approval fixture'} if mode['tool']=='bash' else {'questions':[{'header':'Color','question':'Pick a color','options':[{'label':'Blue','description':'Fixture recommendation'},{'label':'Green','description':'Alternative'}],'multiple':True,'custom':True}]}
                delta={'tool_calls':[{'index':0,'id':'fixture_call','type':'function','function':{'name':mode['tool'],'arguments':json.dumps(args)}}]};finish='tool_calls'
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
            for change,end in [(dict(role='assistant'),None),(delta,None),({},finish)]:
                chunk={'id':'fixture','object':'chat.completion.chunk','created':1,'model':'fixture','choices':[{'index':0,'delta':change,'finish_reason':end}]}
                self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode())
            self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
    server=ThreadingHTTPServer(('127.0.0.1',0),Model);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    project=client.post('/api/projects',json={'project_name':'agent-fixture-'+uuid.uuid4().hex[:8]}).json()
    wid=uuid.UUID(project['workspace']['id'])
    with SessionLocal() as db:
        workspace=db.get(Workspace,wid);service=opencode.for_workspace(workspace,db=db)
    try:
        service.request('PATCH','/config',{'provider':{'fixture':{'npm':'@ai-sdk/openai','name':'Fixture','options':{'baseURL':f'http://127.0.0.1:{server.server_port}/v1','apiKey':'fixture-only'},'models':{'fixture':{'name':'Fixture','api':{'id':'fixture','url':f'http://127.0.0.1:{server.server_port}/v1','npm':'@ai-sdk/openai'},'limit':{'context':16000,'output':1000}}}}}})
        for tool,reply,filename in [('bash','once','approved.txt'),('bash','reject','rejected.txt'),('question',None,'unused.txt')]:
            mode.update(tool=tool,file=filename)
            native=service.request('POST','/session',{'title':'Fixture','permission':[{'permission':'*','pattern':'*','action':'ask'},{'permission':'external_directory','pattern':'*','action':'deny'}]})
            with SessionLocal() as db:
                session=WorkspaceSession(workspace_id=wid,user_id=uuid.UUID(user['id']),title='Fixture',opencode_session_id=native['id'],status='submitted');db.add(session);db.commit();sid=str(session.id)
            with ThreadPoolExecutor(max_workers=1) as pool:
                def submit():
                    response=service.client.request('POST',service.session_path(native['id'],'/message'),params=service.params,json={'model':{'providerID':'fixture','modelID':'fixture'},'parts':[{'type':'text','text':'Execute fixture'}]},timeout=60)
                    # Only this loopback fake-provider fixture is used here.
                    assert response.status_code==200,response.text[:2000]
                    return response.json()
                future=pool.submit(submit)
                endpoint='questions' if tool=='question' else 'permissions'
                deadline=time.monotonic()+25;pending=[]
                while time.monotonic()<deadline:
                    response=client.get(f'/api/sessions/{sid}/{endpoint}');assert response.status_code==200,response.text
                    pending=response.json().get('requests',[]) if tool=='question' else response.json()
                    if pending:break
                    if future.done():raise AssertionError('Execution finished before pending '+endpoint+': '+str(future.result()))
                    time.sleep(.15)
                assert pending, 'No native '+endpoint+' request'
                assert not future.done()
                assert not (workspaces.root_for(workspace)/filename).exists()
                # A fresh read reconnects to the same runtime-owned pending task.
                again=client.get(f'/api/sessions/{sid}/{endpoint}').json()
                assert (again['requests'] if tool=='question' else again)[0]['id']==pending[0]['id']
                if tool=='question':
                    answer=client.post(f'/api/sessions/{sid}/questions/{pending[0]["id"]}',json={'answers':[['Blue','custom fixture']]})
                else:
                    answer=client.post(f'/api/sessions/{sid}/permissions/{pending[0]["id"]}',json={'reply':reply})
                assert answer.status_code==200,answer.text
                completed=future.result(timeout=20)
                assert completed.get('info',{}).get('time',{}).get('completed'),completed
                assert (workspaces.root_for(workspace)/filename).exists()==(tool=='bash' and reply=='once')
    except Exception:
        from backend.app.config import settings
        context=settings.runtime_root/str(workspace.user_id)/str(workspace.id)
        for log in context.rglob('*.log'):
            lines=[line for line in log.read_text(errors='replace').splitlines() if 'ERROR' in line or 'error=' in line]
            if lines:print('DISPOSABLE FIXTURE ERROR', '\n'.join(lines[-3:]).replace(str(context),'[runtime]').replace(str(workspaces.root_for(workspace)),'[fixture-workspace]')[-3000:])
        raise
    finally:
        server.shutdown();server.server_close();opencode.stop_workspace(workspace)
