"""Finite errors and real loopback HTTP; Docker calls are controlled, not real."""
import io
import json
import subprocess
import threading
import urllib.error
from unittest.mock import patch

import pytest
from app.services.preview_container_spec import ContainerSpec
from app.services.preview_diagnostics import MESSAGES, docker_failure_code
from app.services.preview_docker_provisioner import DockerProvisioner, PreviewProvisioningError
from app.services.preview_worker_client import PreviewWorkerClient, PreviewWorkerUnavailable
from app.services import preview_worker_server as worker

CID='b'*64
SPEC=ContainerSpec('docker.io/library/node@sha256:'+'a'*64,('node','server.js'),'/var/lib/preview-worker/jobs/job1/src')

@pytest.mark.parametrize('stderr,code',[
 ('permission denied while trying to connect to the Docker daemon socket at unix:///run/preview-worker/docker.sock','docker_socket_permission_denied'),
 ('Cannot connect to the Docker daemon. Is the docker daemon running?','docker_daemon_unreachable'),
 ('cgroups: cannot set memory limit','docker_resource_limits_unavailable'),
 ('invalid mount config for type bind: source path does not exist','docker_snapshot_mount_denied'),
 ('No such image: registry/private@sha256:SECRET','docker_image_unavailable'),
 ('The container name is already in use','docker_job_conflict'),
 ('exec: ./node_modules/.bin/vite: no such file or directory','application_entrypoint_missing'),
 ('executable file not found in $PATH','application_entrypoint_missing'),
 ('operation not permitted: OCI runtime create failed','docker_isolation_unavailable'),
 ('unknown daemon error with PRIVATE TOKEN','docker_operation_failed'),
])
def test_finite_error_classification(stderr,code):
    def fail(args,**kw):raise subprocess.CalledProcessError(125,args,stderr=stderr)
    with pytest.raises(PreviewProvisioningError) as error:DockerProvisioner(run=fail).launch_smoke('job1',SPEC)
    assert error.value.code==code
    assert str(error.value)==MESSAGES[code]
    assert stderr not in str(error.value)

@pytest.mark.parametrize('failure,code',[(FileNotFoundError('SECRET'),'docker_binary_missing'),(subprocess.TimeoutExpired('SECRET',20),'docker_operation_timed_out')])
def test_missing_binary_timeout(failure,code):
    def fail(*args,**kw):raise failure
    with pytest.raises(PreviewProvisioningError) as error:DockerProvisioner(run=fail).launch_smoke('job1',SPEC)
    assert error.value.code==code and 'SECRET' not in str(error.value)


def test_invalid_spec_does_not_invoke_docker():
    def never(*a,**kw):pytest.fail('Docker called for invalid spec')
    with pytest.raises(PreviewProvisioningError) as error:DockerProvisioner(run=never).launch_smoke('job1',ContainerSpec('node:latest',('node',),SPEC.project_mount))
    assert error.value.code=='invalid_container_spec'


def test_never_auto_pulls_and_keeps_security_flags():
    calls=[]
    def run(args,**kw):calls.append(args);return subprocess.CompletedProcess(args,0,CID)
    assert DockerProvisioner(run=run).launch_smoke('job1',SPEC)==CID
    argv=calls[0];assert argv[argv.index('--pull')+1]=='never'
    for flag in ('--read-only','--cap-drop','--security-opt','--memory','--cpus','--pids-limit'):assert flag in argv
    assert argv[argv.index('--network')+1]=='none'
    assert '--privileged' not in argv and '-p' not in argv


class Adapter:
    def __init__(self,error=None,exited=False):self.error=error;self.exited=exited;self.stopped=False;self.launched=False
    def launch_smoke(self,*args):
        self.launched=True
        if self.error:raise self.error
        return CID
    def status(self,*args):return 'exited' if self.exited else 'running'
    def fetch(self,*args):return {'status':200,'type':'text/html','body':'aGVsbG8='}
    def stop(self,*args):self.stopped=True


@pytest.fixture
def loopback():
    servers=[]
    def make(adapter,spec=SPEC):
        worker.JOBS.clear();worker.JOBS['job1']={'spec':spec,'container_id':None,'state':'ready','family':'node'}
        server=worker.WorkerServer(('127.0.0.1',0),'x'*40,adapter);servers.append(server)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        return PreviewWorkerClient('http://127.0.0.1:'+str(server.server_port),'x'*40)
    yield make
    for server in servers:server.shutdown();server.server_close()
    worker.JOBS.clear()


def test_launch_error_crosses_actual_http_without_secret(loopback,caplog):
    client=loopback(Adapter(PreviewProvisioningError('DO NOT EXPOSE SECRET',code='docker_socket_permission_denied')))
    with pytest.raises(PreviewWorkerUnavailable) as error:client.request('start',{'job_id':'job1'})
    assert 'docker_socket_permission_denied' in str(error.value)
    assert 'reference ' in str(error.value)
    assert 'SECRET' not in str(error.value)+caplog.text
    assert worker.JOBS['job1']['state']=='failed'


def test_unknown_exception_is_not_exposed(loopback,caplog):
    client=loopback(Adapter(ValueError('PRIVATE CUSTOMER DATA')))
    with pytest.raises(PreviewWorkerUnavailable) as error:client.request('start',{'job_id':'job1'})
    assert 'worker_operation_failed' in str(error.value)
    assert 'PRIVATE CUSTOMER DATA' not in str(error.value)+caplog.text


def test_early_exit_is_distinguished_and_stopped(loopback):
    adapter=Adapter(exited=True);client=loopback(adapter)
    with pytest.raises(PreviewWorkerUnavailable) as error:client.request('start',{'job_id':'job1'})
    assert 'application_exited_early' in str(error.value) and adapter.stopped


def test_start_status_fetch_stop_protocol(loopback):
    adapter=Adapter();client=loopback(adapter)
    assert client.request('start',{'job_id':'job1'})['state']=='running'
    assert client.request('status',{'job_id':'job1'})['state']=='running'
    assert client.request('fetch',{'job_id':'job1','path':'/style.css'})['body']=='aGVsbG8='
    assert client.request('stop',{'job_id':'job1'})['state']=='stopped' and adapter.stopped


def test_missing_dependency_stage_never_launches(loopback):
    adapter=Adapter();spec=ContainerSpec(SPEC.image,('./node_modules/.bin/vite','--port','8080'),SPEC.project_mount)
    client=loopback(adapter,spec)
    with pytest.raises(PreviewWorkerUnavailable) as error:client.request('start',{'job_id':'job1'})
    assert 'dependency_preparation_required' in str(error.value) and not adapter.launched


def test_client_does_not_expose_worker_supplied_messages_or_reference():
    raw=json.dumps({'error':'docker_operation_failed','message':'SECRET','reference':'SECRET'}).encode()
    with patch('urllib.request.urlopen',side_effect=urllib.error.HTTPError('http://127.0.0.1',503,'error',{},io.BytesIO(raw))):
        with pytest.raises(PreviewWorkerUnavailable) as error:PreviewWorkerClient('http://127.0.0.1:8791','x'*40).request('start',{'job_id':'job1'})
    assert 'SECRET' not in str(error.value)
