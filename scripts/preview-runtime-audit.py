"""Controlled worker isolation/capacity/timer audit; no customer projects.

Run through the protected operator workflow only. Timers run on the CI job;
no new service, Gateway restart, model prompt or customer code is involved.
"""
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from urllib.request import Request,urlopen
from urllib.error import HTTPError


def archive(source):
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w') as tar:
        member=tarfile.TarInfo('main.py');member.size=len(source)
        tar.addfile(member,io.BytesIO(source))
    return base64.b64encode(stream.getvalue()).decode()


def probe_source(canary,other):
    return ('from fastapi import FastAPI\nfrom pathlib import Path\nimport os\napp=FastAPI()\n'
       '@app.get("/")\ndef health():\n'
       ' return {"ok":True,"uid":os.getuid(),"host_canary_hidden":not Path('+repr(canary)+').exists(),'
       '"other_snapshot_hidden":not Path('+repr(other)+').exists(),'
       '"docker_socket_hidden":not Path("/run/preview-worker/docker.sock").exists(),'
       '"source_read_only":bool(os.statvfs("/workspace").f_flag & os.ST_RDONLY),'
       '"root_read_only":bool(os.statvfs("/").f_flag & os.ST_RDONLY),'
       '"memory_max":Path("/sys/fs/cgroup/memory.max").read_text().strip(),'
       '"cpu_max":Path("/sys/fs/cgroup/cpu.max").read_text().strip(),'
       '"pids_max":Path("/sys/fs/cgroup/pids.max").read_text().strip(),'
       '"apparmor":Path("/proc/self/attr/current").read_text().strip()}\n').encode()


def main():
    if os.geteuid()!=0: raise SystemExit('Protected operator context required')
    docker=['runuser','-u','preview-worker','--','env','HOME=/var/lib/preview-worker',
            'DOCKER_HOST=unix:///run/preview-worker/docker.sock','docker']
    running=subprocess.check_output(docker+['ps','--quiet','--filter','label=opencode.preview.managed=true'],text=True).strip()
    if running: raise SystemExit('Another preview is active; audit did not start')
    rows={}
    for line in Path('/etc/opencode-preview-worker-test.env').read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            key,value=line.split('=',1);rows[key]=value.strip().strip('"').strip("'")
    token=rows['PREVIEW_WORKER_TOKEN']
    jobs=['preview-audit-'+uuid.uuid4().hex[:16] for _ in range(2)]
    registered=[]
    def call(op,job,**extra):
        req=Request('http://127.0.0.1:8791/v1/'+op,
            data=json.dumps({'job_id':job,**extra}).encode(),
            headers={'Authorization':'Bearer '+token})
        with urlopen(req,timeout=90) as response:return json.load(response)
    def prepare(job,source):
        assert call('prepare',job,framework='python',entrypoint='main.py',archive=archive(source))['state']=='ready'
        registered.append(job)
    fd,canary=tempfile.mkstemp(prefix='controlled-preview-canary-',dir='/var/lib/preview-worker')
    os.close(fd)
    Path(canary).write_text(uuid.uuid4().hex)
    other='/var/lib/preview-worker/jobs/'+jobs[1]+'/src/main.py'
    source=probe_source(canary,other)
    try:
        prepare(jobs[1],b'from fastapi import FastAPI\napp=FastAPI()\n')
        prepare(jobs[0],source)
        assert call('start',jobs[0])['state']=='running'
        response=call('fetch',jobs[0],path='/')
        report=json.loads(base64.b64decode(response['body']))
        assert response['status']==200 and report['ok']
        assert report['uid']==10001 and report['apparmor']=='opencode-preview (enforce)'
        assert all(report[key] for key in ['host_canary_hidden','other_snapshot_hidden','docker_socket_hidden','source_read_only','root_read_only'])
        assert int(report['memory_max'])==768*1024*1024 and int(report['pids_max'])==128
        quota,period=map(int,report['cpu_max'].split());assert 0<quota/period<=0.5
        print('Controlled runtime filesystem isolation and actual kernel resource limits: PASS',flush=True)
        try:
            call('start',jobs[1])
            raise AssertionError('Concurrent dynamic preview was admitted')
        except HTTPError as error:
            assert error.code==409 and json.load(error)['error']=='preview_capacity_reached'
        print('Second dynamic preview refused: PASS',flush=True)
        if '--timers' in sys.argv:
            deadline=time.monotonic()+325
            while time.monotonic()<deadline:
                state=call('status',jobs[0])
                if state['state']=='stopped':break
                time.sleep(5)
            assert state['state']=='stopped' and state['stop_reason']=='idle_timeout'
            print('Real idle expiry without activity renewal: PASS',flush=True)
            prepare(jobs[0],source)
            assert call('start',jobs[0])['state']=='running'
            deadline=time.monotonic()+925
            while time.monotonic()<deadline:
                state=call('status',jobs[0],user_activity=True)
                if state['state']=='stopped':break
                time.sleep(5)
            assert state['state']=='stopped' and state['stop_reason']=='runtime_limit'
            print('Real absolute runtime expiry despite explicit activity: PASS',flush=True)
        print('No real customer files or accounts were used by this audit.',flush=True)
    finally:
        for job in set(registered):
            try:call('stop',job)
            except (OSError,ValueError):print('Controlled audit cleanup needs operator review',flush=True)
        Path(canary).unlink(missing_ok=True)

if __name__=='__main__':main()
