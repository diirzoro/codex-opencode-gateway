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
# The TEST deployer runs existing Alembic migrations as the TEST service user.
# It never requires an independently installed root-owned migration command.
EXPECTED_TEST_DATABASE="opencode_gateway_test"
BACKUP_DIR=ROOT.parent/".opencode-gateway-test-db-backups"

def test_service_environment():
    """Use the running TEST service environment, not a possibly stale .env.

    This retains systemd EnvironmentFile overrides (including the TEST
    rollback environment) and never prints credentials to CI logs.
    """
    pid_raw=run("systemctl","show","--value","-p","MainPID",GATEWAY)
    if not pid_raw.isdigit() or int(pid_raw)<2:
        raise RuntimeError("TEST Gateway PID unavailable; migration not attempted")
    proc=Path("/proc")/pid_raw
    if proc.stat().st_uid!=os.geteuid():
        raise RuntimeError("TEST Gateway must run under deployment account")
    if proc.joinpath("cwd").resolve()!=ROOT/"backend":
        raise RuntimeError("TEST Gateway working directory mismatch")
    try:
        data=proc.joinpath("environ").read_bytes()
    except OSError:
        raise RuntimeError("Cannot read running TEST Gateway environment") from None
    variables={}
    for item in data.split(b"\x00"):
        if b"=" in item:
            key,value=item.split(b"=",1)
            variables[key.decode("utf-8")]=value.decode("utf-8")
    url=variables.get("DATABASE_URL","")
    if not url.startswith(("postgresql://","postgresql+psycopg://")):
        raise RuntimeError("Running TEST Gateway has no PostgreSQL DATABASE_URL")
    env=os.environ.copy()
    env.pop("DATABASE_URL",None)
    env.update(variables)
    return env

def test_backend_python():
    for binary in (ROOT/".venv/bin/python",ROOT/"backend/.venv/bin/python"):
        if binary.is_file() and os.access(binary,os.X_OK):
            return str(binary)
    raise RuntimeError("Existing TEST Gateway Python environment unavailable")

# Use the already installed SQLAlchemy and Alembic to check real DB identity.
# No URLs, passwords, or service environment values are printed or logged.
DATABASE_CHECK=r"""
import os,sys
from sqlalchemy import create_engine,text
from alembic.config import Config
from alembic.script import ScriptDirectory
engine=create_engine(os.environ["DATABASE_URL"],pool_pre_ping=True)
with engine.connect() as connection:
    name=connection.execute(text("SELECT current_database()")).scalar_one()
    if name!="opencode_gateway_test":
        raise SystemExit("Refusing migration: connected database is not TEST")
    if len(sys.argv)>1 and sys.argv[1]=="post":
        head=ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
        revisions=connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        if revisions!=[head]:
            raise SystemExit("TEST database is not at the expected Alembic head")
"""

def verified_test_database(python,env,*,post=False):
    run(python,"-c",DATABASE_CHECK,*(["post"] if post else []),
        cwd=ROOT/"backend",env=env,timeout=30)
    print("TEST_DB_MIGRATION_OK" if post else "TEST_DATABASE_CONFIRMED",flush=True)

def backup_test_database(env):
    """Private, validated custom-format PostgreSQL backup before migration."""
    url=env["DATABASE_URL"]
    if url.startswith("postgresql+psycopg://"):
        url="postgresql://"+url.split("://",1)[1]
    if BACKUP_DIR.is_symlink():
        raise RuntimeError("Unsafe TEST backup directory")
    BACKUP_DIR.mkdir(mode=0o700,parents=False,exist_ok=True)
    if BACKUP_DIR.stat().st_uid!=os.geteuid():
        raise RuntimeError("TEST backup directory owner mismatch")
    os.chmod(BACKUP_DIR,0o700)
    fd,name=tempfile.mkstemp(prefix="test-pre-migration-",suffix=".dump",dir=BACKUP_DIR)
    os.close(fd)
    dest=Path(name)
    # libpq environment variables must contain individual fields. A whole
    # SQLAlchemy URL in PGDATABASE is treated as a database *name* by pg_dump,
    # not reliably parsed as a connection URI. Keep passwords out of argv.
    from urllib.parse import urlsplit, unquote, parse_qs
    parts=urlsplit(url)
    if parts.scheme!="postgresql" or not parts.hostname or not parts.path.startswith("/"):
        raise RuntimeError("Invalid TEST PostgreSQL backup connection")
    database=unquote(parts.path[1:])
    if database!=EXPECTED_TEST_DATABASE:
        raise RuntimeError("Refusing backup of non-TEST database")
    backup_env=env.copy()
    for key in ("PGHOST","PGPORT","PGUSER","PGPASSWORD","PGDATABASE","PGSSLMODE","PGSSLROOTCERT"):
        backup_env.pop(key,None)
    backup_env["PGHOST"]=parts.hostname
    backup_env["PGPORT"]=str(parts.port or 5432)
    backup_env["PGDATABASE"]=database
    if parts.username is not None:backup_env["PGUSER"]=unquote(parts.username)
    if parts.password is not None:backup_env["PGPASSWORD"]=unquote(parts.password)
    options=parse_qs(parts.query,keep_blank_values=True)
    for parameter,variable in (("sslmode","PGSSLMODE"),("sslrootcert","PGSSLROOTCERT")):
        if parameter in options and len(options[parameter])==1:
            backup_env[variable]=options[parameter][0]
    try:
        run("pg_dump","--format=custom","--file",str(dest),timeout=180,env=backup_env)
        run("pg_restore","--list",str(dest),timeout=30,env=backup_env)
        if dest.stat().st_size<100:
            raise RuntimeError("TEST database backup was empty")
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    print("TEST_DB_BACKUP_VERIFIED",flush=True)
    return dest

def apply_test_migrations(python, environment):
    """Run only outstanding Alembic revisions; report a safe failure category."""
    try:
        run(python,"-m","alembic","-c","alembic.ini","upgrade","head",
            timeout=180,cwd=ROOT/"backend",env=environment)
    except subprocess.CalledProcessError as exc:
        # Never forward raw subprocess stderr: it can include DATABASE_URL,
        # credentials, or rows of private account data.
        detail=(exc.stderr or b"").decode("utf-8","replace")
        if "Existing normalized account duplicates require owner reconciliation" in detail:
            print("TEST_MIGRATION_FAILED: EXISTING_ACCOUNT_DUPLICATES; preserve users; reconcile TEST data before retry",flush=True)
        elif "permission denied" in detail.lower():
            print("TEST_MIGRATION_FAILED: DATABASE_PERMISSION_DENIED; check TEST role/schema ownership",flush=True)
        elif "duplicate column" in detail.lower() or "duplicate table" in detail.lower():
            print("TEST_MIGRATION_FAILED: EXISTING_SCHEMA_CONFLICT; inspect Alembic current and schema before retry",flush=True)
        elif "does not exist" in detail.lower() or "undefinedcolumn" in detail.lower():
            print("TEST_MIGRATION_FAILED: MISSING_SCHEMA_DEPENDENCY; inspect TEST migration history",flush=True)
        elif "can't locate revision" in detail.lower() or "can't locate revision identified by" in detail.lower():
            print("TEST_MIGRATION_FAILED: UNKNOWN_DATABASE_REVISION; inspect Alembic version table",flush=True)
        elif "ModuleNotFoundError" in detail or "ImportError" in detail:
            print("TEST_MIGRATION_FAILED: PYTHON_DEPENDENCY_ERROR; verify TEST virtualenv requirements",flush=True)
        else:
            print("TEST_MIGRATION_FAILED: UNCLASSIFIED_ALEMBIC_ERROR; inspect protected TEST diagnostics without exposing credentials",flush=True)
        raise RuntimeError("TEST Alembic upgrade failed; no source release marked") from None

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
    if mode=="deploy":
        # Check effective running TEST service before touching source or schema.
        environment=test_service_environment()
        python=test_backend_python()
        verified_test_database(python,environment)
        backup_test_database(environment)
    for name,dest,data in changes:replace(dest,data);print("UPDATED",name,flush=True)
    try:
        if mode=="deploy":
            apply_test_migrations(python,environment)
            verified_test_database(python,environment,post=True)
        run("sudo","-n","/usr/bin/systemctl","restart",GATEWAY)
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
    requirements()
    verified_commit(args.sha)
    if args.mode=="rollback" and args.sha==active_revision():
        raise RuntimeError("Rollback target must differ from deployed revision")
    with LOCK.open("a+") as fd:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        rollout(args.sha,args.mode)
if __name__=="__main__":main()
