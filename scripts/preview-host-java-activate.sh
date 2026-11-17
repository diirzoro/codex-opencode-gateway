#!/usr/bin/env bash
# Extend only the existing worker; no database, Pi, nginx or Docker restart.
set -euo pipefail
umask 077
[[ $(id -u) -eq 0 ]] || exit 1
STAGE=/home/tahir/preview-activation
docker_preview() {
  runuser -u preview-worker -- env HOME=/var/lib/preview-worker DOCKER_HOST=unix:///run/preview-worker/docker.sock docker "$@"
}
[[ -z $(docker_preview ps --quiet --filter label=opencode.preview.managed=true) ]] || { echo 'Active preview; activation refused'; exit 1; }
[[ $(df --output=avail -BM /var/lib/preview-worker | tail -1 | tr -dc '0-9') -ge 6144 ]] || { echo 'Insufficient disk reserve'; exit 1; }
# Runtime is prepared by Actions; the dedicated daemon retains its closed network.
expected_hash=$(cat "$STAGE/preview-java-runtime.sha256")
[[ "$expected_hash" =~ ^[0-9a-f]{64}$ ]] || exit 1
actual_hash=$(sha256sum "$STAGE/preview-java-runtime.tar.gz");actual_hash=${actual_hash%% *}
[[ "$actual_hash" == "$expected_hash" ]] || { echo 'Runtime archive checksum mismatch'; exit 1; }
expected_image=$(cat "$STAGE/preview-java-runtime.id")
[[ "$expected_image" =~ ^sha256:[0-9a-f]{64}$ ]] || exit 1
timeout 300 runuser -u preview-worker -- env HOME=/var/lib/preview-worker DOCKER_HOST=unix:///run/preview-worker/docker.sock docker load < "$STAGE/preview-java-runtime.tar.gz"
export PREVIEW_JAVA_RUNTIME_IMAGE
PREVIEW_JAVA_RUNTIME_IMAGE=$(docker_preview image inspect --format '{{.Id}}' opencode-preview-java:21)
[[ "$PREVIEW_JAVA_RUNTIME_IMAGE" == "$expected_image" ]] || exit 1
python3 - <<'PY'
from pathlib import Path
from datetime import datetime,timezone
import base64,io,json,os,shutil,subprocess,tarfile,time,uuid
from urllib.request import Request,urlopen
stage=Path('/home/tahir/preview-activation')
app=Path('/home/tahir/opencode-gateway')
worker=Path('/opt/opencode-preview-test')
env=Path('/etc/opencode-preview-worker-test.env')
backup=Path('/var/backups/opencode-preview-activation')/datetime.now(timezone.utc).strftime('java-%Y%m%dT%H%M%S%fZ')
backup.mkdir(parents=True,mode=0o700)
shutil.copy2(env,backup/'worker.env')
modules=['preview.py','preview_static_artifact.py','preview_worker_server.py','preview_runner.py',
         'preview_worker_client.py','preview_docker_provisioner.py','preview_launch_profiles.py','preview_scheduling.py']
changes=[]
for target in [app/'backend/app/services',worker/'app/services']:
 for name in modules:
  dest=target/name;old=backup/str(len(changes));existed=dest.exists()
  if existed:shutil.copy2(dest,old)
  changes.append((stage/'backend/app/services'/name,dest,old,existed))
job='java-acceptance-'+uuid.uuid4().hex[:12]
values={row.split('=',1)[0]:row.split('=',1)[1].strip().strip('"').strip("'") for row in env.read_text().splitlines() if '=' in row and not row.startswith('#')}
def call(op,**extra):
 req=Request('http://127.0.0.1:8791/v1/'+op,data=json.dumps({'job_id':job,**extra}).encode(),headers={'Authorization':'Bearer '+values['PREVIEW_WORKER_TOKEN']})
 with urlopen(req,timeout=75) as response:return json.load(response)
try:
 subprocess.run(['systemctl','stop','opencode-preview-worker-test.service'],check=True)
 for source,dest,old,existed in changes:shutil.copy2(source,dest)
 lines=[row for row in env.read_text().splitlines() if not row.startswith('PREVIEW_IMAGE_JAVA=')]
 env.write_text('\n'.join(lines+['PREVIEW_IMAGE_JAVA='+os.environ['PREVIEW_JAVA_RUNTIME_IMAGE']])+'\n');env.chmod(0o600)
 subprocess.run(['systemctl','start','opencode-preview-worker-test.service'],check=True)
 subprocess.run(['systemctl','restart','opencode-gateway.service'],check=True)
 for attempt in range(20):
  try:
   with urlopen(Request('http://127.0.0.1:8000/api/health',headers={'Host':'opencode-gateway.codes'}),timeout=3) as response:
    if response.status==200:break
  except OSError:time.sleep(1)
 else:raise RuntimeError('Gateway health check failed')
 body=b'''import com.sun.net.httpserver.HttpServer; import java.net.InetSocketAddress;
class Main {public static void main(String[] args)throws Exception {var server=HttpServer.create(new InetSocketAddress(8080),0);server.createContext("/",e->{byte[] b="<h1>Java Preview Test</h1>".getBytes();e.getResponseHeaders().set("Content-Type","text/html");e.sendResponseHeaders(200,b.length);e.getResponseBody().write(b);e.close();});server.start();}}'''
 stream=io.BytesIO()
 with tarfile.open(fileobj=stream,mode='w') as tar:
  item=tarfile.TarInfo('Main.java');item.size=len(body);tar.addfile(item,io.BytesIO(body))
 try:
  assert call('prepare',framework='java',entrypoint='Main.java',archive=base64.b64encode(stream.getvalue()).decode())['state']=='ready'
  assert call('start')['state']=='running'
  lease=call('status')['browser_lease']
  response=call('fetch',path='/',browser_lease=lease)
  assert response['status']==200 and b'Java Preview Test' in base64.b64decode(response['body'])
  print('Java source HTTP preview through fixed isolated relay: PASS',flush=True)
 finally:assert call('stop')['state']=='stopped'
 subprocess.run(['systemctl','is-active','--quiet','pi-central.service'],check=True)
 print('Existing Java worker profile activated; Pi and database unchanged',flush=True)
except Exception:
 subprocess.run(['systemctl','stop','opencode-preview-worker-test.service'],check=False)
 shutil.copy2(backup/'worker.env',env)
 for source,dest,old,existed in changes:
  if existed:shutil.copy2(old,dest)
  else:dest.unlink(missing_ok=True)
 subprocess.run(['systemctl','restart','opencode-preview-worker-test.service'],check=False)
 subprocess.run(['systemctl','restart','opencode-gateway.service'],check=False)
 print('Java activation rolled back',flush=True)
 raise
PY
