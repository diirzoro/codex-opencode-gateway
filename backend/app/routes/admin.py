from datetime import datetime, timezone
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import GithubConnection, Plan, PlatformPolicy, Project, ProviderCredential, User, Workspace, WorkspaceSession
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
    rows = db.scalars(select(User).order_by(User.created_at.desc()))
    return [{**user_payload(u), "plan_id": u.plan_id, "plan": u.plan.name if u.plan else None} for u in rows]

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
    if "plan_id" in data.model_fields_set:
        if data.plan_id is not None and db.get(Plan, data.plan_id) is None:
            raise HTTPException(422, "Unknown plan")
        user.plan_id = data.plan_id
    if data.status is not None:
        from .management import stop_work, revoke
        if data.status != 'active': stop_work(db, user)
        revoke(db, user)
        user.status = data.status
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
