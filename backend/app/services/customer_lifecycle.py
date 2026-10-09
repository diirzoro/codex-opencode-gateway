"""Archive expired customers; reuse User, AccountAudit and existing token stores."""
import logging
import shutil
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, select
from ..config import settings
from ..database import SessionLocal
from ..models import (AccountAudit, AuthSession, ExecutionEvent, GithubAuthState,
    GithubConnection, PasswordReset, ProviderCredential, Subscription, User, Workspace, WorkspaceSession)
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
    ends = [aware(user.trial_ends_at)]
    if subscription and subscription.current_period_end:
        ends.append(aware(subscription.current_period_end))
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
    from . import opencode, workspace_cache
    from .entitlements import access_payload
    if _policy_started is None:
        initialize()
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=ACCOUNT_RETENTION_DAYS)
    if _policy_started > cutoff:
        return 0
    count = 0
    with SessionLocal() as db:
        ids = list(db.scalars(select(User.id).outerjoin(Subscription, Subscription.user_id == User.id)
            .where(User.status == "active", User.role == "customer", User.trial_ends_at <= cutoff,
                (Subscription.current_period_end.is_(None) | (Subscription.current_period_end <= cutoff)))
            .order_by(User.trial_ends_at).limit(100)))
    for identifier in ids:
        locks = []
        with SessionLocal() as db:
            try:
                user = db.scalar(select(User).where(User.id == identifier).with_for_update(skip_locked=True))
                if user is None or user.status != "active":
                    continue
                subscription = db.scalar(select(Subscription).where(Subscription.user_id == identifier))
                if access_payload(db, user, now=now)["allowed"] or now < archive_deadline(user, subscription):
                    continue
                # Never wait on a pending activity acknowledgement or execution.
                for model in (AuthSession, WorkspaceSession):
                    ids_before = set(db.scalars(select(model.id).where(model.user_id == identifier)))
                    locked = set(db.scalars(select(model.id).where(model.user_id == identifier).with_for_update(skip_locked=True)))
                    if ids_before != locked:
                        raise RuntimeError("Operational activity is in progress")
                rows = list(db.scalars(select(Workspace).where(Workspace.user_id == identifier)))
                for row in rows:
                    lock = opencode.workspace_lock(row)
                    if not lock.acquire(blocking=False):
                        raise RuntimeError("Workspace write is in progress")
                    locks.append(lock)
                    if db.scalar(select(Workspace.id).where(Workspace.id == row.id).with_for_update(skip_locked=True)) is None:
                        raise RuntimeError("Workspace upload is in progress")
                if db.scalar(select(WorkspaceSession.id).where(WorkspaceSession.user_id == identifier,
                    WorkspaceSession.status.in_(["submitted", "waiting_approval"])).limit(1)):
                    continue
                if any(not workspace_cache.runtime_idle(row) for row in rows):
                    continue
                activity = [aware(user.created_at)]
                if user.last_login_at: activity.append(aware(user.last_login_at))
                activity.extend(aware(r.last_activity_at) for r in rows)
                activity.extend(aware(value) for value in db.scalars(select(AuthSession.last_seen_at).where(
                    AuthSession.user_id == identifier, AuthSession.last_seen_at.is_not(None))))
                for row in rows:
                    opencode.stop_workspace(row)
                # Project files have their own inactivity policy; account
                # archival removes only sensitive operational runtime storage.
                runtime_base = settings.runtime_root.resolve()
                runtime = runtime_base / str(identifier)
                if runtime.is_symlink(): raise RuntimeError("Unsafe runtime path")
                if runtime.exists(): shutil.rmtree(runtime)
                session_ids = select(WorkspaceSession.id).where(WorkspaceSession.user_id == identifier)
                db.execute(delete(ExecutionEvent).where(ExecutionEvent.session_id.in_(session_ids)))
                for model in (WorkspaceSession, AuthSession, ProviderCredential, GithubAuthState, GithubConnection, PasswordReset):
                    db.execute(delete(model).where(model.user_id == identifier))
                user.status = "archived"
                # Retain identity/contact/billing relationships, not a CRM copy
                # of the old login secret. A later paid activation permits reset.
                user.password_hash = "!archived!"
                user.postal_code = ""; user.region_id = user.city_id = None
                db.add(AccountAudit(subject_id=identifier, action="account.last_activity", created_at=max(activity)))
                db.add(AccountAudit(subject_id=identifier, action="account.archived"))
                db.commit(); count += 1
            except Exception:
                db.rollback()
                logger.warning("Customer archival could not complete for %s", identifier)
            finally:
                for lock in reversed(locks): lock.release()
    return count
