import uuid
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import ExecutionEvent, Project, ProviderCredential, User, Workspace, WorkspaceSession
from ..services import credentials, github, opencode, policy, providers
from ..services import workspaces as manager
from .dependencies import require_user, require_workspace_entitlement

router=APIRouter(prefix="/api",tags=["workspaces"],dependencies=[Depends(require_workspace_entitlement)])

class CreateProject(BaseModel):
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)
    project_name: str=Field(min_length=1,max_length=120,pattern=r"^[^\r\n\x00]+$")
    source_type: Literal["github","blank","template"]="blank"
    repository: str|None=None
    branch: str|None=None
    template: str|None=None

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
    api_key: str=Field(min_length=8,max_length=4000)

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
    from ..config import settings
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
    connection=github.connection_for(db,user)
    if not manager.valid_repository(data.repository) or not manager.valid_branch(data.branch):
        raise HTTPException(422,"A valid repository (owner/name) and branch are required")
    repo=next((r for r in github.list_repositories(connection) if r["full_name"]==data.repository),None)
    if repo is None:
        raise HTTPException(404,"Repository is not available to the connected GitHub installation")
    return {"clone_url":repo["clone_url"],"branch":data.branch,"token":github.installation_token(connection),"repository_id":repo["id"],"installation_id":connection.installation_id}

@router.post("/projects",status_code=201)
def create_project(data: CreateProject,user: User=Depends(require_user),db: Session=Depends(get_db)):
    github_source=_github_source(db,user,data) if data.source_type=="github" else None
    project,workspace=manager.create(db,user,data.project_name,data.source_type,data.template,data.repository,data.branch,github_source)
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
    connection=github.connection_for(db,user)
    if not manager.valid_repository(data.repository):
        raise HTTPException(422,"A repository in owner/name form is required")
    branch=data.branch or "work"
    if not manager.valid_branch(branch):
        raise HTTPException(422,"A valid branch name is required")
    repo=next((r for r in github.list_repositories(connection) if r["full_name"]==data.repository),None)
    if repo is None:
        raise HTTPException(404,"Repository is not available to the connected GitHub installation")
    project.repository=data.repository
    project.github_repository_id=repo["id"]
    project.github_installation_id=connection.installation_id
    project.remote_url=repo["clone_url"]
    project.remote_branch=branch
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
    return workspace,project,state

@router.get("/workspaces/{workspace_id}/git/status")
def git_status(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    return _git_status(db,user,workspace_id)[2]

@router.get("/workspaces/{workspace_id}/changes")
def changes(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    return git_status(workspace_id,user,db)["changes"]

@router.get("/workspaces/{workspace_id}/diff")
def diff(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    return manager.diff(manager.owned(db,Workspace,workspace_id,user.id))

@router.get("/workspaces/{workspace_id}/logs")
def logs(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    manager.owned(db,Workspace,workspace_id,user.id)
    rows=db.scalars(select(ExecutionEvent).join(WorkspaceSession,ExecutionEvent.session_id==WorkspaceSession.id).where(WorkspaceSession.workspace_id==workspace_id,WorkspaceSession.user_id==user.id).order_by(ExecutionEvent.id.desc()).limit(200))
    return [{"id":r.id,"type":r.kind,"created_at":r.created_at} for r in rows]

@router.post("/workspaces/{workspace_id}/git/commit")
def commit(workspace_id: uuid.UUID,data: CommitRequest,user: User=Depends(require_user),db: Session=Depends(get_db)):
    return manager.commit(manager.owned(db,Workspace,workspace_id,user.id),user,data.message)

@router.post("/workspaces/{workspace_id}/git/push")
def push(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    workspace,project=_workspace_and_project(db,user,workspace_id)
    if not project.remote_url or not project.remote_branch:
        raise HTTPException(503,"This project has no GitHub remote; publish or create it from a GitHub repository first")
    connection=github.connection_for(db,user)
    state=manager.status(workspace)
    if not state["head"]:
        raise HTTPException(409,"There is no commit to push")
    token=github.installation_token(connection)
    manager.push_remote(workspace,project.remote_url,project.remote_branch,token)
    verified=github.verify_remote_commit(connection,project.repository,project.remote_branch,state["head"])
    if not verified:
        raise HTTPException(502,"Push finished but the expected commit was not verified on the remote branch")
    workspace.status="pushed"; db.commit()
    return {"pushed":True,"branch":project.remote_branch,"head":state["head"],"verified":True}

@router.post("/workspaces/{workspace_id}/sessions",status_code=201)
def new_session(workspace_id: uuid.UUID,data: NewSession,user: User=Depends(require_user),db: Session=Depends(get_db)):
    row=manager.owned(db,Workspace,workspace_id,user.id)
    runtime_id=opencode.for_workspace(row).create_session(data.title)
    session=WorkspaceSession(workspace_id=row.id,user_id=user.id,opencode_session_id=runtime_id,title=data.title)
    db.add(session); db.commit(); db.refresh(session)
    return session_payload(session)

@router.get("/workspaces/{workspace_id}/sessions")
def sessions(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    manager.owned(db,Workspace,workspace_id,user.id)
    return [session_payload(s) for s in db.scalars(select(WorkspaceSession).where(WorkspaceSession.workspace_id==workspace_id,WorkspaceSession.user_id==user.id).order_by(WorkspaceSession.created_at.desc()))]

@router.get("/sessions/{session_id}")
def session(session_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    return session_payload(manager.owned(db,WorkspaceSession,session_id,user.id))

def _workspace_service(db,user,workspace_id):
    row=manager.owned(db,Workspace,workspace_id,user.id)
    opencode.configure_policy(policy.load(db))
    service=opencode.for_workspace(row)
    _install_stored_credentials(db,row,service)
    return row,service

def _install_stored_credentials(db,workspace,service):
    rows=db.scalars(select(ProviderCredential).where(ProviderCredential.workspace_id==workspace.id,ProviderCredential.user_id==workspace.user_id))
    for row in rows:
        try:
            providers.set_api_key(service,row.provider_id,credentials.decrypt(row.ciphertext))
        except Exception:
            # A stale or undecryptable credential must not break provider discovery.
            continue

@router.post("/workspaces/{workspace_id}/runtime/connect")
def connect_workspace_runtime(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    """Start/attach the user's private loopback OpenCode runtime and return safe properties only."""
    workspace,service=_workspace_service(db,user,workspace_id)
    health=service.health()
    provider_rows=policy.filter_providers(providers.discover(service),policy.load(db))
    agents=agent_choices(service)
    return {
        "connected":True,
        "workspace_id":str(workspace.id),
        "runtime_scope":"workspace",
        "transport":"loopback",
        "healthy":bool(health.get("healthy")),
        "version":health.get("version"),
        "providers":len(provider_rows),
        "connected_providers":sum(1 for row in provider_rows if row.get("connected")),
        "agents":agents,
    }

@router.get("/workspaces/{workspace_id}/providers")
def available_providers(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    _,service=_workspace_service(db,user,workspace_id)
    return policy.filter_providers(providers.discover(service),policy.load(db))

@router.get("/workspaces/{workspace_id}/agents")
def available_agents(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    row=manager.owned(db,Workspace,workspace_id,user.id)
    opencode.configure_policy(policy.load(db))
    return agent_choices(opencode.for_workspace(row))

def agent_choices(service):
    rows=service.request("GET","/agent")
    if not isinstance(rows,list): raise HTTPException(502,"Runtime returned an invalid agent list")
    return [{"id":r["name"],"name":r["name"],"description":str(r.get("description", ""))[:500]} for r in rows
            if isinstance(r,dict) and isinstance(r.get("name"),str) and 0<len(r["name"])<=120
            and not r.get("hidden") and r.get("mode") in {"primary","all"}]

@router.post("/workspaces/{workspace_id}/providers/{provider_id}/credentials")
def set_provider_credential(workspace_id: uuid.UUID,provider_id: str,data: ApiKeyCredential,user: User=Depends(require_user),db: Session=Depends(get_db)):
    if not policy.provider_allowed(policy.load(db),provider_id): raise HTTPException(403,'Provider is disabled by platform policy')
    if not credentials.available():
        raise HTTPException(503,'Encrypted credential storage must be configured first')
    workspace,service=_workspace_service(db,user,workspace_id)
    try:
        providers.set_api_key(service,provider_id,data.api_key)
    except Exception:
        raise HTTPException(502,"The runtime did not accept this credential")
    persisted=False
    if credentials.available():
        row=db.scalar(select(ProviderCredential).where(ProviderCredential.workspace_id==workspace.id,ProviderCredential.provider_id==provider_id))
        if row is None:
            row=ProviderCredential(workspace_id=workspace.id,user_id=user.id,provider_id=provider_id,ciphertext="",last4="")
            db.add(row)
        row.ciphertext=credentials.encrypt(data.api_key)
        row.last4=data.api_key[-4:]
        db.commit(); persisted=True
    return {"connected":True,"provider_id":provider_id,"last4":data.api_key[-4:],"persisted":persisted}

@router.delete("/workspaces/{workspace_id}/providers/{provider_id}",status_code=204)
def remove_provider_credential(workspace_id: uuid.UUID,provider_id: str,user: User=Depends(require_user),db: Session=Depends(get_db)):
    workspace,service=_workspace_service(db,user,workspace_id)
    providers.remove(service,provider_id)
    row=db.scalar(select(ProviderCredential).where(ProviderCredential.workspace_id==workspace.id,ProviderCredential.provider_id==provider_id))
    if row is not None:
        db.delete(row); db.commit()

@router.post("/workspaces/{workspace_id}/providers/{provider_id}/test")
def test_provider(workspace_id: uuid.UUID,provider_id: str,user: User=Depends(require_user),db: Session=Depends(get_db)):
    _,service=_workspace_service(db,user,workspace_id)
    return {"connected":providers.is_connected(service,provider_id)}

@router.post("/workspaces/{workspace_id}/providers/{provider_id}/oauth/authorize")
def provider_oauth_authorize(workspace_id: uuid.UUID,provider_id: str,data: OAuthAuthorize,user: User=Depends(require_user),db: Session=Depends(get_db)):
    if not policy.provider_allowed(policy.load(db),provider_id): raise HTTPException(403,'Provider is disabled by platform policy')
    _,service=_workspace_service(db,user,workspace_id)
    return providers.oauth_authorize(service,provider_id,data.method,data.inputs)

@router.post("/workspaces/{workspace_id}/providers/{provider_id}/oauth/callback")
def provider_oauth_callback(workspace_id: uuid.UUID,provider_id: str,data: OAuthCallback,user: User=Depends(require_user),db: Session=Depends(get_db)):
    if not policy.provider_allowed(policy.load(db),provider_id): raise HTTPException(403,'Provider is disabled by platform policy')
    _,service=_workspace_service(db,user,workspace_id)
    accepted=providers.oauth_callback(service,provider_id,data.method,data.code)
    return {"connected":bool(accepted)}
