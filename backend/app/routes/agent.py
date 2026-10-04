"""Local agent execution and durable Gateway event replay.

Runtime model access is a separate prerequisite. No synthetic execution progress.
"""
import asyncio, json, re, uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database import get_db, SessionLocal
from ..models import User, Workspace, WorkspaceSession, ExecutionEvent
from ..services import workspaces, opencode
from .dependencies import require_user

router=APIRouter(prefix="/api/sessions",tags=["agent"])
tasks={}

class MessageRequest(BaseModel):
    text: str=Field(min_length=1,max_length=20000)
    provider_id: str=Field(min_length=1,max_length=120,pattern=r"^[A-Za-z0-9_.-]+$")
    model_id: str=Field(min_length=1,max_length=200)

class Approval(BaseModel):
    reply: str=Field(pattern="^(once|reject)$")

def context(db,user,session_id):
    session=workspaces.owned(db,WorkspaceSession,session_id,user.id)
    workspace=workspaces.owned(db,Workspace,session.workspace_id,user.id)
    return session,workspace

def event(db,session_id,kind,data=None):
    db.add(ExecutionEvent(session_id=session_id,kind=kind,data=json.dumps(data or {})))
    db.commit()

async def execute(session_id,service,runtime_id,data):
    try:
        response=await asyncio.to_thread(service.request,"POST",service.session_path(runtime_id,"/message"),{"parts":[{"type":"text","text":data.text}],"model":{"providerID":data.provider_id,"modelID":data.model_id}},600)
        failure=bool(response.get("info",{}).get("error")) if isinstance(response,dict) else True
        with SessionLocal() as db:
            session=db.get(WorkspaceSession,session_id)
            if session and session.status!="cancelled":
                session.status="failed" if failure else "completed"
                event(db,session.id,session.status)
    except Exception:
        with SessionLocal() as db:
            session=db.get(WorkspaceSession,session_id)
            if session and session.status!="cancelled":
                session.status="failed"; event(db,session.id,"failed",{"reason":"Runtime request failed or timed out; inspect session before retrying"})
    finally:
        tasks.pop(str(session_id),None)

@router.post("/{session_id}/messages",status_code=202)
async def send(session_id: uuid.UUID,data: MessageRequest,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    if str(session_id) in tasks or session.status in {"submitted","waiting_approval"}:
        raise HTTPException(409,"Session already has an active or interrupted request; stop or review it first")
    # One mutating agent at a time per workspace to protect shared files.
    busy=db.scalar(select(WorkspaceSession).where(WorkspaceSession.workspace_id==workspace.id,WorkspaceSession.status.in_(["submitted","waiting_approval"])))
    if busy: raise HTTPException(409,"Another session is using this workspace")
    service=await asyncio.to_thread(opencode.for_workspace,workspace)
    provider_data=await asyncio.to_thread(service.request,"GET","/provider")
    if data.provider_id not in provider_data.get("connected",[]):
        raise HTTPException(503,"Provider authentication is not configured in this workspace runtime")
    provider=next((p for p in provider_data.get("all",[]) if p["id"]==data.provider_id),{})
    if data.model_id not in provider.get("models",{}): raise HTTPException(422,"Model is unavailable")
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
        text=text.replace(str(workspaces.root_for(workspace)),"[workspace]")
        text=re.sub(r"(?:gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,})","[redacted]",text)
        output.append({"role":item.get("info",{}).get("role"),"text":text})
    return output

@router.post("/{session_id}/stop")
def stop(session_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    service=opencode.for_workspace(workspace)
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
