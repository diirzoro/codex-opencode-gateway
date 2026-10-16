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
    if not isinstance(spec.image, str) or re.fullmatch(
        r"[a-z0-9][a-z0-9._/-]*@sha256:[0-9a-f]{64}", spec.image
    ) is None:
        raise UnsafeContainerSpec("Verified SHA256 image digest required")
    if (not spec.argv or spec.internal_port != 8080 or
            re.fullmatch(r"/var/lib/preview-worker/jobs/[a-zA-Z0-9_-]{1,64}/src", spec.project_mount) is None or
            any(not isinstance(part, str) or not part or "\x00" in part or "\n" in part for part in spec.argv)):
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
