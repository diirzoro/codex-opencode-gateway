import hashlib, secrets
from datetime import timedelta, timezone

IDLE_TIMEOUT = timedelta(minutes=15)

def idle_expires_at(session):
    seen = session.last_seen_at or session.created_at
    seen = seen if seen.tzinfo else seen.replace(tzinfo=timezone.utc)
    absolute = session.expires_at
    absolute = absolute if absolute.tzinfo else absolute.replace(tzinfo=timezone.utc)
    return min(seen + IDLE_TIMEOUT, absolute)

def new_session_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, hash_session_token(raw)

def hash_session_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
