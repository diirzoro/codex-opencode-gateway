"""Framework detection is read-only; these tests do not claim app execution."""
import json
import os
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1/test")
from backend.app.services import preview, workspaces


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr(workspaces, "settings", SimpleNamespace(workspace_root=tmp_path))
    workspace=SimpleNamespace(id=uuid.uuid4(),user_id=uuid.uuid4(),status="ready")
    root=workspaces.root_for(workspace);root.mkdir(parents=True)
    return workspace, root


@pytest.mark.parametrize("dependency,expected", [
    ("next", "nextjs"), ("vite", "vite"), ("@angular/core", "angular"),
    ("svelte", "svelte"), ("react", "react"), ("vue", "vue"), ("express", "node")])
def test_web_framework_detection_does_not_execute_scripts(source, dependency, expected):
    workspace,root=source
    (root/"package.json").write_text(json.dumps({"dependencies":{dependency:"fixture"},
        "scripts":{"start":"touch MUST_NOT_EXECUTE"}}))
    result=preview.detect(workspace)
    assert result["framework"] == expected
    assert result["runnable_preview_available"] is False
    assert not (root/"MUST_NOT_EXECUTE").exists()


def test_static_preview_is_sandboxed_and_does_not_read_outside_workspace(source):
    workspace,root=source
    (root/"index.html").write_text('<h1>Fixture</h1><script>console.log("fixture")</script>')
    result=preview.render(workspace)
    assert "connect-src 'none'" in result["html"]
    assert "form-action 'none'" in result["html"]
    assert "Fixture" in result["html"]
    with pytest.raises(HTTPException):preview.render(workspace,"../private.html")
    with pytest.raises(HTTPException):preview.render(workspace,"package.json")


def test_symlink_manifest_cannot_escape_owner_directory(source, tmp_path):
    workspace,root=source
    target=tmp_path/"other-owner.json";target.write_text('{"private":"must-not-read"}')
    (root/"package.json").symlink_to(target)
    with pytest.raises(HTTPException) as error:preview.detect(workspace)
    assert error.value.status_code == 403


@pytest.mark.parametrize("filename,framework,family",[("package.json","node","node"),("requirements.txt","python","python"),("artisan","laravel","php"),("Cargo.toml","rust",None)])
def test_runner_plan_is_fail_closed_and_has_no_host_execution(source,filename,framework,family):
    from backend.app.services.preview_runner import plan
    workspace,root=source
    (root/filename).write_text('{"scripts":{"start":"touch MUST_NOT_EXECUTE"}}' if filename=='package.json' else '')
    result=plan(workspace)
    assert result['framework']==framework and result['runtime_family']==family
    assert result['state']=='blocked' and result['execution_enabled'] is False
    assert result['limits']['network']=='none' and result['limits']['public_ports']==[]
    assert result['limits']['uid']!=0 and result['limits']['read_only_root']
    assert not result['limits']['docker_socket'] and not result['limits']['host_secrets']
    assert result['routing']['authentication_required'] and result['routing']['separate_origin_required']
    assert str(root) not in json.dumps(result)
    assert not (root/'MUST_NOT_EXECUTE').exists()


def test_runner_limits_are_not_shared_mutable_api_state(source):
    from backend.app.services.preview_runner import plan, LIMITS
    workspace,root=source
    first=plan(workspace)
    first['limits']['drop_capabilities'].clear()
    first['limits']['public_ports'].append(8080)
    assert LIMITS['drop_capabilities']==['ALL'] and LIMITS['public_ports']==[]


@pytest.mark.parametrize('dependency,executable',[('next','next'),('vite','vite'),('@angular/core','ng')])
def test_launch_profiles_are_argv_only_and_never_run_package_scripts(source,dependency,executable):
    from backend.app.services.preview_runner import launch_options
    workspace,root=source
    (root/'package.json').write_text(json.dumps({'dependencies':{dependency:'fixture'},'scripts':{'start':'touch MUST_NOT_EXECUTE'}}))
    result=launch_options(workspace)
    assert result['argv'][0]=='./node_modules/.bin/'+executable
    assert result['internal_port']==8080 and not result['execution_enabled']
    assert not (root/'MUST_NOT_EXECUTE').exists()


def test_snapshot_excludes_secrets_dependencies_and_git(source):
    import io,tarfile
    from backend.app.services.preview_snapshot import export
    workspace,root=source
    (root/'main.py').write_text('print("not executed")')
    for name in ('.env.production','secret.pem','opencode.json'):(root/name).write_text('private-fixture')
    (root/'.git').mkdir();(root/'.git'/'config').write_text('private-fixture')
    out=io.BytesIO();result=export(workspace,out)
    assert result['files']==1
    out.seek(0)
    with tarfile.open(fileobj=out) as archive:
        assert archive.getnames()==['main.py']
        item=archive.getmembers()[0];assert item.mode==0o444 and item.isreg()
        assert archive.extractfile(item).read()==b'print("not executed")'


@pytest.mark.parametrize('kind',['symlink','hardlink','fifo'])
def test_snapshot_rejects_links_and_special_files(source,tmp_path,kind):
    import io
    from backend.app.services.preview_snapshot import export
    workspace,root=source
    target=tmp_path/'outside';target.write_text('must-not-export')
    if kind=='symlink':(root/'unsafe').symlink_to(target)
    elif kind=='hardlink':os.link(target,root/'unsafe')
    else:os.mkfifo(root/'unsafe')
    with pytest.raises(HTTPException) as error:export(workspace,io.BytesIO())
    assert error.value.status_code==403


def test_snapshot_limits_actual_source_bytes(source,monkeypatch):
    import io
    from backend.app.services import preview_snapshot
    workspace,root=source;(root/'large.txt').write_bytes(b'12345')
    monkeypatch.setattr(preview_snapshot,'MAX_BYTES',4)
    with pytest.raises(HTTPException) as error:preview_snapshot.export(workspace,io.BytesIO())
    assert error.value.status_code==413
