#!/usr/bin/env bash
# TEST-only native sessions and SSE transport. Never expose publicly.
set -euo pipefail
CONF=/etc/nginx/conf.d/opencode-native-test-session-local.conf
if [[ -e "$CONF" ]]; then echo "Existing config: $CONF (not overwritten)" >&2; exit 1; fi
password=$(sudo sed -n 's/^OPENCODE_SERVER_PASSWORD=//p' /etc/opencode-native-test.env)
[[ -n "$password" ]] || { echo "Missing Native TEST password" >&2; exit 1; }
authorization=$(printf 'opencode:%s' "$password" | base64 -w0)
unset password
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
cat >"$tmp" <<EOF
# Local TEST transport, no public exposure
server {
    listen 127.0.0.1:18098;
    server_name localhost;
    client_max_body_size 2m;
    location = /session {
        proxy_pass http://127.0.0.2:4097;
        proxy_set_header Authorization "Basic $authorization";
        proxy_set_header Cookie "";
        proxy_set_header Host 127.0.0.2:4097;
        proxy_read_timeout 120s;
        add_header Cache-Control "no-store" always;
    }
    location ^~ /session/ {
        proxy_pass http://127.0.0.2:4097;
        proxy_set_header Authorization "Basic $authorization";
        proxy_set_header Cookie "";
        proxy_set_header Host 127.0.0.2:4097;
        proxy_read_timeout 120s;
        add_header Cache-Control "no-store" always;
    }
    location = /event {
        proxy_pass http://127.0.0.2:4097;
        proxy_set_header Authorization "Basic $authorization";
        proxy_set_header Cookie "";
        proxy_set_header Host 127.0.0.2:4097;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 1h;
        add_header Cache-Control "no-store" always;
    }
    location / { return 404; }
}
EOF
sudo install -o root -g root -m 600 "$tmp" "$CONF"
if ! sudo nginx -t; then sudo rm -f "$CONF"; exit 1; fi
sudo systemctl reload nginx
echo "Native TEST session/SSE loopback transport ready on 127.0.0.1:18098"
echo "Gateway and LIVE unchanged. This is NOT a public Workspace route."
