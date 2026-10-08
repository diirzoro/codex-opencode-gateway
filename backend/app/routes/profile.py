from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..schemas import ProfilePatch, UserOut
from ..services.accounts import user_payload
from ..services.entitlements import access_payload
from .auth import validate_locations
from .dependencies import require_user
router = APIRouter(prefix="/api/profile", tags=["profile"])

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
