#!/usr/bin/env bash
# LIVE Pi Gateway promotion, using existing services only.
# Called manually by the production GitHub Actions workflow.
set -euo pipefail
umask 077

# Explicit one-time operator action. Normal deployments never activate or
# change containment settings. Reuse existing units/config; no new service.
if [[ "${1:-}" == --activate-client-isolation ]]; then
  echo "The old shared LIVE/TEST activation is permanently disabled. Use the dedicated LIVE Pi service." >&2
  exit 2
fi

APP=/home/tahir/opencode-gateway
RELEASE=/home/tahir/opencode-gateway-release
SNIPPET=/etc/nginx/snippets/opencode-native-live.conf
PI_SOCKET=/run/pi-central-live/pi.sock

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
sudo_operator /usr/bin/systemctl is-active --quiet pi-central-live.service ||
  { echo "Dedicated LIVE Pi service is not active" >&2; exit 4; }
sudo_operator /usr/bin/systemctl is-active --quiet opencode-gateway.service ||
  { echo "LIVE Gateway is not active" >&2; exit 4; }

# Resolve the file actually executed by the existing shared Pi service. LIVE
# source synchronization alone does not update a separate /home/tahir/pi-test
# runtime. Do not guess a checkout, change ExecStart or replace the SDK.
pi_pid="$(sudo_operator /usr/bin/systemctl show pi-central-live.service -p MainPID --value)"
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
    echo "Release failed; restoring the previous LIVE Pi entry point" >&2
    if install_pi_file "$pi_backup"; then
      if [[ "$pi_restart_attempted" == 1 ]]; then
        sudo_operator /usr/bin/systemctl restart pi-central-live.service ||
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
    "PI_SOCKET": "/run/pi-central-live/pi.sock",
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
# prompts. Dedicated LIVE Pi is updated below only when its actual source differs.
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

# Activate the release in the dedicated LIVE Pi runtime only. No service unit,
# SDK package, environment flag, workflow, payment setting or project is edited.
if [[ "$pi_update_needed" == 1 ]]; then
  install_pi_file "$RELEASE/integration/pi-central.mjs"
  pi_restart_attempted=1
  sudo_operator /usr/bin/systemctl restart pi-central-live.service
  sudo_operator /usr/bin/systemctl is-active --quiet pi-central-live.service
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
  echo "The dedicated LIVE Pi runtime does not match the deployed release" >&2
  exit 9
}
echo "LIVE_PI_SOURCE_DEPLOYED revision=$LIVE_PI_SOURCE_SHA updated=$pi_update_needed"

unset sudo_password
echo "LIVE_PI_GATEWAY_DEPLOYED revision=$LIVE_PI_SOURCE_SHA gateway=8000 db=opencode_gateway live_pi=release-matched"
