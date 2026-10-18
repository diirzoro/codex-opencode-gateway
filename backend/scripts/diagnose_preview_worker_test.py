#!/usr/bin/env python3
"""TEST-only diagnostic; no configuration edits or host app execution.

Default is read-only. --smoke explicitly prepares, starts, fetches and stops
one new disposable Node job through the authenticated loopback Worker API.
No secrets, raw Docker output or customer files are printed.
"""
import argparse
import base64
import io
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import tarfile
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.preview_worker_client import PreviewWorkerClient, PreviewWorkerUnavailable
from app.services.preview_diagnostics import docker_failure_code


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke',action='store_true')
    args=parser.parse_args()
    envfile=Path('/etc/opencode-preview-worker-test.env')
    try:
        config={}
        for line in envfile.read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                key,value=line.split('=',1);config[key]=value.strip().strip('"').strip("'")
        client=PreviewWorkerClient('http://127.0.0.1:8791',config.get('PREVIEW_WORKER_TOKEN',''))
        user=pwd.getpwuid(os.geteuid()).pw_name
        if user not in ('root','preview-worker'):
            raise ValueError('Run as root or preview-worker on TEST')
    except (OSError,ValueError,PreviewWorkerUnavailable) as exc:
        print('Preflight unavailable:',type(exc).__name__);return 1
    print('TEST worker endpoint: 127.0.0.1:8791; caller:',user)
    print('Worker token: configured (value hidden)')
    docker=['/usr/bin/docker']
    safe_env={'PATH':'/usr/bin:/bin','HOME':'/var/lib/preview-worker',
              'DOCKER_HOST':'unix:///run/preview-worker/docker.sock'}
    if user=='root':
        docker=['/usr/sbin/runuser','-u','preview-worker','--','env','-i',
                *[k+'='+v for k,v in safe_env.items()],*docker]
    def run(label,argv):
        try:
            result=subprocess.run([*docker,*argv],env=safe_env,capture_output=True,text=True,timeout=15)
            if result.returncode:
                print(label+': '+docker_failure_code(result.stderr));return False
            print(label+': OK');return True
        except (OSError,subprocess.TimeoutExpired) as exc:
            print(label+': '+type(exc).__name__);return False
    ok=run('Dedicated rootless Docker access',['info','--format','{{.ServerVersion}}'])
    # Inspect presence only; never pull, rebuild, alter the daemon or print env.
    for family in ('NODE','PYTHON','PHP'):
        image=config.get('PREVIEW_IMAGE_'+family,'')
        if '@sha256:' not in image:
            print(family+' image: pinned image not configured');ok=False;continue
        ok=run(family+' pinned image',['image','inspect',image,'--format','{{.Id}}']) and ok
    root=Path('/var/lib/preview-worker/jobs')
    print('Worker jobs directory exists:',root.is_dir())
    try:
        client.request('status',{'job_id':'preview-diagnostic-unregistered'})
        print('Loopback authentication: unexpected existing probe job')
    except PreviewWorkerUnavailable as exc:
        if 'unregistered_job' in str(exc):print('Loopback authentication: OK')
        else:print(str(exc));return 1
    if not args.smoke:return 0 if ok else 1
    if not ok:
        print('Smoke blocked by failed preflight; no sandbox started');return 1
    job='diagnostic-'+uuid.uuid4().hex[:16]
    source=b"const http=require('http');http.createServer((q,r)=>{const css=q.url==='/style.css';r.setHeader('Content-Type',css?'text/css':'text/html');r.end(css?'body{color:green}':'<!doctype html><title>Preview worker smoke</title><link rel=stylesheet href=style.css><h1>PREVIEW_SMOKE_OK</h1>')}).listen(Number(process.env.PORT),'0.0.0.0');"
    archive=io.BytesIO()
    with tarfile.open(fileobj=archive,mode='w') as tar:
        member=tarfile.TarInfo('server.js');member.size=len(source);tar.addfile(member,io.BytesIO(source))
    prepared=False;failed=False
    try:
        response=client.request('prepare',{'job_id':job,'framework':'node','entrypoint':'server.js','archive':base64.b64encode(archive.getvalue()).decode()})
        if response.get('state')!='ready':raise ValueError('prepare did not confirm ready')
        prepared=True;print('Real prepare: OK')
        response=client.request('start',{'job_id':job})
        if response.get('state')!='running':raise ValueError('start did not confirm running')
        print('Real container start/readiness: OK')
        for path,marker in (('/',b'PREVIEW_SMOKE_OK'),('/style.css',b'body{color:green}'),('/nested/route',b'PREVIEW_SMOKE_OK')):
            response=client.request('fetch',{'job_id':job,'path':path})
            if response.get('status')!=200 or marker not in base64.b64decode(response['body'],validate=True):raise ValueError('fixture resource mismatch')
            print('Application resource '+path+': OK')
    except PreviewWorkerUnavailable as exc:
        failed=True;print(str(exc))
    except (ValueError,KeyError,TypeError):
        failed=True;print('Smoke response did not match the fixed fixture contract')
    finally:
        if prepared:
            try:
                stopped=client.request('stop',{'job_id':job})
                if stopped.get('state')!='stopped':raise ValueError('stop not confirmed')
                print('Owned smoke Stop: OK')
            except (PreviewWorkerUnavailable,ValueError) as exc:
                failed=True;print('Owned smoke cleanup not confirmed:',type(exc).__name__)
    print('This checks worker HTTP execution, not browser routing, framework builds or production readiness.')
    return 1 if failed else 0

if __name__=='__main__':raise SystemExit(main())
