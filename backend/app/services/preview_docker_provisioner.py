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
from .preview_diagnostics import MESSAGES, docker_failure_code
from .preview_container_spec import UnsafeContainerSpec

CONTAINER_ID = re.compile(r"^[0-9a-f]{64}$")
JOB_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
Run = Callable[..., subprocess.CompletedProcess]


class PreviewProvisioningError(RuntimeError):
    def __init__(self, message, *, code='worker_operation_failed', operation=None):
        self.code = code if code in MESSAGES else 'worker_operation_failed'
        self.operation = operation
        super().__init__(message)


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
        except subprocess.TimeoutExpired as exc:
            raise PreviewProvisioningError(MESSAGES['docker_operation_timed_out'],
                code='docker_operation_timed_out', operation=args[0]) from exc
        except subprocess.CalledProcessError as exc:
            code = docker_failure_code(exc.stderr)
            raise PreviewProvisioningError(MESSAGES[code], code=code, operation=args[0]) from exc
        except OSError as exc:
            code = 'docker_binary_missing' if isinstance(exc, FileNotFoundError) else 'docker_operation_failed'
            raise PreviewProvisioningError(MESSAGES[code], code=code, operation=args[0]) from exc
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
        try:
            base = argv_for(spec)
        except UnsafeContainerSpec as exc:
            raise PreviewProvisioningError(MESSAGES['invalid_container_spec'],
                code='invalid_container_spec', operation='run') from exc
        # docker run --detach returns a container id and does not publish ports.
        args = ("run", "--detach", "--pull", "never", "--name", f"preview-{job_id}",
                "--label", "opencode.preview.managed=true",
                "--label", f"opencode.preview.job={job_id}", *base[2:])
        # The run --rm contract removes stopped containers. Worker must separately
        # persist job->container mapping and verify cleanup on process restart.
        container_id = self._call(args, timeout=60)
        if CONTAINER_ID.fullmatch(container_id) is None:
            raise PreviewProvisioningError("Docker returned an invalid container identifier")
        return container_id

    def fetch(self, container_id: str, job_id: str, family: str, path: str) -> dict:
        """Fetch a bounded HTTP resource from inside a network-none container.

        No container port is exposed to the host. Only GET resources can be
        served by this minimal Preview relay.
        """
        import base64
        from urllib.parse import urlsplit
        self._require_owned(container_id, job_id)
        if family not in ("node", "python", "php") or not isinstance(path, str):
            raise PreviewProvisioningError("Unsupported preview runtime")
        parsed = urlsplit(path)
        if (not path.startswith("/") or path.startswith("//") or
                parsed.scheme or parsed.netloc or len(path) > 2048 or
                any(ord(char) < 32 for char in path)):
            raise PreviewProvisioningError("Invalid preview path")
        script = (
            "const http=require('http');"
            "http.get({hostname:'127.0.0.1',port:Number(process.env.PORT||8080),path:process.argv[1],timeout:5000},"
            "r=>{const chunks=[];let n=0;r.on('data',c=>{n+=c.length;if(n>262144){r.destroy();process.exit(3);}chunks.push(c)});"
            "r.on('end',()=>{const b=Buffer.concat(chunks);"
            "process.stdout.write(JSON.stringify({status:r.statusCode,type:String(r.headers['content-type']||'application/octet-stream'),body:b.toString('base64')}))})}"
            ").on('error',()=>process.exit(4))"
        ) if family == "node" else (
            "import sys,urllib.request,urllib.error,base64,json;"
            "u='http://127.0.0.1:8080'+sys.argv[1];"
            "r=urllib.request.urlopen(u,timeout=5);"
            "b=r.read(262145);"
            "assert len(b)<=262144;"
            "print(json.dumps({'status':r.status,'type':r.headers.get('Content-Type','application/octet-stream'),'body':base64.b64encode(b).decode()}))"
        )
        if family == "php":
            raise PreviewProvisioningError("PHP relay not yet available")
        binary = "node" if family == "node" else "python"
        output = self._call(("exec", container_id, binary, "-e" if family == "node" else "-c", script, path), timeout=12)
        try:
            result = __import__("json").loads(output)
            if not isinstance(result, dict) or not 200 <= result.get("status", 0) <= 599:
                raise ValueError("Invalid response")
            return result
        except (ValueError, TypeError) as exc:
            raise PreviewProvisioningError("Application returned an invalid response") from exc

    def status(self, container_id: str, job_id: str) -> str:
        """Inspect a matching sandbox, without ever running an application."""
        self._require_owned(container_id, job_id)
        state = self._call(("inspect", "--format", "{{.State.Status}}", container_id))
        if state not in ("created", "running", "restarting", "exited", "dead", "paused"):
            raise PreviewProvisioningError("Unknown sandbox state")
        return state

    def _require_owned(self, container_id: str, job_id: str) -> None:
        if CONTAINER_ID.fullmatch(container_id) is None or JOB_ID.fullmatch(job_id) is None:
            raise PreviewProvisioningError("Invalid sandbox identity")
        labels = self._call(("inspect", "--format",
                             '{{index .Config.Labels "opencode.preview.job"}}|{{index .Config.Labels "opencode.preview.managed"}}',
                             container_id))
        if labels != f"{job_id}|true":
            raise PreviewProvisioningError("Refusing access to an unowned container")

    def stop(self, container_id: str, job_id: str) -> None:
        """Stop only a matching Preview container; never touch unrelated jobs."""
        self._require_owned(container_id, job_id)
        self._call(("stop", "--time", "2", container_id), timeout=15)

    def logs(self, container_id: str, job_id: str) -> str:
        """Bound logs and verify job identity before reading."""
        self._require_owned(container_id, job_id)
        return self._call(("logs", "--tail", "100", container_id), timeout=10)[-100000:]
