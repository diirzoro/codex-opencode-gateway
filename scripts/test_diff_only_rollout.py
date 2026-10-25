#!/usr/bin/env python3
"""Guarded TEST-only diff release; never starts/stops OpenCode or edits LIVE."""
import argparse, hashlib, json, os, pathlib, re, shutil, subprocess, tarfile, tempfile, fcntl, stat
APP=pathlib.Path('/home/tahir/opencode-gateway-test')
CONF=pathlib.Path('/etc/nginx/conf.d/opencode-native-test-session-local.conf')
BACKUPS=pathlib.Path('/home/tahir/opencode-test-diff-backups')
SERVICE='opencode-gateway-test.service'
NATIVE='opencode-native-test.service'
FILES=('app.js','dashboards.js','runtime-client.js','native-session-client.js',
'backend/app/main.py','backend/app/routes/native_sessions.py','backend/app/routes/agent.py','backend/app/services/opencode.py',
'management.js','backend/app/routes/workspaces.py','backend/app/services/native_provider_accounts.py',
'backend/app/services/github.py','backend/app/routes/admin.py','backend/app/services/native_catalog_maintenance.py',
'enhancements.js','backend/app/services/policy.py','backend/app/services/providers.py','backend/app/services/workspaces.py')
# Only the precise original TEST loopback config is eligible for this narrowly scoped
# compatibility addition. These bytes are from the owner's read-only VPS inspection.
EXPECTED_NGINX_SHA='972fa6a13833db26d0f972afe0fc7538656e4c5aad27cee9e9632a250eaf9a11'
def run(*argv):
    return subprocess.run(argv,check=True,capture_output=True,text=True,timeout=45)
def sha(data):return hashlib.sha256(data).hexdigest()
def safe_write(p,data,original=None):
    p.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.test-release-',dir=str(p.parent))
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        if original:
            os.chmod(tmp,stat.S_IMODE(original.st_mode))
            os.chown(tmp,original.st_uid,original.st_gid)
        else:
            os.chmod(tmp,0o644);os.chown(tmp,1001,1001)
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--bundle',type=pathlib.Path,required=True);ap.add_argument('--checksum',type=pathlib.Path,required=True);a=ap.parse_args()
    if os.geteuid()!=0:raise RuntimeError('Requires existing operator sudo permission')
    if not APP.is_dir() or not (APP/'.git').is_dir() or not (APP/'.env').is_file():raise RuntimeError('Not the existing TEST checkout')
    if run('systemctl','is-active',SERVICE).stdout.strip()!='active' or run('systemctl','is-active',NATIVE).stdout.strip()!='active':raise RuntimeError('Expected TEST services are not active')
    if not a.bundle.resolve().is_relative_to(pathlib.Path('/home/tahir')):raise RuntimeError('Untrusted bundle location')
    if a.bundle.is_symlink() or a.checksum.is_symlink() or a.bundle.parent!=a.checksum.parent:raise RuntimeError('Unsafe bundle path')
    expected=a.checksum.read_text().split()[0]
    if not re.fullmatch('[a-f0-9]{64}',expected) or sha(a.bundle.read_bytes())!=expected:raise RuntimeError('Bundle SHA mismatch')
    lockfd=os.open('/run/lock/opencode-test-file-rollout.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    fcntl.flock(lockfd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    native_before=run('systemctl','show','-p','MainPID','--value',NATIVE).stdout.strip()
    if not native_before or native_before=='0':raise RuntimeError('Native PID unavailable')
    data={}
    with tarfile.open(a.bundle,'r') as tf:
        members=tf.getmembers()
        if len(members)!=len(FILES) or {m.name for m in members}!=set(FILES) or any(not m.isfile() or m.issym() or m.islnk() or m.size>3_000_000 for m in members):raise RuntimeError('Unexpected archive contents')
        for member in members:data[member.name]=tf.extractfile(member).read()
    # Inspect existing local state BEFORE writes. New files are permitted; unknown
    # existing symlinks/nonregular files are not.
    differences={}
    for name,new in data.items():
        dest=APP/name
        if dest.is_symlink() or (dest.exists() and not dest.is_file()):raise RuntimeError('Unsafe target '+name)
        if dest.exists():
            old=dest.read_bytes()
            if old!=new:differences[name]=(old,dest.stat())
        else:differences[name]=(None,None)
    # Make no change if routing is outside exact previously inspected TEST config.
    oldconf=CONF.read_bytes()
    if sha(oldconf)!=EXPECTED_NGINX_SHA:
        raise RuntimeError('TEST Nginx drift or route already changed; requires new audited plan, no files updated')
    text=oldconf.decode()
    if text.count('listen 127.0.0.1:18098;')!=1 or text.count('location / { return 404; }')!=1:raise RuntimeError('Unexpected TEST loopback layout')
    auth=re.findall(r'proxy_set_header\s+Authorization\s+("Basic [A-Za-z0-9+/=]+")\s*;',text)
    if not auth or len(set(auth))!=1:raise RuntimeError('Existing Native private authorization cannot be verified')
    # Reuse the exact upstream and private header; read-only metadata only.
    addition='''    # Authorized Gateway metadata; TEST loopback only. No new listener.
    location ~ "^/(?:path|provider/auth|experimental/tool/ids|skill|global/health)$" {
        limit_except GET { deny all; }
        proxy_pass http://127.0.0.2:4097;
        proxy_set_header Authorization AUTH;
        proxy_set_header Cookie "";
        proxy_set_header Host 127.0.0.2:4097;
        add_header Cache-Control "no-store" always;
    }
'''
    addition=addition.replace('AUTH',auth[0])
    newconf=text.replace('    location / { return 404; }',addition+'    location / { return 404; }',1).encode()
    if not differences:print('NO_CHANGE: all 18 application files match, transport needs separate review');return
    BACKUPS.mkdir(mode=0o700,parents=True,exist_ok=True)
    os.chmod(BACKUPS,0o700)
    if BACKUPS.is_symlink():raise RuntimeError('Unsafe backup root')
    backup=pathlib.Path(tempfile.mkdtemp(prefix='native-test-',dir=str(BACKUPS)));os.chmod(backup,0o700)
    manifest={'changed':list(differences),'nginx_before_sha':sha(oldconf),'status':'prepared'}
    for name,(old,st) in differences.items():
        if old is not None:
            target=backup/name;target.parent.mkdir(parents=True,exist_ok=True)
            safe_write(target,old,st)
    safe_write(backup/'nginx-test-before.conf',oldconf,CONF.stat())
    (backup/'manifest.json').write_text(json.dumps(manifest,indent=2));os.chmod(backup/'manifest.json',0o600)
    # Preflight Nginx with its actual config must remain guarded; no host/port edits.
    gateway_touched=False;nginx_touched=False
    try:
        for name,(old,st) in differences.items():safe_write(APP/name,data[name],st)
        gateway_touched=True
        safe_write(CONF,newconf,CONF.stat());nginx_touched=True
        run('nginx','-t')
        run('systemctl','reload','nginx')
        run('systemctl','restart',SERVICE)
        if run('systemctl','is-active',SERVICE).stdout.strip()!='active':raise RuntimeError('Gateway inactive after restart')
        if run('systemctl','show','-p','MainPID','--value',NATIVE).stdout.strip()!=native_before:raise RuntimeError('Native PID changed externally')
        import urllib.request
        response=urllib.request.urlopen('http://127.0.0.1:8001/api/health',timeout=8)
        if json.load(response).get('status')!='ok':raise RuntimeError('Gateway health failed')
        manifest['status']='deployed-health-pass'
        (backup/'manifest.json').write_text(json.dumps(manifest,indent=2))
        print(json.dumps({'result':'DEPLOYED_TEST','changed':list(differences),'backup':str(backup),'gateway_healthy':True,'native_pid_unchanged':True}))
    except Exception:
        # Exact restored bytes only. Keep backup for manual recovery regardless.
        if gateway_touched:
            for name,(old,st) in differences.items():
                dest=APP/name
                if dest.is_file() and dest.read_bytes()!=data[name] and (old is None or dest.read_bytes()!=old):raise RuntimeError('External file drift; stop rollback. Backup '+str(backup))
            for name,(old,st) in differences.items():
                dest=APP/name
                if old is None:
                    if dest.exists():dest.unlink()
                else:safe_write(dest,old,st)
        if nginx_touched and CONF.read_bytes()==newconf:safe_write(CONF,oldconf,CONF.stat())
        try:run('nginx','-t');run('systemctl','reload','nginx');run('systemctl','restart',SERVICE)
        except Exception:pass
        raise RuntimeError('TEST deployment failed; backup retained: '+str(backup))
if __name__=='__main__':
    try:main()
    except Exception as e:
        print('TEST_RELEASE_STOP: '+str(e));raise SystemExit(1)
