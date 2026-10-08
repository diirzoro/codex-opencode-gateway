import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import ExecutionEvent, Project, ProviderCredential, User, Workspace, WorkspaceSession
from ..services import credentials, github, opencode, policy, providers, runtime_snapshot, preview, session_lifecycle
from ..services import workspaces as manager
from ..services.entitlements import access_payload, require_advanced
from .dependencies import require_user, require_workspace_entitlement

router=APIRouter(prefix="/api",tags=["workspaces"],dependencies=[Depends(require_workspace_entitlement)])
logger=logging.getLogger(__name__)

class CreateProject(BaseModel):
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)
    project_name: str=Field(min_length=1,max_length=120,pattern=r"^[^\r\n\x00]+$")
    source_type: Literal["github","blank","template"]="blank"
    repository: str|None=None
    branch: str|None=None
    template: str|None=None
    working_paths: list[str]=Field(default_factory=list,max_length=10)

class RenameProject(BaseModel):
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)
    name: str=Field(min_length=1,max_length=120,pattern=r"^[^\r\n\x00]+$")

class NewSession(BaseModel):
    title: str=Field(default="New session",min_length=1,max_length=120)

class CommitRequest(BaseModel):
    message: str=Field(min_length=1,max_length=500,pattern=r"^[^\x00]+$")

class PublishProject(BaseModel):
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)
    repository: str=Field(min_length=3,max_length=255)
    branch: str|None=Field(default=None,max_length=120)

class ApiKeyCredential(BaseModel):
    model_config=ConfigDict(extra="forbid")
    api_key: str=Field(min_length=1,max_length=4000)
    model_id: str|None=Field(default=None,max_length=200)
    method: int|None=Field(default=None,ge=0,le=20)
    inputs: dict[str,str]|None=None

class OAuthAuthorize(BaseModel):
    model_config=ConfigDict(extra="forbid")
    method: int=Field(ge=0,le=20)
    inputs: dict[str,str]|None=None

class OAuthCallback(BaseModel):
    model_config=ConfigDict(extra="forbid")
    method: int=Field(ge=0,le=20)
    code: str|None=Field(default=None,max_length=4000)

def session_payload(row):
    return {"id":str(row.id),"workspace_id":str(row.workspace_id),"title":row.title,"status":row.status,"created_at":row.created_at}

def _workspace_and_project(db,user,workspace_id):
    workspace=manager.owned(db,Workspace,workspace_id,user.id)
    project=db.get(Project,workspace.project_id)
    return workspace,project

@router.get("/opencode/health")
def health(user: User=Depends(require_user)):
    return opencode.shared_health()

@router.get("/opencode/status")
def runtime_status(user: User=Depends(require_user)):
    try: health=opencode.shared_health()
    except HTTPException: health={"healthy":False,"version":None}
    return {**health,"runtime_mode":settings.runtime_mode,"public_multi_user_ready":False}

@router.get("/github/status")
def github_status(user: User=Depends(require_user),db: Session=Depends(get_db)):
    return github.connection_status(db,user)

@router.get("/templates")
def templates(user: User=Depends(require_user)):
    return [{"id":key,"name":key} for key in manager.TEMPLATES]

def _github_source(db,user,data):
    paths=manager.validate_working_paths(data.working_paths)
    require_advanced(db,user)
    connection=github.connection_for(db,user)
    if not manager.valid_repository(data.repository) or not manager.valid_branch(data.branch):
        raise HTTPException(422,"A valid repository (owner/name) and branch are required")
    repo=github.authorized_repository(connection,data.repository)
    return {"clone_url":repo["clone_url"],"branch":data.branch,"token":github.installation_token(connection),"repository_id":repo["id"],"installation_id":connection.installation_id,"working_paths":paths}

@router.post("/projects",status_code=201)
def create_project(data: CreateProject,user: User=Depends(require_user),db: Session=Depends(get_db)):
    if data.working_paths and data.source_type!="github": raise HTTPException(422,"Selective working directories apply only to GitHub projects")
    github_source=_github_source(db,user,data) if data.source_type=="github" else None
    project,workspace=manager.create(db,user,data.project_name,data.source_type,data.template,data.repository,data.branch,github_source)
    if github_source:
        require_advanced(db,user,start=True); db.commit()
    return {"project":manager.project_payload(project),"workspace":manager.workspace_payload(workspace)}

@router.post("/workspaces",status_code=201)
def create_workspace(data: CreateProject,user: User=Depends(require_user),db: Session=Depends(get_db)):
    # Same creation transaction, not a competing implementation.
    return create_project(data,user,db)

@router.get("/projects")
def projects(user: User=Depends(require_user),db: Session=Depends(get_db)):
    return [manager.project_payload(p) for p in db.scalars(select(Project).where(Project.user_id==user.id,Project.archived_at.is_(None)).order_by(Project.created_at.desc()))]

@router.get("/projects/{project_id}")
def project(project_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    return manager.project_payload(manager.owned(db,Project,project_id,user.id))

@router.patch("/projects/{project_id}")
def rename(project_id: uuid.UUID,data: RenameProject,user: User=Depends(require_user),db: Session=Depends(get_db)):
    row=manager.owned(db,Project,project_id,user.id); row.name=data.name; db.commit()
    return manager.project_payload(row)

@router.post("/projects/{project_id}/archive")
def archive_project(project_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    row=manager.owned(db,Project,project_id,user.id)
    row.archived_at=datetime.now(timezone.utc); db.commit()
    return manager.project_payload(row)

@router.delete("/projects/{project_id}")
def delete_project(project_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    manager.owned(db,Project,project_id,user.id)
    raise HTTPException(409,"Deletion is unavailable; use archive to hide it safely until verified remote backup and retention safeguards are implemented")

@router.post("/projects/{project_id}/publish")
def publish_project(project_id: uuid.UUID,data: PublishProject,user: User=Depends(require_user),db: Session=Depends(get_db)):
    project=manager.owned(db,Project,project_id,user.id)
    require_advanced(db,user)
    connection=github.connection_for(db,user)
    if not manager.valid_repository(data.repository):
        raise HTTPException(422,"A repository in owner/name form is required")
    branch=data.branch or "work"
    if not manager.valid_branch(branch):
        raise HTTPException(422,"A valid branch name is required")
    repo=github.authorized_repository(connection,data.repository)
    project.repository=data.repository
    project.github_repository_id=repo["id"]
    project.github_installation_id=connection.installation_id
    project.remote_url=repo["clone_url"]
    project.remote_branch=branch
    require_advanced(db,user,start=True)
    db.commit()
    return manager.project_payload(project)

@router.get("/workspaces")
def workspaces(user: User=Depends(require_user),db: Session=Depends(get_db)):
    return [manager.workspace_payload(w) for w in db.scalars(select(Workspace).where(Workspace.user_id==user.id).order_by(Workspace.created_at.desc()))]

@router.get("/workspaces/{workspace_id}")
def workspace(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    return manager.workspace_payload(manager.owned(db,Workspace,workspace_id,user.id))

@router.delete("/workspaces/{workspace_id}")
def delete_workspace(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    manager.owned(db,Workspace,workspace_id,user.id)
    raise HTTPException(409,"Workspace preserved: verified push and cleanup policy are not implemented")

@router.get("/workspaces/{workspace_id}/files")
def files(workspace_id: uuid.UUID,path: str="",user: User=Depends(require_user),db: Session=Depends(get_db)):
    return manager.files(manager.owned(db,Workspace,workspace_id,user.id),path)

@router.get("/workspaces/{workspace_id}/files/content")
def file_content(workspace_id: uuid.UUID,path: str=Query(...,max_length=1000),user: User=Depends(require_user),db: Session=Depends(get_db)):
    row=manager.owned(db,Workspace,workspace_id,user.id)
    return {"path":path,"content":manager.content(row,path)}

def _git_status(db,user,workspace_id):
    workspace,project=_workspace_and_project(db,user,workspace_id)
    state=manager.status(workspace)
    connected=False
    if project.remote_url:
        status=github.connection_status(db,user)
        connected=bool(status.get("connected"))
    state["push_available"]=bool(project.remote_url and project.remote_branch and connected)
    state["remote_url"]=project.remote_url
    state["remote_branch"]=project.remote_branch
    state["repository"]=project.repository
    state["github_access"]=access_payload(db,user)["github_access"]
    state["push_available"]=state["push_available"] and state["github_access"]
    return workspace,project,state

@router.get("/workspaces/{workspace_id}/git/status")
def git_status(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    return _git_status(db,user,workspace_id)[2]

@router.get("/workspaces/{workspace_id}/changes")
def changes(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    return git_status(workspace_id,user,db)["changes"]

@router.get("/workspaces/{workspace_id}/diff")
def diff(workspace_id: uuid.UUID,path: str|None=Query(default=None,max_length=1000),user: User=Depends(require_user),db: Session=Depends(get_db)):
    return manager.diff(manager.owned(db,Workspace,workspace_id,user.id),path)

@router.get("/workspaces/{workspace_id}/preview")
def workspace_preview(workspace_id: uuid.UUID,path: str=Query(default="index.html",max_length=1000),user: User=Depends(require_user),db: Session=Depends(get_db)):
    return preview.render(manager.owned(db,Workspace,workspace_id,user.id),path)

@router.get("/workspaces/{workspace_id}/logs")
def logs(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    manager.owned(db,Workspace,workspace_id,user.id)
    rows=db.scalars(select(ExecutionEvent).join(WorkspaceSession,ExecutionEvent.session_id==WorkspaceSession.id).where(WorkspaceSession.workspace_id==workspace_id,WorkspaceSession.user_id==user.id).order_by(ExecutionEvent.id.desc()).limit(200))
    return [{"id":r.id,"type":r.kind,"created_at":r.created_at} for r in rows]

@router.post("/workspaces/{workspace_id}/git/commit")
def commit(workspace_id: uuid.UUID,data: CommitRequest,user: User=Depends(require_user),db: Session=Depends(get_db)):
    workspace=manager.owned(db,Workspace,workspace_id,user.id)
    with opencode.workspace_lock(workspace):
        _require_git_idle(db,workspace)
        return manager.commit(workspace,user,data.message)

def _require_git_idle(db,workspace):
    session_lifecycle.lock_workspace(db,workspace)
    if db.scalar(select(WorkspaceSession.id).where(WorkspaceSession.workspace_id==workspace.id,
        WorkspaceSession.status.in_(["submitted","waiting_approval"]))):
        raise HTTPException(409,"Stop active workspace work before changing Git history")

def _github_remote(db,user,project):
    require_advanced(db,user)
    connection=github.connection_for(db,user)
    repo=github.authorized_repository(connection,project.repository)
    if project.github_repository_id and repo["id"]!=project.github_repository_id:
        raise HTTPException(409,"GitHub repository identity changed; explicitly reconnect this project")
    return connection,repo

@router.post("/workspaces/{workspace_id}/git/push")
def push(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    workspace,project=_workspace_and_project(db,user,workspace_id)
    if not project.remote_url or not project.remote_branch:
        raise HTTPException(503,"This project has no GitHub remote; publish or create it from a GitHub repository first")
    connection,repo=_github_remote(db,user,project)
    with opencode.workspace_lock(workspace):
        _require_git_idle(db,workspace)
        state=manager.status(workspace)
        if not state["head"]: raise HTTPException(409,"There is no commit to push")
        if not state["clean"]: raise HTTPException(409,"Review and commit your working tree before pushing")
        token=github.installation_token(connection)
        manager.push_remote(workspace,repo["clone_url"],project.remote_branch,token)
        verified=github.verify_remote_commit(connection,project.repository,project.remote_branch,state["head"])
        if not verified:
            raise HTTPException(502,"Push finished but the expected commit was not verified on the remote branch")
        require_advanced(db,user,start=True)
        workspace.status="pushed"; db.commit()
    return {"pushed":True,"branch":project.remote_branch,"head":state["head"],"verified":True}

@router.post("/workspaces/{workspace_id}/git/sync")
def sync(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    workspace,project=_workspace_and_project(db,user,workspace_id)
    if not project.remote_branch: raise HTTPException(409,"This project has no GitHub remote")
    connection,repo=_github_remote(db,user,project)
    with opencode.workspace_lock(workspace):
        _require_git_idle(db,workspace)
        state=manager.sync_remote(workspace,repo['clone_url'],project.remote_branch,github.installation_token(connection))
        require_advanced(db,user,start=True)
        workspace.base_commit_sha=state['head']; db.commit()
        return state

@router.get("/workspaces/{workspace_id}/export")
def export_workspace(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    workspace=manager.owned(db,Workspace,workspace_id,user.id)
    with opencode.workspace_lock(workspace):
        _require_git_idle(db,workspace)
        path=manager.export(workspace)
    return FileResponse(path,media_type="application/zip",filename="workspace-source.zip",
                        background=BackgroundTask(path.unlink,missing_ok=True))

@router.post("/workspaces/{workspace_id}/sessions",status_code=201)
def new_session(workspace_id: uuid.UUID,data: NewSession,user: User=Depends(require_user),db: Session=Depends(get_db)):
    row=manager.owned(db,Workspace,workspace_id,user.id)
    if row.project.source_type=="github": require_advanced(db,user)
    manager.require_quota_headroom(row)
    session_lifecycle.lock_workspace(db,row)
    session_lifecycle.require_slot(db,row)
    runtime_id=opencode.for_workspace(row).create_session(data.title)
    session=WorkspaceSession(workspace_id=row.id,user_id=user.id,opencode_session_id=runtime_id,title=data.title)
    db.add(session); db.flush(); session_lifecycle.set_state(db,session,"active")
    if row.project.source_type=="github": require_advanced(db,user,start=True)
    db.commit(); db.refresh(session)
    return session_lifecycle.payload(session,"active")

@router.post("/workspaces/{workspace_id}/files/upload",status_code=201)
def upload_workspace_file(workspace_id: uuid.UUID,file: UploadFile=File(...),path: str=Form(default=""),user: User=Depends(require_user),db: Session=Depends(get_db)):
    import re
    row=manager.owned(db,Workspace,workspace_id,user.id)
    name=(file.filename or "").replace("\\","/").split("/")[-1].strip()
    if not name or name in {".",".."} or "\x00" in name or len(name)>200: raise HTTPException(422,"A valid file name is required")
    if name==".env" or name.endswith((".pem",".key")) or name.startswith("."): raise HTTPException(403,"This file type is not allowed in the workspace")
    folder=(path or "").strip().strip("/")
    if folder and not re.fullmatch(r"[A-Za-z0-9._/-]{1,500}",folder): raise HTTPException(422,"Invalid folder path")
    storage=manager.storage_payload(row)
    content=file.file.read(storage['limit_bytes']+1)
    if len(content)>storage['remaining_bytes']: raise HTTPException(413,"Workspace storage limit reached. Remove files before uploading.")
    target=manager.safe_path(row,(folder+"/" if folder else "")+name)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(content)
    return {"path":(folder+"/" if folder else "")+name,"size":len(content),"storage":manager.storage_payload(row)}

@router.get("/workspaces/{workspace_id}/storage")
def storage(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    return manager.storage_payload(manager.owned(db,Workspace,workspace_id,user.id))

@router.get("/workspaces/{workspace_id}/sessions")
def sessions(workspace_id: uuid.UUID,include_archived: bool=False,user: User=Depends(require_user),db: Session=Depends(get_db)):
    workspace,service=_workspace_service(db,user,workspace_id)
    with service.session_lock:
        rows=runtime_snapshot.sync_sessions(db,workspace,service.request("GET","/session"))
        return rows if include_archived else [row for row in rows if row["lifecycle"]!="archived"]

@router.get("/sessions/{session_id}")
def session(session_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    row=manager.owned(db,WorkspaceSession,session_id,user.id)
    session_lifecycle.require_visible(db,row)
    workspace=manager.owned(db,Workspace,row.workspace_id,user.id)
    live=opencode.for_workspace(workspace).request("GET","/session/"+row.opencode_session_id)
    return {**providers.public_metadata(live),**session_lifecycle.payload(row,session_lifecycle.state(db,row)),"title":live["title"],"runtime_id":row.opencode_session_id}

def _workspace_service(db,user,workspace_id):
    row=manager.owned(db,Workspace,workspace_id,user.id)
    return row,opencode.for_workspace(row)

@router.get("/workspaces/{workspace_id}/runtime")
def workspace_runtime(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db),refresh: bool=False):
    started=time.monotonic()
    row,service=_workspace_service(db,user,workspace_id)
    with service.state_lock:
        if refresh:
            service.invalidate()
        snapshot=runtime_snapshot.public_snapshot(service,row,db)
        snapshot["diagnostics"]["total_runtime_bootstrap_ms"]=round((time.monotonic()-started)*1000,2)
        return snapshot

@router.get("/workspaces/{workspace_id}/runtime/state")
def workspace_runtime_state(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    row,service=_workspace_service(db,user,workspace_id)
    return {"workspace_id":str(row.id),"policy_revision":runtime_snapshot.workspace_policy_revision(db,row,policy.load(db)),**service.discovery_state()}

@router.get("/workspaces/{workspace_id}/runtime/agents")
def workspace_runtime_agents(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    row,service=_workspace_service(db,user,workspace_id)
    return runtime_snapshot.public_agents(service,row)

@router.get("/workspaces/{workspace_id}/runtime/capabilities")
def workspace_capabilities(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db),view: str|None=Query(default=None,pattern="^agent$")):
    row,service=_workspace_service(db,user,workspace_id)
    return runtime_snapshot.public_capabilities(service,row,db,view=view)

@router.get("/workspaces/{workspace_id}/providers")
def available_providers(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    row,service=_workspace_service(db,user,workspace_id)
    return providers.catalog(providers.client_catalog(db,row,service.request("GET","/provider")),
                             providers.auth_methods(service),policy.load(db))

@router.get("/workspaces/{workspace_id}/providers/{provider_id}/models")
def provider_models(workspace_id: uuid.UUID,provider_id: str,user: User=Depends(require_user),db: Session=Depends(get_db)):
    row,service=_workspace_service(db,user,workspace_id)
    with service.state_lock:
        return runtime_snapshot.public_models(service,row,provider_id,db)

@router.get("/workspaces/{workspace_id}/providers/resolve")
def resolve_provider(workspace_id: uuid.UUID,name: str=Query(min_length=1,max_length=200),user: User=Depends(require_user),db: Session=Depends(get_db)):
    row,service=_workspace_service(db,user,workspace_id)
    with service.state_lock:
        return runtime_snapshot.public_provider_lookup(service,row,db,name=name)

@router.get("/workspaces/{workspace_id}/providers/search")
def search_providers(workspace_id: uuid.UUID,query: str=Query(min_length=2,max_length=200),user: User=Depends(require_user),db: Session=Depends(get_db)):
    row,service=_workspace_service(db,user,workspace_id)
    with service.state_lock:
        return runtime_snapshot.public_provider_lookup(service,row,db,query=query)

@router.get("/workspaces/{workspace_id}/agents")
def available_agents(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    row=manager.owned(db,Workspace,workspace_id,user.id)
    return agent_choices(opencode.for_workspace(row))

def agent_choices(service):
    rows=service.request("GET","/agent")
    if not isinstance(rows,list): raise HTTPException(502,"Runtime returned an invalid agent list")
    return [{**providers.public_metadata(r),"id":r["name"],"name":r["name"]} for r in rows
            if isinstance(r,dict) and isinstance(r.get("name"),str) and 0<len(r["name"])<=120
            and not r.get("hidden") and r.get("mode") in {"primary","all"}]

@router.post("/workspaces/{workspace_id}/providers/{provider_id}/credentials")
def set_provider_credential(workspace_id: uuid.UUID,provider_id: str,data: ApiKeyCredential,user: User=Depends(require_user),db: Session=Depends(get_db)):
    require_advanced(db,user)
    if not policy.provider_allowed(policy.load(db),provider_id): raise HTTPException(403,'Provider is disabled by platform policy')
    if not credentials.available():
        raise HTTPException(503,'Encrypted credential storage must be configured first')
    workspace,service=_workspace_service(db,user,workspace_id)
    with opencode.workspace_lock(workspace),service.state_lock:
        session_lifecycle.lock_workspace(db,workspace)
        live=service.snapshot()
        if live["provider_data"] is None:
            raise HTTPException(502,"OpenCode provider discovery must succeed before connecting")
        entry=providers.resolve_provider(live["provider_data"],provider_id)
        if entry["id"] != provider_id:
            raise HTTPException(422,"Use the provider ID reported by OpenCode")
        methods=providers.connection_methods(service,provider_id)
        api_methods=[i for i,method in enumerate(methods) if method.get("type") in {"api","key"}]
        method=data.method if data.method is not None else (api_methods[0] if len(api_methods)==1 else None)
        if method is None or method >= len(methods) or methods[method].get("type") not in {"api","key"}:
            raise HTTPException(422,"Select an API key authentication method reported by OpenCode; OAuth-only providers require their OAuth flow")
        row=db.scalar(select(ProviderCredential).where(ProviderCredential.workspace_id==workspace.id,ProviderCredential.provider_id==provider_id))
        if row is None and providers.is_connected(service,provider_id) and not providers.is_locally_disconnected(db,workspace,provider_id):
            raise HTTPException(409,"Disconnect the existing runtime connection before replacing its authentication")
        service.ensure_auth_idle()
        old_ciphertext=row.ciphertext if row is not None else None
        stage="credential installation"
        try:
            providers.set_api_key(service,provider_id,data.api_key,data.inputs)
            stage="workspace authentication refresh"
            service.refresh_auth()
            stage="model validation"
            validated_model=providers.validate_model(service,provider_id,data.model_id,policy.load(db))
            stage="encrypted credential storage"
            encrypted=credentials.encrypt(json.dumps({"type":"api","key":data.api_key,"metadata":data.inputs or {}}))
            require_advanced(db,user,start=True)
            if row is None:
                row=ProviderCredential(workspace_id=workspace.id,user_id=user.id,provider_id=provider_id,ciphertext="",last4="")
                db.add(row)
            row.ciphertext=encrypted
            row.last4=data.api_key[-4:]
            providers.record_connection(db,workspace,provider_id,connected=True)
            db.commit()
        except Exception as exc:
            db.rollback()
            rollback_confirmed=True
            try:
                providers.remove(service,provider_id)
                if old_ciphertext:
                    providers.restore_credential(service,provider_id,credentials.decrypt(old_ciphertext))
                    service.refresh_auth()
            except Exception:
                rollback_confirmed=False
            if old_ciphertext is None or not rollback_confirmed:
                # Failed/new credentials must not become composer connections
                # even when runtime auth cleanup refuses deletion.
                try:
                    providers.record_connection(db,workspace,provider_id,connected=False)
                    db.commit()
                except Exception:
                    db.rollback()
                    logger.warning("Failed provider connection could not persist its disconnect state for workspace %s",workspace.id)
            detail=f"Provider connection failed during {stage}"
            if isinstance(exc,HTTPException): detail+=" — "+str(exc.detail)
            detail+=". No new key was persisted."
            if not rollback_confirmed: detail+=" Runtime credential cleanup could not be confirmed; disconnect before retrying."
            raise HTTPException(exc.status_code if isinstance(exc,HTTPException) else 502,detail) from None
        return {"connected":True,"provider_id":provider_id,"last4":data.api_key[-4:],"persisted":True,"validated_model":validated_model}

@router.delete("/workspaces/{workspace_id}/providers/{provider_id}",status_code=204)
def remove_provider_credential(workspace_id: uuid.UUID,provider_id: str,user: User=Depends(require_user),db: Session=Depends(get_db)):
    workspace=manager.owned(db,Workspace,workspace_id,user.id)
    with opencode.workspace_lock(workspace):
        session_lifecycle.lock_workspace(db,workspace)
        row=db.scalar(select(ProviderCredential).where(ProviderCredential.workspace_id==workspace.id,
            ProviderCredential.user_id==user.id,ProviderCredential.provider_id==provider_id))
        if row is not None:
            db.delete(row)
        providers.record_connection(db,workspace,provider_id,connected=False)
        db.commit()  # Client cleanup survives absent/unhealthy runtimes and auth DELETE failures.
        service=None
        try:
            service=opencode.for_workspace(workspace,start=False)
            with service.state_lock:
                providers.remove(service,provider_id)
        except Exception:
            # Never include runtime exception bodies; they may contain credentials.
            logger.warning("Runtime auth cleanup could not be confirmed for workspace %s; Gateway provider disconnect persisted",workspace.id)
        finally:
            if service is not None:
                service.invalidate()

@router.post("/workspaces/{workspace_id}/providers/{provider_id}/test")
def test_provider(workspace_id: uuid.UUID,provider_id: str,user: User=Depends(require_user),db: Session=Depends(get_db)):
    row,service=_workspace_service(db,user,workspace_id)
    return {"connected":not providers.is_locally_disconnected(db,row,provider_id) and providers.is_connected(service,provider_id)}

@router.post("/workspaces/{workspace_id}/providers/{provider_id}/oauth/authorize")
def provider_oauth_authorize(workspace_id: uuid.UUID,provider_id: str,data: OAuthAuthorize,user: User=Depends(require_user),db: Session=Depends(get_db)):
    require_advanced(db,user)
    if not policy.provider_allowed(policy.load(db),provider_id): raise HTTPException(403,'Provider is disabled by platform policy')
    _,service=_workspace_service(db,user,workspace_id)
    with service.state_lock:
        return providers.oauth_authorize(service,provider_id,data.method,data.inputs)

@router.post("/workspaces/{workspace_id}/providers/{provider_id}/oauth/callback")
def provider_oauth_callback(workspace_id: uuid.UUID,provider_id: str,data: OAuthCallback,user: User=Depends(require_user),db: Session=Depends(get_db)):
    require_advanced(db,user)
    if not policy.provider_allowed(policy.load(db),provider_id): raise HTTPException(403,'Provider is disabled by platform policy')
    workspace,service=_workspace_service(db,user,workspace_id)
    with opencode.workspace_lock(workspace),service.state_lock:
        session_lifecycle.lock_workspace(db,workspace)
        accepted=providers.oauth_callback(service,provider_id,data.method,data.code)
        # OAuth state belongs to OpenCode. Retire any old Gateway API-key binding.
        row=db.scalar(select(ProviderCredential).where(ProviderCredential.workspace_id==workspace_id,ProviderCredential.provider_id==provider_id))
        if row is not None:
            db.delete(row)
        if accepted:
            require_advanced(db,user,start=True)
            providers.record_connection(db,workspace,provider_id,connected=True)
        db.commit()
        return {"connected":bool(accepted)}
