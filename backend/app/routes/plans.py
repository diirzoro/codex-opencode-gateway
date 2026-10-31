"""Public plan catalog used by the landing page. Read-only."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Plan
from ..services.storage_policy import PLAN_MB

router = APIRouter(prefix="/api/plans", tags=["plans"])

@router.get("")
def list_plans(db: Session = Depends(get_db)):
    rows = db.scalars(select(Plan).where(Plan.active.is_(True)).order_by(Plan.sort_order, Plan.id))
    return [{"id": p.id, "code": p.code, "name": p.name, "price_cents": p.price_cents, "currency": p.currency, "duration_days": p.duration_days,
             "storage_mb": PLAN_MB.get(p.code, 50),
             "includes_ai_api": False,
             "service_description": "Gateway platform, free built-in services and shared local/GitHub workspace storage. Bring your own AI provider/API credentials."} for p in rows]
