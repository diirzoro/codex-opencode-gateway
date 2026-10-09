import hashlib, secrets
from datetime import timedelta, timezone

IDLE_TIMEOUT = timedelta(minutes=15)
REACTIVATION_PREFIX = "reactivation."
ARCHIVED_PASSWORD = "!archived!"

def reactivation_cookie_name():
    from ..config import settings
    return settings.session_cookie_name + "_reactivation"

def normal_access_ready(user):
    return user.status == "active" and user.password_hash != ARCHIVED_PASSWORD

def reactivation_eligible(user):
    return user.role == "customer" and (user.status == "archived" or
        user.status == "active" and user.password_hash == ARCHIVED_PASSWORD)

def new_reactivation_token():
    # The domain tag is bound into the stored hash: moving this cookie into the
    # normal cookie cannot promote its scope; stripping the tag breaks the hash.
    raw = REACTIVATION_PREFIX + secrets.token_urlsafe(32)
    return raw, hash_session_token(raw)

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
