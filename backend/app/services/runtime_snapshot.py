"""Safe, policy-annotated views of the selected OpenCode runtime."""
import time
import uuid
import hashlib
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from ..models import WorkspaceSession
from . import policy, providers, session_lifecycle


def policy_revision(row):
    return hashlib.sha256(((row.allowed_providers or "[]") + "\n" + (row.allowed_models or "[]")).encode()).hexdigest()[:16]


def workspace_policy_revision(db, workspace, row):
    return policy_revision(row) + ":" + str(providers.connection_revision(db, workspace))


def sync_sessions(db, workspace, live):
    """Gateway stores ownership/execution mappings; titles/existence come from OpenCode."""
    session_lifecycle.lock_workspace(db, workspace)
    rows = list(db.scalars(select(WorkspaceSession).where(
        WorkspaceSession.workspace_id == workspace.id, WorkspaceSession.user_id == workspace.user_id)))
    by_runtime = {row.opencode_session_id: row for row in rows}
    for entry in live:
        identifier = entry.get("id", "")
        if not identifier.startswith("ses") or entry.get("parentID"):
            continue
        row = by_runtime.get(identifier)
        if row is None:
            row = WorkspaceSession(id=uuid.uuid4(), workspace_id=workspace.id, user_id=workspace.user_id,
                                   opencode_session_id=identifier, title=entry.get("title", "")[:120], status="idle")
            milliseconds = entry.get("time", {}).get("created")
            if milliseconds is not None:
                row.created_at = datetime.fromtimestamp(milliseconds / 1000, timezone.utc)
            db.add(row); rows.append(row); by_runtime[identifier] = row
            if entry.get("time", {}).get("archived"):
                session_lifecycle.set_state(db, row, "archived")
        row.title = entry.get("title", row.title)[:120]
    db.flush()
    values = session_lifecycle.states(db, rows)
    result = [{**session_lifecycle.payload(row, values[row.id]), "runtime_id": row.opencode_session_id}
              for row in rows if values[row.id] != "deleted"]
    db.commit()
    return result


def public_snapshot(service, workspace, db):
    started = time.monotonic()
    live = service.snapshot()
    live = {**live, "provider_data": providers.client_catalog(db, workspace, live["provider_data"])}
    policy_row = policy.load(db)
    catalog = None
    if live["provider_data"] is not None:
        catalog = providers.catalog_index(live["provider_data"], policy_row)
    return {"status": "partial" if live["errors"] else "ready", "workspace_id": str(workspace.id),
            "generation": live["generation"], "revision": live["revision"], "policy_revision": workspace_policy_revision(db, workspace, policy_row),
            "health": live["health"], "version": live["health"]["version"],
            "providers": catalog, "connected": (live["provider_data"] or {}).get("connected") if live["provider_data"] is not None else None,
            "catalog_size": len((live["provider_data"] or {}).get("all", [])),
            "auth_methods": ({p["id"]: live["auth_methods"].get(p["id"], []) for p in (catalog or [])}
                             if live["auth_methods"] is not None else None),
            "agents": providers.public_metadata(live["agents"]), "default_agent": live["default_agent"],
            "default_agent_resolution": "configured" if live["default_agent"] else "runtime",
            "config": providers.public_metadata(live["config"]),
            "errors": live["errors"], "diagnostics": {**live["diagnostics"],
                "gateway_bootstrap_ms": round((time.monotonic() - started) * 1000, 2)}}


def public_provider_lookup(service, workspace, db, *, name=None, query=None):
    live = service.snapshot()
    live = {**live, "provider_data": providers.client_catalog(db, workspace, live["provider_data"])}
    if live["provider_data"] is None:
        error = live["errors"]["provider_data"]
        raise HTTPException(error["status"], error["detail"])
    policy_row = policy.load(db)
    if name is not None:
        entry = providers.resolve_provider(live["provider_data"], name)
        rows = [providers.provider_index(entry, live["provider_data"], policy_row)]
    else:
        rows = providers.search_index(live["provider_data"], query, policy_row)
    for row in rows:
        if name is not None:
            row["auth_methods"] = providers.connection_methods(service, row["id"])
        else:
            row["auth_methods"] = live["auth_methods"].get(row["id"], []) if live["auth_methods"] is not None else None
    return {"workspace_id": str(workspace.id), "generation": live["generation"], "revision": live["revision"],
            "policy_revision": workspace_policy_revision(db, workspace, policy_row),
            "providers": rows}


def public_models(service, workspace, provider_id, db):
    live = service.snapshot()
    live = {**live, "provider_data": providers.client_catalog(db, workspace, live["provider_data"])}
    if live["provider_data"] is None:
        error = live["errors"]["provider_data"]
        raise HTTPException(error["status"], error["detail"])
    policy_row = policy.load(db)
    return {"workspace_id": str(workspace.id), "generation": live["generation"],
            "revision": live["revision"], "policy_revision": workspace_policy_revision(db, workspace, policy_row),
            **providers.model_details(live["provider_data"], provider_id, policy_row)}


def public_agents(service, workspace):
    live = service.agent_snapshot()
    return {"workspace_id": str(workspace.id), "generation": live["generation"], "revision": live["revision"],
            "health": live["health"], "agents": providers.public_metadata(live["agents"]),
            "default_agent": live["default_agent"], "config": providers.public_metadata(live["config"]),
            "errors": live["errors"]}


def public_capabilities(service, workspace, db, view=None):
    if view == "agent":
        live = service.agent_capabilities()
        _, _, allowed_tools = policy.provider_sets(policy.load(db))
        # Skill bodies/prompts and host paths are never sent to this view.
        skills = [{"name": str(row.get("name", ""))[:120]}
                  for row in (live["skills"] or []) if isinstance(row, dict) and row.get("name")]
        tools = [tool for tool in (live["tools"] or []) if isinstance(tool, str)]
        return {"workspace_id": str(workspace.id), "generation": live["generation"],
                "tools": tools, "skills": skills, "errors": live["errors"],
                "tool_policy": {tool: not allowed_tools or tool in allowed_tools for tool in tools}}
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
