"""Existing React output is served as bounded bytes; no build or app execution."""
import base64
import os
from pathlib import Path
from threading import Thread
import json
import urllib.request
import urllib.error
import pytest
from app.services import preview_static_artifact as static
from app.services.preview_worker_server import WorkerServer

@pytest.fixture
def built(tmp_path):
    root=tmp_path/'dist';root.mkdir();(root/'assets').mkdir()
    (root/'index.html').write_text('<h1>Built React output</h1>')
    (root/'assets/app.js').write_text('console.log("built")')
    return root

def decoded(result):return base64.b64decode(result['body'])

def test_existing_bundle_read_without_dependencies(built):
    result=static.fetch(str(built),'/assets/app.js?v=1')
    assert result['status']==200 and decoded(result)==b'console.log("built")'
    assert result['mode']=='prebuilt_static'

@pytest.mark.parametrize('path',['/../secret','/%2e%2e/secret','/%252e%252e/secret',
    '/.env','//attacker/file.js','/assets/../../main.py','/assets\\main.py','/assets/%00.js'])
def test_traversal_and_private_files_are_rejected(built,path):
    result=static.fetch(str(built),path)
    assert result['status']==400
    assert b'Built React' not in decoded(result)

def test_symlink_cannot_expose_outside_artifact(built,tmp_path):
    secret=tmp_path/'secret.txt';secret.write_text('outside-canary')
    (built/'assets/secret.txt').symlink_to(secret)
    result=static.fetch(str(built),'/assets/secret.txt')
    assert result['status']==404 and b'outside-canary' not in decoded(result)

def test_hard_link_cannot_expose_outside_artifact(built,tmp_path):
    secret=tmp_path/'secret.txt';secret.write_text('outside-canary')
    os.link(secret,built/'assets/secret.txt')
    result=static.fetch(str(built),'/assets/secret.txt')
    assert result['status']==400 and b'outside-canary' not in decoded(result)

def test_large_asset_is_bounded(built):
    (built/'assets/big.js').write_bytes(b'x'*(static.MAX_ASSET_BYTES+1))
    assert static.fetch(str(built),'/assets/big.js')['status']==413

def test_spa_routes_fallback_but_missing_modules_do_not(built):
    assert static.fetch(str(built),'/settings')['status']==200
    assert static.fetch(str(built),'/assets/missing.js')['status']==404

def test_root_asset_references_keep_ticket_scope():
    prefix='/preview/ticket/'
    source=b'const logo="/assets/logo.svg";import("/assets/chunk.js");fetch("/api/items")'
    result=static.rewrite_references(source,'application/javascript',prefix)
    assert b'"/preview/ticket/assets/logo.svg"' in result
    assert b'"/preview/ticket/assets/chunk.js"' in result
    assert b'fetch("/api/items")' in result
    css=static.rewrite_references(b'a{background:url(/assets/logo.svg)}','text/css',prefix)
    assert css==b'a{background:url(/preview/ticket/assets/logo.svg)}'

def test_reference_amplification_is_bounded():
    with pytest.raises(ValueError):
        static.rewrite_references(b'"/assets/a.svg";'*513,'application/javascript','/preview/ticket/')

def test_prefix_cannot_inject_script():
    with pytest.raises(ValueError):
        static.rewrite_references(b'"/assets/a.js"','application/javascript',"/preview/';alert(1);'/")

class NoDocker:
    def __getattr__(self,name):raise AssertionError('Static preview must not call Docker: '+name)

def test_static_http_lifecycle_requires_current_lease_and_no_dynamic_slot(built):
    jobs={'built':dict(state='ready',container_id=None,spec=None,family='static',
                       artifact_root=str(built),artifact_lease='a'*64)}
    server=WorkerServer(('127.0.0.1',0),'x'*32,NoDocker(),jobs=jobs,admission=lambda:False)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    def call(operation,**extra):
        request=urllib.request.Request(f'http://127.0.0.1:{server.server_address[1]}/v1/'+operation,
            data=json.dumps({'job_id':'built',**extra}).encode(),headers={'Authorization':'Bearer '+'x'*32})
        with urllib.request.urlopen(request) as response:return json.load(response)
    try:
        started=call('start')
        assert started['mode']=='prebuilt_static' and started['execution_enabled'] is False
        status=call('status');assert status['browser_lease']=='a'*64
        assert decoded(call('fetch',path='/',browser_lease='a'*64))==b'<h1>Built React output</h1>'
        with pytest.raises(urllib.error.HTTPError) as error:call('fetch',path='/',browser_lease='b'*64)
        assert error.value.code==409
        assert call('stop')['state']=='stopped'
        assert call('status')['browser_lease'] is None
        with pytest.raises(urllib.error.HTTPError) as error:call('fetch',path='/',browser_lease='a'*64)
        assert error.value.code==409
    finally:
        server.shutdown();thread.join();server.server_close()


def test_static_snapshot_expires_and_releases_disk(tmp_path,monkeypatch):
    from app.services import preview_worker_server as worker
    monkeypatch.setattr(worker,'JOB_ROOT',tmp_path)
    root=tmp_path/'cached';(root/'src/dist').mkdir(parents=True)
    (root/worker.STATIC_MARKER).write_text('prebuilt-static-v1')
    (root/'src/dist/index.html').write_text('cached')
    jobs={'cached':dict(state='running',container_id=None,artifact_root=str(root/'src/dist'),started_monotonic=0)}
    server=WorkerServer(('127.0.0.1',0),'x'*32,NoDocker(),jobs=jobs,clock=lambda:900)
    server.reconciled=True
    try:
        server.reap_expired()
        assert jobs['cached']['state']=='stopped'
        assert jobs['cached']['stop_reason']=='artifact_cache_expired'
        assert not root.exists()
    finally:server.server_close()


def test_static_stop_removes_only_its_own_snapshot(tmp_path,monkeypatch):
    from app.services import preview_worker_server as worker
    monkeypatch.setattr(worker,'JOB_ROOT',tmp_path)
    own=tmp_path/'own';own.mkdir();(own/'asset.js').write_text('own')
    other=tmp_path/'other';other.mkdir();(other/'asset.js').write_text('other')
    server=WorkerServer(('127.0.0.1',0),'x'*32,NoDocker(),jobs={})
    server.reconciled=True
    try:
        state=dict(state='running',container_id=None,artifact_root=str(own))
        server.stop_job('own',state,'user_stop')
        assert not own.exists() and (other/'asset.js').read_text()=='other'
    finally:server.server_close()


def test_restart_removes_only_marked_orphan_static_snapshots(tmp_path,monkeypatch):
    from app.services import preview_worker_server as worker
    monkeypatch.setattr(worker,'JOB_ROOT',tmp_path)
    stale=tmp_path/'stale';stale.mkdir();(stale/worker.STATIC_MARKER).write_text('v1')
    unrelated=tmp_path/'unrelated';unrelated.mkdir();(unrelated/'file').write_text('retain')
    class InventoryOnly:
        def managed_containers(self):return ()
    server=WorkerServer(('127.0.0.1',0),'x'*32,InventoryOnly(),jobs={})
    try:
        server.reconcile_orphans()
        assert not stale.exists() and (unrelated/'file').exists()
    finally:server.server_close()


def test_gateway_recognizes_existing_react_build(tmp_path,monkeypatch):
    from app.services import preview_runner as runner
    monkeypatch.setattr(runner.preview,'detect',lambda workspace:{'framework':'react'})
    monkeypatch.setattr(runner.workspaces,'safe_path',lambda workspace,name:tmp_path/name)
    workspace=object()
    assert runner.launch_options(workspace)['profile_available'] is False
    (tmp_path/'dist').mkdir();(tmp_path/'dist/index.html').write_text('<div id="root"></div>')
    result=runner.launch_options(workspace)
    assert result['prebuilt_static'] is True
    assert result['runtime_family']=='static' and result['argv']==[]


def test_gateway_reloads_static_snapshot_instead_of_reusing_stale_output(monkeypatch):
    from types import SimpleNamespace
    from app.services import preview_runner as runner,preview_snapshot
    calls=[]
    class Client:
        def request(self,operation,payload):
            calls.append((operation,payload))
            return {'status':{'state':'running'},'stop':{'state':'stopped'},
                    'prepare':{'state':'ready'},'start':{'state':'running','mode':'prebuilt_static','execution_enabled':False}}[operation]
    monkeypatch.setattr(runner,'_worker',lambda:Client())
    monkeypatch.setattr(runner,'launch_options',lambda workspace:{'framework':'vite','profile_available':True,'prebuilt_static':True,'argv':[]})
    monkeypatch.setattr(preview_snapshot,'export',lambda workspace,stream:stream.write(b'controlled snapshot'))
    result=runner.start(SimpleNamespace(id='11111111-1111-1111-1111-111111111111'))
    assert result['mode']=='prebuilt_static' and result['execution_enabled'] is False
    assert [item[0] for item in calls]==['status','stop','prepare','start']
    assert calls[2][1]['prebuilt_static'] is True and calls[2][1]['entrypoint'] is None
