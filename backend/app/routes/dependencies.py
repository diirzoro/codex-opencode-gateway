from datetime import datetime, timezone
from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import AuthSession, User
from ..services.entitlements import access_payload
from ..security.sessions import (hash_session_token, idle_expires_at,
    REACTIVATION_PREFIX, reactivation_cookie_name, normal_access_ready, reactivation_eligible)

def require_reactivation_user(request: Request, db: Session = Depends(get_db)) -> User:
    raw = request.cookies.get(reactivation_cookie_name(), "")
    if not raw.startswith(REACTIVATION_PREFIX):
        raise HTTPException(401, "Verify your account with a new recovery link to renew")
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_session_token(raw)))
    now = datetime.now(timezone.utc)
    if not session or session.revoked_at or idle_expires_at(session) <= now:
        raise HTTPException(401, "Reactivation session expired; request a new recovery link")
    if not reactivation_eligible(session.user):
        raise HTTPException(403, "Account is not eligible for reactivation")
    request.state.reactivation_session = session
    return session.user

def require_billing_user(request: Request, db: Session = Depends(get_db)) -> User:
    # Used only on explicit renewal/payment endpoints, never profile/workspaces,
    # credential management, social linking, billing-method editing or admin.
    if request.cookies.get(reactivation_cookie_name()):
        return require_reactivation_user(request, db)
    return require_user(request, db)

def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    raw = request.cookies.get(settings.session_cookie_name)
    if not raw:
        if request.url.path == "/api/auth/me" and request.cookies.get(reactivation_cookie_name()):
            require_reactivation_user(request, db)
            raise HTTPException(401, "Account reactivation required")
        raise HTTPException(401, "Authentication required")
    if raw.startswith(REACTIVATION_PREFIX):
        raise HTTPException(403, "Reactivation sessions allow renewal only")
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_session_token(raw)))
    now = datetime.now(timezone.utc)
    if not session or session.revoked_at is not None:
        raise HTTPException(401, "Invalid session")
    if idle_expires_at(session) <= now:
        session.revoked_at = now
        db.commit()
        raise HTTPException(401, "Session expired")
    # Polling, SSE and browser restoration are not meaningful user activity.
    request.state.auth_session = session
    if not normal_access_ready(session.user):
        raise HTTPException(403, "Account is not active")
    return session.user

def require_admin(user: User = Depends(require_user)) -> User:
    if user.role not in {"admin", "owner"}:
        raise HTTPException(403, "Administrator access required")
    return user

def require_workspace_entitlement(request:Request,user:User=Depends(require_user),db:Session=Depends(get_db)):
    path=request.url.path
    # Read-only owned data/discovery remains available after expiry; execution
    # requires entitlement below. Ownership is checked by each route.
    import re
    if request.method in {'GET','HEAD'}:
        return
    # Recovery/visibility operations must remain possible after access expires.
    if (request.method=='DELETE' and re.fullmatch(r'/api/workspaces/[^/]+/providers/[^/]+',path)
        or path.endswith('/export')
        or re.fullmatch(r'/api/sessions/[^/]+/(?:stop|close|archive|restore)(?:$)',path)
        or request.method=='DELETE' and path.startswith('/api/sessions/')
        or re.fullmatch(r'/api/projects/[^/]+/archive',path)):
        return
    working=path.startswith(('/api/workspaces','/api/sessions')) or (path.startswith('/api/projects') and request.method not in {'GET','HEAD'})
    if working and not access_payload(db,user)['allowed']:
        raise HTTPException(402,'Trial ended. An active paid subscription is required to use the workspace.')
