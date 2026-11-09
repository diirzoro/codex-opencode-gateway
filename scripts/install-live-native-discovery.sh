#!/usr/bin/env bash
# Enable authenticated LIVE provider/agent discovery without exposing Native sessions.
set -euo pipefail
[[ "$(id -u)" -eq 0 ]] || { echo "Run as root using the existing protected deployment sudo authorization" >&2; exit 2; }
snippet=/etc/nginx/snippets/opencode-native-live.conf
[[ -f "$snippet" ]] || { echo "LIVE Native snippet missing" >&2; exit 3; }
grep -Fq 'location @native_session_live {' "$snippet" || { echo "Existing LIVE session boundary missing" >&2; exit 4; }
grep -Fq 'location @native_discovery_live {' "$snippet" || { echo "Existing LIVE discovery boundary missing" >&2; exit 4; }
# The two older LIVE routes can already exist. Install missing routes only.
# Detect a duplicate existing auth-method route and leave it unchanged.
# Existing provider/auth is idempotent; still install missing Native routes.
# Fail rather than silently duplicate or overwrite a partially configured route.
# Require existing routes before extending them: never replace or expose them.
if ! grep -Fq 'location = /native-direct/api/provider {' "$snippet" ||
   ! grep -Fq 'location = /native-direct/api/agent {' "$snippet"; then
  echo "LIVE provider/agent routes are missing; repair the base discovery installation first" >&2
  exit 5
fi
backup="${snippet}.bak-discovery-$(date -u +%Y%m%dT%H%M%SZ)"
cp -p "$snippet" "$backup"
if ! grep -Fq 'location = /native-direct/api/provider/auth {' "$snippet"; then
cat >> "$snippet" <<'NGINX'

# Authenticated LIVE provider authentication-method discovery (metadata GET).
# Does not expose /auth/<provider> credential read/write/delete or sessions.
location = /native-direct/api/provider/auth {
    auth_basic off;
    auth_request /api/auth/me;
    limit_except GET { deny all; }
    proxy_pass http://127.0.0.1:18097/provider/auth;
    proxy_set_header Cookie "";
    proxy_set_header Authorization "";
    proxy_set_header Host 127.0.0.1:18097;
    proxy_buffering off;
    add_header Cache-Control "no-store" always;
}
NGINX
fi
# Native credential storage and session transport: Browser -> Nginx -> OpenCode.
# This preserves the existing Gateway sign-in check. Multi-user Native
# session isolation remains BLOCKED under the architecture agreement.
# Do not treat this login check as per-project/session authorization.
if ! grep -Fq 'location ^~ /native-direct/api/auth/ {' "$snippet"; then
cat >> "$snippet" <<'NGINX_AUTH'

# OpenCode credentials are handled by Native 18097 only; never by Python.
location ^~ /native-direct/api/auth/ {
    auth_basic off;
    auth_request /api/auth/me;
    client_max_body_size 256k;
    limit_except GET PUT DELETE { deny all; }
    rewrite ^/native-direct/api/(.*)$ /$1 break;
    proxy_pass http://127.0.0.1:18098;
    proxy_http_version 1.1;
    proxy_set_header Cookie "";
    proxy_set_header Authorization "";
    proxy_set_header Host 127.0.0.1:18098;
    proxy_buffering off;
    proxy_cache off;
    add_header Cache-Control "no-store" always;
}
NGINX_AUTH
fi
# The existing protected Native session transport 18098 includes
# /auth/{provider} in its allowlist. The discovery transport 18097 does
# not reliably expose credential PUT/DELETE, which caused 404 on LIVE.
# Repair pre-existing LIVE snippets as well as fresh installations.
if grep -Fq 'location ^~ /native-direct/api/auth/ {' "$snippet"; then
  temp_auth="$(mktemp)"
  awk '
    /location \^~ \/native-direct\/api\/auth\/ \{/ { in_auth=1; seen=1 }
    in_auth && /proxy_pass http:\/\/127\.0\.0\.1:18097;/ {
      sub("127.0.0.1:18097", "127.0.0.1:18098")
    }
    in_auth && /proxy_set_header Host 127\.0\.0\.1:18097;/ {
      sub("127.0.0.1:18097", "127.0.0.1:18098")
    }
    { print }
    in_auth && /^[[:space:]]*\}/ { in_auth=0 }
    END { if (!seen) exit 1 }
  ' "$snippet" > "$temp_auth"
  cat "$temp_auth" > "$snippet"
  rm -f "$temp_auth"
fi
if ! grep -Fq 'location ^~ /native-direct/api/ {' "$snippet"; then
cat >> "$snippet" <<'NGINX_NATIVE'

# Native session/tool/file/SSE routes, not a Gateway or Python Native proxy.
# Only authenticated test accounts; not a multi-tenant security claim.
location ^~ /native-direct/api/ {
    auth_basic off;
    auth_request /api/auth/me;
    client_max_body_size 2m;
    limit_except GET POST PUT PATCH DELETE { deny all; }
    rewrite ^/native-direct/api/(.*)$ /$1 break;
    proxy_pass http://127.0.0.1:18098;
    proxy_http_version 1.1;
    proxy_set_header Cookie "";
    proxy_set_header Authorization "";
    proxy_set_header Host 127.0.0.1:18098;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 3600s;
    add_header Cache-Control "no-store" always;
}
NGINX_NATIVE
fi
if ! /usr/sbin/nginx -t; then
  cp -p "$backup" "$snippet"
  /usr/sbin/nginx -t || true
  echo "Nginx validation failed; original LIVE snippet restored" >&2
  exit 6
fi
if ! /usr/bin/systemctl reload nginx; then
  cp -p "$backup" "$snippet"
  /usr/sbin/nginx -t && /usr/bin/systemctl reload nginx || true
  echo "Nginx reload failed; original LIVE snippet restored" >&2
  exit 7
fi
echo "LIVE authenticated provider/auth discovery installed; rollback: $backup"
