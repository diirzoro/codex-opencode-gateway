"""Client dashboard: real owned data only, aggregated for the account view."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import Project, ProviderCredential, User, Workspace, WorkspaceSession
from ..services import github, session_lifecycle
from ..services.accounts import user_payload
from ..services.workspaces import project_payload, workspace_payload
from .dependencies import require_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("")
def dashboard(user: User = Depends(require_user), db: Session = Depends(get_db)):
    projects = list(db.scalars(select(Project).where(Project.user_id == user.id, Project.archived_at.is_(None)).order_by(Project.created_at.desc())))
    workspaces = list(db.scalars(select(Workspace).join(Project, Project.id == Workspace.project_id).where(Workspace.user_id == user.id, Project.archived_at.is_(None)).order_by(Workspace.created_at.desc())))
    sessions = list(db.scalars(select(WorkspaceSession).join(Workspace, Workspace.id == WorkspaceSession.workspace_id).join(Project, Project.id == Workspace.project_id).where(WorkspaceSession.user_id == user.id, Project.archived_at.is_(None)).order_by(WorkspaceSession.created_at.desc())))
    session_states = session_lifecycle.states(db, sessions)
    sessions = [s for s in sessions if session_states[s.id] not in {"deleted", "archived"}]
    credentials_count = db.scalar(select(func.count()).select_from(ProviderCredential).where(ProviderCredential.user_id == user.id)) or 0
    by_project = {}
    for workspace in workspaces:
        by_project.setdefault(str(workspace.project_id), []).append(workspace)
    session_counts = {}
    for session in sessions:
        session_counts[str(session.workspace_id)] = session_counts.get(str(session.workspace_id), 0) + 1
    payload_projects = []
    for project in projects:
        items = []
        for workspace in by_project.get(str(project.id), []):
            data = workspace_payload(workspace)
            data["session_count"] = session_counts.get(str(workspace.id), 0)
            items.append(data)
        payload_projects.append({**project_payload(project), "workspaces": items})
    return {
        "profile": {**user_payload(user), "plan": user.plan.name if user.plan else None},
        "plan": {"name": user.plan.name, "active": user.plan.active} if user.plan else None,
        "projects": payload_projects,
        "recent_sessions": [session_lifecycle.payload(s, session_states[s.id]) for s in sessions[:10]],
        "recent_workspaces": [{**workspace_payload(w),"session_count":session_counts.get(str(w.id),0)} for w in sorted(workspaces,key=lambda w:w.last_activity_at,reverse=True)[:10]],
        "counts": {"projects": len(projects), "workspaces": len(workspaces), "sessions": len(sessions), "credentials": credentials_count},
        "github": github.connection_status(db, user),
        "runtime": {"mode": settings.runtime_mode, "healthy": None},
    }
