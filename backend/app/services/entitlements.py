"""Access decisions over the existing User trial and verified Subscription state."""
from datetime import datetime, timedelta, timezone
from math import ceil
from fastapi import HTTPException
from sqlalchemy import select
from ..models import User, Subscription

CORE_TRIAL_DAYS = 30
ADVANCED_TRIAL_DAYS = 0  # Disabled: the only trial is the initial 30 days
ACCOUNT_RETENTION_DAYS = 90

def aware(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value

def access_payload(db, user, *, now=None):
    now = now or datetime.now(timezone.utc)
    core_end = aware(user.trial_ends_at)
    row = db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    paid = bool(row and row.status == "active" and row.plan_id and aware(row.current_period_end) and aware(row.current_period_end) > now)
    admin = user.role in {"admin", "owner"}
    core = admin or paid or bool(core_end and core_end > now)
    advanced = core
    reason = "administration" if admin else "subscription" if paid else "trial" if core else "subscription_required"
    # First verified payment permanently supersedes the one-time 30-day trial.
    # An expired paid subscription never reactivates the original trial.
    paid_history = bool(row and row.plan_id and row.started_at and
        row.status in {"active", "expired", "cancelled"} and row.current_period_end)
    if paid_history and not paid:
        core = admin
        advanced = admin
        reason = "administration" if admin else "subscription_required"
    end = aware(row.current_period_end) if paid_history else core_end
    # Account retention is independent of workspace-file/cache lifetimes. This
    # marks archival rather than deletion of customer/billing relationships.
    from .customer_lifecycle import archive_deadline
    def days(end):
        return max(0, ceil((end - now).total_seconds() / 86400)) if end else None
    return {
        "allowed": core, "reason": reason,
        "kind": "administration" if admin else "subscription" if paid_history else "trial",
        "ends_at": end, "remaining_days": None if admin else days(end),
        "account_retention": {"minimum_days": ACCOUNT_RETENTION_DAYS,
                              "archive_at": archive_deadline(user, row) if not core else None},
        "core_access": core, "advanced_integrations": advanced,
        "byok_access": advanced, "github_access": advanced, "custom_agent_access": advanced,
        # Purchased access is a separate clock. Selecting a plan or browsing
        # integrations never changes trial dates or grants paid days.
        "paid_access": {"active": paid, "ends_at": aware(row.current_period_end) if paid else None,
                        "remaining_days": days(aware(row.current_period_end)) if paid else 0,
                        "plan_id": row.plan_id if paid else None},
        "core_trial": {"started_at": user.trial_started_at, "ends_at": core_end, "remaining_days": 0 if paid_history else days(core_end), "active": bool(not paid_history and core_end > now)},
        "advanced_trial": {"started_at": None, "ends_at": None,
                           "remaining_days": 0, "duration_days": 0, "state": "disabled"},
    }

def require_advanced(db, user, *, start=False):
    # Lock the existing account only for actual use; discovery never starts a timer.
    access = access_payload(db, user)
    if not access["advanced_integrations"]:
        raise HTTPException(402, "Advanced integrations trial ended. An active paid subscription is required; existing data and disconnect remain available.")
    return access
