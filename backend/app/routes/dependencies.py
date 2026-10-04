from datetime import datetime, timezone
from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import AuthSession, User
from ..security.sessions import hash_session_token

def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    raw = request.cookies.get(settings.session_cookie_name)
    if not raw:
        raise HTTPException(401, "Authentication required")
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_session_token(raw)))
    now = datetime.now(timezone.utc)
    if not session or session.revoked_at is not None:
        raise HTTPException(401, "Invalid session")
    expires = session.expires_at if session.expires_at.tzinfo else session.expires_at.replace(tzinfo=timezone.utc)
    if expires <= now:
        raise HTTPException(401, "Session expired")
    session.last_seen_at = now
    db.commit()
    if session.user.status != "active":
        raise HTTPException(403, "Account is not active")
    return session.user

def require_admin(user: User = Depends(require_user)) -> User:
    if user.role not in {"admin", "owner"}:
        raise HTTPException(403, "Administrator access required")
    return user
