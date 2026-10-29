"""Encrypted, non-account registration drafts; only a verified email OTP creates a User.

No AI, model, or workspace service. This is the existing Gateway account-security
control plane. The HttpOnly registration cookie holds a random bearer ticket;
the database holds only its SHA-256 digest, an HMAC email fingerprint, an
encrypted registration payload (password hash, never plaintext), and OTP HMAC.
"""
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import User, PendingRegistration
from ..schemas import RegisterRequest
from ..security.identities import normalized_phone
from ..security.passwords import hash_password
from . import credentials, email_verification
from .disposable_email import require_permanent_email
from .location_validation import validate_locations
from .entitlements import CORE_TRIAL_DAYS

CODE_LIFETIME=timedelta(seconds=60)
DRAFT_LIFETIME=timedelta(hours=1)
MAX_ATTEMPTS=5
MAX_SENDS_PER_DRAFT=5
MAX_SENDS_PER_EMAIL_HOUR=5
COOKIE='gateway_registration_draft'


def aware(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def require_schema(db):
    from sqlalchemy import inspect
    if not inspect(db.connection()).has_table('pending_registrations'):
        raise HTTPException(503,'Registration verification requires TEST migration 0030')
    if not credentials.available():
        raise HTTPException(503,'Encrypted registration drafts are not configured')


def fingerprint(email):
    key=credentials.settings.credentials_encryption_key
    if not key:raise HTTPException(503,'Registration verification is not configured')
    return hmac.new(key.encode(),('registration-email:'+email).encode(),hashlib.sha256).hexdigest()


def normalized(data, db, *, original_hash=None):
    email=str(data.email).strip().casefold()
    require_permanent_email(email)
    username=data.username.strip().casefold() if data.username else 'user_'+uuid.uuid4().hex[:24]
    phone=normalized_phone(data.phone,data.postal_code)
    if phone is None:raise HTTPException(422,'Enter a valid international phone number')
    validate_locations(db,data.country_id,data.region_id,data.city_id)
    if db.scalar(select(User.id).where(or_(
            func.lower(User.username)==username,func.lower(User.email)==email,
            User.phone_identity==phone))):
        raise HTTPException(409,'Username, email or phone number is already registered')
    return {'username':username,'email':email,'phone':phone,
            'password_hash':original_hash if original_hash is not None else hash_password(data.password),
            'postal_code':data.postal_code.strip(),'country_id':data.country_id,
            'region_id':data.region_id,'city_id':data.city_id}


def find(db,challenge,ticket):
    require_schema(db)
    row=db.scalar(select(PendingRegistration).where(PendingRegistration.id==challenge)
        .with_for_update().execution_options(populate_existing=True))
    if (row is None or not isinstance(ticket,str) or len(ticket)<32 or
        not hmac.compare_digest(row.ticket_hash,hashlib.sha256(ticket.encode()).hexdigest())):
        raise HTTPException(404,'Registration request not found. Review your details and register again.')
    if aware(row.expires_at)<=datetime.now(timezone.utc):
        raise HTTPException(410,'Registration draft expired. Review your details and register again.')
    return row


def _email_send_limit(db,email,now,skip=None):
    fp=fingerprint(email)
    recent=list(db.scalars(select(PendingRegistration).where(
        PendingRegistration.email_fingerprint==fp,
        PendingRegistration.last_sent_at>now-timedelta(hours=1))))
    if any(aware(row.last_sent_at)>now-CODE_LIFETIME for row in recent if row is not skip):
        raise HTTPException(429,'Wait one minute before requesting another code for this email')
    if sum(row.sends for row in recent if row is not skip)>=MAX_SENDS_PER_EMAIL_HOUR:
        raise HTTPException(429,'Email code request limit reached. Try later.')
    return fp


def _new_code(identifier):
    code=f'{secrets.randbelow(1000000):06d}'
    digest=email_verification.code_digest('registration:'+str(identifier),code)
    return code,digest


def public(row):
    now=datetime.now(timezone.utc)
    data=json.loads(credentials.decrypt(row.payload_ciphertext))
    return {'status':'pending_verification','email':data['email'],
            'verification_challenge':str(row.id),
            'verification_expires_in':max(0,int((aware(row.code_expires_at)-now).total_seconds()+.999)),
            'resend_in':max(0,int((aware(row.last_sent_at)+CODE_LIFETIME-now).total_seconds()+.999))}


def start(db,data):
    require_schema(db)
    if not email_verification.smtp_ready(db):
        raise HTTPException(503,'Email verification is unavailable; registration cannot proceed')
    details=normalized(data,db)
    now=datetime.now(timezone.utc)
    fp=_email_send_limit(db,details['email'],now)
    identifier=uuid.uuid4()
    ticket=secrets.token_urlsafe(32)
    code,digest=_new_code(identifier)
    row=PendingRegistration(id=identifier,email_fingerprint=fp,
        ticket_hash=hashlib.sha256(ticket.encode()).hexdigest(),
        payload_ciphertext=credentials.encrypt(json.dumps(details)),
        code_hash=digest,code_expires_at=now+CODE_LIFETIME,
        last_sent_at=now,expires_at=now+DRAFT_LIFETIME,attempts=0,sends=1)
    try:
        db.add(row);db.flush()
        email_verification.send_code(details['email'],code,db)
        db.commit()
    except Exception:
        db.rollback();raise
    return public(row),ticket


def resend(db,challenge,ticket):
    row=find(db,challenge,ticket)
    now=datetime.now(timezone.utc)
    if aware(row.last_sent_at)>now-CODE_LIFETIME:
        raise HTTPException(429,'Wait one minute before requesting another verification code')
    if row.sends>=MAX_SENDS_PER_DRAFT:
        raise HTTPException(429,'Verification request limit reached. Start again later.')
    data=json.loads(credentials.decrypt(row.payload_ciphertext))
    _email_send_limit(db,data['email'],now,skip=row)
    if not email_verification.smtp_ready(db):
        raise HTTPException(503,'Email verification is unavailable')
    code,digest=_new_code(row.id)
    row.code_hash=digest;row.attempts=0;row.code_expires_at=now+CODE_LIFETIME
    row.last_sent_at=now;row.sends+=1
    try:email_verification.send_code(data['email'],code,db);db.commit()
    except Exception:db.rollback();raise
    return public(row)


def edit(db,challenge,ticket,patch):
    row=find(db,challenge,ticket)
    old=json.loads(credentials.decrypt(row.payload_ciphertext))
    values=patch.model_dump(exclude_unset=True)
    if 'password' in values and values['password'] is None:
        values.pop('password')
    candidate=RegisterRequest.model_validate({
        'username':values.get('username',old['username']),
        'email':values.get('email',old['email']),
        'phone':values.get('phone',old['phone']),
        'postal_code':values.get('postal_code',old['postal_code']),
        'country_id':values.get('country_id',old['country_id']),
        'region_id':values.get('region_id',old['region_id']),
        'city_id':values.get('city_id',old['city_id']),
        'password':values.get('password') or 'Placeholder9!'
    })
    details=normalized(candidate,db,original_hash=(
        hash_password(values['password']) if values.get('password') else old['password_hash']))
    changed=details['email']!=old['email']
    now=datetime.now(timezone.utc)
    if changed:
        if row.sends>=MAX_SENDS_PER_DRAFT:
            raise HTTPException(429,'Verification request limit reached. Start again later.')
        if not email_verification.smtp_ready(db):
            raise HTTPException(503,'Email verification is unavailable')
        fp=_email_send_limit(db,details['email'],now,skip=row)
        code,digest=_new_code(row.id)
        row.email_fingerprint=fp
        row.code_hash=digest;row.code_expires_at=now+CODE_LIFETIME
        row.last_sent_at=now;row.attempts=0;row.sends+=1
    row.payload_ciphertext=credentials.encrypt(json.dumps(details))
    try:
        if changed:email_verification.send_code(details['email'],code,db)
        db.commit()
    except Exception:db.rollback();raise
    result=public(row)
    result['email_changed']=changed
    return result


def finish(db,challenge,ticket,code):
    row=find(db,challenge,ticket)
    now=datetime.now(timezone.utc)
    if aware(row.code_expires_at)<=now or row.attempts>=MAX_ATTEMPTS:
        raise HTTPException(400,'Verification code expired or too many attempts. Request another code.')
    if not hmac.compare_digest(
        row.code_hash,email_verification.code_digest('registration:'+str(row.id),code)):
        row.attempts+=1;db.commit()
        raise HTTPException(400,'Incorrect verification code. Check the code and retry.')
    details=json.loads(credentials.decrypt(row.payload_ciphertext))
    # Even if the email was free at draft time, a verified User can have appeared
    # meanwhile. Database uniqueness constraints resolve competing drafts safely.
    if db.scalar(select(User.id).where(or_(
        func.lower(User.username)==details['username'],
        func.lower(User.email)==details['email'],User.phone_identity==details['phone']))):
        raise HTTPException(409,'Username, email or phone is now registered. Edit your details.')
    user=User(**details,status='active',trial_started_at=now,
              trial_ends_at=now+timedelta(days=CORE_TRIAL_DAYS),last_login_at=now)
    from ..models import AccountAudit
    try:
        db.add(user);db.flush()
        db.add(AccountAudit(subject_id=user.id,action='account.email_verified'))
        db.delete(row);db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'Username, email or phone is now registered. Edit your details.') from None
    db.refresh(user)
    return user


def abandon(db,challenge,ticket):
    row=find(db,challenge,ticket)
    db.delete(row);db.commit()
    return {'cancelled':True}


def sweep():
    """Existing Gateway maintenance loop only; no customer account deletion."""
    from ..database import SessionLocal
    with SessionLocal() as db:
        if not db.bind.dialect.has_table(db.connection(), 'pending_registrations'):
            return
        db.execute(__import__('sqlalchemy').delete(PendingRegistration).where(
            PendingRegistration.expires_at<datetime.now(timezone.utc)))
        db.commit()
