"""Conservative same-VPS admission gate: advisory, no host execution.

This gate is a second requirement beyond fresh worker attestation and SQL
reservation. Telemetry must originate from a trusted private host collector.
Missing or inconsistent metrics ALWAYS deny dynamic preview.
"""
from dataclasses import dataclass

# Starting envelope for a VPS reported as 4 GB RAM / 80 GB total disk.
MAX_CONCURRENT_PREVIEWS = 1
HOST_RAM_RESERVE_MB = 1536
HOST_DISK_RESERVE_MB = 4096
PREVIEW_RAM_MB = 768
PREVIEW_DISK_MB = 1024

@dataclass(frozen=True)
class HostTelemetry:
    total_ram_mb: int
    available_ram_mb: int
    total_disk_mb: int
    free_disk_mb: int
    active_previews: int
    collector_verified: bool


def permit_preview(host: HostTelemetry | None) -> dict:
    """Reject on missing data, insufficient reserves, or existing preview."""
    deny = {"admitted": False, "reason": "Measured host headroom is insufficient or unverified"}
    if host is None or host.collector_verified is not True:
        return deny
    values = (host.total_ram_mb, host.available_ram_mb, host.total_disk_mb,
              host.free_disk_mb, host.active_previews)
    if any(type(value) is not int or value < 0 for value in values):
        return deny
    if (host.available_ram_mb > host.total_ram_mb or
            host.free_disk_mb > host.total_disk_mb or
            host.active_previews >= MAX_CONCURRENT_PREVIEWS or
            host.total_ram_mb < HOST_RAM_RESERVE_MB + PREVIEW_RAM_MB or
            host.available_ram_mb < HOST_RAM_RESERVE_MB + PREVIEW_RAM_MB or
            host.free_disk_mb < HOST_DISK_RESERVE_MB + PREVIEW_DISK_MB):
        return deny
    return {"admitted": True, "reason": "Host headroom estimate permits one isolated Preview reservation"}
