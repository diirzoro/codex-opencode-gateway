"""Environment-scoped ownership gate. Nginx, never Python, transports native messages/SSE."""
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
from ..security.origins import same_origin
from ..database import get_db
from ..models import User, Workspace, WorkspaceSession, Project
from ..services import workspaces, session_lifecycle, policy
from ..services.entitlements import access_payload
from .dependencies import require_user

router=APIRouter(tags=['native-test'])
ID=r'[A-Za-z0-9_-]{1,120}'
_metadata_request=ContextVar('native_metadata_request',default=None)

def _native_ports():
    """Loopback metadata proxy origins (discovery, session).

    TEST/LIVE stay fixed on the VPS Nginx 18097/18098. LOCAL uses configurable
    origins because Windows can reserve those ports; both remain loopback-only.
    """
    from urllib.parse import urlparse
    if deployment()=='local':
        discovery=os.getenv('OPENCODE_NATIVE_LOCAL_DISCOVERY_URL','http://127.0.0.1:19097').rstrip('/')
        session=os.getenv('OPENCODE_NATIVE_LOCAL_SESSION_URL','http://127.0.0.1:19098').rstrip('/')
        for label,value in (('OPENCODE_NATIVE_LOCAL_DISCOVERY_URL',discovery),('OPENCODE_NATIVE_LOCAL_SESSION_URL',session)):
            parsed=urlparse(value)
            try:
                valid_port=parsed.port is None or 1<=parsed.port<=65535
            except ValueError:
                valid_port=False
            if (parsed.scheme!='http' or parsed.hostname not in {'127.0.0.1','localhost','::1'}
                or parsed.username is not None or parsed.password is not None
                or parsed.path or parsed.query or parsed.fragment or not valid_port):
                raise RuntimeError(label+' must be a loopback HTTP origin without credentials')
        return discovery,session
    return 'http://127.0.0.1:18097','http://127.0.0.1:18098'


def deployment():
    """Select one exact deployment boundary; a wrong environment fails closed.

    TEST retains its original opt-in flag. LIVE needs its own deliberate opt-in;
    LOCAL is a loopback-only development transport (same Nginx 18097/18098 +
    X-Accel layout as TEST) to a locally running `opencode serve`. Neither the
    public Host header nor a browser flag selects the environment.
    """
    truth={'1','true','yes'}
    test=os.getenv('OPENCODE_NATIVE_TEST_ENABLED','').lower() in truth
    live=os.getenv('OPENCODE_NATIVE_LIVE_ENABLED','').lower() in truth
    local=os.getenv('OPENCODE_NATIVE_LOCAL_ENABLED','').lower() in truth
    if sum((test,live,local))>1:
        raise RuntimeError('Native TEST, LIVE and LOCAL are mutually exclusive in one Gateway')
    if not (test or live or local):return None
    if local:
        return 'local'
    environment='test' if test else 'live'
    expected_origin=('https://test.opencode-gateway.codes' if test else 'https://opencode-gateway.codes')
    expected_db='opencode_gateway_test' if test else 'opencode_gateway'
    actual_db=settings.database_url.rsplit('/',1)[-1].split('?',1)[0]
    if settings.public_base_url.rstrip('/')!=expected_origin or actual_db!=expected_db:
        raise RuntimeError('Native deployment origin/database mismatch; nothing was forwarded')
    if live and settings.runtime_mode!='disabled':
        raise RuntimeError('LIVE Native requires the legacy per-workspace runtime disabled')
    return environment

def enabled():return deployment() is not None

def admit(user):
    if not enabled():raise HTTPException(503,'Native transport is not enabled')

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

def native_restrictions_persisted(session, expected):
    """Match OpenCode's documented PATCH merge semantics.

    Native appends newly supplied session permission rules to existing rules,
    rather than replacing the whole array. Permission evaluation uses the
    LAST matching rule. A full expected suffix overrides earlier rules while
    preserving path-specific denies and file grants. NEVER accept an arbitrary
    subset or only a successful PATCH response.
    """
    if not isinstance(session,dict):return False
    stored=session.get('permission')
    if not isinstance(stored,list) or len(stored)<len(expected):return False
    if not expected:return not stored
    return stored[-len(expected):]==expected


def confirm_native_session_restrictions(session_id,root,expected):
    """Verify Native's persisted session policy, not a possibly stale PATCH reply.

    This is metadata validation only. Actual prompts/responses go direct through
    Nginx to the existing shared Native instance. A non-persisting Native
    implementation must refuse execution; never bypass tenant restrictions.
    """
    metadata('PATCH','/session/'+session_id,root,{'permission':expected})
    confirmed=metadata('GET','/session/'+session_id,root)
    if (not isinstance(confirmed,dict) or confirmed.get('id')!=session_id
        or confirmed.get('directory')!=str(root)
        or not native_restrictions_persisted(confirmed,expected)):
        raise HTTPException(503,'Native session did not persist required tool restrictions; prompt not forwarded')
    return confirmed


@router.post('/api/native-test/sessions/{session_id}/permissions/{permission_id}/remember')
def remember_file_permission(session_id:uuid.UUID,permission_id:str,request:Request,user:User=Depends(require_user),db:Session=Depends(get_db)):
    if not same_origin(request.headers.get('origin'),settings.public_base_url):raise HTTPException(403,'Native writes require the Gateway origin')
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
        discovery_base,session_base=_native_ports()
        response=client.request(method,(discovery_base if discovery else session_base)+path,
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
    mode={'test':'authenticated-development-test','live':'authenticated-native-live','local':'authenticated-native-local'}[deployment()]
    payload={'enabled':True,'mode':mode,'version':'1.19.4','public_multi_user_ready':False}
    if deployment()=='local':
        from ..services.native_provider_accounts import root
        payload['native_account_directory']=str(root(user))
    return payload

@router.api_route('/api/native-test/workspaces/{workspace_id}/sessions',methods=['GET','POST'])
def sessions(workspace_id:uuid.UUID,request:Request,data:Create|None=None,user:User=Depends(require_user),db:Session=Depends(get_db)):
    workspace,root,_,_=context(db,user,workspace_id)
    # ONE project = ONE conversation = ONE persistent Native session.
    # A workspace has exactly one active session; legacy extra sessions are
    # preserved in the database but never exposed or re-created.
    live_list=metadata('GET','/session',root)
    live_index={r['id']:r for r in (live_list if isinstance(live_list,list) else [])
                if isinstance(r,dict) and r.get('directory')==str(root)}
    rows=list(db.scalars(select(WorkspaceSession).where(
        WorkspaceSession.user_id==user.id,WorkspaceSession.workspace_id==workspace.id)
        .order_by(WorkspaceSession.created_at.desc())))
    primary=None
    for row in rows:
        if row.opencode_session_id not in live_index:continue
        if session_lifecycle.state(db,row)=='deleted':continue
        primary=row;break
    if request.method=='POST':
        if not same_origin(request.headers.get('origin'),settings.public_base_url):raise HTTPException(403,'Native writes require the Gateway origin')
        if not access_payload(db,user)['allowed']:raise HTTPException(402,'Workspace access has expired')
        if primary is not None:
            lifecycle=session_lifecycle.state(db,primary)
            return {**session_lifecycle.payload(primary,lifecycle),'runtime_id':primary.opencode_session_id,
                    'native':True,'file_base':root.as_uri()+'/','tool_access':workspace._native_tool_access}
        workspaces.require_quota_headroom(workspace,db)
        permissions=policy.native_session_permissions(policy.load(db),root)
        title=str(getattr(workspace,'project',None) and workspace.project.name or (data or Create()).title).strip()[:120]
        live=metadata('POST','/session',root,{'title':title,'permission':permissions})
        if not isinstance(live,dict) or not re.fullmatch('ses'+ID,str(live.get('id',''))) or not isinstance(live.get('title'),str) or live.get('directory')!=str(root):raise HTTPException(502,'Invalid native session metadata')
        row=WorkspaceSession(id=uuid.uuid4(),user_id=user.id,workspace_id=workspace.id,opencode_session_id=live['id'],title=title or live['title'][:120],status='idle')
        db.add(row);db.flush();session_lifecycle.set_state(db,row,'active');db.commit()
        return {**session_lifecycle.payload(row,'active'),'runtime_id':live['id'],'native':True,'file_base':root.as_uri()+'/','tool_access':workspace._native_tool_access}
    if primary is None:
        db.commit();return []
    lifecycle=session_lifecycle.state(db,primary)
    primary.title=str(live_index[primary.opencode_session_id].get('title',primary.title))[:120]
    db.commit()
    return [{**session_lifecycle.payload(primary,lifecycle),'runtime_id':primary.opencode_session_id,'native':True,'file_base':root.as_uri()+'/'}]

@router.get('/api/native-test/sessions/{session_id}')
def session(session_id:uuid.UUID,user:User=Depends(require_user),db:Session=Depends(get_db)):
    admit(user);row=workspaces.owned(db,WorkspaceSession,session_id,user.id)
    workspace,root,row,live=context(db,user,row.workspace_id,session_id)
    return {**session_lifecycle.payload(row,session_lifecycle.state(db,row)),'runtime_id':row.opencode_session_id,'native':True,'file_base':root.as_uri()+'/','model':live.get('model'),'agent':live.get('agent'),'tool_access':workspace._native_tool_access}

@router.patch('/api/native-test/sessions/{session_id}')
def rename(session_id:uuid.UUID,data:Create,request:Request,user:User=Depends(require_user),db:Session=Depends(get_db)):
    if not same_origin(request.headers.get('origin'),settings.public_base_url):raise HTTPException(403,'Native writes require the Gateway origin')
    admit(user);row=workspaces.owned(db,WorkspaceSession,session_id,user.id)
    _,root,row,_=context(db,user,row.workspace_id,session_id)
    live=metadata('PATCH','/session/'+row.opencode_session_id,root,{'title':data.title})
    row.title=str(live.get('title',data.title))[:120];db.commit()
    return session_lifecycle.payload(row,session_lifecycle.state(db,row))

@router.post('/api/native-test/sessions/{session_id}/visibility/{action}')
def visibility(session_id:uuid.UUID,action:str,request:Request,user:User=Depends(require_user),db:Session=Depends(get_db)):
    if not same_origin(request.headers.get('origin'),settings.public_base_url):raise HTTPException(403,'Native writes require the Gateway origin')
    admit(user);row=workspaces.owned(db,WorkspaceSession,session_id,user.id)
    _,root,row,_=context(db,user,row.workspace_id,session_id)
    value={'close':'closed','archive':'archived','restore':'closed','reopen':'active','delete':'deleted'}.get(action)
    if not value:raise HTTPException(404,'Unsupported history action')
    live=metadata('GET','/session/status',root)
    if value in {'closed','archived','deleted'} and live.get(row.opencode_session_id,{}).get('type','idle')!='idle':raise HTTPException(409,'Stop native execution before hiding this conversation')
    session_lifecycle.set_state(db,row,value);db.commit()
    return session_lifecycle.payload(row,value)

# Native prompt/message/SSE/tools/todo/questions/permissions/files transport REMOVED.
# These operations now go Browser -> Nginx -> OpenCode Native directly (no Python).
# Session LIST/CREATE/metadata remain here via /api/native-test/* (Platform-owned).
