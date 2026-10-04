import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, Project, Workspace, WorkspaceSession, ExecutionEvent
from ..services import workspaces as manager, opencode, providers, github
from .dependencies import require_user

router=APIRouter(prefix="/api",tags=["workspaces"])

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

def session_payload(row):
    return {"id":str(row.id),"workspace_id":str(row.workspace_id),"title":row.title,"status":row.status,"created_at":row.created_at}

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
def github_status(user: User=Depends(require_user)):
    return github.connection_status()

@router.get("/templates")
def templates(user: User=Depends(require_user)):
    return [{"id":key,"name":key} for key in manager.TEMPLATES]

@router.post("/projects",status_code=201)
def create_project(data: CreateProject,user: User=Depends(require_user),db: Session=Depends(get_db)):
    project,workspace=manager.create(db,user,data.project_name,data.source_type,data.template,data.repository,data.branch)
    return {"project":manager.project_payload(project),"workspace":manager.workspace_payload(workspace)}

@router.post("/workspaces",status_code=201)
def create_workspace(data: CreateProject,user: User=Depends(require_user),db: Session=Depends(get_db)):
    # Same creation transaction, not a competing implementation.
    return create_project(data,user,db)

@router.get("/projects")
def projects(user: User=Depends(require_user),db: Session=Depends(get_db)):
    return [manager.project_payload(p) for p in db.scalars(select(Project).where(Project.user_id==user.id).order_by(Project.created_at.desc()))]

@router.get("/projects/{project_id}")
def project(project_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    return manager.project_payload(manager.owned(db,Project,project_id,user.id))

@router.patch("/projects/{project_id}")
def rename(project_id: uuid.UUID,data: RenameProject,user: User=Depends(require_user),db: Session=Depends(get_db)):
    row=manager.owned(db,Project,project_id,user.id); row.name=data.name; db.commit()
    return manager.project_payload(row)

@router.delete("/projects/{project_id}")
def delete_project(project_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    manager.owned(db,Project,project_id,user.id)
    raise HTTPException(409,"Deletion is unavailable until verified remote backup and retention safeguards are implemented")

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

@router.get("/workspaces/{workspace_id}/git/status")
def git_status(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    return manager.status(manager.owned(db,Workspace,workspace_id,user.id))

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
    manager.owned(db,Workspace,workspace_id,user.id)
    raise HTTPException(503,"GitHub App connection and remote verification are not implemented; no push was attempted")

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

@router.get("/workspaces/{workspace_id}/providers")
def available_providers(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    row=manager.owned(db,Workspace,workspace_id,user.id)
    return providers.discover(opencode.for_workspace(row))
