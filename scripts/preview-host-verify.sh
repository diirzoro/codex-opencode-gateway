#!/usr/bin/env bash
# Real tiny isolated HTTP smoke; no Gateway/Pi changes.
set -euo pipefail
umask 077
[[ $(id -u) -eq 0 ]] || exit 1
ENVFILE=/etc/opencode-preview-worker-test.env
# Authenticated protocol check without logging credentials.
python3 - "$ENVFILE" <<'PY'
import json,sys
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
rows=dict(line.split('=',1) for line in Path(sys.argv[1]).read_text().splitlines() if '=' in line and not line.startswith('#'))
token=rows['PREVIEW_WORKER_TOKEN'].strip().strip('"').strip("'")
import subprocess
prefix=['runuser','-u','preview-worker','--','env','HOME=/var/lib/preview-worker','DOCKER_HOST=unix:///run/preview-worker/docker.sock','docker']
subprocess.run(prefix+['run','--rm','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--security-opt','apparmor=opencode-preview','--memory','768m','--cpus','0.5',rows['PREVIEW_IMAGE_PYTHON'],'python','-c','import fastapi,uvicorn; print("Non-root immutable Python runtime imports: OK")'],check=True,timeout=45)
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
 try:
  with urlopen(req,timeout=90) as response: return json.load(response)
 except HTTPError as exc:
  payload=json.loads(exc.read(2048))
  print('Runtime smoke operation failed:',operation,'HTTP',exc.code,'code',payload.get('error'),'reference',payload.get('reference'))
  raise
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
 mounts=details['Mounts']
 binds=[mount for mount in mounts if mount['Type']=='bind']
 assert len(binds)==1 and binds[0]['Destination']=='/workspace' and binds[0]['RW'] is False
 assert all(mount['Type']=='bind' or (mount['Type']=='tmpfs' and mount['Destination']=='/tmp') for mount in mounts)
 print('Runtime identity, mounts, network, AppArmor and resource limits: OK')
 result=call('fetch',{'path':'/'})
 assert result['status']==200 and json.loads(base64.b64decode(result['body']))['runtime']=='python'
 print('Real isolated Python runtime HTTP smoke: OK')
finally:
 assert call('stop',{})['state']=='stopped'
print('Runtime stopped after smoke: OK')
proof=Path('/var/lib/opencode-preview-activation')
proof.mkdir(mode=0o700,exist_ok=True)
(proof/'verified.json').write_text(json.dumps({'image':rows['PREVIEW_IMAGE_PYTHON'],'verified_at':time.time()}))
PY
