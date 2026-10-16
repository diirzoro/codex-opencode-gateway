#!/usr/bin/env bash
# Refresh the deployed TEST worker code and prepare pinned runtime images.
# Does not modify master, Live units, or the system Docker daemon.
set -euo pipefail
[[ $(id -u) -eq 0 ]] || { echo "Run with sudo" >&2; exit 1; }
TEST_ROOT=/home/tahir/opencode-gateway-test
WORKER_ROOT=/opt/opencode-preview-test
WORKER_ENV=/etc/opencode-preview-worker-test.env
SOCKET=unix:///run/preview-worker/docker.sock
[[ -r "$TEST_ROOT/backend/app/services/preview_worker_server.py" ]] || {
  echo "Deploy the latest updates to Test first." >&2; exit 1;
}
[[ -S /run/preview-worker/docker.sock ]] || {
  echo "Dedicated Rootless Docker daemon is not running." >&2; exit 1;
}
[[ -f "$WORKER_ENV" ]] || { echo "Missing worker environment." >&2; exit 1; }
install -d -o root -g root -m 0755 "$WORKER_ROOT"
install -d -o preview-worker -g preview-worker -m 0700 /var/lib/preview-worker/jobs
install -d -o preview-worker -g preview-worker -m 0700 /var/lib/preview-worker/logs
# The independent Worker is intentionally not a Git checkout.
# Copy backend app only; do not copy Test secrets or its .env.
rm -rf "$WORKER_ROOT/app.new" "$WORKER_ROOT/app.previous"
cp -a "$TEST_ROOT/backend/app" "$WORKER_ROOT/app.new"
chown -R root:root "$WORKER_ROOT/app.new"
chmod -R a+rX "$WORKER_ROOT/app.new"
if [[ -e "$WORKER_ROOT/app" ]]; then
  mv "$WORKER_ROOT/app" "$WORKER_ROOT/app.previous"
fi
mv "$WORKER_ROOT/app.new" "$WORKER_ROOT/app"
python3 -m compileall -q "$WORKER_ROOT/app"
rm -rf "$WORKER_ROOT/app.previous"
docker_rootless() {
  runuser -u preview-worker -- env HOME=/var/lib/preview-worker DOCKER_HOST="$SOCKET" docker "$@"
}
# Pin each image to its exact pulled digest; do not guess digest values.
for item in node:22-alpine python:3.12-slim php:8.3-cli-alpine; do
  docker_rootless pull "$item"
done
python3 - <<'PY'
import subprocess
from pathlib import Path
envfile=Path("/etc/opencode-preview-worker-test.env")
data=envfile.read_text().splitlines()
def digest(image):
    result=subprocess.check_output([
        "runuser","-u","preview-worker","--","env",
        "HOME=/var/lib/preview-worker",
        "DOCKER_HOST=unix:///run/preview-worker/docker.sock",
        "docker","image","inspect",image,
        "--format","{{index .RepoDigests 0}}"
    ],text=True).strip()
    if "@sha256:" not in result:
        raise SystemExit("No pinned digest for " + image)
    return result
updates={
  "PREVIEW_IMAGE_NODE":digest("node:22-alpine"),
  "PREVIEW_IMAGE_PYTHON":digest("python:3.12-slim"),
  "PREVIEW_IMAGE_PHP":digest("php:8.3-cli-alpine"),
}
kept=[line for line in data if line.split("=",1)[0] not in updates]
kept.extend(key+"="+value for key,value in updates.items())
envfile.write_text("\n".join(kept)+"\n")
PY
chown root:preview-worker "$WORKER_ENV"
chmod 0640 "$WORKER_ENV"
# Attach the worker to the dedicated TEST Rootless Docker socket.
# Never modify system Docker or Live unit files.
install -d -m 0755 /etc/systemd/system/opencode-preview-worker-test.service.d
cat > /etc/systemd/system/opencode-preview-worker-test.service.d/docker.conf <<'OVERRIDE'
[Unit]
Requires=opencode-preview-docker-test.service
After=opencode-preview-docker-test.service
[Service]
Environment=DOCKER_HOST=unix:///run/preview-worker/docker.sock
OVERRIDE
systemctl daemon-reload
systemctl restart opencode-preview-worker-test.service
sleep 2
systemctl is-active --quiet opencode-preview-worker-test.service || {
  journalctl -u opencode-preview-worker-test.service -n 20 --no-pager
  exit 1
}
# Validate authenticated Worker API without printing secrets.
WORKER_ENV_FILE="$WORKER_ENV" python3 - <<'PY'
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import json
import os
env = {}
for line in Path(os.environ["WORKER_ENV_FILE"]).read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        key, value = line.split("=", 1)
        env[key] = value.strip().strip('"').strip("'")
token = env.get("PREVIEW_WORKER_TOKEN", "")
if len(token) < 32:
    raise SystemExit("Preview Worker token missing/invalid")
req = Request(
    "http://127.0.0.1:8791/v1/status",
    data=b'{"job_id":"preview-health-probe"}',
    headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    method="POST",
)
try:
    with urlopen(req, timeout=5):
        raise SystemExit("Unexpected Worker health response")
except HTTPError as exc:
    payload = json.loads(exc.read(1024))
    if exc.code != 404 or payload.get("error") != "unregistered_job":
        raise SystemExit("Preview Worker auth/protocol failed: HTTP " + str(exc.code))
print("Preview Worker authenticated loopback protocol: OK")
PY
echo "TEST worker code and pinned Node/Python/PHP images are configured."
echo "Note: application dependency installation and browser routing still require integration."
