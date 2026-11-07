"""One real Gateway disk quota for every owned local and GitHub worktree.

This is a platform-storage entitlement, NEVER an AI API/model subscription.
No write to Native, GitHub, customers' repositories or payment state here.
"""
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from ..models import PaymentOrder, Plan, Subscription, User

MIB = 1024 * 1024
TRIAL_MB = 50
MAX_PLAN_MB = 250
# Legacy paid subscriptions retain the remaining purchased period. The existing
# 2/3/5 USD plan names map to equivalent tiers, not new charges.
PLAN_MB = {
    "gateway_100": 100, "gateway_150": 150, "gateway_250": 250,
    "monthly": 100, "two_months": 150, "three_months": 250,
}


def quota_mb(db, user_id):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Account not found")
    # Admin capacity is explicitly capped, not unlimited or a second quota.
    if user.role in {"owner", "admin"}:
        return MAX_PLAN_MB
    row = db.scalar(select(Subscription).where(Subscription.user_id == user_id))
    if row is None or row.status != "active" or not row.plan_id or not row.current_period_end:
        return TRIAL_MB
    end = row.current_period_end
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if end <= datetime.now(timezone.utc):
        return TRIAL_MB
    # An unverified checkout cannot increase storage. It must have a paid order.
    approved = db.scalar(select(PaymentOrder.id).where(
        PaymentOrder.user_id == user_id, PaymentOrder.status == "paid"
    ).limit(1))
    if not approved:
        return TRIAL_MB
    plan = db.get(Plan, row.plan_id)
    return PLAN_MB.get(plan.code, TRIAL_MB) if plan else TRIAL_MB


def capacity_label(db, user_id):
    capacity = quota_mb(db, user_id)
    return "Trial" if capacity == TRIAL_MB else (
        "Basic" if capacity == 100 else "Standard" if capacity == 150 else "Plus"
    )


def require_headroom(db, user_id, *, additional=0):
    """Account-wide enforcement: no per-repo GitHub loophole."""
    from . import workspaces
    if additional < 0:
        raise HTTPException(422, "Invalid storage reservation")
    limit = quota_mb(db, user_id) * MIB
    used = workspaces.account_storage(db, user_id, stop_at=limit)
    if used >= limit or used + additional > limit:
        raise HTTPException(413,
            "Your shared Gateway storage is full. This allowance covers ALL "
            "local and imported GitHub projects together. Export/sync files, "
            "remove unused copies or upgrade your Gateway plan. "
            "AI model/API subscriptions are not included.")
    return limit - used
