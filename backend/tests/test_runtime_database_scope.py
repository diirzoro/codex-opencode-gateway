"""Cold-start DB scope: a request must not need a second pooled connection."""
import os
import sys
import uuid
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1/test")

from sqlalchemy import create_engine
from sqlalchemy.exc import TimeoutError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import pytest
from backend.app import database
from backend.app.models import ProviderCredential, UserProviderCredential
from backend.app.services import opencode, policy


def test_credential_restore_uses_callers_only_connection(monkeypatch):
    # SQLite is only a pool/transaction ownership unit fixture, not PG evidence.
    engine = create_engine("sqlite://", poolclass=QueuePool, pool_size=1,
                           max_overflow=0, pool_timeout=.05)
    UserProviderCredential.__table__.create(engine)
    ProviderCredential.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", factory)
    workspace = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
    try:
        with factory() as owned:
            connection = owned.connection()  # request owns the sole connection
            # Reproduce why opening an independent nested session is unsafe.
            service = SimpleNamespace(restore_passes=0, timings={})
            with pytest.raises(TimeoutError):
                opencode._initialize(service, workspace)
            opencode._initialize(service, workspace, db=owned)
            assert service.restore_passes == 2
            assert owned.connection() is connection and owned.in_transaction()
        # Standalone workers still open/close their own sessions normally.
        opencode._initialize(service, workspace)
        assert service.restore_passes == 3
    finally:
        engine.dispose()


def test_cold_account_start_passes_db_without_owning_transaction(tmp_path, monkeypatch):
    db = Mock()
    monkeypatch.setattr(database, "SessionLocal", Mock(side_effect=AssertionError("Nested DB session")))
    monkeypatch.setattr(opencode, "settings", SimpleNamespace(runtime_mode="local", runtime_root=tmp_path,
                                                            opencode_binary=sys.executable))
    service = Mock()
    service.timings = {}
    process = Mock(); process.poll.return_value = None
    monkeypatch.setattr(opencode, "OpenCodeService", Mock(return_value=service))
    monkeypatch.setattr(opencode.subprocess, "Popen", Mock(return_value=process))
    load = Mock(return_value=SimpleNamespace())
    monkeypatch.setattr(policy, "load", load)
    monkeypatch.setattr(policy, "permission_config", lambda row: {})
    initialize = Mock()
    monkeypatch.setattr(opencode, "_initialize", initialize)
    account = opencode.account_workspace(uuid.uuid4())
    try:
        _, actual = opencode.for_account(account.user_id, db=db)
        assert actual is service
        load.assert_called_once_with(db)
        initialize.assert_called_once_with(service, account, db=db)
        db.close.assert_not_called(); db.commit.assert_not_called(); db.rollback.assert_not_called()
    finally:
        opencode.stop_workspace(account)


def test_catalog_forwards_authenticated_request_db(monkeypatch):
    from threading import RLock
    from backend.app.routes import workspaces
    user, db = SimpleNamespace(id=uuid.uuid4()), Mock()
    runtime = SimpleNamespace(state_lock=RLock())
    account = opencode.account_workspace(user.id)
    start = Mock(return_value=(account, runtime))
    monkeypatch.setattr(opencode, "for_account", start)
    catalog = Mock(return_value={"all":[]})
    monkeypatch.setattr(workspaces.opencode_catalog, "public_catalog", catalog)
    workspaces._account_public_catalog(user, "/provider", db)
    start.assert_called_once_with(user.id, db=db)
    catalog.assert_called_once_with("/provider", agents=False, service=runtime)
