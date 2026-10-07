"""Safe, policy-annotated views of the selected OpenCode runtime."""
import time
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from ..models import WorkspaceSession
from . import policy, providers


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
    identity = providers.public_metadata(live["identity"])
    tools = live["tools"]
    _, _, allowed_tools = policy.provider_sets(policy_row)
    return {"status": "partial" if live["errors"] else "ready", "workspace_id": str(workspace.id),
            "generation": live["generation"], "health": live["health"], "version": live["health"]["version"],
            "providers": catalog, "connected": (live["provider_data"] or {}).get("connected") if live["provider_data"] is not None else None,
            "auth_methods": live["auth_methods"], "models": {p["id"]: [model["id"] for model in p["models"]] for p in catalog} if catalog is not None else None,
            "agents": providers.public_metadata(live["agents"]), "default_agent": live["default_agent"],
            "config": providers.public_metadata(live["config"]),
            "permissions": providers.public_metadata(live["permissions"]), "tools": tools,
            "tool_policy": {tool: not allowed_tools or tool in allowed_tools for tool in (tools or [])},
            "sessions": sync_sessions(db, workspace, live["sessions"]) if live["sessions"] is not None else None,
            "identity": {"workspace_id": str(workspace.id), "runtime": identity, "project": providers.public_metadata(live["project"])},
            "vcs": providers.public_metadata(live["vcs"]), "mcp": providers.public_metadata(live["mcp"]),
            "lsp": providers.public_metadata(live["lsp"]), "formatters": providers.public_metadata(live["formatters"]),
            "session_status": live["session_status"], "questions": providers.public_metadata(live["questions"]),
            "errors": live["errors"], "diagnostics": {**live["diagnostics"],
                "gateway_bootstrap_ms": round((time.monotonic() - started) * 1000, 2)}}
