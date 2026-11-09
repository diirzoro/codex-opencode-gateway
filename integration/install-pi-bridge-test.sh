#!/usr/bin/env bash
# Deploy existing Pi Central service implementation IN PLACE. TEST staging only.
# No package installs, no LIVE changes, no Nginx changes, no release directories.
set -euo pipefail
BASE="https://raw.githubusercontent.com/diirzoro/codex-opencode-gateway/updates/integration"
TARGET="/home/tahir/pi-test/pi-central.mjs"
if [[ "$(id -un)" != "tahir" ]]; then echo "Run as tahir"; exit 1; fi
if [[ ! -x /home/tahir/pi-test/node_modules/.bin/pi ]]; then echo "Pi CLI missing"; exit 1; fi
if [[ ! -f "$TARGET" ]]; then echo "Current pi-central.mjs missing"; exit 1; fi
echo "Download reviewed TEST bridge to existing Pi service file"
curl -fLsS --max-time 20 "$BASE/pi-central.mjs" -o "$TARGET.new"
if ! node --check "$TARGET.new"; then rm -f "$TARGET.new"; echo "Syntax failure; service unchanged"; exit 1; fi
mv -f "$TARGET.new" "$TARGET"
echo "Restart existing Pi Central service (does not touch Gateway or Nginx)"
sudo systemctl restart pi-central.service
sleep 2
if ! systemctl is-active --quiet pi-central.service; then
  sudo journalctl -u pi-central.service -n 15 --no-pager
  echo "Pi service did not start"; exit 1
fi
echo "Central Pi service health:"
curl -fLsS --unix-socket /run/pi-central/pi.sock http://localhost/health
echo
echo "Pi TEST transport staged; nginx routes are NOT changed."
