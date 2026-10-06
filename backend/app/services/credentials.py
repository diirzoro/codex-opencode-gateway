"""Server-side encryption for persisted provider credentials.

The key lives outside the database (environment/secret store). If no key is configured,
callers must store runtime-only and never claim durable persistence.
"""
import base64, hashlib
from fastapi import HTTPException
from ..config import settings

def available() -> bool:
    return bool(settings.credentials_encryption_key)

def _fernet():
    if not available():
        raise HTTPException(503, "Encrypted credential storage is not configured")
    try:
        from cryptography.fernet import Fernet
    except ImportError:  # pragma: no cover
        raise HTTPException(503, "Credential encryption dependency is unavailable")
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.credentials_encryption_key.encode()).digest())
    return Fernet(key)

def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()

def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
