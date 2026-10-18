"""Fail-closed preview control plane. No customer code or engine is invoked.

Plans are advisory inputs to a future dedicated runner, never shell commands on
this host. Execution remains unavailable until an isolated runner is verified.
"""
from copy import deepcopy
from typing import Protocol
from fastapi import HTTPException
from . import preview, preview_scheduling, preview_package_manager, workspaces
from .preview_readiness import PreviewReadiness
from .preview_launch_profiles import LaunchProfile, PROFILES

# Fixed security contract: clients cannot loosen these limits via API input.
LIMITS={"cpu_cores":1,"memory_mb":768,"disk_mb":1024,"processes":128,
        "execution_seconds":900,"log_bytes":100000,"uid":10001,
        "read_only_root":True,"drop_capabilities":["ALL"],"no_new_privileges":True,
        "network":"none","public_ports":[],"docker_socket":False,
        "host_secrets":False,"source_mount":"owned_snapshot_read_only",
        "writable_storage":"size_limited_ephemeral"}


def plan(workspace):
    detected=preview.detect(workspace)
    framework=detected['framework']
    web=framework in {'html','nextjs','vite','angular','nuxt','svelte','react','vue','node','django','laravel','python','php'}
    family='node' if framework in {'nextjs','vite','angular','nuxt','svelte','react','vue','node'} else 'python' if framework in {'django','python'} else 'php' if framework in {'laravel','php'} else None
    package_manager = preview_package_manager.detect(workspaces.root_for(workspace)) if family == "node" else None
    return {**preview_scheduling.classify(detected), "package_preparation":package_manager, "mode":"static" if framework=='html' else "isolated_runner_required",
            "runtime_family":family,"web_candidate":web,
            "state":"static_available" if framework=='html' else "blocked",
            "execution_enabled":False,"limits":deepcopy(LIMITS),
            "routing":{"authentication_required":True,"tenant_and_project_bound":True,
                       "separate_origin_required":True,"host_port_exposure":False},
            "blockers":[] if framework=='html' else ["A dedicated isolated runner and authenticated separate-origin routing are not configured or verified.",
                "Build dependencies require a separately controlled preparation stage; runtime egress must remain restricted."],
            "message":"No project code was executed. Non-web projects need a supported output/log runner." if not web else "No application server was started."}


class IsolatedRunner(Protocol):
    """Dedicated service contract; implementations require security acceptance.

    Every operation must bind owner/project/workspace together, persist a lease,
    enforce LIMITS outside customer processes and recheck ownership on routing.
    stop must revoke routing before idempotent cleanup; expired/crashed leases
    must be reaped by the runner even when the Gateway is unavailable.
    Gateway must never accept customer-selected images, mounts, env or ports.
    """
    def start(self, *, owner_id: str, project_id: str, workspace_id: str,
              snapshot_id: str, profile: LaunchProfile) -> dict: ...
    def status(self, *, owner_id: str, project_id: str, workspace_id: str) -> dict: ...
    def stop(self, *, owner_id: str, project_id: str, workspace_id: str) -> dict: ...
    def logs(self, *, owner_id: str, project_id: str, workspace_id: str, limit: int) -> dict: ...


def launch_options(workspace):
    """Expose only verified entry shapes, never guess an ASGI module or npm script."""
    from . import workspaces
    detected = preview.detect(workspace)
    framework = detected['framework']
    profile = PROFILES.get(framework)
    if framework in {'react', 'vue', 'svelte'}:
        # These libraries alone do not establish a server/start command.
        profile = None
    if framework == 'python':
        # FastAPI apps vary in module and app name; explicit supported entry only.
        for name, module in [('main.py', 'main:app'), ('app.py', 'app:app')]:
            path = workspaces.safe_path(workspace, name)
            if path.is_file():
                profile = LaunchProfile('python', ('python', '-m', 'uvicorn', module, '--host', '0.0.0.0', '--port', '8080'))
                break
    if framework == 'node':
        for name in ('server.js', 'index.js'):
            if workspaces.safe_path(workspace, name).is_file():
                profile = LaunchProfile('node', ('node', name))
                break
    if framework == 'php' and workspaces.safe_path(workspace, 'index.php').is_file():
        profile = LaunchProfile('php', ('php', '-S', '0.0.0.0:8080'))
    return {'framework': framework, 'profile_available': profile is not None,
            'runtime_family': profile.family if profile else None,
            'argv': list(profile.argv) if profile else [],
            'internal_port': profile.internal_port if profile else None,
            'environment': {'PORT': '8080', 'HOST': '0.0.0.0'} if profile else {},
            'preparation_required': True, 'execution_enabled': False}


def _worker():
    from .preview_worker_client import configured_client, PreviewWorkerUnavailable
    try:
        client = configured_client()
    except PreviewWorkerUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    if client is None:
        raise HTTPException(503, "Test Preview worker is not configured")
    return client


def _job_id(workspace):
    return str(workspace.id)


def status(workspace):
    base = plan(workspace)
    client = None
    from .preview_worker_client import configured_client, PreviewWorkerUnavailable
    try:
        client = configured_client()
        result = client.request("status", {"job_id": _job_id(workspace)}) if client else {}
    except PreviewWorkerUnavailable:
        result = {}
    import os
    return {**base, "launch": launch_options(workspace),
            "browser_access_required": bool(os.environ.get('PREVIEW_PUBLIC_ORIGIN')),
            "runner_available": client is not None,
            "state": result.get("state", base["state"]),
            "url": result.get("url"), "logs": [],
            "reason": None if result else "No prepared Preview job is available"}


def start(workspace, *, fresh=False):
    import base64
    import tempfile
    from .preview_snapshot import export
    from .preview_worker_client import PreviewWorkerUnavailable
    info = launch_options(workspace)
    framework = info["framework"]
    # Package-based frameworks require a preparation stage, and cannot be
    # declared running until dependencies and browser routing are available.
    if not info["profile_available"]:
        raise HTTPException(422, "No executable Preview profile for this workspace")
    try:
        client = _worker()
        # Opening Preview twice must not re-upload a snapshot over a live job.
        # Return the existing tenant-owned workspace relay instead.
        try:
            existing = client.request("status", {"job_id": _job_id(workspace)})
            if existing.get("state") == "running":
                if not fresh:
                    return {"state": "running",
                            "url": "/api/workspaces/" + _job_id(workspace) + "/preview/live/",
                            "execution_enabled": True, "reused": True}
                stopped=client.request("stop", {"job_id": _job_id(workspace)})
                if stopped.get('state')!='stopped':
                    raise PreviewWorkerUnavailable('Preview stop did not confirm shutdown; fresh preview was not started')
        except PreviewWorkerUnavailable as exc:
            if "unregistered_job" not in str(exc):
                raise
        with tempfile.SpooledTemporaryFile(max_size=2 * 1024 * 1024) as spool:
            export(workspace, spool)
            spool.seek(0)
            archive = base64.b64encode(spool.read()).decode("ascii")
        client.request("prepare", {"job_id": _job_id(workspace),
                                   "framework": framework, "entrypoint": info["argv"][-1] if framework == "node" else ("main.py" if "main:app" in info["argv"] else "app.py" if "app:app" in info["argv"] else "index.php" if framework == "php" else None), "archive": archive})
        response = client.request("start", {"job_id": _job_id(workspace)})
        # No iframe URL is provided until dedicated browser routing exists.
        if response.get("state") != "running":
            raise HTTPException(503, "Preview container did not start")
        return {**response, "url": "/api/workspaces/" + _job_id(workspace) + "/preview/live/", "execution_enabled": True}
    except PreviewWorkerUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


def stop(workspace):
    from .preview_worker_client import PreviewWorkerUnavailable
    try:
        result = _worker().request("stop", {"job_id": _job_id(workspace)})
        return {**result, "url": None}
    except PreviewWorkerUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


def fetch_asset(workspace, path: str, *, relay_prefix: str | None = None, browser_lease: str | None = None):
    """Proxy a bounded GET asset from the tenant-owned running preview."""
    import base64
    from fastapi import Response
    from .preview_worker_client import PreviewWorkerUnavailable
    if len(path) > 2048 or not path.startswith("/"):
        raise HTTPException(400, "Invalid preview asset path")
    try:
        payload = {"job_id": _job_id(workspace), "path": path}
        if browser_lease is not None:
            payload['browser_lease'] = browser_lease
        result = _worker().request("fetch", payload)
        body = base64.b64decode(result["body"], validate=True)
        if len(body) > 262144:
            raise ValueError("Oversized preview response")
        status_code = int(result["status"])
        if not 200 <= status_code <= 599:
            raise ValueError("Invalid upstream response")
        media_type = str(result.get("type") or "application/octet-stream").split(";")[0]
        if media_type not in ("text/html", "text/css", "application/javascript",
                              "text/javascript", "application/json", "image/png",
                              "image/jpeg", "image/svg+xml", "text/plain"):
            media_type = "application/octet-stream"
        if media_type == "text/html" and status_code < 400:
            from html import escape
            import re
            prefix = relay_prefix or "/api/workspaces/" + _job_id(workspace) + "/preview/live/"
            try:
                page = body.decode("utf-8")
            except UnicodeError as exc:
                raise HTTPException(502, "Invalid HTML encoding") from exc
            # A nested document must retain its own URL as the resolution base;
            # always using the project root breaks relative links/assets in it.
            base = '<base href="' + escape(prefix + path.lstrip("/"), quote=True) + '">'
            # Rewrite customer root-relative references before adding our base.
            # Otherwise the injected href is prefixed again and relative assets
            # and nested-page links resolve to a duplicated Gateway API path.
            page = re.sub(r"""((?:src|href)\s*=\s*["'])/(?!/)""", lambda m: m.group(1) + prefix, page)
            head = re.search(r"<head\b[^>]*>", page, re.IGNORECASE)
            page = page[:head.end()] + base + page[head.end():] if head else base + page
            body = page.encode("utf-8")
        return Response(content=body, status_code=status_code, media_type=media_type,
                        headers={"Cache-Control": "no-store",
                                 "Content-Security-Policy": "sandbox allow-scripts"})
    except (PreviewWorkerUnavailable, KeyError, ValueError, TypeError) as exc:
        raise HTTPException(503, "Preview application is not responding yet") from exc
