"""Safe, policy-annotated views of the selected OpenCode runtime."""
import time
import uuid
import hashlib
from datetime import datetime, timezone
from sqlalchemy import select
from ..models import WorkspaceSession
from . import policy, providers


def policy_revision(row):
    return hashlib.sha256(((row.allowed_providers or "[]") + "\n" + (row.allowed_models or "[]")).encode()).hexdigest()[:16]


def sync_sessions(db, workspace, live):
    """Gateway stores ownership/execution mappings; titles/existence come from OpenCode."""
    rows = list(db.scalars(select(WorkspaceSession).where(
        WorkspaceSession.workspace_id == workspace.id, WorkspaceSession.user_id == workspace.user_id)))
    by_runtime = {row.opencode_session_id: row for row in rows}
    result = []
    for entry in live:
        identifier = entry.get("id", "")
        if not identifier.startswith("ses") or entry.get("parentID") or entry.get("time", {}).get("archived"):
            continue
        row = by_runtime.get(identifier)
        if row is None:
            row = WorkspaceSession(id=uuid.uuid4(), workspace_id=workspace.id, user_id=workspace.user_id,
                                   opencode_session_id=identifier, title=entry.get("title", "")[:120], status="idle")
            milliseconds = entry.get("time", {}).get("created")
            if milliseconds is not None:
                row.created_at = datetime.fromtimestamp(milliseconds / 1000, timezone.utc)
            db.add(row)
        row.title = entry.get("title", row.title)[:120]
        result.append({**providers.public_metadata(entry), "id": str(row.id), "runtime_id": identifier,
                       "workspace_id": str(workspace.id), "title": row.title, "status": row.status,
                       "created_at": row.created_at})
    db.commit()
    return result


def public_snapshot(service, workspace, db):
    started = time.monotonic()
    live = service.snapshot()
    policy_row = policy.load(db)
    catalog = None
    if live["provider_data"] is not None:
        catalog = providers.catalog(live["provider_data"], live["auth_methods"] or {}, policy_row)
    return {"status": "partial" if live["errors"] else "ready", "workspace_id": str(workspace.id),
            "generation": live["generation"], "revision": live["revision"], "policy_revision": policy_revision(policy_row),
            "health": live["health"], "version": live["health"]["version"],
            "providers": catalog, "connected": (live["provider_data"] or {}).get("connected") if live["provider_data"] is not None else None,
            "auth_methods": live["auth_methods"], "models": {p["id"]: [model["id"] for model in p["models"]] for p in catalog} if catalog is not None else None,
            "agents": providers.public_metadata(live["agents"]), "default_agent": live["default_agent"],
            "default_agent_resolution": "configured" if live["default_agent"] else "runtime",
            "config": providers.public_metadata(live["config"]),
            "errors": live["errors"], "diagnostics": {**live["diagnostics"],
                "gateway_bootstrap_ms": round((time.monotonic() - started) * 1000, 2)}}


def public_agents(service, workspace):
    live = service.agent_snapshot()
    return {"workspace_id": str(workspace.id), "generation": live["generation"], "revision": live["revision"],
            "health": live["health"], "agents": providers.public_metadata(live["agents"]),
            "default_agent": live["default_agent"], "config": providers.public_metadata(live["config"]),
            "errors": live["errors"]}


def public_capabilities(service, workspace, db):
    live = service.capabilities()
    _, _, allowed_tools = policy.provider_sets(policy.load(db))
    result = {name: providers.public_metadata(live[name]) for name in live if name not in {"diagnostics", "generation", "identity", "project"}}
    result.update(workspace_id=str(workspace.id), generation=live["generation"],
                  status="partial" if live["errors"] else "ready",
                  identity={"workspace_id": str(workspace.id), "runtime": providers.public_metadata(live["identity"]),
                            "project": providers.public_metadata(live["project"])},
                  tool_policy={tool: not allowed_tools or tool in allowed_tools for tool in (live["tools"] or [])},
                  diagnostics=live["diagnostics"])
    return result
