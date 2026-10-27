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
    if isinstance(items,dict):items=items.get('allowed',[])
    return {str(item) for item in items if str(item).strip()}

def provider_sets(policy):
    return _as_set(policy.allowed_providers), _as_set(policy.allowed_models), _as_set(policy.allowed_tools)

def provider_allowed(policy, provider_id: str) -> bool:
    allowed, _, _ = provider_sets(policy)
    return not allowed or provider_id in allowed

def model_allowed(policy, model_id: str, provider_id: str | None = None) -> bool:
    _, allowed, _ = provider_sets(policy)
    return (provider_id is None or provider_allowed(policy,provider_id)) and (not allowed or model_id in allowed or (provider_id is not None and provider_id+'/'+model_id in allowed))

def provider_visible(policy, provider_id):
    try:data=json.loads(policy.allowed_providers or '[]')
    except ValueError:data=[]
    return not isinstance(data,dict) or provider_id not in data.get('hidden',[])

def model_visible(policy,provider_id,model_id):
    try:data=json.loads(policy.allowed_models or '[]')
    except ValueError:data=[]
    return not isinstance(data,dict) or model_id not in data.get('hidden',{}).get(provider_id,[])


def filter_providers(rows, policy):
    allowed_providers, allowed_models, _ = provider_sets(policy)
    output = []
    for provider in rows:
        if allowed_providers and provider.get("id") not in allowed_providers:
            continue
        if not provider_allowed(policy,provider.get('id','')):continue
        models = provider.get("models", [])
        models = [m for m in models if model_allowed(policy,m.get('id',''),provider.get('id'))]
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
        from .workspaces import PROTECTED_WORKSPACE_NAMES
        patterns={'.env*','*/.env*','*.pem','*.key','*/.env*/*','opencode.json*','*/opencode.json*'}
        for name in PROTECTED_WORKSPACE_NAMES:
            patterns.update((name,name+'/*','*/'+name,'*/'+name+'/*'))
        for pattern in sorted(patterns):
            rules.append({'permission': permission, 'pattern': pattern, 'action': 'deny'})
    return rules
