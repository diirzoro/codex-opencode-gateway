"""OpenCode provider/auth catalog and real, tool-free credential validation."""
import json
from urllib.parse import quote
from fastapi import HTTPException


def public_metadata(value):
    """Keep capabilities while excluding credentials and private runtime paths."""
    if isinstance(value, list):
        return [public_metadata(item) for item in value]
    if not isinstance(value, dict):
        return value
    private = {"apikey", "api_key", "password", "secret", "client_secret", "access", "refresh", "token",
               "access_token", "refresh_token", "authorization", "headers", "ciphertext", "key",
               "directory", "cwd", "root", "worktree", "home", "config", "state", "cache", "path"}
    return {key: ("[runtime-path]" if key == "pattern" and isinstance(item, str)
                  and (item.startswith("/") or (len(item) > 2 and item[1:3] in {":\\", ":/"}))
                  else public_metadata(item))
            for key, item in value.items() if key.lower() not in private}


def catalog(data, methods, policy=None):
    from .policy import provider_allowed, model_allowed
    if not isinstance(data, dict) or not isinstance(data.get("all"), list):
        raise HTTPException(502, "OpenCode returned an invalid provider catalog")
    connected = set(data.get("connected", []))
    result = []
    for entry in data["all"]:
        provider = public_metadata(entry)
        provider_id = entry["id"]
        provider["connected"] = provider_id in connected
        provider["allowed"] = policy is None or provider_allowed(policy, provider_id)
        provider["models"] = [{**public_metadata(model), "id": identifier,
                               "allowed": provider["allowed"] and (policy is None or model_allowed(policy, identifier))}
                              for identifier, model in entry.get("models", {}).items()]
        # The methods are schema, not credentials. Preserve prompt keys/conditions.
        provider["auth_methods"] = methods.get(provider_id, [])
        provider["default_model"] = data.get("default", {}).get(provider_id)
        result.append(provider)
    return result


def discover(service, policy=None):
    return catalog(service.request("GET", "/provider"), service.request("GET", "/provider/auth"), policy)


def catalog_index(data, policy=None):
    """Initial browser discovery needs provider state, not every model schema."""
    from .policy import provider_allowed
    if not isinstance(data, dict) or not isinstance(data.get("all"), list):
        raise HTTPException(502, "OpenCode returned an invalid provider catalog")
    connected = set(data.get("connected", []))
    return [{"id": entry["id"], "name": entry.get("name") or entry["id"],
             "connected": entry["id"] in connected,
             "allowed": policy is None or provider_allowed(policy, entry["id"]),
             "model_count": len(entry.get("models", {})),
             "default_model": data.get("default", {}).get(entry["id"])}
            for entry in data["all"]]


def model_details(data, provider_id, policy=None):
    """Sanitize and annotate models for exactly one runtime-reported provider."""
    from .policy import provider_allowed, model_allowed
    if not isinstance(data, dict) or not isinstance(data.get("all"), list):
        raise HTTPException(502, "OpenCode returned an invalid provider catalog")
    entry = next((entry for entry in data["all"] if entry["id"] == provider_id), None)
    if entry is None:
        raise HTTPException(404, "Provider is not available in this workspace runtime")
    allowed = policy is None or provider_allowed(policy, provider_id)
    return {"provider_id": provider_id, "connected": provider_id in data.get("connected", []),
            "allowed": allowed, "default_model": data.get("default", {}).get(provider_id),
            "models": [{**public_metadata(model), "id": identifier,
                        "allowed": allowed and (policy is None or model_allowed(policy, identifier))}
                       for identifier, model in entry.get("models", {}).items()]}


def auth_methods(service):
    return service.request("GET", "/provider/auth")


def set_api_key(service, provider_id, key, metadata=None):
    body = {"type": "api", "key": key}
    if metadata: body["metadata"] = metadata
    result = service.request("PUT", "/auth/" + quote(provider_id, safe=""), body)
    if result is not True:
        raise HTTPException(502, "OpenCode did not accept the credential installation")
    service.invalidate()
    return True


def restore_credential(service, provider_id, plaintext):
    # Legacy records encrypt a bare key. New records also preserve OpenCode auth metadata.
    try:
        saved = json.loads(plaintext)
    except ValueError:
        saved = None
    if isinstance(saved, dict) and saved.get("type") == "api" and isinstance(saved.get("key"), str):
        return set_api_key(service, provider_id, saved["key"], saved.get("metadata"))
    return set_api_key(service, provider_id, plaintext)


def remove(service, provider_id):
    result = service.request("DELETE", "/auth/" + quote(provider_id, safe=""))
    if result is not True:
        raise HTTPException(502, "OpenCode did not confirm credential removal")
    service.invalidate()
    data = service.request("GET", "/provider")
    if provider_id in set(data.get("connected", [])):
        raise HTTPException(502, "OpenCode still reports this provider as connected")
    return True


def validate_model(service, provider_id, model_id=None, policy=None):
    """Require a real assistant answer before persisting a new API key.

    The temporary session is explicitly tool-denied and deleted on all outcomes.
    A connected flag/catalog alone is never considered model validation.
    """
    from .policy import model_allowed
    data = service.request("GET", "/provider")
    entry = next((p for p in data.get("all", []) if p.get("id") == provider_id), None)
    if not entry or provider_id not in data.get("connected", []):
        raise HTTPException(422, "OpenCode does not report the selected provider as connected")
    models = entry.get("models", {})
    candidates = [identifier for identifier, model in models.items()
                  if (policy is None or model_allowed(policy, identifier))
                  and "text" in model.get("modalities", {}).get("output", ["text"])]
    if model_id and model_id not in candidates:
        raise HTTPException(422, "Validation model is unavailable or restricted")
    selected = model_id or data.get("default", {}).get(provider_id)
    if selected not in candidates:
        selected = candidates[0] if candidates else None
    if not selected:
        raise HTTPException(422, "No allowed text model is available for credential validation")
    session_id = None
    try:
        session = service.request("POST", "/session", {"title": "Provider credential validation", "permission": [
            {"permission": "*", "pattern": "*", "action": "deny"}]})
        session_id = session.get("id") if isinstance(session, dict) else None
        if not session_id or not session_id.startswith("ses"):
            raise HTTPException(502, "OpenCode did not create the validation session")
        answer = service.request("POST", service.session_path(session_id, "/message"), {
            "parts": [{"type": "text", "text": "Reply with OK only. Do not use tools."}],
            "model": {"providerID": provider_id, "modelID": selected}}, timeout=90)
        info = answer.get("info", {}) if isinstance(answer, dict) else {}
        parts = answer.get("parts", []) if isinstance(answer, dict) else []
        if (info.get("role") != "assistant" or info.get("error") or not info.get("time", {}).get("completed")
                or info.get("providerID") != provider_id or info.get("modelID") != selected
                or not any(p.get("type") == "text" and str(p.get("text", "")).strip() for p in parts)):
            raise HTTPException(422, "The provider did not complete a real OpenCode model request; no new key was stored")
        return selected
    finally:
        if session_id:
            try:
                service.request("POST", service.session_path(session_id, "/abort"))
            finally:
                service.request("DELETE", service.session_path(session_id))
        service.invalidate()


def oauth_authorize(service, provider_id, method, inputs=None):
    methods = auth_methods(service).get(provider_id, [])
    if method >= len(methods) or methods[method].get("type") != "oauth":
        raise HTTPException(422, "Select an OAuth method returned by this workspace runtime")
    result = service.request("POST", f"/provider/{quote(provider_id, safe='')}/oauth/authorize",
                             {"method": method, "inputs": inputs or {}})
    service.oauth_pending[provider_id] = method
    return result


def oauth_callback(service, provider_id, method, code=None):
    if service.oauth_pending.get(provider_id) != method:
        raise HTTPException(409, "Start OAuth in this workspace before completing it")
    body = {"method": method}
    if code is not None: body["code"] = code
    accepted=service.request("POST", f"/provider/{quote(provider_id, safe='')}/oauth/callback", body, timeout=90)
    if accepted is not True:
        raise HTTPException(502, "OpenCode did not confirm the OAuth callback")
    service.invalidate()
    if not is_connected(service, provider_id):
        raise HTTPException(502, "OpenCode did not confirm the OAuth provider connection")
    service.oauth_pending.pop(provider_id, None)
    return True


def is_connected(service, provider_id):
    return provider_id in set(service.request("GET", "/provider").get("connected", []))
