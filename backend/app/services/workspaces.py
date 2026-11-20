"""Owned filesystem and Git operations; no shell strings or client local paths."""
from pathlib import Path, PureWindowsPath
from datetime import datetime, timezone
import base64, difflib, os, re, stat, subprocess, uuid, time, tempfile, zipfile, selectors
from contextlib import contextmanager
from fastapi import HTTPException
from sqlalchemy import select, and_, or_, exists
from ..config import settings
from ..models import Project, Workspace, GithubConnection

TEMPLATES = {
    "html": {"index.html": "<!doctype html>\n<html lang=\"en\"><meta charset=\"utf-8\"><title>New project</title><link rel=\"stylesheet\" href=\"styles.css\"><h1>New project</h1><script src=\"app.js\"></script></html>\n", "styles.css": "body { font-family: system-ui; margin: 3rem; }\n", "app.js": "'use strict';\n"},
    "python": {"main.py": "def main():\n    print('New project')\n\nif __name__ == '__main__':\n    main()\n", "requirements.txt": "# Add project dependencies here.\n"},
    "node": {"package.json": '{"name":"new-project","private":true,"scripts":{"start":"node index.js"}}\n', "index.js": "console.log('New project');\n"},
}

_FULL_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_BRANCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,119}$")

def github_project_attached(db, user_id, project):
    """An imported/published GitHub workspace is usable ONLY with its owner
    connection and original authorized installation. Never delete its files
    merely because OAuth was revoked; reauthorization can restore access.
    """
    # A local project stays local even when its owner has previously
    # published it to a GitHub remote; unlinking GitHub cannot lock it.
    if project.source_type != 'github':
        return True
    if project.github_installation_id is None:
        return False
    return db.scalar(select(GithubConnection.id).where(
        GithubConnection.user_id == user_id,
        GithubConnection.installation_id == project.github_installation_id,
        GithubConnection.suspended.is_(False))) is not None


def visible_project_predicate(user_id):
    connected = exists(select(GithubConnection.id).where(
        GithubConnection.user_id == user_id,
        GithubConnection.installation_id == Project.github_installation_id,
        GithubConnection.suspended.is_(False)))
    return or_(Project.source_type != 'github',
               and_(Project.source_type == 'github',Project.github_installation_id.is_not(None),connected))


def owned(db, model, identifier, user_id):
    row = db.scalar(select(model).where(model.id == identifier, model.user_id == user_id))
    if row is None:
        raise HTTPException(404, "Not found")
    if model in (Project, Workspace):
        project=row if model is Project else row.project
        if not github_project_attached(db,user_id,project):
            raise HTTPException(409, "GitHub project disconnected. Reauthorize the original GitHub account and installation to reopen this workspace; local files are preserved.")
    return row

def root_for(workspace, *, allow_expired=False):
    if not allow_expired and workspace.status in {"cache_expiring", "cache_expired"}:
        raise HTTPException(410, "Workspace working files are unavailable under the project storage policy. Account records and the original GitHub repository were not deleted.")
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

# Unified owner-wide limit. Storage in GitHub.com is not part of this allowance.
# Legacy constants are retained for consumers but do not define a second quota.
WORKSPACE_QUOTA_BYTES = 50 * 1024 * 1024
GITHUB_WORKTREE_LIMIT_BYTES = 512 * 1024 * 1024

def quota_bytes(workspace, db=None):
    from .storage_policy import quota_mb, MIB
    if db is not None:
        return quota_mb(db, workspace.user_id) * MIB
    from ..database import SessionLocal
    with SessionLocal() as session:
        return quota_mb(session, workspace.user_id) * MIB

def usage_bytes(workspace, *, stop_at=None):
    if workspace.status in {"cache_expiring", "cache_expired"}:
        return 0
    root = root_for(workspace)
    if not root.is_dir():
        return 0
    total = 0
    def failed(error):raise error
    try:
        if hasattr(os,'fwalk'):
            # Descriptor-relative stat: never traverse symlink directories or
            # follow a link substituted for a file during quota inspection.
            for _,_,files,fd in os.fwalk(root,follow_symlinks=False,onerror=failed):
                for name in files:
                    try:info=os.stat(name,dir_fd=fd,follow_symlinks=False)
                    except FileNotFoundError:continue  # File concurrently removed.
                    if stat.S_ISREG(info.st_mode):total+=info.st_size
                    if stop_at is not None and total>=stop_at:return total
        else:
            # Compatibility for non-POSIX development; production is Ubuntu.
            for parent,_,files in os.walk(root,followlinks=False,onerror=failed):
                for name in files:
                    try:info=(Path(parent)/name).lstat()
                    except FileNotFoundError:continue
                    if stat.S_ISREG(info.st_mode):total+=info.st_size
                    if stop_at is not None and total>=stop_at:return total
    except OSError:
        # Unknown usage must not admit another Native execution as under quota.
        raise HTTPException(503,'Workspace storage inspection is unavailable; retry before continuing') from None
    return total


def account_storage_parts(db,user_id,*,stop_at=None):
    """Count regular on-disk files owned by this account, local + GitHub alike.

    Count each Workspace's working files (including local .git metadata).
    Never traverse another owner's path or follow a link.
    """
    local=github=0
    rows=db.scalars(select(Workspace).join(Project,Project.id==Workspace.project_id).where(
        Workspace.user_id==user_id,Project.user_id==user_id,
        Workspace.status.not_in(['cache_expiring','cache_expired'])))
    for row in rows:
        remaining=None if stop_at is None else max(0,stop_at-local-github)
        amount=usage_bytes(row,stop_at=remaining)
        if row.project.source_type=='github':github+=amount
        else:local+=amount
        if stop_at is not None and local+github>=stop_at:break
    return local,github


def account_storage(db,user_id,*,stop_at=None):
    return sum(account_storage_parts(db,user_id,stop_at=stop_at))


def account_local_storage(db,user_id,*,stop_at=None):
    """Compatibility helper returning local-only usage, not a second allowance."""
    return account_storage_parts(db,user_id,stop_at=stop_at)[0]


def account_local_storage_payload(db,user_id):
    from .storage_policy import quota_mb, capacity_label, MIB
    local,github=account_storage_parts(db,user_id)
    used=local+github
    limit_mb=quota_mb(db,user_id)
    limit=limit_mb*MIB
    return {'used_bytes':used,'limit_bytes':limit,'remaining_bytes':max(0,limit-used),
            'used_mb':round(used/MIB,2),'limit_mb':limit_mb,
            'local_used_mb':round(local/MIB,2),'github_used_mb':round(github/MIB,2),
            'local_used_bytes':local,'github_used_bytes':github,
            'over_limit':used>=limit,'percent_used':round(100*used/limit,1),
            'plan_label':capacity_label(db,user_id),'scope':'account_all_projects',
            'plan_disclaimer':'Gateway platform and workspace storage only. No AI model/API subscription or tokens; connect your own provider.'}


def require_account_local_headroom(db,user_id,additional=0):
    """Legacy call sites enforce the SAME shared quota, including GitHub."""
    from .storage_policy import require_headroom
    return require_headroom(db,user_id,additional=additional)


def storage_payload(workspace, db=None):
    from .workspace_cache import cache_payload
    from ..database import SessionLocal
    own_session=db is None
    if own_session:
        db=SessionLocal()
    try:
        account=account_local_storage_payload(db,workspace.user_id)
        workspace_used=usage_bytes(workspace)
        return {**account,'cache':cache_payload(workspace),
                'workspace_used_mb':round(workspace_used/1048576,2),
                'workspace_used_bytes':workspace_used,
                'workspace_source':workspace.project.source_type}
    finally:
        if own_session:db.close()


def require_quota_headroom(workspace,db=None,additional=0):
    from ..database import SessionLocal
    from .storage_policy import require_headroom
    own_session=db is None
    if own_session:db=SessionLocal()
    try:
        return require_headroom(db,workspace.user_id,additional=additional)
    finally:
        if own_session:db.close()

PROTECTED_WORKSPACE_NAMES = frozenset({'.git','.ssh','.aws','.config','.opencode','opencode.json','opencode.jsonc','auth.json','credentials.json'})

def protected_component(name):
    value=name.casefold()
    return value in PROTECTED_WORKSPACE_NAMES or value.startswith('.env') or value.endswith(('.pem','.key'))

def safe_path(workspace, relative=""):
    if "\x00" in relative or "\\" in relative or PureWindowsPath(relative).drive or Path(relative).is_absolute():
        raise HTTPException(422, "A relative workspace path is required")
    parts = Path(relative).parts
    if (os.getenv('OPENCODE_NATIVE_TEST_ENABLED','').lower() in {'1','true','yes'} or os.getenv('OPENCODE_NATIVE_LIVE_ENABLED','').lower() in {'1','true','yes'}) and any(p in {'.opencode','opencode.json','opencode.jsonc'} for p in parts):
        raise HTTPException(403, "Native executable configuration is managed by the server")
    if any(p == ".." or protected_component(p) for p in parts):
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
    env = dict(PATH="/usr/bin:/bin", HOME="/nonexistent", LANG="C.UTF-8",
               GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0",
               GIT_LFS_SKIP_SMUDGE="1", GIT_ATTR_NOSYSTEM="1",
               GIT_NO_REPLACE_OBJECTS="1", GIT_ALLOW_PROTOCOL="https",
               GIT_SSH_COMMAND="/bin/false")
    return env, Path(os.devnull)


@contextmanager
def _git_execution_scope(cwd, arguments, env, workspace=None):
    """Administrative Git only; no extra Gateway hop during native tool calls.

    Existing customer metadata is mounted in a private PID/filesystem boundary.
    Network Git uses an empty allowlisted config, so repository includes, URL
    rewrites, filters and alternate-ref commands cannot execute with its token.
    """
    fixed=["-c","core.hooksPath=/dev/null","-c","core.fsmonitor=false",
           "-c","credential.helper=","-c","protocol.file.allow=never",
           "-c","core.alternateRefsCommand=/bin/true","-c","gc.auto=0",
           "-c","maintenance.auto=false","-c","push.recurseSubmodules=no"]
    if arguments and arguments[0] in {'clone','fetch','push'}:
        urls=[value for value in arguments if value.startswith('https://')]
        if len(urls)!=1 or not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?',urls[0]):
            raise HTTPException(422,'An authorized HTTPS GitHub repository is required')
        fixed+=['-c','http.followRedirects=false','-c','http.proxy=']
    if os.getenv('PI_PROJECT_SANDBOX') != '1':
        yield ['/usr/bin/git',*fixed,*arguments],(),env
        return
    root=Path(cwd)
    if not root.is_absolute() or '..' in root.parts:
        raise HTTPException(503,'Invalid isolated Git directory')
    fds=[];group=None;temp=None;phase='project-directory'
    try:
        # Walk from / with openat and O_NOFOLLOW; do not reopen a checked path.
        fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        fds.append(fd)
        for part in root.parts[1:]:
            next_fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=next_fd;fds[0]=fd
        initial=workspace is not None and workspace.status!='ready' and arguments[0] in {
            'init','clone','sparse-checkout','checkout'}
        git_fd=None
        if not initial:
            git_fd=os.open('.git',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);fds.append(git_fd)
        phase='resource-root'
        cg_root=Path(os.environ['PI_SANDBOX_CGROUP_ROOT'])
        if not str(cg_root).startswith('/sys/fs/cgroup/') or cg_root.resolve()!=cg_root:
            raise ValueError('Invalid resource delegation')
        if not {'cpu','memory','pids'}.issubset(set((cg_root/'cgroup.subtree_control').read_text().split())):
            raise ValueError('Resource controllers unavailable')
        phase='resource-group'
        group=cg_root/('pi-project-'+str(uuid.uuid4()));group.mkdir()
        phase='resource-limits'
        for name,value in {'memory.max':768*1024*1024,'memory.swap.max':0,
                           'memory.oom.group':1,'pids.max':128,'cpu.max':'100000 100000','cpu.weight':20}.items():
            (group/name).write_text(str(value))
        limit_fd=os.open(group/'cgroup.procs',os.O_WRONLY|os.O_NOFOLLOW);fds.append(limit_fd)
        phase='git-configuration'
        args=['/usr/local/libexec/pi-project-bwrap','--unshare-user','--unshare-pid',
              '--unshare-ipc','--unshare-uts','--hostname','project','--disable-userns',
              '--die-with-parent','--new-session','--cap-drop','ALL']
        if arguments[0] not in {'clone','fetch','push'}:args+=['--unshare-net']
        else:
            # Administrative Git alone needs host DNS; these files never enter
            # the model's private-network tool namespace.
            args+=['--ro-bind','/etc/resolv.conf','/etc/resolv.conf']
        for item in ['/usr/bin','/usr/lib','/usr/share','/bin','/lib','/lib64','/etc/ssl/certs']:
            args+=['--ro-bind',item,item]
        args+=['--proc','/proc','--dev','/dev','--tmpfs','/tmp',
               '--bind',f'/proc/self/fd/{fd}',str(root),'--chdir',str(root)]
        child_env=dict(env)
        if git_fd is not None:
            # Parse only pinned config bytes; includes are explicitly disabled.
            cfg=os.open('config',os.O_RDONLY|os.O_NOFOLLOW,dir_fd=git_fd)
            try:
                info=os.fstat(cfg)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>65536:
                    raise ValueError('Unsafe Git configuration')
                data=os.read(cfg,65537)
            finally:os.close(cfg)
            if len(data)>65536:raise ValueError('Git configuration exceeds limit')
            parsed=subprocess.run(['/usr/bin/git','config','--no-includes','--file','-',
                                   '--null','--list'],input=data,capture_output=True,env=_git_env()[0],timeout=3)
            if parsed.returncode:raise ValueError('Invalid Git configuration')
            # Preserve sparse checkout and object-format semantics, not scripts
            # or user-controlled remotes. Commit authors are supplied by the API.
            safe={}
            allowed={'core.repositoryformatversion':{'0','1'},'core.sparsecheckout':{'true','false'},
                     'core.sparsecheckoutcone':{'true','false'},'core.ignorecase':{'true','false'},
                     'extensions.objectformat':{'sha1','sha256'}}
            for row in parsed.stdout.split(b'\0'):
                key,sep,value=row.partition(b'\n')
                key=key.decode('utf8','strict').lower();value=value.decode('utf8','strict').lower()
                if sep and key in allowed and value in allowed[key]:safe[key]=value
            temp=tempfile.TemporaryDirectory(prefix='pi-git-config-')
            config=Path(temp.name)/'config'
            lines=['[core]','\tbare = false','\tlogAllRefUpdates = true']
            for section in ['core','extensions']:
                rows=[(key.split('.')[1],value) for key,value in safe.items() if key.startswith(section+'.')]
                if rows:lines+=['['+section+']',*[f'\t{key} = {value}' for key,value in rows]]
            config.write_text('\n'.join(lines)+'\n');config.chmod(0o600)
            args+=['--bind',f'/proc/self/fd/{git_fd}','/sandbox-git',
                   '--ro-bind',str(config),'/sandbox-git/config']
            # GIT_COMMON_DIR overrides an untrusted commondir file without
            # creating or changing any file in the customer's .git directory.
            child_env.update(GIT_COMMON_DIR='/sandbox-git')
            fixed=['--git-dir=/sandbox-git','--work-tree='+str(root),*fixed]
        bootstrap=(
            'import os,sys;root=int(sys.argv[1]);meta=int(sys.argv[2]);limit=int(sys.argv[3]);'
            'a=os.fstat(root);b=os.stat(os.getcwd());assert(a.st_dev,a.st_ino)==(b.st_dev,b.st_ino);'
            'a=os.fstat(meta) if meta>=0 else None;b=os.stat("/sandbox-git") if meta>=0 else None;'
            'assert meta<0 or (a.st_dev,a.st_ino)==(b.st_dev,b.st_ino);'
            'os.write(limit,b"0");'
            '[os.close(x) for x in [root,meta,limit] if x>=0];'
            'os.execve("/usr/bin/git",["git",*sys.argv[4:]],os.environ)')
        args+=['--','/usr/bin/python3','-c',bootstrap,str(fd),str(git_fd if git_fd is not None else -1),str(limit_fd),*fixed,*arguments]
        phase='git-launch'
        yield args,tuple(fds),child_env
    except (OSError,ValueError,KeyError,UnicodeError,subprocess.TimeoutExpired) as error:
        # Fixed stages and numeric OS codes diagnose containment failures
        # without exposing server paths, environment or repository contents.
        code=error.errno if isinstance(error,OSError) else type(error).__name__
        raise HTTPException(503,f'Isolated Git execution unavailable ({phase}: {code}); project files preserved') from None
    finally:
        for fd in fds:
            try:os.close(fd)
            except OSError:pass
        if temp is not None:temp.cleanup()
        if group is not None:
            try:(group/'cgroup.kill').write_text('1')
            except OSError:pass
            for _ in range(10):
                try:group.rmdir();break
                except OSError:time.sleep(0.01)

def _bounded_git_result(command,cwd,env,fds):
    # Bound actual pipe bytes, not just the final HTTP response slice. A large
    # diff must not allocate unbounded memory in the administrative Gateway.
    output=bytearray();total=0;deadline=time.monotonic()+30
    with subprocess.Popen(command,cwd=cwd,env=env,pass_fds=fds,
                          stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE) as process:
        try:
            with selectors.DefaultSelector() as streams:
                streams.register(process.stdout,selectors.EVENT_READ,True)
                streams.register(process.stderr,selectors.EVENT_READ,False)
                while streams.get_map():
                    if time.monotonic()>deadline:raise subprocess.TimeoutExpired(command,30)
                    for key,_ in streams.select(0.1):
                        data=os.read(key.fileobj.fileno(),65536)
                        if not data:streams.unregister(key.fileobj);continue
                        total+=len(data)
                        if total>4*1024*1024:raise HTTPException(413,'Git output exceeds review limit; files preserved')
                        if key.data:output.extend(data)
            code=process.wait(timeout=max(0.01,deadline-time.monotonic()))
            return subprocess.CompletedProcess(command,code,output.decode('utf8','replace'),'')
        finally:
            if process.poll() is None:process.kill();process.wait()

def git(workspace, *arguments, check=True):
    root = root_for(workspace)
    if not root.is_dir():
        raise HTTPException(409, "Workspace files are unavailable")
    env, hooks = _git_env()
    try:
        with _git_execution_scope(root,list(arguments),env,workspace) as (command,fds,child_env):
            result = _bounded_git_result(command,root,child_env,fds)
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
        env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.https://github.com/.extraHeader", GIT_CONFIG_VALUE_0=_auth_header(token))
    try:
        # Auth stays in the child environment, never argv or persistent Git config.
        with _git_execution_scope(cwd,list(arguments),env,workspace) as (command,fds,child_env):
            with subprocess.Popen(command, cwd=cwd, env=child_env, pass_fds=fds, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as process:
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

def validate_working_paths(paths):
    if not isinstance(paths, list) or len(paths)>10:
        raise HTTPException(422, "Choose up to 10 working directories")
    result=[]
    for value in paths:
        if not isinstance(value,str) or not re.fullmatch(r"[A-Za-z0-9_./ -]{1,200}",value):
            raise HTTPException(422, "Working directories must be relative repository paths")
        parts=Path(value).parts
        if value.startswith(('/', '-')) or not parts or any(p in {'.','..','.git','.ssh'} or p.startswith('.env') for p in parts):
            raise HTTPException(422, "Invalid working directory")
        normalized=Path(value).as_posix()
        if normalized not in result: result.append(normalized)
    return result

def clone_github(workspace, clone_url, branch, token, working_paths=None):
    root = root_for(workspace)
    paths=validate_working_paths(working_paths or [])
    # Explicit sparse directories reduce checkout size. Keep shallow blobs locally:
    # unconfigured promisor fetches from OpenCode could otherwise break private repos.
    arguments=["clone", "--depth", "1", "--single-branch", "--no-tags"]
    if paths: arguments.append("--no-checkout")
    result = _run_git(root, [*arguments,"--branch",branch,clone_url,"."], workspace=workspace,token=token)
    if paths:
        for path in paths:
            if git(workspace,"cat-file","-t","HEAD:"+path,check=False).stdout.strip() != "tree":
                raise HTTPException(422,"A selected working directory does not exist in this branch; files were preserved")
        _run_git(root,["sparse-checkout","set","--cone","--",*paths],workspace=workspace,token=token)
        _run_git(root,["checkout",branch],workspace=workspace,token=token)
    if result.returncode:
        raise HTTPException(409, "GitHub clone failed; the selected repository or branch may be unavailable")

def require_live_project_quota(db, user_id):
    root = settings.workspace_root
    if root != Path("/var/lib/opencode-workspaces"):
        return

    import fcntl
    import struct

    from .storage_policy import MIB, quota_mb

    expected = quota_mb(db, user_id) * MIB
    # Linux FS_IOC_FSGETXATTR returns the XFS project ID and inheritance flag.
    fsxattr = bytearray(28)
    try:
        fd = os.open(root / str(user_id), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            fcntl.ioctl(fd, 0x801C581F, fsxattr)
            flags, _, _, project_id = struct.unpack_from("=IIII", fsxattr)
            capacity = os.fstatvfs(fd)
            filesystem = os.statvfs(root)
        finally:
            os.close(fd)
        visible_limit = capacity.f_blocks * capacity.f_frsize
        filesystem_size = filesystem.f_blocks * filesystem.f_frsize
        # XFS reports the active project limit in statvfs on an inheriting
        # directory. A project tag alone can exist before cron sets its limit.
        if (project_id != 0 and flags & 0x00000200 and
                visible_limit == expected and visible_limit < filesystem_size):
            return
    except OSError:
        pass

    raise HTTPException(
        status_code=503,
        detail="Project storage is being provisioned or updated. Please retry shortly.",
        headers={"Retry-After": "60"},
    )


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
    require_live_project_quota(db, user.id)
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
            clone_github(workspace, github_source["clone_url"], github_source["branch"], github_source["token"],github_source.get("working_paths"))
            workspace.base_commit_sha = git(workspace, "rev-parse", "HEAD").stdout.strip()
        else:
            (path/".gitignore").write_text(".env\n.env.*\n!.env.example\n.venv/\nnode_modules/\n__pycache__/\n",encoding="utf-8")
            (path/"README.md").write_text("# "+name+"\n",encoding="utf-8")
            for filename, content in TEMPLATES.get(template,{}).items():
                (path/filename).write_text(content,encoding="utf-8")
            git(workspace,"init","--initial-branch=work")
        # Verify aggregate owner use AFTER clone/template creation and BEFORE publish.
        # No secondary GitHub-only allowance.
        require_quota_headroom(workspace,db)
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
    from .workspace_cache import cache_payload
    try:
        available = root_for(row).is_dir()
    except (HTTPException, OSError):
        available = False
    return {"files_available":available,"cache":cache_payload(row),"id":str(row.id),"project_id":str(row.project_id),"status":row.status,"base_commit_sha":row.base_commit_sha,"created_at":row.created_at,"last_activity_at":row.last_activity_at}

@contextmanager
def _project_directory(workspace, relative=''):
    safe_path(workspace,relative)
    root=root_for(workspace);fd=None
    try:
        fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        for part in [*root.parts[1:],*Path(relative).parts]:
            next_fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=next_fd
        yield fd
    except OSError as error:
        status=404 if error.errno==2 else 403 if error.errno in {1,13,20,40} else 503
        raise HTTPException(status,'Project file access unavailable') from None
    finally:
        if fd is not None:os.close(fd)

@contextmanager
def _project_file(workspace, relative):
    safe_path(workspace,relative)
    parts=Path(relative).parts
    if not parts:raise HTTPException(404,'File not found')
    with _project_directory(workspace,str(Path(*parts[:-1])) if len(parts)>1 else '') as parent:
        fd=None
        try:
            fd=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
            info=os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:
                raise HTTPException(403,'Linked or special project files are not accessible')
            yield fd,info
        except OSError as error:
            raise HTTPException(404 if error.errno==2 else 403,'Project file access denied') from None
        finally:
            if fd is not None:os.close(fd)

def files(workspace, relative=""):
    result=[]
    with _project_directory(workspace,relative) as fd, os.scandir(fd) as entries:
        for item in entries:
            if protected_component(item.name):continue
            try:info=os.stat(item.name,dir_fd=fd,follow_symlinks=False)
            except FileNotFoundError:continue
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):continue
            result.append({'name':item.name,'path':(Path(relative)/item.name).as_posix(),
                           'type':'directory' if stat.S_ISDIR(info.st_mode) else 'file'})
            if len(result)>=1000:break
    return sorted(result,key=lambda item:item['name'].lower())

def file_bytes(workspace, relative, maximum=1000000):
    with _project_file(workspace,relative) as (fd,info):
        if info.st_size>maximum:raise HTTPException(413,'File exceeds preview limit')
        data=bytearray()
        while len(data)<=maximum:
            chunk=os.read(fd,min(65536,maximum+1-len(data)))
            if not chunk:break
            data.extend(chunk)
        if len(data)>maximum:raise HTTPException(413,'File exceeds preview limit')
        return bytes(data)

def content(workspace, relative):
    data=file_bytes(workspace,relative)
    if b'\0' in data:raise HTTPException(415,'Binary file preview is not supported')
    try:return data.decode('utf8')
    except UnicodeError:raise HTTPException(415,'Binary file preview is not supported') from None

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
        maximum=quota_bytes(workspace);count=0;total=0
        with _project_directory(workspace) as root_fd, zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as archive:
            def walk(fd,prefix='',depth=0):
                nonlocal count,total
                if depth>64:raise HTTPException(413,'Project export depth exceeds limit')
                with os.scandir(fd) as entries:
                    for item in entries:
                        if protected_component(item.name):continue
                        info=os.stat(item.name,dir_fd=fd,follow_symlinks=False)
                        if stat.S_ISLNK(info.st_mode):continue
                        relative=prefix+item.name
                        child=None
                        try:
                            if stat.S_ISDIR(info.st_mode):
                                child=os.open(item.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
                                walk(child,relative+'/',depth+1)
                            elif stat.S_ISREG(info.st_mode):
                                child=os.open(item.name,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW,dir_fd=fd)
                                pinned=os.fstat(child)
                                if not stat.S_ISREG(pinned.st_mode) or pinned.st_nlink!=1:
                                    raise HTTPException(403,'Unsafe project export file')
                                count+=1
                                if count>10000:raise HTTPException(413,'Project export file limit exceeded')
                                entry=zipfile.ZipInfo(relative);entry.compress_type=zipfile.ZIP_DEFLATED
                                entry.external_attr=(pinned.st_mode&0xffff)<<16
                                with archive.open(entry,'w') as output:
                                    while True:
                                        chunk=os.read(child,min(65536,max(1,maximum-total+1)))
                                        if not chunk:break
                                        total+=len(chunk)
                                        if total>maximum:raise HTTPException(413,'Project export exceeds storage allowance')
                                        output.write(chunk)
                        finally:
                            if child is not None:os.close(child)
            walk(root_fd)
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise
