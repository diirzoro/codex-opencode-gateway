import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
from types import SimpleNamespace
import pytest
from app.services import preview_npm_cache as cache,preview_react_build as build
from app.services.preview_container_spec import ContainerSpec,argv_for
from app.services.preview_worker_archive import UnsafePreviewArchive

def tgz(files,mode='w:gz'):
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode=mode) as archive:
        for name,body in files.items():
            item=tarfile.TarInfo(name);item.size=len(body);archive.addfile(item,io.BytesIO(body))
    return stream.getvalue()

def integrity(body):return 'sha512-'+base64.b64encode(hashlib.sha512(body).digest()).decode()

@pytest.mark.parametrize('url',[
 'http://registry.npmjs.org/a/-/a.tgz','https://127.0.0.1/a/-/a.tgz',
 'https://registry.npmjs.org.attacker.test/a/-/a.tgz','https://user:secret@registry.npmjs.org/a/-/a.tgz',
 'https://registry.npmjs.org:443/a/-/a.tgz','https://registry.npmjs.org/a/-/a.tgz?token=secret',
 'https://registry.npmjs.org/a/../a/-/a.tgz','https://registry.npmjs.org/a/%2e%2e/-/a.tgz'])
def test_public_package_fetch_rejects_noncanonical_urls(url):
    with pytest.raises(cache.PackagePreparationError):cache.validate_url(url)

def test_scoped_public_package_is_allowed():
    assert cache.validate_url('https://registry.npmjs.org/@scope/pkg/-/pkg-1.0.0.tgz')

def test_worker_rechecks_integrity_before_staging(tmp_path):
    with pytest.raises(cache.PackagePreparationError):
        cache.stage([{'body':base64.b64encode(b'changed').decode(),'integrity':integrity(b'expected')}],tmp_path/'packages')
    assert not list((tmp_path/'packages').iterdir())

def test_worker_stages_only_numbered_opaque_packages(tmp_path):
    body=b'opaque verified bytes'
    cache.stage([{'body':base64.b64encode(body).decode(),'integrity':integrity(body)}],tmp_path/'packages')
    assert (tmp_path/'packages/0000.tgz').read_bytes()==body

def test_local_package_links_and_missing_integrity_are_rejected():
    for item in [{'link':True},{'resolved':'https://registry.npmjs.org/a/-/a.tgz','integrity':'sha1-weak'}]:
        with pytest.raises(cache.PackagePreparationError):cache.locked_packages({'lockfileVersion':3,'packages':{'node_modules/a':item}})

def test_optional_wrong_platform_package_is_not_downloaded():
    assert cache.locked_packages({'lockfileVersion':3,'packages':{'node_modules/native':{'os':['darwin'],'optional':True}}})==[]

def test_artifact_extraction_rejects_link_and_traversal(tmp_path):
    for name,kind in [('../escape',tarfile.REGTYPE),('linked.js',tarfile.SYMTYPE)]:
        stream=io.BytesIO()
        with tarfile.open(fileobj=stream,mode='w') as archive:
            item=tarfile.TarInfo(name);item.type=kind;item.linkname='/outside';archive.addfile(item)
        with pytest.raises((UnsafePreviewArchive,ValueError)):
            build.extract_artifact(stream.getvalue(),tmp_path/name.replace('/','-'))
    assert not (tmp_path/'escape').exists()

def test_artifact_normalizes_docker_tar_and_keeps_only_dist_files(tmp_path):
    raw=tgz({'./index.html':b'<h1>built</h1>','./assets/a.js':b'console.log(1)'},mode='w')
    build.extract_artifact(raw,tmp_path/'output')
    assert (tmp_path/'output/index.html').read_bytes()==b'<h1>built</h1>'
    assert (tmp_path/'output/assets/a.js').read_bytes()==b'console.log(1)'

def test_build_profile_retains_network_and_host_limits():
    args=argv_for(ContainerSpec('sha256:'+'a'*64,('node','-e',build.BUILD_SCRIPT),
        '/var/lib/preview-worker/jobs/test/src',build_only=True))
    assert args[args.index('--network')+1]=='none'
    assert '--read-only' in args and '10001:10001' in args
    assert 'type=bind,src=/var/lib/preview-worker/jobs/test/packages,dst=/preview-packages,readonly' in args
    assert '/build:rw,nosuid,nodev,size=384m,mode=1777' in args
    assert args[args.index('--cpus')+1]=='0.5'

def test_real_offline_npm_uses_verified_tar_without_install_hooks(tmp_path):
    import shutil
    if not shutil.which('npm'):pytest.skip('npm is required for offline cache acceptance')
    package=tgz({'package/package.json':json.dumps({'name':'preview-cache-fixture','version':'1.0.0',
        'scripts':{'preinstall':"node -e \"require('fs').writeFileSync('UNSAFE_HOOK','ran')\""}}).encode(),
        'package/index.js':b'module.exports=1'})
    archive=tmp_path/'fixture.tgz';archive.write_bytes(package)
    app=tmp_path/'app';app.mkdir();npm_cache=tmp_path/'cache'
    manifest={'name':'preview-app','version':'1.0.0','dependencies':{'preview-cache-fixture':'1.0.0'}}
    (app/'package.json').write_text(json.dumps(manifest))
    lock={'name':'preview-app','version':'1.0.0','lockfileVersion':3,'packages':{'':manifest,
      'node_modules/preview-cache-fixture':{'version':'1.0.0','resolved':'https://registry.npmjs.org/preview-cache-fixture/-/preview-cache-fixture-1.0.0.tgz','integrity':integrity(package)}}}
    (app/'package-lock.json').write_text(json.dumps(lock))
    (tmp_path/'user.npmrc').write_text('');(tmp_path/'global.npmrc').write_text('')
    env={'PATH':os.environ['PATH'],'HOME':str(tmp_path),
         'npm_config_userconfig':str(tmp_path/'user.npmrc'),'npm_config_globalconfig':str(tmp_path/'global.npmrc')}
    flags=['--cache',str(npm_cache),'--offline','--ignore-scripts','--no-audit','--no-fund']
    for command,cwd in [(['npm','cache','add',str(archive),str(archive),*flags],tmp_path),(['npm','ci','--include=dev',*flags],app)]:
        result=subprocess.run(command,cwd=cwd,env=env,capture_output=True,text=True,timeout=20)
        assert result.returncode==0,result.stderr
    assert (app/'node_modules/preview-cache-fixture/index.js').exists()
    assert not list(tmp_path.rglob('UNSAFE_HOOK'))

def test_unchanged_source_reuses_static_result_without_build_or_package_download(monkeypatch):
    from app.services import preview_runner as runner,preview_snapshot
    snapshot=b'controlled snapshot';calls=[]
    class Client:
        def request(self,operation,payload):
            calls.append(operation)
            assert operation=='status'
            return {'state':'running','source_digest':hashlib.sha256(snapshot).hexdigest(),'mode':'built_static'}
    monkeypatch.setattr(runner,'launch_options',lambda workspace:{'framework':'vite','profile_available':True,'build_static':True,'argv':['node']})
    monkeypatch.setattr(runner,'_worker',lambda:Client())
    monkeypatch.setattr(preview_snapshot,'export',lambda workspace,stream:stream.write(snapshot))
    result=runner.start(SimpleNamespace(id='11111111-1111-1111-1111-111111111111'))
    assert result['reused'] and result['mode']=='built_static' and calls==['status']

def test_cancelled_build_cannot_publish_after_stop(tmp_path,monkeypatch):
    from app.services import preview_worker_server as worker
    monkeypatch.setattr(worker,'JOB_ROOT',tmp_path)
    class Docker:
        def build_ready(self,*args):raise AssertionError('Cancelled build must not read container')
    job={'state':'stopped','container_id':None}
    server=worker.WorkerServer(('127.0.0.1',0),'x'*32,Docker(),jobs={'cancelled':job})
    server.reconciled=True
    try:
        server.complete_react_build('cancelled',job,'a'*64)
        assert job['state']=='stopped' and not list(tmp_path.iterdir())
    finally:server.server_close()

def test_completed_build_stops_container_before_publishing_static_lease(tmp_path,monkeypatch):
    from app.services import preview_worker_server as worker
    monkeypatch.setattr(worker,'JOB_ROOT',tmp_path)
    root=tmp_path/'built';root.mkdir();(root/worker.STATIC_MARKER).write_text('build')
    calls=[]
    class Docker:
        def build_ready(self,*args):return True
        def export_build(self,*args):return tgz({'./index.html':b'<h1>current source</h1>'},mode='w')
        def stop(self,*args):calls.append('stop')
    job={'state':'building','container_id':'a'*64,'family':'react_build','started_monotonic':100,'activity_monotonic':100}
    server=worker.WorkerServer(('127.0.0.1',0),'x'*32,Docker(),jobs={'built':job},clock=lambda:100)
    server.reconciled=True
    try:
        server.complete_react_build('built',job,'a'*64)
        assert calls==['stop'] and job['state']=='running' and job['container_id'] is None
        assert job['built_static'] and len(job['artifact_lease'])==64
        assert (Path(job['artifact_root'])/'index.html').read_bytes()==b'<h1>current source</h1>'
        server.stop_job('built',job,'user_stop')
        assert job['state']=='stopped' and not root.exists()
    finally:server.server_close()

def test_cancellation_during_export_does_not_publish_stale_artifact(tmp_path,monkeypatch):
    from app.services import preview_worker_server as worker
    monkeypatch.setattr(worker,'JOB_ROOT',tmp_path)
    root=tmp_path/'cancelled';root.mkdir()
    class Docker:
        def build_ready(self,*args):return True
        def export_build(self,*args):
            server.stop_job('cancelled',job,'user_stop')
            return tgz({'./index.html':b'must not publish'},mode='w')
        def stop(self,*args):pass
    job={'state':'building','container_id':'a'*64,'family':'react_build','started_monotonic':100,'activity_monotonic':100}
    server=worker.WorkerServer(('127.0.0.1',0),'x'*32,Docker(),jobs={'cancelled':job},clock=lambda:100)
    server.reconciled=True
    try:
        server.complete_react_build('cancelled',job,'a'*64)
        assert job['state']=='stopped' and not root.exists() and not job.get('artifact_lease')
    finally:server.server_close()

def test_building_status_does_not_issue_browser_access():
    from app.services import preview_worker_server as worker
    from threading import Thread
    from urllib.request import Request,urlopen
    class Docker:
        def status(self,*args):return 'running'
        def stop(self,*args):pass
    job={'state':'building','container_id':'a'*64,'family':'react_build','started_monotonic':100,'activity_monotonic':100}
    server=worker.WorkerServer(('127.0.0.1',0),'x'*32,Docker(),jobs={'building':job},clock=lambda:100)
    server.reconciled=True
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        request=Request(f'http://127.0.0.1:{server.server_address[1]}/v1/status',data=b'{"job_id":"building"}',
                        headers={'Authorization':'Bearer '+'x'*32})
        with urlopen(request) as response:result=json.load(response)
        assert result['state']=='building' and result['browser_lease'] is None
    finally:server.shutdown();thread.join();server.server_close()
