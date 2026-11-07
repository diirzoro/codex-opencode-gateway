#!/usr/bin/env bash
# Installs only a TEST-specific Nginx route to the existing local Native service.
# No Python, database migration, Native daemon restart, or LIVE app file changes.
set -euo pipefail
stage=/home/tahir/.native-direct-stage
site=/etc/nginx/sites-enabled/opencode-gateway-test
snippet=/etc/nginx/snippets/opencode-native-direct-test.conf
web=/var/www/opencode-native-direct-test
authfile=/etc/nginx/.native-direct-test.htpasswd
access="$stage/native-access-password"
read -r sudo_password
sudo_checked() {
  printf '%s\n' "$sudo_password" | sudo -S -p '' "$@"
}
test "$USER" = tahir
test -f "$stage/index.html" && test -f "$stage/app.js" && test -f "$stage/style.css"
test -f "$stage/nginx.conf" && test -f "$site"
real_site="$(readlink -f "$site")"
grep -Fq 'server_name test.opencode-gateway.codes;' "$real_site"
test "$(grep -Ec '^[[:space:]]*location / \{' "$real_site")" = 1
if ! test -f "$access"; then
  umask 077
  openssl rand -hex 18 > "$access"
fi
chmod 600 "$access"
hash="$(openssl passwd -6 -stdin < "$access")"
credential="$(mktemp)"
printf 'native-test:%s\n' "$hash" > "$credential"
sudo_checked install -D -m 0640 -o root -g www-data "$credential" "$authfile"
rm -f "$credential"
sudo_checked install -D -m 0644 "$stage/nginx.conf" "$snippet"
sudo_checked install -d -m 0755 "$web"
for name in index.html app.js style.css; do
  sudo_checked install -m 0644 "$stage/$name" "$web/$name"
done
if ! grep -Fq 'include /etc/nginx/snippets/opencode-native-direct-test.conf;' "$real_site"; then
  backup="$(mktemp)"
  patched="$(mktemp)"
  cat "$real_site" > "$backup"
  awk '/^[[:space:]]*location \/ \{$/ {print "    include /etc/nginx/snippets/opencode-native-direct-test.conf;"} {print}' "$backup" > "$patched"
  sudo_checked install -m 0644 "$patched" "$real_site"
  if ! sudo_checked nginx -t; then
    sudo_checked install -m 0644 "$backup" "$real_site"
    sudo_checked nginx -t
    rm -f "$backup" "$patched"
    echo 'TEST Native nginx syntax failed; original vhost restored' >&2
    exit 1
  fi
  rm -f "$backup" "$patched"
else
  sudo_checked nginx -t
fi
sudo_checked systemctl reload nginx
unset sudo_password
printf 'NATIVE_DIRECT_TEST_INSTALLED no_python_gateway no_database_changes\n'
printf 'NATIVE_TEST_ACCESS_FILE=%s (readable by the VPS owner only; never logged)\n' "$access"
