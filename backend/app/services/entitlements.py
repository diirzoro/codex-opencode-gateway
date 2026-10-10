"""Access decisions over the existing User trial and verified Subscription state."""
from datetime import datetime, timedelta, timezone
from math import ceil
from fastapi import HTTPException
from sqlalchemy import select
from ..models import User, Subscription

CORE_TRIAL_DAYS = 30
ADVANCED_TRIAL_DAYS = 10
ACCOUNT_RETENTION_DAYS = 90

def aware(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value

def access_payload(db, user, *, now=None):
    now = now or datetime.now(timezone.utc)
    core_end = aware(user.trial_ends_at)
    started = aware(user.advanced_trial_started_at)
    advanced_end = min(core_end, started + timedelta(days=ADVANCED_TRIAL_DAYS)) if started else None
    row = db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    paid = bool(row and row.status == "active" and row.plan_id and aware(row.current_period_end) and aware(row.current_period_end) > now)
    admin = user.role in {"admin", "owner"}
    core = admin or paid or bool(core_end and core_end > now)
    advanced = admin or paid or (core and (started is None or advanced_end > now))
    reason = "administration" if admin else "subscription" if paid else "trial" if core else "subscription_required"
    # Keep the last paid entitlement identifiable after expiry, without granting
    # access or confusing its expiry/plan with the independent free trial.
    subscription_entitlement = paid or bool(not core and row and row.plan_id
        and row.status in {"active", "expired", "cancelled"} and row.current_period_end)
    end = aware(row.current_period_end) if subscription_entitlement else core_end
    # Account retention is independent of workspace-file/cache lifetimes. This
    # marks archival rather than deletion of customer/billing relationships.
    from .customer_lifecycle import archive_deadline
    def days(end):
        return max(0, ceil((end - now).total_seconds() / 86400)) if end else None
    return {
        "allowed": core, "reason": reason,
        "kind": "administration" if admin else "subscription" if subscription_entitlement else "trial",
        "ends_at": end, "remaining_days": None if admin else days(end),
        "account_retention": {"minimum_days": ACCOUNT_RETENTION_DAYS,
                              "archive_at": archive_deadline(user, row) if not core else None},
        "core_access": core, "advanced_integrations": advanced,
        "byok_access": advanced, "github_access": advanced, "custom_agent_access": advanced,
        "core_trial": {"started_at": user.trial_started_at, "ends_at": core_end, "remaining_days": days(core_end), "active": bool(core_end > now)},
        "advanced_trial": {"started_at": started, "ends_at": advanced_end,
                           "remaining_days": days(advanced_end), "duration_days": ADVANCED_TRIAL_DAYS,
                           "state": "not_started" if started is None else "active" if advanced_end > now else "expired"},
    }

def require_advanced(db, user, *, start=False):
    # Lock the existing account only for actual use; discovery never starts a timer.
    if start:
        user = db.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
    access = access_payload(db, user)
    if not access["advanced_integrations"]:
        raise HTTPException(402, "Advanced integrations trial ended. An active paid subscription is required; existing data and disconnect remain available.")
    if start and user.role not in {"admin", "owner"} and access["reason"] != "subscription" and user.advanced_trial_started_at is None:
        user.advanced_trial_started_at = datetime.now(timezone.utc)
        db.flush()  # Caller commits only after the actual operation succeeds.
    return access
