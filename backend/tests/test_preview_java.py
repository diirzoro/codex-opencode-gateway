"""Java entry selection and the same fixed container/relay boundary."""
import subprocess
import base64
import json
import shutil
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import pytest
from app.services import preview_runner as runner
from app.services.preview_docker_provisioner import DockerProvisioner
from app.services.preview_container_spec import ContainerSpec, argv_for
from app.services.preview_launch_profiles import PROFILES

def test_java_requires_explicit_source_entry(tmp_path,monkeypatch):
    monkeypatch.setattr(runner.preview,'detect',lambda workspace:{'framework':'java'})
    monkeypatch.setattr(runner.workspaces,'safe_path',lambda workspace,name:tmp_path/name)
    assert runner.launch_options(object())['profile_available'] is False
    (tmp_path/'Main.java').write_text('class Main {}')
    result=runner.launch_options(object())
    assert result['runtime_family']=='java' and result['argv'][-1]=='Main.java'

def test_java_inherits_network_and_resource_limits():
    args=argv_for(ContainerSpec('sha256:'+'a'*64,PROFILES['java'].argv,
                               '/var/lib/preview-worker/jobs/java-test/src'))
    assert args[args.index('--network')+1]=='none'
    assert args[args.index('--memory')+1]=='768m'
    assert args[args.index('--cpus')+1]=='0.5'
    assert '--read-only' in args and '--source' in args

def test_java_fetch_uses_only_compiled_trusted_relay():
    calls=[]
    def run(args,**kwargs):
        calls.append(args)
        output='java-test|true' if args[1]=='inspect' else '{"status":200,"type":"text/plain","body":"b2s="}'
        return subprocess.CompletedProcess(args,0,stdout=output,stderr='')
    response=DockerProvisioner(run=run).fetch('a'*64,'java-test','java','/health')
    assert response['status']==200
    assert calls[-1][-4:]==('-cp','/opt/preview','PreviewFetch','/health')
    assert 'Main.java' not in calls[-1]

def test_startup_logs_preserve_stderr_after_owner_check():
    calls=[]
    def run(args,**kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args,0,
            stdout='java-test|true' if args[1]=='inspect' else 'application stdout\n',
            stderr='' if args[1]=='inspect' else 'compiler diagnostic\n')
    logs=DockerProvisioner(run=run).logs('a'*64,'java-test')
    assert 'application stdout' in logs and 'compiler diagnostic' in logs
    assert calls[0][1]=='inspect' and calls[1][1]=='logs'

@pytest.mark.parametrize('path,status,body',[
    ('/health',200,b'java-relay-canary'),('/missing',404,b'missing'),
    ('/redirect',302,b''),('/large',None,None)])
def test_real_java_relay_bounds_and_http_status(path,status,body):
    if not shutil.which('java'):pytest.skip('JDK 21 required for relay acceptance')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            value=(b'x'*262145 if self.path=='/large' else b'missing' if self.path=='/missing'
                   else b'' if self.path=='/redirect' else b'java-relay-canary')
            self.send_response(404 if self.path=='/missing' else 302 if self.path=='/redirect' else 200)
            self.send_header('Content-Type','text/plain')
            if self.path=='/redirect':self.send_header('Location','http://unreachable.invalid/')
            self.end_headers();self.wfile.write(value)
    server=ThreadingHTTPServer(('127.0.0.1',8080),Handler)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        source=Path(__file__).resolve().parents[2]/'deploy/PreviewFetch.java'
        result=subprocess.run(('java','-Xmx64m',str(source),path),capture_output=True,text=True,timeout=15)
        if status is None:
            assert result.returncode!=0 and not result.stdout
        else:
            assert result.returncode==0,result.stderr
            response=json.loads(result.stdout)
            assert response['status']==status and base64.b64decode(response['body'])==body
    finally:server.shutdown();thread.join();server.server_close()
