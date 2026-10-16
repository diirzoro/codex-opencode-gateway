"""Dormant PostgreSQL atomic preview admission; never executes user projects.

Requires migration 0020 and trusted private worker heartbeat ingestion.
Caller must authenticate ownership and commit/rollback its transaction.
No public API route calls this module until sandbox security acceptance.
"""
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models.preview import PreviewRuntimeLease, PreviewWorkerCapacity
from .preview_admission import WorkerCapacity
from .preview_worker_registry import WorkerHeartbeat, available_worker


def _aware(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def reserve(db: Session, *, user_id, workspace_id, worker_id: str,
            generation: int, framework: str, now: datetime) -> bool:
    """Reserve one worker slot under its row lock and lease row lock.

    Caller owns transaction; failed results perform no writes. Locks serialize
    competing admissions to the same worker. Only trusted worker IDs allowed.
    This function must not be exposed directly to client JSON.
    """
    if now.tzinfo is None or generation < 1 or not worker_id:
        raise ValueError("Invalid reservation request")
    worker = db.scalar(select(PreviewWorkerCapacity).where(
        PreviewWorkerCapacity.worker_id == worker_id).with_for_update())
    if worker is None:
        return False
    lease = db.scalar(select(PreviewRuntimeLease).where(
        PreviewRuntimeLease.workspace_id == workspace_id,
        PreviewRuntimeLease.user_id == user_id).with_for_update())
    if lease is None or lease.state != "queued" or lease.generation != generation:
        return False
    if lease.worker_id is not None:
        return False
    capacity = WorkerCapacity(worker.worker_id, worker.isolated, worker.security_verified,
                              worker.cpu_free_millicores, worker.memory_free_mb,
                              worker.disk_free_mb, worker.active_jobs, worker.max_jobs,
                              worker.reachable)
    heartbeat = WorkerHeartbeat(capacity, _aware(worker.observed_at),
                                _aware(worker.isolation_verified_at))
    decision = available_worker({"framework": framework}, heartbeat, now=now)
    if decision["action"] != "request_durable_lease":
        return False
    worker.active_jobs += 1
    lease.worker_id = worker.worker_id
    lease.state = "starting"
    db.flush()
    return True


def release(db: Session, *, user_id, workspace_id, generation: int) -> bool:
    """Idempotently release a reservation; worker cleanup is a separate duty."""
    lease = db.scalar(select(PreviewRuntimeLease).where(
        PreviewRuntimeLease.workspace_id == workspace_id,
        PreviewRuntimeLease.user_id == user_id).with_for_update())
    if lease is None or lease.generation != generation or not lease.worker_id:
        return False
    # Serialize with admission for the same worker. Never decrement below zero.
    worker = db.scalar(select(PreviewWorkerCapacity).where(
        PreviewWorkerCapacity.worker_id == lease.worker_id).with_for_update())
    if worker is None:
        # Fail closed; preserve worker ID until reconciliation, not silently leak slot.
        return False
    worker.active_jobs = max(0, worker.active_jobs - 1)
    lease.worker_id = None
    db.flush()
    return True
