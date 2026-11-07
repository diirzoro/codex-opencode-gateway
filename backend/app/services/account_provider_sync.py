"""Account credential checkpoints and idle-only runtime convergence.

OpenCode owns provider-specific refresh. Gateway observes its private auth store,
checkpoints rotations using compare-and-swap, and never revives deleted rows.
"""
import hashlib
import json
import time
import os
import stat
from tempfile import NamedTemporaryFile
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import select, inspect

from ..config import settings
from ..models import User, UserProviderCredential, Workspace, WorkspaceSession
from . import credentials


def oauth_payload(value):
    if not isinstance(value, dict) or value.get("type") != "oauth":
        raise ValueError("Expected OAuth credential")
    if any(not isinstance(value.get(k), str) or not value[k] for k in ("access", "refresh")):
        raise ValueError("Incomplete OAuth credential")
    if type(value.get("expires")) is not int or value["expires"] < 0:
        raise ValueError("Invalid OAuth expiration")
    return {k: value[k] for k in ("type", "access", "refresh", "expires", "accountId", "enterpriseUrl")
            if k in value}


def decode(row):
    try:
        value = json.loads(credentials.decrypt(row.ciphertext))
    except ValueError:
        return None  # Legacy bare API key.
    return oauth_payload(value) if isinstance(value, dict) and value.get("type") == "oauth" else None


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def read_auth(workspace):
    root = settings.runtime_root / str(workspace.user_id) / str(workspace.id)
    path = root / "data/opencode/auth.json"
    # Do not follow a replaced parent directory or a cross-account symlink.
    for parent in (root.parent, root, root / "data", path.parent, path):
        if parent.is_symlink():
            raise ValueError("Unsafe runtime credential path")
    if hasattr(os,"O_NOFOLLOW") and hasattr(os,"O_DIRECTORY"):
        # Bind traversal to directory descriptors; a parent swap after the
        # checks above must not redirect a read into another account.
        descriptors=[]
        try:
            directory=os.open(settings.runtime_root,os.O_RDONLY|os.O_DIRECTORY)
            descriptors.append(directory)
            for part in (str(workspace.user_id),str(workspace.id),"data","opencode"):
                directory=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory)
                descriptors.append(directory)
            fd=os.open("auth.json",os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
            with os.fdopen(fd,"rb") as source:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise ValueError("Invalid runtime credential file")
                content=source.read(1_000_001)
        except FileNotFoundError:
            return {}
        except OSError:
            raise ValueError("Unsafe runtime credential path") from None
        finally:
            for descriptor in reversed(descriptors):os.close(descriptor)
    else:
        if not path.is_file():return {}
        with path.open("rb") as source:content=source.read(1_000_001)
    if len(content)>1_000_000:raise ValueError("Runtime credential store too large")
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("Invalid runtime credential store")
    return data


def _stamp_path(workspace):
    # read_auth validates each existing parent, even when auth.json is absent.
    read_auth(workspace)
    return settings.runtime_root / str(workspace.user_id) / str(workspace.id) / "gateway-credentials.json"


def _stamps(workspace):
    path = _stamp_path(workspace)
    if path.is_symlink():
        raise ValueError("Unsafe credential version file")
    if not path.exists():
        return {}
    if path.stat().st_size > 1_000_000:
        raise ValueError("Credential version file too large")
    values = json.loads(path.read_text())
    if not isinstance(values, dict):
        raise ValueError("Invalid credential version file")
    return values


def bind(service, row):
    if not isinstance(getattr(service, "credential_bindings", None), dict):
        service.credential_bindings = {}
    value = decode(row)
    service.credential_bindings[row.provider_id] = (row.id, row.ciphertext,
        fingerprint(value) if value else None)
    if isinstance(getattr(service, "auth_failures", None), dict):
        service.auth_failures.pop(row.provider_id, None)
    workspace = getattr(service, "workspace_ref", None)
    if workspace is not None:
        values = _stamps(workspace)
        values[row.provider_id] = {"id":str(row.id), "version":fingerprint(row.ciphertext)}
        path = _stamp_path(workspace)
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as output:
            temporary = output.name
            json.dump(values, output)
        try:
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def startup_value(workspace, row):
    """Recover a rotation written before a crash, only for the same DB version."""
    value = decode(row)
    if value is None:
        return credentials.decrypt(row.ciphertext)
    stamp = _stamps(workspace).get(row.provider_id, {})
    if stamp == {"id":str(row.id), "version":fingerprint(row.ciphertext)}:
        saved = read_auth(workspace).get(row.provider_id)
        if isinstance(saved, dict) and saved.get("type") == "oauth":
            current = oauth_payload(saved)
            if current["expires"] > value["expires"]:
                return json.dumps(current)
    return json.dumps(value)


def prune_revoked(workspace, rows, legacy_ids):
    valid = {row.provider_id for row in rows} | set(legacy_ids)
    stale = set(_stamps(workspace)) - valid
    values = read_auth(workspace)
    if not stale.intersection(values):
        return False
    for provider_id in stale:
        values.pop(provider_id, None)
    path = settings.runtime_root / str(workspace.user_id) / str(workspace.id) / "data/opencode/auth.json"
    with NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as output:
        temporary = output.name
        json.dump(values, output)
    try:
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


def services_for(user_id):
    from . import opencode
    return [r.service for r in list(opencode._runtimes.values())
            if getattr(getattr(r.service,"workspace_ref",None),"user_id",None) == user_id]


def public_status(row, services=()):
    try:
        value = decode(row)
    except Exception:
        return {"auth_type":"unknown", "auth_status":"reauthorization_required"}
    if value is None:
        return {"auth_type":"api", "auth_status":"connected"}
    failed = any(getattr(s, "auth_failures", {}).get(row.provider_id) == row.ciphertext for s in services)
    return {"auth_type":"oauth", "auth_status":"reauthorization_required" if failed else
            "refresh_required" if value["expires"] <= int(time.time()*1000) else "connected"}


def checkpoint(db, workspace, service, rows):
    """Commit rotations in the maintenance session, then advance runtime bindings."""
    bindings = getattr(service, "credential_bindings", {})
    if not isinstance(bindings, dict):
        return 0
    values = read_auth(workspace)
    changed = 0
    for row in rows:
        if row.provider_id in getattr(service,"oauth_pending",{}):
            continue  # Callback has not confirmed this authorization yet.
        version = bindings.get(row.provider_id)
        if not version or version[:2] != (row.id, row.ciphertext):
            continue
        previous = decode(row)
        if previous is None or row.provider_id not in values:
            continue
        current = oauth_payload(values[row.provider_id])
        if fingerprint(current) == version[2] or current["expires"] <= previous["expires"]:
            continue
        encrypted = credentials.encrypt(json.dumps(current))
        from .user_provider_credentials import replace_encrypted_if_current
        if replace_encrypted_if_current(db,workspace.user_id,row.provider_id,version[1],encrypted,expected_id=row.id):
            # No insertion and no unconditional upsert: disconnect/reconnect wins.
            identifier, provider_id = row.id, row.provider_id
            db.commit()  # Never called with a request-owned session.
            from sqlalchemy.orm.attributes import set_committed_value
            set_committed_value(row, "ciphertext", encrypted)
            bind(service, SimpleNamespace(id=identifier, provider_id=provider_id, ciphertext=encrypted))
            changed += 1
    return changed


def require_idle(db, workspace, service):
    # Serialize with the submission route's workspace row lock, closing the
    # idle-check -> new-message race. Never wait behind an operational writer.
    if not getattr(workspace,"is_account_runtime",False):
        owned=db.scalar(select(Workspace.id).where(Workspace.id==workspace.id,
            Workspace.user_id==workspace.user_id).with_for_update(skip_locked=True))
        if owned is None or db.scalar(select(WorkspaceSession.id).where(
                WorkspaceSession.workspace_id==workspace.id,
                WorkspaceSession.status.in_(["submitted","waiting_approval"])).limit(1)) is not None:
            raise HTTPException(409,"Workspace is busy; credential sync deferred")
    service.ensure_auth_idle()


def reconcile(db, workspace, service, rows):
    """Retry mismatched credentials only when OpenCode confirms every session idle."""
    from . import providers
    bindings = getattr(service, "credential_bindings", {})
    pending = [row for row in rows if row.provider_id not in getattr(service,"oauth_pending",{})
               and bindings.get(row.provider_id, ())[:2] != (row.id, row.ciphertext)]
    if not pending:
        return False
    require_idle(db, workspace, service)
    for row in pending:
        providers.restore_credential(service, row.provider_id, credentials.decrypt(row.ciphertext))
    service.refresh_auth()
    for row in pending:
        bind(service, row)
    return True


def sweep():
    """One bounded pass over known running runtimes; never starts a stopped one."""
    from ..database import SessionLocal
    from . import opencode
    refs = [(r.service.workspace_ref, r.service) for r in list(opencode._runtimes.values())
            if getattr(r.service, "workspace_ref", None) is not None and r.process.poll() is None]
    groups = {}
    for workspace, service in refs:
        groups.setdefault(workspace.user_id, []).append((workspace, service))
    for uid, owned in groups.items():
        try:
            with SessionLocal() as db:
                if not inspect(db.connection()).has_table("user_provider_credentials"):
                    return
                if db.scalar(select(User.status).where(User.id == uid)) != "active":
                    continue
                rows = list(db.scalars(select(UserProviderCredential).where(UserProviderCredential.user_id == uid)))
                for workspace, service in owned:
                    lock = opencode.workspace_lock(workspace)
                    if not lock.acquire(blocking=False):
                        continue
                    try:
                        if service.state_lock.acquire(blocking=False):
                            try:
                                checkpoint(db, workspace, service, rows)
                            finally:
                                service.state_lock.release()
                    finally:
                        lock.release()
                db.commit()
                # Reload after CAS, never fan out a stale snapshot after a competing update.
                db.expire_all()
                rows = list(db.scalars(select(UserProviderCredential).where(UserProviderCredential.user_id == uid)))
                for workspace, service in owned:
                    lock = opencode.workspace_lock(workspace)
                    if not lock.acquire(blocking=False):
                        continue
                    try:
                        if service.state_lock.acquire(blocking=False):
                            try:
                                reconcile(db, workspace, service, rows)
                            except HTTPException:
                                pass  # busy/unavailable: leave pending; retry next tick
                            finally:
                                db.rollback()  # release the per-workspace idle guard
                                service.state_lock.release()
                    finally:
                        lock.release()
        except Exception:
            # No exception bodies or credentials in logs. Other accounts keep syncing.
            import logging
            logging.getLogger(__name__).warning("Account provider sync deferred")


def remove_auth(user_id, runtime_id, provider_id, *, runtime_root=None):
    """Revoke using a pinned directory FD; never follow another tenant's link."""
    import secrets
    base=runtime_root if runtime_root is not None else settings.runtime_root
    descriptors=[];temporary=None;reading=True
    try:
        directory=os.open(base,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        descriptors.append(directory)
        for part in (str(user_id),str(runtime_id),"data","opencode"):
            directory=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory)
            descriptors.append(directory)
        fd=os.open("auth.json",os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
        with os.fdopen(fd,"rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):raise ValueError("Invalid auth file")
            raw=source.read(1_000_001)
        reading=False
        if len(raw)>1_000_000:raise ValueError("Auth file too large")
        values=json.loads(raw)
        if not isinstance(values,dict):raise ValueError("Invalid auth file")
        if provider_id not in values:return
        del values[provider_id]
        temporary=".gateway-revoke-"+secrets.token_hex(16)
        output=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory)
        with os.fdopen(output,"w") as target:json.dump(values,target)
        os.replace(temporary,"auth.json",src_dir_fd=directory,dst_dir_fd=directory)
        temporary=None
    except FileNotFoundError:
        if reading:return
        raise
    finally:
        if temporary is not None:
            try:os.unlink(temporary,dir_fd=directory)
            except FileNotFoundError:pass
        for descriptor in reversed(descriptors):os.close(descriptor)
