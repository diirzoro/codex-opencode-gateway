from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
import secrets, uuid
from ..services import social_login
from sqlalchemy import or_, select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import AuthSession, City, Country, Region, User
from ..schemas import LoginRequest, RegisterRequest, UserOut
from ..security.passwords import hash_password, verify_password
from ..security.sessions import hash_session_token, new_session_token, idle_expires_at
from ..services.accounts import user_payload
from ..services.entitlements import CORE_TRIAL_DAYS
from .dependencies import require_user
router = APIRouter(prefix="/api/auth", tags=["auth"])

def set_session(response: Response, db: Session, user: User):
    raw, hashed = new_session_token()
    now = datetime.now(timezone.utc)
    session = AuthSession(user_id=user.id, token_hash=hashed, last_seen_at=now,
                          expires_at=now+timedelta(days=settings.session_days))
    db.add(session)
    db.commit()
    # A browser-session cookie, with authoritative server-side idle expiry.
    response.set_cookie(settings.session_cookie_name, raw, httponly=True, secure=settings.cookie_secure, samesite="strict", path="/")
    response.headers["X-Session-Idle-Expires-At"] = idle_expires_at(session).isoformat()

def validate_locations(db, country_id, region_id, city_id):
    country = db.scalar(select(Country).where(Country.id == country_id, Country.enabled.is_(True)))
    if not country: raise HTTPException(422, "Invalid country")
    region = None
    if region_id is not None:
        region = db.scalar(select(Region).where(Region.id == region_id, Region.country_id == country_id, Region.enabled.is_(True)))
        if not region: raise HTTPException(422, "Invalid region")
    if city_id is not None:
        if region is None or not db.scalar(select(City).where(City.id == city_id, City.region_id == region.id, City.enabled.is_(True))):
            raise HTTPException(422, "Invalid city")

@router.post("/register", response_model=UserOut, status_code=201)
def register(data: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    username, email = data.username.strip().lower(), data.email.lower()
    if db.scalar(select(User).where(or_(func.lower(User.username) == username, func.lower(User.email) == email))):
        raise HTTPException(409, "Username or email already exists")
    validate_locations(db, data.country_id, data.region_id, data.city_id)
    now = datetime.now(timezone.utc)
    user = User(username=username, email=email, password_hash=hash_password(data.password), phone=data.phone.strip(), postal_code=data.postal_code.strip(), country_id=data.country_id, region_id=data.region_id, city_id=data.city_id, trial_started_at=now, trial_ends_at=now+timedelta(days=CORE_TRIAL_DAYS), last_login_at=now)
    pending = request.cookies.get(social_login.SIGNUP_COOKIE)
    if pending:
        identity = social_login.unseal(pending, 'signup')
        if email != identity['email']: raise HTTPException(422, 'Use the verified sign-in email to complete registration')
        setattr(user, identity['provider'] + '_subject', identity['subject'])
        response.delete_cookie(social_login.SIGNUP_COOKIE, path='/api/auth', secure=settings.cookie_secure, httponly=True, samesite='strict')
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Username or email already exists")
    db.refresh(user); set_session(response, db, user)
    return user_payload(user)

@router.post("/login", response_model=UserOut)
def login(data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    identity = data.identity.strip().lower()
    user = db.scalar(select(User).where(or_(func.lower(User.email) == identity, func.lower(User.username) == identity)))
    if not user or not verify_password(data.password, user.password_hash): raise HTTPException(401, "Invalid credentials")
    if user.status != "active": raise HTTPException(403, "Account is not active")
    response.delete_cookie('gateway_login_signup', path='/api/auth', secure=settings.cookie_secure, httponly=True, samesite='strict')
    user.last_login_at = datetime.now(timezone.utc); db.commit(); set_session(response, db, user)
    return user_payload(user)

@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get(settings.session_cookie_name)
    if raw:
        session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_session_token(raw)))
        if session: session.revoked_at = datetime.now(timezone.utc); db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/", secure=settings.cookie_secure, httponly=True, samesite="strict")

@router.get("/me", response_model=UserOut)
def me(request: Request, response: Response, user: User = Depends(require_user)):
    response.headers["X-Session-Idle-Expires-At"] = idle_expires_at(request.state.auth_session).isoformat()
    return user_payload(user)

@router.post("/activity")
def activity(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    # Only an explicit activity acknowledgement extends the existing session.
    # Revalidate under a row lock so it cannot revive a concurrently revoked token.
    session = db.scalar(select(AuthSession).where(AuthSession.id == request.state.auth_session.id)
                        .with_for_update().execution_options(populate_existing=True))
    now = datetime.now(timezone.utc)
    if session.revoked_at is not None or idle_expires_at(session) <= now:
        session.revoked_at = session.revoked_at or now
        db.commit()
        raise HTTPException(401, "Session expired")
    session.last_seen_at = now
    db.commit()
    return {"idle_expires_at": idle_expires_at(session).isoformat()}

# OAuth creates the same AuthSession as password login. It never grants repo access.
@router.get('/social/options')
def social_options():
    return {provider: social_login.available(provider) for provider in ('github','google')}

@router.get('/social/pending')
def social_pending(request: Request):
    if not request.cookies.get(social_login.SIGNUP_COOKIE): return {'pending':False}
    identity = social_login.unseal(request.cookies.get(social_login.SIGNUP_COOKIE), 'signup')
    return {'pending':True, 'email':identity['email'], 'provider':identity['provider']}

@router.get('/social/{provider}/start')
def social_start(provider: str, request: Request, db: Session = Depends(get_db)):
    session = None
    if request.cookies.get(settings.session_cookie_name):
        require_user(request, db)
        session = request.state.auth_session
    url, state = social_login.begin(provider, session)
    response = RedirectResponse(url, status_code=303)
    response.set_cookie(social_login.FLOW_COOKIE, state, max_age=social_login.TTL, httponly=True,
                        secure=settings.cookie_secure, samesite='lax', path='/api/auth/social')
    return response

@router.get('/social/{provider}/callback')
def social_callback(provider: str, request: Request, state: str = '', code: str = '',
                    error: str | None = None, db: Session = Depends(get_db)):
    response = RedirectResponse('/#social=error', status_code=303)
    response.delete_cookie(social_login.FLOW_COOKIE, path='/api/auth/social', secure=settings.cookie_secure, httponly=True, samesite='lax')
    try:
        flow = social_login.unseal(request.cookies.get(social_login.FLOW_COOKIE), 'login')
        if error or not code or flow['provider'] != provider or not secrets.compare_digest(flow['state'], state):
            raise HTTPException(400, 'Sign-in authorization failed or was cancelled')
        identity = social_login.identity(provider, code, flow)
        column = getattr(User, provider + '_subject')
        bound = db.scalar(select(User).where(column == identity['subject']))
        if flow.get('session_id'):
            session = db.scalar(select(AuthSession).where(AuthSession.id == uuid.UUID(flow['session_id'])).with_for_update().execution_options(populate_existing=True))
            if not session or session.revoked_at or idle_expires_at(session) <= datetime.now(timezone.utc) or str(session.user_id) != flow['user_id']:
                raise HTTPException(401, 'Sign in again before linking this identity')
            user = db.scalar(select(User).where(User.id == session.user_id).with_for_update().execution_options(populate_existing=True))
            if user.status != 'active': raise HTTPException(403, 'Account is not active')
            if bound and bound.id != user.id: raise HTTPException(409, 'Identity is linked to another account')
            if getattr(user, provider + '_subject') not in (None, identity['subject']):
                raise HTTPException(409, 'Account already has a different sign-in identity')
            setattr(user, provider + '_subject', identity['subject'])
        elif bound:
            user = bound
        else:
            # Matching email does NOT prove account ownership: sign in by password
            # first, then explicitly link from Account. Never silently merge users.
            if db.scalar(select(User.id).where(func.lower(User.email) == identity['email'])):
                raise HTTPException(409, 'Sign in with your existing password, then link this provider from Account')
            response.headers['location'] = '/#social=register'
            response.set_cookie(social_login.SIGNUP_COOKIE, social_login.seal(identity), max_age=social_login.TTL,
                                httponly=True, secure=settings.cookie_secure, samesite='strict', path='/api/auth')
            return response
        if user.status != 'active': raise HTTPException(403, 'Account is not active')
        user.last_login_at = datetime.now(timezone.utc)
        db.commit()
        set_session(response, db, user)
        response.headers['location'] = '/#social=success'
    except (HTTPException, IntegrityError) as exc:
        db.rollback()
        # Fixed browser categories only: no upstream body/token/exception output.
        category = 'existing' if isinstance(exc, HTTPException) and exc.status_code == 409 else 'error'
        response.headers['location'] = '/#social=' + category
    return response
