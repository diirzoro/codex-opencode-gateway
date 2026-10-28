"""Session-bound GitHub connection, callback bridge and explicit identity confirmation."""
import html
import logging
import secrets
import uuid
from pydantic import BaseModel, Field, ConfigDict
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import User
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
    if not state or len(state)>64 or (code and len(code)>1024):
        return RedirectResponse(settings.public_base_url+'/?github=error',303)
    fields={'state':state,'code':code,'installation_id':installation_id,
            'setup_action':setup_action,'error':error}
    inputs=''.join('<input type="hidden" name="'+k+'" value="'+html.escape(str(v),quote=True)+'">'
                   for k,v in fields.items() if v is not None)
    nonce=secrets.token_urlsafe(20)
    page='<!doctype html><html><head><meta charset="utf-8"><meta name="referrer" content="no-referrer"><title>GitHub connection</title></head><body><p>Completing GitHub authorization / استكمال تفويض GitHub</p><form id="complete" method="post" action="/api/github/callback/complete">'+inputs+'<button type="submit">Continue / متابعة</button></form><script nonce="'+nonce+'">history.replaceState(null,\'\',\'/api/github/callback\');document.getElementById(\'complete\').submit();</script></body></html>'
    return HTMLResponse(page,headers={'Cache-Control':'private, no-store','Referrer-Policy':'no-referrer',
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

@router.post('/confirm')
def confirm(body: ConfirmationBody,request: Request,user: User=Depends(require_user),db: Session=Depends(get_db)):
    return JSONResponse(github.confirm_connection(db,user,request.state.auth_session.id,
        body.connection_id,body.github_user_id,body.installation_id),headers={'Cache-Control':'private, no-store'})

@router.post('/pending/install')
def pending_install(body: PendingBody,request: Request,user: User=Depends(require_user),db: Session=Depends(get_db)):
    return JSONResponse({'url':github.pending_installation(db,user,request.state.auth_session.id,body.connection_id)},
                        headers={'Cache-Control':'private, no-store'})

@router.post('/disconnect')
def disconnect(user: User=Depends(require_user),db: Session=Depends(get_db)):
    return JSONResponse(github.disconnect(db,user,remove_installation=True),headers={'Cache-Control':'private, no-store'})

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
