"""Offline contract checks for account-level API-key connections.

These tests mock OpenCode process startup and database writes; they are not a
substitute for isolated PostgreSQL/OpenCode integration tests.
"""
import os
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1/test")

from backend.app.routes import workspaces as routes
from backend.app.services import account_provider_runtime


@pytest.fixture
def setup_account(monkeypatch):
    user=SimpleNamespace(id="test-user",role="customer")
    db=Mock()
    db.scalar.return_value=None
    db.scalars.return_value=[]
    monkeypatch.setattr(routes.user_provider_credentials,"require_schema",lambda db:None)
    monkeypatch.setattr(routes.user_provider_credentials,"find",lambda db,uid,pid:None)
    saved=Mock()
    monkeypatch.setattr(routes.user_provider_credentials,"save_encrypted",saved)
    monkeypatch.setattr(routes,"require_advanced",lambda *args,**kwargs:None)
    monkeypatch.setattr(routes.policy,"load",lambda db:None)
    monkeypatch.setattr(routes.policy,"provider_allowed",lambda *args:True)
    monkeypatch.setattr(routes.credentials,"available",lambda:True)
    monkeypatch.setattr(routes.credentials,"encrypt",lambda x:"ciphertext-placeholder")
    monkeypatch.setattr(routes.providers,"resolve_provider",lambda data,pid:{"id":pid})
    monkeypatch.setattr(routes.providers,"connection_methods",lambda service,pid:[{"type":"key"}])
    monkeypatch.setattr(routes.providers,"set_api_key",lambda *args:True)
    monkeypatch.setattr(routes.providers,"validate_model",lambda *args:"model-1")
    monkeypatch.setattr(routes,"_refresh_other_user_runtimes",lambda *args:None)
    service=Mock()
    service.request.return_value={"all":[{"id":"openai","models":{"model-1":{}}}],"connected":[]}
    @contextmanager
    def isolated(*args):
        yield service
    monkeypatch.setattr(account_provider_runtime,"isolated_validation",isolated)
    return user,db,service,saved


def test_connects_without_project_and_stores_only_encrypted_key(setup_account):
    user,db,service,saved=setup_account
    result=routes.connect_account_provider("openai",
        routes.ApiKeyCredential(api_key="SECRET1234",model_id="model-1",method=0),user,db)
    assert result["connected"] is True
    assert result["last4"]=="1234"
    assert saved.call_args.args[3]=="ciphertext-placeholder"
    db.commit.assert_called_once()


def test_duplicate_connection_rejected_before_runtime_start(setup_account,monkeypatch):
    user,db,service,saved=setup_account
    monkeypatch.setattr(routes.user_provider_credentials,"find",lambda *args:object())
    with pytest.raises(HTTPException) as exc:
        routes.connect_account_provider("openai",
            routes.ApiKeyCredential(api_key="SECRET1234",model_id="model-1",method=0),user,db)
    assert exc.value.status_code==409
    saved.assert_not_called()
    service.request.assert_not_called()


def test_stopped_workspaces_never_scrub_credentials_during_connect(monkeypatch):
    """Stopped runtimes restore new account credentials on startup; no deletion."""
    workspace=SimpleNamespace(id="stopped-workspace",user_id="test-user")
    db=Mock()
    db.scalars.return_value=[workspace]
    monkeypatch.setattr(routes.opencode,"workspace_lock",lambda owned:__import__("threading").RLock())
    monkeypatch.setattr(routes.opencode,"for_workspace",
                        lambda owned,start=False: (_ for _ in ()).throw(
                            HTTPException(409,"No running runtime")))
    monkeypatch.setattr(routes,"_scrub_runtime_provider",
                        Mock(side_effect=AssertionError("Cannot scrub on connect")))
    routes._refresh_other_user_runtimes(db,"test-user",None,"openai","encrypted-key")
    routes._scrub_runtime_provider.assert_not_called()
