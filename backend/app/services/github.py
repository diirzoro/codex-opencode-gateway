"""Real GitHub App integration. Config-gated: unconfigured deployments truthfully refuse.

Nothing here uses a Personal Access Token, simulates a connection, or exposes a token to
the browser. Installation tokens are short-lived and used only server-side.
"""
from __future__ import annotations
import hashlib, hmac, json, secrets
from datetime import datetime, timedelta, timezone
import httpx
from urllib.parse import quote, urlencode
from fastapi import HTTPException
from sqlalchemy import delete, select
from ..config import settings
from ..models import GithubAuthState, GithubConnection, User
from . import credentials, github_app_config
from .entitlements import require_advanced

STATE_TTL_MINUTES = 15

def schema_status(db) -> dict:
    """Read-only structure check. Never return rows, DSNs, tokens or DB errors."""
    from alembic.migration import MigrationContext
    from sqlalchemy import inspect
    from sqlalchemy.exc import SQLAlchemyError
    required = {
        GithubConnection.__tablename__: set(GithubConnection.__table__.columns.keys()),
        GithubAuthState.__tablename__: set(GithubAuthState.__table__.columns.keys()),
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
                "revisions": revisions, "required_migrations": ["0003_github_provider", "0005_account_management"]}
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

def _begin_installation(db, user) -> str:
    cfg=github_app_config.effective(settings,db)
    require_configured(cfg)
    state = 'setup_'+secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    db.add(GithubAuthState(state=state, user_id=user.id, expires_at=now + timedelta(minutes=STATE_TTL_MINUTES)))
    db.commit()
    return install_url(state,cfg)

def begin_fresh_link(db, user) -> str:
    # Explicit POST only: forget this customer's local connection and all old
    # callbacks before minting a fresh account-selection/install flow. Never
    # revoke the shared App installation or another customer's credentials.
    cfg = github_app_config.effective(settings, db)
    require_configured(cfg)
    # Starting a new OAuth flow must not revoke the existing connection.
    # A destructive disconnect is a distinct, explicitly confirmed operation.
    return begin_install(db, user)

def begin_install(db,user) -> str:
    # Never expose installation settings through the browser's old GitHub login
    # before this Gateway account completes an explicit account-selection flow.
    return begin_authorization(db,user,for_install=True)

def begin_authorization(db, user, *, for_install=False) -> str:
    """Reauthorize an existing GitHub App without requiring a second installation.

    A one-time state binds the OAuth code to the signed-in Gateway account.
    The callback separately verifies this user's installation membership.
    """
    cfg=github_app_config.effective(settings,db)
    require_configured(cfg)
    state=('install_' if for_install else '')+secrets.token_urlsafe(32)
    db.add(GithubAuthState(state=state,user_id=user.id,
                           expires_at=datetime.now(timezone.utc)+timedelta(minutes=STATE_TTL_MINUTES)))
    db.commit()
    params=urlencode({'client_id':cfg.github_client_id,'redirect_uri':cfg.github_callback_url,'state':state,'prompt':'select_account'})
    return cfg.github_web_base.rstrip('/')+'/login/oauth/authorize?'+params


def connection_status(db, user) -> dict:
    if not configured(db):
        return {"connected": False, "available": False, "configured": False, "reason": "GitHub App integration is not configured"}
    row = db.scalar(select(GithubConnection).where(GithubConnection.user_id == user.id))
    if row is None or row.suspended or not row.user_token or (row.token_expires_at and _aware(row.token_expires_at)<=datetime.now(timezone.utc)):
        return {"connected": False, "available": True, "configured": True, "reason": "GitHub App is installed" if row and row.suspended else "GitHub is not connected"}
    return {"connected": True, "available": True, "configured": True, "account_login": row.account_login, "account_type": row.account_type, "target_type": row.target_type}

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

def handle_callback(db, state: str, installation_id: int | None, setup_action: str | None, code: str | None = None):
    cfg=github_app_config.effective(settings,db)
    require_configured(cfg)
    if not state:
        raise HTTPException(422, "Missing GitHub authorization parameters")
    now = datetime.now(timezone.utc)
    record = db.scalar(select(GithubAuthState).where(GithubAuthState.state==state).with_for_update())
    if record is None or record.consumed:
        raise HTTPException(400, "Unknown or already-used GitHub state")
    expires = record.expires_at if record.expires_at.tzinfo else record.expires_at.replace(tzinfo=timezone.utc)
    if expires <= now:
        raise HTTPException(400, "GitHub authorization state expired")
    user=db.get(User,record.user_id)
    if not user or user.status!='active': raise HTTPException(403,'Active account and GitHub user authorization required')
    require_advanced(db, user)
    if not code:
        if state.startswith('setup_') and setup_action in {'install','update'}:
            record.consumed=True
            return {'redirect':begin_authorization(db,user)}
        raise HTTPException(422,'Missing GitHub authorization parameters')
    token=exchange_code(code,config=cfg)
    # GitHub OAuth reauthorization has a code but may not include installation_id.
    # Resolve only installations of THIS App that the authenticated user can access.
    # If several are available, never silently attach the wrong organization.
    eligible=[]
    for page in range(1,101):
        items=(_api('GET','/user/installations',token=token['access_token'],params={'per_page':100,'page':page}) or {}).get('installations',[])
        for item in items:
            if item.get('app_id')==cfg.github_app_id and isinstance(item.get('id'),int):
                eligible.append(item['id'])
        if len(items)<100:break
    if state.startswith('install_'):
        # Do not route this account into an installation assigned to another
        # Gateway customer, even if the browser is logged into its GitHub owner.
        foreign=db.scalar(select(GithubConnection).where(GithubConnection.installation_id.in_(eligible),GithubConnection.user_id!=record.user_id)) if eligible else None
        if foreign:raise HTTPException(409,'Installation is already linked to another account')
        record.consumed=True
        return {'redirect':_begin_installation(db,user)}
    if installation_id is None:
        previous=db.scalar(select(GithubConnection).where(GithubConnection.user_id==record.user_id))
        if previous and previous.installation_id in eligible:
            installation_id=previous.installation_id
        elif len(eligible)==1:
            installation_id=eligible[0]
        elif not eligible:
            raise HTTPException(409,'Install the GitHub App on a repository before authorizing')
        else:
            raise HTTPException(409,'Multiple GitHub installations available; choose an installation before linking')
    if installation_id not in eligible:
        raise HTTPException(403,'Installation is not authorized for this GitHub user')
    existing=db.scalar(select(GithubConnection).where(GithubConnection.installation_id==installation_id,GithubConnection.user_id!=record.user_id))
    if existing: raise HTTPException(409,'Installation is already linked to another account')
    # Verify App identity as well as the authenticated user's installation membership.
    info = _api("GET", f"/app/installations/{installation_id}", jwt_token=_jwt(cfg))
    if info.get('app_id')!=cfg.github_app_id:
        raise HTTPException(403,'Installation belongs to a different GitHub App')
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
    row.app_id = cfg.github_app_id
    row.suspended = False
    row.user_token=credentials.encrypt(token['access_token'])
    # GitHub Apps may issue non-expiring user tokens. Do not fabricate an
    # eight-hour expiry when GitHub did not return expires_in.
    row.token_expires_at=now+timedelta(seconds=int(token['expires_in'])) if token.get('expires_in') is not None else None
    require_advanced(db, user, start=True)
    db.commit()
    return row

def disconnect(db, user, *, remove_worktrees=True):
    # Revoking the Gateway link must also invalidate authorization states minted
    # before disconnect. Otherwise a delayed OAuth callback could silently
    # recreate the supposedly disconnected account link.
    from . import workspace_cache
    affected = workspace_cache.expire_github_copies(db, user.id) if remove_worktrees else []
    db.execute(delete(GithubAuthState).where(GithubAuthState.user_id == user.id))
    row = db.scalar(select(GithubConnection).where(GithubConnection.user_id == user.id))
    if row is not None:
        db.delete(row)
    db.commit()
    # Only after committed revocation/barriers may file erasure be attempted.
    # A failure or active Native run leaves a blocked copy for existing
    # maintenance to retry. Never kill/restart the shared OpenCode service.
    if affected:
        try:
            workspace_cache.sweep(workspace_ids=affected)
        except Exception:
            import logging
            logging.getLogger(__name__).warning('Disconnected GitHub copy cleanup deferred')

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
