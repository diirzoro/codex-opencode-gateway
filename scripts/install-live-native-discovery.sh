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
if grep -Fq 'location = /native-direct/api/provider/auth {' "$snippet"; then
  echo "LIVE Native provider authentication-method discovery already present"
  exit 0
fi
# Fail rather than silently duplicate or overwrite a partially configured route.
# Require existing routes before extending them: never replace or expose them.
if ! grep -Fq 'location = /native-direct/api/provider {' "$snippet" ||
   ! grep -Fq 'location = /native-direct/api/agent {' "$snippet"; then
  echo "LIVE provider/agent routes are missing; repair the base discovery installation first" >&2
  exit 5
fi
backup="${snippet}.bak-discovery-$(date -u +%Y%m%dT%H%M%SZ)"
cp -p "$snippet" "$backup"
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
