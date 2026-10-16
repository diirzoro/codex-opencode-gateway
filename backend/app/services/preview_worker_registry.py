"""Fail-closed worker freshness checks; no executable worker provisioned.

Metrics and attestation must be supplied by a trusted private registry, never
from a browser/API request. This module only rejects stale/insecure records.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from .preview_admission import WorkerCapacity, assess_worker

MAX_HEARTBEAT_AGE = timedelta(seconds=30)


@dataclass(frozen=True)
class WorkerHeartbeat:
    capacity: WorkerCapacity
    observed_at: datetime
    isolation_verified_at: datetime


def _utc(dt: datetime) -> datetime:
    if not isinstance(dt, datetime) or dt.tzinfo is None:
        raise ValueError("Worker timestamps must be timezone-aware")
    return dt.astimezone(timezone.utc)


def available_worker(detected: dict, heartbeat: WorkerHeartbeat | None, *, now: datetime) -> dict:
    """Only fresh and attested worker records can be considered for admission.

    A positive decision remains advisory until atomically reserved in DB and
    reconciled with an actual sandbox worker. The Gateway MUST NOT launch code.
    """
    now_utc = _utc(now)
    if heartbeat is None:
        return assess_worker(detected, None)
    observed = _utc(heartbeat.observed_at)
    verified = _utc(heartbeat.isolation_verified_at)
    if observed > now_utc or verified > now_utc or now_utc - observed > MAX_HEARTBEAT_AGE:
        return {"admitted": False, "action": "wait_for_worker", "worker_id": None,
                "reason": "Preview worker heartbeat or attestation is not current"}
    if verified > observed or now_utc - verified > MAX_HEARTBEAT_AGE:
        return {"admitted": False, "action": "wait_for_worker", "worker_id": None,
                "reason": "Preview worker security attestation is stale"}
    return assess_worker(detected, heartbeat.capacity)
