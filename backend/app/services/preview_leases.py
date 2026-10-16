"""Pure lifecycle rules for future durable Preview worker leases.

NO process execution, container management, network calls, or database writes.
A subsequent worker service must persist leases transactionally and enforce
timeouts outside the Gateway process. Status polling is not user activity.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

IDLE_SECONDS = 300
VALID_STATES = frozenset({"queued", "starting", "running", "stopped", "failed", "expired"})

@dataclass(frozen=True)
class PreviewLease:
    owner_id: str
    workspace_id: str
    state: str
    last_user_activity_at: datetime
    started_at: datetime | None = None

def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Timezone-aware datetime required")
    return value.astimezone(timezone.utc)

def should_expire(lease: PreviewLease, *, now: datetime) -> bool:
    """Only active runtime can idle-expire; no renewal from status GET/poll."""
    if lease.state not in VALID_STATES:
        raise ValueError("Unknown preview state")
    if lease.state != "running":
        return False
    return _utc(now) >= _utc(lease.last_user_activity_at) + timedelta(seconds=IDLE_SECONDS)

def transition(lease: PreviewLease, event: str, *, now: datetime) -> PreviewLease:
    """Validate actions before the durable scheduler processes them.

    A stopped/expired runtime CANNOT resume from background polling; only
    explicit user 'start' authorizes another queued execution.
    """
    stamp = _utc(now)
    if lease.state not in VALID_STATES:
        raise ValueError("Unknown preview state")
    if event == "start":
        if lease.state in {"queued", "starting", "running"}:
            raise ValueError("Preview is already active or queued")
        return PreviewLease(lease.owner_id, lease.workspace_id, "queued", stamp)
    if event == "worker_started" and lease.state == "starting":
        return PreviewLease(lease.owner_id, lease.workspace_id, "running", stamp, stamp)
    if event == "worker_reserved" and lease.state == "queued":
        return PreviewLease(lease.owner_id, lease.workspace_id, "starting", lease.last_user_activity_at, lease.started_at)
    if event == "user_activity" and lease.state == "running":
        if stamp < _utc(lease.last_user_activity_at):
            raise ValueError("Activity timestamp cannot go backwards")
        return PreviewLease(lease.owner_id, lease.workspace_id, "running", stamp, lease.started_at)
    if event == "idle_expired" and should_expire(lease, now=stamp):
        return PreviewLease(lease.owner_id, lease.workspace_id, "expired", lease.last_user_activity_at, lease.started_at)
    if event == "stop" and lease.state in {"queued", "starting", "running"}:
        return PreviewLease(lease.owner_id, lease.workspace_id, "stopped", lease.last_user_activity_at, lease.started_at)
    if event == "failed" and lease.state in {"queued", "starting", "running"}:
        return PreviewLease(lease.owner_id, lease.workspace_id, "failed", lease.last_user_activity_at, lease.started_at)
    raise ValueError("Transition not permitted")
