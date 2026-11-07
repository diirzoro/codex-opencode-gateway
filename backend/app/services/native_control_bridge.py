"""Control-plane compatibility for the one persistent OpenCode Native daemon.

No AI runtime, model catalog, credential store, session, provider client, subprocess,
or independent cache exists in this module. Projects still need an owner-scoped
thread lock for filesystem lifecycle transitions.
"""
import threading
from types import SimpleNamespace
from fastapi import HTTPException
from ..config import settings

_locks = {}
_guard = threading.RLock()

def workspace_lock(workspace):
    with _guard:
        return _locks.setdefault(str(workspace.id), threading.RLock())

def stop_workspace(workspace):
    # Only the Native service owns process lifetime. Do not stop it when a
    # Gateway workspace is closed, expired or deleted.
    return None

def stop_all():
    return None

def shared_health():
    # Gateway never probes, starts or reconfigures an AI engine here.
    # Native health is read via its authorized native /global/health endpoint.
    return {"healthy":False,"native_only":True,
            "detail":"Use the existing authorized OpenCode Native health route"}

def account_workspace(user_id):
    return SimpleNamespace(id="account-"+str(user_id),user_id=user_id,
                           is_account_runtime=True)

def for_workspace(workspace, *, start=True, db=None):
    raise HTTPException(410,"Legacy Python OpenCode runtime deleted; use OpenCode Native API")

def for_account(user_id, *, start=True, db=None):
    raise HTTPException(410,"Legacy Python provider runtime deleted; use OpenCode Native API")
