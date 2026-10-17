"""Local agent execution and durable Gateway event replay.

Runtime model access is a separate prerequisite. No synthetic execution progress.
"""
import asyncio, hashlib, json, re, shlex, time, uuid, mimetypes
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from ..database import get_db, SessionLocal
from ..models import User, Workspace, WorkspaceSession, ExecutionEvent, ProviderCredential, AccountAudit
from ..services import workspaces, opencode, policy, providers, session_lifecycle
from .dependencies import require_user, require_workspace_entitlement
from ..services.entitlements import require_advanced

router=APIRouter(prefix="/api/sessions",tags=["agent"],dependencies=[Depends(require_workspace_entitlement)])
tasks={}

EXECUTION_REPORTING = """Execution reporting for this Gateway conversation:
Follow the user's language, selected agent role, project instructions and all existing permissions.
For multi-step work, briefly describe each meaningful next step before tools, then report its actual result.
Use the native Todo tool for a real multi-step plan when available; update it from actual progress.
If a tool or test fails, explain the observed failure without exposing secrets, diagnose it, and attempt a
safe correction within the existing authorization. Rerun only affected checks after a relevant correction.
Never blindly repeat failed operations, bypass a rejection, or proceed past a pending approval/question.
Keep progress updates concise, user-facing and factual; do not disclose private reasoning or credentials.
Before finishing, provide a final report: changes completed, checks actually run and their outcomes,
errors fixed, unresolved issues, and blocked or unverified work. Distinguish a finished tool call from
completion of the entire request. Do not claim success, deployment or verification without evidence.
If you cannot continue safely, explain the blocker and what is needed, rather than inventing progress.
"""

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
        else: state="tool_activity"
        if not states or states[-1]!=state: states.append(state)
    return states

def command_activity_label(command):
    """Expose only exact, harmless command shapes; never arbitrary shell payloads."""
    if not isinstance(command,str) or len(command)>2000:return None
    executable=command.strip().split(' ',1)[0]
    try: argv=shlex.split(command)
    except ValueError:return None
    safe=False
    if argv and argv[0] in {'npm','pnpm','yarn','bun'}:
        args=argv[1:]
        scripts={'test','build','lint','check','typecheck','start','dev','compile','format'}
        safe=(len(args)==1 and args[0] in scripts) or (len(args)==2 and args[0]=='run' and args[1] in scripts)
    if argv in [['python','-m','pytest'],['python3','-m','pytest'],['pytest'],['pytest','-q'],['go','test','./...'],['cargo','test']]:safe=True
    if argv and argv[0]=='git' and argv[1:] in [['status'],['status','--short'],['diff','--stat'],['diff','--check'],['branch','--show-current']]:safe=True
    if safe:return ' '.join(argv)
    # This is explicitly labelled as a restricted summary, not the full command.
    if executable in {'npm','pnpm','yarn','pytest','python','python3','node','git','rg','ls','cat','go','cargo','bun','make'}:return executable
    return None


def safe_tool_activity(parts, workspace):
    """Allowlisted execution metadata; no reasoning, tool output or shell payloads."""
    output=[]
    if not any(isinstance(part,dict) and part.get('type')=='tool' for part in parts or []): return output
    root=workspaces.root_for(workspace).resolve()
    def filename(value):
        if not isinstance(value,str) or not value: return None
        try:
            path=Path(value)
            relative=(path if path.is_absolute() else root/path).resolve().relative_to(root)
        except (ValueError,OSError): return None
        if any(segment.startswith('.env') or segment.lower().endswith(('.key','.pem')) for segment in relative.parts): return '[private file]'
        return _sanitize(relative.as_posix(),workspace)[:500]
    for part in parts or []:
        if not isinstance(part,dict) or part.get('type')!='tool': continue
        tool=part.get('tool'); state=part.get('state')
        if not isinstance(tool,str) or not re.fullmatch(r'[\w.-]{1,120}',tool) or not isinstance(state,dict): continue
        status=state.get('status')
        if status not in {'pending','running','completed','error'}: continue
        item={'id':str(part.get('id') or part.get('callID') or '')[:160], 'tool':tool, 'status':status,
              'stage':normalize_states([part])[0]}
        inp=state.get('input') if isinstance(state.get('input'),dict) else {}
        files=[]
        if tool.lower() in {'read','edit','write','multiedit'}:
            path=filename(inp.get('filePath'))
            if path: files.append({'path':path,'operation':'inspected' if tool.lower()=='read' else 'changed'})
        metadata=state.get('metadata') if isinstance(state.get('metadata'),dict) else {}
        if tool.lower()=='apply_patch' and isinstance(metadata.get('files'),list):
            for entry in metadata['files'][:50]:
                if not isinstance(entry,dict): continue
                path=filename(entry.get('relativePath') or entry.get('filePath'))
                operation={'add':'created','update':'changed','delete':'deleted','move':'moved'}.get(entry.get('type'))
                if path and operation: files.append({'path':path,'operation':operation})
        if files: item['files']=files
        if tool.lower() in {'bash','shell'}:
            command=command_activity_label(inp.get('command'))
            if command:
                item['command']=command
                item['command_limited']=command!=str(inp.get('command','')).strip()
            exit_code=metadata.get('exit')
            if status in {'completed','error'} and type(exit_code) is int:
                item['exit_code']=exit_code
        times=state.get('time') if isinstance(state.get('time'),dict) else {}
        start,end=times.get('start'),times.get('end')
        if status in {'completed','error'} and type(start) is int and type(end) is int and end>=start:
            item['duration_ms']=end-start
        output.append(item)
    return output[:100]

def record_activity(session_id,request_id,activity):
    # DB work belongs to a worker, never the streaming event loop.
    with SessionLocal() as db:
        session=db.get(WorkspaceSession,session_id)
        if session is None or session.status=='cancelled':return False
        latest=db.scalar(select(ExecutionEvent).where(ExecutionEvent.session_id==session_id,ExecutionEvent.kind=='submission').order_by(ExecutionEvent.id.desc()).limit(1))
        if not latest or json.loads(latest.data)['request_id']!=str(request_id):return False
        event(db,session_id,'activity',activity)
        return True

async def monitor_activity(session_id,service,runtime_id,message_id,workspace,request_id,request_task):
    seen=set()
    while True:
        done,_=await asyncio.wait({request_task},timeout=2)
        try:
            rows=await asyncio.to_thread(service.request,'GET',service.session_path(runtime_id,'/message'),timeout=5)
            for row in rows:
                if row.get('info',{}).get('role')!='assistant' or row.get('info',{}).get('parentID')!=message_id: continue
                for activity in safe_tool_activity(row.get('parts',[]),workspace):
                    key=json.dumps(activity,sort_keys=True)
                    if key in seen: continue
                    if not await asyncio.to_thread(record_activity,session_id,request_id,activity):return
                    seen.add(key)
        except Exception:
            # Optional observation must never fail/retry the model submission.
            pass
        if done: return

class AttachmentRequest(BaseModel):
    path: str = Field(min_length=1, max_length=500)

def attachment_metadata(workspace, selected):
    rows=[];seen=set()
    for item in selected:
        path=workspaces.safe_path(workspace,item.path)
        if any(p.startswith('.env') or p.lower().endswith(('.pem','.key')) for p in Path(item.path).parts):
            raise HTTPException(403, 'Private files cannot be attached')
        if not path.is_file(): raise HTTPException(422, 'An attached workspace file is unavailable')
        relative=path.relative_to(workspaces.root_for(workspace)).as_posix()
        if relative in seen: continue
        seen.add(relative)
        mime=mimetypes.guess_type(relative)[0] or 'application/octet-stream'
        rows.append({'path':relative,'name':path.name,'size':path.stat().st_size,'mime':mime})
    return rows

class MessageRequest(BaseModel):
    request_id: uuid.UUID
    attachments: list[AttachmentRequest] = Field(default_factory=list, max_length=10)
    text: str=Field(min_length=1,max_length=20000)
    provider_id: str=Field(min_length=1,max_length=120,pattern=r"^[A-Za-z0-9_.-]+$")
    model_id: str=Field(min_length=1,max_length=200)
    agent_id: str|None=Field(default=None,min_length=1,max_length=120)

class Approval(BaseModel):
    reply: str=Field(pattern="^(once|similar|reject)$")

def context(db,user,session_id):
    session=workspaces.owned(db,WorkspaceSession,session_id,user.id)
    workspace=workspaces.owned(db,Workspace,session.workspace_id,user.id)
    session_lifecycle.require_visible(db,session)
    return session,workspace

@router.get("")
def client_sessions(include_archived: bool=False,user: User=Depends(require_user),db: Session=Depends(get_db)):
    # Client history must not start every workspace runtime just to list rows.
    rows=list(db.scalars(select(WorkspaceSession).join(Workspace,Workspace.id==WorkspaceSession.workspace_id).where(
        WorkspaceSession.user_id==user.id,Workspace.user_id==user.id).order_by(WorkspaceSession.created_at.desc())))
    values=session_lifecycle.states(db,rows)
    return [session_lifecycle.payload(row,values[row.id]) for row in rows
            if values[row.id]!="deleted" and (include_archived or values[row.id]!="archived")]

def event(db,session_id,kind,data=None):
    db.add(ExecutionEvent(session_id=session_id,kind=kind,data=json.dumps(data or {})))
    db.commit()

def finish_execution(db,session_id,kind,states=(),data=None,request_id=None,activities=()):
    # Abort and the background HTTP response can finish concurrently. Evaluate
    # cancellation in the database, not on a previously loaded ORM snapshot.
    current=db.scalar(select(WorkspaceSession).where(WorkspaceSession.id==session_id).with_for_update().execution_options(populate_existing=True))
    if current is None or current.status not in session_lifecycle.BUSY:
        db.rollback(); return
    latest=db.scalar(select(ExecutionEvent).where(ExecutionEvent.session_id==session_id,ExecutionEvent.kind=="submission").order_by(ExecutionEvent.id.desc()).limit(1))
    if request_id is not None and (not latest or json.loads(latest.data)["request_id"]!=str(request_id)):
        db.rollback(); return
    changed=db.execute(update(WorkspaceSession).where(
        WorkspaceSession.id==session_id,WorkspaceSession.status!='cancelled'
    ).values(status=kind).execution_options(synchronize_session=False)).rowcount
    if changed:
        from ..services.workspace_cache import touch
        touch(db, current.workspace_id, current.user_id)
        for activity in activities:
            db.add(ExecutionEvent(session_id=session_id,kind='activity',data=json.dumps(activity)))
        for state in states:
            db.add(ExecutionEvent(session_id=session_id,kind=state,data='{}'))
        db.add(ExecutionEvent(session_id=session_id,kind=kind,data=json.dumps(data or {})))
    db.commit()

def begin_execution(session_id,message_id,request_id,generation):
    with SessionLocal() as db:
        session=db.get(WorkspaceSession,session_id)
        if session is None:return None
        workspace=db.get(Workspace,session.workspace_id)
        session_lifecycle.lock_workspace(db,workspace);db.refresh(session)
        latest=db.scalar(select(ExecutionEvent).where(ExecutionEvent.session_id==session_id,ExecutionEvent.kind=="submission").order_by(ExecutionEvent.id.desc()).limit(1))
        if session.status not in session_lifecycle.BUSY or not latest or json.loads(latest.data)["request_id"]!=str(request_id):return None
        db.add(ExecutionEvent(session_id=session_id,kind="dispatch",data=json.dumps({"request_id":str(request_id),"message_id":message_id,"generation":generation})))
        event(db,session_id,"analyzing")
        return workspace


def complete_execution(session_id,kind,**kwargs):
    with SessionLocal() as db:finish_execution(db,session_id,kind,**kwargs)


async def execute(session_id,service,runtime_id,data,message_id):
    try:
        workspace=await asyncio.to_thread(begin_execution,session_id,message_id,data.request_id,service.generation)
        if workspace is None:return
        payload={"messageID":message_id,"system":EXECUTION_REPORTING,"parts":[{"type":"text","text":data.text}],"model":{"providerID":data.provider_id,"modelID":data.model_id}}
        for item in attachment_metadata(workspace, data.attachments):
            path=workspaces.safe_path(workspace,item['path'])
            # Native file parts for formats OpenCode consumes directly. Other
            # files remain explicit workspace paths for its file/tool context.
            if item['mime'] in {'text/plain','application/pdf','image/png','image/jpeg','image/webp','image/gif'}:
                payload['parts'].append({'type':'file','url':path.as_uri(),'filename':item['name'],'mime':item['mime']})
            else:
                payload['parts'].append({'type':'text','text':'Attached workspace file: '+json.dumps(item['path'])+'\nUse the selected agent’s available tools or skills to read this file. Verify that its contents can be extracted before answering about them. If no available tool can read this format, immediately explain that limitation and request a supported format. Do not infer contents from the filename or claim to have read an unreadable file.'})
        if data.agent_id: payload["agent"]=data.agent_id
        request_task=asyncio.create_task(asyncio.to_thread(service.request,"POST",service.session_path(runtime_id,"/message"),payload,600))
        observer=asyncio.create_task(monitor_activity(session_id,service,runtime_id,message_id,workspace,data.request_id,request_task))
        try:
            response=await request_task
        finally:
            observer.cancel()
            with suppress(asyncio.CancelledError): await observer
        info=response.get("info",{}) if isinstance(response,dict) else {}
        failure=info.get("role")!="assistant" or bool(info.get("error")) or not info.get("time",{}).get("completed")
        if failure:
            # Never relay raw provider errors or credentials.
            await asyncio.to_thread(complete_execution,session_id,'failed',data={'reason':'OpenCode reported an agent error. Review the session before retrying.'},request_id=data.request_id)
        else:
            await asyncio.to_thread(complete_execution,session_id,'completed',request_id=data.request_id,
                                    activities=safe_tool_activity(response.get('parts',[]),workspace))
    except Exception:
        await asyncio.to_thread(complete_execution,session_id,'failed',data={'reason':'Runtime request failed or timed out; inspect session before retrying'},request_id=data.request_id)
    finally:
        if tasks.get(str(session_id)) is asyncio.current_task(): tasks.pop(str(session_id),None)

@router.post("/{session_id}/messages",status_code=202)
async def send(session_id: uuid.UUID,data: MessageRequest,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    signature=data.model_dump(mode="json",exclude={"request_id"})
    # Empty attachments preserve pre-hotfix receipt fingerprints on browser retry.
    if not signature.get('attachments'): signature.pop('attachments',None)
    fingerprint=hashlib.sha256(json.dumps(signature,sort_keys=True).encode()).hexdigest()
    session_lifecycle.lock_workspace(db,workspace); db.refresh(session)
    saved=session_lifecycle.receipt(db,session_id,data.request_id)
    if saved:
        db.rollback()
        if saved["fingerprint"]!=fingerprint: raise HTTPException(409,"Submission ID belongs to a different message")
        return {**saved["receipt"],"replayed":True}
    if session_lifecycle.state(db,session)!="active": raise HTTPException(409,"Open this session before sending")
    session_lifecycle.require_slot(db,workspace,session.id)
    from ..services import workspaces as manager
    manager.require_quota_headroom(workspace)
    if session.status in {"submitted","waiting_approval"}:
        raise HTTPException(409,"Session already has an active or interrupted request; stop or review it first")
    # One mutating agent at a time per workspace to protect shared files.
    busy=db.scalar(select(WorkspaceSession).where(WorkspaceSession.workspace_id==workspace.id,WorkspaceSession.status.in_(["submitted","waiting_approval"])))
    if busy: raise HTTPException(409,"Another session is using this workspace")
    policy_row=policy.load(db)
    if not policy.provider_allowed(policy_row,data.provider_id):
        raise HTTPException(403,"Provider is disabled by platform policy")
    if not policy.model_allowed(policy_row,data.model_id):
        raise HTTPException(403,"Model is disabled by platform policy")
    if providers.is_locally_disconnected(db,workspace,data.provider_id):
        raise HTTPException(409,"Provider is disconnected in this workspace; explicitly reconnect it before sending")
    attached=attachment_metadata(workspace,data.attachments)
    receipt={"status":"submitted","session_id":str(session.id),"request_id":str(data.request_id)}
    message_id=session_lifecycle.new_message_id()
    session.status="submitted"
    workspace.last_activity_at=datetime.now(timezone.utc)
    db.add(ExecutionEvent(session_id=session.id,kind="submission",data=json.dumps({"request_id":str(data.request_id),"fingerprint":fingerprint,"message_id":message_id,"receipt":receipt,"attachments":attached,"text":_sanitize(data.text,workspace)})))
    event(db,session.id,"submitted",{"request_id":str(data.request_id)})
    # Admission is durable BEFORE asynchronous runtime/provider preflight. A
    # concurrent/replayed POST never creates a second task or OpenCode message.
    try:
        service=await asyncio.to_thread(opencode.for_workspace,workspace)
        # Never replace conversation history silently after a probe failure.
        probe=await asyncio.to_thread(service.request,"GET",service.session_path(session.opencode_session_id))
        if not isinstance(probe,dict) or probe.get("id")!=session.opencode_session_id:
            raise HTTPException(409,"OpenCode conversation is unavailable; close this session and start a new one")
        if data.agent_id:
            from .workspaces import agent_choices
            agents=await asyncio.to_thread(agent_choices,service)
            if data.agent_id not in {a["id"] for a in agents}: raise HTTPException(422,"Agent is unavailable")
        provider_data=await asyncio.to_thread(service.request,"GET","/provider")
        provider_data=providers.client_catalog(db,workspace,provider_data)
        if data.provider_id not in provider_data.get("connected",[]):
            raise HTTPException(503,"Provider authentication is not configured in this workspace runtime")
        provider=next((p for p in provider_data.get("all",[]) if p["id"]==data.provider_id),{})
        if data.model_id not in provider.get("models",{}): raise HTTPException(422,"Model is unavailable")
        # Availability remains OpenCode-owned; entitlement classifies actual use.
        model=provider['models'][data.model_id]
        inputs=(model.get('capabilities') or {}).get('input') or {}
        for item in attached:
            category='image' if item['mime'].startswith('image/') else 'pdf' if item['mime']=='application/pdf' else None
            if category and inputs.get(category) is False:
                raise HTTPException(422, 'The selected OpenCode model does not support this attachment type; select a compatible model')
        costs=model.get('cost') or {}
        free_model=costs.get('input')==0 and costs.get('output')==0
        own_key=db.scalar(select(ProviderCredential.id).where(ProviderCredential.workspace_id==workspace.id,
                         ProviderCredential.provider_id==data.provider_id)) is not None
        # OAuth has no Gateway API-key row; reuse its durable connection intent.
        client_binding=db.scalar(select(AccountAudit.id).where(AccountAudit.subject_id==user.id,
            AccountAudit.action=='provider-on:'+providers._binding(workspace,data.provider_id)).limit(1)) is not None
        agent_state=await asyncio.to_thread(service.agent_snapshot)
        effective_agent=data.agent_id or agent_state.get('default_agent')
        selected=next((a for a in agent_state.get('agents') or [] if a.get('name')==effective_agent),None)
        custom_agent=bool(effective_agent and (not selected or selected.get('native') is not True))
        advanced=workspace.project.source_type=='github' or own_key or client_binding or not free_model or custom_agent
        if advanced: require_advanced(db,user)
        # Legacy session rules must not broaden current admin tool restrictions.
        await asyncio.to_thread(service.apply_session_policy,session.opencode_session_id,
                                policy.session_permissions(policy_row))
        if advanced:
            require_advanced(db,user,start=True)
        # Release preflight reads/locks before the async worker opens its own
        # session. Otherwise dispatch can starve a small pool or the PGlite
        # bridge while request cleanup is waiting for that same event loop.
        db.commit()
    except Exception:
        db.rollback(); finish_execution(db,session_id,"failed",data={"reason":"Runtime preflight failed; no new message was dispatched"},request_id=data.request_id)
        raise
    tasks[str(session_id)]=asyncio.create_task(execute(session.id,service,session.opencode_session_id,data,message_id))
    return receipt

@router.get("/{session_id}/submissions/{request_id}")
def submission_receipt(session_id: uuid.UUID,request_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,_=context(db,user,session_id)
    saved=session_lifecycle.receipt(db,session_id,request_id)
    if not saved: raise HTTPException(404,"Submission has not been confirmed")
    return {**saved["receipt"],"status":session.status,"message_id":saved["message_id"]}

@router.get("/{session_id}/messages")
def messages(session_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    service=opencode.for_workspace(workspace,db=db)
    result=service.request("GET",service.session_path(session.opencode_session_id,"/message"))
    attachments={};submitted_text={}
    for recorded in db.scalars(select(ExecutionEvent).where(ExecutionEvent.session_id==session.id,ExecutionEvent.kind=='submission')):
        try:
            saved=json.loads(recorded.data);attachments[saved['message_id']]=saved.get('attachments',[])
            if isinstance(saved.get('text'),str): submitted_text[saved['message_id']]=saved['text']
        except (ValueError,KeyError): pass
    output=[]; hidden=session_lifecycle.hidden_messages(db,session.id); seen=set()
    for item in result:
        text="\n".join(p.get("text","") for p in item.get("parts",[]) if p.get("type")=="text")[:50000]
        info=item.get("info",{}); identifier=info.get("id")
        if identifier in hidden or (identifier and identifier in seen): continue
        seen.add(identifier)
        if info.get('role')=='user': text=submitted_text.get(identifier,text)
        output.append({"id":identifier,"role":info.get("role"),"text":_sanitize(text,workspace),
                       "attachments":attachments.get(identifier,[]),"activity":safe_tool_activity(item.get('parts',[]),workspace),
                       "state":"failed" if info.get("error") else "completed" if info.get("time",{}).get("completed") else "working"})
    return output

@router.get("/{session_id}/todos")
def session_todos(session_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    service=opencode.for_workspace(workspace,db=db)
    try: rows=service.request('GET',service.session_path(session.opencode_session_id,'/todo'))
    except HTTPException as error:
        if error.status_code in {404,405}: return {'supported':False,'items':[]}
        raise
    if not isinstance(rows,list): raise HTTPException(502,'Runtime returned an invalid task list')
    items=[]
    for row in rows[:100]:
        if not isinstance(row,dict) or not isinstance(row.get('content'),str): continue
        status=row.get('status')
        if status not in {'pending','in_progress','completed','cancelled'}: continue
        items.append({'content':_sanitize(row['content'][:2000],workspace),'status':status})
    return {'supported':True,'items':items}

@router.get("/{session_id}/diff")
def session_diff(session_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    service=opencode.for_workspace(workspace,db=db)
    rows=service.request("GET",service.session_path(session.opencode_session_id,"/diff"))
    output=[]
    for item in rows or []:
        patch=_sanitize(item.get("patch",""),workspace)
        output.append({"file":item.get("file"),"status":item.get("status"),"additions":item.get("additions"),"deletions":item.get("deletions"),"patch":patch[:200000]})
    return output

@router.post("/{session_id}/stop")
def stop(session_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    session_lifecycle.lock_workspace(db,workspace); db.refresh(session)
    cancel(db,session,workspace)
    db.commit()
    return {"status":session.status}

def cancel(db,session,workspace):
    if session.status not in session_lifecycle.BUSY: return
    saved=db.scalar(select(ExecutionEvent).where(ExecutionEvent.session_id==session.id,ExecutionEvent.kind=="submission").order_by(ExecutionEvent.id.desc()).limit(1))
    dispatch=db.scalar(select(ExecutionEvent).where(ExecutionEvent.session_id==session.id,ExecutionEvent.kind=="dispatch").order_by(ExecutionEvent.id.desc()).limit(1))
    # A stop during preflight prevents dispatch altogether. Once dispatch begins,
    # wait for its specific user message before aborting: abort-before-POST must
    # never leave a supposedly closed session executing in the background.
    dispatched=not saved or (dispatch and json.loads(dispatch.data)["request_id"]==json.loads(saved.data)["request_id"])
    if dispatched:
        service=opencode.for_workspace(workspace,start=False)
        if saved:
            deadline=time.monotonic()+5
            target=json.loads(saved.data)["message_id"]
            while True:
                rows=service.request("GET",service.session_path(session.opencode_session_id,"/message"),timeout=2)
                db.refresh(session)
                if session.status not in session_lifecycle.BUSY: return
                if any(row.get("info",{}).get("id")==target for row in rows): break
                if time.monotonic()>=deadline: raise HTTPException(409,"OpenCode is still accepting this request; retry Stop before closing")
                time.sleep(.05)
        if service.request("POST",service.session_path(session.opencode_session_id,"/abort")) is not True:
            raise HTTPException(502,"Runtime did not confirm cancellation")
    session.status="cancelled"
    db.add(ExecutionEvent(session_id=session.id,kind="cancelled",data="{}"))

@router.post("/{session_id}/open")
def open_session(session_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    session_lifecycle.lock_workspace(db,workspace); db.refresh(session)
    if session_lifecycle.state(db,session)=="archived": raise HTTPException(409,"Restore this session before opening it")
    session_lifecycle.require_slot(db,workspace,session.id)
    if session_lifecycle.state(db,session)!="active": session_lifecycle.set_state(db,session,"active")
    db.commit()
    return session_lifecycle.payload(session,"active")

@router.post("/{session_id}/close")
def close_session(session_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    session_lifecycle.lock_workspace(db,workspace); db.refresh(session)
    if session_lifecycle.state(db,session)=="archived": raise HTTPException(409,"Session is archived")
    cancel(db,session,workspace)
    session_lifecycle.set_state(db,session,"closed"); db.commit()
    return session_lifecycle.payload(session,"closed")

@router.post("/{session_id}/archive")
def archive_session(session_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    session_lifecycle.lock_workspace(db,workspace); db.refresh(session)
    if session_lifecycle.state(db,session)=="active" or session.status in session_lifecycle.BUSY:
        raise HTTPException(409,"Stop and close this session before archiving")
    session_lifecycle.set_state(db,session,"archived"); db.commit()
    return session_lifecycle.payload(session,"archived")

@router.post("/{session_id}/restore")
def restore_session(session_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    session_lifecycle.lock_workspace(db,workspace); db.refresh(session)
    if session_lifecycle.state(db,session)!="archived": raise HTTPException(409,"Session is not archived")
    session_lifecycle.set_state(db,session,"closed"); db.commit()
    return session_lifecycle.payload(session,"closed")

@router.delete("/{session_id}",status_code=204)
def delete_session(session_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    session_lifecycle.lock_workspace(db,workspace); db.refresh(session)
    if session_lifecycle.state(db,session)=="active" or session.status in session_lifecycle.BUSY:
        raise HTTPException(409,"Stop and close this session before deleting it from client history")
    session_lifecycle.set_state(db,session,"deleted"); db.commit()

@router.delete("/{session_id}/messages/{message_id}",status_code=204)
def hide_message(session_id: uuid.UUID,message_id: str,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    session_lifecycle.lock_workspace(db,workspace); db.refresh(session)
    if session.status in session_lifecycle.BUSY: raise HTTPException(409,"Stop the running request before hiding messages")
    if not re.fullmatch(r"msg_[A-Za-z0-9_-]{1,120}",message_id): raise HTTPException(422,"Invalid message ID")
    service=opencode.for_workspace(workspace,db=db)
    rows=service.request("GET",service.session_path(session.opencode_session_id,"/message"))
    if not any(row.get("info",{}).get("id")==message_id for row in rows): raise HTTPException(404,"Message not found in this session")
    if message_id not in session_lifecycle.hidden_messages(db,session.id):
        db.add(ExecutionEvent(session_id=session.id,kind="client_message_hidden",data=json.dumps({"message_id":message_id})))
    db.commit()

class QuestionReply(BaseModel):
    answers: list[list[str]] = Field(default_factory=list,max_length=20)
    reject: bool = False

@router.get("/{session_id}/questions")
def session_questions(session_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    try: rows=opencode.for_workspace(workspace,db=db).request('GET','/question')
    except HTTPException as error:
        if error.status_code in {404,405}: return {'supported':False,'requests':[]}
        raise
    output=[]
    for row in rows:
        if row.get('sessionID')!=session.opencode_session_id: continue
        questions=[]
        for q in row.get('questions',[])[:20]:
            questions.append({'header':_sanitize(str(q.get('header',''))[:200],workspace),
                'question':_sanitize(str(q.get('question',''))[:8000],workspace),
                'multiple':bool(q.get('multiple')),'custom':q.get('custom') is not False,
                'options':[{'label':_sanitize(str(o.get('label',''))[:2000],workspace),
                    'description':_sanitize(str(o.get('description',''))[:2000],workspace),
                    'recommended':o.get('recommended') is True or bool(re.search(r'\(\s*(?:recommended|موصى به)\s*\)\s*$',str(o.get('label','')),re.I))} for o in q.get('options',[])[:50] if isinstance(o,dict)]})
        output.append({'id':row['id'],'questions':questions})
    return {'supported':True,'requests':output}

@router.post("/{session_id}/questions/{question_id}")
def answer_question(session_id: uuid.UUID,question_id: str,data: QuestionReply,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id);service=opencode.for_workspace(workspace,db=db)
    rows=service.request('GET','/question')
    pending=next((r for r in rows if r.get('sessionID')==session.opencode_session_id and r.get('id')==question_id),None)
    if pending is None: raise HTTPException(404,'Question not found in this conversation')
    from urllib.parse import quote
    path='/question/'+quote(question_id,safe='')
    if data.reject: result=service.request('POST',path+'/reject')
    else:
        questions=pending.get('questions',[])
        if len(data.answers)!=len(questions) or not questions: raise HTTPException(422,'Answer every question')
        answers=[]
        for q,values in zip(questions,data.answers):
            if not values or len(values)>20 or (not q.get('multiple') and len(values)!=1) or any(not v.strip() or len(v)>2000 for v in values):
                raise HTTPException(422,'Invalid answer')
            labels={_sanitize(str(o.get('label',''))[:2000],workspace):o.get('label') for o in q.get('options',[])}
            # A duplicated answer must not be sent twice to the runtime; an
            # untrusted custom answer cannot masquerade as an offered choice.
            if len(set(values)) != len(values):
                raise HTTPException(422,'Duplicate choices are not allowed')
            if q.get('custom') is False and any(v not in labels for v in values):
                raise HTTPException(422,'Select one of the offered answers')
            answers.append([labels.get(v,v) for v in values])
        result=service.request('POST',path+'/reply',{'answers':answers})
    if result is not True: raise HTTPException(502,'Runtime did not confirm the answer')
    event(db,session.id,'question_decision',{'rejected':data.reject})
    return {'accepted':True}

class RoutineApproval(BaseModel):
    enabled: bool

def routine_enabled(db, session_id):
    record=db.scalar(select(ExecutionEvent).where(ExecutionEvent.session_id==session_id,
        ExecutionEvent.kind=='routine_approval').order_by(ExecutionEvent.id.desc()).limit(1))
    # Fail closed: new conversations require explicit approval until the user opts in.
    if record is None: return False
    try: return json.loads(record.data).get('enabled') is True
    except (ValueError,TypeError): return False

@router.get("/{session_id}/permissions/routine")
def routine_permissions(session_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,_=context(db,user,session_id)
    return {'enabled':routine_enabled(db,session.id)}

@router.put("/{session_id}/permissions/routine")
def set_routine_permissions(session_id: uuid.UUID,data: RoutineApproval,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id);session_lifecycle.lock_workspace(db,workspace)
    event(db,session.id,'routine_approval',{'enabled':data.enabled})
    return {'enabled':data.enabled}

def permission_tool_part(service, session, pending):
    reference=pending.get('tool') or {}
    if not reference.get('messageID') or not reference.get('callID'): return None
    rows=service.request('GET',service.session_path(session.opencode_session_id,'/message'))
    part=next((p for row in rows if row.get('info',{}).get('id')==reference['messageID']
        for p in row.get('parts',[]) if p.get('type')=='tool' and p.get('callID')==reference['callID']),None)
    return part

def routine_project_path(workspace, raw):
    if not isinstance(raw,str): return False
    try:
        path=Path(raw);root=workspaces.root_for(workspace).resolve()
        if path.is_absolute():
            if not path.is_relative_to(root): return False
            raw=path.relative_to(root).as_posix()
        if any(p.startswith('.env') or p.lower().endswith(('.pem','.key')) for p in Path(raw).parts): return False
        if any(ord(char)<32 for char in raw): return False
        if '.github/workflows' in Path(raw).as_posix() or Path(raw).name in {'opencode.json','opencode.jsonc'} or '.opencode' in Path(raw).parts: return False
        workspaces.safe_path(workspace,raw)
    except (HTTPException,ValueError): return False
    return True

def routine_file_patch(workspace, patch):
    """Only recognize bounded native file additions/edits; never shell patches.

    Unknown grammar, deletion and movement require a separate reviewed approval.
    Every target is checked, including later hunks; patch contents are not executed.
    """
    if not isinstance(patch,str) or not patch or len(patch)>200_000 or '\x00' in patch: return False
    lines=patch.strip().splitlines()
    if len(lines)<3 or lines[0]!='*** Begin Patch' or lines[-1]!='*** End Patch': return False
    operation=None;targets=0
    for line in lines[1:-1]:
        match=re.fullmatch(r'\*\*\* (Add|Update) File: (.+)',line)
        if match:
            if not routine_project_path(workspace,match[2]): return False
            operation=match[1];targets+=1
            if targets>50: return False
        elif operation=='Add' and line.startswith('+'): continue
        elif operation=='Update' and (line.startswith((' ','+','-','@@')) or line=='*** End of File'): continue
        else: return False
    return targets>0

def routine_request(workspace, part):
    if not part or part.get('tool') not in {'read','list','glob','grep','write','edit','apply_patch','todowrite','todoread'}: return False
    if part['tool'] in {'todowrite','todoread'}: return True
    inp=(part.get('state') or {}).get('input') or {}
    if part['tool']=='apply_patch': return routine_file_patch(workspace,inp.get('patchText'))
    raw=inp.get('filePath') or inp.get('path')
    if raw is None and part['tool'] in {'list','glob','grep'}: raw=''
    return routine_project_path(workspace,raw)

def approval_fingerprint(permission, patterns, tool=None):
    return hashlib.sha256(json.dumps([permission, tool, sorted(patterns)], ensure_ascii=False).encode()).hexdigest()

def remembered_approvals(db, session_id):
    approved=set()
    records=db.scalars(select(ExecutionEvent).where(ExecutionEvent.session_id==session_id,
        ExecutionEvent.kind.in_(['approval_rule','approval_rules_cleared'])).order_by(ExecutionEvent.id))
    for record in records:
        if record.kind=='approval_rules_cleared': approved.clear(); continue
        if record.kind!='approval_rule': continue
        try:
            value=json.loads(record.data).get('fingerprint')
            if isinstance(value,str) and re.fullmatch(r'[a-f0-9]{64}',value): approved.add(value)
        except (ValueError,TypeError): pass
    return approved

@router.get("/{session_id}/permissions/remembered")
def remembered_permissions(session_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,_=context(db,user,session_id)
    return {'count':len(remembered_approvals(db,session.id))}

@router.delete("/{session_id}/permissions/remembered")
def clear_remembered_permissions(session_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    session_lifecycle.lock_workspace(db,workspace)
    event(db,session.id,'approval_rules_cleared')
    return {'cleared':True}

@router.get("/{session_id}/permissions")
def permissions(session_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    service=opencode.for_workspace(workspace,db=db)
    rows=service.request("GET","/permission")
    remembered=remembered_approvals(db,session.id)
    _,_,allowed_tools=policy.provider_sets(policy.load(db))
    owned=[]
    for pending in rows:
        if pending.get("sessionID")!=session.opencode_session_id:
            continue
        patterns=pending.get("patterns",[])
        reviewable=isinstance(patterns,list) and 0<len(patterns)<=20 and all(isinstance(p,str) and 0<len(p)<=4000 for p in patterns)
        # Never offer blind approval or approve a truncated command/pattern.
        details=[p.replace(str(workspaces.root_for(workspace)),"[workspace]") for p in patterns] if reviewable else []
        permission=pending.get('permission')
        allowed=isinstance(permission,str) and permission!='external_directory' and (not allowed_tools or permission in allowed_tools)
        part=None
        if allowed and reviewable:
            try: part=permission_tool_part(service,session,pending)
            except HTTPException: pass
        tool=part.get('tool') if part else permission if permission in {'bash','read','glob','grep','list','todowrite','todoread'} else None
        rememberable=reviewable and allowed and bool(tool) and all(p not in {'*','**'} for p in patterns)
        fingerprint=approval_fingerprint(permission,patterns,tool) if rememberable else None
        routine=False
        if allowed and reviewable and routine_enabled(db,session.id):
            try: routine=routine_request(workspace,part)
            except HTTPException: routine=False
        if fingerprint in remembered or routine:
            # Exact reviewed requests only, scoped to this owned conversation.
            # Recheck current platform policy on every repeat; never use runtime "always".
            from urllib.parse import quote
            session_lifecycle.lock_workspace(db,workspace)
            _,_,current_tools=policy.provider_sets(policy.load(db))
            current_allowed=permission!='external_directory' and (not current_tools or permission in current_tools)
            if not current_allowed or (fingerprint not in remembered_approvals(db,session.id) and not (routine and routine_enabled(db,session.id))):
                db.rollback()
            else:
                try: result=service.request('POST','/permission/'+quote(pending['id'],safe='')+'/reply',{'reply':'once'})
                except HTTPException as error:
                    db.rollback()
                    if error.status_code==404: continue
                    raise
                if result is not True: raise HTTPException(502,'Runtime did not confirm the repeated approval')
                db.execute(update(WorkspaceSession).where(WorkspaceSession.id==session.id,
                    WorkspaceSession.status=='waiting_approval').values(status='submitted').execution_options(synchronize_session=False))
                event(db,session.id,'approval_decision',{'reply':'routine' if routine else 'similar','automatic':True,'fingerprint':fingerprint})
                continue
        owned.append({'id':pending['id'],'permission':permission,'patterns':details,'reviewable':reviewable,
                      'rememberable':rememberable,'fingerprint':fingerprint})
    if owned and session.status in {"submitted","waiting_approval"}:
        changed=db.execute(update(WorkspaceSession).where(WorkspaceSession.id==session.id,
            WorkspaceSession.status=="submitted").values(status="waiting_approval").execution_options(synchronize_session=False)).rowcount
        if changed: event(db,session.id,"waiting_approval")
        else: db.rollback()
    return owned

@router.post("/{session_id}/permissions/{permission_id}")
def approve(session_id: uuid.UUID,permission_id: str,data: Approval,user: User=Depends(require_user),db: Session=Depends(get_db)):
    session,workspace=context(db,user,session_id)
    pending=permissions(session_id,user,db)
    if permission_id not in {p["id"] for p in pending}: raise HTTPException(404,"Permission request not found")
    if data.reply in {"once","similar"} and not next(p["reviewable"] for p in pending if p["id"]==permission_id):
        raise HTTPException(409,"Permission details cannot be fully reviewed; deny this request")
    requested=next(p for p in pending if p["id"]==permission_id)
    _,_,allowed_tools=policy.provider_sets(policy.load(db))
    if data.reply in {"once","similar"} and (requested["permission"]=="external_directory" or
                               (allowed_tools and requested["permission"] not in allowed_tools)):
        raise HTTPException(403,"This permission is disabled by platform policy")
    if data.reply=='similar' and not requested.get('rememberable'):
        raise HTTPException(409,'This request cannot be remembered; approve once or reject')
    from urllib.parse import quote
    result=opencode.for_workspace(workspace,db=db).request("POST","/permission/"+quote(permission_id,safe="")+"/reply",{"reply":"once" if data.reply=="similar" else data.reply})
    if result is not True: raise HTTPException(502,"Runtime did not confirm the decision")
    if data.reply=='similar':
        db.add(ExecutionEvent(session_id=session.id,kind='approval_rule',data=json.dumps({'fingerprint':requested['fingerprint']})))
    db.execute(update(WorkspaceSession).where(WorkspaceSession.id==session.id,
        WorkspaceSession.status=="waiting_approval").values(status="submitted").execution_options(synchronize_session=False))
    event(db,session.id,"approval_decision",{"reply":data.reply})
    return {"accepted":True}

def event_page(request,session_id,cursor):
    # Return detached values; never keep a connection checked out while yielding
    # SSE bytes to a slow/disconnected browser.
    with SessionLocal() as current:
        try:
            current_user=require_user(request,current)
            context(current,current_user,session_id)
        except HTTPException as exc:
            return [],'authentication_expired' if exc.status_code in {401,403} else 'closed'
        rows=current.scalars(select(ExecutionEvent).where(ExecutionEvent.session_id==session_id,ExecutionEvent.id>cursor).order_by(ExecutionEvent.id).limit(100))
        return [(row.id,row.kind,row.data) for row in rows],None


@router.get("/{session_id}/events")
def events(session_id: uuid.UUID,request: Request,after: int=0,last_event_id: str|None=Header(default=None),user: User=Depends(require_user),db: Session=Depends(get_db)):
    context(db,user,session_id)
    try: cursor=max(0,int(last_event_id) if last_event_id is not None else after)
    except ValueError: raise HTTPException(422,"Invalid event ID")
    db.rollback()  # Initial ownership is read-only; release before streaming.
    async def stream():
        nonlocal cursor
        while not await request.is_disconnected():
            rows,failure=await asyncio.to_thread(event_page,request,session_id,cursor)
            if failure:
                if failure=='authentication_expired':yield 'event: authentication_expired\ndata: {}\n\n'
                return
            for identifier,kind,data in rows:
                cursor=identifier
                yield f"id: {identifier}\nevent: {kind}\ndata: {data}\n\n"
            yield ": keepalive\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(stream(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})
