"""Fail-closed preview worker admission checks.

Pure decisions only: does not provision containers, reserve durable leases,
execute commands, or allow callers to override secure worker attestation.
A real scheduler must enforce admission atomically in its durable datastore.
"""
from dataclasses import dataclass
from .preview_scheduling import classify

@dataclass(frozen=True)
class WorkerCapacity:
    worker_id: str
    isolated: bool
    security_verified: bool
    cpu_free_millicores: int
    memory_free_mb: int
    disk_free_mb: int
    active_jobs: int
    max_jobs: int
    reachable: bool = False

# Conservative *admission estimates*, not an actual consumption guarantee.
BUILD_REQUIREMENTS = (1000, 768, 1024)
RUNTIME_REQUIREMENTS = (1000, 512, 512)

def assess_worker(detected: dict, worker: WorkerCapacity | None) -> dict:
    """Explain whether a *trusted registry* could admit this job.

    Never construct WorkerCapacity from untrusted request JSON; a trusted worker
    registry must own verification, heartbeat and available-resource metrics.
    """
    tier = classify(detected)["resource_tier"]
    if tier == "static":
        return {"admitted": True, "action": "serve_static", "worker_id": None,
                "reason": "No dynamic worker required"}
    if tier == "unsupported":
        return {"admitted": False, "action": "unsupported", "worker_id": None,
                "reason": "Unsupported preview framework"}
    if tier == "conditional":
        return {"admitted": False, "action": "inspect_required", "worker_id": None,
                "reason": "Framework needs static/SSR inspection inside an isolated worker"}
    if worker is None or not worker.reachable or not worker.isolated or not worker.security_verified:
        return {"admitted": False, "action": "wait_for_worker", "worker_id": None,
                "reason": "Verified reachable isolated preview worker unavailable"}
    if not worker.worker_id or any(not isinstance(v, int) or isinstance(v, bool) or v < 0
                                   for v in (worker.cpu_free_millicores, worker.memory_free_mb,
                                             worker.disk_free_mb, worker.active_jobs, worker.max_jobs)):
        return {"admitted": False, "action": "invalid_capacity", "worker_id": None,
                "reason": "Worker capacity data is invalid"}
    cpu, mem, disk = BUILD_REQUIREMENTS if tier == "build" else RUNTIME_REQUIREMENTS
    if worker.active_jobs >= worker.max_jobs or worker.cpu_free_millicores < cpu or worker.memory_free_mb < mem or worker.disk_free_mb < disk:
        return {"admitted": False, "action": "queue", "worker_id": None,
                "reason": "Worker execution slots or measured capacity exhausted"}
    return {"admitted": True, "action": "request_durable_lease", "worker_id": worker.worker_id,
            "reason": "Eligible for atomic durable reservation; not yet started"}


def request_start(detected: dict, worker: WorkerCapacity | None, *, explicit_start: bool) -> dict:
    """Guard admission behind an explicit user Preview action.

    Internal callers must pass a server-derived explicit action flag, never a
    value supplied by a GET/status request or client-provided JSON field.
    This is a policy check, not authentication, leasing, or execution.
    """
    if explicit_start is not True:
        return {"admitted": False, "action": "await_user_start", "worker_id": None,
                "reason": "Preview only starts when the user clicks Start Preview"}
    return assess_worker(detected, worker)
