"""Loopback-only Preview worker service for the Test environment.

Run as a separate dedicated service account with Docker permissions. This
service deliberately accepts *no* arbitrary image, mount, command or source
path from the HTTP caller. Registered jobs must first be provisioned via
the local trusted worker operator; unregistered Start requests fail closed.
"""
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import RLock

from .preview_docker_provisioner import DockerProvisioner, PreviewProvisioningError
from .preview_container_spec import ContainerSpec

MAX_BODY = 16384
LOCK = RLock()
JOBS = {}


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
                        "container_id": None, "state": "ready"}


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
        authorized = self.headers.get("Authorization", "")
        expected = "Bearer " + self.server.token
        if not hmac.compare_digest(authorized, expected):
            self.reply(401, {"error": "unauthorized"})
            return
        operation = self.path.removeprefix("/v1/")
        if self.path != "/v1/" + operation or operation not in ("start", "stop", "status", "logs"):
            self.reply(404, {"error": "not_found"})
            return
        try:
            size = int(self.headers.get("Content-Length", "-1"))
            if not 0 <= size <= MAX_BODY:
                self.reply(413, {"error": "invalid_payload_size"})
                return
            request = json.loads(self.rfile.read(size))
            if not isinstance(request, dict) or not isinstance(request.get("job_id"), str):
                raise ValueError("Invalid payload")
            job_id = request["job_id"]
        except (ValueError, UnicodeError):
            self.reply(400, {"error": "invalid_payload"})
            return
        with LOCK:
            job = JOBS.get(job_id)
            if job is None:
                self.reply(404, {"error": "unregistered_job"})
                return
            try:
                if operation == "start":
                    if job["state"] != "ready":
                        self.reply(409, {"error": "job_already_started"})
                        return
                    job["state"] = "launching"
                    try:
                        cid = self.server.provisioner.launch_smoke(job_id, job["spec"])
                    except Exception:
                        job["state"] = "failed"
                        raise
                    job["container_id"] = cid
                    job["state"] = "running"
                    result = {"state": "running", "job_id": job_id, "container_id": cid, "url": None}
                elif operation == "status":
                    cid = job["container_id"]
                    state = self.server.provisioner.status(cid, job_id) if cid else job["state"]
                    result = {"state": state, "job_id": job_id, "url": None}
                elif operation == "logs":
                    cid = job["container_id"]
                    result = {"logs": self.server.provisioner.logs(cid, job_id) if cid else ""}
                else:
                    cid = job["container_id"]
                    if cid:
                        self.server.provisioner.stop(cid, job_id)
                    job["state"] = "stopped"
                    result = {"state": "stopped", "job_id": job_id}
                self.reply(200, result)
            except (PreviewProvisioningError, OSError, ValueError):
                self.reply(503, {"error": "worker_operation_failed"})


def main():
    token = os.environ.get("PREVIEW_WORKER_TOKEN", "")
    # Do not bind all interfaces or auto-register arbitrary customer jobs.
    WorkerServer(("127.0.0.1", 8791), token).serve_forever()


if __name__ == "__main__":
    main()
