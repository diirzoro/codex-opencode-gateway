"""Platform policy helpers: filter runtime capabilities and build OpenCode permissions.

Effective availability is the intersection of (1) runtime-reported capabilities,
(2) admin-enabled provider/model/tool entries, and (3) the user's authenticated state.
"""
import json
from ..models.platform import get_policy

DEFAULT_PERMISSION = {"*": "ask", "external_directory": "deny"}

def load(db):
    return get_policy(db)

def _as_set(value: str) -> set[str]:
    try:
        items = json.loads(value or "[]")
    except ValueError:
        return set()
    return {str(item) for item in items if str(item).strip()}

def provider_sets(policy):
    return _as_set(policy.allowed_providers), _as_set(policy.allowed_models), _as_set(policy.allowed_tools)

def provider_allowed(policy, provider_id: str) -> bool:
    allowed, _, _ = provider_sets(policy)
    return not allowed or provider_id in allowed

def model_allowed(policy, model_id: str) -> bool:
    _, allowed, _ = provider_sets(policy)
    return not allowed or model_id in allowed

def filter_providers(rows, policy):
    allowed_providers, allowed_models, _ = provider_sets(policy)
    output = []
    for provider in rows:
        if allowed_providers and provider.get("id") not in allowed_providers:
            continue
        models = provider.get("models", [])
        if allowed_models:
            models = [m for m in models if m.get("id") in allowed_models]
        output.append({**provider, "models": models})
    return output

def permission_config(policy) -> dict:
    _, _, tools = provider_sets(policy)
    config = {"external_directory": "deny"}
    if tools:
        config["*"] = "deny"
        action = "ask" if policy.require_tool_approval else "allow"
        for tool in tools:
            config[tool] = action
    else:
        config["*"] = "ask" if policy.require_tool_approval else "allow"
    return config
