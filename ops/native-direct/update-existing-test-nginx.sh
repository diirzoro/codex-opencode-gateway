#!/usr/bin/env bash
# TEST only — replace the existing Pi service implementation and Nginx snippet
# in place. Do not create releases, a second service, or persistent backups.
set -euo pipefail
test "$(id -u)" -eq 0
STAGE=/home/tahir/.native-direct-stage
PI_SRC="$STAGE/pi-central.mjs"
PI_DST=/home/tahir/pi-test/pi-central.mjs
NGINX_SRC="$STAGE/nginx.conf"
NGINX_DST=/etc/nginx/snippets/pi-central-test.conf
UNIT="$(systemctl show pi-central.service --property FragmentPath --value)"
test "$UNIT" = /etc/systemd/system/pi-central.service
test -f "$PI_SRC" && test -f "$PI_DST" && test -f "$NGINX_SRC" && test -f "$NGINX_DST"
# The shared Nginx instance must reference the one canonical TEST Pi snippet.
test -f /etc/nginx/sites-enabled/opencode-gateway-test
grep -Fq "include /etc/nginx/snippets/pi-central-test.conf;" /etc/nginx/sites-enabled/opencode-gateway-test
! grep -Eq "18097|18098" "$NGINX_SRC"
test -x /home/tahir/pi-test/node_modules/.bin/pi
test "$(systemctl show pi-central.service --property User --value)" = tahir
grep -Fq '/home/tahir/pi-test/pi-central.mjs' "$UNIT"
grep -Fq 'RuntimeDirectory=pi-central' "$UNIT"
node --check "$PI_SRC"

# Full in-memory rollback if any service or Nginx validation fails. No extra files.
old_pi="$(cat "$PI_DST")"
old_unit="$(cat "$UNIT")"
old_nginx="$(cat "$NGINX_DST")"
changed=0
stage=preflight
restore() {
  local code="$?" failed_at="${stage:-unknown}"
  trap - ERR
  set +e
  echo "TEST_PI_DEPLOY_FAILED stage=$failed_at exit=$code" >&2
  systemctl show pi-central.service -p ActiveState -p SubState -p Result -p ExecMainStatus --no-pager >&2 || true
  if [ "$changed" = 1 ]; then
    printf '%s\n' "$old_pi" > "$PI_DST"
    chown tahir:tahir "$PI_DST"
    chmod 0644 "$PI_DST"
    printf '%s\n' "$old_unit" > "$UNIT"
    chown root:root "$UNIT"
    chmod 0644 "$UNIT"
    printf '%s\n' "$old_nginx" > "$NGINX_DST"
    chown root:root "$NGINX_DST"
    chmod 0644 "$NGINX_DST"
    systemctl daemon-reload
    systemctl restart pi-central.service || true
    nginx -t && systemctl reload nginx || true
    echo TEST_PI_ROLLED_BACK >&2
  fi
  exit "$code"
}
trap restore ERR
changed=1
stage=pi_source_install
install -o tahir -g tahir -m 0644 "$PI_SRC" "$PI_DST"
# Keep existing systemd unit: only its own service group & runtime-dir access.
stage=pi_systemd_configuration
python3 - "$UNIT" <<'PY'
import pathlib,sys,re
p=pathlib.Path(sys.argv[1])
s=p.read_text()
def set_service_option(s,key,value):
    pat=r'(?m)^'+re.escape(key)+r'=.*$'
    if re.search(pat,s):
        return re.sub(pat,key+'='+value,s)
    return s.replace('[Service]','[Service]\n'+key+'='+value,1)
assert '[Service]' in s
s=set_service_option(s,'Group','www-data')
s=set_service_option(s,'RuntimeDirectoryMode','0750')
p.write_text(s)
PY
stage=pi_daemon_reload
systemctl daemon-reload
stage=pi_restart
systemctl restart pi-central.service
stage=pi_active_check
systemctl is-active --quiet pi-central.service
stage=pi_socket_check
test -S /run/pi-central/pi.sock
# Check the ACTUAL nginx worker account can traverse directory and reach Pi.
stage=pi_socket_http_health
runuser -u www-data -- curl -fsS --max-time 7 \
  --unix-socket /run/pi-central/pi.sock http://localhost/health |
  grep -q '"status":"ready"'
echo TEST_PI_SOCKET_ACCESS_OK

# The TEST snippet is the only Nginx file being updated.
stage=nginx_config_install
if ! cmp -s "$NGINX_SRC" "$NGINX_DST"; then
  install -o root -g root -m 0644 "$NGINX_SRC" "$NGINX_DST"
fi
stage=nginx_configuration_test
nginx -t
stage=nginx_reload
systemctl reload nginx
echo TEST_PI_NGINX_ACTIVE
echo TEST_PI_DEPLOY_SUCCESS
trap - ERR
