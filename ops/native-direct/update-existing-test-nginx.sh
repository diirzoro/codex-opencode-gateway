#!/usr/bin/env bash
# Replace existing TEST routing IN PLACE. No release/backup files, no LIVE edits.
set -euo pipefail
source_file=/home/tahir/.native-direct-stage/nginx.conf
target=/etc/nginx/snippets/opencode-native-direct-test.conf
test "$(id -u)" -eq 0
test -f "$source_file"
test -f "$target"
test -S /run/pi-central/pi.sock
# Roll back from memory if Nginx rejects new config; never leave invalid config.
previous="$(cat "$target")"
install -m 0644 -o root -g root "$source_file" "$target"
if nginx -t && systemctl reload nginx; then
  echo "TEST_PI_NGINX_ROUTE_ACTIVE"
else
  printf '%s\n' "$previous" > "$target"
  nginx -t
  systemctl reload nginx
  echo "TEST Pi Nginx route not applied; previous runtime restored" >&2
  exit 1
fi
