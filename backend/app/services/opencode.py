"""OpenCode 1.18.31 adapter. Local runtimes are isolated contexts, NOT OS sandboxes."""
import atexit, base64, json, os, secrets, shutil, socket, subprocess, threading, time
from dataclasses import dataclass
from urllib.parse import quote
import httpx
from fastapi import HTTPException
from ..config import settings
from .policy import DEFAULT_PERMISSION, permission_config
from .workspaces import root_for

# Admin provider/model/tool policy is applied when a per-workspace runtime starts.
_policy_permission = dict(DEFAULT_PERMISSION)

def configure_policy(policy):
    global _policy_permission
    _policy_permission = permission_config(policy) if policy is not None else dict(DEFAULT_PERMISSION)

@dataclass
class Runtime:
    url: str
    password: str
    process: subprocess.Popen
    log: object

_runtimes = {}
_lock = threading.RLock()

class OpenCodeService:
    def __init__(self, url, password=None, directory=None):
        self.url=url
        self.auth=("opencode",password) if password else None
        self.params={"directory":str(directory)} if directory else {}

    def request(self, method, path, data=None, timeout=15):
        try:
            with httpx.Client(base_url=self.url, auth=self.auth, timeout=timeout, trust_env=False) as client:
                response=client.request(method,path,params=self.params,json=data)
                response.raise_for_status()
                return response.json() if response.content else None
        except (httpx.HTTPError,ValueError):
            raise HTTPException(503,"OpenCode request failed; no operation success was assumed")

    def health(self):
        result=self.request("GET","/global/health")
        if not isinstance(result,dict) or result.get("healthy") is not True:
            raise HTTPException(503,"OpenCode is unavailable")
        return {"healthy":True,"version":str(result.get("version","unknown"))}

    def create_session(self,title):
        result=self.request("POST","/session",{"title":title,"permission":[{"permission":"*","pattern":"*","action":"ask"},{"permission":"external_directory","pattern":"*","action":"deny"}]})
        if not isinstance(result,dict) or not str(result.get("id","")).startswith("ses"):
            raise HTTPException(502,"OpenCode returned an invalid session")
        return result["id"]

    def session_path(self,identifier,suffix=""):
        return "/session/"+quote(identifier,safe="")+suffix

def shared_health():
    # Health only; never forward shared sessions/providers/auth to customers.
    return OpenCodeService(settings.opencode_url,os.getenv("OPENCODE_SERVER_PASSWORD")).health()

def for_workspace(workspace):
    if settings.runtime_mode!="local":
        raise HTTPException(503,"Local runtime is disabled; enable only for trusted local development")
    key=str(workspace.id)
    with _lock:
        runtime=_runtimes.get(key)
        if runtime and runtime.process.poll() is None:
            return OpenCodeService(runtime.url,runtime.password,root_for(workspace))
        binary=shutil.which(settings.opencode_binary)
        if not binary: raise HTTPException(503,"OpenCode executable is not installed")
        repo=root_for(workspace)
        if not repo.is_dir(): raise HTTPException(409,"Workspace files are missing")
        context=settings.runtime_root/str(workspace.user_id)/str(workspace.id)
        context.mkdir(parents=True,exist_ok=True)
        env={k:v for k,v in os.environ.items() if k.upper() in {"PATH","SYSTEMROOT","WINDIR","COMSPEC","PATHEXT","TEMP","TMP","PROCESSOR_ARCHITECTURE"}}
        for key_env,folder in {"HOME":"home","USERPROFILE":"home","APPDATA":"config","LOCALAPPDATA":"data","XDG_CONFIG_HOME":"config","XDG_DATA_HOME":"data","XDG_STATE_HOME":"state","XDG_CACHE_HOME":"cache"}.items():
            path=context/folder; path.mkdir(exist_ok=True); env[key_env]=str(path)
        password=secrets.token_urlsafe(32)
        env.update(OPENCODE_SERVER_PASSWORD=password,OPENCODE_CONFIG_CONTENT=json.dumps({"autoupdate":False,"share":"disabled","plugin":[],"permission":_policy_permission}))
        with socket.socket() as sock:
            sock.bind(("127.0.0.1",0)); port=sock.getsockname()[1]
        log=open(context/"runtime.log","a",encoding="utf-8")
        try:
            process=subprocess.Popen([binary,"serve","--pure","--hostname","127.0.0.1","--port",str(port)],cwd=repo,env=env,stdout=log,stderr=log)
        except OSError:
            log.close(); raise HTTPException(503,"Cannot start local OpenCode runtime")
        runtime=Runtime(f"http://127.0.0.1:{port}",password,process,log)
        _runtimes[key]=runtime
        service=OpenCodeService(runtime.url,password,repo)
        for _ in range(30):
            if process.poll() is not None: break
            try:
                health=service.health()
                if health["version"]!="1.18.31":
                    stop_workspace(workspace)
                    raise HTTPException(503,"Installed OpenCode version has not been verified for this adapter")
                return service
            except HTTPException:
                time.sleep(.5)
        stop_workspace(workspace)
        raise HTTPException(503,"OpenCode startup failed or timed out")

def stop_workspace(workspace):
    with _lock:
        runtime=_runtimes.pop(str(workspace.id),None)
        if runtime:
            if runtime.process.poll() is None:
                if os.name=="nt":
                    subprocess.run(["taskkill","/PID",str(runtime.process.pid),"/T","/F"],capture_output=True,timeout=15)
                else:
                    runtime.process.terminate()
                    try: runtime.process.wait(timeout=10)
                    except subprocess.TimeoutExpired: runtime.process.kill()
            runtime.log.close()

def stop_all():
    for key in list(_runtimes):
        stop_workspace(type("WorkspaceRef",(),{"id":key})())

atexit.register(stop_all)
