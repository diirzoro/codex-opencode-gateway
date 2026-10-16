"""Fail-closed preview control plane. No customer code or engine is invoked.

Plans are advisory inputs to a future dedicated runner, never shell commands on
this host. Execution remains unavailable until an isolated runner is verified.
"""
from copy import deepcopy
from dataclasses import dataclass
from typing import Protocol
from fastapi import HTTPException
from . import preview, preview_scheduling, preview_package_manager, workspaces
from .preview_readiness import PreviewReadiness

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


@dataclass(frozen=True)
class LaunchProfile:
    """Runner-side argv, never executed by the Gateway or supplied by a client.

    Dependencies must already be prepared in the sandbox. No shell interpolation,
    automatic package download or user-selected host command is permitted.
    """
    family: str
    argv: tuple[str, ...]
    internal_port: int = 8080


PROFILES = {
    "nextjs": LaunchProfile("node", ("./node_modules/.bin/next", "dev", "--hostname", "0.0.0.0", "--port", "8080")),
    "vite": LaunchProfile("node", ("./node_modules/.bin/vite", "--host", "0.0.0.0", "--port", "8080", "--strictPort")),
    "angular": LaunchProfile("node", ("./node_modules/.bin/ng", "serve", "--host", "0.0.0.0", "--port", "8080")),
    "nuxt": LaunchProfile("node", ("./node_modules/.bin/nuxt", "dev", "--host", "0.0.0.0", "--port", "8080")),
    "django": LaunchProfile("python", ("python", "manage.py", "runserver", "0.0.0.0:8080", "--noreload")),
    "laravel": LaunchProfile("php", ("php", "artisan", "serve", "--host=0.0.0.0", "--port=8080")),
}


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
    return {**base, "launch": launch_options(workspace),
            "runner_available": client is not None,
            "state": result.get("state", base["state"]),
            "url": result.get("url"), "logs": [],
            "reason": None if result else "No prepared Preview job is available"}


def start(workspace):
    import base64
    import tempfile
    from .preview_snapshot import export
    from .preview_worker_client import PreviewWorkerUnavailable
    info = launch_options(workspace)
    framework = info["framework"]
    # Package-based frameworks require a preparation stage, and cannot be
    # declared running until dependencies and browser routing are available.
    if framework not in PROFILES:
        raise HTTPException(422, "No executable Preview profile for this workspace")
    try:
        client = _worker()
        with tempfile.SpooledTemporaryFile(max_size=2 * 1024 * 1024) as spool:
            export(workspace, spool)
            spool.seek(0)
            archive = base64.b64encode(spool.read()).decode("ascii")
        client.request("prepare", {"job_id": _job_id(workspace),
                                   "framework": framework, "archive": archive})
        response = client.request("start", {"job_id": _job_id(workspace)})
        # No iframe URL is provided until dedicated browser routing exists.
        return {**response, "url": None, "execution_enabled": True}
    except PreviewWorkerUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


def stop(workspace):
    from .preview_worker_client import PreviewWorkerUnavailable
    try:
        result = _worker().request("stop", {"job_id": _job_id(workspace)})
        return {**result, "url": None}
    except PreviewWorkerUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
