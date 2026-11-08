"""Platform-only locks for project and account filesystem administration.

These locks have no access to the OpenCode Native API or process.
"""
import threading
from types import SimpleNamespace

_locks = {}
_guard = threading.RLock()


def workspace_lock(workspace):
    with _guard:
        return _locks.setdefault(str(workspace.id), threading.RLock())


def account_workspace(user_id):
    return SimpleNamespace(id="account-" + str(user_id))
