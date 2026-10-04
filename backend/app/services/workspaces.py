"""Owned filesystem and Git operations; no shell strings or client local paths."""
from pathlib import Path, PureWindowsPath
from datetime import datetime, timezone
import difflib, os, subprocess, uuid
from fastapi import HTTPException
from sqlalchemy import select
from ..config import settings
from ..models import Project, Workspace

TEMPLATES = {
    "html": {"index.html": "<!doctype html>\n<html lang=\"en\"><meta charset=\"utf-8\"><title>New project</title><link rel=\"stylesheet\" href=\"styles.css\"><h1>New project</h1><script src=\"app.js\"></script></html>\n", "styles.css": "body { font-family: system-ui; margin: 3rem; }\n", "app.js": "'use strict';\n"},
    "python": {"main.py": "def main():\n    print('New project')\n\nif __name__ == '__main__':\n    main()\n", "requirements.txt": "# Add project dependencies here.\n"},
    "node": {"package.json": '{"name":"new-project","private":true,"scripts":{"start":"node index.js"}}\n', "index.js": "console.log('New project');\n"},
}

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

def git(workspace, *arguments, check=True):
    root = root_for(workspace)
    if not root.is_dir():
        raise HTTPException(409, "Workspace files are unavailable")
    hooks = settings.runtime_root / "empty-hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    env = {k:v for k,v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    try:
        result = subprocess.run(["git", "-c", f"core.hooksPath={hooks}", "-c", "core.fsmonitor=false", "-c", "credential.helper=", "-c", "protocol.file.allow=never", *arguments], cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        raise HTTPException(503, "Git command unavailable or timed out")
    if check and result.returncode:
        # Git stderr can include host paths or credentials; do not return it.
        raise HTTPException(409, "Git operation failed; workspace files were preserved")
    return result

def create(db, user, name, source_type, template=None, repository=None, branch=None):
    if source_type == "github":
        raise HTTPException(503, "GitHub App is not connected yet")
    if source_type == "template" and template not in TEMPLATES:
        raise HTTPException(422, "Unsupported template")
    if source_type != "template" and template:
        raise HTTPException(422, "Template is only valid for template projects")
    if repository or branch:
        raise HTTPException(422, "Repository and branch apply to GitHub projects only")
    project = Project(id=uuid.uuid4(), user_id=user.id, name=name, source_type=source_type, template=template, default_branch="work")
    workspace = Workspace(id=uuid.uuid4(), project_id=project.id, user_id=user.id, status="creating")
    db.add(project); db.flush(); db.add(workspace); db.flush()
    path = root_for(workspace)
    try:
        path.mkdir(parents=True, exist_ok=False)
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
    return {"id":str(row.id),"name":row.name,"source_type":row.source_type,"repository":row.repository,"branch":row.default_branch,"template":row.template,"created_at":row.created_at}

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
    return {"branch":branch.stdout.strip() or None,"head":head.stdout.strip() if head.returncode==0 else None,"changes":entries,"clean":not entries,"push_available":False}

def diff(workspace):
    result=git(workspace,"diff","--no-ext-diff","--no-textconv").stdout
    result+=git(workspace,"diff","--cached","--no-ext-diff","--no-textconv").stdout
    for item in status(workspace)["changes"][:30]:
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
