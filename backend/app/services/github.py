"""Real GitHub App integration. Config-gated: unconfigured deployments truthfully refuse.

Nothing here uses a Personal Access Token, simulates a connection, or exposes a token to
the browser. Installation tokens are short-lived and used only server-side.
"""
from __future__ import annotations
import hashlib, hmac, json, secrets
from datetime import datetime, timedelta, timezone
import httpx
from urllib.parse import quote
from fastapi import HTTPException
from sqlalchemy import select
from ..config import settings
from ..models import GithubAuthState, GithubConnection, User
from . import credentials
from .entitlements import require_advanced

STATE_TTL_MINUTES = 15

def configured() -> bool:
    return bool(settings.github_configured and settings.github_client_id and settings.github_client_secret and credentials.available())

def require_configured():
    if not configured():
        raise HTTPException(503, "GitHub App is not configured on this server")

def install_url(state: str) -> str:
    require_configured()
    base = settings.github_web_base.rstrip("/")
    return f"{base}/apps/{settings.github_app_slug}/installations/new?state={state}"

def _jwt() -> str:
    require_configured()
    try:
        import jwt
    except ImportError:  # pragma: no cover - dependency is pinned in requirements
        raise HTTPException(503, "GitHub App signing dependency is unavailable")
    now = datetime.now(timezone.utc)
    payload = {"iat": int((now - timedelta(seconds=60)).timestamp()), "exp": int((now + timedelta(minutes=9)).timestamp()), "iss": str(settings.github_app_id)}
    return jwt.encode(payload, settings.github_private_key, algorithm="RS256")

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

def begin_install(db, user) -> str:
    require_configured()
    state = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    db.add(GithubAuthState(state=state, user_id=user.id, expires_at=now + timedelta(minutes=STATE_TTL_MINUTES)))
    db.commit()
    return install_url(state)

def connection_status(db, user) -> dict:
    if not configured():
        return {"connected": False, "available": False, "configured": False, "reason": "GitHub App integration is not configured"}
    row = db.scalar(select(GithubConnection).where(GithubConnection.user_id == user.id))
    if row is None or row.suspended or not row.user_token or not row.token_expires_at or _aware(row.token_expires_at)<=datetime.now(timezone.utc):
        return {"connected": False, "available": True, "configured": True, "reason": "GitHub App is installed" if row and row.suspended else "GitHub is not connected"}
    return {"connected": True, "available": True, "configured": True, "account_login": row.account_login, "account_type": row.account_type, "target_type": row.target_type}

def installation_token(connection: GithubConnection) -> str:
    # Every customer operation uses the customer's authorization, never the App's
    # broader installation token. Membership removal therefore takes effect at GitHub.
    if not connection.user_token or not connection.token_expires_at or _aware(connection.token_expires_at)<=datetime.now(timezone.utc):
        raise HTTPException(403,'Reconnect GitHub: user authorization expired')
    return credentials.decrypt(connection.user_token)

def _aware(value): return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

def exchange_code(code, redirect_uri=None, verifier=None):
    try:
        with httpx.Client(timeout=20,follow_redirects=False,trust_env=False) as client:
            response=client.post(settings.github_web_base.rstrip('/')+'/login/oauth/access_token',headers={'Accept':'application/json'},data={'client_id':settings.github_client_id,'client_secret':settings.github_client_secret,'code':code,'redirect_uri':redirect_uri or settings.github_callback_url,**({'code_verifier':verifier} if verifier else {})})
            result=response.json()
    except (httpx.HTTPError,ValueError): raise HTTPException(502,'GitHub authorization failed')
    if response.status_code!=200 or not result.get('access_token'): raise HTTPException(403,'GitHub authorization failed')
    return result

def connection_for(db, user) -> GithubConnection:
    row = db.scalar(select(GithubConnection).where(GithubConnection.user_id == user.id))
    if row is None or row.suspended:
        raise HTTPException(503, "GitHub is not connected for this account")
    return row

def handle_callback(db, state: str, installation_id: int | None, setup_action: str | None, code: str | None = None):
    require_configured()
    if not state or not installation_id:
        raise HTTPException(422, "Missing GitHub installation parameters")
    now = datetime.now(timezone.utc)
    record = db.scalar(select(GithubAuthState).where(GithubAuthState.state==state).with_for_update())
    if record is None or record.consumed:
        raise HTTPException(400, "Unknown or already-used GitHub state")
    expires = record.expires_at if record.expires_at.tzinfo else record.expires_at.replace(tzinfo=timezone.utc)
    if expires <= now:
        raise HTTPException(400, "GitHub authorization state expired")
    user=db.get(User,record.user_id)
    if not user or user.status!='active' or not code: raise HTTPException(403,'Active account and GitHub user authorization required')
    require_advanced(db, user)
    token=exchange_code(code)
    authorized=False
    for page in range(1,101):
        items=(_api('GET','/user/installations',token=token['access_token'],params={'per_page':100,'page':page}) or {}).get('installations',[])
        if any(item.get('id')==installation_id for item in items): authorized=True; break
        if len(items)<100: break
    if not authorized: raise HTTPException(403,'Installation is not authorized for this GitHub user')
    existing=db.scalar(select(GithubConnection).where(GithubConnection.installation_id==installation_id,GithubConnection.user_id!=record.user_id))
    if existing: raise HTTPException(409,'Installation is already linked to another account')
    # Verify App identity as well as the authenticated user's installation membership.
    info = _api("GET", f"/app/installations/{installation_id}", jwt_token=_jwt())
    account = info.get("account") or {}
    login = account.get("login") or "unknown"
    record.consumed = True
    row = db.scalar(select(GithubConnection).where(GithubConnection.user_id == record.user_id))
    if row is None:
        row = GithubConnection(user_id=record.user_id, installation_id=installation_id)
        db.add(row)
    row.installation_id = installation_id
    row.account_login = login
    row.account_type = account.get("type") or "User"
    row.target_type = info.get("target_type") or "User"
    row.app_id = settings.github_app_id
    row.suspended = False
    row.user_token=credentials.encrypt(token['access_token'])
    row.token_expires_at=now+timedelta(seconds=min(int(token.get('expires_in',28800)),28800))
    require_advanced(db, user, start=True)
    db.commit()
    return row

def disconnect(db, user):
    row = db.scalar(select(GithubConnection).where(GithubConnection.user_id == user.id))
    if row is None:
        raise HTTPException(404, "No GitHub connection to remove")
    db.delete(row)
    db.commit()

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
    if not settings.github_webhook_secret:
        raise HTTPException(503, "GitHub webhook is not configured")
    if not signature or not signature.startswith("sha256="):
        return False
    expected = hmac.new(settings.github_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
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
            db.delete(row)
        elif action in {"suspend", "suspended"}:
            row.suspended = True
        else:
            row.suspended = bool(installation.get("suspended", False))
        db.commit()
