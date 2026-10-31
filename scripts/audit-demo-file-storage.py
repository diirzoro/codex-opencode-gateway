#!/usr/bin/env python3
"""Read-only inventory of retired project/conversation directories after SQL cleanup."""
import os
from pathlib import Path
import shlex
import sys
import subprocess

DEPLOYS = {'TEST': Path('/home/tahir/opencode-gateway-test'), 'LIVE': Path('/home/tahir/opencode-gateway')}
SUDO = None

def read_env(path):
    global SUDO
    try:
        raw=path.read_text()
    except PermissionError:
        if SUDO is None:
            with os.fdopen(3, 'r') as f: SUDO=f.readline().rstrip('\n')
        if not SUDO: raise RuntimeError('SUDO_MISSING')
        p=subprocess.run(['sudo','-S','-p','','/usr/bin/cat',str(path)],input=SUDO+'\n',capture_output=True,text=True,timeout=10)
        if p.returncode:raise RuntimeError('ENV_DENIED')
        raw=p.stdout
    result={}
    for line in raw.splitlines():
        line=line.strip().removeprefix('export ')
        if not line or line.startswith('#') or '=' not in line:continue
        k,v=line.split('=',1)
        if k.strip() in ('WORKSPACE_ROOT','RUNTIME_ROOT'):
            x=shlex.split(v,comments=True)
            if len(x)!=1:raise RuntimeError('INVALID_STORAGE_ROOT')
            result[k.strip()]=x[0]
    return result

def inspect(root):
    if root.is_symlink():raise RuntimeError('ROOT_IS_SYMLINK')
    if not root.exists():return 'ABSENT'
    if not root.is_dir():raise RuntimeError('NOT_DIRECTORY')
    children=list(root.iterdir())
    dirs=sum(x.is_dir() and not x.is_symlink() for x in children)
    symlinks=sum(x.is_symlink() for x in children)
    files=sum(x.is_file() and not x.is_symlink() for x in children)
    return f'{dirs}_DIRS_{files}_FILES_{symlinks}_SYMLINKS'

def main():
    roots={}
    for env,base in DEPLOYS.items():
        values=read_env(base/'.env')
        for var,kind in (('WORKSPACE_ROOT','workspaces'),('RUNTIME_ROOT','runtime')):
            path=Path(values.get(var,base/kind)).resolve()
            if not path.is_relative_to(base) or path == base:
                print(env+'_'+kind.upper()+'_OUTSIDE_DEPLOYMENT=YES')
                continue
            roots[(env,kind)]=path
            print(env+'_'+kind.upper()+'_ROOT='+inspect(path),flush=True)
    if len(set(roots.values()))!=len(roots):raise RuntimeError('OVERLAPPING_STORAGE_ROOTS')
    print('DISK_STORAGE_AUDIT_FINISHED')

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('DISK_AUDIT_FAILED='+str(exc) if isinstance(exc,RuntimeError) else 'DISK_AUDIT_FAILED='+type(exc).__name__,file=sys.stderr)
        sys.exit(1)
