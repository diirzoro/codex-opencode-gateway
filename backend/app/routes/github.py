"""Session-bound GitHub connection, callback bridge and explicit identity confirmation."""
import html
import logging
import secrets
import uuid
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import User, Project, Workspace, AccountAudit
from ..services import github
from ..services.entitlements import require_advanced
from .dependencies import require_user

router = APIRouter(prefix="/api/github", tags=["github"])

@router.get("/status")
def status(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    # A disconnected customer must never see a cached 'connected' response
    # when returning to the Gateway from GitHub or reloading the client UI.
    return JSONResponse(github.connection_status(db, user, request.state.auth_session.id),
                        headers={"Cache-Control": "private, no-store"})

@router.post("/connect")
def connect(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    require_advanced(db, user)
    return JSONResponse({"url": github.begin_fresh_link(db, user, request.state.auth_session.id)},
                        headers={"Cache-Control": "private, no-store"})

# Uvicorn normally logs the entire query string. OAuth codes/state must not be logged.
class GithubCallbackLogFilter(logging.Filter):
    def filter(self, record):
        if isinstance(record.args,tuple) and len(record.args)>=3:
            args=list(record.args)
            if isinstance(args[2],str) and args[2].split('?')[0]=='/api/github/callback':
                args[2]='/api/github/callback?[redacted]'
                record.args=tuple(args)
        return True

logging.getLogger('uvicorn.access').addFilter(GithubCallbackLogFilter())


@router.get('/install')
@router.get('/authorize')
def legacy_entry(user: User = Depends(require_user)):
    # Legacy GET links cannot silently clear/recreate an authorization.
    return RedirectResponse(settings.public_base_url+'/?github=connect-required',303)


class CallbackBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    state: str = Field(min_length=1,max_length=64)
    code: str | None = Field(default=None,max_length=1024)
    installation_id: int | None = None
    setup_action: str | None = None
    error: str | None = Field(default=None,max_length=120)


@router.get('/callback')
def callback(state: str | None=None, installation_id: int | None=None,
             setup_action: str | None=None, code: str | None=None, error: str | None=None):
    # Cross-site GitHub navigation omits SameSite=Strict Gateway cookies. A local
    # document submits a same-origin POST, where require_user validates the real
    # current Gateway login. Do not weaken the session cookie to solve redirects.
    # no-referrer makes navigation-mode form POSTs send Origin: null, which our
    # CSRF boundary correctly rejects. strict-origin preserves the real origin
    # without disclosing callback code/state in Referer, including without JS.
    if not state or len(state)>64 or (code and len(code)>1024):
        return RedirectResponse(settings.public_base_url+'/?github=error',303)
    fields={'state':state,'code':code,'installation_id':installation_id,
            'setup_action':setup_action,'error':error}
    inputs=''.join('<input type="hidden" name="'+k+'" value="'+html.escape(str(v),quote=True)+'">'
                   for k,v in fields.items() if v is not None)
    nonce=secrets.token_urlsafe(20)
    page='<!doctype html><html><head><meta charset="utf-8"><meta name="referrer" content="strict-origin"><title>GitHub connection</title></head><body><p>Completing GitHub authorization / استكمال تفويض GitHub</p><form id="complete" method="post" action="/api/github/callback/complete">'+inputs+'<button type="submit">Continue / متابعة</button></form><script nonce="'+nonce+'">history.replaceState(null,\'\',\'/api/github/callback\');document.getElementById(\'complete\').submit();</script></body></html>'
    return HTMLResponse(page,headers={'Cache-Control':'private, no-store','Referrer-Policy':'strict-origin',
        'Content-Security-Policy':"default-src 'none'; form-action 'self'; frame-ancestors 'none'; script-src 'nonce-"+nonce+"'",'X-Frame-Options':'DENY'})


@router.post('/callback/complete')
async def complete_callback(request: Request,user: User=Depends(require_user),db: Session=Depends(get_db)):
    form=dict(await request.form())
    try:
        body=CallbackBody.model_validate(form)
    except ValueError:
        raise HTTPException(422,'Invalid GitHub callback')
    destination=settings.public_base_url+'/?github='
    try:
        if body.error:
            # State/session validation is still mandatory when cancelling.
            record=github._state(db,body.state,user,request.state.auth_session.id)
            record.consumed=True;record.pending_payload=None;db.commit()
            return RedirectResponse(destination+'denied',303)
        # Vendor requests are synchronous; use the existing threadpool, not an
        # event-loop blocking handler or a background authorization service.
        from starlette.concurrency import run_in_threadpool
        result=await run_in_threadpool(github.handle_callback,db,body.state,body.installation_id,
            body.setup_action,body.code,user=user,auth_session_id=request.state.auth_session.id)
        if result.get('redirect'):return RedirectResponse(result['redirect'],303)
        return RedirectResponse(destination+'confirm',303)
    except HTTPException as exc:
        outcome='transaction-expired' if exc.status_code==400 else 'account-conflict' if exc.status_code==409 else 'session-mismatch' if exc.status_code==403 else 'configuration' if exc.status_code==503 else 'error'
        return RedirectResponse(destination+outcome,303)


class ConfirmationBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    connection_id: uuid.UUID
    github_user_id: int
    installation_id: int

class PendingBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    connection_id: uuid.UUID


class GithubEmailRequest(PendingBody):
    email: EmailStr


class GithubEmailCode(PendingBody):
    code: str = Field(pattern=r'^\d{6}$')


@router.post('/pending/email/send')
def send_email_code(body: GithubEmailRequest,request: Request,user: User=Depends(require_user),db: Session=Depends(get_db)):
    return JSONResponse(github.send_connection_code(db,user,request.state.auth_session.id,body.connection_id,str(body.email)),
                        headers={'Cache-Control':'private, no-store'})


@router.post('/pending/email/verify')
def verify_email_code(body: GithubEmailCode,request: Request,user: User=Depends(require_user),db: Session=Depends(get_db)):
    return JSONResponse(github.verify_connection_code(db,user,request.state.auth_session.id,body.connection_id,body.code),
                        headers={'Cache-Control':'private, no-store'})

@router.post('/confirm')
def confirm(body: ConfirmationBody,request: Request,user: User=Depends(require_user),db: Session=Depends(get_db)):
    return JSONResponse(github.confirm_connection(db,user,request.state.auth_session.id,
        body.connection_id,body.github_user_id,body.installation_id),headers={'Cache-Control':'private, no-store'})

@router.post('/pending/install')
def pending_install(body: PendingBody,request: Request,user: User=Depends(require_user),db: Session=Depends(get_db)):
    return JSONResponse({'url':github.pending_installation(db,user,request.state.auth_session.id,body.connection_id)},
                        headers={'Cache-Control':'private, no-store'})

@router.post('/disconnect')
def disconnect(request: Request,body: PendingBody | None=Body(default=None),user: User=Depends(require_user),db: Session=Depends(get_db)):
    # Explicit account disconnect removes authorization, not a potentially
    # shared App installation. Uninstall remains a separate ownership action.
    github.lock_owner(db,user)
    connection=db.scalar(select(github.GithubConnection).where(github.GithubConnection.user_id==user.id))
    if body:
        if connection and connection.id!=body.connection_id:
            raise HTTPException(409,'Connection changed; review again')
        if not connection and not db.scalar(select(github.GithubAuthState.state).where(
            github.GithubAuthState.user_id==user.id,
            github.GithubAuthState.auth_session_id==request.state.auth_session.id,
            github.GithubAuthState.connection_id==body.connection_id)):
            raise HTTPException(409,'Connection changed; review again')
    if connection:
        for row in db.scalars(select(Workspace).join(Project).where(
            Workspace.user_id==user.id,Project.user_id==user.id,Project.source_type=='github',
            Project.github_installation_id==connection.installation_id,
            Workspace.status.notin_(['cache_expiring','cache_expired']))):
            row.last_activity_at=datetime.now(timezone.utc)
    return JSONResponse(github.disconnect(db,user,revoke_grant=True),headers={'Cache-Control':'private, no-store'})


def _disconnect_copy(db,user,workspace_id):
    from ..services import workspaces
    row=workspaces.owned(db,Workspace,workspace_id,user.id)
    connection=github.connection_for(db,user)
    if (row.project.user_id!=user.id or row.project.source_type!='github'
        or row.project.github_installation_id!=connection.installation_id):
        raise HTTPException(404,'No imported working copy belongs to this connection')
    return row,connection


def _copy_snapshot(row):
    """Review fingerprint only; no content, credentials or physical paths."""
    from ..services import workspaces
    state=workspaces.status(row)
    digest=hashlib.sha256(json.dumps(state,sort_keys=True).encode())
    # Include actual changed-file bytes: a draft may change without a new HEAD
    # or a different porcelain status. Never read protected files or symlinks.
    for change in state['changes']:
        for name in (change['path'],change.get('original_path')):
            if not name:continue
            path=workspaces.safe_path(row,name)
            if path.is_dir():raise HTTPException(409,'Nested repositories or submodules need manual save review')
            if path.is_file():
                with path.open('rb') as stream:
                    while chunk:=stream.read(65536):digest.update(chunk)
    ignored=workspaces.git(row,'ls-files','--others','--ignored','--exclude-standard','-z').stdout
    refs=workspaces.git(row,'for-each-ref','--format=%(objectname)','refs/heads','refs/stash').stdout.splitlines()
    digest.update(json.dumps(refs).encode())
    return state,digest.hexdigest(),bool(ignored) or any(sha!=state['head'] for sha in refs)


@router.get('/disconnect/workspaces')
def disconnect_workspaces(user: User=Depends(require_user),db: Session=Depends(get_db)):
    connection=github.connection_for(db,user)
    rows=list(db.scalars(select(Workspace).join(Project).where(
        Workspace.user_id==user.id,Project.user_id==user.id,Project.source_type=='github',
        Project.github_installation_id==connection.installation_id,
        Workspace.status.notin_(['cache_expiring','cache_expired'])).order_by(Workspace.id).limit(101)))
    if len(rows)>100:raise HTTPException(409,'Review working copies in smaller groups before disconnecting')
    copies=[]
    for row in rows:
        try:
            state,snapshot,ignored=_copy_snapshot(row)
            copies.append({'id':str(row.id),'name':row.project.name,'repository':row.project.repository,
                'branch':row.project.remote_branch,'head':state['head'],'snapshot':snapshot,
                'changes':state['changes'],'ahead':state.get('ahead'),
                'blocked': 'Ignored files, local branches or stashes need review before deletion' if ignored else None})
        except HTTPException:
            copies.append({'id':str(row.id),'name':row.project.name,'repository':row.project.repository,
                'branch':row.project.remote_branch,'snapshot':None,'changes':[],
                'blocked':'Working copy needs review; disconnect can preserve it'})
    return JSONResponse({'connection_id':str(connection.id),'workspaces':copies,'retention_hours':73},
                        headers={'Cache-Control':'private, no-store'})


class CopyDecision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    connection_id: uuid.UUID
    snapshot: str = Field(pattern=r'^[0-9a-f]{64}$')
    action: str = Field(pattern=r'^(save|delete)$')


@router.post('/disconnect/workspaces/{workspace_id}')
def disconnect_copy(workspace_id: uuid.UUID,body: CopyDecision,
                    user: User=Depends(require_user),db: Session=Depends(get_db)):
    from ..services import workspaces,opencode,workspace_cache
    from . import workspaces as git_routes
    row,connection=_disconnect_copy(db,user,workspace_id)
    if connection.id!=body.connection_id:raise HTTPException(409,'Connection changed; review again')
    with opencode.workspace_lock(row):
        github.lock_owner(db,user)
        row,connection=_disconnect_copy(db,user,workspace_id)
        if connection.id!=body.connection_id:raise HTTPException(409,'Connection changed; review again')
        git_routes._require_git_idle(db,row)
        if not workspace_cache.runtime_idle(row):raise HTTPException(409,'Stop Native execution before saving or deleting files')
        state,snapshot,ignored=_copy_snapshot(row)
        if snapshot!=body.snapshot:raise HTTPException(409,'Working files changed; review again. Nothing deleted')
        if ignored:raise HTTPException(409,'Ignored files, local branches or stashes are not saved; export or review them first')
        if body.action=='save':
            # Reuse the existing authenticated Git implementation and its
            # non-force push plus remote verification. Never embed tokens in URLs.
            if not state['clean']:git_routes.commit(workspace_id,git_routes.CommitRequest(message='Save workspace before GitHub disconnect'),user,db)
            pushed=git_routes.push(workspace_id,user,db)
            current,new_snapshot,_=_copy_snapshot(row)
            if not current['clean'] or current['head']!=pushed['head']:
                raise HTTPException(409,'Files changed during save; nothing deleted')
            return {'saved':True,'verified':True,'head':current['head'],'snapshot':new_snapshot}
        # Even a forged direct delete request needs a fresh server-side remote
        # match, clean files, current connection, ownership and idle execution.
        git_routes._github_remote(db,user,row.project)
        if not state['clean'] or not state['head'] or not github.verify_remote_commit(
            connection,row.project.repository,row.project.remote_branch,state['head']):
            raise HTTPException(409,'Save and verify all changes on GitHub before deleting this copy')
        checked,latest,ignored=_copy_snapshot(row)
        if latest!=snapshot or not checked['clean'] or ignored or not workspace_cache.runtime_idle(row):
            raise HTTPException(409,'Workspace changed during verification; files preserved')
        root=workspaces.root_for(row)
        row.status='cache_expiring'
        db.add(AccountAudit(subject_id=user.id,action='github.copy_delete_verified:'+str(row.id)))
        db.commit()  # File access barrier survives a failed filesystem operation.
        try:
            shutil.rmtree(root)
        except OSError:
            raise HTTPException(503,'Verified copy cleanup failed; metadata and remote remain intact') from None
        row.status='cache_expired'
        db.flush()
        remaining=db.scalar(select(Workspace.id).where(Workspace.project_id==row.project_id,
            Workspace.user_id==user.id,Workspace.status.notin_(['cache_expiring','cache_expired'])).limit(1))
        if remaining is None:row.project.archived_at=datetime.now(timezone.utc)
        db.commit()
        return {'deleted':True,'head':state['head'],'remote_preserved':True,'history_preserved':True}

@router.get("/repositories")
def repositories(user: User = Depends(require_user), db: Session = Depends(get_db)):
    connection = github.connection_for(db, user)
    return JSONResponse(github.list_repositories(connection),
                        headers={"Cache-Control": "private, no-store"})

@router.get("/branches")
def branches(repository: str, user: User = Depends(require_user), db: Session = Depends(get_db)):
    if not repository.count("/") == 1:
        raise HTTPException(422, "A repository in owner/name form is required")
    connection = github.connection_for(db, user)
    return github.list_branches(connection, repository)

@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("x-hub-signature-256")
    if not github.verify_webhook(body, signature):
        raise HTTPException(401, "Invalid webhook signature")
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(422, "Invalid webhook payload")
    github.handle_webhook(db, request.headers.get("x-github-event", ""), payload)
    return {"received": True}
