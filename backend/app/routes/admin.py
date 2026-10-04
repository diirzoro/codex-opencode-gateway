from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..services.accounts import user_payload
from .dependencies import require_admin
router = APIRouter(prefix="/api/admin", tags=["admin"])
@router.get("/users")
def users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [user_payload(u) for u in db.scalars(select(User).order_by(User.created_at.desc()))]

@router.get("/overview")
def overview(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    total = db.scalar(select(func.count(User.id))) or 0
    active = db.scalar(select(func.count(User.id)).where(User.status == "active")) or 0
    admins = db.scalar(select(func.count(User.id)).where(User.role == "admin")) or 0
    trial_active = db.scalar(select(func.count(User.id)).where(User.trial_ends_at > now)) or 0
    trial_expired = db.scalar(select(func.count(User.id)).where(User.trial_ends_at <= now)) or 0
    return {
        "users": {"total": total, "active": active, "admins": admins, "trial_active": trial_active, "trial_expired": trial_expired},
        "payments": {"status": "not_available", "label": "Not available yet"},
        "visitors": {"status": "not_available", "label": "Not available yet"},
        "integrations": {"github": "not_connected", "opencode": "local_opt_in", "payments": "not_available"},
    }
