import json, secrets, uuid
from urllib.parse import urlsplit
import ipaddress
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator
from sqlalchemy import select, update, func
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, AuthSession, Workspace, GithubConnection, Country, Region, City
from ..models.management import BillingMethod, AccountAudit, PasswordReset
from ..schemas.account import RegisterRequest
from ..security.passwords import hash_password, verify_password
from ..security.sessions import (hash_session_token, new_reactivation_token,
    reactivation_cookie_name, reactivation_eligible)
from ..services import credentials, recovery, paypal, github
from ..services.billing_methods import method_payload
from ..services.accounts import user_payload
from .dependencies import require_user, require_admin, require_billing_user, require_reactivation_user

router=APIRouter(prefix='/api',tags=['account management'])
def now(): return datetime.now(timezone.utc)
def aware(date): return date if date.tzinfo else date.replace(tzinfo=timezone.utc)
def audit(db,user,action,subject=None): db.add(AccountAudit(actor_id=user.id if user else None,subject_id=subject or (user.id if user else None),action=action))
def revoke(db,user):
    db.execute(update(AuthSession).where(AuthSession.user_id==user.id,AuthSession.revoked_at.is_(None)).values(revoked_at=now()))
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
    message={'message':'If an eligible account matches and email delivery is available, a recovery link will be sent.'}
    from ..services.email_service_policies import enabled
    if not enabled(db,'password_reset',True):return message
    user=db.scalar(select(User).where(func.lower(User.email)==str(data.email).lower(),User.status.in_(['active','archived','pending_email'])))
    if user and user.status=='archived' and not reactivation_eligible(user): return message
    if not user: return message
    count=db.scalar(select(func.count()).select_from(PasswordReset).where(PasswordReset.user_id==user.id,PasswordReset.created_at>now()-timedelta(hours=1)))
    if count>=3: return message
    token=secrets.token_urlsafe(32)
    record=PasswordReset(user_id=user.id,token_hash=hash_session_token(token),expires_at=now()+timedelta(seconds=60))
    db.add(record); db.commit()
    try: recovery.send_reset(user.email,token,db)
    except HTTPException:
        record.used=True; audit(db,user,'password.recovery_delivery_unavailable'); db.commit()
    return message

class RecoveryToken(BaseModel):
    model_config=ConfigDict(extra='forbid')
    token: str=Field(min_length=32,max_length=256)

def recovery_record(db,token,*,lock=False):
    query=select(PasswordReset).where(PasswordReset.token_hash==hash_session_token(token))
    record=db.scalar(query)
    if lock and record:
        # User first, then proof: two different links must not each hold their
        # proof while waiting to invalidate the account's other recovery links.
        # This also matches archival/password completion's account lock order.
        db.scalar(select(User).where(User.id==record.user_id).with_for_update().execution_options(populate_existing=True))
        record=db.scalar(query.with_for_update().execution_options(populate_existing=True))
    if not record or record.used or aware(record.expires_at)<=now() or (record.created_at is not None and now()-aware(record.created_at)>=timedelta(seconds=60)): raise HTTPException(400,'Recovery link is invalid or expired')
    return record

@router.post('/auth/recovery-status')
def recovery_status(data:RecoveryToken,db:Session=Depends(get_db)):
    record=recovery_record(db,data.token)
    user=db.get(User,record.user_id)
    if not user or user.status not in {'active','archived','pending_email'}: raise HTTPException(400,'Recovery link is invalid or expired')
    return {'reactivation_required':reactivation_eligible(user),'account_activation_required':user.status=='pending_email'}

def reactivation_payload(db,user):
    # Email proof and password activation do not depend on subscriptions.
    # Billing remains a separate post-login service.
    return {'email':user.email,'username':user.username,'scope':'reactivation',
            'password_setup_required':True}

@router.post('/auth/reactivation/verify')
def verify_reactivation(data:RecoveryToken,response:Response,db:Session=Depends(get_db)):
    record=recovery_record(db,data.token,lock=True)
    user=db.scalar(select(User).where(User.id==record.user_id).with_for_update().execution_options(populate_existing=True))
    if not user or not reactivation_eligible(user): raise HTTPException(400,'Recovery link is invalid or expired')
    # Single-use email proof issues a temporary password-setup session.
    # It does not grant access or require billing before the new password.
    revoke(db,user)
    db.execute(update(PasswordReset).where(PasswordReset.user_id==user.id).values(used=True))
    raw,hashed=new_reactivation_token()
    db.add(AuthSession(user_id=user.id,token_hash=hashed,last_seen_at=now(),expires_at=now()+timedelta(minutes=30)))
    audit(db,user,'account.reactivation_verified');db.commit()
    from ..config import settings
    response.delete_cookie(settings.session_cookie_name,path='/',secure=settings.cookie_secure,httponly=True,samesite='strict')
    response.set_cookie(reactivation_cookie_name(),raw,path='/api',httponly=True,secure=settings.cookie_secure,samesite='strict')
    return reactivation_payload(db,user)

@router.get('/auth/reactivation')
def reactivation_status(user:User=Depends(require_reactivation_user),db:Session=Depends(get_db)):
    return reactivation_payload(db,user)

class ReactivationPassword(BaseModel):
    model_config=ConfigDict(extra='forbid')
    password: str=Field(min_length=8,max_length=128)
    @field_validator('password')
    @classmethod
    def strong(cls,value): return RegisterRequest.strong_password(value)

@router.post('/auth/reactivation/password')
def reactivation_password(data:ReactivationPassword,response:Response,user:User=Depends(require_reactivation_user),db:Session=Depends(get_db)):
    user=db.scalar(select(User).where(User.id==user.id).with_for_update().execution_options(populate_existing=True))
    if not reactivation_eligible(user):
        raise HTTPException(409,'Account reactivation is not available')
    user.password_hash=hash_password(data.password)
    user.status='active'
    revoke(db,user)
    db.execute(update(PasswordReset).where(PasswordReset.user_id==user.id).values(used=True))
    audit(db,user,'account.reactivation_completed');audit(db,user,'password.reset');db.commit()
    from ..config import settings
    response.delete_cookie(reactivation_cookie_name(),path='/api',secure=settings.cookie_secure,httponly=True,samesite='strict')
    return {'message':'Account reactivated. Sign in with your fresh password.'}

@router.post('/auth/reset-password')
def reset(data:Reset,response:Response,db:Session=Depends(get_db)):
    record=recovery_record(db,data.token,lock=True)
    user=db.scalar(select(User).where(User.id==record.user_id).with_for_update().execution_options(populate_existing=True))
    if not user or user.status not in {'active','pending_email'}: raise HTTPException(400,'Use account reactivation to renew this archived account')
    activating_legacy=user.status=='pending_email'
    finishing_reactivation=reactivation_eligible(user)
    # Recovery and account activation are independent of payment.
    user.password_hash=hash_password(data.password)
    if finishing_reactivation: user.status='active'
    revoke(db,user)
    activation_challenge = None
    if activating_legacy:
        # Email link and password proof are not a replacement for the
        # registration OTP. Keep the account pending until the fresh code
        # is verified, then start its ONE 30-day trial.
        from ..models import EmailVerification
        from ..services import email_verification
        email_verification.require_code_schema(db)
        if not email_verification.smtp_ready(db):
            raise HTTPException(503, 'Email verification delivery is unavailable')
        issued_at=now()
        db.execute(update(EmailVerification).where(
            EmailVerification.user_id==user.id,
            EmailVerification.used_at.is_(None)
        ).values(used_at=issued_at))
        challenge, code=email_verification.create_code(db,user)
        activation_challenge=str(challenge)
        email_verification.send_code(user.email,code,db)
        audit(db,user,'account.activation_code_sent')
    db.execute(update(PasswordReset).where(PasswordReset.user_id==user.id).values(used=True))
    audit(db,user,'password.reset')
    if finishing_reactivation: audit(db,user,'account.reactivation_completed')
    db.commit()
    from ..config import settings
    response.delete_cookie(settings.session_cookie_name,path='/',secure=settings.cookie_secure,httponly=True,samesite='strict')
    response.delete_cookie(reactivation_cookie_name(),path='/api',secure=settings.cookie_secure,httponly=True,samesite='strict')
    if activating_legacy:
        return {'activation_required':True,'verification_challenge':activation_challenge,
                'verification_expires_in':60,
                'message':'New password saved. Verify the six-digit email code to activate your account.'}
    return {'message':'Password reset. Sign in with your new password.'}

class Lifecycle(BaseModel):
    action: str=Field(pattern='^(suspend|delete)$')
    password: str=Field(min_length=1,max_length=128)
    confirmation: str=Field(max_length=50)

@router.post('/account/lifecycle')
def lifecycle(data:Lifecycle,user:User=Depends(require_user),db:Session=Depends(get_db)):
    if user.role in {'admin','owner'}: raise HTTPException(409,'Transfer administration before closing this account')
    if data.confirmation!=user.username or not verify_password(data.password,user.password_hash): raise HTTPException(400,'Account confirmation failed')
    user.status='suspended' if data.action=='suspend' else 'deletion_requested'; revoke(db,user)
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
def receiving(plan_id:int|None=Query(default=None,ge=1),include_unavailable:bool=False,user:User=Depends(require_billing_user),db:Session=Depends(get_db)):
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
    audit(db,user,'github.disconnected',user_id)
    github.disconnect(db, db.get(User,user_id))

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


# ---- Gateway-owned AI catalog and BYOK connections (existing API paths) ----
# AI execution and streaming stay exclusively inside Pi Central. This module
# handles ONLY model metadata, authentication checks and encrypted credentials.
import os
import hmac as _ai_hmac
import httpx as _ai_httpx
from sqlalchemy import inspect as _ai_inspect, text as _ai_text
from sqlalchemy.exc import SQLAlchemyError as _AiSqlError, IntegrityError as _AiIntegrityError
from ..models import AiProviderCatalog, AiProviderModel, AiUserConnection, Project
from ..models.platform import get_policy as _ai_get_policy

_AI_TABLES = ("ai_provider_catalog", "ai_provider_models", "ai_user_connections")
_AI_VERIFY_URLS = {
    "openrouter": "https://openrouter.ai/api/v1/key",
    "deepseek": "https://api.deepseek.com/user/balance",
    "openai": "https://api.openai.com/v1/models",
    "groq": "https://api.groq.com/openai/v1/models",
    "mistral": "https://api.mistral.ai/v1/models",
    "xai": "https://api.x.ai/v1/models",
    "together": "https://api.together.xyz/v1/models",
    "cerebras": "https://api.cerebras.ai/v1/models",
}
_AI_REFRESH_DAYS = 14
_AI_STALE_DAYS = 14
_AI_SCHEMA_OK_UNTIL = 0.0


def _ai_schema(db):
    # Cache only a POSITIVE table check for one minute. Before manual SQL
    # migration, missing tables are never cached as available.
    global _AI_SCHEMA_OK_UNTIL
    import time
    current = time.monotonic()
    if current < _AI_SCHEMA_OK_UNTIL:
        return
    existing = set(_ai_inspect(db.bind).get_table_names())
    if not set(_AI_TABLES).issubset(existing):
        raise HTTPException(503, "TEST AI catalog schema is not installed. Apply the reviewed manual PostgreSQL migration before enabling provider connections.")
    _AI_SCHEMA_OK_UNTIL = current + 60.0


def _ai_policy(db):
    return _ai_get_policy(db).as_payload()


def _ai_allowed(db, provider_id, model_id=None, rules=None):
    if rules is None:
        rules = _ai_policy(db)
    allowed = rules.get("allowed_providers") or []
    if provider_id in (rules.get("hidden_providers") or []):
        return False
    if allowed and provider_id not in allowed:
        return False
    if model_id is not None:
        allowed_models = rules.get("allowed_models") or []
        hidden = rules.get("hidden_models") or {}
        if model_id in hidden.get(provider_id, []):
            return False
        if allowed_models and not any(x in allowed_models for x in (model_id, provider_id + "/" + model_id)):
            return False
    return True


# Per-customer model preferences are encrypted WITH the existing verified
# connection, avoiding schema changes and keeping legacy encrypted API keys
# readable. No account preferences or secrets live in browser storage.
_AI_CONNECTION_ENVELOPE = "GATEWAY-AI-CONNECTION-V1:"

def _ai_connection_secret_and_models(row):
    value = credentials.decrypt(row.ciphertext)
    if not value.startswith(_AI_CONNECTION_ENVELOPE):
        return value, set()
    try:
        payload = json.loads(value[len(_AI_CONNECTION_ENVELOPE):])
        key = payload["key"]
        disabled = payload.get("disabled_models", [])
        if not isinstance(key, str) or not key or not isinstance(disabled, list):
            raise ValueError("Invalid encrypted connection")
        return key, {x for x in disabled if isinstance(x, str)}
    except (ValueError, KeyError, TypeError):
        raise HTTPException(503, "Stored account connection requires recovery") from None


def _ai_seal_connection(key, disabled):
    if not disabled:
        return credentials.encrypt(key)
    if len(disabled) > 2000:
        raise HTTPException(422, "Too many model overrides")
    return credentials.encrypt(_AI_CONNECTION_ENVELOPE + json.dumps({
        "key": key, "disabled_models": sorted(disabled)
    }, separators=(",", ":")))


class AiModelPreference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_id: str = Field(min_length=1, max_length=300)
    enabled: bool


def _ai_connection_payload(row):
    return {"connection_id": str(row.id), "provider_id": row.provider_id,
            "auth_status": row.auth_status, "credit_status": row.credit_status,
            "last4": row.last4, "verified_at": row.verified_at,
            "connected": row.auth_status == "verified", "verified": row.auth_status == "verified"}


def _ai_provider_rows(db, user_id, *, query="", include_connected_models=False, provider_id=None, connected_only=False):
    _ai_schema(db)
    connected = {row.provider_id: row for row in db.scalars(
        select(AiUserConnection).where(AiUserConnection.user_id == user_id))}
    provider_query = select(AiProviderCatalog).order_by(AiProviderCatalog.name)
    if connected_only:
        provider_query = provider_query.where(AiProviderCatalog.id.in_(connected))
    if provider_id:
        provider_query = provider_query.where(AiProviderCatalog.id == provider_id)
    if query:
        provider_query = provider_query.where(
            (func.lower(AiProviderCatalog.id).contains(query.lower())) |
            (func.lower(AiProviderCatalog.name).contains(query.lower())))
    rows = list(db.scalars(provider_query.limit(1000)))
    rules = _ai_policy(db)
    # Fetch connected model details in ONE indexed query instead of one SQL
    # round-trip per provider. Read-only Dashboard opens stay lightweight.
    details_for = {provider.id for provider in rows
                   if provider_id == provider.id or
                   (include_connected_models and provider.id in connected)}
    models_by_provider = {}
    disabled_by_provider = {
        pid: _ai_connection_secret_and_models(connected[pid])[1]
        for pid in details_for if pid in connected
    }
    if details_for:
        models = db.scalars(select(AiProviderModel).where(
            AiProviderModel.provider_id.in_(details_for),
            AiProviderModel.active.is_(True)).order_by(
            AiProviderModel.provider_id, AiProviderModel.name))
        for model in models:
            if _ai_allowed(db, model.provider_id, model.model_id, rules=rules):
                models_by_provider.setdefault(model.provider_id, {})[model.model_id] = {
                    **json.loads(model.details_json or "{}"),
                    "id": model.model_id, "name": model.name,
                    "enabled": model.model_id not in disabled_by_provider.get(model.provider_id, set())}
    checked_at = now()
    result = []
    for provider in rows:
        if not _ai_allowed(db, provider.id, rules=rules):
            continue
        record = connected.get(provider.id)
        stale = (not provider.models_synced_at or
                 checked_at - aware(provider.models_synced_at) > timedelta(days=_AI_STALE_DAYS))
        item = {"id": provider.id, "name": provider.name,
                "model_count": provider.model_count, "models": {},
                "connected": bool(record and record.auth_status == "verified"),
                "verified": bool(record and record.auth_status == "verified"),
                "credential_stored": False, "credential_source": "gateway" if record else "none",
                "auth_status": record.auth_status if record else "not_connected",
                "credit_status": record.credit_status if record else "unknown",
                "last_synced_at": provider.models_synced_at, "stale": stale}
        if provider.id in details_for:
            item["models"] = models_by_provider.get(provider.id, {})
        result.append(item)
    return result


@router.get("/opencode/catalog/providers")
def ai_catalog_list(provider_id: str | None = None, query: str = "",
                    include_connected_models: bool = False,
                    connected_only: bool = False, discover: bool = False,
                    user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Read saved PostgreSQL catalog; metadata synchronization runs in maintenance."""
    # No Pi requests during workspace use, chat, tools, uploads or normal
    # account-connection reads. Reuse the 14-day database snapshot.
    # Legacy discover=true is retained for compatibility but it is now
    # read-only. The EXISTING Gateway maintenance task owns Pi synchronization,
    # not browser clicks, workspace chats or per-request authentication.
    if discover:
        _ai_schema(db)
        if db.scalar(select(AiProviderCatalog.id).limit(1)) is None:
            raise HTTPException(503, "Pi catalog initial synchronization pending; check TEST maintenance logs")
    rows = _ai_provider_rows(db, user.id, query=query[:120],
                             include_connected_models=include_connected_models,
                             provider_id=provider_id, connected_only=connected_only)
    return {"all": rows, "connected": [p["id"] for p in rows if p["connected"]],
            "default": {}, "source": "gateway", "refresh_days": _AI_REFRESH_DAYS,
            "stale_after_days": _AI_STALE_DAYS}


@router.get("/opencode/connections")
def ai_connections(user: User = Depends(require_user), db: Session = Depends(get_db)):
    _ai_schema(db)
    return [_ai_connection_payload(x) for x in db.scalars(
        select(AiUserConnection).where(AiUserConnection.user_id == user.id)
        .order_by(AiUserConnection.provider_id))]


class AiKeyInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    provider_id: str = Field(pattern=r"^[a-zA-Z0-9._-]{1,120}$")
    api_key: str = Field(min_length=8, max_length=8192)


def _ai_verify(provider_id, key):
    url = _AI_VERIFY_URLS.get(provider_id)
    if not url:
        raise HTTPException(422, "This provider has no approved real API-key verification method yet")
    # Only fixed trusted HTTPS endpoints; no user-supplied URLs or SSRF.
    try:
        with _ai_httpx.Client(timeout=12, follow_redirects=False, trust_env=False) as client:
            response = client.get(url, headers={"Authorization": "Bearer " + key,
                                                   "Accept": "application/json"})
    except _ai_httpx.RequestError:
        raise HTTPException(503, "Provider verification unavailable; key was not stored") from None
    status = response.status_code
    if status == 401:
        raise HTTPException(422, "Provider rejected this API key (401); key was not stored")
    if status == 402:
        raise HTTPException(402, "Provider reports insufficient balance; authentication was not independently confirmed")
    if status == 403:
        raise HTTPException(403, "Provider denied API access; key was not stored")
    if status == 429:
        raise HTTPException(429, "Provider verification rate limited; retry later")
    if status != 200:
        raise HTTPException(503, "Provider verification was inconclusive; key was not stored")
    try:
        document = response.json()
    except ValueError:
        raise HTTPException(503, "Provider returned invalid verification data") from None
    if not isinstance(document, dict):
        raise HTTPException(503, "Provider verification data was unrecognized")
    if provider_id == "openrouter" and not isinstance(document.get("data"), dict):
        raise HTTPException(503, "OpenRouter did not return authenticated key details")
    if provider_id == "deepseek" and "is_available" not in document and "balance_infos" not in document:
        raise HTTPException(503, "DeepSeek did not return authenticated balance details")
    if provider_id not in ("openrouter", "deepseek") and not isinstance(document.get("data"), (list, dict)):
        raise HTTPException(503, "Model-provider verification was inconclusive")
    credit = "unknown"
    if provider_id == "deepseek":
        credit = "available" if document.get("is_available") is True else "insufficient_balance"
    return credit


def _ai_save(data, user, db, replace=False):
    _ai_schema(db)
    if not _ai_allowed(db, data.provider_id) or not db.get(AiProviderCatalog, data.provider_id):
        raise HTTPException(404, "Unknown or hidden provider")
    if not credentials.available():
        raise HTTPException(503, "Encrypted credential storage is not configured")
    existing = db.scalar(select(AiUserConnection).where(
        AiUserConnection.user_id == user.id, AiUserConnection.provider_id == data.provider_id)
        .with_for_update())
    if existing is not None and not replace:
        raise HTTPException(409, "Connection already exists; use replace")
    if existing is None and replace:
        raise HTTPException(404, "Connection not found")
    credit = _ai_verify(data.provider_id, data.api_key)
    # Preserve this customer's model preferences when rotating a key.
    disabled = _ai_connection_secret_and_models(existing)[1] if existing else set()
    cipher = _ai_seal_connection(data.api_key, disabled)
    if existing is None:
        existing = AiUserConnection(user_id=user.id, provider_id=data.provider_id,
                                    ciphertext=cipher, last4=data.api_key[-4:],
                                    auth_status="verified", credit_status=credit,
                                    verified_at=now())
        db.add(existing)
    else:
        existing.ciphertext = cipher
        existing.last4 = data.api_key[-4:]
        existing.auth_status = "verified"
        existing.credit_status = credit
        existing.verified_at = now()
    audit(db, user, "ai.connection.verified")
    try:
        db.commit()
    except _AiIntegrityError:
        db.rollback()
        raise HTTPException(409, "A connection for this provider already exists") from None
    db.refresh(existing)
    return _ai_connection_payload(existing)


@router.post("/opencode/connections", status_code=201)
def ai_connect(data: AiKeyInput, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return _ai_save(data, user, db)


@router.put("/opencode/connections/{provider_id}")
def ai_replace(provider_id: str, data: AiKeyInput,
               user: User = Depends(require_user), db: Session = Depends(get_db)):
    if provider_id != data.provider_id:
        raise HTTPException(422, "Provider mismatch")
    return _ai_save(data, user, db, replace=True)


@router.delete("/opencode/connections/{provider_id}", status_code=204)
def ai_disconnect(provider_id: str, user: User = Depends(require_user),
                  db: Session = Depends(get_db)):
    _ai_schema(db)
    record = db.scalar(select(AiUserConnection).where(
        AiUserConnection.user_id == user.id, AiUserConnection.provider_id == provider_id)
        .with_for_update())
    if record is None:
        raise HTTPException(404, "Connection not found")
    db.delete(record)
    audit(db, user, "ai.connection.deleted")
    db.commit()


@router.get("/opencode/connections/{provider_id}/models")
def ai_my_connection_models(provider_id: str, user: User = Depends(require_user),
                            db: Session = Depends(get_db)):
    """Lazy, owned model list for the expanded connected-provider accordion."""
    _ai_schema(db)
    record = db.scalar(select(AiUserConnection).where(
        AiUserConnection.user_id == user.id, AiUserConnection.provider_id == provider_id,
        AiUserConnection.auth_status == "verified"))
    if record is None:
        raise HTTPException(404, "Verified account connection not found")
    disabled = _ai_connection_secret_and_models(record)[1]
    rules = _ai_policy(db)
    models = list(db.scalars(select(AiProviderModel).where(
        AiProviderModel.provider_id == provider_id, AiProviderModel.active.is_(True))
        .order_by(AiProviderModel.name).limit(2000)))
    return {"provider_id": provider_id,
            "models": [{"id": m.model_id, "name": m.name,
                        "enabled": m.model_id not in disabled and
                        _ai_allowed(db, provider_id, m.model_id, rules=rules),
                        "admin_allowed": _ai_allowed(db, provider_id, m.model_id, rules=rules)}
                       for m in models]}


@router.post("/opencode/connections/{provider_id}/models")
def ai_set_connection_model(provider_id: str, data: AiModelPreference,
                            user: User = Depends(require_user),
                            db: Session = Depends(get_db)):
    """Persist model toggles in the customer's encrypted connection only."""
    _ai_schema(db)
    record = db.scalar(select(AiUserConnection).where(
        AiUserConnection.user_id == user.id, AiUserConnection.provider_id == provider_id,
        AiUserConnection.auth_status == "verified").with_for_update())
    if record is None:
        raise HTTPException(404, "Verified account connection not found")
    model = db.get(AiProviderModel, (provider_id, data.model_id))
    if model is None or not model.active:
        raise HTTPException(404, "Pi model is not in the saved provider catalog")
    if data.enabled and not _ai_allowed(db, provider_id, data.model_id):
        raise HTTPException(403, "The administrator disabled this model")
    key, disabled = _ai_connection_secret_and_models(record)
    if data.enabled:
        disabled.discard(data.model_id)
    else:
        disabled.add(data.model_id)
    record.ciphertext = _ai_seal_connection(key, disabled)
    db.commit()
    return {"provider_id": provider_id, "model_id": data.model_id,
            "enabled": data.enabled}


@router.get("/opencode/connections/{provider_id}")
def ai_internal_credential(provider_id: str, request: Request, workspace_id: uuid.UUID,
                           user: User = Depends(require_user),
                           db: Session = Depends(get_db)):
    """Internal Pi-only retrieval. Never expose plaintext to a browser."""
    secret = os.getenv("PI_GATEWAY_INTERNAL_TOKEN", "")
    claimed = request.headers.get("x-pi-gateway-token", "")
    if not secret or len(secret) < 32 or not _ai_hmac.compare_digest(secret, claimed):
        raise HTTPException(404, "Not found")
    if not request.client or request.client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(404, "Not found")
    workspace = db.scalar(select(Workspace).join(Project, Project.id == Workspace.project_id).where(
        Workspace.id == workspace_id, Workspace.user_id == user.id,
        Project.user_id == user.id, Project.archived_at.is_(None)))
    if workspace is None:
        raise HTTPException(404, "Workspace unavailable")
    _ai_schema(db)
    if not _ai_allowed(db, provider_id):
        raise HTTPException(403, "Provider unavailable")
    record = db.scalar(select(AiUserConnection).where(
        AiUserConnection.user_id == user.id, AiUserConnection.provider_id == provider_id,
        AiUserConnection.auth_status == "verified"))
    if not record:
        raise HTTPException(403, "No verified customer connection for the selected provider")
    model_id = request.query_params.get("model_id")
    key, disabled = _ai_connection_secret_and_models(record)
    if model_id:
        model = db.get(AiProviderModel, (provider_id, model_id))
        if (model_id in disabled or model is None or not model.active
                or not _ai_allowed(db, provider_id, model_id)):
            raise HTTPException(403, "Model is disabled or not available for this account")
    return {"provider_id": provider_id, "connection_id": str(record.id),
            "key": key}


def _ai_catalog_refresh_if_due():
    """Refresh missing or 14-day-old Pi metadata in existing TEST PostgreSQL.

    Runs from existing Gateway maintenance; never during Pi inference, chats,
    file operations or normal account reads. A failed refresh keeps the last
    successful snapshot and is retried on a later maintenance pass.
    """
    from ..database import SessionLocal
    with SessionLocal() as db:
        # This automatic catalog is TEST-only. Never query Pi or write a
        # production catalog if this source is promoted in a later release.
        if getattr(getattr(db.bind, "url", None), "database", None) != "opencode_gateway_test":
            return True
        try:
            _ai_schema(db)
            last = db.scalar(select(func.min(AiProviderCatalog.models_synced_at)))
            count = db.scalar(select(func.count()).select_from(AiProviderCatalog)) or 0
            if count and last is not None and now() - aware(last) < timedelta(days=_AI_REFRESH_DAYS):
                return True
            locked = db.execute(_ai_text("SELECT pg_try_advisory_xact_lock(732062611)")).scalar_one()
            if not locked:
                return False
            sock = os.getenv("PI_SOCKET", "/run/pi-central/pi.sock")
            # Only PUBLIC model metadata is fetched over the existing local
            # filesystem-protected Pi UNIX socket. Customer API credentials
            # still require the separate authenticated internal token.
            internal_token = os.getenv("PI_GATEWAY_INTERNAL_TOKEN", "")
            headers = ({"x-pi-gateway-token": internal_token}
                       if len(internal_token) >= 32 else {})
            with _ai_httpx.Client(transport=_ai_httpx.HTTPTransport(uds=sock),
                                  timeout=60, trust_env=False) as client:
                result = client.get("http://pi/provider", params={
                    "directory": os.getenv("PI_CATALOG_DIRECTORY", "/home/tahir/pi-test"),
                    "models": "full"}, headers=headers)
                result.raise_for_status()
                payload = result.json()
            all_rows = payload.get("all")
            if not isinstance(all_rows, list) or not all_rows:
                raise ValueError("Pi returned an empty provider catalog")
            stamped = now()
            # One provider query and one model query per explicit discovery,
            # instead of one SELECT and one flush for every provider.
            known = {row.id: row for row in db.scalars(select(AiProviderCatalog))}
            valid = {}
            for item in all_rows:
                if not isinstance(item, dict):
                    continue
                pid = item.get("id")
                incoming = item.get("models")
                if (not isinstance(pid, str) or not 0 < len(pid) <= 120 or
                        not isinstance(incoming, dict)):
                    continue
                valid[pid] = (str(item.get("name") or pid)[:200], incoming)
                if pid not in known:
                    row = AiProviderCatalog(id=pid, name=valid[pid][0])
                    db.add(row)
                    known[pid] = row
            if not valid:
                raise ValueError("Pi catalog contains no valid providers")
            db.flush()  # parent rows must exist before model foreign keys
            prior = {}
            for model in db.scalars(select(AiProviderModel).where(
                    AiProviderModel.provider_id.in_(valid))):
                prior.setdefault(model.provider_id, {})[model.model_id] = model
            for pid, (name, incoming) in valid.items():
                row = known[pid]
                row.name = name
                old_models = prior.get(pid, {})
                # Never deactivate a healthy saved catalog because a provider
                # temporarily returned an empty or incomplete inventory.
                if not incoming and old_models:
                    continue
                seen = set()
                for model_id, data in incoming.items():
                    if (not isinstance(model_id, str) or
                            not 0 < len(model_id) <= 300 or
                            not isinstance(data, dict)):
                        continue
                    seen.add(model_id)
                    model = old_models.get(model_id)
                    if model is None:
                        model = AiProviderModel(
                            provider_id=pid, model_id=model_id, name=model_id)
                        db.add(model)
                    model.name = str(data.get("name") or model_id)[:300]
                    metadata = json.dumps(data, separators=(",", ":"))
                    if len(metadata) > 12000:
                        metadata = json.dumps({"id": model_id, "name": model.name})
                    model.details_json = metadata
                    model.active = True
                for model_id, previous in old_models.items():
                    if model_id not in seen:
                        previous.active = False
                row.model_count = len(seen)
                row.models_synced_at = stamped
                row.last_sync_error = None
            db.commit()
            return True
        except (HTTPException, _AiSqlError, _ai_httpx.HTTPError, ValueError, OSError, RuntimeError) as exc:
            db.rollback()
            # Never log Pi responses, provider payloads, tokens or account keys.
            import logging
            status = (exc.response.status_code
                      if isinstance(exc, _ai_httpx.HTTPStatusError) else None)
            logging.getLogger(__name__).warning(
                "TEST AI catalog synchronization postponed (%s, upstream_http=%s)",
                type(exc).__name__, status if status is not None else "-")
            return False


@router.get("/workspaces/{workspace_id}/providers")
def ai_workspace_providers(workspace_id: uuid.UUID, user: User = Depends(require_user),
                           db: Session = Depends(get_db)):
    workspace = db.scalar(select(Workspace.id).where(
        Workspace.id == workspace_id, Workspace.user_id == user.id))
    if workspace is None:
        raise HTTPException(404, "Workspace not found")
    return _ai_provider_rows(db, user.id, include_connected_models=True)


@router.get("/workspaces/{workspace_id}/providers/search")
def ai_workspace_provider_search(workspace_id: uuid.UUID, query: str = "",
                                  user: User = Depends(require_user),
                                  db: Session = Depends(get_db)):
    if db.scalar(select(Workspace.id).where(Workspace.id == workspace_id,
                                          Workspace.user_id == user.id)) is None:
        raise HTTPException(404, "Workspace not found")
    return {"native": False, "providers": _ai_provider_rows(db, user.id, query=query[:120])}


@router.get("/workspaces/{workspace_id}/providers/resolve")
def ai_workspace_provider_resolve(workspace_id: uuid.UUID, name: str = "",
                                   user: User = Depends(require_user),
                                   db: Session = Depends(get_db)):
    if db.scalar(select(Workspace.id).where(Workspace.id == workspace_id,
                                          Workspace.user_id == user.id)) is None:
        raise HTTPException(404, "Workspace not found")
    records = _ai_provider_rows(db, user.id, query=name[:120])
    return {"native": False, "providers": records[:1]}


@router.get("/workspaces/{workspace_id}/providers/{provider_id}/models")
def ai_workspace_models(workspace_id: uuid.UUID, provider_id: str,
                         user: User = Depends(require_user),
                         db: Session = Depends(get_db)):
    if db.scalar(select(Workspace.id).where(Workspace.id == workspace_id,
                                          Workspace.user_id == user.id)) is None:
        raise HTTPException(404, "Workspace not found")
    rows = _ai_provider_rows(db, user.id, provider_id=provider_id)
    if not rows:
        raise HTTPException(404, "Provider unavailable")
    return rows[0]
