"""Compensated runtime archival; SQL commit precedes irreversible erasure.

A same-filesystem private rename keeps data recoverable on rollback/crash. The
user's committed status is the recovery journal; no schema/business-rule change.
Project files and billing records are outside this storage and never touched.
"""
import logging
import shutil
import uuid
from ..config import settings
logger = logging.getLogger(__name__)


class StagedRuntime:
    def __init__(self, owner_id):
        owner = str(uuid.UUID(str(owner_id)))
        base = settings.runtime_root.resolve()
        parent = base / '.account-archive'
        if parent.is_symlink(): raise RuntimeError('Unsafe archive staging directory')
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.source = base / owner
        self.staged = parent / owner
        self.validate()

    def validate(self):
        if self.source.is_symlink() or self.staged.is_symlink():
            raise RuntimeError('Unsafe account runtime directory')

    def stage(self):
        self.validate()
        if self.staged.exists(): raise RuntimeError('Unrecovered account archive exists')
        if self.source.exists(): self.source.rename(self.staged)

    def restore(self):
        self.validate()
        if not self.staged.exists(): return
        if self.source.exists(): raise RuntimeError('Account runtime recovery conflicts with existing storage')
        self.staged.rename(self.source)

    def erase(self):
        self.validate()
        if self.staged.exists(): shutil.rmtree(self.staged)


def recover_pending(db):
    from sqlalchemy import select
    from ..models import User, Workspace
    from . import opencode
    base = settings.runtime_root.resolve() / '.account-archive'
    if not base.exists(): return
    if base.is_symlink(): raise RuntimeError('Unsafe archive staging directory')
    # This directory is server-created/private. Bound each maintenance pass.
    import itertools
    for path in itertools.islice(base.iterdir(), 100):
        try: identifier = uuid.UUID(path.name)
        except ValueError: continue
        locks = []
        try:
            for row in [opencode.account_workspace(identifier), *db.scalars(select(Workspace).where(Workspace.user_id == identifier))]:
                lock = opencode.workspace_lock(row)
                if not lock.acquire(blocking=False): raise RuntimeError('Runtime recovery busy')
                locks.append(lock)
                runtime = opencode._runtimes.get(str(row.id))
                if runtime and runtime.process.poll() is None: raise RuntimeError('Runtime is active during archive recovery')
            user = db.scalar(select(User).where(User.id == identifier).with_for_update(skip_locked=True))
            if user is None: continue  # Unknown/locked identity is never deleted.
            storage = StagedRuntime(identifier)
            if user.status == 'archived': storage.erase()
            else: storage.restore()
            db.commit()
        except Exception:
            db.rollback()
            logger.warning('Account runtime archive recovery deferred for %s', identifier)
        finally:
            for lock in reversed(locks): lock.release()
