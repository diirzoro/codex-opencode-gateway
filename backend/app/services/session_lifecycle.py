"""Durable client visibility and submission receipts, using existing event storage.

OpenCode owns conversations and execution. Gateway owns client open/closed state,
visibility and admission. Workspace row locks serialize these small transactions
across workers; no migration or runtime session deletion is required.
"""
import json
import secrets
import threading
import time
from fastapi import HTTPException
from sqlalchemy import select
from ..models import ExecutionEvent, Workspace, WorkspaceSession

BUSY = {"submitted", "waiting_approval"}
_message_lock = threading.Lock()
_message_clock = 0


def new_message_id():
    # OpenCode message IDs sort by a six-byte timestamp/counter prefix. Keep
    # that native format; a random UUID can place user messages out of order.
    global _message_clock
    with _message_lock:
        _message_clock = max((time.time_ns() // 1_000_000 << 12) + 1, _message_clock + 1)
        prefix = (_message_clock & ((1 << 48) - 1)).to_bytes(6, "big").hex()
    suffix = "".join(secrets.choice("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz") for _ in range(14))
    return "msg_" + prefix + suffix


def lock_workspace(db, workspace):
    return db.scalar(select(Workspace).where(Workspace.id == workspace.id,
        Workspace.user_id == workspace.user_id).with_for_update().execution_options(populate_existing=True))


def states(db, rows):
    if not rows:
        return {}
    result = {row.id: ("active" if row.status in BUSY else "closed") for row in rows}
    events = db.scalars(select(ExecutionEvent).where(ExecutionEvent.session_id.in_(result),
        ExecutionEvent.kind == "client_session").order_by(ExecutionEvent.id))
    for event in events:
        result[event.session_id] = json.loads(event.data)["state"]
    return result


def state(db, session):
    return states(db, [session])[session.id]


def set_state(db, session, value):
    db.add(ExecutionEvent(session_id=session.id, kind="client_session", data=json.dumps({"state": value})))


def workspace_rows(db, workspace):
    return list(db.scalars(select(WorkspaceSession).where(WorkspaceSession.workspace_id == workspace.id,
        WorkspaceSession.user_id == workspace.user_id).execution_options(populate_existing=True)))


def require_slot(db, workspace, selected=None):
    rows = workspace_rows(db, workspace)
    values = states(db, rows)
    if any((row.status in BUSY or values[row.id] == "active") and row.id != selected for row in rows):
        raise HTTPException(409, "Close the active session before opening or creating another session")


def require_visible(db, session):
    if state(db, session) == "deleted":
        raise HTTPException(404, "Session is not in client history")


def payload(session, lifecycle):
    status = ("running" if session.status in BUSY else session.status
              if session.status in {"completed", "failed"} else "active") if lifecycle == "active" else lifecycle
    return {"id": str(session.id), "workspace_id": str(session.workspace_id), "title": session.title,
            "lifecycle": lifecycle, "status": status, "execution_status": session.status,
            "created_at": session.created_at}


def hidden_messages(db, session_id):
    return {json.loads(row.data)["message_id"] for row in db.scalars(select(ExecutionEvent).where(
        ExecutionEvent.session_id == session_id, ExecutionEvent.kind == "client_message_hidden"))}


def receipt(db, session_id, request_id):
    # Session admission is under the workspace lock. Receipts survive browser and
    # Gateway restarts and are checked before any request reaches OpenCode.
    for row in db.scalars(select(ExecutionEvent).where(ExecutionEvent.session_id == session_id,
            ExecutionEvent.kind == "submission").order_by(ExecutionEvent.id.desc())):
        data = json.loads(row.data)
        if data["request_id"] == str(request_id):
            return data
    return None
