#!/usr/bin/env bash
# Enable automatic builds globally using the existing cached Node runtime.
set -euo pipefail
umask 077
[[ $(id -u) -eq 0 ]] || exit 1
python3 - <<'PY'
from pathlib import Path
from datetime import datetime,timezone
import base64,io,json,os,re,shutil,subprocess,tarfile,tempfile,time,uuid,sys
from urllib.request import Request,urlopen
from urllib.error import HTTPError
stage=Path('/home/tahir/preview-activation');app=Path('/home/tahir/opencode-gateway');worker=Path('/opt/opencode-preview-test')
docker=['runuser','-u','preview-worker','--','env','HOME=/var/lib/preview-worker','DOCKER_HOST=unix:///run/preview-worker/docker.sock','docker']
if subprocess.check_output(docker+['ps','--quiet','--filter','label=opencode.preview.managed=true'],text=True).strip():
 raise SystemExit('Active dynamic preview; build activation refused')
if shutil.disk_usage('/var/lib/preview-worker').free<6*1024**3:raise SystemExit('Insufficient disk reserve')
values={}
for row in Path('/etc/opencode-preview-worker-test.env').read_text().splitlines():
 if '=' in row and not row.startswith('#'):
  key,value=row.split('=',1);values[key]=value.strip().strip('"').strip("'")
image=values.get('PREVIEW_IMAGE_NODE','')
if not re.fullmatch(r'(?:[a-z0-9._/-]+@)?sha256:[0-9a-f]{64}',image):raise SystemExit('Pinned Node runtime required')
subprocess.run(docker+['image','inspect',image],stdout=subprocess.DEVNULL,check=True)
backup=Path('/var/backups/opencode-preview-activation')/datetime.now(timezone.utc).strftime('react-build-%Y%m%dT%H%M%S%fZ')
backup.mkdir(parents=True,mode=0o700)
env=app/'.env';shutil.copy2(env,backup/'gateway.env')
index=app/'index.html';shutil.copy2(index,backup/'index.html')
asset_pattern=r'(src=["\x27](?:/)?dashboards\.js\?v=)[^"\x27]+'
original_asset=re.search(asset_pattern,index.read_text()).group(0)
modules=['preview_npm_cache.py','preview_react_build.py','preview_worker_server.py',
 'preview_runner.py','preview_container_spec.py','preview_docker_provisioner.py',
 'preview_snapshot.py','preview_worker_archive.py']
changes=[]
for target in [app/'backend/app/services',worker/'app/services']:
 for name in modules:
  destination=target/name;old=backup/str(len(changes));existed=destination.exists()
  if existed:shutil.copy2(destination,old)
  changes.append((stage/'backend/app/services'/name,destination,old,existed))
shutil.copy2(app/'dashboards.js',backup/'dashboards.js')
changes.append((stage/'dashboards.js',app/'dashboards.js',backup/'dashboards.js',True))
job='react-build-acceptance-'+uuid.uuid4().hex[:10]
def call(operation,**extra):
 req=Request('http://127.0.0.1:8791/v1/'+operation,
  data=json.dumps({'job_id':job,**extra}).encode(),headers={'Authorization':'Bearer '+values['PREVIEW_WORKER_TOKEN']})
 try:
  with urlopen(req,timeout=75) as response:return json.load(response)
 except HTTPError as exc:
  try:error=json.loads(exc.read(4096)).get('error','unknown')
  except ValueError:error='unknown'
  print('Controlled React fixture operation failed: '+operation+' '+str(error),flush=True)
  raise
try:
 subprocess.run(['systemctl','stop','opencode-preview-worker-test.service'],check=True)
 for source,destination,old,existed in changes:shutil.copy2(source,destination)
 lines=[row for row in env.read_text().splitlines() if not row.startswith('PREVIEW_REACT_BUILD_ENABLED=')]
 env.write_text('\n'.join(lines+['PREVIEW_REACT_BUILD_ENABLED=1'])+'\n')
 html,count=re.subn(asset_pattern,lambda match:match[1]+'20261117-react-autobuild-v1',index.read_text())
 if count!=1:raise RuntimeError('Unexpected frontend asset reference')
 index.write_text(html)
 subprocess.run(['systemctl','start','opencode-preview-worker-test.service'],check=True)
 subprocess.run(['systemctl','restart','opencode-gateway.service'],check=True)
 for attempt in range(20):
  try:
   with urlopen(Request('http://127.0.0.1:8000/api/health',headers={'Host':'opencode-gateway.codes'}),timeout=3) as response:
    if response.status==200:break
  except OSError:time.sleep(1)
 else:raise RuntimeError('Gateway health check failed')
 pid=subprocess.check_output(['systemctl','show','opencode-gateway.service','--property=MainPID','--value'],text=True).strip()
 if b'PREVIEW_REACT_BUILD_ENABLED=1' not in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0'):
  raise RuntimeError('Global preview build flag was not loaded')
 # Only generated public fixture source is used; no customer workspace is read.
 files={name:(stage/'preview-react-fixture'/name).read_bytes() for name in ['package.json','package-lock.json']}
 files['index.html']=b'<div id="root"></div><script type="module" src="/src/main.jsx"></script>'
 files['src/main.jsx']=b'''import React from 'react';import {createRoot} from 'react-dom/client';function App(){const [n,setN]=React.useState(0);return <main><h1>Automatic React Build Test</h1><button onClick={()=>setN(n+1)}>Count: {n}</button></main>}createRoot(document.getElementById('root')).render(<App/>);'''
 stream=io.BytesIO()
 with tarfile.open(fileobj=stream,mode='w') as archive:
  for name,body in files.items():
   item=tarfile.TarInfo(name);item.size=len(body);archive.addfile(item,io.BytesIO(body))
 snapshot=stream.getvalue()
 sys.path.insert(0,str(worker))
 from app.services import preview_npm_cache
 # Operator cache is temporary and distinct from the Gateway service-user cache.
 with tempfile.TemporaryDirectory(prefix='pi-react-public-acceptance-') as cache:
  packages=preview_npm_cache.prepare(snapshot,cache_root=Path(cache))
  try:
   assert call('prepare',framework='vite',build_static=True,packages=packages,archive=base64.b64encode(snapshot).decode())['state']=='ready'
   assert call('start')['state']=='building'
   for attempt in range(150):
    status=call('status')
    if status['state']!='building':break
    time.sleep(1)
   if status['state']!='running':
    print('Generated React fixture logs: '+call('logs').get('logs','')[-5000:],flush=True)
    raise RuntimeError('Controlled React build did not complete')
   assert status['mode']=='built_static' and status['browser_lease']
   result=call('fetch',path='/',browser_lease=status['browser_lease'])
   html=base64.b64decode(result['body']).decode();assert result['status']==200 and 'assets/' in html
   asset=re.search(r'src="([^\"]+\.js)"',html).group(1)
   result=call('fetch',path='/'+asset.removeprefix('./').lstrip('/'),browser_lease=status['browser_lease'])
   assert result['status']==200 and b'Automatic React Build Test' in base64.b64decode(result['body'])
   assert not subprocess.check_output(docker+['ps','--quiet','--filter','label=opencode.preview.managed=true'],text=True).strip()
   print('Real React/Vite offline install, build, static assets and stopped build container: PASS',flush=True)
  finally:assert call('stop')['state']=='stopped'
 subprocess.run(['systemctl','is-active','--quiet','pi-central.service'],check=True)
 print('Automatic React builds enabled globally; existing Pi and database unchanged',flush=True)
except Exception:
 subprocess.run(['systemctl','stop','opencode-preview-worker-test.service'],check=False)
 old_flag=[row for row in (backup/'gateway.env').read_text().splitlines() if row.startswith('PREVIEW_REACT_BUILD_ENABLED=')]
 current=[row for row in env.read_text().splitlines() if not row.startswith('PREVIEW_REACT_BUILD_ENABLED=')]
 env.write_text('\n'.join(current+old_flag)+'\n')
 index.write_text(re.sub(asset_pattern,lambda match:original_asset,index.read_text()))
 for source,destination,old,existed in changes:
  if existed:shutil.copy2(old,destination)
  else:destination.unlink(missing_ok=True)
 subprocess.run(['systemctl','restart','opencode-preview-worker-test.service'],check=False)
 subprocess.run(['systemctl','restart','opencode-gateway.service'],check=False)
 print('Automatic React build activation rolled back',flush=True)
 raise
PY
