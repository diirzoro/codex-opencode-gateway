#!/usr/bin/env bash
# Enable authenticated LIVE provider/agent discovery without exposing Native sessions.
set -euo pipefail
[[ "$(id -u)" -eq 0 ]] || { echo "Run as root using the existing protected deployment sudo authorization" >&2; exit 2; }
snippet=/etc/nginx/snippets/opencode-native-live.conf
[[ -f "$snippet" ]] || { echo "LIVE Native snippet missing" >&2; exit 3; }
grep -Fq 'location @native_session_live {' "$snippet" || { echo "Existing LIVE session boundary missing" >&2; exit 4; }
grep -Fq 'location @native_discovery_live {' "$snippet" || { echo "Existing LIVE discovery boundary missing" >&2; exit 4; }
if grep -Fq 'location = /native-direct/api/provider {' "$snippet" &&
   grep -Fq 'location = /native-direct/api/agent {' "$snippet"; then
  echo "LIVE Native discovery routes already present"
  exit 0
fi
# Fail rather than silently duplicate or overwrite a partially configured route.
if grep -Fq 'location = /native-direct/api/provider {' "$snippet" ||
   grep -Fq 'location = /native-direct/api/agent {' "$snippet"; then
  echo "Partial LIVE discovery configuration detected; manual reconciliation required" >&2
  exit 5
fi
backup="${snippet}.bak-discovery-$(date -u +%Y%m%dT%H%M%SZ)"
cp -p "$snippet" "$backup"
cat >> "$snippet" <<'NGINX'

# Authenticated LIVE discovery only: no Native session, tools or credential writes.
# This check authenticates the Gateway account; it does not grant session access.
location = /native-direct/api/provider {
    auth_basic off;
    auth_request /api/auth/me;
    limit_except GET { deny all; }
    proxy_pass http://127.0.0.1:18097/provider;
    proxy_set_header Cookie "";
    proxy_set_header Authorization "";
    proxy_set_header Host 127.0.0.1:18097;
    proxy_buffering off;
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types application/json;
    add_header Cache-Control "no-store" always;
}
location = /native-direct/api/agent {
    auth_basic off;
    auth_request /api/auth/me;
    limit_except GET { deny all; }
    proxy_pass http://127.0.0.1:18097/agent;
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
echo "LIVE authenticated provider and agent discovery installed; rollback: $backup"
