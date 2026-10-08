"""Owned filesystem and Git operations; no shell strings or client local paths."""
from pathlib import Path, PureWindowsPath
from datetime import datetime, timezone
import base64, difflib, os, re, subprocess, uuid, time, tempfile, zipfile
from fastapi import HTTPException
from sqlalchemy import select
from ..config import settings
from ..models import Project, Workspace

TEMPLATES = {
    "html": {"index.html": "<!doctype html>\n<html lang=\"en\"><meta charset=\"utf-8\"><title>New project</title><link rel=\"stylesheet\" href=\"styles.css\"><h1>New project</h1><script src=\"app.js\"></script></html>\n", "styles.css": "body { font-family: system-ui; margin: 3rem; }\n", "app.js": "'use strict';\n"},
    "python": {"main.py": "def main():\n    print('New project')\n\nif __name__ == '__main__':\n    main()\n", "requirements.txt": "# Add project dependencies here.\n"},
    "node": {"package.json": '{"name":"new-project","private":true,"scripts":{"start":"node index.js"}}\n', "index.js": "console.log('New project');\n"},
}

_FULL_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_BRANCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,119}$")

def owned(db, model, identifier, user_id):
    row = db.scalar(select(model).where(model.id == identifier, model.user_id == user_id))
    if row is None:
        raise HTTPException(404, "Not found")
    return row

def root_for(workspace):
    base = settings.workspace_root.resolve()
    candidate = base / str(workspace.user_id) / str(workspace.id) / "repo"
    current = base
    for part in candidate.relative_to(base).parts:
        current = current / part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise HTTPException(403, "Unsafe workspace path")
    if not candidate.resolve().is_relative_to(base):
        raise HTTPException(403, "Unsafe workspace path")
    return candidate

# Temporary workspace storage allowance for client projects (files, not database storage).
WORKSPACE_QUOTA_BYTES = 50 * 1024 * 1024
# Working materialization bound, distinct from the local-project product quota.
GITHUB_WORKTREE_LIMIT_BYTES = 512 * 1024 * 1024

def quota_bytes(workspace):
    return GITHUB_WORKTREE_LIMIT_BYTES if workspace.project.source_type == "github" else WORKSPACE_QUOTA_BYTES

def usage_bytes(workspace):
    root = root_for(workspace)
    if not root.is_dir():
        return 0
    total = 0
    for item in root.rglob("*"):
        try:
            if item.is_file() and not item.is_symlink():
                total += item.stat().st_size
        except OSError:
            continue
    return total

def storage_payload(workspace):
    used = usage_bytes(workspace)
    limit = quota_bytes(workspace)
    remaining = max(0, limit - used)
    return {"used_bytes": used, "limit_bytes": limit, "remaining_bytes": remaining,
            "scope": "github_working_copy" if workspace.project.source_type == "github" else "local_project",
            "used_mb": round(used / (1024 * 1024), 2), "limit_mb": limit // (1024 * 1024), "over_limit": used >= limit}

def require_quota_headroom(workspace):
    if usage_bytes(workspace) >= quota_bytes(workspace):
        raise HTTPException(413, "Workspace storage limit reached. Export or safely resolve files before continuing.")

def safe_path(workspace, relative=""):
    if "\x00" in relative or "\\" in relative or PureWindowsPath(relative).drive or Path(relative).is_absolute():
        raise HTTPException(422, "A relative workspace path is required")
    parts = Path(relative).parts
    if any(p in {"..", ".git", ".ssh", ".env"} for p in parts):
        raise HTTPException(403, "Path is not accessible")
    root = root_for(workspace)
    candidate = root
    for part in parts:
        candidate = candidate / part
        if candidate.is_symlink() or (hasattr(candidate,"is_junction") and candidate.is_junction()):
            raise HTTPException(403, "Symbolic links are not accessible")
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise HTTPException(403, "Path is outside workspace")
    return candidate

def _git_env():
    hooks = settings.runtime_root / "empty-hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    env = {k:v for k,v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0", GIT_LFS_SKIP_SMUDGE="1")
    return env, hooks

def git(workspace, *arguments, check=True):
    root = root_for(workspace)
    if not root.is_dir():
        raise HTTPException(409, "Workspace files are unavailable")
    env, hooks = _git_env()
    try:
        result = subprocess.run(["git", "-c", f"core.hooksPath={hooks}", "-c", "core.fsmonitor=false", "-c", "credential.helper=", "-c", "protocol.file.allow=never", *arguments], cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        raise HTTPException(503, "Git command unavailable or timed out")
    if check and result.returncode:
        # Git stderr can include host paths or credentials; do not return it.
        raise HTTPException(409, "Git operation failed; workspace files were preserved")
    return result

def _auth_header(token):
    return "AUTHORIZATION: basic " + base64.b64encode(f"x-access-token:{token}".encode()).decode()

def _run_git(cwd, arguments, check=True, workspace=None, token=None):
    env, hooks = _git_env()
    if token:
        env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.extraHeader", GIT_CONFIG_VALUE_0=_auth_header(token))
    try:
        # Auth stays in the child environment, never argv or persistent Git config.
        with tempfile.TemporaryFile() as output:
            with subprocess.Popen(["git", "-c", f"core.hooksPath={hooks}", "-c", "core.fsmonitor=false", "-c", "credential.helper=", "-c", "protocol.file.allow=never", *arguments], cwd=cwd, env=env, stdout=output, stderr=output) as process:
                started = time.monotonic()
                try:
                    while process.poll() is None:
                        if time.monotonic()-started > 180:
                            raise HTTPException(503, "Git operation timed out; working files were preserved")
                        if workspace is not None and usage_bytes(workspace) >= quota_bytes(workspace):
                            raise HTTPException(413, "GitHub working copy exceeds the temporary disk limit; files were preserved for export")
                        time.sleep(0.25)
                finally:
                    if process.poll() is None:
                        process.kill(); process.wait()
                result = subprocess.CompletedProcess(arguments, process.returncode)
            if workspace is not None: require_quota_headroom(workspace)
    except (OSError, subprocess.TimeoutExpired):
        raise HTTPException(503, "Git command unavailable or timed out")
    if check and result.returncode:
        raise HTTPException(409, "Git operation failed; workspace files were preserved")
    return result

def valid_repository(value):
    return bool(value and _FULL_NAME.fullmatch(value))

def valid_branch(value):
    return bool(value and _BRANCH.fullmatch(value) and ".." not in value and "//" not in value and not value.endswith(".lock"))

def clone_github(workspace, clone_url, branch, token):
    root = root_for(workspace)
    result = _run_git(root, ["clone", "--depth", "1", "--single-branch", "--no-tags", "--branch", branch, clone_url, "."], workspace=workspace,token=token)
    if result.returncode:
        raise HTTPException(409, "GitHub clone failed; the selected repository or branch may be unavailable")

def create(db, user, name, source_type, template=None, repository=None, branch=None, github_source=None):
    if source_type == "github":
        if github_source is None:
            raise HTTPException(503, "GitHub App is not connected or the repository was not selected")
        if not valid_repository(repository) or not valid_branch(github_source.get("branch")):
            raise HTTPException(422, "A valid repository and branch are required for a GitHub project")
    else:
        if template and source_type != "template":
            raise HTTPException(422, "Template is only valid for template projects")
        if source_type == "template" and template not in TEMPLATES:
            raise HTTPException(422, "Unsupported template")
        if repository or branch:
            raise HTTPException(422, "Repository and branch apply to GitHub projects only")
    project = Project(id=uuid.uuid4(), user_id=user.id, name=name, source_type=source_type, template=template, default_branch="work")
    if source_type == "github":
        project.repository = repository
        project.github_repository_id = github_source.get("repository_id")
        project.github_installation_id = github_source.get("installation_id")
        project.remote_url = github_source.get("clone_url")
        project.remote_branch = github_source["branch"]
        project.default_branch = github_source["branch"]
    workspace = Workspace(id=uuid.uuid4(), project=project, user_id=user.id, status="creating")
    db.add(project); db.flush(); db.add(workspace); db.flush()
    path = root_for(workspace)
    try:
        path.mkdir(parents=True, exist_ok=False)
        if source_type == "github":
            clone_github(workspace, github_source["clone_url"], github_source["branch"], github_source["token"])
            workspace.base_commit_sha = git(workspace, "rev-parse", "HEAD").stdout.strip()
        else:
            (path/".gitignore").write_text(".env\n.env.*\n!.env.example\n.venv/\nnode_modules/\n__pycache__/\n",encoding="utf-8")
            (path/"README.md").write_text("# "+name+"\n",encoding="utf-8")
            for filename, content in TEMPLATES.get(template,{}).items():
                (path/filename).write_text(content,encoding="utf-8")
            git(workspace,"init","--initial-branch=work")
        workspace.status="ready"
        db.commit()
    except Exception:
        # Preserve any created files and the failed record for diagnosis/recovery.
        workspace.status="failed"
        db.commit()
        raise
    return project, workspace

def project_payload(row):
    return {"id":str(row.id),"name":row.name,"source_type":row.source_type,"repository":row.repository,"branch":row.default_branch,"template":row.template,"remote_url":row.remote_url,"remote_branch":row.remote_branch,"archived":row.archived_at is not None,"created_at":row.created_at}

def workspace_payload(row):
    return {"id":str(row.id),"project_id":str(row.project_id),"status":row.status,"base_commit_sha":row.base_commit_sha,"created_at":row.created_at,"last_activity_at":row.last_activity_at}

def files(workspace, relative=""):
    path=safe_path(workspace,relative)
    if not path.is_dir(): raise HTTPException(404,"Directory not found")
    result=[]
    for item in sorted(path.iterdir(),key=lambda p:p.name.lower()):
        if item.name in {".git",".env",".ssh"} or item.is_symlink() or (hasattr(item,"is_junction") and item.is_junction()): continue
        result.append({"name":item.name,"path":item.relative_to(root_for(workspace)).as_posix(),"type":"directory" if item.is_dir() else "file"})
        if len(result)>=1000: break
    return result

def content(workspace, relative):
    path=safe_path(workspace,relative)
    if not path.is_file(): raise HTTPException(404,"File not found")
    if path.stat().st_size>1000000: raise HTTPException(413,"File exceeds 1 MB preview limit")
    try: return path.read_text(encoding="utf-8")
    except UnicodeError: raise HTTPException(415,"Binary file preview is not supported")

def status(workspace):
    raw=git(workspace,"status","--porcelain=v1","-z","--untracked-files=all").stdout
    entries=[]; fields=iter(raw.split("\x00"))
    for field in fields:
        if not field: continue
        code, path=field[:2],field[3:]
        entry={"status":code,"path":path}
        if "R" in code or "C" in code: entry["original_path"]=next(fields,"")
        entries.append(entry)
    head=git(workspace,"rev-parse","--verify","HEAD",check=False)
    branch=git(workspace,"symbolic-ref","--short","HEAD",check=False)
    result = {"branch":branch.stdout.strip() or None,"head":head.stdout.strip() if head.returncode==0 else None,"changes":entries,"clean":not entries,"push_available":False}
    remote_branch = workspace.project.remote_branch
    if remote_branch and valid_branch(remote_branch):
        counts = git(workspace,"rev-list","--left-right","--count",f"HEAD...refs/remotes/origin/{remote_branch}",check=False)
        if counts.returncode == 0:
            result["ahead"], result["behind"] = (int(value) for value in counts.stdout.split())
    return result

def diff(workspace, relative=None):
    if relative is not None: safe_path(workspace,relative)
    selected=["--",relative] if relative is not None else []
    result=git(workspace,"diff","--no-ext-diff","--no-textconv",*selected).stdout
    result+=git(workspace,"diff","--cached","--no-ext-diff","--no-textconv",*selected).stdout
    for item in status(workspace)["changes"][:30]:
        if relative is not None and item["path"]!=relative: continue
        if item['status']=="??":
            try:
                text=content(workspace,item['path'])
                result+=''.join(difflib.unified_diff([],text.splitlines(True),fromfile='/dev/null',tofile='b/'+item['path']))
            except HTTPException:
                result+="\nUntracked file not previewable.\n"
    return {"diff":result[:1000000],"truncated":len(result)>1000000}

def commit(workspace,user,message):
    if not status(workspace)["changes"]: raise HTTPException(409,"No changes to commit")
    git(workspace,"add","--all")
    git(workspace,"-c",f"user.name={user.username}","-c",f"user.email={user.email}","commit","-m",message)
    return status(workspace)

def push_remote(workspace, remote_url, branch, token):
    root = root_for(workspace)
    result = _run_git(root, ["push", remote_url, f"HEAD:refs/heads/{branch}"],workspace=workspace,token=token)
    if result.returncode:
        raise HTTPException(409, "Git push was rejected; the remote was not updated")

def sync_remote(workspace, remote_url, branch, token):
    if not status(workspace)["clean"]:
        raise HTTPException(409, "Commit or export your uncommitted work before syncing; nothing was discarded")
    ref = f"refs/remotes/origin/{branch}"
    _run_git(root_for(workspace), ["fetch", "--depth=50", "--no-tags", remote_url, f"refs/heads/{branch}:{ref}"], workspace=workspace,token=token)
    # No reset, rebase, force-push or conflict resolution. Divergence preserves work.
    git(workspace, "merge", "--ff-only", ref)
    return status(workspace)

def export(workspace):
    """User-requested source export, including uncommitted work, without Git/auth data."""
    # The caller removes the temporary ZIP after the response is sent.
    handle = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    path = Path(handle.name); handle.close()
    try:
        root = root_for(workspace)
        if not root.is_dir(): raise HTTPException(409,"Workspace files are unavailable")
        with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as archive:
            for directory, folders, files in os.walk(root,followlinks=False):
                folders[:] = [name for name in folders if name not in {'.git','.ssh'} and not (Path(directory)/name).is_symlink()]
                for name in files:
                    item=Path(directory)/name
                    relative=item.relative_to(root).as_posix()
                    if item.is_symlink() or any(part.startswith('.env') or part.endswith(('.key','.pem')) for part in item.relative_to(root).parts): continue
                    archive.write(item,relative)
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise
