"""Public plan catalog used by the landing page. Read-only."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Plan

router = APIRouter(prefix="/api/plans", tags=["plans"])

# Deprecated offers remain in the database only for historical orders.
LEGACY_PLAN_CODES = ("monthly", "two_months", "three_months")

@router.get("")
def list_plans(db: Session = Depends(get_db)):
    rows = db.scalars(select(Plan).where(Plan.active.is_(True), Plan.code.notin_(LEGACY_PLAN_CODES)).order_by(Plan.sort_order, Plan.id))
    return [{"id": p.id, "code": p.code, "name": p.name, "price_cents": p.price_cents, "currency": p.currency, "duration_days": p.duration_days,
             "storage_mb": p.storage_mb, "description_ar": p.description_ar, "description_en": p.description_en,
             "includes_ai_api": False,
             "service_description": "Gateway platform, free built-in services and shared local/GitHub workspace storage. Bring your own AI provider/API credentials."} for p in rows]
