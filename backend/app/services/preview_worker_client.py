"""Minimal Test-only preview controller protocol.

Gateway never talks to Docker. A separately deployed worker may expose a
loopback-only endpoint guarded by a per-installation bearer secret. This
client intentionally cannot enable preview unless an operator configures it.
"""
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

class PreviewWorkerUnavailable(RuntimeError):
    pass

@dataclass(frozen=True)
class PreviewWorkerClient:
    base_url: str
    token: str
    timeout: float = 8.0

    def __post_init__(self):
        if not self.base_url.startswith("http://127.0.0.1:") or not self.token or len(self.token) < 32:
            raise PreviewWorkerUnavailable("Test worker endpoint or credentials invalid")

    def request(self, operation: str, payload: dict) -> dict:
        if operation not in ("prepare", "start", "stop", "status", "logs", "fetch"):
            raise ValueError("Unknown worker operation")
        body = json.dumps(payload, separators=(",", ":")).encode()
        if len(body) > 72 * 1024 * 1024:
            raise ValueError("Worker request exceeds limit")
        request = urllib.request.Request(
            self.base_url.rstrip("/") + "/v1/" + operation, data=body,
            headers={"Authorization": "Bearer " + self.token,
                     "Content-Type": "application/json"}, method="POST")
        # A snapshot transfer and an application readiness check take longer
        # than a status ping. The previous 8s global timeout hid both failures.
        timeout = {"prepare": 60.0, "start": 75.0, "fetch": 20.0}.get(operation, self.timeout)
        limit = 524288 if operation == "fetch" else 65536
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    raise PreviewWorkerUnavailable("Preview worker returned a non-success response")
                raw = response.read(limit + 1)
                if len(raw) > limit:
                    raise PreviewWorkerUnavailable("Preview response exceeds safe size limit")
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise ValueError("Invalid worker response")
                return result
        except urllib.error.HTTPError as exc:
            # Expose only finite error identifiers emitted by our own Worker.
            # Never return raw response bodies or authorization headers.
            allowed = {
                "unauthorized", "not_found", "invalid_payload",
                "invalid_payload_size", "job_exists", "job_already_running",
                "job_already_started", "unregistered_job", "not_running",
                "unsupported_framework", "invalid_snapshot",
                "worker_operation_failed", "application_not_ready",
                "unsafe_job_directory", "stale_job_in_use",
            }
            try:
                error = json.loads(exc.read(1024)).get("error")
            except (ValueError, OSError, AttributeError):
                error = None
            if error not in allowed:
                error = "HTTP " + str(exc.code)
            raise PreviewWorkerUnavailable(
                f"Preview worker {operation} failed: {error}"
            ) from exc
        except (OSError, ValueError) as exc:
            raise PreviewWorkerUnavailable(
                f"Preview worker {operation} connection failed ({type(exc).__name__})"
            ) from exc


def configured_client() -> PreviewWorkerClient | None:
    """Only enabled by explicit Test environment settings; default stays off."""
    if os.environ.get("PREVIEW_WORKER_ENABLED") != "test":
        return None
    url = os.environ.get("PREVIEW_WORKER_URL", "")
    token = os.environ.get("PREVIEW_WORKER_TOKEN", "")
    return PreviewWorkerClient(url, token)
