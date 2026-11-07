"""Real GitHub App integration. Config-gated: unconfigured deployments truthfully refuse.

Nothing here uses a Personal Access Token, simulates a connection, or exposes a token to
the browser. Installation tokens are short-lived and used only server-side.
"""
from __future__ import annotations
import hashlib, hmac, json, secrets, uuid
from datetime import datetime, timedelta, timezone
import httpx
from urllib.parse import quote, urlencode
from fastapi import HTTPException
from sqlalchemy import delete, select, or_, func, text
from sqlalchemy.exc import IntegrityError
from ..config import settings
from ..models import GithubAuthState, GithubConnection, GithubIdentityRegistry, User, AccountAudit
from . import credentials, github_app_config
from .entitlements import require_advanced

STATE_TTL_MINUTES = 15
EMAIL_PROOF_TTL = timedelta(seconds=60)
EMAIL_SEND_ACTION = 'github.mail.request:'
AUTH_AUDIT_PREFIX = 'github.auth.'
AUTH_AUDIT_RETENTION = timedelta(days=90)
IDENTITY_IN_USE = ('This GitHub account is already connected to another OpenCode Gateway account and cannot be connected to two Gateway accounts simultaneously.\n\n'
    'Please sign in to the Gateway account where this GitHub identity is currently connected and disconnect it first, or select a different GitHub account.\n\n'
    'Logging out does not disconnect GitHub.')


def _audit_authorization(db,user,identity_id,event):
    # A private, bounded history in the existing audit table. No email, tokens,
    # codes, session/connection UUIDs or reusable authorization are recorded.
    if type(identity_id) is int and identity_id>0:
        db.add(AccountAudit(subject_id=user.id,action=AUTH_AUDIT_PREFIX+event+':'+str(identity_id)))


def _require_identity_registry(db):
    from sqlalchemy import inspect
    if not inspect(db.connection()).has_table(GithubIdentityRegistry.__tablename__):
        raise HTTPException(503,'GitHub identity verification requires TEST migration 0029')


def _require_email_verification_service(db):
    from . import email_service_policies
    if not email_service_policies.enabled(db,'github_connection_verification',True):
        raise HTTPException(503,'GitHub connection verification is disabled by the administrator; new connections are blocked')


def _primary_email_hmac(identity_id,email):
    key=credentials.settings.credentials_encryption_key
    if not key:raise HTTPException(503,'GitHub identity verification requires Gateway credential encryption')
    value='github-primary-email:'+str(identity_id)+':'+email.strip().casefold()
    return hmac.new(key.encode(),value.encode(),hashlib.sha256).hexdigest()


def schema_status(db) -> dict:
    """Read-only structure check. Never return rows, DSNs, tokens or DB errors."""
    from alembic.migration import MigrationContext
    from sqlalchemy import inspect
    from sqlalchemy.exc import SQLAlchemyError
    required = {
        GithubConnection.__tablename__: set(GithubConnection.__table__.columns.keys()),
        GithubAuthState.__tablename__: set(GithubAuthState.__table__.columns.keys()),
        GithubIdentityRegistry.__tablename__: set(GithubIdentityRegistry.__table__.columns.keys()),
        "projects": {"github_repository_id", "github_installation_id", "remote_url", "remote_branch"},
    }
    try:
        connection = db.connection()
        inspector = inspect(connection)
        missing = []
        for table, columns in required.items():
            if not inspector.has_table(table):
                missing.append(table)
            else:
                actual = {column["name"] for column in inspector.get_columns(table)}
                missing.extend(table + "." + name for name in sorted(columns - actual))
        revisions = list(MigrationContext.configure(connection).get_current_heads())
        return {"checked": True, "ready": not missing, "missing": missing,
                "revisions": revisions, "required_migrations": ["0003_github_provider", "0005_account_management", "0028_github_connection_identity", "0029_github_identity_registry"]}
    except SQLAlchemyError:
        return {"checked": False, "ready": False, "missing": [], "revisions": [],
                "reason": "Database schema inspection unavailable"}


def configured(db=None, *, config=None) -> bool:
    cfg=config if config is not None else github_app_config.effective(settings,db)
    return bool(cfg.github_configured and cfg.github_client_id and cfg.github_client_secret and credentials.available())

def require_configured(config=None):
    if not configured(config=config):
        raise HTTPException(503, "GitHub App is not configured on this server")

def install_url(state: str, config=None) -> str:
    cfg=config if config is not None else github_app_config.effective(settings)
    require_configured(cfg)
    base = cfg.github_web_base.rstrip("/")
    return f"{base}/apps/{cfg.github_app_slug}/installations/new?state={state}"

def _jwt(config=None) -> str:
    cfg=config if config is not None else github_app_config.effective(settings)
    require_configured(cfg)
    try:
        import jwt
    except ImportError:  # pragma: no cover - dependency is pinned in requirements
        raise HTTPException(503, "GitHub App signing dependency is unavailable")
    now = datetime.now(timezone.utc)
    payload = {"iat": int((now - timedelta(seconds=60)).timestamp()), "exp": int((now + timedelta(minutes=9)).timestamp()), "iss": str(cfg.github_app_id)}
    return jwt.encode(payload, cfg.github_private_key, algorithm="RS256")

def _api(method: str, path: str, token: str | None = None, jwt_token: str | None = None, **kwargs):
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"
    try:
        with httpx.Client(base_url=settings.github_api_base, headers=headers, timeout=20, follow_redirects=False) as client:
            response = client.request(method, path, **kwargs)
    except httpx.HTTPError:
        raise HTTPException(502, "GitHub API request failed")
    if response.status_code == 404:
        raise HTTPException(404, "GitHub resource not found")
    if response.status_code in (401, 403):
        raise HTTPException(403, "GitHub denied the request; verify App permissions")
    if response.status_code >= 400:
        raise HTTPException(502, "GitHub API returned an error")
    return response.json() if response.content else None

def lock_owner(db, user):
    # All connection mutations acquire the same owner row first. A delayed
    # callback cannot commit after a completed disconnect/new transaction.
    current = db.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
    if current is None or current.status != 'active':
        raise HTTPException(403, 'Active Gateway account required')
    return current


def begin_fresh_link(db, user, auth_session_id):
    cfg = github_app_config.effective(settings, db)
    require_configured(cfg)
    _require_identity_registry(db)
    _require_email_verification_service(db)
    if not auth_session_id:
        raise HTTPException(401, 'Authenticated Gateway session required')
    lock_owner(db,user)
    existing=db.scalar(select(GithubConnection).where(GithubConnection.user_id==user.id))
    if existing is not None:
        raise HTTPException(409,'Disconnect the existing GitHub account before linking another')
    disconnect(db,user,commit=False)
    return begin_authorization(db, user, auth_session_id=auth_session_id)


def begin_authorization(db, user, *, auth_session_id, connection_id=None, expected_identity=None):
    cfg = github_app_config.effective(settings, db)
    require_configured(cfg)
    state = 'oauth_' + secrets.token_urlsafe(32)
    record = GithubAuthState(state=state, user_id=user.id, auth_session_id=auth_session_id,
        connection_id=connection_id or uuid.uuid4(),
        expires_at=datetime.now(timezone.utc)+timedelta(minutes=STATE_TTL_MINUTES))
    if expected_identity:
        record.pending_payload = credentials.encrypt(json.dumps({'expected_identity': expected_identity}))
    db.add(record)
    db.commit()
    params = urlencode({'client_id':cfg.github_client_id, 'redirect_uri':cfg.github_callback_url,
                        'state':state, 'prompt':'select_account'})
    return cfg.github_web_base.rstrip('/')+'/login/oauth/authorize?'+params


def pending_connection(db, user, auth_session_id):
    if not auth_session_id:
        return None
    records = db.scalars(select(GithubAuthState).where(GithubAuthState.user_id == user.id,
        GithubAuthState.auth_session_id == auth_session_id, GithubAuthState.consumed.is_(True),
        GithubAuthState.pending_payload.is_not(None)))
    for record in records:
        if _aware(record.expires_at) <= datetime.now(timezone.utc):
            record.pending_payload = None
            continue
        payload = json.loads(credentials.decrypt(record.pending_payload))
        if 'identity' in payload:
            proof=payload.get('email_proof') or {}
            valid=bool(proof.get('email_matched') and proof.get('verified') and _aware(datetime.fromisoformat(proof['expires_at']))>datetime.now(timezone.utc))
            return {'connection_id':str(record.connection_id), 'github_user_id':payload['identity']['id'],
                    'github_login':payload['identity']['login'], 'installations':payload['installations'],
                    'email_verification':{'required':True,'verified':valid,
                        'sent':proof.get('sent',False),'expires_at':proof.get('expires_at')}}
    return None


def connection_status(db, user, auth_session_id=None) -> dict:
    if not configured(db):
        return {'connected':False, 'available':False, 'configured':False,
                'reason':'GitHub App integration is not configured'}
    row = db.scalar(select(GithubConnection).where(GithubConnection.user_id == user.id))
    result = {'connected':False, 'available':True, 'configured':True}
    if row and not row.suspended and row.user_token and (not row.token_expires_at or _aware(row.token_expires_at)>datetime.now(timezone.utc)):
        result.update(connected=True, connection_id=str(row.id), account_login=row.account_login,
                      github_login=row.github_user_login, github_user_id=row.github_user_id,
                      account_type=row.account_type, target_type=row.target_type)
    result['pending'] = pending_connection(db, user, auth_session_id)
    db.commit()
    return result

def installation_token(connection: GithubConnection) -> str:
    # Every customer operation uses the customer's authorization, never the App's
    # broader installation token. Membership removal therefore takes effect at GitHub.
    if not connection.user_token or (connection.token_expires_at and _aware(connection.token_expires_at)<=datetime.now(timezone.utc)):
        raise HTTPException(403,'Reconnect GitHub: user authorization expired')
    return credentials.decrypt(connection.user_token)

def _aware(value): return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

def exchange_code(code, redirect_uri=None, verifier=None, *, config=None):
    cfg=config if config is not None else github_app_config.effective(settings)
    try:
        with httpx.Client(timeout=20,follow_redirects=False,trust_env=False) as client:
            response=client.post(cfg.github_web_base.rstrip('/')+'/login/oauth/access_token',headers={'Accept':'application/json'},data={'client_id':cfg.github_client_id,'client_secret':cfg.github_client_secret,'code':code,'redirect_uri':redirect_uri or cfg.github_callback_url,**({'code_verifier':verifier} if verifier else {})})
            result=response.json()
    except (httpx.HTTPError,ValueError): raise HTTPException(502,'GitHub authorization failed')
    if response.status_code!=200 or not result.get('access_token'): raise HTTPException(403,'GitHub authorization failed')
    return result

def connection_for(db, user) -> GithubConnection:
    row = db.scalar(select(GithubConnection).where(GithubConnection.user_id == user.id))
    if row is None or row.suspended:
        raise HTTPException(503, "GitHub is not connected for this account")
    return row

def _state(db, state, user, auth_session_id, *, pending=False):
    lock_owner(db, user)
    record = db.scalar(select(GithubAuthState).where(GithubAuthState.state == state).with_for_update())
    if not record or record.user_id != user.id or not auth_session_id or record.auth_session_id != auth_session_id:
        raise HTTPException(403, 'GitHub transaction does not belong to this Gateway session')
    if _aware(record.expires_at) <= datetime.now(timezone.utc):
        raise HTTPException(400, 'GitHub authorization state expired')
    if record.consumed != pending:
        raise HTTPException(400, 'Unknown or already-used GitHub state')
    return record


def installations_for(token, cfg):
    result=[]
    for page in range(1,101):
        items=(_api('GET','/user/installations',token=token,params={'per_page':100,'page':page}) or {}).get('installations',[])
        for item in items:
            if item.get('app_id') == cfg.github_app_id and type(item.get('id')) is int:
                account=item.get('account') or {}
                result.append({'id':item['id'], 'login':account.get('login','GitHub'), 'type':account.get('type','User'), 'account_id':account.get('id')})
        if len(items)<100: return result
    raise HTTPException(502, 'GitHub installation list exceeded safe pagination')


def handle_callback(db, state, installation_id, setup_action, code=None, *, user, auth_session_id):
    cfg=github_app_config.effective(settings,db)
    require_configured(cfg)
    if not state: raise HTTPException(422, 'Missing GitHub authorization parameters')
    record=_state(db,state,user,auth_session_id)
    require_advanced(db,user)
    expected=None
    if record.pending_payload:
        expected=json.loads(credentials.decrypt(record.pending_payload)).get('expected_identity')
    # Single use even when the vendor rejects a code. Owner lock prevents races.
    record.consumed=True
    record.pending_payload=None
    try:
        if not code:
            if not state.startswith('setup_') or setup_action not in {'install','update'}:
                raise HTTPException(422,'Missing GitHub authorization code')
            return {'redirect':begin_authorization(db,user,auth_session_id=auth_session_id,
                      connection_id=record.connection_id,expected_identity=expected)}
        token=exchange_code(code,config=cfg)
        identity=_api('GET','/user',token=token['access_token']) or {}
        if type(identity.get('id')) is not int or not identity.get('login'):
            raise HTTPException(502,'GitHub user identity unavailable')
        if expected and identity['id'] != expected:
            revoke_token(token['access_token'],cfg)
            raise HTTPException(409,'GitHub account changed during installation; start a new connection')
        eligible=installations_for(token['access_token'],cfg)
        if installation_id is not None:
            eligible=[item for item in eligible if item['id']==installation_id]
            if not eligible: raise HTTPException(403,'Installation is not authorized for this GitHub user')
        _assert_identity_available(db,user,identity['id'],eligible)
        # Never save an active connection from a callback. No repository access
        # until a same-origin authenticated POST confirms this exact identity.
        payload={'identity':{'id':identity['id'],'login':identity['login']},
                 'installations':eligible,'token':token['access_token'],
                 'expires_at':(datetime.now(timezone.utc)+timedelta(seconds=int(token['expires_in']))).isoformat() if token.get('expires_in') is not None else None}
        record.pending_payload=credentials.encrypt(json.dumps(payload))
        db.commit()
        return {'pending':True}
    except HTTPException as exc:
        # Do not revoke a token or Grant belonging to the active owner, even if
        # GitHub returned an authorization associated with an existing session.
        conflict=(exc.status_code==409 and exc.detail==IDENTITY_IN_USE) or (exc.status_code==503 and str(exc.detail).startswith('Existing GitHub connection ownership'))
        if conflict:_audit_authorization(db,user,identity['id'],'refused')
        if 'token' in locals() and not conflict:revoke_token(token['access_token'],cfg)
        db.commit()
        raise


def _pending(db,user,auth_session_id,connection_id):
    lock_owner(db,user)
    record=db.scalar(select(GithubAuthState).where(GithubAuthState.user_id==user.id,
        GithubAuthState.connection_id==connection_id, GithubAuthState.consumed.is_(True),
        GithubAuthState.pending_payload.is_not(None)).with_for_update())
    if not record: raise HTTPException(409,'GitHub confirmation is no longer available')
    _state(db,record.state,user,auth_session_id,pending=True)
    payload=json.loads(credentials.decrypt(record.pending_payload))
    if 'identity' not in payload: raise HTTPException(409,'GitHub authorization is incomplete')
    return record,payload


def _assert_identity_available(db,user,identity_id,installations):
    # Migration0028 preserved legacy rows with a NULL immutable ID. Resolve
    # only that missing ownership metadata from each row's own stored token;
    # otherwise another installation could bypass the old row's ownership.
    legacy=list(db.scalars(select(GithubConnection).where(
        GithubConnection.github_user_id.is_(None)).with_for_update()))
    if legacy:
        claimed=set(db.scalars(select(GithubConnection.github_user_id).where(GithubConnection.github_user_id.is_not(None))))
        resolved=[]
        for row in legacy:
            try:
                # A revoked/expired legacy user token must not block every new
                # customer's connection if this App can verify the original
                # personal installation's immutable GitHub owner ID.
                owner={}
                if row.user_token and (not row.token_expires_at or _aware(row.token_expires_at)>datetime.now(timezone.utc)):
                    try: owner=_api('GET','/user',token=credentials.decrypt(row.user_token),timeout=4) or {}
                    except HTTPException: pass
                actual=owner.get('id')
                if type(actual) is not int or actual<=0:
                    if row.account_type!='User' or not row.installation_id:
                        raise ValueError('Unverifiable legacy installation')
                    cfg=github_app_config.effective(settings,db)
                    if row.app_id and row.app_id!=cfg.github_app_id:
                        raise ValueError('Legacy installation App mismatch')
                    installation=_api('GET',f'/app/installations/{row.installation_id}',jwt_token=_jwt(cfg),timeout=4) or {}
                    account=installation.get('account') or {}
                    if (installation.get('app_id')!=cfg.github_app_id or
                        installation.get('id')!=row.installation_id or
                        account.get('type')!='User' or installation.get('target_type')!='User'):
                        raise ValueError('Unverifiable personal installation')
                    actual=account.get('id')
                    owner=account
                if type(actual) is not int or actual<=0 or actual in claimed:raise ValueError('Legacy identity conflict')
            except Exception:
                # Organizational/unknown ownership stays blocked until a
                # verified recovery; never guess from a login or legacy email.
                raise HTTPException(503,'Existing GitHub connection ownership requires verified recovery before new connections') from None
            claimed.add(actual);resolved.append((row,actual,owner.get('login')))
        for row,actual,login in resolved:row.github_user_id=actual;row.github_user_login=login
        db.flush()
    foreign=db.scalar(select(GithubConnection.id).where(GithubConnection.user_id!=user.id,
        or_(GithubConnection.github_user_id==identity_id,
            GithubConnection.installation_id.in_([i['id'] for i in installations if i.get('type')=='User' and i.get('account_id')==identity_id]))))
    if foreign:raise HTTPException(409,IDENTITY_IN_USE)


def _verified_primary_email(token,identity_id):
    # Never use Gateway user.email or /user's unverified public email as proof.
    identity=_api('GET','/user',token=token,timeout=4) or {}
    if identity.get('id')!=identity_id:raise HTTPException(403,'GitHub identity changed; start again')
    try:addresses=_api('GET','/user/emails',token=token,params={'per_page':100},timeout=4)
    except HTTPException:
        raise HTTPException(503,'GitHub verified email unavailable; this App needs Email addresses: read permission') from None
    if not isinstance(addresses,list):raise HTTPException(502,'GitHub email response is invalid')
    from pydantic import TypeAdapter,EmailStr,ValidationError
    for address in addresses:
        if not isinstance(address,dict) or address.get('verified') is not True or address.get('primary') is not True:continue
        try:email=str(TypeAdapter(EmailStr).validate_python(address.get('email')))
        except ValidationError:continue
        if email.lower().endswith('@users.noreply.github.com'):continue
        return email
    raise HTTPException(409,'Verify a deliverable primary email on GitHub before connecting')


def _require_gateway_email_matches_github(user, github_primary_email):
    """An OAuth GitHub ID is necessary but no longer sufficient to link.

    The authenticated Gateway account email must match the independently
    GitHub-verified primary mailbox. Do not expose that mailbox on mismatch.
    """
    gateway_email=str(getattr(user,'email','') or '').strip().casefold()
    github_email=str(github_primary_email or '').strip().casefold()
    if (not gateway_email or not github_email or
        not hmac.compare_digest(gateway_email.encode('utf-8'),github_email.encode('utf-8'))):
        raise HTTPException(403,
            'This Gateway account email is not the verified primary email of the authorized GitHub account. '
            'Use the matching GitHub account or verify and update your Gateway email before linking.')


def _email_code_hash(connection_id,nonce,code):
    # Reuse the existing keyed OTP digest, with a separate domain. Do not put
    # GitHub challenges in registration EmailVerification rows or verify accounts.
    from .email_verification import code_digest
    return code_digest('github-ownership:'+str(connection_id)+':'+nonce,code)


def _send_ownership_code(email,code,db):
    from email.message import EmailMessage
    from .email_verification import smtp_settings
    from .email_delivery import send
    cfg=smtp_settings(db)
    message=EmailMessage()
    message['From']=cfg.get('smtp_from','')
    message['To']=email
    message['Subject']='OpenCode Gateway · Confirm GitHub repository connection'
    message.set_content('رمز تأكيد ربط مستودعات GitHub / GitHub connection code:\n\n'+code+
        '\n\nصالح لمدة دقيقة واحدة. لا تشاركه. إذا لم تطلب الربط فتجاهل الرسالة.'
        '\nValid for 1 minute. Do not share it. Ignore this email if you did not request this connection.')
    send(cfg,message,error_status=503,timeout=12)


def send_connection_code(db,user,auth_session_id,connection_id,submitted_email):
    _require_email_verification_service(db)
    record,payload=_pending(db,user,auth_session_id,connection_id)
    _assert_identity_available(db,user,payload['identity']['id'],payload['installations'])
    now=datetime.now(timezone.utc)
    # Short-lived, pseudonymous abuse counters survive fresh OAuth transactions.
    # They store no email, OAuth token, code or permanent ownership reservation.
    key=_email_code_hash('rate','identity',str(payload['identity']['id']))[:32]
    if db.get_bind().dialect.name=='postgresql':
        # Serialize limits for the same GitHub identity across Gateway users.
        # Transaction-local advisory locks need no schema/config changes.
        db.execute(text('SELECT pg_advisory_xact_lock(:namespace, :identity)'),
                   {'namespace':194731,'identity':int(key[:8],16)&0x7fffffff})
    action=EMAIL_SEND_ACTION+key
    recent=select(AccountAudit).where(AccountAudit.action.like('github.mail.%'),
        or_(AccountAudit.subject_id==user.id,AccountAudit.action.in_([action,'github.mail.sent:'+key])))
    count=db.scalar(select(func.count()).select_from(recent.where(AccountAudit.created_at>now-timedelta(hours=1)).subquery()))
    last=db.scalar(recent.order_by(AccountAudit.created_at.desc()).limit(1))
    if count>=5 or last and _aware(last.created_at)>now-timedelta(seconds=60):
        raise HTTPException(429,'Wait before requesting another GitHub email code')
    old=payload.get('email_proof') or {}
    if old.get('attempts',0)>=5:
        raise HTTPException(429,'Code attempts exhausted; start a fresh connection')
    # Every email-match attempt consumes the same persisted rate limit, not
    # just successful sends. A wrong address cannot be guessed without bounds.
    payload.pop('email_proof',None)
    record.pending_payload=credentials.encrypt(json.dumps(payload))
    db.add(AccountAudit(subject_id=user.id,action=action))
    try:
        email=_verified_primary_email(payload['token'],payload['identity']['id'])
        _require_gateway_email_matches_github(user,email)
        if not hmac.compare_digest(email.casefold().encode(),submitted_email.strip().casefold().encode()):
            raise HTTPException(403,'GitHub email authorization denied: the entered address does not match the verified primary email for the selected GitHub account. No verification email was sent.')
        nonce=secrets.token_urlsafe(16);code=f'{secrets.randbelow(1000000):06d}'
        expires=min(_aware(record.expires_at),now+EMAIL_PROOF_TTL)
        proof={'nonce':nonce,'digest':_email_code_hash(connection_id,nonce,code),
            'email_hmac':_primary_email_hmac(payload['identity']['id'],email),
            'expires_at':expires.isoformat(),'issued_at':now.isoformat(),'attempts':old.get('attempts',0),
            'email_matched':True,'verified':False,'sent':False}
        payload['email_proof']=proof
        _send_ownership_code(email,code,db)
    except HTTPException as exc:
        if 'proof' in locals():proof.pop('digest',None)
        record.pending_payload=credentials.encrypt(json.dumps(payload));db.commit()
        if exc.status_code in {400,403}:raise
        # Do not return provider email details or distinguish guessed addresses.
        raise HTTPException(503,'GitHub email verification is unavailable. Check App email permission and mail delivery.') from None
    proof['sent']=True
    record.pending_payload=credentials.encrypt(json.dumps(payload));db.commit()
    return {'sent':True,'expires_at':proof['expires_at']}


def verify_connection_code(db,user,auth_session_id,connection_id,code):
    _require_email_verification_service(db)
    record,payload=_pending(db,user,auth_session_id,connection_id)
    _assert_identity_available(db,user,payload['identity']['id'],payload['installations'])
    proof=payload.get('email_proof') or {}
    if (not proof.get('email_matched') or not proof.get('sent') or proof.get('verified') or not proof.get('digest') or proof.get('attempts',0)>=5
        or _aware(datetime.fromisoformat(proof['expires_at']))<=datetime.now(timezone.utc)
        or not proof.get('issued_at') or datetime.now(timezone.utc)-_aware(datetime.fromisoformat(proof['issued_at']))>=EMAIL_PROOF_TTL):
        raise HTTPException(400,'GitHub code is expired or unavailable; request a fresh code')
    proof['attempts']=proof.get('attempts',0)+1
    valid=hmac.compare_digest(proof['digest'],_email_code_hash(connection_id,proof['nonce'],code))
    if valid:
        proof['verified']=True;proof.pop('digest',None)
        # The emailed OTP expires after 60 seconds; successful verification
        # remains valid for the existing OAuth transaction, not a second OTP.
        proof['expires_at']=record.expires_at.isoformat()
        _audit_authorization(db,user,payload['identity']['id'],'email_verified')
    record.pending_payload=credentials.encrypt(json.dumps(payload));db.commit()
    if not valid:raise HTTPException(400,'Incorrect GitHub verification code')
    return {'verified':True}


def expire_pending_authorizations():
    """Run in the existing Gateway maintenance loop; no new daemon or table."""
    from ..database import SessionLocal
    now=datetime.now(timezone.utc)
    with SessionLocal() as db:
        states=list(db.scalars(select(GithubAuthState.state).where(GithubAuthState.expires_at<=now)
            .order_by(GithubAuthState.expires_at).limit(100).with_for_update(skip_locked=True)))
        if states:db.execute(delete(GithubAuthState).where(GithubAuthState.state.in_(states)))
        audits=list(db.scalars(select(AccountAudit.id).where(AccountAudit.action.like('github.mail.%'),
            AccountAudit.created_at<now-timedelta(hours=24)).order_by(AccountAudit.created_at,AccountAudit.id).limit(100)))
        if audits:db.execute(delete(AccountAudit).where(AccountAudit.id.in_(audits)))
        history=list(db.scalars(select(AccountAudit.id).where(AccountAudit.action.like(AUTH_AUDIT_PREFIX+'%'),
            AccountAudit.created_at<now-AUTH_AUDIT_RETENTION).order_by(AccountAudit.created_at,AccountAudit.id).limit(100)))
        if history:db.execute(delete(AccountAudit).where(AccountAudit.id.in_(history)))
        from sqlalchemy import inspect
        if inspect(db.connection()).has_table(GithubIdentityRegistry.__tablename__):
            active=select(GithubConnection.id).where(GithubConnection.github_user_id==GithubIdentityRegistry.github_user_id).exists()
            old=list(db.scalars(select(GithubIdentityRegistry.github_user_id).where(
                GithubIdentityRegistry.retain_until<now,~active)
                .order_by(GithubIdentityRegistry.retain_until).limit(100).with_for_update(skip_locked=True)))
            if old:db.execute(delete(GithubIdentityRegistry).where(GithubIdentityRegistry.github_user_id.in_(old)))
        db.commit()


def confirm_connection(db,user,auth_session_id,connection_id,github_user_id,installation_id):
    _require_identity_registry(db)
    _require_email_verification_service(db)
    record,payload=_pending(db,user,auth_session_id,connection_id)
    require_advanced(db,user)
    if payload['identity']['id'] != github_user_id:
        raise HTTPException(409,'Confirm the GitHub identity shown by the server')
    if payload['expires_at'] and datetime.fromisoformat(payload['expires_at'])<=datetime.now(timezone.utc):
        raise HTTPException(409,'GitHub token expired; start a new connection')
    cfg=github_app_config.effective(settings,db)
    eligible=installations_for(payload['token'],cfg)
    if installation_id not in {item['id'] for item in payload['installations']} or installation_id not in {item['id'] for item in eligible}:
        raise HTTPException(403,'Installation is not authorized for this GitHub user')
    foreign=db.scalar(select(GithubConnection).where(GithubConnection.user_id!=user.id,
        or_(GithubConnection.installation_id==installation_id, GithubConnection.github_user_id==github_user_id,
            GithubConnection.installation_id.in_([i['id'] for i in eligible if i.get('type')=='User' and i.get('account_id')==github_user_id]))))
    if foreign: raise HTTPException(409,IDENTITY_IN_USE)
    proof=payload.get('email_proof') or {}
    if not proof.get('email_matched') or not proof.get('verified') or _aware(datetime.fromisoformat(proof['expires_at']))<=datetime.now(timezone.utc):
        raise HTTPException(403,'Verify the code sent to this GitHub account email before confirming')
    email=_verified_primary_email(payload['token'],github_user_id)
    _require_gateway_email_matches_github(user,email)
    email_hmac=_primary_email_hmac(github_user_id,email)
    if not hmac.compare_digest(email_hmac,proof.get('email_hmac','')):
        raise HTTPException(409,'GitHub primary email changed; request a fresh verification code')
    info=_api('GET',f'/app/installations/{installation_id}',jwt_token=_jwt(cfg))
    if info.get('app_id')!=cfg.github_app_id: raise HTTPException(403,'Installation belongs to a different GitHub App')
    row=GithubConnection(id=record.connection_id,user_id=user.id,installation_id=installation_id,
        github_user_id=github_user_id,github_user_login=payload['identity']['login'],
        account_login=(info.get('account') or {}).get('login') or payload['identity']['login'],
        account_type=(info.get('account') or {}).get('type') or 'User',target_type=info.get('target_type') or 'User',
        app_id=cfg.github_app_id,suspended=False,user_token=credentials.encrypt(payload['token']),
        token_expires_at=datetime.fromisoformat(payload['expires_at']) if payload['expires_at'] else None)
    try:
        # Existing registry rows serialize reconnect/email updates. On a first
        # claim the PK plus the active-connection unique constraint reject races.
        identity=db.scalar(select(GithubIdentityRegistry).where(
            GithubIdentityRegistry.github_user_id==github_user_id).with_for_update())
        now=datetime.now(timezone.utc)
        if identity:
            if not hmac.compare_digest(identity.primary_email_hmac,email_hmac):
                _audit_authorization(db,user,github_user_id,'email_changed')
            identity.primary_email_hmac=email_hmac;identity.last_verified_at=now;identity.verification_status='verified'
            identity.retain_until=now+AUTH_AUDIT_RETENTION
        else:
            db.add(GithubIdentityRegistry(github_user_id=github_user_id,primary_email_hmac=email_hmac,
                first_verified_at=now,last_verified_at=now,retain_until=now+AUTH_AUDIT_RETENTION,verification_status='verified'))
        db.add(row)
        _audit_authorization(db,user,github_user_id,'connected')
        db.execute(delete(GithubAuthState).where(GithubAuthState.user_id==user.id))
        require_advanced(db,user,start=True)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'GitHub identity was claimed by another connection; start again')
    return {'connected':True,'connection_id':str(row.id),'github_login':row.github_user_login,'account_login':row.account_login}


def pending_installation(db,user,auth_session_id,connection_id):
    record,payload=_pending(db,user,auth_session_id,connection_id)
    cfg=github_app_config.effective(settings,db)
    state='setup_'+secrets.token_urlsafe(32)
    # Reuse the transaction identity, never an old token or active connection.
    revoke_token(payload['token'],cfg)
    record.pending_payload=None
    db.add(GithubAuthState(state=state,user_id=user.id,auth_session_id=auth_session_id,
        connection_id=record.connection_id,expires_at=record.expires_at,
        pending_payload=credentials.encrypt(json.dumps({'expected_identity':payload['identity']['id']}))))
    db.commit()
    return install_url(state,cfg)


def revoke_token(token,cfg,*,grant=False):
    """Grant revocation covers this GitHub user's tokens for this App only."""
    if not token: return 'not-needed'
    try:
        with httpx.Client(base_url=settings.github_api_base,timeout=5,trust_env=False,follow_redirects=False,
                          auth=(cfg.github_client_id,cfg.github_client_secret)) as client:
            path='/applications/'+quote(cfg.github_client_id,safe='')
            response=client.request('DELETE',path+('/grant' if grant else '/token'),json={'access_token':token})
            if grant and response.status_code!=204:return 'unconfirmed'
            if response.status_code not in (204,404): return 'unconfirmed'
            check=client.post(path+'/token',json={'access_token':token})
            return 'verified' if check.status_code==404 else 'unconfirmed'
    except (httpx.HTTPError,ValueError): return 'unconfirmed'


def remove_owned_installation(row,token,cfg):
    # A GitHub App's JWT can uninstall any installation: do not exercise that
    # authority for a mere collaborator or an unverified organization owner.
    checking_installation=False
    try:
        identity=_api('GET','/user',token=token,timeout=4)
        checking_installation=True
        info=_api('GET',f'/app/installations/{row.installation_id}',jwt_token=_jwt(cfg),timeout=4)
        account=info.get('account') or {}
        if (info.get('app_id')!=cfg.github_app_id or account.get('type')!='User'
            or identity.get('id')!=account.get('id')
            or row.github_user_id is not None and row.github_user_id!=identity.get('id')):
            return 'owner-review-required'
        _api('DELETE',f'/app/installations/{row.installation_id}',jwt_token=_jwt(cfg),timeout=4)
        try: _api('GET',f'/app/installations/{row.installation_id}',jwt_token=_jwt(cfg),timeout=4)
        except HTTPException as exc:
            if exc.status_code==404: return 'verified'
        return 'unconfirmed'
    except HTTPException as exc:
        return 'already-absent' if checking_installation and exc.status_code==404 else 'unconfirmed'
    except Exception: return 'unconfirmed'


def disconnect(db,user,*,remove_installation=False,commit=True,revoke_grant=False):
    lock_owner(db,user)
    cfg=github_app_config.effective(settings,db)
    row=db.scalar(select(GithubConnection).where(GithubConnection.user_id==user.id).with_for_update())
    records=list(db.scalars(select(GithubAuthState).where(GithubAuthState.user_id==user.id).with_for_update()))
    tokens=[];results=[]
    if row and row.user_token:
        try: tokens.append(credentials.decrypt(row.user_token))
        except Exception: results.append('unconfirmed')
    for record in records:
        if record.pending_payload:
            try:
                token=json.loads(credentials.decrypt(record.pending_payload)).get('token')
                if token: tokens.append(token)
            except Exception: results.append('unconfirmed')
    installation='not-requested'
    if remove_installation and row:
        installation=remove_owned_installation(row,tokens[0],cfg) if tokens else 'unconfirmed'
    grant_result='not-requested'
    # Never revoke a whole grant for an unconfirmed/pending identity: that
    # GitHub account may belong to a different Gateway user. Automatic state
    # cleanup, webhook and administrative cleanup retain token-only semantics.
    if revoke_grant and row and row.user_token:
        try:
            token=credentials.decrypt(row.user_token)
            identity=_api('GET','/user',token=token,timeout=4)
            identity_id=identity.get('id')
            conflict=db.scalar(select(GithubConnection.id).where(
                GithubConnection.user_id!=user.id,GithubConnection.github_user_id==identity_id))
            if not identity_id or row.github_user_id!=identity_id or conflict:
                grant_result='owner-review-required'
            else:
                grant_result=revoke_token(token,cfg,grant=True)
                # A failed external call must not keep a reusable local link.
                if grant_result=='verified':
                    tokens=[t for t in tokens if t!=token]
                    results.append('verified')
        except Exception:
            grant_result='unconfirmed'
    for token in set(tokens): results.append(revoke_token(token,cfg))
    if grant_result not in {'not-requested','verified'}:results.append('unconfirmed')
    db.execute(delete(GithubAuthState).where(GithubAuthState.user_id==user.id))
    if row:
        from sqlalchemy import inspect
        if inspect(db.connection()).has_table(GithubIdentityRegistry.__tablename__) and row.github_user_id:
            identity=db.scalar(select(GithubIdentityRegistry).where(
                GithubIdentityRegistry.github_user_id==row.github_user_id).with_for_update())
            if identity:identity.retain_until=datetime.now(timezone.utc)+AUTH_AUDIT_RETENTION
        _audit_authorization(db,user,row.github_user_id,'disconnected')
        db.delete(row)
    if commit: db.commit()
    # Connection cleanup must NEVER expire/delete workspaces or native history.
    return {'connected':False,'local_credentials_removed':True,'installation_removal':installation,'grant_revocation':grant_result,
            'revocation':'unconfirmed' if 'unconfirmed' in results else ('verified' if results else 'not-needed')}

def list_repositories(connection: GithubConnection) -> list[dict]:
    token = installation_token(connection)
    repos = []
    for page in range(1,101):
        data = _api("GET", f"/user/installations/{connection.installation_id}/repositories", token=token, params={"per_page": 100,"page":page})
        items = (data or {}).get("repositories", [])
        for repo in items:
            owner = (repo.get("owner") or {}).get("login")
            repos.append({
                "id": repo.get("id"), "full_name": repo.get("full_name"), "name": repo.get("name"),
                "private": bool(repo.get("private")), "default_branch": repo.get("default_branch"),
                "owner": owner, "clone_url": repo.get("clone_url"),
            })
        if len(items)<100: break
    return repos

def authorized_repository(connection, full_name):
    repo = next((repo for repo in list_repositories(connection) if repo['full_name'] == full_name), None)
    if repo is None:
        raise HTTPException(404, "Repository is not available to the connected GitHub installation")
    return repo

def list_branches(connection: GithubConnection, full_name: str) -> list[dict]:
    authorized_repository(connection, full_name)
    token = installation_token(connection)
    rows = []
    for page in range(1,101):
        data = _api("GET", f"/repos/{full_name}/branches", token=token, params={"per_page": 100,"page":page}) or []
        rows.extend({"name": b.get("name"), "commit": (b.get("commit") or {}).get("sha")} for b in data)
        if len(data)<100: break
    return rows

def verify_remote_commit(connection: GithubConnection, full_name: str, branch: str, sha: str) -> bool:
    token = installation_token(connection)
    try:
        data = _api("GET", f"/repos/{full_name}/git/ref/heads/{quote(branch,safe='')}", token=token)
    except HTTPException as exc:
        if exc.status_code == 404:
            return False
        raise
    return ((data or {}).get("object") or {}).get("sha") == sha

def verify_webhook(body: bytes, signature: str | None) -> bool:
    cfg=github_app_config.effective(settings)
    if not cfg.github_webhook_secret:
        raise HTTPException(503, "GitHub webhook is not configured")
    if not signature or not signature.startswith("sha256="):
        return False
    expected = hmac.new(cfg.github_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature[len("sha256="):], expected)

def handle_webhook(db, event: str, payload: dict):
    installation = payload.get("installation") or {}
    installation_id = installation.get("id")
    if installation_id is None:
        return
    row = db.scalar(select(GithubConnection).where(GithubConnection.installation_id == installation_id))
    if row is None:
        return
    if event in {"installation", "installation_repositories"}:
        action = payload.get("action")
        if action == "deleted":
            disconnect(db, db.get(User, row.user_id))
            return
        elif action in {"suspend", "suspended"}:
            row.suspended = True
        else:
            row.suspended = bool(installation.get("suspended", False))
        db.commit()
