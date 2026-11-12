#!/usr/bin/env bash
# LIVE Pi Gateway promotion, using existing services only.
# Called manually by the production GitHub Actions workflow.
set -euo pipefail
umask 077

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
# prompts. Pi Central itself is shared and is NEVER changed or restarted here.
"$APP/.venv/bin/python" -m pip install --disable-pip-version-check -q -r "$APP/backend/requirements.txt"
(
  set -a
  . "$APP/.env"
  set +a
  cd "$APP/backend"
  ../.venv/bin/python -m alembic upgrade head
  ../.venv/bin/python -m alembic current
)
sudo_operator /usr/bin/systemctl restart opencode-gateway.service
sudo_operator /usr/bin/systemctl is-active --quiet opencode-gateway.service
curl -fsS --max-time 15 --retry 8 --retry-delay 2 \
  --header 'Host: opencode-gateway.codes' http://127.0.0.1:8000/api/health >/dev/null

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
trap 'rm -f "$rollback"' EXIT
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

unset sudo_password
echo "LIVE_PI_GATEWAY_DEPLOYED revision=$LIVE_PI_SOURCE_SHA gateway=8000 db=opencode_gateway shared_pi=unchanged"
