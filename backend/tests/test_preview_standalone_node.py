"""Plain Node server discovery; never execute source on the Gateway host."""
import os
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://test:test@127.0.0.1/test')
import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from backend.app.services import preview,preview_runner,workspaces,preview_worker_client
from backend.tests.test_preview_detection import source

@pytest.mark.parametrize('with_html',[False,True])
def test_server_without_manifest_selects_fixed_isolated_node_profile(source,with_html):
    workspace,root=source
    (root/'server.js').write_text('throw Error("MUST_NOT_RUN_ON_HOST")')
    if with_html:(root/'index.html').write_text('<a href="/nested/page">Next</a>')
    assert preview.detect(workspace)['framework']=='node'
    info=preview_runner.launch_options(workspace)
    assert info['argv']==['node','server.js'] and info['profile_available']
    assert preview_runner.plan(workspace)['mode']=='isolated_runner_required'
    assert info['environment']=={'PORT':'8080','HOST':'0.0.0.0'}
    assert info['execution_enabled'] is False


def test_browser_index_js_does_not_imply_node_server(source):
    workspace,root=source
    (root/'index.js').write_text('document.body.textContent="browser"')
    (root/'index.html').write_text('<script src="index.js"></script>')
    assert preview.detect(workspace)['framework']=='html'
    assert preview_runner.launch_options(workspace)['profile_available'] is False

@pytest.mark.parametrize('manifest,content,expected',[
    ('package.json',json.dumps({'dependencies':{'vite':'fixture'}}),'vite'),
    ('requirements.txt','fastapi\nuvicorn\n','python'),
])
def test_existing_explicit_framework_keeps_precedence(source,manifest,content,expected):
    workspace,root=source
    (root/manifest).write_text(content);(root/'server.js').write_text('// incidental file')
    assert preview.detect(workspace)['framework']==expected


def test_external_symlink_is_not_a_server_entry(source,tmp_path):
    workspace,root=source;outside=tmp_path/'foreign.js';outside.write_text('private')
    (root/'server.js').symlink_to(outside)
    with pytest.raises(HTTPException) as error:preview.detect(workspace)
    assert error.value.status_code==403


def test_oversized_entry_keeps_existing_detection_bound(source):
    workspace,root=source
    (root/'server.js').write_text('x'*250001);(root/'index.html').write_text('static')
    assert preview.detect(workspace)['framework']=='html'


def test_start_sends_real_source_archive_to_worker_not_host(source,monkeypatch):
    import base64,io,tarfile
    workspace,root=source
    (root/'server.js').write_text('throw Error("HOST_EXECUTION_FORBIDDEN")')
    (root/'index.html').write_text('<h1>root</h1>')
    (root/'nested').mkdir();(root/'nested/page.html').write_text('<h1>nested</h1>')
    requests=[]
    class Worker:
        def request(self,operation,payload):
            requests.append((operation,payload))
            if operation=='status':raise preview_worker_client.PreviewWorkerUnavailable('unregistered_job')
            return {'state':'running' if operation=='start' else 'ready'}
    monkeypatch.setattr(preview_runner,'_worker',lambda:Worker())
    result=preview_runner.start(workspace)
    assert result['url']==f'/api/workspaces/{workspace.id}/preview/live/'
    assert [op for op,_ in requests]==['status','prepare','start']
    prepared=requests[1][1];assert prepared['framework']=='node' and prepared['entrypoint']=='server.js'
    with tarfile.open(fileobj=io.BytesIO(base64.b64decode(prepared['archive'])),mode='r:*') as archive:
        names=archive.getnames()
        assert 'server.js' in names and 'nested/page.html' in names
    assert (root/'server.js').read_text()=='throw Error("HOST_EXECUTION_FORBIDDEN")'
