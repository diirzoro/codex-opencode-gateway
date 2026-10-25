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
    config = {}
    if tools:
        config["*"] = "deny"
        action = "ask" if policy.require_tool_approval else "allow"
        for tool in sorted(tools - {"external_directory"}):
            config[tool] = action
    else:
        config["*"] = "ask" if policy.require_tool_approval else "allow"
    config["external_directory"] = "deny"
    return config

def session_permissions(policy):
    return [{"permission": name, "pattern": "*", "action": action}
            for name, action in permission_config(policy).items()]


# Native execution is deny-by-default, including delegation/custom command tools.
# Shell stays blocked for administrators too until TEST's OS/project boundary is
# verified. A role alone cannot constrain a shared process's filesystem access.
NATIVE_REVIEW_TOOLS = frozenset({'read', 'edit', 'write', 'apply_patch', 'glob', 'grep',
                                 'list', 'question', 'todowrite', 'todoread'})

NATIVE_AUTOMATIC_TOOLS = frozenset({'question', 'todowrite', 'todoread'})
NATIVE_FILE_TOOLS = frozenset({'read', 'edit', 'write', 'apply_patch'})

def native_session_permissions(row, root, grants=()):
    allowed = provider_sets(row)[2]
    rules = [{'permission': '*', 'pattern': '*', 'action': 'deny'}]
    for name in sorted(NATIVE_REVIEW_TOOLS):
        if not allowed or name in allowed:
            rules.append({'permission': name, 'pattern': '*', 'action': 'allow' if name in NATIVE_AUTOMATIC_TOOLS else 'ask'})
    # Exact, ownership-validated grants are stored only in this Native session.
    # Never use Native's instance-wide `always` cache: 1.19.4 appends it AFTER
    # configured deny rules, and built-in file tools propose the wildcard '*'.
    for grant in sorted(grants, key=lambda rule:(rule['permission'],rule['pattern'])):
        if grant['permission'] in NATIVE_FILE_TOOLS and (not allowed or grant['permission'] in allowed):
            rules.append({'permission':grant['permission'],'pattern':grant['pattern'],'action':'allow'})
    # Session rules follow agent rules. Gateway never forwards `always`;
    # pre-existing Native instance-cache grants are not revoked by these rules.
    for name in ('bash', 'shell', 'terminal', 'execute', 'task', 'skill', 'lsp', 'external_directory'):
        rules.append({'permission': name, 'pattern': '*', 'action': 'deny'})
    for permission in ('read', 'edit', 'write', 'apply_patch', 'glob', 'grep', 'list'):
        for pattern in ('.git', '.git/*', '*/.git', '*/.git/*', '.opencode', '.opencode/*',
                        '*/.opencode', '*/.opencode/*', '.env*', '*/.env*',
                        'opencode.json*', '*/opencode.json*', '.ssh', '.ssh/*', '*/.ssh/*'):
            rules.append({'permission': permission, 'pattern': pattern, 'action': 'deny'})
    return rules
