"""Unit checks for one-time account verification; no SMTP or PostgreSQL connection."""
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1/test")

from backend.app.services import email_verification


def test_verification_token_created_as_hash_only():
    db = Mock()
    user = SimpleNamespace(id="test-user-id")
    raw = email_verification.create_pending(db, user)
    saved = db.add.call_args.args[0]
    assert len(raw) > 32
    assert raw != saved.token_hash
    assert len(saved.token_hash) == 64
    assert saved.user_id == user.id


@pytest.mark.parametrize("offset,expected", [
    (timedelta(minutes=15), True),
    (-timedelta(seconds=1), False),
])
def test_verification_accepts_valid_tokens_and_rejects_expired(offset, expected):
    now = datetime.now(timezone.utc)
    stored = SimpleNamespace(user_id="test-user-id", used_at=None,
                             expires_at=(now + offset).replace(tzinfo=None))
    db = Mock()
    db.scalar.return_value = stored
    if expected:
        token, _ = email_verification.verify(db, "a"*43)
        assert token is stored
    else:
        with pytest.raises(HTTPException) as exc:
            email_verification.verify(db, "a"*43)
        assert exc.value.status_code == 400


def test_used_token_is_rejected():
    db = Mock()
    db.scalar.return_value = SimpleNamespace(
        used_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
    with pytest.raises(HTTPException) as exc:
        email_verification.verify(db, "b"*43)
    assert exc.value.status_code == 400


def test_missing_smtp_configuration_blocks_delivery(monkeypatch):
    for key in ("SMTP_HOST", "SMTP_FROM", "SMTP_USERNAME", "SMTP_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(HTTPException) as exc:
        email_verification.send_link("test@example.org", "fake")
    assert exc.value.status_code == 503
