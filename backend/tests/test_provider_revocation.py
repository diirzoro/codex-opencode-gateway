"""Revocation must remove persisted auth even when a runtime is stopped."""
import json
import os
import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1/test")
from backend.app.routes import workspaces as routes


@pytest.mark.parametrize("running", [False, True])
def test_disconnect_scrubs_all_owned_auth_files(tmp_path, monkeypatch, running):
    owner, other = uuid.uuid4(), uuid.uuid4()
    workspace = SimpleNamespace(id=uuid.uuid4(), user_id=owner)
    second_workspace = SimpleNamespace(id=uuid.uuid4(), user_id=owner)
    account = routes.opencode.account_workspace(owner)
    paths = []
    for uid, rid in [(owner, workspace.id), (owner, account.id), (owner, second_workspace.id), (other, uuid.uuid4())]:
        path = tmp_path / str(uid) / str(rid) / "data/opencode/auth.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"example": {"type": "api", "key": "fixture-only"},
                                    "keep": {"type": "api", "key": "keep-fixture"}}))
        paths.append(path)
    other_before = paths[-1].read_bytes()
    monkeypatch.setattr(routes, "settings", SimpleNamespace(runtime_root=tmp_path))
    monkeypatch.setattr(routes.user_provider_credentials, "require_schema", lambda db: None)
    monkeypatch.setattr(routes.user_provider_credentials, "delete_owned", lambda *args: True)
    monkeypatch.setattr(routes.providers, "record_connection", Mock())
    service = SimpleNamespace(state_lock=__import__("threading").RLock())
    def runtime(owned, start=False):
        if not running:
            raise HTTPException(409, "No running OpenCode runtime")
        return service
    monkeypatch.setattr(routes.opencode, "for_workspace", runtime)
    remove = Mock()
    monkeypatch.setattr(routes.providers, "remove", remove)
    db = Mock()
    db.scalars.side_effect = [[workspace, second_workspace], []]
    routes._remove_account_api_provider(db, SimpleNamespace(id=owner), "example")
    assert "example" not in json.loads(paths[0].read_text())
    assert "example" not in json.loads(paths[1].read_text())
    assert "keep" in json.loads(paths[0].read_text())
    assert "example" not in json.loads(paths[2].read_text())
    assert paths[-1].read_bytes() == other_before
    assert remove.call_count == (3 if running else 0)
    db.commit.assert_called_once()


def test_revocation_rejects_parent_link_into_another_account(tmp_path,monkeypatch):
    owner,other,runtime=uuid.uuid4(),uuid.uuid4(),uuid.uuid4()
    otherdir=tmp_path/str(other)/str(runtime)/"data/opencode";otherdir.mkdir(parents=True)
    path=otherdir/"auth.json";path.write_text('{"example":{"type":"api","key":"other-fixture"}}');before=path.read_bytes()
    (tmp_path/str(owner)).mkdir();(tmp_path/str(owner)/str(runtime)).symlink_to(otherdir.parent.parent,target_is_directory=True)
    monkeypatch.setattr(routes,"settings",SimpleNamespace(runtime_root=tmp_path))
    with pytest.raises(HTTPException) as error:routes._scrub_runtime_provider(owner,runtime,"example")
    assert error.value.status_code==503 and path.read_bytes()==before


def test_failed_atomic_replace_is_not_reported_as_success(tmp_path,monkeypatch):
    owner,runtime=uuid.uuid4(),uuid.uuid4()
    folder=tmp_path/str(owner)/str(runtime)/"data/opencode";folder.mkdir(parents=True)
    path=folder/"auth.json";path.write_text('{"example":{"type":"api","key":"fixture"}}');before=path.read_bytes()
    monkeypatch.setattr(routes,"settings",SimpleNamespace(runtime_root=tmp_path))
    monkeypatch.setattr(routes.account_provider_sync.os,"replace",Mock(side_effect=FileNotFoundError()))
    with pytest.raises(HTTPException) as error:routes._scrub_runtime_provider(owner,runtime,"example")
    assert error.value.status_code==503 and path.read_bytes()==before
    assert len(list(folder.iterdir()))==1
