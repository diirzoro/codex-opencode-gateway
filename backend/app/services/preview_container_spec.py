"""Fixed sandbox invocation specification for a dedicated Preview provisioner.

Never execute this from the Gateway API process. Provisioner must verify
trusted image digests, host mount ownership, daemon access and network policy.
"""
from dataclasses import dataclass
import re

@dataclass(frozen=True)
class ContainerSpec:
    image: str
    argv: tuple[str, ...]
    project_mount: str
    internal_port: int = 8080


class UnsafeContainerSpec(ValueError):
    pass


def argv_for(spec: ContainerSpec) -> tuple[str, ...]:
    """Fixed Docker arguments; no shell, user-supplied flags, ports or mounts."""
    if not spec.image.startswith("sha256:") or len(spec.image) != 71 or any(
        c not in "0123456789abcdef" for c in spec.image[7:]
    ):
        raise UnsafeContainerSpec("Verified SHA256 image digest required")
    if (not spec.argv or spec.internal_port != 8080 or
            not spec.project_mount.startswith("/var/lib/preview-worker/jobs/") or
            ".." in spec.project_mount.split("/") or
            not spec.project_mount.endswith("/src") or
            any(not part for part in spec.argv) or
            any("\x00" in part for part in spec.argv)):
        raise UnsafeContainerSpec("Invalid fixed worker launch contract")
    # This is a *configuration contract*, not a complete sandbox security proof.
    # No -p, --privileged, host namespaces, Docker socket or secret volumes.
    return (
        "docker", "run", "--rm", "--network", "none",
        "--read-only", "--user", "10001:10001",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--memory", "768m", "--memory-swap", "768m",
        "--cpus", "1", "--pids-limit", "128",
        "--tmpfs", "/tmp:rw,nosuid,noexec,size=64m",
        "--mount", f"type=bind,src={spec.project_mount},dst=/workspace,readonly",
        "--workdir", "/workspace", "--env", "PORT=8080",
        "--env", "HOST=0.0.0.0", spec.image, *spec.argv,
    )
