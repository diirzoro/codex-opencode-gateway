"""Loopback-only Preview worker service for the Test environment.

Run as a separate dedicated service account with Docker permissions. This
service deliberately accepts *no* arbitrary image, mount, command or source
path from the HTTP caller. Registered jobs must first be provisioned via
the local trusted worker operator; unregistered Start requests fail closed.
"""
import hmac
import hashlib
import base64
import io
import re
import tarfile
import shutil
import uuid
import json
import os
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import RLock

from .preview_docker_provisioner import DockerProvisioner, PreviewProvisioningError
from .preview_worker_archive import extract_into_sandbox
from .preview_container_spec import ContainerSpec
from .preview_launch_profiles import PROFILES, LaunchProfile
from .preview_diagnostics import MESSAGES

MAX_BODY = 72 * 1024 * 1024
JOB_NAME = re.compile(r'^[A-Za-z0-9_-]{1,64}' + chr(36))
LOCK = RLock()
JOBS = {}
LOGGER = logging.getLogger('preview.worker')


def register_local_job(job_id: str, image: str, argv: tuple[str, ...]):
    """Privileged worker bootstrap only; never invoke with client-supplied values."""
    from .preview_docker_provisioner import JOB_ID
    if JOB_ID.fullmatch(job_id) is None or not argv:
        raise ValueError("Invalid job")
    mount = Path(f"/var/lib/preview-worker/jobs/{job_id}/src")
    if mount.is_symlink() or not mount.is_dir():
        raise ValueError("Snapshot not staged in worker-owned root")
    with LOCK:
        if job_id in JOBS:
            raise ValueError("Already registered")
        JOBS[job_id] = {"spec": ContainerSpec(image, tuple(argv), str(mount)),
                        "container_id": None, "state": "ready", "family": "node" if argv[0] == "node" else "python"}


class WorkerServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, addr, token: str, provisioner=None):
        if len(token) < 32:
            raise ValueError("Worker token must contain at least 32 characters")
        super().__init__(addr, WorkerHandler)
        self.token = token
        self.provisioner = provisioner or DockerProvisioner()


class WorkerHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def reply(self, status, data):
        body = json.dumps(data, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        # Handler errors otherwise abort the TCP connection and surface as
        # RemoteDisconnected in the Gateway, with no actionable error code.
        # Log only the operation and exception class; never request payloads.
        try:
            self._dispatch_post()
        except (BrokenPipeError, ConnectionResetError):
            LOGGER.warning("Preview worker client disconnected while replying")
        except Exception as exc:
            # Do not log exception values/tracebacks: daemon errors may contain
            # private paths, app arguments or registry credentials.
            reference = uuid.uuid4().hex[:12]
            LOGGER.error("Preview worker handler failed class=%s reference=%s",
                         type(exc).__name__, reference)
            try:
                self.reply(503, {"error": "worker_internal_error", "reference": reference})
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

    def _dispatch_post(self):
        authorized = self.headers.get("Authorization", "")
        expected = "Bearer " + self.server.token
        if not hmac.compare_digest(authorized, expected):
            self.reply(401, {"error": "unauthorized"})
            return
        operation = self.path.removeprefix("/v1/")
        if self.path != "/v1/" + operation or operation not in ("prepare", "start", "stop", "status", "logs", "fetch"):
            self.reply(404, {"error": "not_found"})
            return
        try:
            size = int(self.headers.get("Content-Length", "-1"))
            if not 0 <= size <= MAX_BODY:
                self.reply(413, {"error": "invalid_payload_size"})
                return
            request = json.loads(self.rfile.read(size))
            if not isinstance(request, dict) or not isinstance(request.get("job_id"), str) or not JOB_NAME.fullmatch(request["job_id"]):
                raise ValueError("Invalid payload")
            job_id = request["job_id"]
        except (ValueError, UnicodeError):
            self.reply(400, {"error": "invalid_payload"})
            return
        with LOCK:
            if operation == "prepare":
                if job_id in JOBS:
                    previous = JOBS[job_id]
                    if previous.get("container_id") and previous.get("state") == "running":
                        self.reply(409, {"error": "job_already_running"})
                        return
                    JOBS.pop(job_id, None)
                    shutil.rmtree(Path("/var/lib/preview-worker/jobs") / job_id, ignore_errors=True)
                framework = request.get("framework")
                profile = PROFILES.get(framework) if isinstance(framework, str) else None
                selected = request.get("entrypoint")
                if framework == "python" and selected in ("main.py", "app.py"):
                    profile = LaunchProfile("python", ("python", "-m", "uvicorn", selected[:-3] + ":app", "--host", "0.0.0.0", "--port", "8080"))
                elif framework == "node" and selected in ("server.js", "index.js"):
                    profile = LaunchProfile("node", ("node", selected))
                elif framework == "php" and selected == "index.php":
                    profile = LaunchProfile("php", ("php", "-S", "0.0.0.0:8080"))
                if profile is None or not isinstance(request.get("archive"), str):
                    self.reply(400, {"error": "unsupported_framework"})
                    return
                try:
                    encoded = request["archive"]
                    snapshot = base64.b64decode(encoded, validate=True)
                    if len(snapshot) > 50 * 1024 * 1024:
                        raise ValueError("oversized snapshot")
                    root = Path("/var/lib/preview-worker/jobs") / job_id
                    if root.exists():
                        # The Worker process may have restarted while a
                        # previous sandbox snapshot remained on disk.
                        if root.is_symlink() or not root.is_dir():
                            self.reply(409, {"error": "unsafe_job_directory"})
                            return
                        try:
                            old_id = self.server.provisioner._call((
                                "inspect", "--format", "{{.Id}}",
                                "preview-" + job_id))
                        except PreviewProvisioningError:
                            old_id = None
                        if old_id:
                            try:
                                self.server.provisioner.stop(old_id, job_id)
                            except PreviewProvisioningError:
                                self.reply(409, {"error": "stale_job_in_use"})
                                return
                        shutil.rmtree(root)
                    root.mkdir(mode=0o700)
                    try:
                        source = root / "src"
                        source.mkdir(mode=0o700)
                        extract_into_sandbox(tarfile.open(fileobj=io.BytesIO(snapshot), mode='r:'), source)
                        # Archive content is owned by the worker; the container
                        # runs under a different UID and requires read access.
                        if selected and not (source / selected).is_file():
                            raise ValueError("Missing selected entrypoint")
                        for path in source.rglob("*"):
                            if path.is_dir():
                                path.chmod(0o755)
                            elif path.is_file():
                                path.chmod(0o644)
                        source.chmod(0o755)
                        image = os.environ.get('PREVIEW_IMAGE_' + profile.family.upper(), '')
                        if not image:
                            raise ValueError('Worker runtime image is not configured')
                        JOBS[job_id] = {"spec": ContainerSpec(image, profile.argv, str(source)),
                                        "container_id": None, "state": "ready", "family": profile.family}
                    except Exception:
                        shutil.rmtree(root)
                        raise
                    self.reply(200, {"state": "ready", "job_id": job_id})
                except (ValueError, tarfile.TarError, OSError):
                    self.reply(400, {"error": "invalid_snapshot"})
                return
            job = JOBS.get(job_id)
            if job is None:
                self.reply(404, {"error": "unregistered_job"})
                return
            try:
                if operation == "start":
                    if job["state"] != "ready":
                        self.reply(409, {"error": "job_already_started"})
                        return
                    # Source archives deliberately exclude node_modules. A
                    # copied snapshot is not an installed/built application.
                    entrypoint = job['spec'].argv[0]
                    if entrypoint.startswith('./node_modules/') and not (Path(job['spec'].project_mount) / entrypoint).is_file():
                        self.reply(503, {'error': 'dependency_preparation_required',
                                         'message': MESSAGES['dependency_preparation_required']})
                        return
                    job["state"] = "launching"
                    try:
                        cid = self.server.provisioner.launch_smoke(job_id, job["spec"])
                    except Exception:
                        job["state"] = "failed"
                        raise
                    job["container_id"] = cid
                    job["state"] = "running"
                    # Docker accepted the container; that is not proof the HTTP
                    # app has started. Gate the iframe URL on a real response.
                    import time
                    ready = False
                    for _ in range(12):
                        try:
                            if self.server.provisioner.status(cid, job_id) != "running":
                                job['failure_code'] = 'application_exited_early'
                                break
                            response = self.server.provisioner.fetch(
                                cid, job_id, job["family"], "/")
                            ready = 200 <= response["status"] < 500
                            if ready:
                                break
                        except (PreviewProvisioningError, OSError, ValueError):
                            pass
                        time.sleep(0.5)
                    if not ready:
                        job["state"] = "failed"
                        try:
                            self.server.provisioner.stop(cid, job_id)
                        except PreviewProvisioningError:
                            pass
                        self.reply(503, {"error": job.get('failure_code', 'application_not_ready')})
                        return
                    result = {"state": "running", "job_id": job_id, "container_id": cid, "url": None}
                elif operation == "status":
                    cid = job["container_id"]
                    state = self.server.provisioner.status(cid, job_id) if cid else job["state"]
                    result = {"state": state, "job_id": job_id, "url": None,
                              "browser_lease": hashlib.sha256(cid.encode()).hexdigest() if cid and state == 'running' else None}
                elif operation == "fetch":
                    cid = job["container_id"]
                    if not cid or job["state"] != "running":
                        self.reply(409, {"error": "not_running"})
                        return
                    expected = request.get('browser_lease')
                    if expected is not None and (not isinstance(expected,str) or
                        not hmac.compare_digest(expected,hashlib.sha256(cid.encode()).hexdigest())):
                        self.reply(409, {'error':'stale_preview_lease'})
                        return
                    result = self.server.provisioner.fetch(
                        cid, job_id, job["family"], request.get("path", "/"))
                elif operation == "logs":
                    cid = job["container_id"]
                    result = {"logs": self.server.provisioner.logs(cid, job_id) if cid else ""}
                else:
                    cid = job["container_id"]
                    if cid:
                        self.server.provisioner.stop(cid, job_id)
                    job["state"] = "stopped"
                    job["container_id"] = None
                    result = {"state": "stopped", "job_id": job_id}
                self.reply(200, result)
            except (PreviewProvisioningError, OSError, ValueError) as exc:
                code = exc.code if isinstance(exc, PreviewProvisioningError) else 'worker_operation_failed'
                reference = uuid.uuid4().hex[:12]
                LOGGER.error('Preview worker operation=%s code=%s reference=%s', operation, code, reference)
                self.reply(503, {"error": code, "message": MESSAGES[code], "reference": reference})


def main():
    token = os.environ.get("PREVIEW_WORKER_TOKEN", "")
    # Do not bind all interfaces or auto-register arbitrary customer jobs.
    WorkerServer(("127.0.0.1", 8791), token).serve_forever()


if __name__ == "__main__":
    main()
