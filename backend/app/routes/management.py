import json, secrets, uuid
from urllib.parse import urlsplit
import ipaddress
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator
from sqlalchemy import select, update, func
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, AuthSession, Workspace, GithubConnection, Country, Region, City
from ..models.management import BillingMethod, AccountAudit, PasswordReset
from ..schemas.account import RegisterRequest
from ..security.passwords import hash_password, verify_password
from ..security.sessions import hash_session_token
from ..services import credentials, recovery, opencode, paypal
from ..services.accounts import user_payload
from .dependencies import require_user, require_admin

router=APIRouter(prefix='/api',tags=['account management'])
def now(): return datetime.now(timezone.utc)
def aware(date): return date if date.tzinfo else date.replace(tzinfo=timezone.utc)
def audit(db,user,action,subject=None): db.add(AccountAudit(actor_id=user.id if user else None,subject_id=subject or (user.id if user else None),action=action))
def revoke(db,user):
    db.execute(update(AuthSession).where(AuthSession.user_id==user.id,AuthSession.revoked_at.is_(None)).values(revoked_at=now()))
def stop_work(db,user):
    for workspace in db.scalars(select(Workspace).where(Workspace.user_id==user.id)): opencode.stop_workspace(workspace)

class PasswordInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    current_password: str=Field(min_length=1,max_length=128)
    new_password: str=Field(min_length=8,max_length=128)
    @field_validator('new_password')
    @classmethod
    def strong(cls,value): return RegisterRequest.strong_password(value)

@router.put('/account/password')
def password(data:PasswordInput,user:User=Depends(require_user),db:Session=Depends(get_db)):
    if not verify_password(data.current_password,user.password_hash): raise HTTPException(400,'Current password is incorrect')
    user.password_hash=hash_password(data.new_password); revoke(db,user)
    db.execute(update(PasswordReset).where(PasswordReset.user_id==user.id).values(used=True))
    audit(db,user,'password.changed'); db.commit()
    return {'message':'Password changed. Sign in again.'}

class Forgot(BaseModel):
    email: EmailStr
class Reset(BaseModel):
    token: str=Field(min_length=32,max_length=256)
    password: str=Field(min_length=8,max_length=128)
    @field_validator('password')
    @classmethod
    def strong(cls,value): return RegisterRequest.strong_password(value)

@router.post('/auth/forgot-password',status_code=202)
def forgot(data:Forgot,db:Session=Depends(get_db)):
    message={'message':'If an active account matches and email delivery is available, a recovery link will be sent.'}
    user=db.scalar(select(User).where(func.lower(User.email)==str(data.email).lower(),User.status=='active'))
    if not user: return message
    count=db.scalar(select(func.count()).select_from(PasswordReset).where(PasswordReset.user_id==user.id,PasswordReset.created_at>now()-timedelta(hours=1)))
    if count>=3: return message
    token=secrets.token_urlsafe(32)
    record=PasswordReset(user_id=user.id,token_hash=hash_session_token(token),expires_at=now()+timedelta(minutes=30))
    db.add(record); db.commit()
    try: recovery.send_reset(user.email,token)
    except HTTPException:
        record.used=True; audit(db,user,'password.recovery_delivery_unavailable'); db.commit()
    return message

@router.post('/auth/reset-password')
def reset(data:Reset,db:Session=Depends(get_db)):
    record=db.scalar(select(PasswordReset).where(PasswordReset.token_hash==hash_session_token(data.token)).with_for_update())
    if not record or record.used or aware(record.expires_at)<=now(): raise HTTPException(400,'Recovery link is invalid or expired')
    user=db.get(User,record.user_id)
    if not user or user.status!='active': raise HTTPException(400,'Recovery link is invalid or expired')
    user.password_hash=hash_password(data.password); revoke(db,user)
    db.execute(update(PasswordReset).where(PasswordReset.user_id==user.id).values(used=True))
    audit(db,user,'password.reset'); db.commit()
    return {'message':'Password reset. Sign in with your new password.'}

class Lifecycle(BaseModel):
    action: str=Field(pattern='^(suspend|delete)$')
    password: str=Field(min_length=1,max_length=128)
    confirmation: str=Field(max_length=50)

@router.post('/account/lifecycle')
def lifecycle(data:Lifecycle,user:User=Depends(require_user),db:Session=Depends(get_db)):
    if user.role in {'admin','owner'}: raise HTTPException(409,'Transfer administration before closing this account')
    if data.confirmation!=user.username or not verify_password(data.password,user.password_hash): raise HTTPException(400,'Account confirmation failed')
    stop_work(db,user); user.status='suspended' if data.action=='suspend' else 'deletion_requested'; revoke(db,user)
    connection=db.scalar(select(GithubConnection).where(GithubConnection.user_id==user.id))
    if connection: db.delete(connection)
    audit(db,user,'account.'+user.status); db.commit()
    return {'status':user.status,'files_deleted':False,'message':'Account access disabled. Files are retained for administrator review.'}

@router.get('/account/sessions')
def sessions(request:Request,user:User=Depends(require_user),db:Session=Depends(get_db)):
    from ..config import settings
    current=hash_session_token(request.cookies.get(settings.session_cookie_name,''))
    return [{'id':str(s.id),'current':s.token_hash==current,'created_at':s.created_at} for s in db.scalars(select(AuthSession).where(AuthSession.user_id==user.id,AuthSession.revoked_at.is_(None),AuthSession.expires_at>now()))]

@router.delete('/account/sessions/{session_id}',status_code=204)
def logout_session(session_id:uuid.UUID,user:User=Depends(require_user),db:Session=Depends(get_db)):
    row=db.get(AuthSession,session_id)
    if not row or row.user_id!=user.id: raise HTTPException(404,'Session not found')
    row.revoked_at=now(); audit(db,user,'session.revoked'); db.commit()

class MethodInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    kind: str=Field(pattern='^(paypal|bank|wallet|googlepay|binance|other)$')
    label: str=Field(min_length=1,max_length=100)
    account_name: str=Field(default='',max_length=150)
    account_reference: str=Field(default='',max_length=200)
    iban: str=Field(default='',max_length=64)
    branch: str=Field(default='',max_length=150)
    bank_name: str=Field(default='',max_length=150)
    currency: str=Field(default='USD',pattern='^[A-Z]{3}$')
    network: str=Field(default='',max_length=100)
    instructions: str=Field(default='',max_length=1000)
    available_country_codes: list[str]=Field(default_factory=list,max_length=100)
    checkout_mode: str=Field(default='manual',pattern='^(manual|link|paypal)$')
    payment_url: str=Field(default='',max_length=2000)
    plan_id: int|None=Field(default=None,ge=1)
    enabled: bool=True
    @field_validator('payment_url')
    @classmethod
    def public_payment_link(cls,value):
        if not value:return value
        try:
            url=urlsplit(value)
            host=(url.hostname or '').lower()
            if url.scheme!='https' or not host or url.username or url.password or url.port not in (None,443):raise ValueError()
            if host=='localhost' or host.endswith(('.localhost','.local','.internal')) or '.' not in host:raise ValueError()
            try:
                address=ipaddress.ip_address(host)
            except ValueError:address=None
            if address is not None and not address.is_global:raise ValueError()
        except ValueError:raise ValueError('Use a public HTTPS payment link without credentials')
        return value
def scope(user,platform):
    if platform and user.role not in {'owner','admin','finance'}: raise HTTPException(403,'Billing administration required')
    return None if platform else user.id
def method_payload(row): return {'id':str(row.id),'kind':row.kind,'label':row.label,'enabled':row.enabled,'details':json.loads(credentials.decrypt(row.details))}
def method_values(data):
    values=data.model_dump(); detail={key:values.pop(key) for key in ['account_name','account_reference','iban','branch','bank_name','currency','network','instructions','checkout_mode','payment_url','plan_id','available_country_codes']}
    return {**values,'details':credentials.encrypt(json.dumps(detail))}
def validate_receiving_method(db,data,platform):
    from ..models import Plan
    if data.checkout_mode=='link' and (not platform or (data.enabled and (not data.payment_url or not data.plan_id))):
        raise HTTPException(422,'Hosted payment links require a platform method, payment URL and matching plan')
    if data.checkout_mode=='manual' and data.payment_url:
        raise HTTPException(422,'Select hosted payment link mode to use a payment URL')
    if data.checkout_mode=='paypal' and (not platform or data.kind!='paypal' or data.payment_url):
        raise HTTPException(422,'PayPal API checkout requires a platform PayPal method without a static link')
    if data.kind=='googlepay' and data.enabled and data.checkout_mode!='link':
        raise HTTPException(422,'Google Pay requires a configured hosted checkout link from a supported payment processor')
    if data.kind=='googlepay' and data.enabled and not data.plan_id:
        raise HTTPException(422,'Google Pay requires a hosted payment link bound to one active plan')
    if data.enabled and data.checkout_mode=='manual':
        missing=[name for name,value in [('account holder',data.account_name),('receiving account or address',data.account_reference),('payment instructions',data.instructions)] if not value.strip()]
        if data.kind=='bank' and not data.bank_name.strip(): missing.append('bank name')
        if data.kind=='binance' and not data.network.strip(): missing.append('asset and network')
        if missing: raise HTTPException(422,'Complete the real receiving details before enabling: '+', '.join(missing))
    if data.enabled:
        host=(urlsplit(data.payment_url).hostname or '').lower()
        if host=='example.com' or host.endswith(('.example','.example.com','.example.org','.example.net')) or any('EXAMPLE_REPLACE' in value.upper() for value in [data.account_name,data.account_reference,data.network]):
            raise HTTPException(422,'Replace example receiving details before enabling this payment method')
    if data.plan_id:
        plan=db.get(Plan,data.plan_id)
        if not plan or not plan.active or plan.currency!=data.currency:raise HTTPException(422,'Choose an active plan with matching currency')
    codes=[c.strip().upper() for c in (data.available_country_codes or []) if c.strip()]
    if codes:
        from ..models import Country
        valid={r.code.upper() for r in db.scalars(select(Country).where(Country.enabled.is_(True)))}
        unknown=[c for c in codes if c not in valid]
        if unknown: raise HTTPException(422,'Unknown country codes: '+', '.join(unknown))
        data.available_country_codes=sorted(set(codes))
    else:
        data.available_country_codes=[]
@router.get('/billing/methods')
def methods(platform:bool=False,user:User=Depends(require_user),db:Session=Depends(get_db)):
    owner=scope(user,platform)
    return [method_payload(row) for row in db.scalars(select(BillingMethod).where(BillingMethod.user_id==owner))]
@router.get('/billing/available-methods')
def receiving(plan_id:int|None=Query(default=None,ge=1),include_unavailable:bool=False,user:User=Depends(require_user),db:Session=Depends(get_db)):
    from ..models import Plan
    plan=db.get(Plan,plan_id) if plan_id is not None else None
    if plan_id is not None and (plan is None or not plan.active): raise HTTPException(422,'Unknown or inactive plan')
    user_code=(user.country.code.upper() if getattr(user,'country',None) and user.country.code else None)
    ranked=[]
    for row in db.scalars(select(BillingMethod).where(BillingMethod.user_id.is_(None),BillingMethod.enabled.is_(True))):
        payload=method_payload(row); details=payload['details']; mode=details.get('checkout_mode','manual')
        allowed_countries=[c.upper() for c in (details.get('available_country_codes') or [])]
        if allowed_countries and (not user_code or user_code not in allowed_countries): continue
        if plan is not None and (details.get('currency')!=plan.currency or details.get('plan_id') not in (None,plan.id)): continue
        reason=None
        if mode=='paypal' and not paypal.configured(): reason='provider_not_connected'
        elif mode=='link':
            host=(urlsplit(details.get('payment_url') or '').hostname or '').lower()
            if not details.get('payment_url') or not details.get('plan_id') or host=='example.com' or host.endswith(('.invalid','.test','.example','.local','.localhost')): reason='processor_not_connected'
        elif mode=='manual' and (not details.get('account_name') or not details.get('account_reference') or not details.get('instructions')): reason='details_not_configured'
        elif row.kind=='bank' and mode=='manual' and not details.get('bank_name'): reason='details_not_configured'
        elif row.kind=='binance' and mode=='manual' and not details.get('network'): reason='details_not_configured'
        if reason:
            if not include_unavailable: continue
            payload['available']=False; payload['available_reason']=reason
        else:
            payload['available']=True
        ranked.append((0 if (allowed_countries and user_code in allowed_countries) else 1,payload))
    ranked.sort(key=lambda item:item[0])
    return [payload for _,payload in ranked]
@router.post('/billing/methods',status_code=201)
def create_method(data:MethodInput,platform:bool=False,user:User=Depends(require_user),db:Session=Depends(get_db)):
    scope(user,platform);validate_receiving_method(db,data,platform)
    row=BillingMethod(user_id=scope(user,platform),**method_values(data)); db.add(row); audit(db,user,'billing.method_created'); db.commit(); return method_payload(row)
def owned_method(db,user,platform,method_id):
    owner=scope(user,platform); row=db.get(BillingMethod,method_id)
    if not row or row.user_id!=owner: raise HTTPException(404,'Billing method not found')
    return row
@router.put('/billing/methods/{method_id}')
def edit_method(method_id:uuid.UUID,data:MethodInput,platform:bool=False,user:User=Depends(require_user),db:Session=Depends(get_db)):
    row=owned_method(db,user,platform,method_id)
    validate_receiving_method(db,data,platform)
    for key,value in method_values(data).items(): setattr(row,key,value)
    audit(db,user,'billing.method_updated'); db.commit(); return method_payload(row)
@router.delete('/billing/methods/{method_id}',status_code=204)
def delete_method(method_id:uuid.UUID,platform:bool=False,user:User=Depends(require_user),db:Session=Depends(get_db)):
    db.delete(owned_method(db,user,platform,method_id)); audit(db,user,'billing.method_deleted'); db.commit()

@router.get('/account/logs')
def logs(user:User=Depends(require_user),db:Session=Depends(get_db),before:int|None=None):
    query=select(AccountAudit).where(AccountAudit.subject_id==user.id)
    if before is not None: query=query.where(AccountAudit.id<before)
    return list(db.scalars(query.order_by(AccountAudit.id.desc()).limit(100)))
@router.get('/admin/logs')
def admin_logs(user:User=Depends(require_admin),db:Session=Depends(get_db),before:int|None=None):
    query=select(AccountAudit)
    if before is not None: query=query.where(AccountAudit.id<before)
    return list(db.scalars(query.order_by(AccountAudit.id.desc()).limit(100)))
@router.get('/admin/connections')
def connections(user:User=Depends(require_admin),db:Session=Depends(get_db)):
    return [{'user_id':str(r.user_id),'login':r.account_login,'suspended':r.suspended} for r in db.scalars(select(GithubConnection))]
@router.delete('/admin/connections/{user_id}',status_code=204)
def remove_connection(user_id:uuid.UUID,user:User=Depends(require_admin),db:Session=Depends(get_db)):
    row=db.scalar(select(GithubConnection).where(GithubConnection.user_id==user_id))
    if not row: raise HTTPException(404,'Connection not found')
    db.delete(row); audit(db,user,'github.disconnected',user_id); db.commit()

class RoleChange(BaseModel):
    role:str=Field(pattern='^(owner|admin|support|finance|customer)$')
@router.put('/admin/users/{user_id}/role')
def change_role(user_id:uuid.UUID,data:RoleChange,user:User=Depends(require_admin),db:Session=Depends(get_db)):
    if user.role!='owner': raise HTTPException(403,'Owner role required')
    target=db.get(User,user_id)
    if not target: raise HTTPException(404,'User not found')
    if target.id==user.id or target.role=='owner': raise HTTPException(409,'Existing owner cannot be demoted here')
    target.role=data.role; revoke(db,target); audit(db,user,'role.changed',target.id); db.commit(); return user_payload(target)

LOCATION={'countries':Country,'regions':Region,'cities':City}
class LocationInput(BaseModel):
    name:str=Field(min_length=1,max_length=120)
    code:str|None=Field(default=None,pattern='^[A-Z]{2}$')
    parent_id:int|None=None
    enabled:bool=True
def location_model(kind):
    if kind not in LOCATION: raise HTTPException(404,'Location type not found')
    return LOCATION[kind]
@router.get('/admin/locations/{kind}')
def locations(kind:str,user:User=Depends(require_admin),db:Session=Depends(get_db)):
    return list(db.scalars(select(location_model(kind)).order_by(location_model(kind).id)))
def location_values(db,kind,data):
    values={'name':data.name.strip(),'enabled':data.enabled}
    if not values['name']: raise HTTPException(422,'Name is required')
    if kind=='countries':
        if not data.code: raise HTTPException(422,'Country code is required')
        values['code']=data.code
    else:
        parent=Country if kind=='regions' else Region
        if not data.parent_id or not db.get(parent,data.parent_id): raise HTTPException(422,'Invalid parent location')
        values['country_id' if kind=='regions' else 'region_id']=data.parent_id
    return values
@router.post('/admin/locations/{kind}',status_code=201)
def add_location(kind:str,data:LocationInput,user:User=Depends(require_admin),db:Session=Depends(get_db)):
    model=location_model(kind); values=location_values(db,kind,data)
    if kind=='countries' and db.scalar(select(Country).where((Country.code==data.code)|(Country.name==values['name']))): raise HTTPException(409,'Country already exists')
    row=model(**values); db.add(row); audit(db,user,'location.created'); db.commit(); db.refresh(row); return row
@router.put('/admin/locations/{kind}/{location_id}')
def edit_location(kind:str,location_id:int,data:LocationInput,user:User=Depends(require_admin),db:Session=Depends(get_db)):
    row=db.get(location_model(kind),location_id)
    if not row: raise HTTPException(404,'Location not found')
    values=location_values(db,kind,data)
    for key in ['country_id','region_id']:
        if key in values and values[key]!=getattr(row,key): raise HTTPException(409,'Location hierarchy cannot be changed')
    if kind=='countries' and db.scalar(select(Country).where(Country.id!=row.id,(Country.code==data.code)|(Country.name==values['name']))): raise HTTPException(409,'Country already exists')
    for key,value in values.items(): setattr(row,key,value)
    audit(db,user,'location.updated'); db.commit(); db.refresh(row); return row
@router.delete('/admin/locations/{kind}/{location_id}',status_code=204)
def disable_location(kind:str,location_id:int,user:User=Depends(require_admin),db:Session=Depends(get_db)):
    row=db.get(location_model(kind),location_id)
    if not row: raise HTTPException(404,'Location not found')
    row.enabled=False; audit(db,user,'location.disabled'); db.commit()
