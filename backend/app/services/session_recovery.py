"""Reconcile durable dispatches against native execution; never replay a tool.

OpenCode persists history but pending tool promises are process-local. A healthy
idle runtime without the original pending request cannot resume that request.
Transient HTTP/health errors are not proof of interruption and must propagate.
"""
import json
from sqlalchemy import select
from ..models import ExecutionEvent, WorkspaceSession
from . import session_lifecycle


def reconcile(db, workspace, service, session=None):
    if getattr(workspace, 'is_account_runtime', False): return
    from ..routes.agent import tasks
    rows = [session] if session is not None else list(db.scalars(select(WorkspaceSession).where(
        WorkspaceSession.workspace_id == workspace.id, WorkspaceSession.user_id == workspace.user_id,
        WorkspaceSession.status.in_(session_lifecycle.BUSY))))
    for row in rows:
        if row.status not in session_lifecycle.BUSY: continue
        submitted = db.scalar(select(ExecutionEvent).where(ExecutionEvent.session_id == row.id,
            ExecutionEvent.kind == 'submission').order_by(ExecutionEvent.id.desc()).limit(1))
        dispatched = db.scalar(select(ExecutionEvent).where(ExecutionEvent.session_id == row.id,
            ExecutionEvent.kind == 'dispatch').order_by(ExecutionEvent.id.desc()).limit(1))
        if not submitted or not dispatched: continue  # Preflight is not a dispatched operation.
        saved, dispatch = json.loads(submitted.data), json.loads(dispatched.data)
        if dispatch.get('request_id') != saved.get('request_id'): continue
        task = tasks.get(str(row.id))
        changed_generation = bool(dispatch.get('generation') and dispatch['generation'] != service.generation)
        if task is not None and not task.done() and not changed_generation: continue
        statuses = service.request('GET', '/session/status')
        if not isinstance(statuses, dict): continue
        current = statuses.get(row.opencode_session_id, {'type': 'idle'})
        if not isinstance(current, dict) or current.get('type') != 'idle': continue
        permissions = service.request('GET', '/permission')
        questions = service.request('GET', '/question')
        if not isinstance(permissions, list) or not isinstance(questions, list): continue
        if any(p.get('sessionID') == row.opencode_session_id for p in [*permissions, *questions] if isinstance(p, dict)):
            continue  # A surviving native waiter remains the authority.
        messages = service.request('GET', service.session_path(row.opencode_session_id, '/message'))
        if not isinstance(messages, list): continue
        replies = [m for m in messages if isinstance(m, dict) and
            m.get('info', {}).get('role') == 'assistant' and m['info'].get('parentID') == saved.get('message_id')]
        unfinished = any(p.get('type') == 'tool' and p.get('state', {}).get('status') in {'pending', 'running'}
            for m in replies for p in m.get('parts', []) if isinstance(p, dict))
        final = replies[-1].get('info', {}) if replies else {}
        completed = bool(final.get('time', {}).get('completed') and not final.get('error') and not unfinished
                         and final.get('finish') in {'stop', 'length', 'content-filter'}
                         and any(p.get('type') == 'text' and p.get('text', '').strip()
                                 for p in replies[-1].get('parts', [])))
        # Serialize with admission/Stop and recheck the receipt after network IO.
        session_lifecycle.lock_workspace(db, workspace); db.refresh(row)
        latest = db.scalar(select(ExecutionEvent).where(ExecutionEvent.session_id == row.id,
            ExecutionEvent.kind == 'submission').order_by(ExecutionEvent.id.desc()).limit(1))
        if row.status not in session_lifecycle.BUSY or not latest or latest.id != submitted.id:
            continue
        row.status = 'completed' if completed else 'failed'
        details = {'request_id': saved['request_id'], 'automatic_replay': False,
                   'reason': 'Runtime interruption detected. History is preserved; review it before sending a new request.'}
        db.add(ExecutionEvent(session_id=row.id, kind='execution_recovered' if completed else 'runtime_interrupted', data=json.dumps(details)))
        db.add(ExecutionEvent(session_id=row.id, kind=row.status, data=json.dumps({} if completed else details)))
        db.commit()
