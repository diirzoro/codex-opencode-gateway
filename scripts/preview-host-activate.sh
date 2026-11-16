#!/usr/bin/env bash
# Connect LIVE to the prepared existing worker and existing preview hostname.
set -euo pipefail
umask 077
[[ $(id -u) -eq 0 ]] || exit 1
STAGE=/home/tahir/preview-activation
APP=/home/tahir/opencode-gateway
systemctl is-active --quiet pi-central.service
systemctl is-active --quiet opencode-gateway.service
systemctl is-active --quiet opencode-preview-worker-test.service
systemctl is-active --quiet opencode-preview-docker-test.service
# One-time operator helper, never part of model/chat execution.
python3 - <<'PY'
from pathlib import Path
from datetime import datetime, timezone
import json,os,re,shutil,subprocess,tempfile,time
from urllib.request import Request,urlopen
from urllib.error import HTTPError
app=Path('/home/tahir/opencode-gateway')
stage=Path('/home/tahir/preview-activation')
worker_env=Path('/etc/opencode-preview-worker-test.env')
def env(path):
 result={}
 for line in path.read_text().splitlines():
  if '=' in line and not line.lstrip().startswith('#'):
   k,v=line.split('=',1); result[k.strip()]=v.strip().strip('"').strip("'")
 return result
live=env(app/'.env'); test=env(Path('/home/tahir/opencode-gateway-test/.env'))
assert live.get('PUBLIC_BASE_URL')=='https://opencode-gateway.codes'
assert test.get('PREVIEW_WORKER_ENABLED') not in {'test','live'}, 'TEST preview already enabled; refuse route takeover'
credentials=env(worker_env); token=credentials['PREVIEW_WORKER_TOKEN']; assert len(token)>=32
req=Request('http://127.0.0.1:8791/v1/status',data=b'{"job_id":"activation-readiness"}',headers={'Authorization':'Bearer '+token})
try:
 urlopen(req,timeout=10); raise AssertionError('Unexpected readiness response')
except HTTPError as exc:
 assert exc.code==404 and json.load(exc)['error']=='unregistered_job'
# Reuse the known existing preview TLS host; no DNS, certificates or new service.
vhost=Path('/etc/nginx/sites-enabled/zz-opencode-preview-test').resolve(strict=True)
original=vhost.read_text()
assert 'preview-test.opencode-gateway.codes' in original
assert 'proxy_pass http://127.0.0.1:8001' in original or 'proxy_pass http://127.0.0.1:8000' in original
updated=original.replace('proxy_pass http://127.0.0.1:8001','proxy_pass http://127.0.0.1:8000')
# Fail before changing anything if active TLS cannot validate this hostname.
import ssl,socket
with socket.create_connection(('127.0.0.1',443),timeout=5) as raw:
 with ssl.create_default_context().wrap_socket(raw,server_hostname='preview-test.opencode-gateway.codes'):
  pass
backup=Path('/var/backups/opencode-preview-activation')/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
backup.mkdir(parents=True,mode=0o700)
modules=['preview_runner.py','preview_worker_client.py','preview_container_spec.py','preview_worker_server.py','preview_docker_provisioner.py']
shutil.copy2(app/'.env',backup/'gateway.env')
shutil.copy2(vhost,backup/'preview-nginx.conf')
for name in modules:
 shutil.copy2(app/'backend/app/services'/name,backup/name)
def atomic(path,text):
 stat=path.stat(); fd,temp=tempfile.mkstemp(dir=path.parent,prefix='.preview-')
 try:
  with os.fdopen(fd,'w') as f: f.write(text); f.flush(); os.fsync(f.fileno())
  os.chmod(temp,stat.st_mode & 0o777); os.chown(temp,stat.st_uid,stat.st_gid); os.replace(temp,path)
 finally:
  if os.path.exists(temp): os.unlink(temp)
try:
 changes={'PREVIEW_WORKER_ENABLED':'live','PREVIEW_WORKER_URL':'http://127.0.0.1:8791','PREVIEW_WORKER_TOKEN':token,'PREVIEW_PUBLIC_ORIGIN':'https://preview-test.opencode-gateway.codes'}
 lines=(app/'.env').read_text().splitlines(); seen=set(); out=[]
 for line in lines:
  key=line.split('=',1)[0].strip() if '=' in line and not line.lstrip().startswith('#') else ''
  if key in changes:
   assert key not in seen, 'Duplicate preview environment setting'
   out.append(key+'='+changes[key]); seen.add(key)
  else: out.append(line)
 out.extend(key+'='+value for key,value in changes.items() if key not in seen)
 for name in modules:
  shutil.copy2(stage/'backend/app/services'/name,app/'backend/app/services'/name)
 atomic(app/'.env','\n'.join(out)+'\n')
 atomic(vhost,updated)
 subprocess.run(['/usr/sbin/nginx','-t'],check=True)
 subprocess.run(['systemctl','restart','opencode-gateway.service'],check=True)
 for attempt in range(20):
  try:
   with urlopen('http://127.0.0.1:8000/api/health',timeout=3) as response:
    if response.status==200: break
  except OSError: time.sleep(1)
 else: raise RuntimeError('Gateway health failed')
 subprocess.run(['systemctl','reload','nginx'],check=True)
 subprocess.run(['systemctl','is-active','--quiet','pi-central.service'],check=True)
 print('LIVE preview configuration activated; existing Pi service unchanged')
except Exception:
 shutil.copy2(backup/'gateway.env',app/'.env')
 shutil.copy2(backup/'preview-nginx.conf',vhost)
 for name in modules: shutil.copy2(backup/name,app/'backend/app/services'/name)
 subprocess.run(['systemctl','restart','opencode-gateway.service'],check=False)
 subprocess.run(['/usr/sbin/nginx','-t'],check=True)
 subprocess.run(['systemctl','reload','nginx'],check=False)
 print('Activation rolled back to original Gateway and preview configuration')
 raise
PY
bash "$STAGE/scripts/preview-host-inspect.sh"
