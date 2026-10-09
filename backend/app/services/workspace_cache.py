"""Inactivity cleanup of workspace files, independent of account entitlement.

Reuse Workspace.last_activity_at, row/process locks and AccountAudit. Never
remove account/payment records, native conversation storage or remote repos.
"""
import logging
import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import and_, or_, select, update
from ..database import SessionLocal
from ..models import AccountAudit, Project, Workspace, WorkspaceSession
from .entitlements import aware

LOCAL_RETENTION = timedelta(days=7)
LOCAL_WARNING = timedelta(days=5)
GITHUB_RETENTION = timedelta(hours=73)
POLICY_ACTION = "workspace.file_retention_started"
_policy_started = None
logger = logging.getLogger(__name__)


def initialize():
    global _policy_started
    with SessionLocal() as db:
        # The persisted start grants existing files a full initial grace period.
        marker = db.scalar(select(AccountAudit).where(AccountAudit.action == POLICY_ACTION)
                           .order_by(AccountAudit.created_at, AccountAudit.id).limit(1))
        if marker is None:
            marker = AccountAudit(action=POLICY_ACTION)
            db.add(marker); db.commit(); db.refresh(marker)
        _policy_started = aware(marker.created_at)


def cache_payload(workspace, *, now=None):
    now = now or datetime.now(timezone.utc)
    github = workspace.project.source_type == "github"
    duration = GITHUB_RETENTION if github else LOCAL_RETENTION
    base = aware(workspace.last_activity_at)
    if _policy_started:
        base = max(base, _policy_started)
    expired = workspace.status in {"cache_expiring", "cache_expired"}
    return {"scope": "github_working_copy" if github else "local_project",
            "retention_hours": int(duration.total_seconds() / 3600),
            "expires_at": base + duration, "expired": expired,
            "warning": not github and not expired and now >= base + LOCAL_WARNING}


def touch(db, workspace_id, user_id, now=None):
    row = db.scalar(select(Workspace).where(Workspace.id == workspace_id, Workspace.user_id == user_id)
                    .with_for_update().execution_options(populate_existing=True))
    if row is None:
        raise HTTPException(404, "Workspace not found")
    if row.status not in {"cache_expiring", "cache_expired"}:
        row.last_activity_at = now or datetime.now(timezone.utc)
    return row


def begin_upload(request, workspace_id):
    # Acquire before multipart parsing, so a slow in-flight upload is protected
    # across workers. The upload route performs no second workspace row lock.
    from ..routes.dependencies import require_user, require_workspace_entitlement
    db = SessionLocal()
    try:
        user = require_user(request, db)
        require_workspace_entitlement(request, user, db)
        row = touch(db, workspace_id, user.id)
        if row.status in {"cache_expiring", "cache_expired"}:
            raise HTTPException(410, "Workspace files have expired")
        db.flush()
        return db
    except Exception:
        db.close()
        raise


def end_upload(db, success):
    try:
        if success: db.commit()
        else: db.rollback()
    finally:
        db.close()


def runtime_idle(row):
    from . import opencode
    if opencode.settings.runtime_mode != "local":
        return True
    try:
        service = opencode.for_workspace(row, start=False)
    except HTTPException as error:
        if error.status_code == 409:
            return True
        raise  # Cannot confirm a living runtime is idle.
    statuses = service.request("GET", "/session/status")
    return isinstance(statuses, dict) and all(isinstance(s, dict) and s.get("type") == "idle" for s in statuses.values())


def last_file_activity(path):
    # Native tools may finish outside a browser request. Ignore Git's internal
    # index refreshes, which can be caused by passive status polling.
    if not path.is_dir():
        return None
    latest = path.stat().st_mtime
    for parent, dirs, files in os.walk(path, followlinks=False):
        latest = max(latest, Path(parent).stat().st_mtime)
        dirs[:] = [d for d in dirs if d != ".git" and not (Path(parent) / d).is_symlink()]
        for name in files:
            if name == ".git":
                continue
            item = Path(parent) / name
            if not item.is_symlink():
                latest = max(latest, item.stat().st_mtime)
    return datetime.fromtimestamp(latest, timezone.utc)


def sweep(*, now=None):
    from . import opencode, workspaces
    if _policy_started is None:
        initialize()
    now = now or datetime.now(timezone.utc)
    count = 0
    with SessionLocal() as db:
        # At most 100 workspaces per pass; no filesystem scans on request paths.
        ids = list(db.scalars(select(Workspace.id).join(Project).where(Workspace.status != "cache_expired",
            or_(and_(Project.source_type == "github", Workspace.last_activity_at <= now - GITHUB_RETENTION),
                and_(Project.source_type != "github", Workspace.last_activity_at <= now - LOCAL_RETENTION)))
            .order_by(Workspace.last_activity_at).limit(100)))
    for identifier in ids:
        with SessionLocal() as db:
            row = db.get(Workspace, identifier)
            lock = opencode.workspace_lock(row)
            # Existing Git mutations take process then row locks. Never invert
            # that order, or wait behind a write/active submission during cleanup.
            if not lock.acquire(blocking=False):
                continue
            try:
                row = db.scalar(select(Workspace).where(Workspace.id == identifier)
                    .with_for_update(skip_locked=True).execution_options(populate_existing=True))
                if row is None or row.status == "cache_expired":
                    continue
                meta = cache_payload(row, now=now)
                if now < meta["expires_at"]:
                    continue
                if db.scalar(select(WorkspaceSession.id).where(WorkspaceSession.workspace_id == identifier,
                        WorkspaceSession.status.in_(["submitted", "waiting_approval"])).limit(1)):
                    continue
                if not runtime_idle(row):
                    continue
                path = workspaces.root_for(row, allow_expired=True)
                if row.status != "cache_expiring":
                    modified = last_file_activity(path)
                    if modified and aware(row.last_activity_at) < modified <= now:
                        row.last_activity_at = modified
                        if now < cache_payload(row, now=now)["expires_at"]:
                            db.commit()
                            continue
                opencode.stop_workspace(row)
                # Persist a file-access barrier before deletion; failed cleanup
                # is retried without recreating missing files or extending TTL.
                last_activity = row.last_activity_at
                db.execute(update(Workspace).where(Workspace.id == identifier).values(
                    status="cache_expiring", last_activity_at=last_activity))
                db.commit()
                if path.exists():
                    shutil.rmtree(path)
                db.execute(update(Workspace).where(Workspace.id == identifier).values(
                    status="cache_expired", last_activity_at=last_activity))
                db.add(AccountAudit(subject_id=row.user_id, action="workspace.files_cleaned:" + str(identifier)))
                db.commit(); count += 1
            except Exception:
                db.rollback()
                logger.warning("Workspace file cleanup could not complete for %s", identifier)
            finally:
                lock.release()
    return count
