#!/usr/bin/env bash
# Read-only inventory. No environment values, tokens or customer files printed.
set -euo pipefail
[[ $(id -u) -eq 0 ]] || { echo 'Root inventory required'; exit 1; }
python3 - <<'PY'
from pathlib import Path
import json, shutil, subprocess

def command(argv):
    r=subprocess.run(argv,capture_output=True,text=True,timeout=25)
    return r.stdout.strip()
print('HOST_RESOURCES')
print(command(['free','-m']))
print(command(['df','-Pm','/var/lib/preview-worker','/home/tahir']))
print('CPU_COUNT', command(['getconf','_NPROCESSORS_ONLN']))
print('LOAD', Path('/proc/loadavg').read_text().split()[:3])
for unit in ['pi-central.service','opencode-gateway.service','opencode-gateway-test.service','opencode-preview-worker-test.service','opencode-preview-docker-test.service','docker.service']:
    print('UNIT', unit, command(['systemctl','show',unit,'--property=LoadState,ActiveState,SubState,MemoryCurrent,CPUQuotaPerSecUSec,FragmentPath,WorkingDirectory,User']))
for path in ['/run/preview-worker/docker.sock','/opt/opencode-preview-test/app/services/preview_worker_server.py','/etc/opencode-preview-worker-test.env']:
    p=Path(path); print('PATH',path,'exists',p.exists(),'socket',p.is_socket())
for filename in ['/home/tahir/opencode-gateway/.env','/home/tahir/opencode-gateway-test/.env','/etc/opencode-preview-worker-test.env']:
    p=Path(filename)
    if not p.is_file(): continue
    rows={}
    for line in p.read_text().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            k,v=line.split('=',1); rows[k.strip()]=v.strip().strip('\"').strip("'")
    safe={k:rows.get(k) for k in ['PREVIEW_WORKER_ENABLED','PREVIEW_WORKER_URL','PREVIEW_PUBLIC_ORIGIN','PUBLIC_BASE_URL','APP_PORT','PREVIEW_IMAGE_NODE','PREVIEW_IMAGE_PYTHON'] if k in rows}
    safe['worker_token_present']=len(rows.get('PREVIEW_WORKER_TOKEN',''))>=32
    print('CONFIG',filename,json.dumps(safe))
nginx=command(['/usr/sbin/nginx','-T'])
print('NGINX_PREVIEW')
for line in nginx.splitlines():
    if ('configuration file' in line and 'preview' in line) or ('server_name' in line and ('preview' in line or 'opencode' in line)):
        print(line.strip())
if Path('/run/preview-worker/docker.sock').is_socket() and shutil.which('docker'):
    prefix=['runuser','-u','preview-worker','--','env','HOME=/var/lib/preview-worker','DOCKER_HOST=unix:///run/preview-worker/docker.sock','docker']
    print('PREVIEW_CONTAINERS',command(prefix+['ps','--all','--format','{{.Names}} {{.State}} {{.Image}}']))
    print('PREVIEW_IMAGES',command(prefix+['images','--digests','--format','{{.Repository}}:{{.Tag}} {{.Digest}} {{.Size}}']))
print('READ_ONLY_INVENTORY_COMPLETE')
PY
