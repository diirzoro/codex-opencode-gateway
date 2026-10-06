from datetime import datetime, timedelta, timezone
import json
import uuid as _uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import GithubConnection, Plan, PlatformPolicy, Project, ProviderCredential, Subscription, User, Workspace, WorkspaceSession
from ..models.platform import get_policy
from ..services import opencode
from ..services.accounts import user_payload
from .dependencies import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])

class PlanIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9_]+$")
    price_cents: int = Field(ge=0, le=10000000)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    duration_days: int = Field(ge=1, le=3650)
    active: bool = True
    sort_order: int = Field(default=0, ge=0, le=10000)

class PlanPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    price_cents: int | None = Field(default=None, ge=0, le=10000000)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    duration_days: int | None = Field(default=None, ge=1, le=3650)
    active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10000)

class UserAdminPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: int | None = None
    status: str | None = Field(default=None, pattern="^(active|suspended)$")
    role: str | None = Field(default=None, pattern="^(customer|support|finance|admin|owner)$")
    trial_days: int | None = Field(default=None, ge=0, le=3650)

class PolicyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowed_providers: list[str] = Field(default_factory=list, max_length=200)
    allowed_models: list[str] = Field(default_factory=list, max_length=500)
    allowed_tools: list[str] = Field(default_factory=list, max_length=500)
    require_tool_approval: bool = True

def _count(db, model, *conditions):
    return db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0

def _runtime_health():
    if settings.runtime_mode != "local":
        return {"mode": settings.runtime_mode, "healthy": False, "detail": "Local runtime is disabled"}
    try:
        health = opencode.shared_health()
        return {"mode": settings.runtime_mode, "healthy": True, "version": health.get("version")}
    except HTTPException:
        return {"mode": settings.runtime_mode, "healthy": False, "detail": "Runtime is not reachable"}

def plan_payload(row: Plan) -> dict:
    return {"id": row.id, "code": row.code, "name": row.name, "price_cents": row.price_cents, "currency": row.currency, "duration_days": row.duration_days, "active": bool(row.active), "sort_order": row.sort_order}

@router.get("/users")
def users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = list(db.scalars(select(User).order_by(User.created_at.desc())))
    project_counts = dict(db.execute(select(Project.user_id, func.count()).group_by(Project.user_id)).all())
    workspace_counts = dict(db.execute(select(Workspace.user_id, func.count()).group_by(Workspace.user_id)).all())
    return [{**user_payload(u), "plan_id": u.plan_id, "plan": u.plan.name if u.plan else None,
             "projects_count": project_counts.get(u.id, 0), "workspaces_count": workspace_counts.get(u.id, 0)} for u in rows]

@router.patch("/users/{user_id}")
def update_user(user_id: str, data: UserAdminPatch, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    import uuid as _uuid
    try:
        user = db.get(User, _uuid.UUID(user_id))
    except ValueError:
        raise HTTPException(422, "Invalid user id")
    if user is None:
        raise HTTPException(404, "User not found")
    if user.id == actor.id or user.role == 'owner' or (actor.role != 'owner' and user.role == 'admin'):
        raise HTTPException(403, 'Cannot change this administrator account')
    if data.role is not None and actor.role != 'owner':
        raise HTTPException(403, 'Owner role required')
    if "plan_id" in data.model_fields_set:
        if data.plan_id is not None and db.get(Plan, data.plan_id) is None:
            raise HTTPException(422, "Unknown plan")
        user.plan_id = data.plan_id
    if data.status is not None:
        from .management import stop_work, revoke
        if data.status != 'active': stop_work(db, user)
        revoke(db, user)
        user.status = data.status
    if data.role is not None:
        if actor.role != 'owner': raise HTTPException(403,'Owner role required')
        from .management import revoke
        user.role=data.role; revoke(db,user)
    if data.trial_days is not None:
        now = datetime.now(timezone.utc)
        user.trial_ends_at = now + timedelta(days=data.trial_days)
        if user.trial_started_at is None: user.trial_started_at = now
    from .management import audit
    audit(db, actor, 'account.admin_updated', user.id)
    db.commit(); db.refresh(user)
    return {**user_payload(user), "plan_id": user.plan_id, "plan": user.plan.name if user.plan else None}

@router.get("/overview")
def overview(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    github_connected = _count(db, GithubConnection, GithubConnection.suspended.is_(False))
    return {
        "users": {
            "total": _count(db, User),
            "active": _count(db, User, User.status == "active"),
            "suspended": _count(db, User, User.status != "active"),
            "admins": _count(db, User, User.role == "admin"),
            "owners": _count(db, User, User.role == "owner"),
            "trial_active": _count(db, User, User.trial_ends_at > now),
            "trial_expired": _count(db, User, User.trial_ends_at <= now),
        },
        "projects": {"total": _count(db, Project)},
        "workspaces": {
            "total": _count(db, Workspace),
            "ready": _count(db, Workspace, Workspace.status == "ready"),
            "failed": _count(db, Workspace, Workspace.status == "failed"),
            "pushed": _count(db, Workspace, Workspace.status == "pushed"),
        },
        "sessions": {"total": _count(db, WorkspaceSession)},
        "credentials": {"stored": _count(db, ProviderCredential), "users": db.scalar(select(func.count(func.distinct(ProviderCredential.user_id)))) or 0},
        "plans": {"total": _count(db, Plan), "active": _count(db, Plan, Plan.active.is_(True))},
        "runtime": _runtime_health(),
        "integrations": {
            "github": {"configured": settings.github_configured, "connected_users": github_connected},
            "opencode": settings.runtime_mode,
            "payments": "not_available",
        },
        "payments": {"status": "not_available", "label": "Not available yet"},
        "visitors": {"status": "not_available", "label": "Not available yet"},
    }

def _user_index(db):
    return {u.id: u for u in db.scalars(select(User))}

@router.get("/projects")
def admin_projects(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    owners = _user_index(db)
    workspaces = list(db.scalars(select(Workspace)))
    session_counts = dict(db.execute(select(WorkspaceSession.workspace_id, func.count()).group_by(WorkspaceSession.workspace_id)).all())
    ws_by_project = {}
    for workspace in workspaces:
        ws_by_project.setdefault(workspace.project_id, []).append(workspace.id)
    output = []
    for project in db.scalars(select(Project).order_by(Project.created_at.desc())):
        owner = owners.get(project.user_id)
        ws_ids = ws_by_project.get(project.id, [])
        output.append({"id": str(project.id), "owner": owner.username if owner else None, "owner_email": owner.email if owner else None,
                       "name": project.name, "source_type": project.source_type, "repository": project.repository, "template": project.template,
                       "workspaces": len(ws_ids), "sessions": sum(session_counts.get(w, 0) for w in ws_ids), "archived": project.archived_at is not None, "created_at": project.created_at})
    return output

@router.get("/workspaces")
def admin_workspaces(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    owners = _user_index(db)
    projects = {p.id: p for p in db.scalars(select(Project))}
    session_counts = dict(db.execute(select(WorkspaceSession.workspace_id, func.count()).group_by(WorkspaceSession.workspace_id)).all())
    output = []
    for workspace in db.scalars(select(Workspace).order_by(Workspace.created_at.desc())):
        owner = owners.get(workspace.user_id); project = projects.get(workspace.project_id)
        output.append({"id": str(workspace.id), "owner": owner.username if owner else None, "project": project.name if project else None,
                       "status": workspace.status, "base_commit_sha": workspace.base_commit_sha, "sessions": session_counts.get(workspace.id, 0),
                       "created_at": workspace.created_at, "last_activity_at": workspace.last_activity_at})
    return output

@router.get("/sessions")
def admin_sessions(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    owners = _user_index(db)
    workspaces = {w.id: w for w in db.scalars(select(Workspace))}
    projects = {p.id: p for p in db.scalars(select(Project))}
    output = []
    for session in db.scalars(select(WorkspaceSession).order_by(WorkspaceSession.created_at.desc())):
        owner = owners.get(session.user_id); workspace = workspaces.get(session.workspace_id)
        project = projects.get(workspace.project_id) if workspace else None
        output.append({"id": str(session.id), "owner": owner.username if owner else None, "workspace": workspace.status if workspace else None,
                       "project": project.name if project else None, "title": session.title, "status": session.status, "created_at": session.created_at})
    return output

@router.get("/subscriptions")
def admin_subscriptions(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    owners = _user_index(db)
    plans = {p.id: p for p in db.scalars(select(Plan))}
    output = []
    for sub in db.scalars(select(Subscription).order_by(Subscription.created_at.desc())):
        owner = owners.get(sub.user_id)
        output.append({"id": str(sub.id), "owner": owner.username if owner else None, "owner_email": owner.email if owner else None,
                       "plan": plans[sub.plan_id].name if (sub.plan_id in plans) else None, "status": sub.status,
                       "started_at": sub.started_at, "current_period_end": sub.current_period_end, "cancelled_at": sub.cancelled_at})
    return output

@router.get("/billing/summary")
def admin_billing_summary(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    counts = {status: _count(db, Subscription, Subscription.status == status) for status in ("trial", "pending_payment", "active", "cancelled", "expired")}
    counts["total"] = _count(db, Subscription)
    return {"subscriptions": counts, "revenue": {"available": False, "label": "Not available yet"}, "payments": {"available": False, "label": "Not available yet"}}

@router.get("/billing/transactions")
def admin_billing_transactions(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {"available": False, "label": "Not available yet", "items": []}

@router.get("/reports")
def admin_reports(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {
        "counts": {"users": _count(db, User), "projects": _count(db, Project), "workspaces": _count(db, Workspace), "sessions": _count(db, WorkspaceSession), "subscriptions": _count(db, Subscription)},
        "revenue": {"available": False, "label": "Not available yet"},
        "visitors": {"available": False, "label": "Not available yet"},
    }

@router.get("/plans")
def list_plans(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(Plan).order_by(Plan.sort_order, Plan.id))
    return [plan_payload(p) for p in rows]

@router.post("/plans", status_code=201)
def create_plan(data: PlanIn, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.scalar(select(Plan).where(Plan.code == data.code)):
        raise HTTPException(409, "A plan with this code already exists")
    row = Plan(**data.model_dump())
    db.add(row); db.commit(); db.refresh(row)
    return plan_payload(row)

@router.patch("/plans/{plan_id}")
def update_plan(plan_id: int, data: PlanPatch, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.get(Plan, plan_id)
    if row is None:
        raise HTTPException(404, "Plan not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    db.commit(); db.refresh(row)
    return plan_payload(row)

@router.get("/policy")
def read_policy(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return get_policy(db).as_payload()

@router.put("/policy")
def write_policy(data: PolicyIn, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = get_policy(db)
    row.allowed_providers = json.dumps(sorted({p.strip() for p in data.allowed_providers if p.strip()}))
    row.allowed_models = json.dumps(sorted({m.strip() for m in data.allowed_models if m.strip()}))
    row.allowed_tools = json.dumps(sorted({t.strip() for t in data.allowed_tools if t.strip()}))
    row.require_tool_approval = data.require_tool_approval
    db.commit(); db.refresh(row)
    return row.as_payload()
