"""Verified account identity changes. This is Gateway authentication control, never AI runtime."""
import hashlib
import hmac
import json
import re
import secrets
import uuid
from datetime import datetime,timedelta,timezone

from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,EmailStr,Field
from sqlalchemy import func,select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AccountAudit,EmailVerification,GithubConnection,User
from ..security.identities import normalized_phone
from ..security.passwords import verify_password
from ..services import credentials,email_verification
from ..services.disposable_email import require_permanent_email
from ..services.accounts import user_payload
from .dependencies import require_user

router=APIRouter(prefix='/change',tags=['profile-security'])

class ProfileValues(BaseModel):
    model_config=ConfigDict(extra='forbid')
    username:str|None=Field(default=None,min_length=6,max_length=50,pattern=r'^[A-Za-z0-9_.-]+$')
    email:EmailStr|None=None
    phone:str|None=Field(default=None,min_length=6,max_length=30)
    postal_code:str|None=Field(default=None,min_length=2,max_length=24)

class Begin(ProfileValues):
    current_password:str=Field(min_length=1,max_length=128)

class Confirm(ProfileValues):
    challenge_id:uuid.UUID
    code:str=Field(pattern=r'^[0-9]{6}$')

def _values(db,user,payload):
    values=payload.model_dump(exclude_unset=True,exclude={'current_password','challenge_id','code'})
    if not values:raise HTTPException(422,'Choose an account detail to change')
    if any(value is None for value in values.values()):
        raise HTTPException(422,'Account identity fields cannot be empty')
    if 'username' in values:
        value=values['username'].strip().casefold()
        if not re.fullmatch(r'[a-z0-9_.-]{6,50}',value):raise HTTPException(422,'Invalid username')
        values['username']=value
        if db.scalar(select(User.id).where(User.id!=user.id,func.lower(User.username)==value)) is not None:
            raise HTTPException(409,'Username is already registered')
    if 'email' in values:
        value=str(values['email']).strip().casefold()
        require_permanent_email(value)
        values['email']=value
        if db.scalar(select(User.id).where(User.id!=user.id,func.lower(User.email)==value)) is not None:
            raise HTTPException(409,'Email is already registered')
    if 'phone' in values or 'postal_code' in values:
        phone=normalized_phone(values.get('phone',user.phone),values.get('postal_code',user.postal_code))
        if not phone:raise HTTPException(422,'Enter a valid international phone number')
        values['phone']=phone
        if db.scalar(select(User.id).where(User.id!=user.id,User.phone_identity==phone)) is not None:
            raise HTTPException(409,'Phone is already registered')
    if not any(getattr(user,key)!=value for key,value in values.items()):
        raise HTTPException(409,'No account detail was changed')
    return dict(sorted(values.items()))

def _digest(challenge,code,values):
    key=credentials.settings.credentials_encryption_key
    if not key:raise HTTPException(503,'Email verification encryption is unavailable')
    intent=json.dumps(values,sort_keys=True,separators=(',',':'),ensure_ascii=True)
    return hmac.new(key.encode(),
        ('profile-change:'+str(challenge)+':'+code+':'+intent).encode(),hashlib.sha256).hexdigest()

def _github_email_guard(db,user,values):
    if 'email' in values and values['email']!=user.email:
        if db.scalar(select(GithubConnection.id).where(GithubConnection.user_id==user.id)) is not None:
            raise HTTPException(409,'Disconnect GitHub before changing your Gateway email to maintain verified primary-email matching')

@router.post('/request')
def request_change(data:Begin,user:User=Depends(require_user),db:Session=Depends(get_db)):
    if not verify_password(data.current_password,user.password_hash):
        raise HTTPException(403,'Current account password is incorrect')
    values=_values(db,user,data)
    _github_email_guard(db,user,values)
    email_verification.require_code_schema(db)
    if not email_verification.smtp_ready(db):raise HTTPException(503,'Email verification delivery is unavailable')
    now=datetime.now(timezone.utc)
    recent=db.scalar(select(EmailVerification).where(
        EmailVerification.user_id==user.id,
        EmailVerification.verification_method=='profile')
        .order_by(EmailVerification.created_at.desc()).limit(1))
    if recent and recent.created_at:
        created=recent.created_at if recent.created_at.tzinfo else recent.created_at.replace(tzinfo=timezone.utc)
        if now-created<timedelta(seconds=60):
            raise HTTPException(429,'Wait 60 seconds before requesting another profile verification code')
    for row in db.scalars(select(EmailVerification).where(
        EmailVerification.user_id==user.id,EmailVerification.verification_method=='profile',
        EmailVerification.used_at.is_(None))):row.used_at=now
    identifier=uuid.uuid4();code=f'{secrets.randbelow(1000000):06d}'
    db.add(EmailVerification(id=identifier,user_id=user.id,token_hash=_digest(identifier,code,values),
        verification_method='profile',code_attempts=0,expires_at=now+timedelta(seconds=60)))
    db.flush()
    target=values.get('email',user.email)
    email_verification.send_code(target,code,db)
    db.commit()
    return {'challenge_id':str(identifier),'expires_in':60,
            'destination':'new_email' if 'email' in values and values['email']!=user.email else 'current_email'}

@router.post('/confirm')
def confirm_change(data:Confirm,user:User=Depends(require_user),db:Session=Depends(get_db)):
    email_verification.require_code_schema(db)
    row=db.scalar(select(EmailVerification).where(EmailVerification.id==data.challenge_id,
        EmailVerification.user_id==user.id).with_for_update().execution_options(populate_existing=True))
    now=datetime.now(timezone.utc)
    expires=(row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)) if row and row.expires_at else None
    if (row is None or row.verification_method!='profile' or row.used_at is not None
        or row.code_attempts>=5 or expires is None or expires<=now):
        raise HTTPException(400,'Profile verification code is invalid or expired')
    # Re-check unique ownership and GitHub identity at commit time.
    values=_values(db,user,data)
    _github_email_guard(db,user,values)
    if not hmac.compare_digest(row.token_hash,_digest(row.id,data.code,values)):
        row.code_attempts+=1
        if row.code_attempts>=5:row.used_at=now
        db.commit()
        raise HTTPException(400,'Incorrect code or changed profile details; request a new code')
    for key,value in values.items():setattr(user,key,value)
    row.used_at=now
    db.add(AccountAudit(actor_id=user.id,subject_id=user.id,action='account.profile_verified_update'))
    try:db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'An account identifier was already claimed during verification') from None
    db.refresh(user)
    return user_payload(user)
