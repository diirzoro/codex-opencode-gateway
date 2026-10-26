"""One-time email ownership verification, tokens stored only as SHA-256 digests."""
import hashlib
import os
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import select

from ..models import EmailVerification
from ..config import settings

TOKEN_TTL = timedelta(hours=24)


def required_for_registration(db=None) -> bool:
    """Deployment-controlled launch switch; default secure/verified.

    Set EMAIL_VERIFICATION_REQUIRED=false explicitly for early acquisition.
    Invalid values fail closed instead of disabling verification.
    """
    value = os.getenv("EMAIL_VERIFICATION_REQUIRED", "true").strip().lower()
    if value in {"true", "1", "yes", "on"}:
        default = True
    elif value in {"false", "0", "no", "off"}:
        default = False
    else:
        raise RuntimeError("EMAIL_VERIFICATION_REQUIRED must be true or false")
    if db is not None:
        from . import email_service_policies
        return email_service_policies.enabled(db, "registration_verification", default)
    return default



def smtp_settings(db=None):
    if db is not None:
        from . import admin_email_config
        saved=admin_email_config.read(db)
        if saved:return saved
    return {'smtp_host':os.getenv('SMTP_HOST',''),'smtp_from':os.getenv('SMTP_FROM',''),
            'smtp_username':os.getenv('SMTP_USERNAME',''),'smtp_password':os.getenv('SMTP_PASSWORD',''),
            'smtp_port':int(os.getenv('SMTP_PORT','587'))}


def smtp_ready(db=None):
    config=smtp_settings(db)
    from .email_delivery import ready
    return ready(config)


def send_link(email: str, raw: str, db=None):
    config=smtp_settings(db)
    if not smtp_ready(db):
        raise HTTPException(503, "Email verification delivery is not configured")
    if not settings.public_base_url.startswith("https://"):
        raise HTTPException(503, "Verification links require HTTPS")
    message = EmailMessage()
    message["Subject"] = "Verify your OpenCode Gateway email"
    message["From"] = config["smtp_from"]
    message["To"] = email
    url = settings.public_base_url + "/api/auth/verify-email?token=" + quote(raw, safe="")
    message.set_content("Verify your email address using this link (valid for 24 hours):\n" + url)
    from .email_delivery import send
    send(config,message,error_status=503,timeout=12)


def create_pending(db, user):
    raw = secrets.token_urlsafe(32)
    db.add(EmailVerification(user_id=user.id, token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                             expires_at=datetime.now(timezone.utc)+TOKEN_TTL))
    return raw


def verify(db, raw):
    if not raw or len(raw) > 256:
        raise HTTPException(400, "Invalid verification link")
    digest = hashlib.sha256(raw.encode()).hexdigest()
    token = db.scalar(select(EmailVerification).where(
        EmailVerification.token_hash == digest).with_for_update())
    now = datetime.now(timezone.utc)
    expires = token.expires_at.replace(tzinfo=timezone.utc) if token and token.expires_at and token.expires_at.tzinfo is None else (token.expires_at if token else None)
    if token is None or token.used_at is not None or expires is None or expires <= now:
        raise HTTPException(400, "Verification link is expired or has already been used")
    return token, now


CODE_TTL = timedelta(minutes=10)
MAX_CODE_ATTEMPTS = 5


def require_code_schema(db):
    from sqlalchemy import inspect
    inspector=inspect(db.connection())
    if not inspector.has_table('email_verifications') or not {'verification_method','code_attempts'}.issubset({c['name'] for c in inspector.get_columns('email_verifications')}):
        raise HTTPException(503,'Email code verification requires TEST migration 0025')
    from . import credentials
    if not credentials.available():raise HTTPException(503,'Email code verification requires Gateway credential encryption')


def code_digest(challenge, code):
    import hmac
    from . import credentials
    key=credentials.settings.credentials_encryption_key
    if not key:raise HTTPException(503,'Email code verification is not configured')
    return hmac.new(key.encode(),('email-verification:'+str(challenge)+':'+code).encode(),hashlib.sha256).hexdigest()


def create_code(db,user):
    import uuid
    require_code_schema(db)
    challenge=uuid.uuid4();code=f'{secrets.randbelow(1000000):06d}'
    db.add(EmailVerification(id=challenge,user_id=user.id,token_hash=code_digest(challenge,code),
                            expires_at=datetime.now(timezone.utc)+CODE_TTL,verification_method='code',code_attempts=0))
    return challenge,code


def send_code(email,code,db):
    from .email_delivery import send
    config=smtp_settings(db)
    message=EmailMessage();message['From']=config['smtp_from'];message['To']=email
    message['Subject']='OpenCode Gateway · Email verification code'
    message.set_content('رمز تفعيل حسابك / Your verification code:\n\n'+code+'\n\nصالح لمدة 10 دقائق. لا تشارك الرمز. / Valid for 10 minutes. Do not share this code.')
    send(config,message,error_status=503,timeout=12)


def verify_code(db,challenge,code):
    import hmac
    require_code_schema(db)
    record=db.scalar(select(EmailVerification).where(EmailVerification.id==challenge).with_for_update().execution_options(populate_existing=True))
    now=datetime.now(timezone.utc)
    expires=record.expires_at.replace(tzinfo=timezone.utc) if record and record.expires_at.tzinfo is None else (record.expires_at if record else None)
    if not record or record.verification_method!='code' or record.used_at is not None or not expires or expires<=now or record.code_attempts>=MAX_CODE_ATTEMPTS:
        raise HTTPException(400,'Verification code is invalid, expired, or no longer available')
    if not hmac.compare_digest(record.token_hash,code_digest(challenge,code)):
        record.code_attempts+=1
        if record.code_attempts>=MAX_CODE_ATTEMPTS:record.used_at=now
        db.commit()
        raise HTTPException(400,'Verification code is incorrect; request a new code after five failed attempts')
    return record,now
