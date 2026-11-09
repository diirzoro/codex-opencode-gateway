#!/usr/bin/env bash
# Update only the existing TEST Native snippet. Keep the vhost, ports and TLS.
set -euo pipefail
source_file=/home/tahir/.native-direct-stage/nginx.conf
target=/etc/nginx/snippets/opencode-native-direct-test.conf
test "$(id -u)" -eq 0
test -f "$source_file"
test -f "$target"
# An invalid Auth.Info body is rejected by Native before auth.set can run.
# This checks route reachability without writing/deleting any credential, and
# avoids installing a route to an unprepared private transport. No fallback.
auth_status=$(curl --silent --show-error --max-time 10 --output /dev/null \
  --write-out '%{http_code}' --request PUT --header 'Content-Type: application/json' \
  --data '{}' http://127.0.0.1:18098/auth/gateway-route-probe-invalid)
case "$auth_status" in
  400|422) ;;
  *) echo "TEST_NATIVE_AUTH_ROUTE_UNAVAILABLE status=$auth_status; Nginx unchanged" >&2; exit 1 ;;
esac
backup="$(mktemp)"
cp "$target" "$backup"
restore() {
  install -m 0644 -o root -g root "$backup" "$target"
  nginx -t
  systemctl reload nginx
  rm -f "$backup"
}
trap restore ERR
install -m 0644 -o root -g root "$source_file" "$target"
nginx -t
systemctl reload nginx
trap - ERR
rm -f "$backup"
echo TEST_NATIVE_NGINX_AUTH_UPDATED
