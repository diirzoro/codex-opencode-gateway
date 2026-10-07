"""Local agent execution and durable Gateway event replay.

Runtime model access is a separate prerequisite. No synthetic execution progress.
"""
import asyncio, json, re, uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from ..database import get_db, SessionLocal
from ..models import User, Workspace, WorkspaceSession, ExecutionEvent
from ..services import workspaces, opencode, policy
from .dependencies import require_user, require_workspace_entitlement

router=APIRouter(prefix="/api/sessions",tags=["agent"],dependencies=[Depends(require_workspace_entitlement)])
tasks={}

_SECRET_RE = re.compile(r"(?:sk-[A-Za-z0-9_-]{16,}|sk-ant-[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})")

def _sanitize(text, workspace):
    text=str(text).replace(str(workspaces.root_for(workspace)),"[workspace]")
    return _SECRET_RE.sub("[redacted]",text)

def normalize_states(parts):
    """Map real OpenCode tool parts to Gateway execution states (order preserving)."""
    states=[]
    for part in parts or []:
        if not isinstance(part,dict) or part.get("type")!="tool": continue
        tool=str(part.get("tool") or "").lower()
        if tool in {"read","list","glob","grep","webfetch","fetch","ls"}: state="reading_files"
        elif tool in {"edit","write","patch","multiedit","apply_patch"}: state="editing"
        elif tool in {"bash","shell"}:
            state_obj=part.get("state") or {}
            inp=state_obj.get("input") if isinstance(state_obj,dict) else {}
            command=str((inp or {}).get("command","")) if isinstance(inp,dict) else ""
            state="running_tests" if re.search(r"\b(test|pytest|jest|vitest|go test|cargo test|npm test|yarn test|pnpm test)\b",command,re.I) else "running_command"
        else: state="analyzing"
        if not states or states[-1]!=state: states.append(state)
    return states

class MessageRequest(BaseModel):
    text: str=Field(min_length=1,max_length=20000)
    provider_id: str=Field(min_length=1,max_length=120,pattern=r"^[A-Za-z0-9_.-]+$")
    model_id: str=Field(min_length=1,max_length=200)
    agent_id: str|None=Field(default=None,min_length=1,max_length=120)

class Approval(BaseModel):
    reply: str=Field(pattern="^(once|reject)$")

def context(db,user,session_id):
    session=workspaces.owned(db,WorkspaceSession,session_id,user.id)
    workspace=workspaces.owned(db,Workspace,session.workspace_id,user.id)
    return session,workspace

def event(db,session_id,kind,data=None):
    db.add(ExecutionEvent(session_id=session_id,kind=kind,data=json.dumps(data or {})))
    db.commit()

def finish_execution(db,session_id,kind,states=(),data=None):
    # Abort and the background HTTP response can finish concurrently. Evaluate
    # cancellation in the database, not on a previously loaded ORM snapshot.
    changed=db.execute(update(WorkspaceSession).where(
        WorkspaceSession.id==session_id,WorkspaceSession.status!='cancelled'
    ).values(status=kind).execution_options(synchronize_session=False)).rowcount
    if changed:
        for state in states:
            db.add(ExecutionEvent(session_id=session_id,kind=state,data='{}'))
        db.add(ExecutionEvent(session_id=session_id,kind=kind,data=json.dumps(data or {})))
    db.commit()

async def execute(session_id,service,runtime_id,data):
    try:
        with SessionLocal() as db:
            session=db.get(WorkspaceSession,session_id)
            if session and session.status!="cancelled": event(db,session.id,"analyzing")
        payload={"parts":[{"type":"text","text":data.text}],"model":{"providerID":data.provider_id,"modelID":data.model_id}}
        if data.agent_id: payload["agent"]=data.agent_id
        response=await asyncio.to_thread(service.request,"POST",service.session_path(runtime_id,"/message"),payload,600)
        info=response.get("info",{}) if isinstance(response,dict) else {}
        failure=info.get("role")!="assistant" or bool(info.get("error")) or not info.get("time",{}).get("completed")
        with SessionLocal() as db:
            if failure:
                error=info.get("error") if isinstance(info.get("error"),dict) else {}
                error_name=str(error.get("name") or "")
                error_data=error.get("data") if isinstance(error.get("data"),dict) else {}
                error_msg=str(error_data.get("message") or error.get("message") or "")
                detail=(": "+error_name+(" - "+error_msg if error_msg else "")).strip(" :") if (error_name or error_msg) else ""
                finish_execution(db,session_id,'failed',data={'reason':'OpenCode reported an agent error. Review the session before retrying.'+detail[:400]})
            else:
                finish_execution(db,session_id,'completed',normalize_states(response.get('parts',[])))
    except Exception:
        with SessionLocal() as db:
            finish_execution(db,session_id,'failed',data={'reason':'Runtime request failed or timed out; inspect session before retrying'})
    finally:
        tasks.pop(str(session_id),None)

@router.post("/{session_id}/messages",status_code=202)
async def send(session_id: uuid.UUID,data: MessageRequest,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    from ..services import workspaces as manager
    manager.require_quota_headroom(workspace)
    if str(session_id) in tasks or session.status in {"submitted","waiting_approval"}:
        raise HTTPException(409,"Session already has an active or interrupted request; stop or review it first")
    # One mutating agent at a time per workspace to protect shared files.
    busy=db.scalar(select(WorkspaceSession).where(WorkspaceSession.workspace_id==workspace.id,WorkspaceSession.status.in_(["submitted","waiting_approval"])))
    if busy: raise HTTPException(409,"Another session is using this workspace")
    policy_row=policy.load(db)
    if not policy.provider_allowed(policy_row,data.provider_id):
        raise HTTPException(403,"Provider is disabled by platform policy")
    if not policy.model_allowed(policy_row,data.model_id):
        raise HTTPException(403,"Model is disabled by platform policy")
    service=await asyncio.to_thread(opencode.for_workspace,workspace)
    # Self-heal orphaned runtime sessions (for example after a runtime restart):
    # when the stored runtime session no longer exists, create a fresh one for the same files.
    try:
        probe=await asyncio.to_thread(service.request,"GET",service.session_path(session.opencode_session_id))
    except HTTPException:
        probe=None
    if not isinstance(probe,dict) or probe.get("id")!=session.opencode_session_id:
        new_runtime_id=await asyncio.to_thread(service.create_session,session.title)
        session.opencode_session_id=new_runtime_id; db.commit()
    if data.agent_id:
        from .workspaces import agent_choices
        agents=await asyncio.to_thread(agent_choices,service)
        if data.agent_id not in {a["id"] for a in agents}: raise HTTPException(422,"Agent is unavailable")
    provider_data=await asyncio.to_thread(service.request,"GET","/provider")
    if data.provider_id not in provider_data.get("connected",[]):
        raise HTTPException(503,"Provider authentication is not configured in this workspace runtime")
    provider=next((p for p in provider_data.get("all",[]) if p["id"]==data.provider_id),{})
    if data.model_id not in provider.get("models",{}): raise HTTPException(422,"Model is unavailable")
    # Refresh session-level rules too: legacy session overrides and later admin
    # policy changes must not broaden the runtime's current tool restrictions.
    await asyncio.to_thread(service.apply_session_policy,session.opencode_session_id,
                            policy.session_permissions(policy_row))
    session.status="submitted"; event(db,session.id,"submitted")
    tasks[str(session_id)]=asyncio.create_task(execute(session.id,service,session.opencode_session_id,data))
    return {"status":"submitted","session_id":str(session.id)}

@router.get("/{session_id}/messages")
def messages(session_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    service=opencode.for_workspace(workspace)
    result=service.request("GET",service.session_path(session.opencode_session_id,"/message"))
    output=[]
    for item in result:
        text="\n".join(p.get("text","") for p in item.get("parts",[]) if p.get("type")=="text")[:50000]
        output.append({"role":item.get("info",{}).get("role"),"text":_sanitize(text,workspace)})
    return output

@router.get("/{session_id}/diff")
def session_diff(session_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    service=opencode.for_workspace(workspace)
    rows=service.request("GET",service.session_path(session.opencode_session_id,"/diff"))
    output=[]
    for item in rows or []:
        patch=_sanitize(item.get("patch",""),workspace)
        output.append({"file":item.get("file"),"status":item.get("status"),"additions":item.get("additions"),"deletions":item.get("deletions"),"patch":patch[:200000]})
    return output

@router.post("/{session_id}/stop")
def stop(session_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    service=opencode.for_workspace(workspace,start=False)
    if service.request("POST",service.session_path(session.opencode_session_id,"/abort")) is not True:
        raise HTTPException(502,"Runtime did not confirm cancellation")
    session.status="cancelled"; event(db,session.id,"cancelled")
    return {"status":"cancelled"}

@router.get("/{session_id}/permissions")
def permissions(session_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    rows=opencode.for_workspace(workspace).request("GET","/permission")
    owned=[]
    for pending in rows:
        if pending.get("sessionID")!=session.opencode_session_id:
            continue
        patterns=pending.get("patterns",[])
        reviewable=isinstance(patterns,list) and 0<len(patterns)<=20 and all(isinstance(p,str) and 0<len(p)<=4000 for p in patterns)
        # Never offer blind approval or approve a truncated command/pattern.
        details=[p.replace(str(workspaces.root_for(workspace)),"[workspace]") for p in patterns] if reviewable else []
        owned.append({"id":pending["id"],"permission":pending.get("permission"),"patterns":details,"reviewable":reviewable})
    if owned and session.status=="submitted":
        session.status="waiting_approval"; event(db,session.id,"waiting_approval")
    return owned

@router.post("/{session_id}/permissions/{permission_id}")
def approve(session_id: uuid.UUID,permission_id: str,data: Approval,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    pending=permissions(session_id,user,db)
    if permission_id not in {p["id"] for p in pending}: raise HTTPException(404,"Permission request not found")
    if data.reply=="once" and not next(p["reviewable"] for p in pending if p["id"]==permission_id):
        raise HTTPException(409,"Permission details cannot be fully reviewed; deny this request")
    requested=next(p for p in pending if p["id"]==permission_id)
    _,_,allowed_tools=policy.provider_sets(policy.load(db))
    if data.reply=="once" and (requested["permission"]=="external_directory" or
                               (allowed_tools and requested["permission"] not in allowed_tools)):
        raise HTTPException(403,"This permission is disabled by platform policy")
    from urllib.parse import quote
    result=opencode.for_workspace(workspace).request("POST","/permission/"+quote(permission_id,safe="")+"/reply",{"reply":data.reply})
    if result is not True: raise HTTPException(502,"Runtime did not confirm the decision")
    session.status="submitted"; event(db,session.id,"approval_decision",{"reply":data.reply})
    return {"accepted":True}

@router.get("/{session_id}/events")
async def events(session_id: uuid.UUID,request: Request,after: int=0,last_event_id: str|None=Header(default=None),user: User=Depends(require_user),db: Session=Depends(get_db)):
    context(db,user,session_id)
    try: cursor=max(0,int(last_event_id) if last_event_id is not None else after)
    except ValueError: raise HTTPException(422,"Invalid event ID")
    async def stream():
        nonlocal cursor
        while not await request.is_disconnected():
            # Revalidate current cookie on each polling cycle (revocation/expiry).
            with SessionLocal() as current:
                try:
                    current_user=require_user(request,current)
                    context(current,current_user,session_id)
                except HTTPException:
                    return
                rows=list(current.scalars(select(ExecutionEvent).where(ExecutionEvent.session_id==session_id,ExecutionEvent.id>cursor).order_by(ExecutionEvent.id).limit(100)))
                for row in rows:
                    cursor=row.id
                    yield f"id: {row.id}\nevent: {row.kind}\ndata: {row.data}\n\n"
            yield ": keepalive\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(stream(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})
