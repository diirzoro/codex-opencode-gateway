#!/usr/bin/env bash
# Reuse the existing dedicated rootless worker; never system Docker or Pi.
set -euo pipefail
umask 077
[[ $(id -u) -eq 0 ]] || exit 1
STAGE=/home/tahir/preview-activation
WORKER=/opt/opencode-preview-test
ENVFILE=/etc/opencode-preview-worker-test.env
[[ -f "$ENVFILE" && -f "$STAGE/backend/app/services/preview_worker_server.py" ]] || exit 2
[[ $(systemctl show opencode-preview-docker-test.service -p User --value) == preview-worker ]] || exit 3
[[ $(systemctl show opencode-preview-worker-test.service -p User --value) == preview-worker ]] || exit 3
bash "$STAGE/scripts/preview-host-inspect.sh"
# Named enforcing policy avoids rootless Docker attempting to load docker-default.
# Keep AppArmor enabled; never use apparmor=unconfined or disable host security.
command -v apparmor_parser >/dev/null
install -o root -g root -m 0644 "$STAGE/deploy/apparmor-preview" /etc/apparmor.d/opencode-preview
apparmor_parser -r /etc/apparmor.d/opencode-preview
# Preserve existing unit isolation and add aggregate resource ceilings.
install -d -m 0755 /etc/systemd/system/opencode-preview-docker-test.service.d
cat > /etc/systemd/system/opencode-preview-docker-test.service.d/resources.conf <<'UNIT'
[Service]
MemoryMax=1G
CPUQuota=60%
TasksMax=256
UNIT
install -d -m 0755 /etc/systemd/system/opencode-preview-worker-test.service.d
cat > /etc/systemd/system/opencode-preview-worker-test.service.d/resources.conf <<'UNIT'
[Service]
MemoryMax=384M
CPUQuota=25%
TasksMax=64
UNIT
# The historical daemon was launched as a system unit without its user bus.
# Rootless systemd cgroups require the dedicated user's manager, not root D-Bus.
preview_uid=$(id -u preview-worker)
loginctl enable-linger preview-worker
systemctl start "user@${preview_uid}.service"
[[ -S "/run/user/${preview_uid}/bus" ]] || { echo 'Dedicated user bus unavailable'; exit 7; }
cat > /etc/systemd/system/opencode-preview-docker-test.service.d/user-bus.conf <<UNIT
[Service]
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/${preview_uid}/bus
Delegate=yes
UNIT
install -d -m 0755 "/etc/systemd/system/user-${preview_uid}.slice.d"
cat > "/etc/systemd/system/user-${preview_uid}.slice.d/preview-resources.conf" <<'UNIT'
[Slice]
MemoryMax=1G
CPUQuota=60%
TasksMax=256
UNIT
systemctl daemon-reload
systemctl restart opencode-preview-docker-test.service
for attempt in {1..20}; do
  [[ -S /run/preview-worker/docker.sock ]] && break
  sleep 1
done
[[ -S /run/preview-worker/docker.sock ]] || exit 4
docker_preview() {
 runuser -u preview-worker -- env HOME=/var/lib/preview-worker DOCKER_HOST=unix:///run/preview-worker/docker.sock DOCKER_BUILDKIT=0 docker "$@"
}
# Require actual rootless cgroup support before launching any customer process.
info=$(docker_preview info --format '{{json .SecurityOptions}} {{.CgroupVersion}} {{.CgroupDriver}}')
[[ "$info" == *rootless* && "$info" == *' 2 '* && "$info" != *' none' ]] || { echo 'Rootless cgroup enforcement unavailable'; exit 5; }
base=$(python3 - "$ENVFILE" <<'PYBASE'
import sys,re
from pathlib import Path
rows=dict(line.split('=',1) for line in Path(sys.argv[1]).read_text().splitlines() if '=' in line and not line.startswith('#'))
image=rows.get('PREVIEW_PYTHON_BASE',rows.get('PREVIEW_IMAGE_PYTHON','')).strip().strip('"')
assert re.fullmatch(r'[a-z0-9._/-]+@sha256:[0-9a-f]{64}',image)
print(image)
PYBASE
)
docker_preview image inspect "$base" >/dev/null
# Prepare trusted dependencies in a bounded named-policy builder container.
# No customer code, customer requirements, or host mounts enter this container.
builder="preview-python-build-$(date +%s)"
cleanup_builder() { docker_preview rm -f "$builder" >/dev/null 2>&1 || true; }
trap cleanup_builder EXIT
[[ -f "$STAGE/preview-wheels/SHA256SUMS" ]] || { echo 'Trusted offline runtime wheels missing'; exit 8; }
(cd "$STAGE/preview-wheels" && sha256sum --check SHA256SUMS)
docker_preview create --name "$builder" --network=none --memory=512m --memory-swap=512m --cpus=0.4 --pids-limit=128 \
 --cap-drop=ALL --security-opt=no-new-privileges --security-opt=apparmor=opencode-preview \
 "$base" python -c "import subprocess,shutil; subprocess.run(['python','-m','pip','install','--no-index','--find-links=/runtime-wheels','--no-cache-dir','--disable-pip-version-check','fastapi>=0.115.6,<1','uvicorn>=0.34.0,<1'],check=True)" >/dev/null
docker_preview cp "$STAGE/preview-wheels/." "$builder:/runtime-wheels"
docker_preview start --attach "$builder"
[[ $(docker_preview inspect --format '{{.State.ExitCode}}' "$builder") == 0 ]] || exit 9
docker_preview commit --change 'USER 10001:10001' --change 'WORKDIR /workspace' \
 --change 'ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1' \
 "$builder" preview-python-runtime:configured >/dev/null
cleanup_builder
trap - EXIT
image_id=$(docker_preview image inspect preview-python-runtime:configured --format '{{.Id}}')
[[ "$image_id" =~ ^sha256:[0-9a-f]{64}$ ]] || exit 6
PREVIEW_RUNTIME_BASE="$base" PREVIEW_RUNTIME_IMAGE="$image_id" python3 - "$ENVFILE" <<'PY'
from pathlib import Path
import os,sys
p=Path(sys.argv[1]); lines=p.read_text().splitlines()
lines=[line for line in lines if not line.startswith(('PREVIEW_IMAGE_PYTHON=','PREVIEW_PYTHON_BASE='))]
lines.append('PREVIEW_PYTHON_BASE='+os.environ['PREVIEW_RUNTIME_BASE'])
lines.append('PREVIEW_IMAGE_PYTHON='+os.environ['PREVIEW_RUNTIME_IMAGE'])
p.write_text('\n'.join(lines)+'\n')
PY
# Replace only worker modules in the existing independent deployment.
systemctl stop opencode-preview-worker-test.service
for file in "$STAGE"/backend/app/services/preview*.py; do
 install -o root -g root -m 0644 "$file" "$WORKER/app/services/$(basename "$file")"
done
systemctl start opencode-preview-worker-test.service
systemctl is-active --quiet opencode-preview-worker-test.service
# Authenticated protocol check without logging credentials.
python3 - "$ENVFILE" <<'PY'
import json,sys
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
rows=dict(line.split('=',1) for line in Path(sys.argv[1]).read_text().splitlines() if '=' in line and not line.startswith('#'))
token=rows['PREVIEW_WORKER_TOKEN'].strip().strip('"').strip("'")
req=Request('http://127.0.0.1:8791/v1/status',data=b'{"job_id":"readiness-probe"}',headers={'Authorization':'Bearer '+token})
import time
for attempt in range(20):
 try:
  urlopen(req,timeout=10)
  raise SystemExit('Unexpected protocol response')
 except HTTPError as exc:
  assert exc.code==404 and json.load(exc)['error']=='unregistered_job'
  break
 except OSError:
  if attempt==19: raise
  time.sleep(0.5)
print('Existing preview worker authenticated protocol: OK')
import base64,io,tarfile,uuid,time
job='preview-readiness-'+uuid.uuid4().hex[:12]
source=b'from fastapi import FastAPI\napp=FastAPI()\n@app.get("/")\ndef health(): return {"ok":True,"runtime":"python"}\n'
archive=io.BytesIO()
with tarfile.open(fileobj=archive,mode='w') as tar:
 member=tarfile.TarInfo('main.py'); member.size=len(source); tar.addfile(member,io.BytesIO(source))
def call(operation,payload):
 req=Request('http://127.0.0.1:8791/v1/'+operation,data=json.dumps({'job_id':job,**payload}).encode(),headers={'Authorization':'Bearer '+token})
 with urlopen(req,timeout=90) as response: return json.load(response)
try:
 assert call('prepare',{'framework':'python','entrypoint':'main.py','archive':base64.b64encode(archive.getvalue()).decode()})['state']=='ready'
 started=call('start',{})
 assert started['state']=='running'
 import subprocess
 prefix=['runuser','-u','preview-worker','--','env','HOME=/var/lib/preview-worker','DOCKER_HOST=unix:///run/preview-worker/docker.sock','docker']
 details=json.loads(subprocess.check_output(prefix+['inspect',started['container_id']],text=True))[0]
 host=details['HostConfig']
 assert host['NetworkMode']=='none' and host['ReadonlyRootfs'] is True
 assert host['Memory']==768*1024*1024 and host['NanoCpus']==500000000 and host['PidsLimit']==128
 assert details['Config']['User']=='10001:10001' and host['CapDrop']==['ALL']
 assert any('no-new-privileges' in option for option in host['SecurityOpt'])
 assert 'apparmor=opencode-preview' in host['SecurityOpt']
 assert len(details['Mounts'])==1 and details['Mounts'][0]['Destination']=='/workspace' and details['Mounts'][0]['RW'] is False
 print('Runtime identity, mounts, network, AppArmor and resource limits: OK')
 result=call('fetch',{'path':'/'})
 assert result['status']==200 and json.loads(base64.b64decode(result['body']))['runtime']=='python'
 print('Real isolated Python runtime HTTP smoke: OK')
finally:
 assert call('stop',{})['state']=='stopped'
print('Runtime stopped after smoke: OK')
PY
echo 'Prepared existing worker and immutable Python runtime; Gateway not yet enabled.'
bash "$STAGE/scripts/preview-host-inspect.sh"
