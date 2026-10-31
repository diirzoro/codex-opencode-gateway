#!/usr/bin/env python3
"""GitHub-commit-based, TEST-only full application rollout. No source backups."""
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
NATIVE="opencode-native-test.service"
REVISION=ROOT/".test-full-release-revision"
LOCK=Path("/home/tahir/.gateway-test-deploy.lock")
FRONT={"app.js","index.html","styles.css","dashboards.js","enhancements.js",
       "management.js","native-session-client.js","runtime-client.js"}
ALLOWED_ROOTS=("backend/app/","backend/alembic/versions/","assets/")
ALLOWED_EXACT={"backend/alembic.ini","backend/alembic/env.py","backend/alembic/script.py.mako"}
PROTECTED=("backend/app/services/preview_", "backend/app/routes/preview_", "backend/app/models/preview.py")
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
        if name in FRONT or name in ALLOWED_EXACT or (
            name.startswith("backend/app/") and name.endswith(".py") and not name.startswith(PROTECTED)
        ) or (name.startswith("backend/alembic/versions/") and name.endswith(".py")
        ) or name.startswith("assets/"):
            result.append(name)
    if not {"backend/app/main.py","backend/app/routes/admin.py","backend/alembic.ini","index.html"} <= set(result):
        raise RuntimeError("Incomplete source revision")
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
    if not service(GATEWAY) or not service(NATIVE):raise RuntimeError("Expected TEST services inactive")
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
    print("TARGET",target,"FILES_TOTAL",len(source),"CHANGES",len(changes),flush=True)
    for name,_,_ in changes:print("CHANGE",name,flush=True)
    if mode=="audit":return
    oldrev=active_revision()
    if mode=="rollback" and not oldrev:raise RuntimeError("No prior GitHub release marker; rollback unavailable")
    nativepid=run("systemctl","show","--value","-p","MainPID",NATIVE)
    for name,dest,data in changes:replace(dest,data);print("UPDATED",name,flush=True)
    try:
        # A TEST-only, root-owned migration gate is a mandatory deployment dependency.
        # It must validate current_database() and run Alembic against the exact TEST
        # service environment. Never infer DB identity from a filename or URL.
        # A missing or failed gate must block restart and release marking.
        if mode == "deploy":
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
        sudo_run("/usr/bin/systemctl","restart",GATEWAY)
        time.sleep(3)
        if not service(GATEWAY):raise RuntimeError("Gateway unhealthy after restart")
        if nativepid!=run("systemctl","show","--value","-p","MainPID",NATIVE):
            raise RuntimeError("OpenCode Native PID changed")
        replace(REVISION,(target+"\n").encode())
        print("FULL_TEST_RELEASE_SUCCESS",target,flush=True)
    except Exception:
        if oldrev:
            for name in files(oldrev):
                dest=check(name)
                data=subprocess.run(["git","-C",str(ROOT),"show",oldrev+":"+name],
                                    check=True,capture_output=True,timeout=45).stdout
                replace(dest,data)
            run("sudo","-n","/usr/bin/systemctl","restart",GATEWAY)
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
