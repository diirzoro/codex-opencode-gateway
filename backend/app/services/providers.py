"""Discover installed auth methods; never read global user auth/config."""
def discover(service):
    providers=service.request("GET","/provider")
    methods=service.request("GET","/provider/auth")
    connected=set(providers.get("connected",[]))
    return [{"id":p["id"],"name":p.get("name",p["id"]),"connected":p["id"] in connected,"models":[{"id":key,"name":value.get("name",key)} for key,value in p.get("models",{}).items()],"auth_methods":[{"type":m.get("type"),"label":m.get("label")} for m in methods.get(p["id"],[])]} for p in providers.get("all",[])]
