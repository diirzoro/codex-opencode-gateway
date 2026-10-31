#!/usr/bin/env bash
# VPS-only GitHub release: LIVE code/schema => TEST Native First architecture.
# Never overwrite production domain/SSL/DB credentials/workspaces or Native data.
set -euo pipefail
umask 077
[[ "${PROMOTE_NATIVE_LIVE_CONFIRM:-}" == promote ]] || { echo 'Requires PROMOTE_NATIVE_LIVE_CONFIRM=promote' >&2; exit 2; }
# Password is received once from GitHub's protected secret over encrypted SSH stdin.
# No plaintext credentials are stored on disk, logged or passed as CLI arguments.
sudo_password=''
if [[ "${LIVE_SUDO_PASS_STDIN:-0}" == 1 ]]; then
  IFS= read -r sudo_password || { echo 'Missing protected sudo authorization' >&2; exit 9; }
  [[ -n "$sudo_password" ]] || { echo 'Empty protected sudo authorization' >&2; exit 9; }
fi
sudo_operator() {
  if [[ -n "$sudo_password" ]]; then
    printf '%s\n' "$sudo_password" | sudo -S -p '' "$@"
  else
    sudo -n "$@"
  fi
}
APP="$HOME/opencode-gateway"
RELEASE="$HOME/opencode-gateway-release"
# Backups and cleanup are intentionally deferred until LIVE acceptance.
test -f "$APP/.env" && test -f "$RELEASE/backend/app/main.py" && test -x "$APP/.venv/bin/python" || { echo 'LIVE/release files missing' >&2; exit 3; }
# Verify published frontend files really match the actual TEST working tree.
TEST_APP="$HOME/opencode-gateway-test"
test -d "$TEST_APP" || { echo 'TEST deployment root is missing' >&2; exit 5; }
for file in index.html app.js styles.css dashboards.js enhancements.js management.js native-session-client.js runtime-client.js; do
  cmp -s "$TEST_APP/$file" "$RELEASE/$file" || { echo "TEST frontend differs from GitHub source: $file" >&2; exit 6; }
done
# Also prevent promoting a backend that does not match the tested implementation.
for file in app/services/native_provider_accounts.py app/services/policy.py app/models/workspace.py; do
  cmp -s "$TEST_APP/backend/$file" "$RELEASE/backend/$file" || { echo "TEST backend differs from GitHub source: $file" >&2; exit 7; }
done
ss -ltn | grep -F '127.0.0.2:4097' >/dev/null
ss -ltn | grep -F '127.0.0.1:18097' >/dev/null
ss -ltn | grep -F '127.0.0.1:18098' >/dev/null
# Inspect the actual active Nginx configuration with operator authorization.
# Avoid guessing the name of the VPS Nginx sites-enabled file.
nginx_config="$(sudo_operator /usr/sbin/nginx -T 2>/dev/null || true)"
[[ "$nginx_config" == *'location @native_session_live'* &&
   "$nginx_config" == *'location @native_discovery_live'* ]] ||
   { echo 'LIVE Nginx Native locations missing or cannot inspect with supplied authorization' >&2; exit 4; }
unset nginx_config
# Confirm permission before editing any source, environment, or schema.
if ! sudo_operator -l /usr/bin/systemctl restart opencode-gateway.service >/dev/null 2>&1; then
  echo 'Operator authorization cannot restart opencode-gateway.service; deployment stopped before modifications' >&2
  exit 8
fi
echo 'LIVE Nginx routes and Gateway-only restart authorization verified'
# Validate LIVE configuration only. Do not create backups, delete files,
# replace the database, or change production callback/domain values.
"$APP/.venv/bin/python" - "$APP/.env" <<'PY'
import sys
from pathlib import Path
from sqlalchemy.engine import make_url
p=Path(sys.argv[1]); values={}
for line in p.read_text().splitlines():
    if not line.lstrip().startswith('#') and '=' in line:
        key,v=line.split('=',1);values[key.strip()]=v.strip().strip('"').strip("'")
url=make_url(values.get('DATABASE_URL',''))
assert url.get_backend_name()=='postgresql' and url.database=='opencode_gateway', 'Wrong production DB'
assert url.host in {'localhost','127.0.0.1','::1'}, 'Nonlocal production DB'
assert values.get('PUBLIC_BASE_URL')=='https://opencode-gateway.codes', 'Wrong LIVE domain'
assert values.get('APP_PORT')=='8000', 'Wrong LIVE port'
assert values.get('GITHUB_CALLBACK_URL')=='https://opencode-gateway.codes/api/github/callback', 'Wrong GitHub callback'
assert values.get('CREDENTIALS_ENCRYPTION_KEY'), 'LIVE encryption key missing'
print('LIVE environment validated; no backup requested or created')
PY
rsync -a --exclude='.env' --exclude='.env.*' --exclude='.git/' \
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
sudo_operator /usr/bin/systemctl restart opencode-gateway.service
unset sudo_password
/usr/bin/systemctl is-active --quiet opencode-gateway.service
curl -fsS --retry 15 --retry-delay 2 --retry-connrefused http://127.0.0.1:8000/api/health
echo "LIVE_CODE_AND_SCHEMA_PROMOTED no-backup-created; old files retained"
# Real Native prompts, file permissions, SSE and cross-user isolation still
# require authenticated browser acceptance; health alone is not enough.
