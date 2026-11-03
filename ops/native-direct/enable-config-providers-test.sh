#!/usr/bin/env bash
# TEST-only repair: expose OpenCode's lightweight configured-model endpoint
# through the EXISTING private 18098 reverse proxy. Never print auth secrets.
set -euo pipefail
FILE=/etc/nginx/conf.d/opencode-native-test-session-local.conf
test "$(id -u)" -eq 0
test -f "$FILE"
grep -Eq 'listen[[:space:]]+127[.]0[.]0[.]1:18098[[:space:]]*;' "$FILE"
grep -Fq 'proxy_pass http://127.0.0.2:4097' "$FILE"
if grep -Eq 'location[[:space:]]*=[[:space:]]*/config/providers' "$FILE"; then
  nginx -t
  echo 'TEST_NATIVE_CONFIG_PROVIDERS_ALREADY_PRESENT'
  exit 0
fi
AUTH="$(grep -E '^[[:space:]]*proxy_set_header[[:space:]]+Authorization[[:space:]]+"Basic [A-Za-z0-9+/=]+";' "$FILE" | head -1)"
test -n "$AUTH"
test "$(grep -Ec '^[[:space:]]*server[[:space:]]*[{][[:space:]]*$' "$FILE")" -eq 1
BACKUP="/var/backups/opencode-native-test-config-providers.$(date +%Y%m%d%H%M%S).conf"
umask 077
cp -a "$FILE" "$BACKUP"
TEMP="$(mktemp "$(dirname "$FILE")/.config-providers.XXXXXXXX")"
trap 'rm -f "$TEMP"' EXIT
added=0
while IFS= read -r line || [[ -n "$line" ]]; do
  printf '%s\n' "$line" >> "$TEMP"
  if [[ "$line" =~ ^[[:space:]]*server[[:space:]]*\{[[:space:]]*$ ]] && (( added == 0 )); then
    cat >> "$TEMP" <<'CONF'
    # OpenCode Native configured providers/models; no Gateway Python/catalog DB.
    location = /config/providers {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.2:4097;
CONF
    printf '%s\n' "$AUTH" >> "$TEMP"
    cat >> "$TEMP" <<'CONF'
        proxy_set_header Host 127.0.0.2:4097;
        proxy_set_header Cookie "";
        proxy_cache off;
        add_header Cache-Control "no-store" always;
    }
CONF
    added=1
  fi
done < "$FILE"
test "$added" -eq 1
chmod --reference="$FILE" "$TEMP"
chown --reference="$FILE" "$TEMP"
mv "$TEMP" "$FILE"
if ! nginx -t; then
  cp -a "$BACKUP" "$FILE"
  nginx -t
  echo 'TEST_NATIVE_CONFIG_PROVIDERS_ROLLBACK_SYNTAX'
  exit 1
fi
if ! systemctl reload nginx; then
  cp -a "$BACKUP" "$FILE"
  nginx -t
  systemctl reload nginx
  echo 'TEST_NATIVE_CONFIG_PROVIDERS_ROLLBACK_RELOAD'
  exit 1
fi
echo 'TEST_NATIVE_CONFIG_PROVIDERS_ROUTED 18098->127.0.0.2:4097'
