"""One-time email ownership verification, tokens stored only as SHA-256 digests."""
import hashlib
import os
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import select

from ..models import EmailVerification
from ..config import settings

TOKEN_TTL = timedelta(hours=24)


def smtp_ready():
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM") and os.getenv("SMTP_USERNAME")
                and os.getenv("SMTP_PASSWORD"))


def send_link(email: str, raw: str):
    if not smtp_ready():
        raise HTTPException(503, "Email verification delivery is not configured")
    if not settings.public_base_url.startswith("https://"):
        raise HTTPException(503, "Verification links require HTTPS")
    message = EmailMessage()
    message["Subject"] = "Verify your OpenCode Gateway email"
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = email
    url = settings.public_base_url + "/api/auth/verify-email?token=" + quote(raw, safe="")
    message.set_content("Verify your email address using this link (valid for 24 hours):\n" + url)
    try:
        port = int(os.getenv("SMTP_PORT", "587"))
        with smtplib.SMTP(os.environ["SMTP_HOST"], port, timeout=12) as client:
            client.starttls(context=ssl.create_default_context())
            client.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
            client.send_message(message)
    except (OSError, smtplib.SMTPException, ValueError):
        raise HTTPException(503, "Verification email could not be delivered; try again later") from None


def create_pending(db, user):
    raw = secrets.token_urlsafe(32)
    db.add(EmailVerification(user_id=user.id, token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                             expires_at=datetime.now(timezone.utc)+TOKEN_TTL))
    return raw


def verify(db, raw):
    if not raw or len(raw) > 256:
        raise HTTPException(400, "Invalid verification link")
    digest = hashlib.sha256(raw.encode()).hexdigest()
    token = db.scalar(select(EmailVerification).where(
        EmailVerification.token_hash == digest).with_for_update())
    now = datetime.now(timezone.utc)
    expires = token.expires_at.replace(tzinfo=timezone.utc) if token and token.expires_at and token.expires_at.tzinfo is None else (token.expires_at if token else None)
    if token is None or token.used_at is not None or expires is None or expires <= now:
        raise HTTPException(400, "Verification link is expired or has already been used")
    return token, now
