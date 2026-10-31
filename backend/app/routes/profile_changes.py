"""Password-confirmed client profile edits (no email delivery or OTP cost).

Client must prove ownership using the *existing* password. This endpoint never
changes that password, never sends an email, and never calls OpenCode Native.
Registration, password resets and optional GitHub OAuth verification are separate.
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AccountAudit, GithubConnection, User
from ..security.identities import normalized_phone
from ..security.passwords import verify_password
from ..services.disposable_email import require_permanent_email
from ..services.accounts import user_payload
from .dependencies import require_user

router = APIRouter(prefix="/change", tags=["profile-security"])


class ProfileValues(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str | None = Field(default=None, min_length=6, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=6, max_length=30)
    postal_code: str | None = Field(default=None, min_length=2, max_length=24)


class ProfileUpdate(ProfileValues):
    current_password: str = Field(min_length=1, max_length=128)


def _values(db, user, payload):
    values = payload.model_dump(exclude_unset=True, exclude={"current_password"})
    if not values:
        raise HTTPException(422, "Choose an account detail to change")
    if any(v is None for v in values.values()):
        raise HTTPException(422, "Account identity fields cannot be empty")
    if "username" in values:
        value = values["username"].strip().casefold()
        if not re.fullmatch(r"[a-z0-9_.-]{6,50}", value):
            raise HTTPException(422, "Invalid username")
        values["username"] = value
        if db.scalar(select(User.id).where(User.id != user.id, func.lower(User.username) == value)) is not None:
            raise HTTPException(409, "Username is already registered")
    if "email" in values:
        value = str(values["email"]).strip().casefold()
        require_permanent_email(value)
        values["email"] = value
        if db.scalar(select(User.id).where(User.id != user.id, func.lower(User.email) == value)) is not None:
            raise HTTPException(409, "Email is already registered")
    if "phone" in values or "postal_code" in values:
        phone = normalized_phone(values.get("phone", user.phone), values.get("postal_code", user.postal_code))
        if not phone:
            raise HTTPException(422, "Enter a valid international phone number")
        values["phone"] = phone
        if db.scalar(select(User.id).where(User.id != user.id, User.phone_identity == phone)) is not None:
            raise HTTPException(409, "Phone is already registered")
    if not any(getattr(user, k) != v for k, v in values.items()):
        raise HTTPException(409, "No account detail was changed")
    return dict(sorted(values.items()))


def _github_email_guard(db, user, values):
    if "email" in values and values["email"] != user.email:
        if db.scalar(select(GithubConnection.id).where(GithubConnection.user_id == user.id)) is not None:
            raise HTTPException(409, "Disconnect GitHub before changing your Gateway email to maintain verified primary-email matching")


@router.post("/update")
def update_profile(data: ProfileUpdate, user: User = Depends(require_user), db: Session = Depends(get_db)):
    # The user requested no email verification on profile edits. Existing
    # password is therefore mandatory even for updating a single field.
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(403, "Current account password is incorrect; account ownership was not verified")
    values = _values(db, user, data)
    _github_email_guard(db, user, values)
    for key, value in values.items():
        setattr(user, key, value)
    db.add(AccountAudit(actor_id=user.id, subject_id=user.id, action="account.profile_password_authorized_update"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account identifier was already claimed during the update") from None
    db.refresh(user)
    return user_payload(user)
