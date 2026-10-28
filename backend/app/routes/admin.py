from datetime import datetime, timedelta, timezone
import json
import uuid as _uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import GithubConnection, PaymentOrder, Plan, PlatformPolicy, Project, ProviderCredential, Subscription, User, Workspace, WorkspaceSession
from ..models.platform import get_policy
from ..services import opencode, github
from ..services.accounts import user_payload
from .dependencies import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])

class NativeCatalogSchedule(BaseModel):
    model_config=ConfigDict(extra='forbid')
    interval_days:Literal[7,14]

@router.get('/native/catalog-maintenance')
def native_catalog_status(_:User=Depends(require_admin)):
    from ..services import native_catalog_maintenance
    return native_catalog_maintenance.status()

@router.put('/native/catalog-maintenance')
def native_catalog_schedule(data:NativeCatalogSchedule,_:User=Depends(require_admin)):
    from ..services import native_catalog_maintenance
    return native_catalog_maintenance.configure(data.interval_days)

@router.post('/native/catalog-maintenance/refresh')
def native_catalog_refresh(_:User=Depends(require_admin)):
    from ..services import native_catalog_maintenance
    return native_catalog_maintenance.refresh()

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

from ..schemas import ProfilePatch

class UserAdminPatch(ProfilePatch):
    model_config = ConfigDict(extra="forbid")
    username: str | None = Field(default=None,min_length=6,max_length=50,pattern=r'^[A-Za-z0-9_.-]+$')
    email: EmailStr | None = None
    @field_validator('username','email')
    @classmethod
    def identity_required(cls,value):
        if value is None:raise ValueError('Identity cannot be empty')
        return value.strip().lower()
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
    hidden_providers: list[str] | None = Field(default=None,max_length=2000)
    hidden_models: dict[str,list[str]] | None = None

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
    return [{**user_payload(u), "country_id":u.country_id,"region_id":u.region_id,"city_id":u.city_id,"created_at":u.created_at,"plan_id": u.plan_id, "plan": u.plan.name if u.plan else None,
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
    values=data.model_dump(exclude_unset=True,exclude={'plan_id','status','role','trial_days'})
    if any(key in values for key in ('country_id','region_id','city_id')):
        from ..services.location_validation import validate_locations
        validate_locations(db,values.get('country_id',user.country_id),values.get('region_id',user.region_id),values.get('city_id',user.city_id))
    if 'phone' in values:
        from ..security.identities import normalized_phone
        values['phone']=normalized_phone(values['phone'],values.get('postal_code',user.postal_code))
        if values['phone'] is None:raise HTTPException(422,'Enter a valid international phone number')
    for key,value in values.items():setattr(user,key,value)
    # Database unique indexes remain authoritative, including concurrent edits.
    try:db.flush()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Email, username or phone is already registered') from None
    if 'email' in values or 'username' in values:
        from .management import revoke
        revoke(db,user)
    if 'email' in values:
        from ..models import PasswordReset,EmailVerification
        db.execute(update(PasswordReset).where(PasswordReset.user_id==user.id).values(used=True))
        db.execute(update(EmailVerification).where(EmailVerification.user_id==user.id,EmailVerification.used_at.is_(None)).values(used_at=datetime.now(timezone.utc)))
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
    if data.status=='suspended':audit(db,actor,'account.admin_suspended',user.id)
    if 'email' in values:audit(db,actor,'account.email_changed',user.id)
    db.commit(); db.refresh(user)
    return {**user_payload(user), "plan_id": user.plan_id, "plan": user.plan.name if user.plan else None}

@router.delete('/users/{user_id}')
def archive_user(user_id:_uuid.UUID,actor:User=Depends(require_admin),db:Session=Depends(get_db)):
    """Reversible account removal: preserve every owned record and foreign key."""
    user=db.scalar(select(User).where(User.id==user_id).with_for_update())
    if user is None:raise HTTPException(404,'User not found')
    if user.id==actor.id or user.role in {'admin','owner'}:
        raise HTTPException(403,'Administrator accounts cannot be removed')
    from .management import stop_work,revoke,audit
    if user.status!='archived':
        stop_work(db,user);revoke(db,user);user.status='archived'
        audit(db,actor,'account.admin_archived',user.id);db.commit()
    return {'archived':True,'data_preserved':True,'id':str(user.id)}

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
            "github": {"configured": github.configured(db), "connected_users": github_connected},
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
    totals = db.execute(
        select(PaymentOrder.currency, func.sum(PaymentOrder.amount_cents))
        .where(PaymentOrder.status == "paid")
        .group_by(PaymentOrder.currency)
        .order_by(PaymentOrder.currency)
    ).all()
    revenue = [{"currency": currency, "amount_cents": int(amount_cents or 0)} for currency, amount_cents in totals]
    return {
        "subscriptions": counts,
        "revenue": {"available": True, "items": revenue},
        "payments": {
            "available": True,
            "total": _count(db, PaymentOrder),
            "awaiting_payment": _count(db, PaymentOrder, PaymentOrder.status == "awaiting_payment"),
            "pending_review": _count(db, PaymentOrder, PaymentOrder.status == "pending_review"),
            "paid": _count(db, PaymentOrder, PaymentOrder.status == "paid"),
            "sandbox_paid": _count(db, PaymentOrder, PaymentOrder.status == "sandbox_paid"),
        },
    }

@router.get("/billing/transactions")
def admin_billing_transactions(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(
        select(PaymentOrder, User.email)
        .join(User, User.id == PaymentOrder.user_id)
        .order_by(PaymentOrder.created_at.desc())
        .limit(500)
    ).all()
    items = [
        {
            "id": str(order.id),
            "user_id": str(order.user_id),
            "email": email,
            "plan_name": order.plan_name,
            "method_label": order.method_label,
            "amount_cents": order.amount_cents,
            "currency": order.currency,
            "status": order.status,
            "payment_reference": order.payment_reference,
            "created_at": order.created_at,
            "paid_at": order.paid_at,
        }
        for order, email in rows
    ]
    return {"available": True, "items": items}

@router.get("/reports")
def admin_reports(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    totals = db.execute(
        select(PaymentOrder.currency, func.sum(PaymentOrder.amount_cents))
        .where(PaymentOrder.status == "paid")
        .group_by(PaymentOrder.currency)
        .order_by(PaymentOrder.currency)
    ).all()
    return {
        "counts": {"users": _count(db, User), "projects": _count(db, Project), "workspaces": _count(db, Workspace), "sessions": _count(db, WorkspaceSession), "subscriptions": _count(db, Subscription)},
        "revenue": {"available": True, "items": [{"currency": currency, "amount_cents": int(amount_cents or 0)} for currency, amount_cents in totals]},
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
    previous=row.as_payload()
    hidden=data.hidden_providers if data.hidden_providers is not None else previous['hidden_providers']
    selection=data.hidden_models if data.hidden_models is not None else previous['hidden_models']
    if len(selection)>1000 or sum(len(v) for v in selection.values())>10000 or any(not key or len(key)>200 or any(not v or len(v)>300 for v in values) for key,values in selection.items()) or any(not p or len(p)>200 for p in hidden):
        raise HTTPException(422,'Invalid provider/model policy')
    row.allowed_providers = json.dumps({'allowed':sorted({p.strip() for p in data.allowed_providers if p.strip()}),'hidden':sorted(set(hidden))})
    row.allowed_models = json.dumps({'allowed':sorted({m.strip() for m in data.allowed_models if m.strip()}),'hidden':{key:sorted(set(values)) for key,values in selection.items()}})
    row.allowed_tools = json.dumps(sorted({t.strip() for t in data.allowed_tools if t.strip()}))
    row.require_tool_approval = data.require_tool_approval
    db.commit(); db.refresh(row)
    return row.as_payload()

@router.get('/native/providers')
def native_provider_policy_catalog(offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=50),query:str=Query('',max_length=200),provider_id:str|None=Query(None,max_length=200),actor:User=Depends(require_admin),db:Session=Depends(get_db)):
    from . import native_sessions
    from ..services import native_provider_accounts,policy,providers
    if not native_sessions.enabled():raise HTTPException(409,'Native discovery is not enabled')
    native_sessions.admit(actor)
    data=native_sessions.metadata('GET','/provider',native_provider_accounts.root(actor))
    if not isinstance(data,dict) or not isinstance(data.get('all'),list):raise HTTPException(502,'Invalid Native catalog')
    rules=policy.load(db)
    def summary(entry):
        pid=entry['id']
        return {'id':pid,'name':str(entry.get('name',pid)), 'runtime_configured':pid in data.get('connected',[]),
                'allowed':policy.provider_allowed(rules,pid),'visible':policy.provider_visible(rules,pid),'model_count':len(entry.get('models',{}))}
    if provider_id is not None:
        entry=next((r for r in data['all'] if r.get('id')==provider_id),None)
        if entry is None:raise HTTPException(404,'Provider is not discovered by Native')
        return {'provider':summary(entry),'models':[{'id':mid,'name':str(m.get('name',mid)), 'allowed':policy.model_allowed(rules,mid,provider_id),'visible':policy.model_visible(rules,provider_id,mid)} for mid,m in entry.get('models',{}).items()]}
    term=query.casefold();rows=sorted([r for r in data['all'] if not term or term in (str(r.get('id',''))+' '+str(r.get('name',''))).casefold()],key=lambda r:r['id'])
    return {'items':[summary(r) for r in rows[offset:offset+limit]],'total':len(rows),'next_offset':offset+limit if offset+limit<len(rows) else None,
            'custom_provider_creation':False,'custom_provider_reason':'Custom Native provider configuration is protected on the shared engine. Select an existing discovered provider; customer credentials connect separately.'}

class EmailDeliveryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    provider: Literal["resend", "brevo"] = "resend"
    smtp_from: str | None = Field(default=None,min_length=6,max_length=254)
    sender_name: str | None = Field(default=None,min_length=1,max_length=120)
    api_key: str | None = Field(default=None,min_length=5,max_length=4096)

@router.put("/service-integrations/email")
def save_email_delivery(data: EmailDeliveryUpdate, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    from ..services import admin_email_config, email_delivery
    existing=admin_email_config.read(db) or {}
    accounts=dict(existing.get('provider_accounts') or {})
    old_provider=existing.get('provider','resend')
    if old_provider in email_delivery.PROVIDERS:
        accounts[old_provider]={key:value for key,value in existing.items() if key not in ('provider_accounts','inbox_api_key')}
    selected=accounts.get(data.provider,{})
    sender=data.smtp_from or selected.get('smtp_from') or email_delivery.DEFAULT_SENDER
    if not sender.endswith("@opencode-gateway.codes") or any(c in sender for c in "\r\n<> ,"):
        raise HTTPException(422,"Sender must use the authorized opencode-gateway.codes domain")
    name=data.sender_name or selected.get('sender_name') or email_delivery.DEFAULT_NAME
    if any(c in name for c in '\r\n'):raise HTTPException(422,'Invalid sender name')
    key=data.api_key or selected.get('api_key' if data.provider=='brevo' else 'smtp_password')
    if not key:raise HTTPException(422,'Enter an API key for the selected email provider')
    cfg={'provider':data.provider,'smtp_from':sender,'sender_name':name}
    if data.provider=='brevo':cfg['api_key']=key
    else:cfg.update(smtp_host='smtp.resend.com',smtp_port=587,smtp_username='resend',smtp_password=key)
    accounts[data.provider]=dict(cfg)
    cfg['provider_accounts']=accounts
    # Read credentials belong to Resend, independent of the active sender.
    if existing.get('inbox_api_key'):cfg['inbox_api_key']=existing['inbox_api_key']
    elif data.provider=='resend' and data.api_key:cfg['inbox_api_key']=data.api_key
    admin_email_config.save(db,actor.id,cfg)
    return {**email_delivery.public_config(cfg),'credentials_configured':True,'delivery_verified':False}

class SupportInboxCredential(BaseModel):
    model_config=ConfigDict(extra="forbid", str_strip_whitespace=True)
    api_key: str = Field(min_length=5,max_length=4096)

@router.put("/service-integrations/inbox-credential")
def save_inbox_credential(data:SupportInboxCredential,actor:User=Depends(require_admin),db:Session=Depends(get_db)):
    from ..services import admin_email_config, credentials
    if not credentials.available():
        raise HTTPException(503,"Encrypted credential storage is unavailable")
    config=admin_email_config.read(db)
    if config is None:
        raise HTTPException(409,"Configure the Resend sender first")
    from ..services.email_delivery import read_resend
    read_resend("/emails/receiving?limit=1",data.api_key)
    config["inbox_api_key"]=data.api_key
    admin_email_config.save(db,actor.id,config)
    return {"configured":True,"address":"support@opencode-gateway.codes"}

class AdminDraftWrite(BaseModel):
    model_config=ConfigDict(extra="forbid", str_strip_whitespace=True)
    to: str = Field(default="",max_length=254)
    subject: str = Field(default="",max_length=300)
    body: str = Field(default="",max_length=50000)

@router.get("/service-integrations/drafts")
def list_admin_mail_drafts(actor:User=Depends(require_admin),db:Session=Depends(get_db)):
    from sqlalchemy import text
    from ..services import credentials
    if not credentials.available():
        raise HTTPException(503,"Encrypted drafts require CREDENTIALS_ENCRYPTION_KEY")
    rows=db.execute(text("""SELECT id, ciphertext, updated_at FROM admin_mail_drafts
                            WHERE admin_id=:admin ORDER BY updated_at DESC LIMIT 50"""),
                    {"admin":actor.id}).all()
    items=[]
    for row in rows:
        try: draft=json.loads(credentials.decrypt(row.ciphertext))
        except Exception:raise HTTPException(503,"Cannot decrypt a stored draft") from None
        items.append({"id":str(row.id),"to":draft.get("to",""),"subject":draft.get("subject",""),
                      "preview":draft.get("body","")[:140],"updated_at":row.updated_at.isoformat()})
    return {"items":items}

@router.get("/service-integrations/drafts/{draft_id}")
def get_admin_mail_draft(draft_id:_uuid.UUID,actor:User=Depends(require_admin),db:Session=Depends(get_db)):
    from sqlalchemy import text
    from ..services import credentials
    token=db.execute(text("""SELECT ciphertext FROM admin_mail_drafts
                            WHERE id=:id AND admin_id=:admin"""),
                     {"id":draft_id,"admin":actor.id}).scalar_one_or_none()
    if token is None:raise HTTPException(404,"Draft not found")
    try: draft=json.loads(credentials.decrypt(token))
    except Exception:raise HTTPException(503,"Cannot decrypt a stored draft") from None
    return {"id":str(draft_id),**{field:draft.get(field,"") for field in ("to","subject","body")}}

@router.post("/service-integrations/drafts")
def create_admin_mail_draft(data:AdminDraftWrite,actor:User=Depends(require_admin),db:Session=Depends(get_db)):
    from sqlalchemy import text
    from ..services import credentials
    token=credentials.encrypt(data.model_dump_json())
    draft_id=_uuid.uuid4()
    db.execute(text("""INSERT INTO admin_mail_drafts(id,admin_id,ciphertext)
                       VALUES(:id,:admin,:token)"""),{"id":draft_id,"admin":actor.id,"token":token})
    db.commit()
    return {"id":str(draft_id),"saved":True}

@router.put("/service-integrations/drafts/{draft_id}")
def update_admin_mail_draft(draft_id:_uuid.UUID,data:AdminDraftWrite,
                            actor:User=Depends(require_admin),db:Session=Depends(get_db)):
    from sqlalchemy import text
    from ..services import credentials
    token=credentials.encrypt(data.model_dump_json())
    updated=db.execute(text("""UPDATE admin_mail_drafts SET ciphertext=:token,
                              updated_at=CURRENT_TIMESTAMP WHERE id=:id AND admin_id=:admin
                              RETURNING id"""),
                       {"token":token,"id":draft_id,"admin":actor.id}).scalar_one_or_none()
    if updated is None:db.rollback();raise HTTPException(404,"Draft not found")
    db.commit()
    return {"id":str(draft_id),"saved":True}

@router.delete("/service-integrations/drafts/{draft_id}")
def delete_admin_mail_draft(draft_id:_uuid.UUID,actor:User=Depends(require_admin),db:Session=Depends(get_db)):
    from sqlalchemy import text
    deleted=db.execute(text("""DELETE FROM admin_mail_drafts
                               WHERE id=:id AND admin_id=:admin RETURNING id"""),
                       {"id":draft_id,"admin":actor.id}).scalar_one_or_none()
    if deleted is None:db.rollback();raise HTTPException(404,"Draft not found")
    db.commit()
    return {"deleted":True}

class AdminComposeEmail(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    to: str = Field(min_length=3,max_length=254)
    subject: str = Field(min_length=1,max_length=300)
    body: str = Field(min_length=1,max_length=100000)

@router.post("/service-integrations/send-email")
def admin_compose_send(data:AdminComposeEmail,actor:User=Depends(require_admin),db:Session=Depends(get_db)):
    """Send admin-authored mail through the saved sender; acceptance is not inbox delivery."""
    import re
    from email.message import EmailMessage
    from ..services import email_verification, email_delivery
    if not re.fullmatch(r"[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+",data.to):
        raise HTTPException(422,"Invalid recipient address")
    cfg=email_verification.smtp_settings(db)
    if not email_delivery.ready(cfg):raise HTTPException(503,'Configure an email provider and encryption before sending')
    if cfg.get('provider','resend') not in email_delivery.PROVIDERS or (cfg.get('provider','resend')=='resend' and cfg.get('smtp_host')!='smtp.resend.com'):
        raise HTTPException(503,'Admin compose requires a supported configured email provider')
    message=EmailMessage();message['From']=cfg['smtp_from'];message['To']=data.to;message['Subject']=data.subject;message.set_content(data.body)
    email_delivery.send(cfg,message)
    return {"sent":True,"to":data.to}

@router.get("/service-integrations/sent-emails")
def resend_sent_emails(_:User=Depends(require_admin),db:Session=Depends(get_db)):
    """Read real Resend sent-email metadata. No keys or HTML returned to browsers."""
    from ..services import admin_email_config
    cfg=admin_email_config.read(db) or {}
    key=cfg.get("inbox_api_key")
    if not key:return {"configured":False,"items":[],"reason":"Resend read-capable API key is required"}
    from ..services.email_delivery import read_resend
    payload=read_resend("/emails?limit=50",key)
    return {"configured":True,"items":[
        {"id":str(item.get("id","")),"to":item.get("to",[])[:10] if isinstance(item.get("to"),list) else [],
         "subject":str(item.get("subject",""))[:300],
         "status":str(item.get("last_event") or item.get("status") or "unknown")[:50],
         "created_at":str(item.get("created_at",""))}
        for item in payload.get("data",[]) if isinstance(item,dict)
    ],"has_more":bool(payload.get("has_more",False))}

@router.get("/service-integrations/support-inbox")
def support_inbox(_:User=Depends(require_admin),db:Session=Depends(get_db)):
    """Admin-only, read-only metadata for messages addressed to support mailbox."""
    from ..services import admin_email_config
    cfg=admin_email_config.read(db) or {}
    key=cfg.get("inbox_api_key")
    if not key:return {"configured":False,"items":[],"reason":"Receiving API key has not been configured"}
    from ..services.email_delivery import read_resend
    payload=read_resend("/emails/receiving?limit=50",key)
    items=[]
    for message in payload.get("data",[]):
        if not isinstance(message,dict):continue
        recipients=message.get("to") or []
        if not isinstance(recipients,list) or not any(str(x).lower()=="support@opencode-gateway.codes" for x in recipients):
            continue
        items.append({"id":str(message.get("id","")),"from":str(message.get("from",""))[:254],
                      "subject":str(message.get("subject",""))[:300],
                      "created_at":str(message.get("created_at",""))})
    return {"configured":True,"items":items,"has_more":bool(payload.get("has_more",False))}

@router.get("/service-integrations/sent-emails/{message_id}")
def resend_sent_message(message_id:_uuid.UUID,_:User=Depends(require_admin),db:Session=Depends(get_db)):
    """Read a sent message from Resend, returning bounded text only."""
    from ..services import admin_email_config
    cfg=admin_email_config.read(db) or {}
    key=cfg.get("inbox_api_key")
    if not key:raise HTTPException(503,"Resend read key is not configured")
    from ..services.email_delivery import read_resend
    mail=read_resend("/emails/"+str(message_id),key)
    recipients=mail.get("to") or []
    return {"id":str(message_id),"subject":str(mail.get("subject",""))[:300],
            "to":recipients[:10] if isinstance(recipients,list) else [],
            "from":str(mail.get("from",""))[:254],
            "text":str(mail.get("text") or "")[:50000],
            "created_at":str(mail.get("created_at","")),
            "status":str(mail.get("last_event",""))[:50]}

@router.get("/service-integrations/support-inbox/{message_id}")
def support_inbox_message(message_id:_uuid.UUID,_:User=Depends(require_admin),db:Session=Depends(get_db)):
    from ..services import admin_email_config
    cfg=admin_email_config.read(db) or {}
    key=cfg.get("inbox_api_key")
    if not key:raise HTTPException(503,"Receiving API key has not been configured")
    from ..services.email_delivery import read_resend
    email=read_resend("/emails/receiving/"+str(message_id),key)
    recipients=email.get("to") or []
    if not isinstance(recipients,list) or not any(str(x).lower()=="support@opencode-gateway.codes" for x in recipients):
        raise HTTPException(404,"Support email not found")
    # Plain text only; never render untrusted email HTML.
    return {"id":str(message_id),"subject":str(email.get("subject",""))[:300],
            "from":str(email.get("from",""))[:254],
            "text":str(email.get("text") or "")[:50000],
            "created_at":str(email.get("created_at",""))}

class EmailServiceToggle(BaseModel):
    model_config=ConfigDict(extra="forbid")
    enabled: bool

@router.put("/service-integrations/services/{service_id}")
def update_email_service(service_id:str, data:EmailServiceToggle,
                         _:User=Depends(require_admin), db:Session=Depends(get_db)):
    from ..services import email_service_policies
    if service_id not in email_service_policies.SUPPORTED:
        raise HTTPException(409,"This email service is not implemented")
    if service_id not in {'registration_verification','password_reset','github_connection_verification'}:
        from ..services import email_notifications
        if not email_notifications.ready(db):raise HTTPException(503,'Apply email notification migration 0027 before changing this service')
    try:
        email_service_policies.set_enabled(db, service_id, data.enabled)
    except Exception:
        db.rollback()
        raise
    return {"id":service_id,"enabled":data.enabled,"saved":True}

class NotificationReport(BaseModel):
    model_config=ConfigDict(extra='forbid')
    user_id:_uuid.UUID
    event_id:_uuid.UUID
    detail:str=Field(min_length=1,max_length=2000)

@router.post('/service-integrations/services/{service_id}/report')
def notification_report(service_id:str,data:NotificationReport,actor:User=Depends(require_admin),db:Session=Depends(get_db)):
    from ..services import email_notifications
    if service_id not in email_notifications.MANUAL:raise HTTPException(409,'This service is driven by its original event source')
    target=db.get(User,data.user_id)
    if target is None:raise HTTPException(404,'User not found')
    result=email_notifications.deliver(db,target,service_id,'manual:'+str(data.event_id),data.detail)
    if result=='disabled':raise HTTPException(409,'Enable this notification before sending')
    if result in {'migration_required','sender_unavailable'}:raise HTTPException(503,'Notification storage or configured sender is unavailable')
    return {'accepted':result=='accepted','state':result}

@router.get("/service-integrations")
def service_integrations(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    import os
    from ..services import email_verification
    from ..services import admin_email_config, credentials
    from ..services import email_delivery
    saved=admin_email_config.read(db)
    mail=email_verification.smtp_settings(db)
    mail_ready=email_delivery.ready(mail)
    required=email_verification.required_for_registration(db)
    from ..services import email_service_policies
    recovery_enabled=email_service_policies.enabled(db,"password_reset",True)
    github_verification_enabled=email_service_policies.enabled(db,'github_connection_verification',True)
    from sqlalchemy import inspect
    github_verification_ready=inspect(db.connection()).has_table('github_identity_registry')
    from ..services import email_notifications
    notification_schema=email_notifications.ready(db)
    accounts=dict((saved or {}).get('provider_accounts') or {})
    if mail.get('provider','resend') in email_delivery.PROVIDERS:accounts[mail.get('provider','resend')]=mail
    return {"email":{**email_delivery.public_config(mail),"sending_ready":mail_ready,
          "verification_required":required,"settings_schema_ready":admin_email_config.schema_ready(db),
          "credential_storage_ready":credentials.available(),
          "receiving_configured":bool((saved or {}).get("inbox_api_key")),"delivery_verified":False,
          "credentials_configured":bool(mail.get('api_key') if mail.get('provider')=='brevo' else mail.get('smtp_password')),
          "message_provider":"resend",
          "provider_configurations":{pid:email_delivery.public_config(accounts.get(pid,{'provider':pid})) for pid in email_delivery.PROVIDERS}},
       "services":[
         {"id":"registration_verification","enabled":required,"available":True,"editable":True,
          "reason":"" if mail_ready else "Selected email provider API key is missing"},
         {"id":"password_reset","enabled":recovery_enabled,"available":True,"editable":True,"delivery_ready":mail_ready,"reason":"Uses the configured email sender"},
         {"id":"github_connection_verification","enabled":github_verification_enabled,"available":github_verification_ready,"editable":True,"delivery_ready":mail_ready,
          "reason":"Apply migration 0029" if not github_verification_ready else "New GitHub connections require email matching and OTP; disabling blocks new connections"},
         *({"id":i,"available":i in email_service_policies.SUPPORTED and notification_schema,"editable":i in email_service_policies.SUPPORTED and notification_schema,"enabled":email_service_policies.enabled(db,i,False),"reason":"Apply migration 0027" if i in email_service_policies.SUPPORTED and not notification_schema else "Requires an authorized Resend Full access read key" if i=="support_received" else "Manual administrator report" if i in {"system_updates","service_incident","backup_status"} else "Gateway event notification" if i in email_service_policies.SUPPORTED else "Source event integration is not available"} for i in
           ("welcome_email","subscription_expiry","low_balance","account_suspension",
            "payment_receipt","renewal_reminder","system_updates","login_security",
            "password_changed","email_changed","payment_failed","trial_expiring",
            "support_received","support_unanswered","service_incident","mail_delivery_failure",
            "unusual_activity","backup_status"))
       ]}

@router.get("/github-configuration")
def github_configuration(_:User=Depends(require_admin),db:Session=Depends(get_db)):
    """Read-only effective GitHub settings metadata; never disclose secrets."""
    from ..services import github, credentials, github_app_config
    cfg=github_app_config.effective(settings,db)
    return {
        "provider":"github_app", "configured":github.configured(db,config=cfg),
        "database":github.schema_status(db),
        "app_id":cfg.github_app_id,
        "app_slug":cfg.github_app_slug or "",
        "client_id":cfg.github_client_id or "",
        "callback_url":cfg.github_callback_url,
        "public_base_url":settings.public_base_url,
        "api_base":cfg.github_api_base,
        "web_base":cfg.github_web_base,
        "webhook_url":settings.public_base_url.rstrip("/")+"/api/github/webhook",
        "secrets":{
            "client_secret":bool(cfg.github_client_secret),
            "private_key":bool(cfg.github_private_key),
            "webhook_secret":bool(cfg.github_webhook_secret),
            "encryption_key":credentials.available(),
        },
        "missing":[label for label,ok in {
            "GITHUB_APP_ID":bool(cfg.github_app_id),
            "GITHUB_APP_SLUG":bool(cfg.github_app_slug),
            "GITHUB_CLIENT_ID":bool(cfg.github_client_id),
            "GITHUB_CLIENT_SECRET":bool(cfg.github_client_secret),
            "GITHUB_APP_PRIVATE_KEY":bool(cfg.github_private_key),
            "CREDENTIALS_ENCRYPTION_KEY":credentials.available(),
        }.items() if not ok],
        "source":"encrypted_database" if github_app_config.read(db) is not None else "protected_server_environment",
        "editable":True,
        "settings_schema_ready":github_app_config.schema_ready(db),
        "credential_storage_ready":credentials.available(),
        "message":"Blank secrets preserve saved values. Saving requires migration 0024 and the original Gateway encryption key. App registration alone does not authorize customer repositories.",
    }

class GithubAppConfigurationIn(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    app_id:int=Field(gt=0)
    app_slug:str=Field(pattern=r'^[a-z0-9][a-z0-9-]{0,99}$')
    client_id:str=Field(min_length=1,max_length=128,pattern=r'^[A-Za-z0-9_]+$')
    client_secret:str|None=None
    private_key:str|None=None
    webhook_secret:str|None=None

@router.put('/github-configuration')
def save_github_configuration(data:GithubAppConfigurationIn,user:User=Depends(require_admin),db:Session=Depends(get_db)):
    from ..services import github_app_config
    github_app_config.save(db,user.id,settings,data.model_dump())
    return github_configuration(user,db)
