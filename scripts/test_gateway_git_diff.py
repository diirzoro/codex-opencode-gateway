#!/usr/bin/env python3
"""TEST-only file-diff rollout from a pinned origin/updates git commit.

The runner uses tahir's existing permissions. It never edits configs, systemd,
database, Nginx, engine processes, secrets, or the Git checkout index.
"""
import ast, fcntl, hashlib, json, os, pathlib, re, stat, subprocess, tempfile, time
APP=pathlib.Path('/home/tahir/opencode-gateway-test')
BACKUPS=pathlib.Path('/home/tahir/opencode-gateway-test-release-backups')
SERVICE='opencode-gateway-test.service'
NATIVE='opencode-native-test.service'
def run(*args,timeout=60):
    return subprocess.run(args,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout).stdout
def digest(data):return hashlib.sha256(data).hexdigest()
def check_path(name):
    p=pathlib.PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or not p.parts or str(p)!=name:raise RuntimeError('Invalid manifest path')
    dest=APP/name
    for parent in (dest,*list(dest.parents)[:len(p.parts)-1]):
        if parent.is_symlink():raise RuntimeError('Symlink target or parent: '+name)
    if dest.exists() and (not dest.is_file() or dest.stat().st_nlink!=1):raise RuntimeError('Unsafe destination: '+name)
    return dest
def write(dest,data,meta):
    dest.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.gateway-test-release-',dir=dest.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,meta[0])
        os.chown(tmp,meta[1],meta[2])
        os.replace(tmp,dest)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def main():
    if os.geteuid()==0:raise RuntimeError('Never run release as root')
    if pathlib.Path.cwd()!=APP:raise RuntimeError('Must run from TEST checkout')
    if not (APP/'.env').is_file() or not (APP/'.git').exists():raise RuntimeError('TEST checkout missing')
    if run('systemctl','is-active',SERVICE).strip()!=b'active' or run('systemctl','is-active',NATIVE).strip()!=b'active':raise RuntimeError('TEST services not active')
    lock=open('/home/tahir/.gateway-test-deploy.lock','a+')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    source=run('git','show','origin/updates:scripts/native_test_release.py').decode()
    match=re.search(r'^FILES=(\\(.*?\\))\\n',source,re.S|re.M)
    if not match:raise RuntimeError('Missing source manifest')
    files=ast.literal_eval(match.group(1))
    if len(files)!=18 or len(set(files))!=18:raise RuntimeError('Unexpected release manifest')
    sha=run('git','rev-parse','origin/updates').decode().strip()
    changed=[]
    for name in files:
        dest=check_path(name)
        new=run('git','show',sha+':'+name)
        old=dest.read_bytes() if dest.exists() else None
        if old!=new:
            st=dest.stat() if old is not None else APP.stat()
            changed.append((name,dest,old,new,(stat.S_IMODE(st.st_mode) if old is not None else 0o644,st.st_uid,st.st_gid)))
    if not changed:
        print('TEST_ALREADY_CURRENT',sha,flush=True);return
    if BACKUPS.is_symlink():raise RuntimeError('Unsafe backup root')
    BACKUPS.mkdir(mode=0o700,exist_ok=True);os.chmod(BACKUPS,0o700)
    folder=pathlib.Path(tempfile.mkdtemp(prefix='release-',dir=BACKUPS));os.chmod(folder,0o700)
    manifest={'revision':sha,'changed':[item[0] for item in changed],'status':'staged'}
    for name,_,old,_,_ in changed:
        if old is not None:
            dest=folder/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(old)
    (folder/'manifest.json').write_text(json.dumps(manifest))
    native_pid=run('systemctl','show','--value','-p','MainPID',NATIVE).strip()
    applied=[];restart_attempted=False
    try:
        for name,dest,old,new,meta in changed:
            # Refuse races/unknown changes, even during rollout.
            if (dest.read_bytes() if dest.exists() else None)!=old:raise RuntimeError('Concurrent change: '+name)
            write(dest,new,meta);applied.append((name,dest,old,new,meta))
            print('UPDATED',name,flush=True)
        restart_attempted=True
        run('sudo','-n','/usr/bin/systemctl','restart',SERVICE)
        if run('systemctl','is-active',SERVICE).strip()!=b'active':raise RuntimeError('TEST Gateway inactive')
        if run('systemctl','show','--value','-p','MainPID',NATIVE).strip()!=native_pid:raise RuntimeError('Shared Native process changed')
        # Observe service stability instead of assuming a successful restart is readiness.
        time.sleep(2)
        if run('systemctl','is-active',SERVICE).strip()!=b'active':raise RuntimeError('Gateway did not remain active')
        manifest['status']='service-active';(folder/'manifest.json').write_text(json.dumps(manifest))
        print('TEST_DIFF_DEPLOY_SUCCESS',len(changed),'revision',sha,'backup',folder,flush=True)
    except Exception:
        conflicts=[]
        for name,dest,old,new,meta in reversed(applied):
            try:
                if not dest.is_file() or dest.read_bytes()!=new:
                    conflicts.append(name);continue
                if old is None:dest.unlink()
                else:write(dest,old,meta)
            except Exception:conflicts.append(name)
        if restart_attempted:
            try:run('sudo','-n','/usr/bin/systemctl','restart',SERVICE)
            except Exception:conflicts.append('Gateway restart')
        manifest['status']='rollback-conflicts' if conflicts else 'rolled-back'
        (folder/'manifest.json').write_text(json.dumps(manifest))
        print('ROLLBACK_STATUS',manifest['status'],'conflicts',conflicts,flush=True)
        raise
if __name__=='__main__':main()
