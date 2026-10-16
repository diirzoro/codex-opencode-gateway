"""Dedicated Preview-worker lifecycle state machine (no Docker access).

This module belongs to a worker service, never the public Gateway.
The executor is an injected provisioner with verified identity; this code
cannot confer authority to start a container. Ownership and durable leases
must be checked by the caller *before* invoking it.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

IDLE_LIMIT = timedelta(seconds=300)


@dataclass(frozen=True)
class WorkerJob:
    job_id: str
    lease_generation: int
    state: str
    last_user_activity: datetime
    container_id: str | None = None


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Worker activity timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def may_launch(job: WorkerJob, *, explicit_start: bool) -> bool:
    """Only a new queued generation initiated by an explicit Start can launch."""
    return (explicit_start is True and job.state == "queued"
            and job.lease_generation > 0 and job.container_id is None
            and bool(job.job_id))


def started(job: WorkerJob, container_id: str) -> WorkerJob:
    if job.state != "queued" or job.container_id is not None or not container_id:
        raise ValueError("Invalid worker launch acknowledgement")
    return WorkerJob(job.job_id, job.lease_generation, "running",
                     _utc(job.last_user_activity), container_id)


def activity(job: WorkerJob, *, at: datetime, genuine_user_action: bool) -> WorkerJob:
    """Polling, background requests and stale activity never extend runtime."""
    stamp = _utc(at)
    if not genuine_user_action or job.state != "running" or stamp < _utc(job.last_user_activity):
        return job
    if stamp - _utc(job.last_user_activity) >= IDLE_LIMIT:
        return job
    return WorkerJob(job.job_id, job.lease_generation, job.state, stamp, job.container_id)


def needs_cleanup(job: WorkerJob, *, now: datetime) -> bool:
    """A private reaper must revoke proxy routing then destroy the sandbox."""
    if job.state != "running":
        return False
    stamp = _utc(now)
    prior = _utc(job.last_user_activity)
    return stamp >= prior and stamp - prior >= IDLE_LIMIT


def stopped(job: WorkerJob, *, routing_revoked: bool,
            container_destroyed: bool) -> WorkerJob:
    """Do not report released/complete before both cleanup proofs arrive."""
    if job.state not in ("running", "stopping"):
        raise ValueError("Only allocated worker jobs can be stopped")
    if routing_revoked is not True or container_destroyed is not True:
        raise ValueError("Both proxy revocation and sandbox destruction required")
    return WorkerJob(job.job_id, job.lease_generation, "stopped",
                     job.last_user_activity, None)
