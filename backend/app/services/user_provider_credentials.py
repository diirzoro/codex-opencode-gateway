"""User-owned encrypted API credentials, independent of project/workspace.

This repository does not mutate legacy workspace credentials. Runtime installation
and OAuth are separate operations and must be authorized before use.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import UserProviderCredential


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
    if not isinstance(provider_id, str) or not provider_id or len(provider_id) > 200:
        raise ValueError("Invalid provider identifier")
    if not isinstance(ciphertext, str) or not ciphertext:
        raise ValueError("Encrypted credential is required")
    if not isinstance(last4, str) or len(last4) > 4:
        raise ValueError("Invalid credential fingerprint")
    row = find(db, user_id, provider_id)
    if row is None:
        row = UserProviderCredential(
            user_id=user_id, provider_id=provider_id,
            ciphertext=ciphertext, last4=last4,
        )
        db.add(row)
    else:
        row.ciphertext = ciphertext
        row.last4 = last4
    return row


def delete_owned(db: Session, user_id, provider_id: str):
    """Delete only the requesting user's key, not another user's credentials."""
    row = find(db, user_id, provider_id)
    if row is not None:
        db.delete(row)
    return row is not None
