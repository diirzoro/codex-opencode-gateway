import hashlib, secrets

def new_session_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, hash_session_token(raw)

def hash_session_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
