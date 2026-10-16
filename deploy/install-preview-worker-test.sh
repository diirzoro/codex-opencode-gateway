#!/usr/bin/env bash
# Install the isolated TEST worker service without touching Live.
# Usage: sudo bash deploy/install-preview-worker-test.sh
set -euo pipefail
[[ $(id -u) -eq 0 ]] || { echo 'Run as root'; exit 1; }
APP=/home/tahir/opencode-gateway-test
SERVICE=opencode-preview-worker-test.service
SOURCE="$APP/deploy/$SERVICE"
[[ -f "$SOURCE" && -x "$APP/.venv/bin/python" ]] || {
  echo 'Test deployment has not yet included the Preview worker files.' >&2
  exit 1
}
if ! id preview-worker >/dev/null 2>&1; then
  useradd --system --no-create-home --shell /usr/sbin/nologin preview-worker
fi
install -d -o preview-worker -g preview-worker -m 0700 /var/lib/preview-worker/jobs
install -d -o preview-worker -g preview-worker -m 0700 /var/lib/preview-worker/logs
if [[ ! -f /etc/opencode-preview-worker-test.env ]]; then
  umask 077
  TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')
  printf 'PREVIEW_WORKER_TOKEN=%s\n' "$TOKEN" > /etc/opencode-preview-worker-test.env
fi
chown root:preview-worker /etc/opencode-preview-worker-test.env
chmod 0640 /etc/opencode-preview-worker-test.env
install -o root -g root -m 0644 "$SOURCE" "/etc/systemd/system/$SERVICE"
systemctl daemon-reload
# Deliberately do not enable/start: the Gateway worker registry and browser
# routing are not yet wired, and Docker access is not provisioned for this user.
echo 'Installed TEST worker unit. Worker remains stopped until wiring is complete.'
