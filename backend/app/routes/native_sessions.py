"""TEST-only ownership gate. Nginx, never Python, transports native messages/SSE."""
import os
import re
import uuid
from pathlib import Path
from urllib.parse import urlencode
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import User, Workspace, WorkspaceSession, Project
from ..services import workspaces, session_lifecycle
from ..services.entitlements import access_payload
from .dependencies import require_user

router=APIRouter(tags=['native-test'])
ID=r'[A-Za-z0-9_-]{1,120}'

def enabled():return os.getenv('OPENCODE_NATIVE_TEST_ENABLED','').lower() in {'1','true','yes'}

def admit(user):
    if not enabled():raise HTTPException(503,'Native TEST transport is not enabled')
    if settings.public_base_url.rstrip('/')!='https://test.opencode-gateway.codes' or settings.database_url.rsplit('/',1)[-1].split('?',1)[0]!='opencode_gateway_test':
        raise HTTPException(503,'Native transport requires the TEST deployment')
    if str(user.id)!=os.getenv('OPENCODE_NATIVE_TEST_OWNER_ID',''):
        raise HTTPException(403,'Shared native execution is limited to the TEST owner')

def context(db,user,workspace_id,session_id=None):
    admit(user)
    workspace=workspaces.owned(db,Workspace,workspace_id,user.id)
    project=workspaces.owned(db,Project,workspace.project_id,user.id)
    if project.archived_at is not None:raise HTTPException(409,'Restore the project before native execution')
    root=workspaces.root_for(workspace)
    if not root.is_dir():raise HTTPException(409,'Workspace files are unavailable; records were preserved')
    row=None;live=None
    if session_id is not None:
        row=workspaces.owned(db,WorkspaceSession,session_id,user.id)
        if row.workspace_id!=workspace.id:raise HTTPException(404,'Conversation is outside this Workspace')
        session_lifecycle.require_visible(db,row)
        live=metadata('GET','/session/'+row.opencode_session_id,root)
        if live.get('id')!=row.opencode_session_id or live.get('directory')!=str(root):
            raise HTTPException(409,'Native conversation requires an owned directory mapping')
    return workspace,root,row,live

def metadata(method,path,root,data=None):
    # Only ownership/session metadata. No prompts, model responses or events.
    if not ((path=='/session' and method in {'GET','POST'}) or method=='GET' and re.fullmatch(r'/session/'+ID,path) or path in {'/permission','/question'} and method=='GET'):
        raise HTTPException(403,'Unsupported metadata operation')
    try:
        with httpx.Client(base_url='http://127.0.0.1:18098',trust_env=False,timeout=15) as client:
            response=client.request(method,path,params={'directory':str(root)},json=data)
            response.raise_for_status()
            if not response.headers.get('content-type','').startswith('application/json') or len(response.content)>4*1024*1024:raise ValueError()
            return response.json()
    except (httpx.HTTPError,ValueError):raise HTTPException(502,'Native session metadata is unavailable') from None

class Create(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title:str=Field(default='New session',min_length=1,max_length=120)

@router.get('/api/native-test/state')
def state(user:User=Depends(require_user)):
    if not enabled():return {'enabled':False}
    admit(user)
    return {'enabled':True,'mode':'single-owner-test','version':'1.18.32'}

@router.api_route('/api/native-test/workspaces/{workspace_id}/sessions',methods=['GET','POST'])
def sessions(workspace_id:uuid.UUID,request:Request,data:Create|None=None,user:User=Depends(require_user),db:Session=Depends(get_db)):
    workspace,root,_,_=context(db,user,workspace_id)
    if request.method=='POST':
        if request.headers.get('origin')!=settings.public_base_url.rstrip('/'):raise HTTPException(403,'Native writes require the Gateway origin')
        if not access_payload(db,user)['allowed']:raise HTTPException(402,'Workspace access has expired')
        workspaces.require_quota_headroom(workspace)
        live=metadata('POST','/session',root,{'title':(data or Create()).title,'permission':[{'permission':'external_directory','pattern':'*','action':'deny'}]})
        if not isinstance(live,dict) or not re.fullmatch('ses'+ID,str(live.get('id',''))) or not isinstance(live.get('title'),str) or live.get('directory')!=str(root):raise HTTPException(502,'Invalid native session metadata')
        row=WorkspaceSession(id=uuid.uuid4(),user_id=user.id,workspace_id=workspace.id,opencode_session_id=live['id'],title=live['title'][:120],status='idle')
        db.add(row);db.flush();session_lifecycle.set_state(db,row,'active');db.commit()
        return {**session_lifecycle.payload(row,'active'),'runtime_id':live['id'],'native':True,'file_base':root.as_uri()+'/'}
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
    return {**session_lifecycle.payload(row,session_lifecycle.state(db,row)),'runtime_id':row.opencode_session_id,'native':True,'file_base':root.as_uri()+'/','model':live.get('model'),'agent':live.get('agent')}

@router.api_route('/native-session/{workspace_id}/{resource:path}',methods=['GET','POST'])
async def transport(workspace_id:uuid.UUID,resource:str,request:Request,user:User=Depends(require_user),db:Session=Depends(get_db)):
    admit(user)
    raw=bytearray()
    if request.method=='POST':
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw)>2*1024*1024:raise HTTPException(413,'Native request is too large')
    return await run_in_threadpool(authorize_native,workspace_id,resource,request,user,db,bytes(raw))

def authorize_native(workspace_id,resource,request,user,db,raw):
    if request.query_params:raise HTTPException(403,'Caller routing parameters are not allowed')
    write=request.method=='POST'
    if write and request.headers.get('origin')!=settings.public_base_url.rstrip('/'):raise HTTPException(403,'Native writes require the Gateway origin')
    workspace,root,_,_=context(db,user,workspace_id)
    discovery=request.method=='GET' and resource in {'provider','agent'}
    match=re.fullmatch(r'session/('+ID+r')(?:/(message|todo|diff|prompt_async|abort))?',resource)
    if resource=='session/status':match=None
    if not discovery and resource not in {'event','permission','question','session/status'} and not match and not re.fullmatch(r'(permission|question)/'+ID+r'/(reply|reject)',resource):
        raise HTTPException(403,'Unsupported native route')
    if match:
        row=db.scalar(select(WorkspaceSession).where(WorkspaceSession.workspace_id==workspace.id,WorkspaceSession.user_id==user.id,WorkspaceSession.opencode_session_id==match.group(1)))
        if row is None:raise HTTPException(404,'Conversation is not owned')
        context(db,user,workspace_id,row.id)
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
        context(db,user,workspace_id,row.id)
    if write:
        if raw and request.headers.get('content-type','').split(';')[0]!='application/json':raise HTTPException(415,'Native writes require JSON')
        if not resource.endswith(('/abort','/reject')) and not access_payload(db,user)['allowed']:raise HTTPException(402,'Workspace access has expired')
        if match and match.group(2)=='prompt_async':
            import json
            try:body=json.loads(raw)
            except (ValueError,UnicodeError):raise HTTPException(400,'Invalid native JSON') from None
            # Native schema validates models, variants and agents. Only file URIs
            # need Gateway ownership validation before tools may read them.
            if not isinstance(body,dict) or not isinstance(body.get('parts'),list) or any(not isinstance(p,dict) for p in body['parts']):raise HTTPException(422,'Invalid native prompt parts')
            for part in body['parts']:
                if part.get('type')=='file':
                    from urllib.parse import urlsplit,unquote
                    uri=urlsplit(str(part.get('url','')))
                    if uri.scheme!='file' or uri.netloc or uri.query or uri.fragment:raise HTTPException(403,'Only owned uploaded files are supported')
                    try:relative=Path(unquote(uri.path)).relative_to(root).as_posix()
                    except ValueError:raise HTTPException(403,'Attachment is outside this Workspace') from None
                    if not workspaces.safe_path(workspace,relative).is_file():raise HTTPException(403,'Attachment is unavailable')
            workspaces.require_quota_headroom(workspace)
    query=urlencode({'directory':str(root)})
    return Response(headers={'X-Accel-Redirect':'@native_discovery_test' if discovery else '@native_session_test','X-Native-URI':'/'+resource+'?'+query,'Cache-Control':'no-store'})
