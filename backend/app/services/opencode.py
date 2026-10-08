"""Workspace-owned OpenCode processes, pooled HTTP, and live capability snapshots.

Process separation is not an OS sandbox. The supported deployment uses one Gateway
worker; an OS lock prevents a second worker from starting the same workspace.
"""
import atexit
import json
import logging
import os
import secrets
import shutil
import socket
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from urllib.parse import quote

import httpx
from fastapi import HTTPException
from ..config import settings
from .workspaces import root_for

logger = logging.getLogger(__name__)
SUPPORTED_RUNTIME_VERSIONS = {"1.18.31", "1.18.32"}
STARTUP_TIMEOUT = 30.0
HEALTH_INTERVAL = 5.0
SNAPSHOT_TTL = 1.0  # Coalesce simultaneous callers; auth mutations invalidate it.
CORE_PATHS = {"provider_data": "/provider", "auth_methods": "/provider/auth",
              "agents": "/agent", "config": "/config"}
CAPABILITY_PATHS = {"permissions": "/permission", "tools": "/experimental/tool/ids",
                    "identity": "/path", "vcs": "/vcs", "mcp": "/mcp", "lsp": "/lsp",
                    "formatters": "/formatter", "project": "/project/current",
                    "session_status": "/session/status", "questions": "/question"}
_runtimes = {}
_locks = {}
_registry_lock = threading.Lock()


def workspace_lock(workspace):
    with _registry_lock:
        return _locks.setdefault(str(workspace.id), threading.RLock())


@dataclass
class Runtime:
    process: subprocess.Popen
    log: object
    service: object
    owner_lock: object = None


class OpenCodeService:
    def __init__(self, url, password=None, directory=None):
        self.params = {"directory": str(directory)} if directory else {}
        self.client = httpx.Client(base_url=url, auth=("opencode", password) if password else None,
                                   timeout=15, trust_env=False)
        self.generation = secrets.token_hex(12)
        self.state_lock = threading.RLock()
        self.session_lock = threading.Lock()
        self.capability_lock = threading.Lock()
        self.last_health = 0.0
        self.health_state = None
        self.snapshot_cache = None
        self.snapshot_at = 0.0
        self.capability_cache = None
        self.capability_at = 0.0
        self.timings = {}
        self.call_counts = {}
        self.metrics_lock = threading.Lock()
        self.restore_passes = 0
        self.restore_puts = 0
        self.restore_errors = []
        self.oauth_pending = {}
        self.session_policies = {}

    def close(self):
        self.client.close()

    def request(self, method, path, data=None, timeout=15):
        started = time.monotonic()
        try:
            response = self.client.request(method, path, params=self.params, json=data, timeout=timeout)
            response.raise_for_status()
            return response.json() if response.content else None
        except httpx.TimeoutException:
            raise HTTPException(504, "OpenCode request timed out") from None
        except httpx.HTTPStatusError as exc:
            raise HTTPException(502, f"OpenCode returned HTTP {exc.response.status_code}") from None
        except (httpx.HTTPError, ValueError):
            raise HTTPException(503, "OpenCode runtime request failed") from None
        finally:
            # Endpoint names only: never log bodies, credentials, or host paths.
            metric = method + " " + path
            elapsed = round((time.monotonic() - started) * 1000, 2)
            with self.metrics_lock:
                self.timings[metric] = elapsed
                self.call_counts[metric] = self.call_counts.get(metric, 0) + 1
            logger.debug("OpenCode %s %.2fms generation=%s", metric, elapsed, self.generation)

    def health(self, timeout=3):
        result = self.request("GET", "/global/health", timeout=timeout)
        if not isinstance(result, dict) or result.get("healthy") is not True:
            raise HTTPException(503, "OpenCode health check failed")
        version = str(result.get("version", "unknown"))
        if version not in SUPPORTED_RUNTIME_VERSIONS:
            raise HTTPException(503, "Unsupported OpenCode version: " + version)
        self.last_health = time.monotonic()
        self.health_state = {"healthy": True, "version": version}
        return self.health_state

    def invalidate(self):
        with self.state_lock:
            self.snapshot_cache = None
            self.snapshot_at = 0.0

    def create_session(self, title):
        result = self.request("POST", "/session", {"title": title, "permission": [
            {"permission": "external_directory", "pattern": "*", "action": "deny"}]})
        if not isinstance(result, dict) or not str(result.get("id", "")).startswith("ses"):
            raise HTTPException(502, "OpenCode returned an invalid session")
        self.invalidate()
        return result["id"]

    def session_path(self, identifier, suffix=""):
        return "/session/" + quote(identifier, safe="") + suffix

    def apply_session_policy(self, identifier, rules):
        with self.state_lock:
            signature = json.dumps(rules, sort_keys=True)
            if self.session_policies.get(identifier) == signature:
                return
            result = self.request("PATCH", self.session_path(identifier), {"permission": rules})
            # OpenCode merges these rules onto existing session permissions.
            # The appended rules take precedence; check the actual reply.
            stored = result.get("permission", []) if isinstance(result, dict) else []
            if not rules or stored[-len(rules):] != rules:
                raise HTTPException(502, "OpenCode did not confirm current session tool policy")
            self.session_policies[identifier] = signature

    def _discover(self, paths):
        results, errors = {}, {}
        with ThreadPoolExecutor(max_workers=min(8, len(paths))) as pool:
            futures = {name: pool.submit(self.request, "GET", path) for name, path in paths.items()}
            for name, future in futures.items():
                try:
                    value = future.result()
                    valid = True
                    if name == "provider_data":
                        valid = isinstance(value, dict) and isinstance(value.get("all"), list)
                    elif name in {"config", "auth_methods"}:
                        valid = isinstance(value, dict)
                    elif name == "agents":
                        valid = isinstance(value, list) and all(isinstance(a, dict) and isinstance(a.get("name"), str) for a in value)
                    if not valid:
                        raise HTTPException(502, "OpenCode returned invalid " + name + " data")
                    results[name] = value
                except HTTPException as exc:
                    errors[name] = {"status": exc.status_code, "detail": exc.detail}
        return {name: results.get(name) for name in paths}, errors

    def diagnostics(self):
        with self.metrics_lock:
            return {"timings_ms": dict(self.timings), "api_calls": dict(self.call_counts),
                    "credential_restore_passes": self.restore_passes,
                    "credential_restore_puts": self.restore_puts,
                    "credential_restore_errors": list(self.restore_errors)}

    def snapshot(self):
        # Concurrent bootstrap calls share one discovery pass. Auth changes take
        # this same lock so a snapshot cannot straddle a credential mutation.
        with self.state_lock:
            if self.snapshot_cache is not None and time.monotonic() - self.snapshot_at < SNAPSHOT_TTL:
                return self.snapshot_cache
            started = time.monotonic()
            health = self.health_state if self.health_state and time.monotonic() - self.last_health < HEALTH_INTERVAL else self.health()
            result, errors = self._discover(CORE_PATHS)
            result.update(health=health, errors=errors, generation=self.generation)
            result["default_agent"] = (result.get("config") or {}).get("default_agent")
            result["config"] = {key: (result.get("config") or {}).get(key)
                                for key in ("default_agent", "model", "small_model", "permission")}
            with self.metrics_lock:
                self.timings["bootstrap_ms"] = round((time.monotonic() - started) * 1000, 2)
            result["diagnostics"] = self.diagnostics()
            self.snapshot_cache = result
            self.snapshot_at = time.monotonic()
            return result

    def capabilities(self):
        """Optional discovery is independent of the composer and auth locks."""
        with self.capability_lock:
            if self.capability_cache is not None and time.monotonic() - self.capability_at < SNAPSHOT_TTL:
                return self.capability_cache
            started = time.monotonic()
            result, errors = self._discover(CAPABILITY_PATHS)
            with self.metrics_lock:
                self.timings["capabilities_ms"] = round((time.monotonic() - started) * 1000, 2)
            result.update(errors=errors, generation=self.generation, diagnostics=self.diagnostics())
            self.capability_cache = result
            self.capability_at = time.monotonic()
            return result


def shared_health():
    service = OpenCodeService(settings.opencode_url)
    try:
        return service.health()
    finally:
        service.close()


def _initialize(service, workspace):
    """One restoration pass per generation, regardless of which route starts it."""
    from sqlalchemy import select
    from ..database import SessionLocal
    from ..models import ProviderCredential
    from . import credentials, providers
    started = time.monotonic()
    service.restore_passes += 1
    with SessionLocal() as db:
        rows = db.scalars(select(ProviderCredential).where(
            ProviderCredential.workspace_id == workspace.id,
            ProviderCredential.user_id == workspace.user_id))
        for row in rows:
            try:
                providers.restore_credential(service, row.provider_id, credentials.decrypt(row.ciphertext))
                service.restore_puts += 1
            except Exception:
                service.restore_errors.append({"provider_id": row.provider_id,
                                                "detail": "Stored credential could not be restored"})
    service.timings["credential_restore_ms"] = round((time.monotonic() - started) * 1000, 2)


def for_workspace(workspace, *, start=True):
    if settings.runtime_mode != "local":
        raise HTTPException(503, "Workspace runtime is disabled")
    key = str(workspace.id)
    with workspace_lock(workspace):
        runtime = _runtimes.get(key)
        if runtime and runtime.process.poll() is None:
            if time.monotonic() - runtime.service.last_health > HEALTH_INTERVAL:
                # Do not silently replace a living but unhealthy process.
                runtime.service.health()
            return runtime.service
        if runtime:
            stop_workspace(workspace)
        if not start:
            raise HTTPException(409, "No running OpenCode runtime")
        binary = shutil.which(settings.opencode_binary)
        if not binary:
            raise HTTPException(503, "OpenCode executable is not installed")
        repo = root_for(workspace)
        if not repo.is_dir():
            raise HTTPException(409, "Workspace files are missing")
        context = settings.runtime_root / str(workspace.user_id) / key
        context.mkdir(parents=True, exist_ok=True)
        env = {k: v for k, v in os.environ.items() if k.upper() in {
            "PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP", "PROCESSOR_ARCHITECTURE",
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR", "NODE_EXTRA_CA_CERTS"}}
        for name, folder in {"HOME": "home", "USERPROFILE": "home", "APPDATA": "config", "LOCALAPPDATA": "data",
                             "XDG_CONFIG_HOME": "config", "XDG_DATA_HOME": "data", "XDG_STATE_HOME": "state", "XDG_CACHE_HOME": "cache"}.items():
            path = context / folder
            path.mkdir(exist_ok=True)
            env[name] = str(path)
        from ..database import SessionLocal
        from .policy import load, permission_config
        with SessionLocal() as db:
            permission = permission_config(load(db))
        password = secrets.token_urlsafe(32)
        env.update(OPENCODE_SERVER_PASSWORD=password, OPENCODE_CONFIG_CONTENT=json.dumps({
            "autoupdate": False, "share": "disabled", "plugin": [], "permission": permission}))
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        log = open(context / "runtime.log", "a", encoding="utf-8")
        service = OpenCodeService(f"http://127.0.0.1:{port}", password, repo)
        owner_lock = None
        if os.name != "nt":
            import fcntl
            owner_lock = open(context / "process.lock", "a")
            try:
                fcntl.flock(owner_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                owner_lock.close()
                service.close()
                log.close()
                raise HTTPException(503, "Workspace runtime belongs to another Gateway worker; use one worker") from None
        started = time.monotonic()
        try:
            process = subprocess.Popen([binary, "serve", "--pure", "--hostname", "127.0.0.1", "--port", str(port)],
                                       cwd=repo, env=env, stdout=log, stderr=log)
        except OSError:
            service.close()
            log.close()
            if owner_lock: owner_lock.close()
            raise HTTPException(503, "Cannot spawn OpenCode process") from None
        service.timings["process_spawn_ms"] = round((time.monotonic() - started) * 1000, 2)
        _runtimes[key] = Runtime(process, log, service, owner_lock)
        deadline = started + STARTUP_TIMEOUT
        try:
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise HTTPException(503, "OpenCode exited before health-ready; inspect the private runtime log")
                try:
                    service.health(timeout=min(1, max(.01, deadline - time.monotonic())))
                    break
                except HTTPException as exc:
                    if str(exc.detail).startswith("Unsupported"):
                        raise
                    time.sleep(min(.1, max(0, deadline - time.monotonic())))
            else:
                raise HTTPException(504, "OpenCode did not become healthy within the total startup deadline")
            service.timings["health_ready_ms"] = round((time.monotonic() - started) * 1000, 2)
            _initialize(service, workspace)
            return service
        except Exception:
            stop_workspace(workspace)
            raise


def stop_workspace(workspace):
    with workspace_lock(workspace):
        runtime = _runtimes.pop(str(workspace.id), None)
        if runtime:
            if runtime.process.poll() is None:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(runtime.process.pid), "/T", "/F"], capture_output=True, timeout=15)
                else:
                    runtime.process.terminate()
                    try: runtime.process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        runtime.process.kill()
                        runtime.process.wait(timeout=5)
            runtime.service.close()
            runtime.log.close()
            if runtime.owner_lock: runtime.owner_lock.close()


def stop_all():
    for key in list(_runtimes):
        stop_workspace(type("WorkspaceRef", (), {"id": key})())


atexit.register(stop_all)
