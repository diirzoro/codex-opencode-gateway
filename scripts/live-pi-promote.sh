#!/usr/bin/env bash
# LIVE Pi Gateway promotion, using existing services only.
# Called manually by the production GitHub Actions workflow.
set -euo pipefail
umask 077

# One-time LIVE activation, also reused by normal LIVE promotion below.
# Existing units/config only; no per-customer or additional service.
if [[ "${1:-}" == --activate-client-isolation ]]; then
  [[ $(id -u) -eq 0 ]] || { echo 'Run this activation with sudo'; exit 2; }
  /usr/bin/python3 - <<'PY_ACTIVATE'
import hashlib,json,os,re,secrets,shutil,stat,subprocess,tempfile,time
from pathlib import Path
from urllib.request import Request,urlopen

def run(*args):
    return subprocess.check_output(args,text=True,stderr=subprocess.PIPE).strip()
def require(condition,message):
    if not condition:raise SystemExit(message)
def env(path):
    values={}
    for line in path.read_text().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key,value=line.split('=',1)
            require(key.strip() not in values,'Duplicate setting in '+str(path))
            values[key.strip()]=value.strip().strip('"').strip("'")
    return values
def replace_env(text,changes):
    out=[];seen=set()
    for line in text.splitlines(keepends=True):
        key=line.split('=',1)[0].strip() if '=' in line and not line.lstrip().startswith('#') else ''
        if key in changes:out.append(key+'='+changes[key]+'\n');seen.add(key)
        else:out.append(line)
    for key,value in changes.items():
        if key not in seen:
            if out and not out[-1].endswith('\n'):out.append('\n')
            out.append(key+'='+value+'\n')
    return ''.join(out)
def atomic(path,data,mode=None):
    previous=path.stat();fd,tmp=tempfile.mkstemp(prefix='.pi-activate-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as output:output.write(data);output.flush();os.fsync(output.fileno())
        os.chmod(tmp,mode if mode is not None else stat.S_IMODE(previous.st_mode))
        os.chown(tmp,previous.st_uid,previous.st_gid);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

live=Path('/home/tahir/opencode-gateway')
require(int(run('systemctl','--version').split()[1])>=254,'systemd 254 or newer is required')
units=['pi-central.service','opencode-gateway.service']
for unit in units:require(run('systemctl','is-active',unit)=='active',unit+' is not active; no settings changed')
require((live/'.env').is_file() and not (live/'.env').is_symlink(),'Unsafe LIVE Gateway environment')
require(env(live/'.env').get('PUBLIC_BASE_URL')=='https://opencode-gateway.codes','Unexpected LIVE Gateway identity')
# Scope the existing shared Pi sandbox to LIVE. No TEST source comparison,
# environment rewrite, service configuration or Gateway restart is performed.
pid=int(run('systemctl','show','pi-central.service','-p','MainPID','--value'))
args=[part.decode() for part in (Path('/proc')/str(pid)/'cmdline').read_bytes().split(b'\0') if part]
sources=[Path(arg) for arg in args if Path(arg).name=='pi-central.mjs']
require(len(sources)==1,'Cannot identify the running Pi source')
source=sources[0]
if not source.is_absolute():source=(Path('/proc')/str(pid)/'cwd').resolve()/source
require(source.read_bytes()==(live/'integration/pi-central.mjs').read_bytes(),'Running Pi source does not match the deployed release')
helper=Path('/usr/local/libexec/pi-project-bwrap')
require(helper.is_file() and not helper.is_symlink() and helper.stat().st_uid==0 and
        not helper.stat().st_mode&0o6022 and helper.read_bytes()==Path('/usr/bin/bwrap').read_bytes(),
        'The previously approved bwrap helper is missing or changed')
require('pi-project-bwrap (unconfined)' in Path('/sys/kernel/security/apparmor/profiles').read_text(),
        'The previously approved AppArmor userns profile is not loaded')

paths={units[0]:Path('/etc/systemd/system/pi-central.service.d/99-security-containment.conf')}
for unit in units[1:]:paths[unit]=Path(run('systemctl','show',unit,'-p','FragmentPath','--value'))
for path in paths.values():
    require(str(path).startswith('/etc/systemd/system/') and path.is_file() and not path.is_symlink() and
            path.stat().st_uid==0 and not path.stat().st_mode&0o022,'Unsafe existing systemd configuration: '+str(path))
roots=[];identities={}
for unit in units:
    user=run('systemctl','show',unit,'-p','User','--value')
    require(user=='tahir','Unexpected service user; nothing changed')
    group=run('systemctl','show',unit,'-p','Group','--value') or user
    import pwd,grp
    identities[unit]=(pwd.getpwnam(user).pw_uid,grp.getgrnam(group).gr_gid)
    control=run('systemctl','show',unit,'-p','ControlGroup','--value')
    require(re.fullmatch(r'/system\.slice/[a-zA-Z0-9_.@-]+',control),'Unexpected cgroup layout')
    roots.append('/sys/fs/cgroup'+control+'/projects')

live_env=env(live/'.env')
token=live_env.get('PI_GATEWAY_INTERNAL_TOKEN','')
if not re.fullmatch(r'[A-Za-z0-9_-]{32,256}',token):token=secrets.token_urlsafe(48)
workspace_root=live_env.get('WORKSPACE_ROOT','/var/lib/opencode-workspaces')
require(workspace_root=='/var/lib/opencode-workspaces','Unexpected LIVE workspace root; files preserved')
# Both existing services use tahir, but their primary groups differ. Grant
# that already approved UID read/execute on the root-owned helper itself;
# never add www-data membership or make the userns helper world executable.
import errno,struct
helper_fd=os.open(helper,os.O_RDONLY|os.O_NOFOLLOW)
try:
    info=os.fstat(helper_fd)
    try:
        raw=os.getxattr(helper_fd,'system.posix_acl_access')
        require(len(raw)>=4 and struct.unpack('<I',raw[:4])[0]==2 and (len(raw)-4)%8==0,
                'Unsupported helper ACL; nothing changed')
        entries=[list(struct.unpack('<HHI',raw[i:i+8])) for i in range(4,len(raw),8)]
    except OSError as error:
        if error.errno!=errno.ENODATA:raise
        entries=[[1,(info.st_mode>>6)&7,0xffffffff],
                 [4,(info.st_mode>>3)&7,0xffffffff],[32,info.st_mode&7,0xffffffff]]
    for uid in sorted({value[0] for value in identities.values()}):
        entry=next((row for row in entries if row[0]==2 and row[2]==uid),None)
        if entry is None:entries.append([2,5,uid])
        else:entry[1]|=5
    mask=next((row for row in entries if row[0]==16),None)
    if mask is None:entries.append([16,((info.st_mode>>3)&7)|5,0xffffffff])
    else:mask[1]|=5
    entries.sort(key=lambda row:(row[0],row[2]))
    updated=struct.pack('<I',2)+b''.join(struct.pack('<HHI',*row) for row in entries)
    if 'raw' not in locals() or raw!=updated:
        os.setxattr(helper_fd,'system.posix_acl_access',updated)
        print('LIVE_GIT_HELPER_ACCESS_READY=1; existing service UID only; no group expansion.')
finally:os.close(helper_fd)
def running_environment(unit):
    pid=int(run('systemctl','show',unit,'-p','MainPID','--value'))
    return dict(item.split(b'=',1) for item in (Path('/proc')/str(pid)/'environ').read_bytes().split(b'\0') if b'=' in item)
def activation_is_current():
    try:
        for i,unit in enumerate(units):
            actual=running_environment(unit)
            wanted={'PI_PROJECT_SANDBOX':'1','PI_SANDBOX_CGROUP_ROOT':roots[i]}
            if i==0:wanted.update(PI_PROJECT_SANDBOX_ORIGIN='https://opencode-gateway.codes',
                                  PI_GATEWAY_LIVE_TOKEN=token,PI_GATEWAY_LIVE_ROOT=workspace_root)
            else:wanted['PI_GATEWAY_INTERNAL_TOKEN']=token
            if not all(actual.get(k.encode())==v.encode() for k,v in wanted.items()):return False
            if not {'cpu','memory','pids'}.issubset(set((Path(roots[i])/'cgroup.subtree_control').read_text().split())):return False
        return True
    except (OSError,ValueError,subprocess.SubprocessError):return False
if activation_is_current():
    print('CLIENT_ISOLATION_ALREADY_ACTIVE=1; LIVE settings retained; no extra restart or tool probe.')
    raise SystemExit(0)
changes={}
p=live/'.env'
changes[p]=replace_env(p.read_text(),{'PI_PROJECT_SANDBOX':'1',
    'PI_GATEWAY_INTERNAL_TOKEN':token,'PI_SANDBOX_CGROUP_ROOT':roots[1]}).encode()
for i,unit in enumerate(units):
    p=paths[unit];uid,gid=identities[unit];parent=str(Path(roots[i]).parent)
    # Each service gets its own delegated subtree. Moving backend Git into
    # Pi's subtree would fail cgroup common-ancestor permission checks.
    setup=('from pathlib import Path;import os;'
      f'r=Path({parent!r});p=r/"projects";'
      '(r/"cgroup.subtree_control").write_text("+cpu +memory +pids");p.mkdir(exist_ok=True);'
      f'(p/"memory.max").write_text("{1536*1024*1024 if i==0 else 512*1024*1024}");'
      '(p/"memory.swap.max").write_text("0");(p/"pids.max").write_text("256");'
      '(p/"cpu.max").write_text("100000 100000");(p/"cpu.weight").write_text("20");'
      '(p/"cgroup.subtree_control").write_text("+cpu +memory +pids");'
      f'[os.chown(x,{uid},{gid}) for x in [p,p/"cgroup.procs",p/"cgroup.subtree_control"]]')
    extra='\n[Service]\nDelegate=cpu memory pids\nDelegateSubgroup=control\nProtectControlGroups=no\n'
    extra+='ExecStartPost=+/usr/bin/python3 -c '+json.dumps(setup)+'\n'
    if i==0:
        values={'PI_PROJECT_SANDBOX':'1','PI_PROJECT_SANDBOX_ORIGIN':'https://opencode-gateway.codes',
                'PI_GATEWAY_LIVE_TOKEN':token,
                'PI_GATEWAY_LIVE_ROOT':workspace_root,'PI_SANDBOX_CGROUP_ROOT':roots[0]}
        extra+=''.join('Environment='+json.dumps(key+'='+value)+'\n' for key,value in values.items())
    original=p.read_text()
    require('# PI_CLIENT_ISOLATION_MANAGED' not in original,'Activation was already configured; no settings changed')
    changes[p]=(original+'\n# PI_CLIENT_ISOLATION_MANAGED\n'+extra).encode()

backup=Path('/var/backups/pi-client-isolation')/(time.strftime('%Y%m%dT%H%M%S')+'-'+secrets.token_hex(3))
backup.mkdir(parents=True,mode=0o700)
originals={p:(p.read_bytes(),stat.S_IMODE(p.stat().st_mode)) for p in changes}
for index,(path,(data,mode)) in enumerate(originals.items()):
    destination=backup/str(index);destination.write_bytes(data);destination.chmod(0o600)
(backup/'paths.json').write_text(json.dumps([str(p) for p in originals]));(backup/'paths.json').chmod(0o600)
try:
    for path,data in changes.items():atomic(path,data,0o600 if path in paths.values() else None)
    run('systemctl','daemon-reload')
    for unit in units:
        require(run('systemctl','show',unit,'-p','DelegateSubgroup','--value')=='control','Service delegation was overridden')
    run('systemctl','restart',*units)
    for _ in range(20):
        try:
            for port,host in [(8000,'opencode-gateway.codes')]:
                with urlopen(Request(f'http://127.0.0.1:{port}/api/health',headers={'Host':host}),timeout=2) as response:
                    if response.status!=200:raise OSError('Gateway not ready')
            break
        except OSError:time.sleep(1)
    else:raise RuntimeError('Gateway startup did not become ready')
    for i,unit in enumerate(units):
        require(run('systemctl','is-active',unit)=='active','Service did not remain active')
        require({'cpu','memory','pids'}.issubset(set((Path(roots[i])/'cgroup.subtree_control').read_text().split())),
                'Delegated resource controllers were not initialized')
    for i,unit in enumerate(units):
        pid=int(run('systemctl','show',unit,'-p','MainPID','--value'))
        actual=running_environment(unit)
        expected={'PI_PROJECT_SANDBOX':'1','PI_SANDBOX_CGROUP_ROOT':roots[i]}
        if i==0:expected.update(PI_GATEWAY_LIVE_TOKEN=token,PI_GATEWAY_LIVE_ROOT=workspace_root,
                               PI_PROJECT_SANDBOX_ORIGIN='https://opencode-gateway.codes')
        else:expected['PI_GATEWAY_INTERNAL_TOKEN']=token
        require(all(actual.get(key.encode())==value.encode() for key,value in expected.items()),
                unit+' did not load the security configuration; values hidden')
    # One initial acceptance check with the installed native SDK and disposable
    # project canaries. Join Pi's mount namespace and delegated control cgroup
    # before dropping UID/capabilities; otherwise a cgroup migration from the
    # deployer's unrelated service would not represent a real Pi worker.
    pi_pid=int(run('systemctl','show','pi-central.service','-p','MainPID','--value'))
    node=str((Path('/proc')/str(pi_pid)/'exe').resolve())
    uid,gid=identities['pi-central.service']
    control_procs=str(Path(roots[0]).parent/'control'/'cgroup.procs')
    bootstrap=('import os,sys;'
      'f=os.open(sys.argv[1],os.O_WRONLY);os.write(f,b"0");os.close(f);'
      'os.execve("/usr/bin/setpriv",["setpriv","--reuid='+str(uid)+'","--regid='+str(gid)+'",'
      '"--clear-groups","--no-new-privs","--bounding-set=-all","--",*sys.argv[2:]],os.environ)')
    probe_env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':'/home/tahir','LANG':'C.UTF-8',
               'PI_SANDBOX_CGROUP_ROOT':roots[0]}
    probe=subprocess.run(['/usr/bin/nsenter','-t',str(pi_pid),'-m','--','/usr/bin/python3','-c',
                          bootstrap,control_procs,node,str(source),'--isolation-probe'],
                         env=probe_env,capture_output=True,text=True,timeout=60)
    try:proof=json.loads((probe.stdout if probe.returncode==0 else probe.stderr).strip().splitlines()[-1])
    except (ValueError,IndexError):proof={}
    if probe.returncode!=0 or proof.get('probe')!='PASS':
        diagnostic=backup/'native-worker-proof.json'
        diagnostic.write_text(json.dumps(proof));diagnostic.chmod(0o600)
        print('LIVE_NATIVE_TOOL_BOUNDARY_FAIL '+json.dumps(proof))
    require(probe.returncode==0 and proof.get('probe')=='PASS',
            'Native LIVE project worker acceptance failed; configuration will be restored')
    print('LIVE_NATIVE_TOOL_BOUNDARY=PASS; disposable canaries removed; no model/payment call.')
    print('CLIENT_ISOLATION_ACTIVATED=1; existing services active; global configuration persistent.')
    print('LIVE-origin tool sandbox; TEST configuration unchanged. No disk-quota, boot, workflow, payment or project-file changes. Private rollback backup: '+str(backup))
except BaseException:
    for path,(data,mode) in originals.items():atomic(path,data,mode)
    subprocess.run(['systemctl','daemon-reload'],check=False)
    subprocess.run(['systemctl','restart',*units],check=False)
    print('Activation did not complete; previous configuration restored. Backup: '+str(backup))
    raise
PY_ACTIVATE
  exit $?
fi

APP=/home/tahir/opencode-gateway
RELEASE=/home/tahir/opencode-gateway-release
SNIPPET=/etc/nginx/snippets/opencode-native-live.conf
PI_SOCKET=/run/pi-central/pi.sock

[[ "$LIVE_SUDO_PASS_STDIN" == "1" ]] || { echo "Protected sudo stdin required" >&2; exit 2; }
[[ "$LIVE_PI_SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "Invalid release revision" >&2; exit 2; }
sudo_password=
IFS= read -r sudo_password || { echo "Missing production sudo authorization" >&2; exit 2; }
[[ -n "$sudo_password" ]] || { echo "Empty production sudo authorization" >&2; exit 2; }
sudo_operator() {
  printf '%s\n' "$sudo_password" | sudo -S -p '' "$@"
}

# Fail before touching LIVE if the source, existing service, or Pi socket is missing.
[[ -d "$APP" && ! -L "$APP" && -d "$RELEASE" && ! -L "$RELEASE" ]] ||
  { echo "LIVE/release root missing or unsafe" >&2; exit 3; }
[[ -f "$APP/.env" && -x "$APP/.venv/bin/python" && -f "$RELEASE/backend/app/main.py" &&
   -f "$RELEASE/integration/pi-central.mjs" &&
   -f "$RELEASE/ops/native-direct/nginx-live.conf" &&
   -f "$RELEASE/backend/requirements.txt" ]] ||
  { echo "Incomplete Pi release or LIVE environment" >&2; exit 3; }
[[ -S "$PI_SOCKET" ]] || { echo "The existing Pi Central Unix socket is unavailable" >&2; exit 4; }
[[ -f "$SNIPPET" && ! -L "$SNIPPET" ]] ||
  { echo "Existing LIVE Nginx native snippet not found; nothing deployed" >&2; exit 4; }
sudo_operator /usr/bin/systemctl is-active --quiet pi-central.service ||
  { echo "Shared Pi Central service is not active" >&2; exit 4; }
sudo_operator /usr/bin/systemctl is-active --quiet opencode-gateway.service ||
  { echo "LIVE Gateway is not active" >&2; exit 4; }

# Resolve the file actually executed by the existing shared Pi service. LIVE
# source synchronization alone does not update a separate /home/tahir/pi-test
# runtime. Do not guess a checkout, change ExecStart or replace the SDK.
pi_pid="$(sudo_operator /usr/bin/systemctl show pi-central.service -p MainPID --value)"
pi_file="$("$APP/.venv/bin/python" - "$pi_pid" <<'PY'
import sys
from pathlib import Path
pid = int(sys.argv[1])
assert pid > 0, 'Pi process is unavailable'
proc = Path('/proc') / str(pid)
args = (proc / 'cmdline').read_bytes().split(b'\0')
files = [Path(arg.decode()) for arg in args if arg and Path(arg.decode()).name == 'pi-central.mjs']
assert len(files) == 1, 'Cannot identify the existing Pi entry point'
p = files[0]
if not p.is_absolute():
    p = (proc / 'cwd').resolve() / p
p = p.resolve(strict=True)
assert p.is_file() and str(p).startswith('/home/tahir/'), 'Unexpected Pi entry point'
assert '\n' not in str(p), 'Invalid Pi entry point'
print(p)
PY
)"
pi_update_needed=0
cmp -s "$pi_file" "$RELEASE/integration/pi-central.mjs" || pi_update_needed=1
read -r pi_uid pi_gid pi_mode < <(stat -c '%u %g %a' "$pi_file")
pi_backup=
pi_source_touched=0
pi_restart_attempted=0
rollback=
install_pi_file() {
  local source="$1" staged
  staged="$(sudo_operator /usr/bin/mktemp "${pi_file}.release.XXXXXX")" || return 1
  if ! sudo_operator /usr/bin/install -o "$pi_uid" -g "$pi_gid" -m "$pi_mode" "$source" "$staged" ||
     ! sudo_operator /usr/bin/mv -fT -- "$staged" "$pi_file"; then
    sudo_operator /usr/bin/rm -f -- "$staged" || true
    return 1
  fi
}
finish_release() {
  local result=$?
  trap - EXIT
  if [[ "$result" != 0 && "$pi_source_touched" == 1 && -n "$pi_backup" ]]; then
    echo "Release failed; restoring the previous shared Pi entry point" >&2
    if install_pi_file "$pi_backup"; then
      if [[ "$pi_restart_attempted" == 1 ]]; then
        sudo_operator /usr/bin/systemctl restart pi-central.service ||
          echo "Pi recovery requires operator attention; private backup retained" >&2
      fi
    else
      echo "Pi source recovery requires operator attention; private backup retained" >&2
    fi
  fi
  [[ -z "$rollback" ]] || rm -f -- "$rollback"
  exit "$result"
}
trap finish_release EXIT

# Confirm the LIVE host actually loads the existing production-only snippet.
nginx_before="$(sudo_operator /usr/sbin/nginx -T 2>/dev/null)"
if ! grep -Fq "configuration file $SNIPPET:" <<< "$nginx_before"; then
  echo "LIVE virtual host does not include the expected Nginx snippet" >&2
  exit 4
fi
unset nginx_before

# Validate production identity without printing database credentials or secrets.
"$APP/.venv/bin/python" - "$APP/.env" <<'PY'
import sys
from pathlib import Path
from sqlalchemy.engine import make_url
env = {}
for row in Path(sys.argv[1]).read_text().splitlines():
    row = row.strip()
    if not row or row.startswith("#") or "=" not in row:
        continue
    key, value = row.split("=", 1)
    env[key.strip()] = value.strip().strip('"').strip("'")
url = make_url(env.get("DATABASE_URL", ""))
assert url.get_backend_name() == "postgresql" and url.database == "opencode_gateway", "Unexpected LIVE database"
assert env.get("PUBLIC_BASE_URL") == "https://opencode-gateway.codes", "Unexpected LIVE origin"
assert env.get("APP_PORT") == "8000", "Unexpected LIVE Gateway port"
assert env.get("CREDENTIALS_ENCRYPTION_KEY"), "LIVE credential encryption key missing"
assert env.get("GITHUB_CALLBACK_URL", "https://opencode-gateway.codes/api/github/callback") == "https://opencode-gateway.codes/api/github/callback", "Unexpected LIVE GitHub callback"
print("LIVE origin/port/database/credential configuration verified (secrets hidden)")
PY

# Back up the existing LIVE PostgreSQL database BEFORE any release files,
# dependencies, or migrations are changed. Never include the dump in rsync.
(
  set -a
  . "$APP/.env"
  set +a
  command -v pg_dump >/dev/null || {
    echo "pg_dump unavailable; refusing to migrate LIVE without a backup" >&2
    exit 5
  }
  backup_dir="$APP/backups"
  install -d -m 700 "$backup_dir"
  backup_path="$backup_dir/pre-live-$(date -u +%Y%m%dT%H%M%SZ)-${LIVE_PI_SOURCE_SHA:0:12}.dump"
  pg_url="${DATABASE_URL/postgresql+psycopg:\/\//postgresql:\/\/}"
  pg_dump --format=custom --file="$backup_path" "$pg_url"
  [[ -s "$backup_path" ]] || {
    echo "LIVE PostgreSQL backup is empty; refusing to deploy" >&2
    exit 5
  }
  chmod 600 "$backup_path"
  sha256sum "$backup_path" > "$backup_path.sha256"
  chmod 600 "$backup_path.sha256"
  echo "LIVE_PRE_DEPLOY_DATABASE_BACKUP_OK (private dump retained under $backup_dir)"
)

if [[ "$pi_update_needed" == 1 ]]; then
  pi_backup="$(mktemp "$APP/backups/pi-central-before-${LIVE_PI_SOURCE_SHA:0:12}.XXXXXX")"
  cat "$pi_file" > "$pi_backup"
  chmod 600 "$pi_backup"
  # rsync below may itself replace this file when ExecStart points into APP.
  # Retain recovery before that happens, as well as for a separate Pi runtime.
  pi_source_touched=1
fi

# Replace the entire legacy OpenCode source, not just changed files.
# Preserve only production environment, databases, project/runtime state, and keys.
rsync -a --delete \
  --exclude='.git/' --exclude='.github/' \
  --exclude='.env' --exclude='.env.*' --exclude='.venv/' \
  --exclude='runtime/' --exclude='workspaces/' --exclude='state/' \
  --exclude='sessions/' --exclude='uploads/' --exclude='secrets/' \
  --exclude='receipts/' --exclude='logs/' --exclude='backups/' \
  --exclude='releases/' --exclude='node_modules/' \
  --exclude='*.pem' --exclude='*.key' --exclude='*.p12' --exclude='*.pfx' \
  --exclude='*.db' --exclude='*.sqlite*' \
  "$RELEASE/" "$APP/"
echo "LIVE source synchronized from master; legacy source removed; state and secrets preserved"

# Switch only native-mode selectors. Payment, email, database and other LIVE
# configuration values are retained byte-for-byte in their existing lines.
"$APP/.venv/bin/python" - "$APP/.env" <<'PY'
import os, stat, sys, tempfile
from pathlib import Path
p = Path(sys.argv[1])
changes = {
    "OPENCODE_NATIVE_LIVE_ENABLED": "true",
    "OPENCODE_NATIVE_TEST_ENABLED": "false",
    "OPENCODE_NATIVE_LOCAL_ENABLED": "false",
    "OPENCODE_RUNTIME_MODE": "disabled",
}
original = p.read_text()
lines = original.splitlines(keepends=True)
seen = set()
out = []
for line in lines:
    raw = line.lstrip()
    key = line.split("=", 1)[0].strip() if "=" in line and not raw.startswith("#") else ""
    if key not in changes:
        out.append(line)
        continue
    if key in seen:
        raise SystemExit("Duplicate native mode flag in LIVE environment: " + key)
    seen.add(key)
    out.append(key + "=" + changes[key] + "\n")
for key, value in changes.items():
    if key not in seen:
        if out and not out[-1].endswith("\n"):
            out.append("\n")
        out.append(key + "=" + value + "\n")
new = "".join(out)
if new != original:
    mode = stat.S_IMODE(p.stat().st_mode)
    fd, tmp = tempfile.mkstemp(prefix=".pi-live-env-", dir=p.parent)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(new)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
print("LIVE Pi native selectors set; payment, email and database values preserved")
PY

# Gateway is the existing Python administrative backend; it never processes Pi
# prompts. Shared Pi is updated below only when its actual source differs.
"$APP/.venv/bin/python" -m pip install --disable-pip-version-check -q -r "$APP/backend/requirements.txt"
(
  set -a
  . "$APP/.env"
  set +a
  cd "$APP/backend"
  ../.venv/bin/python -m alembic upgrade head
  ../.venv/bin/python -m alembic current
  # Verify that Pi's three dedicated tables are truly present in LIVE,
  # not merely that the historical 0036 Alembic head was applied.
  ../.venv/bin/python - <<'PY'
from sqlalchemy import inspect, text
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.database import engine
expected_revision = ScriptDirectory.from_config(Config('alembic.ini')).get_current_head()
required = {"ai_provider_catalog", "ai_provider_models", "ai_user_connections",
            "admin_finance_notes", "admin_report_presets"}
with engine.connect() as connection:
    database = connection.execute(text("SELECT current_database()")).scalar_one()
    revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    tables = set(inspect(connection).get_table_names())
    subscription_columns = {c["name"] for c in inspect(connection).get_columns("subscriptions")}
    profile_columns = {c["name"] for c in inspect(connection).get_columns("payment_provider_profiles")}
if database != "opencode_gateway" or revision != expected_revision:
    raise SystemExit("LIVE Pi database or Alembic revision mismatch")
if not required.issubset(tables):
    raise SystemExit("LIVE Pi catalog tables missing after migration")
if "admin_suspended_at" not in subscription_columns:
    raise SystemExit("LIVE admin subscription suspension column missing")
if 'admin_suspended' not in profile_columns:
    raise SystemExit('LIVE payment provider suspension column missing')
print(f"LIVE_PI_DATABASE_READY revision={revision} tables=5")
PY
)
sudo_operator /usr/bin/systemctl restart opencode-gateway.service
sudo_operator /usr/bin/systemctl is-active --quiet opencode-gateway.service
# systemctl restart returns when the service is spawned, not when Uvicorn
# has finished imports/startup and bound port 8000. Retry connection refusals
# within a bounded window. A persistent failure stops before Nginx changes.
if ! curl -fsS --max-time 10 --connect-timeout 3 --retry 15 \
  --retry-delay 2 --retry-connrefused \
  --header 'Host: opencode-gateway.codes' \
  http://127.0.0.1:8000/api/health >/dev/null; then
  echo 'LIVE Gateway did not become healthy on 127.0.0.1:8000; Nginx left unchanged' >&2
  sudo_operator /usr/bin/systemctl show opencode-gateway.service \
    -p ActiveState -p SubState -p Result -p ExecMainStatus --no-pager >&2 || true
  exit 8
fi

# Replace only the existing LIVE Nginx snippet. Keep a temporary copy only
# long enough to restore it if validation or reload fails.
rollback="$(mktemp)"
chmod 600 "$rollback"
sudo_operator /usr/bin/cat "$SNIPPET" > "$rollback"
restore_nginx() {
  sudo_operator /usr/bin/install -m 644 "$rollback" "$SNIPPET"
  sudo_operator /usr/sbin/nginx -t >/dev/null
  sudo_operator /usr/bin/systemctl reload nginx
}
sudo_operator /usr/bin/install -m 644 "$RELEASE/ops/native-direct/nginx-live.conf" "$SNIPPET"
if ! sudo_operator /usr/sbin/nginx -t; then
  restore_nginx
  echo "New LIVE Nginx configuration rejected; original restored" >&2
  exit 6
fi
if ! sudo_operator /usr/bin/systemctl reload nginx; then
  restore_nginx
  echo "LIVE Nginx reload failed; original restored" >&2
  exit 7
fi

# Activate the same source in the existing shared Pi runtime. No service unit,
# SDK package, environment flag, workflow, payment setting or project is edited.
if [[ "$pi_update_needed" == 1 ]]; then
  install_pi_file "$RELEASE/integration/pi-central.mjs"
  pi_restart_attempted=1
  sudo_operator /usr/bin/systemctl restart pi-central.service
  sudo_operator /usr/bin/systemctl is-active --quiet pi-central.service
  # A missing Unix socket during startup is ENOENT, which curl's TCP
  # --retry-connrefused does not retry. Allow the existing service to bind it.
  pi_ready=0
  for attempt in {1..15}; do
    if curl -fsS --max-time 3 --unix-socket "$PI_SOCKET" \
      http://localhost/health >/dev/null 2>&1; then
      pi_ready=1
      break
    fi
    sleep 1
  done
  [[ "$pi_ready" == 1 ]] || { echo "Pi did not finish startup; restoring its previous source" >&2; exit 9; }
fi
cmp -s "$pi_file" "$RELEASE/integration/pi-central.mjs" || {
  echo "The shared Pi runtime does not match the deployed release" >&2
  exit 9
}
echo "SHARED_PI_SOURCE_DEPLOYED revision=$LIVE_PI_SOURCE_SHA updated=$pi_update_needed"

# One global activation for present/future LIVE customers. The action returns
# immediately when the effective configuration is already active. TEST
# Gateway/source is neither inspected nor modified by this action.
sudo_operator /usr/bin/bash "$APP/scripts/live-pi-promote.sh" --activate-client-isolation

unset sudo_password
echo "LIVE_PI_GATEWAY_DEPLOYED revision=$LIVE_PI_SOURCE_SHA gateway=8000 db=opencode_gateway shared_pi=release-matched"
