#!/usr/bin/env bash
# Code-only extension of the existing worker and Gateway. No env/DB/Pi changes.
set -euo pipefail
umask 077
[[ $(id -u) -eq 0 ]] || exit 1
python3 - <<'PY'
from pathlib import Path
from datetime import datetime,timezone
import base64,io,json,os,shutil,subprocess,tarfile,time,uuid
from urllib.request import Request,urlopen
from urllib.error import HTTPError
stage=Path('/home/tahir/preview-activation')
app=Path('/home/tahir/opencode-gateway')
worker=Path('/opt/opencode-preview-test')
docker=['runuser','-u','preview-worker','--','env','HOME=/var/lib/preview-worker','DOCKER_HOST=unix:///run/preview-worker/docker.sock','docker']
if subprocess.check_output(docker+['ps','--quiet','--filter','label=opencode.preview.managed=true'],text=True).strip():
 raise SystemExit('A dynamic preview is active; code activation did not start')
modules=['preview_static_artifact.py','preview_worker_server.py','preview_runner.py','preview_worker_client.py']
backup=Path('/var/backups/opencode-preview-activation')/datetime.now(timezone.utc).strftime('react-%Y%m%dT%H%M%S%fZ')
backup.mkdir(parents=True,mode=0o700)
changes=[]
for target in [app/'backend/app/services',worker/'app/services']:
 for name in modules:
  destination=target/name
  copy=backup/str(len(changes))
  existed=destination.exists()
  if existed:shutil.copy2(destination,copy)
  changes.append((stage/'backend/app/services'/name,destination,copy,existed))
changes.append((stage/'dashboards.js',app/'dashboards.js',backup/'dashboards.js',True))
shutil.copy2(app/'dashboards.js',backup/'dashboards.js')
try:
 subprocess.run(['systemctl','stop','opencode-preview-worker-test.service'],check=True)
 for source,destination,copy,existed in changes:shutil.copy2(source,destination)
 subprocess.run(['systemctl','start','opencode-preview-worker-test.service'],check=True)
 subprocess.run(['systemctl','restart','opencode-gateway.service'],check=True)
 for attempt in range(20):
  try:
   with urlopen(Request('http://127.0.0.1:8000/api/health',headers={'Host':'opencode-gateway.codes'}),timeout=3) as response:
    if response.status==200:break
  except OSError:time.sleep(1)
 else:raise RuntimeError('Gateway health check failed')
 # Exercise the exact private static lifecycle. This fixture contains no customer data.
 values={}
 for row in Path('/etc/opencode-preview-worker-test.env').read_text().splitlines():
  if '=' in row and not row.startswith('#'):
   key,value=row.split('=',1);values[key]=value.strip().strip('"').strip("'")
 token=values['PREVIEW_WORKER_TOKEN'];job='static-acceptance-'+uuid.uuid4().hex[:12]
 def call(op,**extra):
  req=Request('http://127.0.0.1:8791/v1/'+op,data=json.dumps({'job_id':job,**extra}).encode(),headers={'Authorization':'Bearer '+token})
  with urlopen(req,timeout=60) as response:return json.load(response)
 stream=io.BytesIO()
 with tarfile.open(fileobj=stream,mode='w') as tar:
  for name,body in [('dist/index.html',b'<h1>Static acceptance</h1><script type="module" src="/assets/app.js"></script>'),('dist/assets/app.js',b'console.log("static acceptance")')]:
   item=tarfile.TarInfo(name);item.size=len(body);tar.addfile(item,io.BytesIO(body))
 try:
  assert call('prepare',framework='vite',prebuilt_static=True,archive=base64.b64encode(stream.getvalue()).decode())['state']=='ready'
  started=call('start');assert started['state']=='running' and started['execution_enabled'] is False
  status=call('status');lease=status['browser_lease'];assert len(lease)==64
  result=call('fetch',path='/assets/app.js',browser_lease=lease)
  assert result['status']==200 and base64.b64decode(result['body'])==b'console.log("static acceptance")'
  assert not subprocess.check_output(docker+['ps','--quiet','--filter','label=opencode.preview.managed=true'],text=True).strip()
  print('Prebuilt static HTTP assets with no application container: PASS',flush=True)
 finally:
  assert call('stop')['state']=='stopped'
 subprocess.run(['systemctl','is-active','--quiet','pi-central.service'],check=True)
 print('Existing worker and LIVE React artifact preview activated; Pi unchanged',flush=True)
except Exception:
 for source,destination,copy,existed in changes:
  if existed:shutil.copy2(copy,destination)
  else:destination.unlink(missing_ok=True)
 subprocess.run(['systemctl','restart','opencode-preview-worker-test.service'],check=False)
 subprocess.run(['systemctl','restart','opencode-gateway.service'],check=False)
 print('React code activation rolled back',flush=True)
 raise
PY
