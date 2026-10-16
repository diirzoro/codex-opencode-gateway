"""Docker adapter for a *separate* privileged Preview provisioner.

Never import or expose this adapter from Gateway routes. Calling service must
authenticate its peer, reserve a durable lease, verify the snapshot owner and
isolate proxy access before allowing launch. Network-none containers are only
suitable for isolated smoke tests, NOT browser-hosted web previews.
"""
import re
import subprocess
from dataclasses import dataclass
from typing import Callable

from .preview_container_spec import ContainerSpec, argv_for

CONTAINER_ID = re.compile(r"^[0-9a-f]{64}$")
JOB_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
Run = Callable[..., subprocess.CompletedProcess]


class PreviewProvisioningError(RuntimeError):
    pass


@dataclass(frozen=True)
class DockerProvisioner:
    """Explicit worker-side execution with fixed limits and no shell."""

    run: Run = subprocess.run
    docker_binary: str = "/usr/bin/docker"

    def _call(self, args: tuple[str, ...], *, timeout: int = 20) -> str:
        try:
            completed = self.run(
                (self.docker_binary, *args), capture_output=True, text=True,
                check=True, timeout=timeout,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError,
                OSError) as exc:
            raise PreviewProvisioningError("Worker Docker operation failed") from exc
        return completed.stdout.strip()

    def launch_smoke(self, job_id: str, spec: ContainerSpec) -> str:
        """Run a pinned, network-disconnected smoke container.

        Not available to the Gateway; provisioner must verify authorization,
        snapshot ownership, image allowlist, host headroom and exclusive lease.
        """
        if JOB_ID.fullmatch(job_id) is None:
            raise PreviewProvisioningError("Invalid worker job id")
        expected = f"/var/lib/preview-worker/jobs/{job_id}/src"
        if spec.project_mount != expected:
            raise PreviewProvisioningError("Worker job does not own requested snapshot")
        base = argv_for(spec)
        # docker run --detach returns a container id and does not publish ports.
        args = ("run", "--detach", "--name", f"preview-{job_id}",
                "--label", "opencode.preview.managed=true",
                "--label", f"opencode.preview.job={job_id}", *base[2:])
        # The run --rm contract removes stopped containers. Worker must separately
        # persist job->container mapping and verify cleanup on process restart.
        container_id = self._call(args, timeout=60)
        if CONTAINER_ID.fullmatch(container_id) is None:
            raise PreviewProvisioningError("Docker returned an invalid container identifier")
        return container_id

    def stop(self, container_id: str, job_id: str) -> None:
        """Stop only a matching Preview container; never touch unrelated jobs."""
        if CONTAINER_ID.fullmatch(container_id) is None or JOB_ID.fullmatch(job_id) is None:
            raise PreviewProvisioningError("Invalid sandbox identity")
        label = self._call(("inspect", "--format",
                            "{{index .Config.Labels \"opencode.preview.job\"}}", container_id))
        if label != job_id:
            raise PreviewProvisioningError("Refusing to stop an unowned container")
        self._call(("stop", "--time", "2", container_id), timeout=15)

    def logs(self, container_id: str, job_id: str) -> str:
        """Bound logs and verify job identity before reading."""
        if CONTAINER_ID.fullmatch(container_id) is None or JOB_ID.fullmatch(job_id) is None:
            raise PreviewProvisioningError("Invalid sandbox identity")
        label = self._call(("inspect", "--format",
                            "{{index .Config.Labels \"opencode.preview.job\"}}", container_id))
        if label != job_id:
            raise PreviewProvisioningError("Refusing logs for an unowned container")
        return self._call(("logs", "--tail", "100", container_id), timeout=10)[-100000:]
