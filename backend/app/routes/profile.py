from fastapi import APIRouter, Depends, HTTPException
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, AccountAudit
from ..schemas import ProfilePatch, UserOut
from ..services.accounts import user_payload
from ..services.entitlements import access_payload
from .auth import validate_locations
from .dependencies import require_user
router = APIRouter(prefix="/api/profile", tags=["profile"])

class MarketingConsent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    marketing_consent: bool
    permitted_channels: list[Literal["email", "sms", "whatsapp"]] = Field(default_factory=list, max_length=3)

@router.get("/marketing-consent")
def marketing_consent(user: User = Depends(require_user), db: Session = Depends(get_db)):
    from ..services.customer_lifecycle import consent_payload
    return consent_payload(db, user.id)

@router.put("/marketing-consent")
def update_marketing_consent(data: MarketingConsent, user: User = Depends(require_user), db: Session = Depends(get_db)):
    from ..services.customer_lifecycle import consent_payload
    if data.marketing_consent != bool(data.permitted_channels):
        raise HTTPException(422, "Select permitted channels for explicit consent, or clear channels to opt out")
    channels = sorted(set(data.permitted_channels))
    action = "marketing.opt_in:" + ",".join(channels) if data.marketing_consent else "marketing.opt_out"
    db.add(AccountAudit(actor_id=user.id, subject_id=user.id, action=action)); db.commit()
    return consent_payload(db, user.id)

@router.get("/access")
def get_access(user: User = Depends(require_user), db: Session = Depends(get_db)):
    # Lightweight; no billing mutation, runtime startup or external GitHub request.
    return {"access": access_payload(db, user)}

@router.get("", response_model=UserOut)
def get_profile(user: User = Depends(require_user)): return user_payload(user)

@router.patch("", response_model=UserOut)
def patch_profile(data: ProfilePatch, user: User = Depends(require_user), db: Session = Depends(get_db)):
    values = data.model_dump(exclude_unset=True)
    country_id = values.get("country_id", user.country_id); region_id = values.get("region_id", user.region_id); city_id = values.get("city_id", user.city_id)
    if any(k in values for k in ("country_id", "region_id", "city_id")): validate_locations(db, country_id, region_id, city_id)
    for key, value in values.items(): setattr(user, key, value)
    db.commit(); db.refresh(user); return user_payload(user)
