#!/usr/bin/env bash
# Update only the existing TEST Native snippet. Keep the vhost, ports and TLS.
set -euo pipefail
source_file=/home/tahir/.native-direct-stage/nginx.conf
target=/etc/nginx/snippets/opencode-native-direct-test.conf
test "$(id -u)" -eq 0
test -f "$source_file"
test -f "$target"
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
