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


def test_legacy_email_link_cannot_exceed_one_minute_even_with_old_expiry():
    now=datetime.now(timezone.utc)
    row=SimpleNamespace(user_id="test-user-id",used_at=None,
                        created_at=now-timedelta(seconds=61),
                        expires_at=now+timedelta(hours=12))
    db=Mock();db.scalar.return_value=row
    with pytest.raises(HTTPException) as exc:
        email_verification.verify(db,"a"*43)
    assert exc.value.status_code==400


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


def test_profile_change_password_is_optional_and_password_is_not_changed():
    from backend.app.routes.profile_changes import Begin, Confirm
    request = Begin.model_validate({"email": "new@example.org"})
    assert request.current_password is None
    assert request.email == "new@example.org"
    assert "current_password" not in Confirm.model_fields


def test_resend_https_delivery_accepts_id_without_smtp(monkeypatch):
    from email.message import EmailMessage
    from types import SimpleNamespace
    from backend.app.services import email_delivery
    sent = {}
    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False
            assert kwargs["trust_env"] is False
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def post(self, url, headers, json):
            sent["url"],sent["headers"],sent["payload"]=url,headers,json
            return SimpleNamespace(status_code=200,json=lambda:{"id":"email_fixture"})
    monkeypatch.setattr(email_delivery.httpx,"Client",FakeClient)
    msg=EmailMessage()
    msg["From"]="sender@example.org";msg["To"]="recipient@example.org"
    msg["Subject"]="Fixture verification";msg.set_content("123456")
    config={"provider":"resend","smtp_host":"smtp.resend.com","smtp_port":587,
            "smtp_from":"sender@example.org","smtp_username":"resend",
            "smtp_password":"fixture-resend-api-key"}
    email_delivery.send(config,msg,error_status=503,timeout=12)
    assert sent["url"]=="https://api.resend.com/emails"
    assert sent["headers"]["Authorization"]=="Bearer fixture-resend-api-key"
    assert sent["payload"]["to"]==["recipient@example.org"]
    assert "fixture-resend-api-key" not in str(sent["payload"])


def test_resend_rejected_sender_never_reveals_api_key(monkeypatch):
    from email.message import EmailMessage
    from types import SimpleNamespace
    from backend.app.services import email_delivery
    class FakeClient:
        def __init__(self,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def post(self,*args,**kwargs):
            return SimpleNamespace(status_code=422,text="server might contain secrets")
    monkeypatch.setattr(email_delivery.httpx,"Client",FakeClient)
    msg=EmailMessage()
    msg["From"]="sender@example.org";msg["To"]="recipient@example.org"
    msg["Subject"]="Verify";msg.set_content("123456")
    config={"provider":"resend","smtp_host":"smtp.resend.com","smtp_from":"sender@example.org",
            "smtp_username":"resend","smtp_password":"fixture-do-not-expose"}
    with pytest.raises(HTTPException) as exc:
        email_delivery.send(config,msg,error_status=503,timeout=12)
    assert exc.value.status_code==503
    assert "HTTP 422" in str(exc.value.detail)
    assert "fixture-do-not-expose" not in str(exc.value.detail)
