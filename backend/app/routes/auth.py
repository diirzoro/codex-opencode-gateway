from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import or_, select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import AuthSession, City, Country, Region, User
from ..schemas import LoginRequest, RegisterRequest, UserOut
from ..security.passwords import hash_password, verify_password
from ..security.sessions import hash_session_token, new_session_token
from ..services.accounts import user_payload
from .dependencies import require_user
router = APIRouter(prefix="/api/auth", tags=["auth"])

def set_session(response: Response, db: Session, user: User):
    raw, hashed = new_session_token()
    db.add(AuthSession(user_id=user.id, token_hash=hashed, expires_at=datetime.now(timezone.utc)+timedelta(days=settings.session_days)))
    db.commit()
    response.set_cookie(settings.session_cookie_name, raw, max_age=settings.session_days*86400, httponly=True, secure=settings.cookie_secure, samesite="strict", path="/")

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
def register(data: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    username, email = data.username.strip().lower(), data.email.lower()
    if db.scalar(select(User).where(or_(func.lower(User.username) == username, func.lower(User.email) == email))):
        raise HTTPException(409, "Username or email already exists")
    validate_locations(db, data.country_id, data.region_id, data.city_id)
    now = datetime.now(timezone.utc)
    user = User(username=username, email=email, password_hash=hash_password(data.password), phone=data.phone.strip(), postal_code=data.postal_code.strip(), country_id=data.country_id, region_id=data.region_id, city_id=data.city_id, trial_started_at=now, trial_ends_at=now+timedelta(days=10), last_login_at=now)
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
def me(user: User = Depends(require_user)): return user_payload(user)
