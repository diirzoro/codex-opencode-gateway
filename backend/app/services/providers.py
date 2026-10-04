"""Provider discovery and real authentication against the installed OpenCode runtime.

No provider list or credential can be synthesized. API keys are sent only server-side.
"""
from urllib.parse import quote

def discover(service):
    providers=service.request("GET","/provider")
    methods=service.request("GET","/provider/auth")
    connected=set(providers.get("connected",[]))
    return [{"id":p["id"],"name":p.get("name",p["id"]),"connected":p["id"] in connected,"models":[{"id":key,"name":value.get("name",key)} for key,value in p.get("models",{}).items()],"auth_methods":[{"type":m.get("type"),"label":m.get("label")} for m in methods.get(p["id"],[])]} for p in providers.get("all",[])]

def auth_methods(service):
    return service.request("GET","/provider/auth")

def set_api_key(service, provider_id, key):
    path = "/auth/" + quote(provider_id, safe="")
    result = service.request("PUT", path, {"type": "api", "key": key})
    if result is not True:
        raise RuntimeError("provider credential was not accepted")
    return True

def remove(service, provider_id):
    return service.request("DELETE", "/auth/" + quote(provider_id, safe=""))

def oauth_authorize(service, provider_id, method, inputs=None):
    path = f"/provider/{quote(provider_id, safe='')}/oauth/authorize"
    return service.request("POST", path, {"method": int(method), "inputs": inputs or {}})

def oauth_callback(service, provider_id, method, code=None):
    path = f"/provider/{quote(provider_id, safe='')}/oauth/callback"
    body = {"method": int(method)}
    if code is not None:
        body["code"] = code
    return service.request("POST", path, body)

def is_connected(service, provider_id):
    data = service.request("GET", "/provider")
    return provider_id in set(data.get("connected", []))
