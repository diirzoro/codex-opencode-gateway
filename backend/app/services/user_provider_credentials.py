"""User-owned encrypted API credentials, independent of project/workspace.

This repository does not mutate legacy workspace credentials. Runtime installation
and OAuth are separate operations and must be authorized before use.
"""
from fastapi import HTTPException
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from ..models import UserProviderCredential


def require_schema(db: Session):
    """Fail clearly before account connection reads if migration 0017 is absent."""
    if not inspect(db.connection()).has_table("user_provider_credentials"):
        raise HTTPException(503, "Account provider connections require database migration 0017")


def find(db: Session, user_id, provider_id: str):
    return db.scalar(select(UserProviderCredential).where(
        UserProviderCredential.user_id == user_id,
        UserProviderCredential.provider_id == provider_id,
    ))


def list_owned(db: Session, user_id):
    return list(db.scalars(select(UserProviderCredential).where(
        UserProviderCredential.user_id == user_id
    ).order_by(UserProviderCredential.provider_id)))


def save_encrypted(db: Session, user_id, provider_id: str, ciphertext: str, last4: str):
    """Stage the upsert; transaction ownership stays with the calling route."""
    if not isinstance(provider_id, str) or not provider_id or len(provider_id) > 120:
        raise ValueError("Invalid provider identifier")
    if not isinstance(ciphertext, str) or not ciphertext:
        raise ValueError("Encrypted credential is required")
    if not isinstance(last4, str) or len(last4) > 4:
        raise ValueError("Invalid credential fingerprint")
    row = find(db, user_id, provider_id)
    if row is not None:
        raise HTTPException(409, "This provider is already connected to your account")
    row = UserProviderCredential(
        user_id=user_id, provider_id=provider_id,
        ciphertext=ciphertext, last4=last4,
    )
    db.add(row)
    return row


def delete_owned(db: Session, user_id, provider_id: str):
    """Delete only the requesting user's key, not another user's credentials."""
    row = find(db, user_id, provider_id)
    if row is not None:
        db.delete(row)
    return row is not None


def replace_encrypted_if_current(db: Session, user_id, provider_id: str,
                                 expected_ciphertext: str, new_ciphertext: str):
    """Compare-and-swap for OAuth rotation; caller owns transaction/commit.

    A refresh that started from an older credential cannot overwrite a token
    already updated by another runtime. Returning False requires the caller
    to discard its stale token and re-read current account credentials.
    """
    if not expected_ciphertext or not new_ciphertext:
        raise ValueError("Encrypted credentials are required")
    row = db.scalar(select(UserProviderCredential).where(
        UserProviderCredential.user_id == user_id,
        UserProviderCredential.provider_id == provider_id,
    ).with_for_update())
    if row is None or row.ciphertext != expected_ciphertext:
        return False
    if new_ciphertext == expected_ciphertext:
        return True
    row.ciphertext = new_ciphertext
    return True
