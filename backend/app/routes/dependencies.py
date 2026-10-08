from datetime import datetime, timezone
from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import AuthSession, User, Subscription
from ..security.sessions import hash_session_token, idle_expires_at

def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    raw = request.cookies.get(settings.session_cookie_name)
    if not raw:
        raise HTTPException(401, "Authentication required")
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
    if session.user.status != "active":
        raise HTTPException(403, "Account is not active")
    return session.user

def require_admin(user: User = Depends(require_user)) -> User:
    if user.role not in {"admin", "owner"}:
        raise HTTPException(403, "Administrator access required")
    return user

def access_payload(db,user):
    now=datetime.now(timezone.utc)
    def future(value):
        return bool(value and (value if value.tzinfo else value.replace(tzinfo=timezone.utc))>now)
    if user.role in {'admin','owner'}: return {'allowed':True,'reason':'administration'}
    row=db.scalar(select(Subscription).where(Subscription.user_id==user.id))
    if row and row.status=='active' and row.plan_id and future(row.current_period_end):
        return {'allowed':True,'reason':'subscription','ends_at':row.current_period_end}
    if future(user.trial_ends_at): return {'allowed':True,'reason':'trial','ends_at':user.trial_ends_at}
    return {'allowed':False,'reason':'subscription_required'}

def require_workspace_entitlement(request:Request,user:User=Depends(require_user),db:Session=Depends(get_db)):
    path=request.url.path
    # Existing owned project data remains readable after expiry; runtime discovery
    # and execution still require entitlement. Ownership is checked by each route.
    import re
    if request.method in {'GET','HEAD'} and (path=='/api/workspaces' or re.fullmatch(r'/api/workspaces/[^/]+(?:/(?:files(?:/content)?|diff|changes|logs|git/status|sessions|preview))?',path)):
        return
    if request.method=='POST' and re.fullmatch(r'/api/sessions/[^/]+/stop',path):
        return
    working=path.startswith(('/api/workspaces','/api/sessions')) or (path.startswith('/api/projects') and request.method not in {'GET','HEAD'})
    if working and not access_payload(db,user)['allowed']:
        raise HTTPException(402,'Trial ended. An active paid subscription is required to use the workspace.')
