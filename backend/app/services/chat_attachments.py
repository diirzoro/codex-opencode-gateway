"""Owned temporary uploads only. No AI execution, message storage or SSE transport.

Manifests live outside repo/Native storage. Only the exact manifest-owned original
and partial file are unlinked; unknown files, project files and Native history
are never recursively removed. Existing maintenance performs conservative reap.
"""
import asyncio
import fcntl
import json
import os
import stat
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from fastapi import HTTPException
from sqlalchemy import select
from ..config import settings
from ..models import Workspace, WorkspaceSession
from . import workspaces

DIRECTORY = '__gateway_chat_attachments'
TTL = 24 * 3600
# OpenCode Native alone decides whether a file's format/model is readable.
# Gateway only authorizes ownership, safely stores temporary transport bytes,
# and applies the existing workspace disk quota. Do not invent a MIME allowlist.
FORWARD_GRACE = 10
_sweep_cursor = ""


def _area(workspace):
    # Server-generated UUID components only; never use a browser path.
    root = settings.runtime_root / 'chat-attachments' / str(workspace.user_id) / str(workspace.id)
    current = settings.runtime_root
    for component in ('chat-attachments', str(workspace.user_id), str(workspace.id)):
        current = current / component
        if current.is_symlink(): raise HTTPException(403, 'Unsafe temporary storage')
        current.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


@contextmanager
def _guard(workspace):
    area=_area(workspace)
    fd=os.open(area/'.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        yield area
    finally: os.close(fd)


@contextmanager
def locked(workspace, identifier):
    try: identifier=str(uuid.UUID(str(identifier)))
    except ValueError: raise HTTPException(403,'Invalid attachment identifier') from None
    with _guard(workspace) as area:
        path=area/(identifier+'.json')
        if path.is_symlink(): raise HTTPException(403,'Unsafe temporary manifest')
        value=json.loads(path.read_text()) if path.exists() else None
        yield value,path


def _save(path, value):
    # Held under a stable per-workspace flock, including across workers.
    temp = path.with_suffix('.new')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream: json.dump(value, stream)
    os.replace(temp, path)


def _directory(workspace, value):
    return workspaces.safe_path(workspace, DIRECTORY + '/' + value['id'])


def _remove(workspace, value):
    directory = _directory(workspace, value)
    if not directory.exists(): return
    # Pin the directory: symlink swaps cannot redirect unlink into projects.
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for name in (value['name'], 'upload.part'):
            try:
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode): raise HTTPException(409, 'Temporary file requires review')
                os.unlink(name, dir_fd=fd)
            except FileNotFoundError: pass
    finally: os.close(fd)
    # Never remove unknown intermediate files: classification must be explicit.
    try: directory.rmdir()
    except OSError: pass


def create(db, workspace, session_id, name, size, mime):
    with _guard(workspace):
        return _create(db,workspace,session_id,name,size,mime)


def _create(db,workspace,session_id,name,size,mime):
    session = workspaces.owned(db, WorkspaceSession, session_id, workspace.user_id)
    if session.workspace_id != workspace.id: raise HTTPException(404, 'Conversation is outside this Workspace')
    if not name or len(name)>200 or name in {'.','..','upload.part'} or any(c in name for c in '/\\\x00\r\n') or workspaces.protected_component(name):
        raise HTTPException(422, 'A safe attachment filename is required')
    if size<=0: raise HTTPException(422,'Attachment must not be empty')
    # Neither file format nor per-file model limits are decided here; Native
    # and the chosen provider report actual support after secure transport.
    # One authoritative quota scan suffices; the size-aware comparison below
    # already rejects both full workspaces and the incoming attachment.
    totals = workspaces.account_local_storage_payload(db,workspace.user_id)
    used_bytes = totals["used_bytes"]
    quota_limit = totals["limit_bytes"]
    if used_bytes + size > quota_limit:
        raise HTTPException(413, 'Gateway account storage is full across local and GitHub projects')
    # Bounded number of live uploads prevents reserving unlimited disk slots.
    area = _area(workspace)
    count = 0;reserved_bytes=0
    records=list(area.glob('*.json'))
    if len(records)>=200: raise HTTPException(429,'Recent attachment limit reached; wait for temporary cleanup')
    for path in records:
        if path.is_symlink(): continue
        existing=json.loads(path.read_text())
        if existing.get('state') not in {'removed','cancelled','failed'}: count+=1
        if existing.get('state')=='uploading': reserved_bytes+=existing['size']
        if count >= 20: raise HTTPException(429, 'Too many pending attachments; cancel or wait for cleanup')
    if used_bytes + reserved_bytes + size > quota_limit:
        raise HTTPException(413,'Workspace storage is reserved by pending uploads')
    reserved=workspaces.safe_path(workspace,DIRECTORY)
    if reserved.exists() and not (area/'managed').is_file():
        raise HTTPException(409,'Reserved attachment directory already exists; all files preserved')
    reserved.mkdir(mode=0o700,exist_ok=True)
    fd=os.open(area/'managed',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600);os.close(fd)
    identifier = str(uuid.uuid4())
    value = {'id':identifier, 'session_id':str(session.id), 'runtime_id':session.opencode_session_id,
             'name':name, 'size':size, 'mime':mime, 'created':time.time(), 'state':'uploading', 'started':False}
    directory = _directory(workspace, value)
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    _save(area/(identifier+'.json'),value)
    return public(value)


def managed(workspace):
    marker=settings.runtime_root/'chat-attachments'/str(workspace.user_id)/str(workspace.id)/'managed'
    return marker.is_file() and not any(path.is_symlink() for path in (marker,*marker.parents))


def public(value):
    return {k:value[k] for k in ('id','name','size','mime','state')} | {'path':DIRECTORY+'/'+value['id']+'/'+value['name'], 'temporary':True}


async def upload(workspace, identifier, request):
    total = 0
    fd = None
    owns_transfer=False
    try:
        with locked(workspace, identifier) as (value, path):
            if not value: raise HTTPException(404, 'Attachment not found')
            if value['state'] != 'uploading' or value['started']: raise HTTPException(409, 'Upload cannot be restarted')
            value['started'] = True; _save(path,value);owns_transfer=True
            fd = os.open(_directory(workspace,value)/'upload.part', os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
        async with asyncio.timeout(900):
            async for chunk in request.stream():
                with locked(workspace,identifier) as (value,path):
                    if not value or value['state'] != 'uploading': raise HTTPException(409, 'Upload cancelled')
                    total += len(chunk)
                    if total > value['size']: raise HTTPException(413, 'Transfer exceeded the reserved upload size')
                    # A chunk write may be partial; preserve all bytes.
                    view=memoryview(chunk)
                    while view:
                        written=os.write(fd,view); view=view[written:]
        os.close(fd);fd=None
        with locked(workspace,identifier) as (value,path):
            if not value or value['state'] != 'uploading': raise HTTPException(409, 'Upload cancelled')
            if total != value['size']: raise HTTPException(422, 'Incomplete attachment upload')
            if workspaces.storage_payload(workspace)["used_bytes"] > workspaces.quota_bytes(workspace):
                raise HTTPException(413, 'Gateway shared account storage limit reached')
            directory=_directory(workspace,value)
            directory_fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            try: os.rename('upload.part',value['name'],src_dir_fd=directory_fd,dst_dir_fd=directory_fd)
            finally: os.close(directory_fd)
            value['state']='ready'; _save(path,value)
            return public(value)
    except BaseException:
        if fd is not None: os.close(fd)
        with locked(workspace,identifier) as (value,path):
            if owns_transfer and value and value['state']=='uploading':
                _remove(workspace,value);value['state']='failed';_save(path,value)
        raise


def pending(workspace):
    """Expose only owner/workspace-scoped temporary slot metadata, never file data."""
    with _guard(workspace) as area:
        result=[]
        for path in sorted(area.glob('*.json')):
            if path.is_symlink():continue
            try:
                value=json.loads(path.read_text())
                if value.get('id')!=path.stem or value.get('state') not in {'uploading','ready','processing'}:continue
                result.append({**public(value),'session_id':value['session_id']})
            except (ValueError,KeyError,TypeError):continue
            if len(result)>=200:break
        return result


def clear_pending(workspace):
    """Explicit account-owner action. Never delete Native-leased/processing files."""
    removed=[];processing=0;preserved=0
    with _guard(workspace) as area:
        for path in sorted(area.glob('*.json')):
            if path.is_symlink():preserved+=1;continue
            try:
                value=json.loads(path.read_text())
                if not isinstance(value,dict) or value.get('id')!=path.stem:
                    preserved+=1;continue
                uuid.UUID(value['id'])
                if value.get('state')=='processing':
                    processing+=1;continue
                if value.get('state') not in {'uploading','ready','cancelled','failed','removed'}:
                    preserved+=1;continue
                _remove(workspace,value)
                if _directory(workspace,value).exists():
                    preserved+=1;continue  # Unknown entries: never forget manifest.
                removed.append(value['id'])
                path.unlink()
            except (ValueError,KeyError,TypeError,OSError,HTTPException):
                preserved+=1
        return {'removed':len(removed),'removed_ids':removed,
                'skipped_processing':processing,'preserved_for_review':preserved}



def clear_native_deleted_session(workspace, session_id):
    """Remove only temporary attachments after Native confirms session deletion.

    This never reads AI content, project files, or OpenCode history. It may
    remove processing slots because the original Native session is gone.
    """
    removed=0
    with _guard(workspace) as area:
        for manifest in area.glob('*.json'):
            if manifest.is_symlink():continue
            try:
                value=json.loads(manifest.read_text())
                if value.get('id')!=manifest.stem or value.get('session_id')!=str(session_id):
                    continue
                if value.get('state') not in {'ready','uploading','processing','failed','cancelled','removed'}:
                    continue
                _remove(workspace,value)
                if _directory(workspace,value).exists():continue
                manifest.unlink()
                removed+=1
            except (OSError,ValueError,KeyError,TypeError,HTTPException):
                # Preserve unknown files rather than risk deleting project data.
                continue
    return removed


def cancel(workspace,identifier):
    with locked(workspace,identifier) as (value,path):
        if not value: raise HTTPException(404, 'Attachment not found')
        if value['state']=='processing': raise HTTPException(409, 'Stop Native processing before removing this attachment')
        _remove(workspace,value);value['state']='cancelled';_save(path,value)
        return {'state':'cancelled','removed':True}


def lease(workspace, session, relative, message_id):
    parts=relative.split('/')
    if not parts or parts[0]!=DIRECTORY: return  # Existing intentional project-file attachments stay permanent.
    if not isinstance(message_id,str) or not message_id.startswith('msg_') or len(message_id)>120: raise HTTPException(422,'A native message ID is required for temporary attachments')
    if len(parts)!=3: raise HTTPException(403,'Invalid temporary attachment')
    with locked(workspace,parts[1]) as (value,path):
        if not value or value['session_id']!=str(session.id) or value['name']!=parts[2]: raise HTTPException(404,'Attachment not found')
        if value['state']=='processing' and value.get('message_id')==message_id: return
        if value['state']!='ready' or time.time()-value['created']>=TTL: raise HTTPException(410,'Temporary attachment is unavailable')
        value.update(state='processing',leased_at=time.time(),message_id=message_id)
        _save(path,value)


def acknowledge(workspace,session_id,message_id,identifiers):
    # A delivery hint for cleanup, never authorization/execution confirmation.
    # Native idle is still independently required before removing a leased file.
    for identifier in identifiers:
        with locked(workspace,identifier) as (value,path):
            if not value or value['session_id']!=str(session_id) or value.get('message_id')!=message_id:
                raise HTTPException(404,'Attachment is outside this native submission')
            if value['state']=='processing':
                value['delivery_observed']=True;_save(path,value)
    return {'recorded':True}


def reap_workspace(workspace, *, now=None):
    now=time.time() if now is None else now
    area=_area(workspace); candidates=[]
    for path in area.glob('*.json'):
        if path.is_symlink(): continue
        with locked(workspace,path.stem) as (value,_):
            if not value: continue
            due=(value['state']=='processing' and value.get('delivery_observed') and now-value.get('leased_at',now)>=FORWARD_GRACE) or now-value['created']>=TTL
            if due: candidates.append(value['id'])
        if len(candidates)>=100: break
    if not candidates: return
    # Native's status is authoritative, never client text/first streamed token.
    # Unknown/error status preserves files, including exceptions beyond 24h.
    from .workspace_cache import runtime_idle
    needs_idle=any(json.loads((area/(identifier+'.json')).read_text()).get('state')=='processing' for identifier in candidates)
    idle=True
    if needs_idle:
        try: idle=runtime_idle(workspace)
        except (HTTPException,OSError): idle=None
    if not idle:
        for identifier in candidates:
            with locked(workspace,identifier) as (value,path):
                if value and value['state']=='processing' and now-value['created']>=TTL:
                    value['cleanup_deferred']='native-active' if idle is False else 'native-status-unavailable'
                    _save(path,value)
        return
    for identifier in candidates:
        with locked(workspace,identifier) as (value,path):
            if not value: continue
            if value['state']=='processing' and (now-value.get('leased_at',now)<FORWARD_GRACE or not value.get('delivery_observed') and now-value['created']<TTL): continue
            if value['state']!='processing' and now-value['created']<TTL: continue
            _remove(workspace,value)
            if now-value['created']>=TTL:
                path.unlink(missing_ok=True)
            else:
                value['state']='removed';_save(path,value)


def sweep():
    global _sweep_cursor
    from ..database import SessionLocal
    with SessionLocal() as db:
        # Only manifests minted by this feature. No scan/deletion of old uploads.
        base=settings.runtime_root/'chat-attachments'
        if not base.is_dir() or base.is_symlink(): return
        paths=sorted(set(p.parent for p in base.glob('*/*/*.json')))
        following=[path for path in paths if str(path)>_sweep_cursor]
        batch=(following or paths)[:100]
        for path in batch:
            _sweep_cursor=str(path)
            if path.is_symlink(): continue
            try: owner=uuid.UUID(path.parent.name);identifier=uuid.UUID(path.name)
            except ValueError: continue
            workspace=db.scalar(select(Workspace).where(Workspace.id==identifier,Workspace.user_id==owner).with_for_update(skip_locked=True))
            if workspace is not None:
                try: reap_workspace(workspace)
                except (HTTPException,OSError,ValueError): pass # Fail closed; retry through existing maintenance.
            db.commit()
