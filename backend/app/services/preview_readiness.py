"""Preview execution gates for staging rollout.

Only an operator-controlled Test deployment may enable dynamic Preview.
The flag alone never grants Docker authority: a separately authenticated
worker, capacity leases, snapshot transfer and router are prerequisites.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PreviewReadiness:
    staging: bool
    worker_authenticated: bool
    lease_store_ready: bool
    snapshot_channel_ready: bool
    private_router_ready: bool
    cleanup_reaper_ready: bool

    @property
    def enabled(self) -> bool:
        return all((
            self.staging,
            self.worker_authenticated,
            self.lease_store_ready,
            self.snapshot_channel_ready,
            self.private_router_ready,
            self.cleanup_reaper_ready,
        ))

    def missing(self) -> tuple[str, ...]:
        checks = (
            ("test_environment", self.staging),
            ("authenticated_worker", self.worker_authenticated),
            ("durable_lease_store", self.lease_store_ready),
            ("private_snapshot_transfer", self.snapshot_channel_ready),
            ("isolated_router", self.private_router_ready),
            ("automatic_cleanup_reaper", self.cleanup_reaper_ready),
        )
        return tuple(name for name, passed in checks if not passed)
