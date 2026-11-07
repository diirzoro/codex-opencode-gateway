"""Read-only Linux host telemetry for future private Preview controller.

Not an attestation: measurements are trusted ONLY if collected inside the
authenticated dedicated worker-control service, never from an HTTP caller.
Does not start processes or touch production state.
"""
from pathlib import Path
from shutil import disk_usage

from .preview_host_gate import HostTelemetry


def read_host_telemetry(*, storage: Path, active_previews: int,
                        trusted_collector: bool = False) -> HostTelemetry:
    """Read MemAvailable and free bytes, reject absent/malformed information."""
    values = {}
    for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
        if line.startswith(("MemTotal:", "MemAvailable:")):
            key, amount, units = line.split()
            if units != "kB":
                raise ValueError("Unexpected host memory units")
            values[key.rstrip(":")] = int(amount) // 1024
    if set(values) != {"MemTotal", "MemAvailable"}:
        raise ValueError("Host memory readings are incomplete")
    disk = disk_usage(storage)
    return HostTelemetry(
        total_ram_mb=values["MemTotal"],
        available_ram_mb=values["MemAvailable"],
        total_disk_mb=disk.total // (1024 * 1024),
        free_disk_mb=disk.free // (1024 * 1024),
        active_previews=active_previews,
        collector_verified=trusted_collector,
    )
