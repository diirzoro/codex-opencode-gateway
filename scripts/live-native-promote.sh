#!/usr/bin/env bash
# VPS-only GitHub release: LIVE code/schema => TEST Native First architecture.
# Never overwrite production domain/SSL/DB credentials/workspaces or Native data.
set -euo pipefail
umask 077
[[ "${PROMOTE_NATIVE_LIVE_CONFIRM:-}" == promote ]] || { echo 'Requires PROMOTE_NATIVE_LIVE_CONFIRM=promote' >&2; exit 2; }
APP="$HOME/opencode-gateway"
RELEASE="$HOME/opencode-gateway-release"
BACKUPS="$HOME/opencode-backups"
test -f "$APP/.env" && test -f "$RELEASE/backend/app/main.py" && test -x "$APP/.venv/bin/python" || { echo 'LIVE/release files missing' >&2; exit 3; }
# Verify published frontend files really match the actual TEST working tree.
TEST_APP="$HOME/opencode-gateway-test"
test -d "$TEST_APP" || { echo 'TEST deployment root is missing' >&2; exit 5; }
for file in index.html app.js styles.css dashboards.js enhancements.js management.js native-session-client.js runtime-client.js; do
  cmp -s "$TEST_APP/$file" "$RELEASE/$file" || { echo "TEST frontend differs from GitHub source: $file" >&2; exit 6; }
done
# Also prevent promoting a backend that does not match the tested implementation.
for file in app/main.py app/config.py app/routes/native_sessions.py app/services/native_provider_accounts.py; do
  cmp -s "$TEST_APP/backend/$file" "$RELEASE/backend/$file" || { echo "TEST backend differs from GitHub source: $file" >&2; exit 7; }
done
ss -ltn | grep -F '127.0.0.2:4097' >/dev/null
ss -ltn | grep -F '127.0.0.1:18097' >/dev/null
ss -ltn | grep -F '127.0.0.1:18098' >/dev/null
# LIVE internal locations MUST be added to the existing production TLS server.
nginx_config="$(sudo -n nginx -T 2>/dev/null || nginx -T 2>/dev/null || true)"
[[ "$nginx_config" == *'location @native_session_live'* && "$nginx_config" == *'location @native_discovery_live'* ]] || { echo 'Install LIVE Nginx Native locations first' >&2; exit 4; }
unset nginx_config
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$BACKUPS/native-live-$stamp"
mkdir -p "$backup"
chmod 700 "$backup"
# Validate/backup original LIVE environment and PostgreSQL before editing.
"$APP/.venv/bin/python" - "$APP/.env" "$backup" <<'PY'
import os,sys,subprocess
from pathlib import Path
from sqlalchemy.engine import make_url
p=Path(sys.argv[1]);target=Path(sys.argv[2]);values={}
for line in p.read_text().splitlines():
    if not line.lstrip().startswith('#') and '=' in line:
        key,v=line.split('=',1);values[key.strip()]=v.strip().strip('"').strip("'")
url=make_url(values.get('DATABASE_URL',''))
assert url.get_backend_name()=='postgresql' and url.database=='opencode_gateway'
assert url.host in {'localhost','127.0.0.1','::1'}
assert values.get('PUBLIC_BASE_URL')=='https://opencode-gateway.codes'
assert values.get('APP_PORT')=='8000'
assert values.get('GITHUB_CALLBACK_URL','').startswith('https://opencode-gateway.codes/')
assert values.get('CREDENTIALS_ENCRYPTION_KEY'), 'LIVE encryption key missing'
(target/'live.env.before').write_bytes(p.read_bytes())
(target/'live.env.before').chmod(0o600)
pg_env=dict(os.environ,PGPASSWORD=url.password or '')
cmd=['pg_dump','-Fc','-h',url.host or '127.0.0.1','-p',str(url.port or 5432),
     '-U',url.username,'-d',url.database,'-f',str(target/'database.dump')]
subprocess.run(cmd,env=pg_env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,check=True,timeout=180)
print('LIVE environment and PostgreSQL backup completed')
PY
tar -czf "$backup/live-source-before.tgz" --exclude='./.venv' --exclude='./runtime' --exclude='./workspaces' -C "$APP" .
rsync -a --delete --exclude='.env' --exclude='.env.*' --exclude='.git/' \
  --exclude='.venv/' --exclude='runtime/' --exclude='workspaces/' \
  --exclude='logs/' --exclude='receipts/' --exclude='secrets/' \
  "$RELEASE/" "$APP/"
"$APP/.venv/bin/python" - "$APP/.env" <<'PY'
import os,sys,tempfile
from pathlib import Path
p=Path(sys.argv[1])
new={'OPENCODE_NATIVE_LIVE_ENABLED':'true','OPENCODE_NATIVE_TEST_ENABLED':'false',
     'OPENCODE_RUNTIME_MODE':'disabled','OPENCODE_BASE_URL':'http://127.0.0.2:4097',
     'OPENCODE_NATIVE_SERVICE':'opencode-native-test.service',
     'OPENCODE_NATIVE_MAINTENANCE_ENABLED':'false'}
lines=p.read_text().splitlines();out=[];seen=set()
for line in lines:
    key=line.split('=',1)[0].strip() if '=' in line and not line.lstrip().startswith('#') else ''
    if key in new:
        if key in seen:raise SystemExit('Duplicate native setting; manual review required')
        out.append(key+'='+new[key]);seen.add(key)
    else:out.append(line)
out.extend(key+'='+value for key,value in new.items() if key not in seen)
fd,name=tempfile.mkstemp(dir=p.parent,prefix='.live-env-')
try:
    with os.fdopen(fd,'w') as stream:
        stream.write('\n'.join(out)+'\n');stream.flush();os.fsync(stream.fileno())
    os.chmod(name,0o600);os.replace(name,p)
finally:
    if os.path.exists(name):os.unlink(name)
print('LIVE Native selectors updated; production domain, DB, secrets unchanged')
PY
"$APP/.venv/bin/python" -m pip install -q -r "$APP/backend/requirements.txt"
set -a
. "$APP/.env"
set +a
(cd "$APP/backend" && ../.venv/bin/python -m alembic upgrade head && ../.venv/bin/python -m alembic current)
sudo -n systemctl restart opencode-gateway.service
sudo -n systemctl is-active --quiet opencode-gateway.service
curl -fsS --retry 15 --retry-delay 2 --retry-connrefused http://127.0.0.1:8000/api/health
echo "LIVE_CODE_AND_SCHEMA_PROMOTED backup=$backup"
# Real Native prompts, file permissions, SSE and cross-user isolation still
# require authenticated browser acceptance; health alone is not enough.
