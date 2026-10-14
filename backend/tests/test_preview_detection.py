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
