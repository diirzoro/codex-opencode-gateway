#!/usr/bin/env bash
# Deploy only the Pi Central implementation to the EXISTING pi-central.service.
# TEST Nginx is already configured; never edit Nginx, units or other services here.
set -euo pipefail
test "$(id -u)" -eq 0

src=/home/tahir/.native-direct-stage/pi-central.mjs
dst=/home/tahir/pi-test/pi-central.mjs
test -f "$src" && test -f "$dst"
node --check "$src"

if cmp -s "$src" "$dst"; then
  echo "PI_SOURCE_ALREADY_CURRENT"
  exit 0
fi

previous="$(mktemp /tmp/pi-central-previous.XXXXXX)"
cp -p "$dst" "$previous"
cleanup() { rm -f "$previous"; }
rollback() {
  code=$?
  trap - ERR
  echo "PI_DEPLOY_FAILED: restoring previous Pi file only" >&2
  install -o tahir -g tahir -m 0644 "$previous" "$dst"
  systemctl restart pi-central.service || true
  cleanup
  exit "$code"
}
trap rollback ERR
trap cleanup EXIT

install -o tahir -g tahir -m 0644 "$src" "$dst"
systemctl restart pi-central.service

# One readiness check after restart. No Nginx reload or systemd unit changes.
ready=0
for attempt in 1 2 3 4 5; do
  if runuser -u www-data -- curl -fsS --max-time 4 \
      --unix-socket /run/pi-central/pi.sock \
      http://localhost/health | grep -Fq '"status":"ready"'; then
    ready=1
    break
  fi
  sleep 1
done
test "$ready" = 1
trap - ERR
echo "PI_CODE_DEPLOYED"
