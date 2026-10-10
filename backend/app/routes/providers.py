"""Account-level provider connection.

Provider connection is an account-level concern: a signed-in user can list, search,
connect and disconnect providers without selecting or creating a workspace. Discovery
and validation run in a lightweight, loopback-only account OpenCode runtime
(services/opencode.for_account) that holds no project files and is a separate process
from any workspace execution runtime. Credential storage and install/remove logic are
the same as the workspace scope (services/providers.py); account rows use
workspace_id NULL and are consumed by every workspace runtime.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import ProviderCredential, User
from ..services import opencode, policy, providers
from ..services.entitlements import require_advanced
from .dependencies import require_user
from .workspaces import ApiKeyCredential, OAuthAuthorize, OAuthCallback

router = APIRouter(prefix="/api/providers", tags=["providers"])


def _account_service(user: User):
    return opencode.for_account(user)


def _account_catalog(db: Session, user: User, service):
    return providers.overlay_account_connections(db, user.id, service.request("GET", "/provider"))


@router.get("")
def list_providers(user: User = Depends(require_user), db: Session = Depends(get_db)):
    service = _account_service(user)
    return providers.catalog(_account_catalog(db, user, service), providers.auth_methods(service), policy.load(db))


@router.get("/search")
def search_providers(query: str = Query(min_length=2, max_length=200), user: User = Depends(require_user), db: Session = Depends(get_db)):
    service = _account_service(user)
    return providers.search_index(_account_catalog(db, user, service), query, policy.load(db))


@router.get("/resolve")
def resolve_provider(name: str = Query(min_length=1, max_length=200), user: User = Depends(require_user), db: Session = Depends(get_db)):
    service = _account_service(user)
    data = _account_catalog(db, user, service)
    row = providers.provider_index(providers.resolve_provider(data, name), data, policy.load(db))
    # /provider/auth is sparse; the real key methods come from the integration
    # registry (the same source the workspace connection flow uses).
    row["auth_methods"] = providers.connection_methods(service, row["id"])
    return [row]


@router.get("/{provider_id}/models")
def provider_models(provider_id: str, user: User = Depends(require_user), db: Session = Depends(get_db)):
    service = _account_service(user)
    return providers.model_details(_account_catalog(db, user, service), provider_id, policy.load(db))


@router.post("/{provider_id}/credentials")
def set_provider_credential(provider_id: str, data: ApiKeyCredential, user: User = Depends(require_user), db: Session = Depends(get_db)):
    require_advanced(db, user)
    service = _account_service(user)
    result = providers.install_api_credential(db, user=user, service=service, provider_id=provider_id,
        api_key=data.api_key, model_id=data.model_id, method=data.method, inputs=data.inputs, account_level=True)
    opencode.stop_user_workspaces(user.id)
    return result


@router.delete("/{provider_id}", status_code=204)
def remove_provider_credential(provider_id: str, user: User = Depends(require_user), db: Session = Depends(get_db)):
    providers.remove_credential(db, user=user, provider_id=provider_id, account_level=True)
    opencode.stop_user_workspaces(user.id)


@router.post("/{provider_id}/oauth/authorize")
def provider_oauth_authorize(provider_id: str, data: OAuthAuthorize, user: User = Depends(require_user), db: Session = Depends(get_db)):
    require_advanced(db, user)
    if not policy.provider_allowed(policy.load(db), provider_id):
        raise HTTPException(403, 'Provider is disabled by platform policy')
    service = _account_service(user)
    with service.state_lock:
        return providers.oauth_authorize(service, provider_id, data.method, data.inputs)


@router.post("/{provider_id}/oauth/callback")
def provider_oauth_callback(provider_id: str, data: OAuthCallback, user: User = Depends(require_user), db: Session = Depends(get_db)):
    require_advanced(db, user)
    if not policy.provider_allowed(policy.load(db), provider_id):
        raise HTTPException(403, 'Provider is disabled by platform policy')
    service = _account_service(user)
    with opencode.account_lock(user), service.state_lock:
        accepted = providers.oauth_callback(service, provider_id, data.method, data.code)
        # OAuth state belongs to OpenCode. Retire any old account-level API-key binding.
        row = db.scalar(select(ProviderCredential).where(ProviderCredential.workspace_id.is_(None),
            ProviderCredential.user_id == user.id, ProviderCredential.provider_id == provider_id))
        if row is not None:
            db.delete(row)
        if accepted:
            require_advanced(db, user, start=True)
            providers.record_account_connection(db, user.id, provider_id, connected=True)
        db.commit()
        if accepted:
            opencode.stop_user_workspaces(user.id)
        return {"connected": bool(accepted)}
