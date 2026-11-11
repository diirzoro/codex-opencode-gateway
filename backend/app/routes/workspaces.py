import uuid
from datetime import datetime, timezone
from typing import Literal


from fastapi.responses import FileResponse
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..config import settings
from ..security.origins import same_origin
from ..database import get_db
from ..models import ExecutionEvent, Project, ProjectNativeSessionBinding, User, Workspace, WorkspaceSession
from ..services import github, policy, preview, attachment_reader
from ..services import workspaces as manager
from ..services.entitlements import access_payload, require_advanced
from .dependencies import require_user, require_workspace_entitlement
from . import native_sessions

router=APIRouter(prefix="/api",tags=["workspaces"],dependencies=[Depends(require_workspace_entitlement)])

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

class PublishProject(BaseModel):
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)
    repository: str=Field(min_length=3,max_length=255)
    branch: str|None=Field(default=None,max_length=120)

def _workspace_and_project(db,user,workspace_id):
    workspace=manager.owned(db,Workspace,workspace_id,user.id)
    project=db.get(Project,workspace.project_id)
    return workspace,project

@router.get("/opencode/display-policy")
def account_provider_display_policy(user: User=Depends(require_user),db: Session=Depends(get_db)):
    """Expose only admin display settings; OpenCode remains provider/model registry.

    This control-plane metadata has no credentials or full Native model catalog.
    """
    rules=policy.load(db).as_payload()
    return {key:rules[key] for key in (
        "allowed_providers","hidden_providers","allowed_models","hidden_models","updated_at")}


@router.get("/opencode/status")
def runtime_status(user: User=Depends(require_user)):
    # Platform runtime mode only. Native health is read by the browser directly.
    mode=native_sessions.deployment()
    return {"runtime_mode":"native-"+mode if mode else "disabled",
            "healthy":None,"status":"check_native_from_browser" if mode else "disabled"}

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
    # Serialize this owner's simultaneous imports against the unified quota.
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    manager.require_account_local_headroom(db,user.id)
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
    return [manager.project_payload(p) for p in db.scalars(select(Project).where(Project.user_id==user.id,Project.archived_at.is_(None),manager.visible_project_predicate(user.id)).order_by(Project.created_at.desc()))]

@router.get("/projects/{project_id}")
def project(project_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    return manager.project_payload(manager.owned(db,Project,project_id,user.id))

class BindProjectNativeSession(BaseModel):
    """The browser already created the Native session directly through Nginx."""
    model_config=ConfigDict(extra="forbid")
    workspace_id:uuid.UUID
    native_session_id:str=Field(min_length=1,max_length=120,pattern=r"^[A-Za-z0-9_-]+$")
    replace_legacy_opencode:bool=False


def _native_binding_payload(binding):
    return {"project_id":str(binding.project_id),
            "workspace_id":str(binding.workspace_id),
            "native_session_id":binding.native_session_id}


@router.get("/projects/{project_id}/native-binding")
def native_binding(project_id:uuid.UUID,user:User=Depends(require_user),
                   db:Session=Depends(get_db)):
    """Read Platform-owned binding only. NEVER contact the Native service."""
    manager.owned(db,Project,project_id,user.id)
    binding=db.get(ProjectNativeSessionBinding,project_id)
    if binding is None:return {"project_id":str(project_id),"binding":None}
    if binding.user_id!=user.id:raise HTTPException(404,"Project not found")
    return {"project_id":str(project_id),"binding":_native_binding_payload(binding)}


@router.post("/projects/{project_id}/native-binding")
def bind_native_session(project_id:uuid.UUID,data:BindProjectNativeSession,
                        request:Request,user:User=Depends(require_user),
                        db:Session=Depends(get_db)):
    """Persist an immutable project-to-session reference; no Native API calls.

    A legacy multi-session Project needs an explicit owner-reviewed recovery
    instead of silently choosing the newest session and losing history.
    """
    if not same_origin(request.headers.get("origin"),settings.public_base_url):
        raise HTTPException(403,"Project binding requires the Gateway origin")
    project=db.scalar(select(Project).where(
        Project.id==project_id,Project.user_id==user.id).with_for_update())
    if project is None:raise HTTPException(404,"Project not found")
    if project.archived_at is not None:
        raise HTTPException(409,"Restore this project before binding a conversation")
    workspace=manager.owned(db,Workspace,data.workspace_id,user.id)
    if workspace.project_id!=project.id:
        raise HTTPException(404,"Workspace does not belong to this project")
    current=db.get(ProjectNativeSessionBinding,project.id)
    if current is not None:
        if (current.user_id!=user.id or current.workspace_id!=workspace.id):
            raise HTTPException(409,"This project already has another persistent Native session")
        if current.native_session_id==data.native_session_id:
            return _native_binding_payload(current)
        # Explicit one-way conversion of a TEST-only legacy OpenCode identifier.
        # Never infer consent, never migrate LIVE, and never permit Pi -> OpenCode.
        if (data.replace_legacy_opencode and native_sessions.deployment()=="test"
                and current.native_session_id.startswith("ses_")
                and data.native_session_id.startswith("pi_")):
            current.native_session_id=data.native_session_id
            db.commit()
            return _native_binding_payload(current)
        raise HTTPException(409,"This project already has another persistent Native session")
    binding=ProjectNativeSessionBinding(project_id=project.id,user_id=user.id,
        workspace_id=workspace.id,native_session_id=data.native_session_id)
    db.add(binding)
    try:db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,
            "Native session is already bound or another request claimed this project") from None
    return _native_binding_payload(binding)


@router.patch("/projects/{project_id}")
def rename(project_id: uuid.UUID,data: RenameProject,user: User=Depends(require_user),db: Session=Depends(get_db)):
    row=manager.owned(db,Project,project_id,user.id); row.name=data.name
    db.execute(update(Workspace).where(Workspace.project_id==row.id,Workspace.status.not_in(["cache_expiring","cache_expired"])).values(last_activity_at=datetime.now(timezone.utc)))
    db.commit()
    return manager.project_payload(row)

@router.post("/projects/{project_id}/archive")
def archive_project(project_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    row=manager.owned(db,Project,project_id,user.id)
    row.archived_at=datetime.now(timezone.utc)
    db.execute(update(Workspace).where(Workspace.project_id==row.id,Workspace.status.not_in(["cache_expiring","cache_expired"])).values(last_activity_at=datetime.now(timezone.utc)))
    db.commit()
    return manager.project_payload(row)

class ConfirmLocalProjectDelete(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirm_name:str=Field(min_length=1,max_length=120)
    confirmation:Literal['DELETE LOCAL PROJECT']


@router.delete("/projects/{project_id}")
def delete_project(project_id:uuid.UUID,data:ConfirmLocalProjectDelete,
                   user:User=Depends(require_user),db:Session=Depends(get_db)):
    """Delete one confirmed owned Project after its Native session is deleted.

    Platform removes only administrative links, workspaces and owned files.
    The browser calls OpenCode Native directly to delete the session first;
    this route never queries or invokes any Native API.
    """
    import shutil
    from sqlalchemy import delete,inspect
    from ..models import PreviewRuntimeLease
    project=db.scalar(select(Project).where(
        Project.id==project_id,Project.user_id==user.id).with_for_update())
    if project is None:raise HTTPException(404,'Project not found')
    if data.confirm_name!=project.name:
        raise HTTPException(400,'Type the project name exactly to confirm local deletion')
    rows=list(db.scalars(select(Workspace).where(
        Workspace.project_id==project.id,Workspace.user_id==user.id).with_for_update()))
    # Preview leases may be running or contain tasks outside the Native
    # conversation path; refuse rather than stopping unrelated runtimes.
    if inspect(db.connection()).has_table('preview_runtime_leases') and rows:
        live=db.scalar(select(PreviewRuntimeLease.id).where(
            PreviewRuntimeLease.workspace_id.in_([w.id for w in rows]),
            PreviewRuntimeLease.state.in_(['queued','starting','running'])).limit(1))
        if live:raise HTTPException(409,'Stop this project preview before deleting local files')
    # The user-confirmed browser flow has already removed the Native session.
    # Retire its Platform-only mapping as part of deleting the Project.
    binding=db.get(ProjectNativeSessionBinding,project.id)
    if binding is not None:
        db.delete(binding)
        db.flush()
    paths=[]
    for row in rows:
        path=manager.root_for(row,allow_expired=True)
        if path.is_symlink() or path.parent.is_symlink() or path.parent.parent.is_symlink():
            raise HTTPException(403,'Unsafe project worktree; manual review required')
        paths.append(path)
    ids=[w.id for w in rows]
    if ids:
        # One project = one conversation: remove the session + event rows with
        # the project (Native still owns the actual session history/state).
        db.execute(delete(ExecutionEvent).where(ExecutionEvent.session_id.in_(
            select(WorkspaceSession.id).where(WorkspaceSession.workspace_id.in_(ids)))))
        db.execute(delete(WorkspaceSession).where(WorkspaceSession.workspace_id.in_(ids)))
        if inspect(db.connection()).has_table('preview_runtime_leases'):
            db.execute(delete(PreviewRuntimeLease).where(PreviewRuntimeLease.workspace_id.in_(ids)))
        db.execute(delete(Workspace).where(Workspace.id.in_(ids),Workspace.user_id==user.id))
    source_type=project.source_type
    db.delete(project)
    try:
        # Resolve all FK dependencies before deleting any physical files.
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'Other Platform records still reference this project') from None
    # Use existing paths computed exclusively from owned Workspace rows.
    try:
        for path in paths:
            if path.exists():
                shutil.rmtree(path)
    except OSError:
        db.rollback()
        raise HTTPException(503,'Could not remove project worktree; project record was retained') from None
    db.commit()
    return {'deleted':True,'project_id':str(project_id),'source_type':source_type,
            'remote_repository_deleted':False,'local_worktrees_removed':len(paths)}


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

@router.get("/workspace-context")
def restore_workspace_context(workspace_id: uuid.UUID|None=None,session_id: uuid.UUID|None=None,
                              user: User=Depends(require_user),db: Session=Depends(get_db)):
    from ..services.workspace_context import restore
    return restore(db,user,workspace_id,session_id)

@router.get("/workspaces")
def workspaces(user: User=Depends(require_user),db: Session=Depends(get_db)):
    return [manager.workspace_payload(w) for w in db.scalars(select(Workspace).join(Project,Project.id==Workspace.project_id).where(Workspace.user_id==user.id,Project.user_id==user.id,Project.archived_at.is_(None),manager.visible_project_predicate(user.id)).order_by(Workspace.created_at.desc()))]

@router.get("/workspaces/{workspace_id}")
def workspace(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    row=manager.owned(db,Workspace,workspace_id,user.id)
    payload=manager.workspace_payload(row)
    # Filesystem identity for the existing Workspace/Pi integration.
    # Project location is platform metadata; no AI service-enable gate applies.
    payload["native_directory"]=str(manager.root_for(row,allow_expired=True))
    return payload

@router.post("/workspaces/{workspace_id}/attachments/pi-preflight")
async def pi_attachment_preflight(workspace_id:uuid.UUID,request:Request,
                                  file:UploadFile=File(...),
                                  user:User=Depends(require_user),
                                  db:Session=Depends(get_db)):
    """Security-only admission before sending bytes directly to Pi Native.

    Never executes, summarizes, extracts or stores uploaded content.
    """
    if not same_origin(request.headers.get("origin"),settings.public_base_url):
        raise HTTPException(403,"Attachment preflight requires the Gateway origin")
    workspace=manager.owned(db,Workspace,workspace_id,user.id)
    project=manager.owned(db,Project,workspace.project_id,user.id)
    if workspace.project_id!=project.id or project.archived_at is not None:
        raise HTTPException(403,"The selected project is unavailable")
    # Starlette's UploadFile can be spooled to disk; enforce a real size cap.
    raw=await file.read(attachment_reader.PI_UPLOAD_MAX_BYTES+1)
    try:
        return await run_in_threadpool(attachment_reader.pi_upload_preflight,file.filename,raw)
    finally:
        await file.close()


@router.get("/workspaces/{workspace_id}/preview/capabilities")
def workspace_preview_capabilities(workspace_id: uuid.UUID,user: User=Depends(require_user),
                                   db: Session=Depends(get_db)):
    workspace=manager.owned(db,Workspace,workspace_id,user.id)
    return preview.detect(workspace)


@router.get("/workspaces/{workspace_id}/preview/plan")
def workspace_preview_plan(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    from ..services.preview_runner import plan
    return plan(manager.owned(db,Workspace,workspace_id,user.id))


@router.get("/workspaces/{workspace_id}/preview/status")
def workspace_preview_status(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    from ..services.preview_runner import status
    return status(manager.owned(db,Workspace,workspace_id,user.id))


@router.post("/workspaces/{workspace_id}/preview/start")
def workspace_preview_start(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db),fresh: bool=False):
    from ..services.preview_runner import start
    workspace=manager.owned(db,Workspace,workspace_id,user.id)
    return start(workspace,fresh=True) if fresh else start(workspace)


@router.post("/workspaces/{workspace_id}/preview/stop")
def workspace_preview_stop(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    from ..services.preview_runner import stop
    return stop(manager.owned(db,Workspace,workspace_id,user.id))


@router.post("/workspaces/{workspace_id}/preview/access")
def workspace_preview_access(workspace_id: uuid.UUID, request: Request,
                             user: User=Depends(require_user), db: Session=Depends(get_db)):
    from ..services import preview_access
    workspace=manager.owned(db,Workspace,workspace_id,user.id)
    return preview_access.mint(workspace,getattr(request.state,'auth_session',None),user)


@router.get("/workspaces/{workspace_id}/preview/live/{asset_path:path}")
def workspace_preview_live(workspace_id: uuid.UUID,asset_path: str,request: Request,user: User=Depends(require_user),db: Session=Depends(get_db)):
    from ..services.preview_runner import fetch_asset
    workspace=manager.owned(db,Workspace,workspace_id,user.id)
    # Preserve application routing/query parameters (including repeated values).
    # Starlette's path parameter excludes the query string.
    path = "/" + asset_path
    if request.url.query:
        path += "?" + request.url.query
    response=fetch_asset(workspace, path)
    # Mark only the authenticated, owned and sandboxed preview response.
    # Middleware must not infer embedding permission from a URL alone.
    request.state.owned_preview_response=True
    return response


@router.get("/workspaces/{workspace_id}/preview")
def workspace_preview(workspace_id: uuid.UUID,path: str=Query(default="index.html",max_length=1000),user: User=Depends(require_user),db: Session=Depends(get_db)):
    return preview.render(manager.owned(db,Workspace,workspace_id,user.id),path)

@router.get("/workspaces/{workspace_id}/logs")
def logs(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    manager.owned(db,Workspace,workspace_id,user.id)
    rows=db.scalars(select(ExecutionEvent).join(WorkspaceSession,ExecutionEvent.session_id==WorkspaceSession.id).where(WorkspaceSession.workspace_id==workspace_id,WorkspaceSession.user_id==user.id).order_by(ExecutionEvent.id.desc()).limit(200))
    return [{"id":r.id,"type":r.kind,"created_at":r.created_at} for r in rows]

@router.get("/workspaces/{workspace_id}/export")
def export_workspace(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    workspace=manager.owned(db,Workspace,workspace_id,user.id)
    path=manager.export(workspace)
    return FileResponse(path,media_type="application/zip",filename="workspace-source.zip",
                        background=BackgroundTask(path.unlink,missing_ok=True))

@router.get("/workspaces/{workspace_id}/storage")
def storage(workspace_id: uuid.UUID,user: User=Depends(require_user),db: Session=Depends(get_db)):
    workspace=manager.owned(db,Workspace,workspace_id,user.id)
    # Both GitHub and local projects return the exact same owner-wide totals.
    return manager.storage_payload(workspace,db)

