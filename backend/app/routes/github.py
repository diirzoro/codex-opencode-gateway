"""Real GitHub App routes.

Install navigates the browser to the real github.com installation page. The callback is
public because GitHub performs a cross-site top-level redirect (SameSite=Strict cookies are
not sent), so it is authenticated by the one-time server-side state instead of a cookie.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import User
from ..services import github
from ..services.entitlements import require_advanced
from .dependencies import require_user

router = APIRouter(prefix="/api/github", tags=["github"])

@router.get("/status")
def status(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return github.connection_status(db, user)

@router.get("/install")
def install(user: User = Depends(require_user), db: Session = Depends(get_db)):
    require_advanced(db, user)  # The timer starts only after successful authorization.
    return RedirectResponse(github.begin_install(db, user), status_code=302)

@router.get("/callback")
def callback(state: str | None = None, installation_id: int | None = None, setup_action: str | None = None, code: str | None = None, db: Session = Depends(get_db)):
    destination = f"{settings.public_base_url}/?github="
    try:
        github.handle_callback(db, state, installation_id, setup_action, code)
        return RedirectResponse(destination + "connected", status_code=302)
    except HTTPException:
        return RedirectResponse(destination + "error", status_code=302)

@router.post("/disconnect", status_code=204)
def disconnect(user: User = Depends(require_user), db: Session = Depends(get_db)):
    github.disconnect(db, user)

@router.get("/repositories")
def repositories(user: User = Depends(require_user), db: Session = Depends(get_db)):
    connection = github.connection_for(db, user)
    return github.list_repositories(connection)

@router.get("/branches")
def branches(repository: str, user: User = Depends(require_user), db: Session = Depends(get_db)):
    if not repository.count("/") == 1:
        raise HTTPException(422, "A repository in owner/name form is required")
    connection = github.connection_for(db, user)
    return github.list_branches(connection, repository)

@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("x-hub-signature-256")
    if not github.verify_webhook(body, signature):
        raise HTTPException(401, "Invalid webhook signature")
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(422, "Invalid webhook payload")
    github.handle_webhook(db, request.headers.get("x-github-event", ""), payload)
    return {"received": True}
