"""Security regression: routine tool approvals are opt-in per conversation."""
import os
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("DATABASE_URL","postgresql+psycopg://test:test@127.0.0.1/test")
from backend.app.routes.agent import routine_enabled


def test_no_preference_requires_manual_approval():
    db=Mock()
    db.scalar.return_value=None
    assert routine_enabled(db,"session-1") is False


def test_user_enabled_routine_is_explicit():
    db=Mock()
    db.scalar.return_value=SimpleNamespace(data='{"enabled":true}')
    assert routine_enabled(db,"session-1") is True


def test_user_disabled_or_corrupt_preference_fails_closed():
    db=Mock()
    for data in ('{"enabled":false}', '{"enabled":"true"}', 'invalid'):
        db.scalar.return_value=SimpleNamespace(data=data)
        assert routine_enabled(db,"session-1") is False
