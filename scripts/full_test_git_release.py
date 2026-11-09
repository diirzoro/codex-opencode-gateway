#!/usr/bin/env python3
"""TEST-only file-diff deployment: restart Gateway only for backend changes."""
import argparse
import ast
import fcntl
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
import time

ROOT=Path("/home/tahir/opencode-gateway-test")
GATEWAY="opencode-gateway-test.service"
PI="pi-central.service"
REVISION=ROOT/".test-full-release-revision"
LOCK=Path("/home/tahir/.gateway-test-deploy.lock")
# Source-of-truth: deploy every tracked file from the selected GitHub commit.
# Only test suites, screenshots and generated test artifacts are excluded.
# No .env or runtime user data are tracked in this repository.
EXCLUDED_DIRS={"tests","test","__tests__","screenshots","screenshot",
    "test-results","playwright-report",".pytest_cache","__pycache__",
    ".venv","node_modules","workspaces"}
EXCLUDED_SUFFIXES=(".pyc",".pyo",".log")
RETIRED_FILES = (
    "backend/app/routes/agent.py",
    "backend/app/services/message_queue.py",
    "backend/app/services/opencode.py",
    "backend/app/services/opencode_catalog.py",
    "backend/app/services/account_provider_runtime.py",
    "backend/app/services/session_recovery.py",
    "backend/app/services/native_control_bridge.py",
    "backend/app/services/chat_attachments.py",
    "backend/app/services/account_provider_sync.py",
    "backend/app/services/native_provider_accounts.py",
    "backend/app/services/user_provider_credentials.py",
    "backend/app/services/providers.py",
    "backend/app/services/runtime_snapshot.py",
    "backend/app/services/archive_storage.py",
    # The failed TEST rollout left this uncommitted, unapplied sibling of 0034.
    # New project binding is 0035 after the pre-existing 0034 payment migration.
    "backend/alembic/versions/0034_project_native_session_binding.py",
    # Standalone OpenCode console was removed; the main TEST workspace stays.
    "assets/native-direct/app.js",
    "assets/native-direct/index.html",
)

def run(*argv,timeout=90,cwd=None,env=None):
    return subprocess.run(argv,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                          timeout=timeout,cwd=cwd,env=env).stdout.decode().strip()
# Optional existing GitHub production sudo secret, passed only through SSH stdin.
# It authorizes the same sudo commands as before; it never changes DB credentials.
SUDO_PASSWORD=None
def sudo_run(*argv,timeout=90):
    if SUDO_PASSWORD is None:
        return run("sudo","-n",*argv,timeout=timeout)
    result=subprocess.run(["sudo","-S","-p","",*argv],
        input=(SUDO_PASSWORD+"\n").encode(),check=True,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    return result.stdout.decode().strip()

def git(*argv):return run("git","-C",str(ROOT),*argv)
def files(revision):
    listing=git("ls-tree","-r","--name-only",revision)
    result=[]
    for name in listing.splitlines():
        parts=PurePosixPath(name).parts
        if any(part in EXCLUDED_DIRS for part in parts):continue
        if any(part.startswith("test_") or part.endswith("_test.py") for part in parts):continue
        if name.endswith(EXCLUDED_SUFFIXES):continue
        result.append(name)
    required={"backend/app/main.py","backend/app/routes/admin.py",
              "backend/alembic.ini","index.html",
              "ops/native-direct/nginx.conf","scripts/full_test_git_release.py"}
    if not required <= set(result):raise RuntimeError("Incomplete project source revision")
    return sorted(result)
def check(name):
    rel=PurePosixPath(name)
    if rel.is_absolute() or ".." in rel.parts or str(rel)!=name:raise RuntimeError("Unsafe path")
    dest=ROOT/name
    if dest.exists() and (not dest.is_file() or dest.stat().st_nlink!=1):raise RuntimeError("Unsafe file "+name)
    for parent in (dest,*dest.parents):
        if parent==ROOT.parent:break
        if parent.is_symlink():raise RuntimeError("Symlink in source path "+name)
    return dest
def replace(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    old=path.stat() if path.exists() else ROOT.stat()
    fd,tmp=tempfile.mkstemp(prefix=".release-",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as handle:handle.write(data);handle.flush();os.fsync(handle.fileno())
        os.chmod(tmp,stat.S_IMODE(old.st_mode) if path.exists() else 0o644)
        os.chown(tmp,old.st_uid,old.st_gid)
        os.replace(tmp,path)
    finally:
        if os.path.lexists(tmp):os.unlink(tmp)
def service(name):return run("systemctl","is-active",name)=="active"
def requirements():
    if os.geteuid()==0 or Path.cwd()!=ROOT:raise RuntimeError("Must run as tahir from TEST app")
    if not (ROOT/".env").is_file():raise RuntimeError("Existing TEST .env missing")
    if not (ROOT/".git").exists():raise RuntimeError("TEST Git checkout missing")
def verified_commit(sha):
    if not re.fullmatch(r"[a-f0-9]{40}",sha):raise RuntimeError("Invalid commit")
    if git("cat-file","-t",sha)!="commit":raise RuntimeError("Not a commit")
    run("git","-C",str(ROOT),"merge-base","--is-ancestor",sha,"origin/updates")
def active_revision():
    v=REVISION.read_text().strip() if REVISION.is_file() else ""
    return v if re.fullmatch(r"[a-f0-9]{40}",v) else None
def migration_runner():
    for tool in (ROOT/".venv/bin/alembic",ROOT/"backend/.venv/bin/alembic"):
        if tool.is_file() and os.access(tool,os.X_OK):return [str(tool)]
    return None
def db_env():
    # Extract only DATABASE_URL from the existing TEST .env with stdlib.
    # Do not rely on python-dotenv being installed in the VPS virtualenv.
    # Never print, rewrite, or save server credentials.
    import shlex
    env=os.environ.copy()
    path=ROOT/".env"
    for line in path.read_text(encoding="utf-8").splitlines():
        match=re.match(r"^\s*(?:export\s+)?DATABASE_URL\s*=\s*(.*)$",line)
        if not match:continue
        raw=match.group(1).strip()
        try:
            values=shlex.split(raw,comments=True,posix=True)
        except ValueError:
            raise RuntimeError("Invalid TEST DATABASE_URL entry; refusing deployment") from None
        if len(values)!=1:
            raise RuntimeError("TEST DATABASE_URL must be one quoted value; refusing deployment")
        env["DATABASE_URL"]=values[0]
        break
    if not env.get("DATABASE_URL","").startswith(("postgresql://","postgresql+psycopg://")):
        raise RuntimeError("TEST DATABASE_URL is missing or invalid; refusing deployment")
    return env
def migration_needed(target):
    # Explicitly limited to the known forward-only email config migration.
    return "backend/alembic/versions/0021_email_delivery_settings.py" in files(target)
def rollout(target,mode):
    source=files(target)
    changes=[]
    for name in source:
        dest=check(name)
        expected=subprocess.run(
            ["git","-C",str(ROOT),"show",target+":"+name],check=True,capture_output=True,timeout=45).stdout
        old=dest.read_bytes() if dest.is_file() else None
        if expected!=old:changes.append((name,dest,expected))
    # Deleted files are not returned by files(target). Remove only this
    # explicit legacy AI allowlist; never prune arbitrary untracked files.
    retired = [(name, check(name)) for name in RETIRED_FILES if name not in source]
    pending_retired = [(name, dest) for name, dest in retired if dest.exists()]
    print("TARGET",target,"FILES_TOTAL",len(source),"CHANGES",len(changes),
          "RETIRED_FILES_COUNT",len(pending_retired),flush=True)
    for name,_,_ in changes:print("CHANGE",name,flush=True)
    for name,_ in pending_retired:print("REMOVE_OBSOLETE_FILE",name,flush=True)
    if mode=="audit":return
    oldrev=active_revision()
    if mode=="rollback" and not oldrev:raise RuntimeError("No prior GitHub release marker; rollback unavailable")
    for name,dest,data in changes:replace(dest,data);print("UPDATED",name,flush=True)
    for name, dest in pending_retired:
        dest.unlink()
        print("DELETED_OBSOLETE_FILE",name,flush=True)
        # Remove only Python's compiled artifacts of this exact retired module.
        cached=dest.parent/"__pycache__"
        if cached.is_dir() and not cached.is_symlink():
            for bytecode in cached.glob(dest.stem+".*.pyc"):
                if bytecode.is_file() and not bytecode.is_symlink():
                    bytecode.unlink()
    try:
        # Only apply database migrations when the deployed migration files changed.
        migration_changes=any(name.startswith("backend/alembic/versions/") or name=="backend/alembic/env.py" for name,_,_ in changes)
        backend_changes=any(name.startswith("backend/") for name,_,_ in changes) or any(name.startswith("backend/") for name,_ in pending_retired)
        # The root-owned migration gate is used only for a database schema change.
        # It must validate current_database() and run Alembic against the exact TEST
        # service environment. Never infer DB identity from a filename or URL.
        # A missing or failed gate must block restart and release marking.
        if mode == "deploy" and migration_changes:
            gate = "/usr/local/sbin/opencode-gateway-test-migrate"
            try:
                sudo_run(gate,"upgrade",timeout=180)
            except subprocess.CalledProcessError as ex:
                # The root-owned migration gate may capture sensitive stderr.
                # Never print stderr/stdout or DATABASE_URL/credentials; only
                # emit stable diagnostic categories for secure troubleshooting.
                output=(ex.stderr or b"") + b"\n" + (ex.stdout or b"")
                msg=output.decode("utf-8",errors="replace").lower()
                indicators=(
                    ("password authentication failed","DB_AUTH_FAILED"),
                    ("authentication failed","DB_AUTH_FAILED"),
                    ("connection refused","DB_CONNECTION_REFUSED"),
                    ("could not connect","DB_CONNECTION_FAILED"),
                    ("permission denied for schema","DB_SCHEMA_CREATE_PERMISSION_DENIED"),
                    ("permission denied for database","DB_DATABASE_PERMISSION_DENIED"),
                    ("permission denied for relation","DB_RELATION_PERMISSION_DENIED"),
                    ("permission denied for table","DB_TABLE_PERMISSION_DENIED"),
                    ("permission denied for sequence","DB_SEQUENCE_PERMISSION_DENIED"),
                    ("permission denied","MIGRATION_PERMISSION_DENIED"),
                    ("insufficientprivilege","MIGRATION_PERMISSION_DENIED"),
                    ("multiple head revisions","ALEMBIC_MULTIPLE_HEADS"),
                    ("can't locate revision","ALEMBIC_UNKNOWN_REVISION"),
                    ("cannot locate revision","ALEMBIC_UNKNOWN_REVISION"),
                    ("database does not exist","DB_NOT_FOUND"),
                    ("already exists","MIGRATION_OBJECT_EXISTS"),
                    ("value too long","ALEMBIC_REVISION_TOO_LONG"),
                    ("wrong database","DB_IDENTITY_GUARD_FAILED"),
                    ("not authorized","MIGRATION_GATE_UNAUTHORIZED"),
                    ("not allowed","MIGRATION_GATE_REJECTED"),
                    ("refusing","MIGRATION_GATE_REJECTED"),
                )
                category=next((code for needle,code in indicators if needle in msg),
                              "MIGRATION_GATE_FAILED_UNCLASSIFIED")
                if category == "DB_TABLE_PERMISSION_DENIED":
                    # Output only a fixed allowlist of public schema table names,
                    # never arbitrary captured text or database connection values.
                    known_tables=("alembic_version","users","billing_methods",
                                  "payment_provider_profiles","payment_profile_publications")
                    for table in known_tables:
                        if re.search(r"permission denied for table\s+"+re.escape(table)+r"(?:\b|$)",msg):
                            category += "_" + table.upper()
                            break
                print("TEST_MIGRATION_GATE_FAILURE_CATEGORY",category,flush=True)
                raise RuntimeError("TEST database migration gate failed; "
                                   "deployment rolled back. Credentials are never logged.") from None
            print("TEST_MIGRATION_GATE_PASSED",flush=True)
        if backend_changes:
            sudo_run("/usr/bin/systemctl","restart",GATEWAY)
            print("GATEWAY_CODE_RELOADED",flush=True)
        else:
            print("GATEWAY_NOT_RESTARTED_NO_BACKEND_CHANGES",flush=True)
        replace(REVISION,(target+"\n").encode())
        print("FULL_TEST_RELEASE_SUCCESS",target,flush=True)
    except Exception:
        if oldrev:
            for name in files(oldrev):
                dest=check(name)
                data=subprocess.run(["git","-C",str(ROOT),"show",oldrev+":"+name],
                                    check=True,capture_output=True,timeout=45).stdout
                replace(dest,data)
            if backend_changes:
                sudo_run("/usr/bin/systemctl","restart",GATEWAY)
            print("GIT_ROLLBACK_APPLIED",oldrev,flush=True)
        else:
            print("FIRST_RELEASE_HAS_NO_RECORDED_PREVIOUS_GIT_COMMIT; MANUAL RECOVERY REQUIRED",flush=True)
        raise
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=("audit","deploy","rollback"))
    parser.add_argument("sha")
    args=parser.parse_args()
    global SUDO_PASSWORD
    if os.environ.get("TEST_SUDO_PASS_STDIN") == "1":
        # Read once from private stdin; never print, store or forward to DB.
        SUDO_PASSWORD=sys.stdin.readline().rstrip("\r\n")
        if not SUDO_PASSWORD:
            raise RuntimeError("Missing protected sudo authorization")
    requirements()
    verified_commit(args.sha)
    if args.mode=="rollback" and args.sha==active_revision():
        raise RuntimeError("Rollback target must differ from deployed revision")
    with LOCK.open("a+") as fd:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        rollout(args.sha,args.mode)
if __name__=="__main__":main()
