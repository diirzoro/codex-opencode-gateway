"""Transactional Preview lease storage, intentionally dormant until migration.

Do not call from API routes until the PreviewRuntimeLease migration exists,
worker admission is transactional, and the isolated runner is verified.
Preview and OpenCode agent lifecycles MUST remain independent.
"""
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models.preview import PreviewRuntimeLease
from .preview_leases import PreviewLease, transition


def _from_row(row: PreviewRuntimeLease) -> PreviewLease:
    def aware(value):
        if value is None:
            return None
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return PreviewLease(str(row.user_id), str(row.workspace_id), row.state,
                        aware(row.last_user_activity_at), aware(row.started_at))


def owned_for_update(db: Session, *, user_id, workspace_id) -> PreviewRuntimeLease | None:
    """Lock only the owning customer's Preview lease, not an agent session."""
    return db.scalar(select(PreviewRuntimeLease).where(
        PreviewRuntimeLease.user_id == user_id,
        PreviewRuntimeLease.workspace_id == workspace_id,
    ).with_for_update())


def apply_transition(db: Session, *, user_id, workspace_id, event: str,
                     now: datetime) -> PreviewRuntimeLease:
    """Apply state guard while holding a DB lock; caller controls transaction.

    Only the authenticated POST/start handler may submit 'start'. Worker events
    must come from a separate authenticated, server-owned dispatcher.
    This method intentionally does NOT create any process or lease allocation.
    """
    row = owned_for_update(db, user_id=user_id, workspace_id=workspace_id)
    if row is None:
        raise LookupError("Preview lease not found")
    old = _from_row(row)
    updated = transition(old, event, now=now)
    row.state = updated.state
    row.last_user_activity_at = updated.last_user_activity_at
    row.started_at = updated.started_at
    if event == "start":
        row.generation += 1
        row.worker_id = None
        row.pool_id = None
        row.expires_at = None
    if event in {"stop", "idle_expired", "failed"}:
        row.expires_at = now
    db.flush()
    return row
