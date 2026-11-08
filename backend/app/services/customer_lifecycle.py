"""Archive expired customers; reuse User, AccountAudit and existing token stores."""
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select, update
from ..database import SessionLocal
from ..models import AccountAudit, AuthSession, Subscription, User
from .entitlements import ACCOUNT_RETENTION_DAYS, aware

POLICY_ACTION = "account.retention_started"
_policy_started = None
logger = logging.getLogger(__name__)


def initialize():
    global _policy_started
    with SessionLocal() as db:
        marker = db.scalar(select(AccountAudit).where(AccountAudit.action == POLICY_ACTION)
            .order_by(AccountAudit.created_at, AccountAudit.id).limit(1))
        if marker is None:
            marker = AccountAudit(action=POLICY_ACTION)
            db.add(marker); db.commit(); db.refresh(marker)
        _policy_started = aware(marker.created_at)


def archive_deadline(user, subscription):
    # Paid access supersedes the one-time trial. Retention starts from the
    # paid expiry when present, never from a superseded future trial expiry.
    paid_period = bool(subscription and subscription.plan_id and
        subscription.current_period_end and subscription.status in
        {"active", "expired", "cancelled", "pending_payment"})
    ends = [aware(subscription.current_period_end)] if paid_period else [aware(user.trial_ends_at)]
    if _policy_started:
        ends.append(_policy_started)  # Existing customers receive a full grace period.
    return max(ends) + timedelta(days=ACCOUNT_RETENTION_DAYS)


def consent_payload(db, user_id):
    events = list(db.scalars(select(AccountAudit).where(AccountAudit.subject_id == user_id,
        AccountAudit.action.like("marketing.%")).order_by(AccountAudit.id.desc())))
    latest = next((e for e in events if e.action == "marketing.opt_out" or e.action.startswith("marketing.opt_in:")), None)
    grant = next((e for e in events if e.action.startswith("marketing.opt_in:")), None)
    consent = bool(latest and latest.action.startswith("marketing.opt_in:"))
    return {"marketing_consent": consent,
        "permitted_channels": latest.action.split(":", 1)[1].split(",") if consent else [],
        "consent_at": grant.created_at if grant else None,
        "opted_out": bool(latest and latest.action == "marketing.opt_out"),
        "opted_out_at": latest.created_at if latest and latest.action == "marketing.opt_out" else None}


def archive_due(*, now=None):
    """Archive only Gateway account access, never OpenCode runtime data.

    Native owns API credentials, session history, files and process lifetime.
    Platform keeps project bindings and billing records for account recovery.
    """
    from .entitlements import access_payload
    if _policy_started is None:
        initialize()
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=ACCOUNT_RETENTION_DAYS)
    if _policy_started > cutoff:
        return 0
    archived = 0
    with SessionLocal() as db:
        ids = list(db.scalars(
            select(User.id).outerjoin(Subscription, Subscription.user_id == User.id)
            .where(User.status == "active", User.role == "customer",
                   func.coalesce(Subscription.current_period_end, User.trial_ends_at) <= cutoff)
            .order_by(User.trial_ends_at).limit(100)
        ))
    for identifier in ids:
        with SessionLocal() as db:
            try:
                user = db.scalar(select(User).where(User.id == identifier)
                    .with_for_update(skip_locked=True))
                if not user or user.status != "active":
                    continue
                subscription = db.scalar(select(Subscription).where(
                    Subscription.user_id == identifier))
                if access_payload(db,user,now=now)["allowed"] or now < archive_deadline(user,subscription):
                    continue
                # No Native service call, file staging, session-history deletion,
                # provider credential DB, or parallel runtime involvement.
                db.execute(update(AuthSession).where(AuthSession.user_id == identifier,
                    AuthSession.revoked_at.is_(None)).values(revoked_at=now))
                activity = [aware(user.created_at)]
                if user.last_login_at:
                    activity.append(aware(user.last_login_at))
                user.status = "archived"
                user.password_hash = "!archived!"
                user.postal_code = ""
                user.region_id = user.city_id = None
                db.add(AccountAudit(subject_id=identifier,
                    action="account.last_activity",created_at=max(activity)))
                db.add(AccountAudit(subject_id=identifier,action="account.archived"))
                db.commit()
                archived += 1
            except Exception:
                db.rollback()
                logger.warning("Platform-only customer archival deferred for %s",identifier)
    return archived
