"""TEST-only ownership gate. Nginx, never Python, transports native messages/SSE."""
import os
import re
import uuid
import json
import time
from contextvars import ContextVar
from pathlib import Path
from urllib.parse import urlencode
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, JSONResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import User, Workspace, WorkspaceSession, Project
from ..services import workspaces, session_lifecycle, policy
from ..services.entitlements import access_payload
from .dependencies import require_user

router=APIRouter(tags=['native-test'])
ID=r'[A-Za-z0-9_-]{1,120}'
_metadata_request=ContextVar('native_metadata_request',default=None)

def enabled():return os.getenv('OPENCODE_NATIVE_TEST_ENABLED','').lower() in {'1','true','yes'}

def admit(user):
    if not enabled():raise HTTPException(503,'Native TEST transport is not enabled')
    if settings.public_base_url.rstrip('/')!='https://test.opencode-gateway.codes' or settings.database_url.rsplit('/',1)[-1].split('?',1)[0]!='opencode_gateway_test':
        raise HTTPException(503,'Native transport requires the TEST deployment')

def context(db,user,workspace_id,session_id=None):
    admit(user)
    workspace=workspaces.owned(db,Workspace,workspace_id,user.id)
    project=workspaces.owned(db,Project,workspace.project_id,user.id)
    if project.archived_at is not None:raise HTTPException(409,'Restore the project before native execution')
    workspace._native_tool_access=tool_access(db,user,workspace,project=project)
    root=workspaces.root_for(workspace)
    if not root.is_dir():raise HTTPException(409,'Workspace files are unavailable; records were preserved')
    # Imported repositories may contain Native plugins/MCP/agent configuration.
    # Do not initialize that executable configuration in the shared process.
    # Preserve it for operator review instead of changing/deleting project files.
    base=settings.workspace_root.resolve()
    for directory in (root,*root.parents):
        if any((directory/name).exists() or (directory/name).is_symlink() for name in ('.opencode','opencode.json','opencode.jsonc')):
            raise HTTPException(409,'Project Native configuration requires operator review; all files were preserved')
        if directory==base:break
    row=None;live=None
    if session_id is not None:
        row=workspaces.owned(db,WorkspaceSession,session_id,user.id)
        live=owned_native_session(db,user,workspace,root,row)
    return workspace,root,row,live

def owned_native_session(db,user,workspace,root,row):
    # Reuse only the ownership/root checks performed earlier in THIS request.
    # No cross-request authorization cache: role, policy and mapping stay live.
    if row.user_id!=user.id or row.workspace_id!=workspace.id or workspace.user_id!=user.id:
        raise HTTPException(404,'Conversation is outside this Workspace')
    session_lifecycle.require_visible(db,row)
    live=metadata('GET','/session/'+row.opencode_session_id,root)
    if not isinstance(live,dict):raise HTTPException(502,'Invalid native conversation metadata')
    if live.get('id')!=row.opencode_session_id or live.get('directory')!=str(root):
        raise HTTPException(409,'Native conversation requires an owned directory mapping')
    return live

def tool_access(db,user,workspace,*,project=None):
    project=project if project is not None else workspaces.owned(db,Project,workspace.project_id,user.id)
    # The schema has account admin/owner roles and project ownership, no
    # independent Project Manager membership. Ownership alone is not Shell rights.
    manager=user.role in {'admin','owner'} and project.user_id==user.id
    return {'project_manager':manager,'shell_authorized':manager,'shell_enabled':False,
            'shell_blocker':'project_execution_boundary_unverified' if manager else 'project_manager_required'}

def file_grants(workspace,root,rules,location=None):
    """Validate exact Native path rules, never browser patterns or `always` '*'."""
    if not rules:return []
    location=location if location is not None else metadata('GET','/path',root)
    if not isinstance(location,dict) or location.get('directory')!=str(root):raise HTTPException(503,'Native file context is unavailable')
    worktree=Path(location.get('worktree',''))
    if not worktree.is_absolute() or not root.is_relative_to(worktree):raise HTTPException(503,'Native worktree is unavailable')
    result=[]
    for rule in rules:
        name,pattern=rule.get('permission'),rule.get('pattern')
        if name not in policy.NATIVE_FILE_TOOLS or not isinstance(pattern,str) or not pattern or len(pattern)>1000 or re.search(r'[\x00-\x1f\x7f*?\\]',pattern):raise HTTPException(403,'Only exact owned file permissions can be remembered')
        path=Path(pattern);absolute=path if path.is_absolute() else worktree/path
        try:relative=absolute.relative_to(root).as_posix()
        except ValueError:raise HTTPException(403,'Permission is outside this Workspace') from None
        if relative=='.' or any(p.startswith('.env') or p in {'.opencode','opencode.json','opencode.jsonc','.aws','.config','auth.json','credentials.json'} or p.endswith(('.pem','.key')) for p in Path(relative).parts):raise HTTPException(403,'Protected files cannot be remembered')
        target=workspaces.safe_path(workspace,relative)
        if target.is_dir():raise HTTPException(403,'Directory-wide permissions cannot be remembered')
        candidate={'permission':name,'pattern':pattern,'action':'allow'}
        if candidate not in result:result.append(candidate)
    return result

def session_permissions(db,workspace,root,live,location=None):
    candidates=[r for r in live.get('permission',[]) if isinstance(r,dict) and r.get('action')=='allow' and r.get('permission') in policy.NATIVE_FILE_TOOLS]
    grants=[]
    if candidates and location is None:location=metadata('GET','/path',root)
    # Revalidate each remembered path on every new prompt; invalid/stale grants
    # disappear, while other valid file decisions stay in Native storage.
    for candidate in candidates:
        try:grants.extend(file_grants(workspace,root,[candidate],location))
        except HTTPException as error:
            if error.status_code!=403:raise
    return policy.native_session_permissions(policy.load(db),root,grants)

def confirm_native_session_restrictions(session_id,root,expected):
    """Verify Native's persisted session policy, not a possibly stale PATCH reply.

    This is metadata validation only. Actual prompts/responses go direct through
    Nginx to the existing shared Native instance. A non-persisting Native
    implementation must refuse execution; never bypass tenant restrictions.
    """
    metadata('PATCH','/session/'+session_id,root,{'permission':expected})
    confirmed=metadata('GET','/session/'+session_id,root)
    if (not isinstance(confirmed,dict) or confirmed.get('id')!=session_id
        or confirmed.get('directory')!=str(root) or confirmed.get('permission')!=expected):
        raise HTTPException(503,'Native session did not persist required tool restrictions; prompt not forwarded')
    return confirmed


@router.post('/api/native-test/sessions/{session_id}/permissions/{permission_id}/remember')
def remember_file_permission(session_id:uuid.UUID,permission_id:str,request:Request,user:User=Depends(require_user),db:Session=Depends(get_db)):
    if request.headers.get('origin')!=settings.public_base_url.rstrip('/'):raise HTTPException(403,'Native writes require the Gateway origin')
    admit(user);row=workspaces.owned(db,WorkspaceSession,session_id,user.id)
    workspace,root,_,_=context(db,user,row.workspace_id)
    session_lifecycle.lock_workspace(db,workspace)
    _,_,_,live=context(db,user,row.workspace_id,session_id)
    if not access_payload(db,user)['allowed']:raise HTTPException(402,'Workspace access has expired')
    pending=metadata('GET','/permission',root)
    item=next((r for r in pending if r.get('id')==permission_id and r.get('sessionID')==row.opencode_session_id),None) if isinstance(pending,list) else None
    if item is None:raise HTTPException(404,'Native request is not owned')
    allowed=policy.provider_sets(policy.load(db))[2]
    if item.get('permission') not in policy.NATIVE_FILE_TOOLS or allowed and item['permission'] not in allowed:raise HTTPException(403,'This permission cannot be remembered')
    patterns=item.get('patterns')
    if not isinstance(patterns,list) or not 1<=len(patterns)<=20:raise HTTPException(403,'Exact file paths are required')
    location=metadata('GET','/path',root)
    additions=file_grants(workspace,root,[{'permission':item['permission'],'pattern':p} for p in patterns],location)
    existing=session_permissions(db,workspace,root,live,location)
    grants=[r for r in existing if r['action']=='allow' and r['permission'] in policy.NATIVE_FILE_TOOLS]
    grants=[r for r in grants if r not in additions]+additions
    if len(grants)>100:raise HTTPException(409,'Conversation file permission limit reached; use Allow once')
    permissions=policy.native_session_permissions(policy.load(db),root,grants)
    confirm_native_session_restrictions(row.opencode_session_id,root,permissions)
    db.commit()
    # The pending tool is still answered through the original Native once flow.
    # 1.19.4 captures policy at run start: the saved rule takes effect NEXT run.
    return {'remembered':True,'scope':'next-prompts-in-this-conversation'}

def metadata(method,path,root,data=None):
    # Only ownership/session metadata. No prompts, model responses or events.
    discovery=path in {'/provider','/agent'} and method=='GET'
    auth=(method in {'PUT','DELETE'} and re.fullmatch(r'/auth/'+ID,path)) or (method=='POST' and re.fullmatch(r'/provider/'+ID+r'/oauth/(authorize|callback)',path)) or (method=='GET' and path=='/provider/auth') or (method=='DELETE' and re.fullmatch(r'/session/'+ID,path))
    if not (discovery or auth or (path=='/session' and method in {'GET','POST'}) or method in {'GET','PATCH'} and re.fullmatch(r'/session/'+ID,path) or path in {'/permission','/question','/session/status','/global/health','/experimental/tool/ids','/skill','/path'} and method=='GET'):
        raise HTTPException(403,'Unsupported metadata operation')
    state=_metadata_request.get()
    remaining=15 if state is None else state['deadline']-time.monotonic()
    if remaining<=0:raise HTTPException(504,'Native authorization timed out before forwarding')
    temporary=state is None
    client=None
    try:
        if temporary:
            client=httpx.Client(trust_env=False,timeout=15)
        else:
            if state['client'] is None:state['client']=httpx.Client(trust_env=False,timeout=15)
            client=state['client']
        response=client.request(method,'http://127.0.0.1:'+('18097' if discovery else '18098')+path,
                                params={'directory':str(root)},json=data,timeout=min(15,remaining))
        response.raise_for_status()
        if not response.headers.get('content-type','').startswith('application/json') or len(response.content)>(16 if path=='/provider' else 4)*1024*1024:raise ValueError()
        return response.json()
    except (httpx.HTTPError,ValueError):raise HTTPException(502,'Native session metadata is unavailable') from None
    finally:
        if temporary and client is not None:client.close()


# Retention runs inside the existing Gateway maintenance loop, not an AI/chat
# engine, task queue, or parallel OpenCode storage. The only conversation
# deletion is the installed Native DELETE /session/{id} endpoint.
NATIVE_HISTORY_IDLE_TTL = 24 * 3600
_native_history_cursor = None


def _native_history_timestamp(live):
    """Fail closed on malformed Native time; milliseconds are Native format."""
    from datetime import datetime, timezone
    stamp=live.get('time',{}).get('updated') if isinstance(live.get('time'),dict) else None
    if type(stamp) not in (int,float) or not 1_000_000_000_000 <= stamp <= 4_000_000_000_000:
        return None
    try:return datetime.fromtimestamp(stamp/1000,timezone.utc)
    except (ValueError,OverflowError,OSError):return None


def sweep_expired_native_history(*, now=None):
    """Delete >24h inactive owned conversations through Native's own API.

    Gateway keeps its security mappings and bookkeeping only. Never delete an
    active/unknown Native session, a foreign session, or a project file. Existing
    maintenance calls this conservatively and can retry after Native errors.
    """
    if not enabled():return {'deleted':0,'skipped':0}
    from datetime import datetime,timedelta,timezone
    from sqlalchemy import delete
    from ..database import SessionLocal
    from ..models import ExecutionEvent
    from ..services import chat_attachments, workspace_cache
    global _native_history_cursor
    now = now or datetime.now(timezone.utc)
    cutoff=now-timedelta(seconds=NATIVE_HISTORY_IDLE_TTL)
    deleted=0;skipped=0
    with SessionLocal() as db:
        query=select(WorkspaceSession.id).where(WorkspaceSession.created_at<=cutoff).order_by(WorkspaceSession.id).limit(25)
        if _native_history_cursor is not None:
            query=query.where(WorkspaceSession.id>_native_history_cursor)
        candidates=list(db.scalars(query))
        if not candidates:
            _native_history_cursor=None
            return {'deleted':0,'skipped':0}
        _native_history_cursor=candidates[-1]
        for identifier in candidates:
            try:
                row=db.scalar(select(WorkspaceSession).where(WorkspaceSession.id==identifier).with_for_update(skip_locked=True).execution_options(populate_existing=True))
                if not row or row.status in session_lifecycle.BUSY:
                    skipped+=1;db.rollback();continue
                user=db.get(User,row.user_id)
                if user is None:skipped+=1;db.rollback();continue
                workspace,root,_,_=context(db,user,row.workspace_id)
                if workspace.id!=row.workspace_id or not workspace_cache.runtime_idle(workspace):
                    skipped+=1;db.rollback();continue
                live=metadata('GET','/session/'+row.opencode_session_id,root)
                if not isinstance(live,dict) or live.get('id')!=row.opencode_session_id or live.get('directory')!=str(root):
                    skipped+=1;db.rollback();continue
                updated=_native_history_timestamp(live)
                if updated is None or updated>cutoff:
                    skipped+=1;db.rollback();continue
                # Gateway receipts/visibility also count as user activity.
                latest=db.scalar(select(ExecutionEvent.created_at).where(ExecutionEvent.session_id==row.id).order_by(ExecutionEvent.created_at.desc()).limit(1))
                if latest is not None and (latest if latest.tzinfo else latest.replace(tzinfo=timezone.utc))>cutoff:
                    skipped+=1;db.rollback();continue
                # Recheck that Native has not started execution before removal.
                if not workspace_cache.runtime_idle(workspace):
                    skipped+=1;db.rollback();continue
                outcome=metadata('DELETE','/session/'+row.opencode_session_id,root)
                if outcome is not True:
                    skipped+=1;db.rollback();continue
                # Native has removed the session and messages. Only now remove
                # the temporary uploads belonging to this exact conversation.
                chat_attachments.clear_native_deleted_session(workspace,row.id)
                db.execute(delete(ExecutionEvent).where(ExecutionEvent.session_id==row.id))
                db.delete(row)
                db.commit()
                deleted+=1
            except (HTTPException,OSError,ValueError,TypeError,KeyError,httpx.HTTPError):
                db.rollback();skipped+=1
    return {'deleted':deleted,'skipped':skipped}


class Create(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title:str=Field(default='New session',min_length=1,max_length=120)

@router.get('/api/native-test/state')
def state(user:User=Depends(require_user)):
    if not enabled():return {'enabled':False}
    admit(user)
    return {'enabled':True,'mode':'authenticated-development-test','version':'1.19.4','public_multi_user_ready':False}

@router.api_route('/api/native-test/workspaces/{workspace_id}/sessions',methods=['GET','POST'])
def sessions(workspace_id:uuid.UUID,request:Request,data:Create|None=None,user:User=Depends(require_user),db:Session=Depends(get_db)):
    workspace,root,_,_=context(db,user,workspace_id)
    if request.method=='POST':
        if request.headers.get('origin')!=settings.public_base_url.rstrip('/'):raise HTTPException(403,'Native writes require the Gateway origin')
        if not access_payload(db,user)['allowed']:raise HTTPException(402,'Workspace access has expired')
        workspaces.require_quota_headroom(workspace)
        permissions=policy.native_session_permissions(policy.load(db),root)
        live=metadata('POST','/session',root,{'title':(data or Create()).title,'permission':permissions})
        if not isinstance(live,dict) or not re.fullmatch('ses'+ID,str(live.get('id',''))) or not isinstance(live.get('title'),str) or live.get('directory')!=str(root):raise HTTPException(502,'Invalid native session metadata')
        row=WorkspaceSession(id=uuid.uuid4(),user_id=user.id,workspace_id=workspace.id,opencode_session_id=live['id'],title=live['title'][:120],status='idle')
        db.add(row);db.flush();session_lifecycle.set_state(db,row,'active');db.commit()
        return {**session_lifecycle.payload(row,'active'),'runtime_id':live['id'],'native':True,'file_base':root.as_uri()+'/','tool_access':workspace._native_tool_access}
    live=metadata('GET','/session',root)
    if not isinstance(live,list):raise HTTPException(502,'Invalid native session list')
    # Never adopt arbitrary IDs from the shared engine. Existing map is authority.
    index={r['id']:r for r in live if isinstance(r,dict) and r.get('directory')==str(root)}
    rows=db.scalars(select(WorkspaceSession).where(WorkspaceSession.user_id==user.id,WorkspaceSession.workspace_id==workspace.id))
    result=[]
    for row in rows:
        if row.opencode_session_id not in index:continue
        lifecycle=session_lifecycle.state(db,row)
        if lifecycle=='deleted':continue
        row.title=str(index[row.opencode_session_id].get('title',row.title))[:120]
        result.append({**session_lifecycle.payload(row,lifecycle),'runtime_id':row.opencode_session_id,'native':True,'file_base':root.as_uri()+'/'})
    db.commit();return result

@router.get('/api/native-test/sessions/{session_id}')
def session(session_id:uuid.UUID,user:User=Depends(require_user),db:Session=Depends(get_db)):
    admit(user);row=workspaces.owned(db,WorkspaceSession,session_id,user.id)
    workspace,root,row,live=context(db,user,row.workspace_id,session_id)
    return {**session_lifecycle.payload(row,session_lifecycle.state(db,row)),'runtime_id':row.opencode_session_id,'native':True,'file_base':root.as_uri()+'/','model':live.get('model'),'agent':live.get('agent'),'tool_access':workspace._native_tool_access}

@router.patch('/api/native-test/sessions/{session_id}')
def rename(session_id:uuid.UUID,data:Create,request:Request,user:User=Depends(require_user),db:Session=Depends(get_db)):
    if request.headers.get('origin')!=settings.public_base_url.rstrip('/'):raise HTTPException(403,'Native writes require the Gateway origin')
    admit(user);row=workspaces.owned(db,WorkspaceSession,session_id,user.id)
    _,root,row,_=context(db,user,row.workspace_id,session_id)
    live=metadata('PATCH','/session/'+row.opencode_session_id,root,{'title':data.title})
    row.title=str(live.get('title',data.title))[:120];db.commit()
    return session_lifecycle.payload(row,session_lifecycle.state(db,row))

@router.post('/api/native-test/sessions/{session_id}/visibility/{action}')
def visibility(session_id:uuid.UUID,action:str,request:Request,user:User=Depends(require_user),db:Session=Depends(get_db)):
    if request.headers.get('origin')!=settings.public_base_url.rstrip('/'):raise HTTPException(403,'Native writes require the Gateway origin')
    admit(user);row=workspaces.owned(db,WorkspaceSession,session_id,user.id)
    _,root,row,_=context(db,user,row.workspace_id,session_id)
    value={'close':'closed','archive':'archived','restore':'closed','reopen':'active','delete':'deleted'}.get(action)
    if not value:raise HTTPException(404,'Unsupported history action')
    live=metadata('GET','/session/status',root)
    if value in {'closed','archived','deleted'} and live.get(row.opencode_session_id,{}).get('type','idle')!='idle':raise HTTPException(409,'Stop native execution before hiding this conversation')
    session_lifecycle.set_state(db,row,value);db.commit()
    return session_lifecycle.payload(row,value)

@router.api_route('/native-session/{workspace_id}/{resource:path}',methods=['GET','POST'])
async def transport(workspace_id:uuid.UUID,resource:str,request:Request,user:User=Depends(require_user),db:Session=Depends(get_db)):
    try:
        admit(user)
        raw=bytearray()
        if request.method=='POST':
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw)>2*1024*1024:raise HTTPException(413,'Native request is too large')
        response=await run_in_threadpool(authorize_native,workspace_id,resource,request,user,db,bytes(raw))
        if request.method=='POST' and await request.is_disconnected():
            raise HTTPException(408,'Native request cancelled before forwarding')
        return response
    except HTTPException as error:
        # No X-Accel response has been returned to Nginx yet. Unlike an
        # upstream timeout, this rejection proves the prompt was not sent.
        # Preserve the real status/detail and never mark forwarded responses.
        error.headers={**(error.headers or {}),'X-Native-Request-Outcome':'not-forwarded'}
        raise

def authorize_native(workspace_id,resource,request,user,db,raw):
    # Reuse an HTTP connection only within this authorization, never cache a
    # permission/provider/session decision across requests. Budget is shorter
    # than the browser prompt receipt timeout, including checks after metadata.
    state={'deadline':time.monotonic()+(5 if resource.endswith('/abort') else 20),'client':None}
    token=_metadata_request.set(state)
    try:
        response=_authorize_native(workspace_id,resource,request,user,db,raw)
        if time.monotonic()>=state['deadline']:
            raise HTTPException(504,'Native authorization timed out before forwarding')
        import logging
        logging.getLogger(__name__).debug('Native authorization allowed')
        return response
    except HTTPException as error:
        import logging
        logging.getLogger(__name__).info('Native authorization refused status=%d',error.status_code)
        raise
    finally:
        try:
            if state['client'] is not None:state['client'].close()
        finally:_metadata_request.reset(token)


def _authorize_native(workspace_id,resource,request,user,db,raw):
    if any(k.lower() in {'x-native-uri','x-accel-redirect','x-opencode-directory','x-native-upstream'} for k in request.headers):raise HTTPException(403,'Caller routing headers are not allowed')
    if request.query_params:raise HTTPException(403,'Caller routing parameters are not allowed')
    write=request.method=='POST'
    if write and request.headers.get('origin')!=settings.public_base_url.rstrip('/'):raise HTTPException(403,'Native writes require the Gateway origin')
    workspace,root,_,_=context(db,user,workspace_id)
    discovery=request.method=='GET' and resource in {'provider','agent'}
    if discovery:
        # Provider definitions contain an optional plaintext key and options.
        # This is management metadata, not an AI response. Never transport it
        # verbatim to a browser, even through an authenticated Nginx redirect.
        if resource=='provider':
            from ..services.native_provider_accounts import catalog
            data=catalog(db,user,root)
        else:
            data=[{k:r[k] for k in ('name','mode','hidden','description') if k in r} for r in metadata('GET','/agent',root) if isinstance(r,dict)]
        return JSONResponse(data,headers={'Cache-Control':'no-store'})
    match=re.fullmatch(r'session/('+ID+r')(?:/(message|todo|diff|prompt_async|abort))?',resource)
    if resource=='session/status':match=None
    if not discovery and resource not in {'event','permission','question','session/status'} and not match and not re.fullmatch(r'(permission|question)/'+ID+r'/(reply|reject)',resource):
        raise HTTPException(403,'Unsupported native route')
    if match:
        row=db.scalar(select(WorkspaceSession).where(WorkspaceSession.workspace_id==workspace.id,WorkspaceSession.user_id==user.id,WorkspaceSession.opencode_session_id==match.group(1)))
        if row is None:raise HTTPException(404,'Conversation is not owned')
        session_live=owned_native_session(db,user,workspace,root,row)
        if write and match.group(2) not in {'prompt_async','abort'}:raise HTTPException(403,'Unsupported native write')
        if not write and match.group(2) in {'prompt_async','abort'}:raise HTTPException(403,'Unsupported native method')
    elif write:
        action=re.fullmatch(r'(permission|question)/('+ID+r')/(reply|reject)',resource)
        if action and action.group(1)=='permission' and action.group(3)!='reply':raise HTTPException(403,'Unsupported permission operation')
        if not action:raise HTTPException(403,'Unsupported native write')
        items=metadata('GET','/'+action.group(1),root)
        if not isinstance(items,list):raise HTTPException(502,'Invalid native request metadata')
        item=next((i for i in items if i.get('id')==action.group(2)),None)
        row=None if item is None else db.scalar(select(WorkspaceSession).where(WorkspaceSession.user_id==user.id,WorkspaceSession.workspace_id==workspace.id,WorkspaceSession.opencode_session_id==item.get('sessionID')))
        if row is None:raise HTTPException(404,'Native request is not owned')
        owned_native_session(db,user,workspace,root,row)
    if write:
        if raw and request.headers.get('content-type','').split(';')[0]!='application/json':raise HTTPException(415,'Native writes require JSON')
        if not resource.endswith(('/abort','/reject')) and not access_payload(db,user)['allowed']:raise HTTPException(402,'Workspace access has expired')
        if not match:
            try:body=json.loads(raw or b'{}')
            except (ValueError,UnicodeError):raise HTTPException(400,'Invalid native JSON') from None
            if not isinstance(body,dict):raise HTTPException(422,'Invalid native reply')
            if action.group(1)=='permission':
                if set(body)!={'reply'} or body['reply'] not in {'once','reject'}:raise HTTPException(422,'Only one-time approval or rejection is allowed')
                if body['reply']!='reject':
                    if item.get('permission') not in policy.NATIVE_REVIEW_TOOLS:raise HTTPException(403,'This execution capability is prohibited; it cannot be approved')
                    allowed=policy.provider_sets(policy.load(db))[2]
                    if allowed and item['permission'] not in allowed:raise HTTPException(403,'Tool disabled by policy')
                    # Validate native file-permission patterns too; an old pending
                    # request must not authorize a foreign file or a symlink.
                    if item['permission'] in {'read','edit','write','apply_patch','glob','grep','list'}:
                        location=metadata('GET','/path',root)
                        if not isinstance(location,dict) or location.get('directory')!=str(root) or not isinstance(location.get('worktree'),str):raise HTTPException(503,'Native file-permission context is unavailable')
                        worktree=Path(location['worktree'])
                        if not worktree.is_absolute() or not root.is_relative_to(worktree):raise HTTPException(403,'Native file-permission context is outside this Workspace')
                        # Native read/edit patterns are relative to worktree,
                        # which is '/' for a non-Git project, NOT to directory.
                        # Search metadata.path, conversely, is directory-relative.
                        search=item['permission'] in {'glob','grep','list'}
                        patterns=([item.get('metadata',{}).get('path') or str(root)] if item['permission'] in {'glob','grep','list'} else item.get('patterns',[]))
                        if not patterns:raise HTTPException(403,'File permission has no owned path')
                        for pattern in patterns:
                            try:
                                path=Path(pattern)
                                absolute=path if path.is_absolute() else (root if search else worktree)/path
                                relative=absolute.relative_to(root).as_posix()
                            except (TypeError,ValueError):raise HTTPException(403,'File permission is outside this Workspace') from None
                            if any(p in {'.opencode','opencode.json','opencode.jsonc'} or p.startswith('.env') for p in Path(relative).parts):raise HTTPException(403,'Runtime configuration and secrets are protected')
                            workspaces.safe_path(workspace,relative)
            elif action.group(3)=='reply':
                answers=body.get('answers')
                if set(body)!={'answers'} or not isinstance(answers,list) or len(answers)>30 or any(not isinstance(a,list) or not a or len(a)>50 or any(not isinstance(v,str) or not 1<=len(v)<=2000 for v in a) or len(set(a))!=len(a) for a in answers):raise HTTPException(422,'Invalid native question answers')
                if len(answers)!=len(item.get('questions',[])):raise HTTPException(422,'Answer every native question')
        if match and match.group(2)=='prompt_async':
            try:body=json.loads(raw)
            except (ValueError,UnicodeError):raise HTTPException(400,'Invalid native JSON') from None
            # Native schema validates models, variants and agents. Only file URIs
            # need Gateway ownership validation before tools may read them.
            if not isinstance(body,dict) or not isinstance(body.get('parts'),list) or any(not isinstance(p,dict) for p in body['parts']):raise HTTPException(422,'Invalid native prompt parts')
            if set(body)-{'messageID','model','agent','variant','parts'}:raise HTTPException(422,'Unsupported native prompt fields')
            if not 1<=len(body['parts'])<=25 or any(p.get('type') not in {'text','file'} for p in body['parts']):raise HTTPException(422,'Only text and owned attachments are supported')
            model=body.get('model')
            if not isinstance(model,dict) or set(model)!={'providerID','modelID'} or any(not isinstance(v,str) or not 1<=len(v)<=200 for v in model.values()):raise HTTPException(422,'Select a native provider and model')
            current_policy=policy.load(db)
            # PATCH the supported Native session permission field before any new
            # execution, including sessions created under the older ask-all rules.
            # Never alter a running session and pretend its old tools were revoked.
            permissions=session_permissions(db,workspace,root,session_live)
            if session_live.get('permission')!=permissions:
                statuses=metadata('GET','/session/status',root)
                if statuses.get(row.opencode_session_id,{}).get('type','idle')!='idle':raise HTTPException(409,'Stop this conversation before applying its new tool restrictions')
                # Native may return a stale/minimal PATCH acknowledgement. The
                # authoritative safety gate is a subsequent GET of the rules
                # actually stored by the SAME Native session. Never infer
                # success from HTTP 200/PATCH acknowledgement alone.
                confirm_native_session_restrictions(row.opencode_session_id,root,permissions)
            tools=metadata('GET','/experimental/tool/ids',root)
            builtins={'invalid','question','bash','shell','terminal','read','glob','grep','list','edit','write','task','webfetch','todowrite','todoread','websearch','codesearch','skill','apply_patch','execute','lsp','plan_enter','plan_exit'}
            if not isinstance(tools,list) or any(not isinstance(t,str) or t not in builtins for t in tools) or len(tools)!=len(set(tools)):raise HTTPException(503,'Custom Native tool execution requires verified restrictions; execution is blocked')
            if not policy.provider_allowed(current_policy,model['providerID']) or not policy.model_allowed(current_policy,model['modelID'],model['providerID']):raise HTTPException(403,'Model disabled by policy')
            from ..services.native_provider_accounts import require_model
            require_model(db,user,root,model['providerID'],model['modelID'])
            for part in body['parts']:
                if part.get('type')=='file':
                    from urllib.parse import urlsplit,unquote
                    uri=urlsplit(str(part.get('url','')))
                    if uri.scheme!='file' or uri.netloc or uri.query or uri.fragment:raise HTTPException(403,'Only owned uploaded files are supported')
                    try:relative=Path(unquote(uri.path)).relative_to(root).as_posix()
                    except ValueError:raise HTTPException(403,'Attachment is outside this Workspace') from None
                    if not workspaces.safe_path(workspace,relative).is_file():raise HTTPException(403,'Attachment is unavailable')
            workspaces.require_quota_headroom(workspace)
            # Lease only after every authorization check. Nginx still forwards
            # the original prompt; Gateway neither executes nor stores it.
            from ..services import chat_attachments
            for part in body['parts']:
                if part.get('type')=='file':
                    relative=Path(unquote(urlsplit(part['url']).path)).relative_to(root).as_posix()
                    chat_attachments.lease(workspace,row,relative,body.get('messageID'))
    query=urlencode({'directory':str(root)})
    return Response(headers={'X-Accel-Redirect':'@native_discovery_test' if discovery else '@native_session_test','X-Native-URI':'/'+resource+'?'+query,'Cache-Control':'no-store'})
