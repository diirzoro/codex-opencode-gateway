"""Disposable-only runtime inventory and ONE bounded Agent diagnostic request.

Run through run_isolated_audit.py --diagnose-agent. Never load production .env.
"""
import json, os, socket, subprocess, sys, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

assert os.environ.get('AUDIT_DISPOSABLE_DB')=='1'
assert urlsplit(os.environ['DATABASE_URL']).hostname=='127.0.0.1'
import httpx
from sqlalchemy import text
from backend.app.config import settings
from backend.app.database import SessionLocal
from backend.app.services import opencode

observed=[]
class Model(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
        self.wfile.write(json.dumps({'status':'ready','data':[{'id':'fixture','object':'model'}]}).encode())
    def do_POST(self):
        data=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
        observed.append({'path':self.path,'fields':sorted(data),'stream':data.get('stream'),'tool_count':len(data.get('tools',[]))})
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
        for delta,finish in [({'role':'assistant'},None),({'content':'Fixture connection ready'},None),({},'stop')]:
            self.wfile.write(('data: '+json.dumps({'id':'fixture','object':'chat.completion.chunk','created':1,'model':'fixture','choices':[{'index':0,'delta':delta,'finish_reason':finish}]})+'\n\n').encode())
        self.wfile.write(b'data: [DONE]\n\n')


def port():
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]

model=ThreadingHTTPServer(('127.0.0.1',0),Model)
threading.Thread(target=model.serve_forever,daemon=True).start()
app_port=port();env=dict(os.environ,AUDIT_STAGING_PORT=str(app_port),AUDIT_MAILBOX=str(settings.runtime_root.parent/'fixture-mail.json'),COOKIE_SECURE='false')
app_process=subprocess.Popen([sys.executable,'-m','uvicorn','tests.staging_app:app','--host','127.0.0.1','--port',str(app_port),'--lifespan','off','--log-level','warning'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
owner=uuid.uuid4();account=opencode.account_workspace(owner);service=None
report={'hostname':socket.gethostname(),'internal_addresses':sorted({r[4][0] for r in socket.getaddrinfo(socket.gethostname(),None)}),'scope':'disposable loopback only',
        'configuration_sources':['tests/run_isolated_audit.py','tests/staging_app.py','backend/app/config.py','backend/app/services/opencode.py',__file__],
        'secret_environment':{k:bool(os.getenv(k)) for k in ['DATABASE_URL','CREDENTIALS_ENCRYPTION_KEY','OPENCODE_SERVER_PASSWORD','HTTP_PROXY','HTTPS_PROXY','NO_PROXY']}}
original_spawn=opencode.subprocess.Popen
# Private fixture logs only. Production startup flags are not modified.
def verbose(args,*a,**kw):
    if 'serve' in args:
        args=[*args,'--print-logs','--log-level','DEBUG']
        launch_env=dict(kw['env']);config=json.loads(launch_env['OPENCODE_CONFIG_CONTENT'])
        config['provider']={'fixture':{'npm':'@ai-sdk/openai-compatible','name':'Fixture','options':{'baseURL':f'http://127.0.0.1:{model.server_port}/v1','apiKey':'fixture-only'},'models':{'fixture':{'name':'Fixture','limit':{'context':16000,'output':1000}}}}}
        launch_env['OPENCODE_CONFIG_CONTENT']=json.dumps(config);kw['env']=launch_env
    return original_spawn(args,*a,**kw)
opencode.subprocess.Popen=verbose
try:
    with httpx.Client(trust_env=False,timeout=2) as client:
        for attempt in range(100):
            try:
                response=client.get(f'http://127.0.0.1:{app_port}/api/health')
                if response.status_code==200:break
            except httpx.HTTPError:pass
            time.sleep(.1)
        else:raise RuntimeError('Disposable Gateway health unavailable')
        report['fastapi']={'host':'127.0.0.1','port':app_port,'origin':f'http://127.0.0.1:{app_port}','api_base':f'http://127.0.0.1:{app_port}/api','health_status':response.status_code,'transport':'real Uvicorn HTTP; earlier fixture uses in-process https://testserver'}
        with SessionLocal() as db:
            report['database']={'engine':'PGlite (not native PostgreSQL)','host':urlsplit(settings.database_url).hostname,'port':urlsplit(settings.database_url).port,'ready':db.scalar(text('select 1'))==1,'migration':db.scalar(text('select version_num from alembic_version'))}
            service=opencode.for_workspace(account,db=db);db.commit()
        runtime=opencode._runtimes[str(account.id)]
        origin=str(service.client.base_url).rstrip('/')
        unauth=client.get(origin+'/global/health')
        report['opencode']={'executable':settings.opencode_binary,'version':service.health().get('version'),'host':urlsplit(origin).hostname,'port':urlsplit(origin).port,'origin':origin,'authenticated_health':True,'unauthenticated_status':unauth.status_code,'authentication':'generated per-runtime HTTP Basic; password omitted','command':'opencode serve --pure --hostname 127.0.0.1 --port <allocated> --print-logs --log-level DEBUG','proxy_inheritance':'runtime may inherit proxy variables; Gateway client trust_env=False'}
        report['roots']={'workspace_root':str(settings.workspace_root),'runtime_root':str(settings.runtime_root),'runtime_directory_exists':(settings.runtime_root/str(owner)/str(account.id)).is_dir(),'workdir_exists':Path(service.params['directory']).is_dir()}
        try:report['network_namespace_shared']=os.readlink('/proc/self/ns/net')==os.readlink(f'/proc/{runtime.process.pid}/ns/net')
        except OSError:report['network_namespace_shared']='unavailable'
        endpoint=f'http://127.0.0.1:{model.server_port}/v1'
        report['model']={'provider':'fixture','model':'fixture','endpoint':endpoint,'health_status':client.get(endpoint+'/models').status_code,'auth':'fixture-only value; omitted','npm':'@ai-sdk/openai-compatible','streaming':'fixture currently emits chat.completion.chunk'}
        catalog=service.request('GET','/provider');entry=next((p for p in catalog.get('all',[]) if p.get('id')=='fixture'),None)
        report['model']['catalog_model_present']=bool(entry and 'fixture' in entry.get('models',{}))
        if entry:report['model']['resolved_api']=entry['models']['fixture'].get('api')
        assert report['model']['catalog_model_present'],'Fixture model must be discoverable before an Agent request'
        print('ENVIRONMENT_PREFLIGHT',json.dumps(report),flush=True)
        # Only after service/DB/network/config checks, trace one original request.
        native=service.request('POST','/session',{'title':'Network/protocol diagnostic','permission':[{'permission':'*','pattern':'*','action':'ask'}]})
        response=service.client.post(service.session_path(native['id'],'/message'),params=service.params,json={'model':{'providerID':'fixture','modelID':'fixture'},'parts':[{'type':'text','text':'Return the local diagnostic response.'}]},timeout=30)
        body=response.json();report['agent_diagnostic']={'status':response.status_code,'error_name':body.get('name'),'error_reference':body.get('data',{}).get('ref'),'model_requests':observed,'assistant_error':body.get('info',{}).get('error',{}).get('name')}
        context=settings.runtime_root/str(owner)/str(account.id)
        errors=[]
        for log in context.rglob('*.log'):
            for line in log.read_text(errors='replace').splitlines():
                if 'ERROR' in line or 'error=' in line:
                    line=line.replace(str(context),'[runtime]').replace(service.params['directory'],'[fixture-workdir]')
                    # Diagnostic contains exclusively synthetic fixture data.
                    errors.append(line[:3500])
        report['sanitized_fixture_errors']=errors[-8:]
        print('AGENT_DIAGNOSTIC',json.dumps({'request':report['agent_diagnostic'],'logs':report['sanitized_fixture_errors']}),flush=True)
        output=os.getenv('AUDIT_ENV_REPORT')
        if output:Path(output).write_text(json.dumps(report,indent=2)+'\n')
finally:
    opencode.subprocess.Popen=original_spawn
    opencode.stop_workspace(account)
    model.shutdown();model.server_close()
    app_process.terminate()
    try:app_process.wait(timeout=5)
    except subprocess.TimeoutExpired:app_process.kill();app_process.wait()
