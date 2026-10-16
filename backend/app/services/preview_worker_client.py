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
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                if response.status != 200:
                    raise PreviewWorkerUnavailable("Preview worker rejected request")
                data = response.read(65537)
                if len(data) > 65536:
                    raise PreviewWorkerUnavailable("Preview worker response too large")
                result = json.loads(data)
                if not isinstance(result, dict):
                    raise ValueError("Invalid worker response")
                return result
        except (OSError, ValueError, urllib.error.HTTPError) as exc:
            raise PreviewWorkerUnavailable("Preview worker is not available") from exc


def configured_client() -> PreviewWorkerClient | None:
    """Only enabled by explicit Test environment settings; default stays off."""
    if os.environ.get("PREVIEW_WORKER_ENABLED") != "test":
        return None
    url = os.environ.get("PREVIEW_WORKER_URL", "")
    token = os.environ.get("PREVIEW_WORKER_TOKEN", "")
    return PreviewWorkerClient(url, token)
