#!/usr/bin/env python3
"""Delete only orphaned demo workspace files and Native sessions via official Native API."""
import argparse
import os
from pathlib import Path
import re
import shutil
import sys
import uuid

import httpx

PATHS = {
 'TEST': (Path('/var/lib/opencode-workspaces-test'), Path('/var/lib/opencode-runtime-test')),
 'LIVE': (Path('/var/lib/opencode-workspaces'), Path('/var/lib/opencode-runtime')),
}
NATIVE = 'http://127.0.0.1:18098'
ID = re.compile(r'^[A-Za-z0-9_-]{1,120}$')

def is_uuid(value):
    try:
        return str(uuid.UUID(value))==value.lower()
    except (ValueError,AttributeError):
        return False

def safe_child(parent, child):
    if parent.is_symlink() or child.is_symlink() or child.parent != parent:
        raise RuntimeError('UNSAFE_STORAGE_PATH')
    if child.exists() and not child.is_dir():
        raise RuntimeError('UNEXPECTED_STORAGE_TYPE')
    return child

def scan(root, want_repo):
    if not root.is_dir() or root.is_symlink():raise RuntimeError('UNSAFE_ROOT')
    results=[]
    for owner in sorted(root.iterdir()):
        if not is_uuid(owner.name):continue
        safe_child(root,owner)
        for child in sorted(owner.iterdir()):
            if not is_uuid(child.name):continue
            safe_child(owner,child)
            if want_repo:
                repo=safe_child(child,child/'repo')
                if repo.is_dir():results.append((child,repo))
                else:results.append((child,None))
            else:results.append((child,None))
    return results

def scoped_sessions(client, root):
    r=client.get('/session',params={'directory':str(root)},timeout=15)
    r.raise_for_status()
    if not isinstance(r.json(),list):raise RuntimeError('INVALID_NATIVE_SESSION_LIST')
    sessions=r.json()
    if len(sessions)>2000:raise RuntimeError('NATIVE_SESSION_LIMIT_EXCEEDED')
    ids=[]
    for x in sessions:
        if not isinstance(x,dict) or x.get('directory')!=str(root) or not isinstance(x.get('id'),str) or not ID.fullmatch(x['id']):
            raise RuntimeError('NATIVE_SESSION_SCOPE_MISMATCH')
        ids.append(x['id'])
    if len(ids)!=len(set(ids)):raise RuntimeError('DUPLICATE_NATIVE_SESSION_IDS')
    return ids

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=('audit','apply'))
    args=parser.parse_args()
    if os.geteuid()==0:raise RuntimeError('DO_NOT_RUN_AS_ROOT')
    groups={}
    total=0
    with httpx.Client(base_url=NATIVE,trust_env=False,timeout=15) as native:
        # This is the shared Native service; no restart and no direct storage edits.
        health=native.get('/global/health')
        health.raise_for_status()
        if not health.headers.get("content-type","").startswith("application/json"):
            raise RuntimeError("NATIVE_HEALTH_NOT_JSON")
        for side,(workspaces,runtime) in PATHS.items():
            work=scan(workspaces,True)
            legacy=scan(runtime,False)
            planned=[]
            for folder,repo in work:
                ids=scoped_sessions(native,repo) if repo is not None else []
                planned.append((folder,repo,ids))
            groups[side]=(planned,legacy)
            count=sum(len(ids) for _,_,ids in planned)
            total+=count
            print(side+'_PROJECT_FOLDERS='+str(len(planned)),flush=True)
            print(side+'_LEGACY_RUNTIME_FOLDERS='+str(len(legacy)),flush=True)
            print(side+'_NATIVE_SESSIONS='+str(count),flush=True)
        if args.mode=='audit':
            print('FILE_PURGE_AUDITED_ONLY',flush=True)
            return
        for side,(planned,legacy) in groups.items():
            deleted_sessions=0
            for folder,repo,ids in planned:
                for session_id in ids:
                    reply=native.delete('/session/'+session_id,params={'directory':str(repo)},timeout=20)
                    reply.raise_for_status()
                    deleted_sessions+=1
                if repo is not None and scoped_sessions(native,repo):
                    raise RuntimeError(side+'_NATIVE_SESSIONS_STILL_PRESENT')
                safe_child(folder.parent,folder)
                shutil.rmtree(folder)
            # Never delete UUID runtime trees blindly: they may hold account
            # provider OAuth/auth material even after demo project DB cleanup.
            # A separate ownership mapping is required before touching them.
            print(side+'_LEGACY_RUNTIME_TREES_PRESERVED='+str(len(legacy)),flush=True)
            print(side+'_PROJECT_FILES_PURGED=YES',flush=True)
            print(side+'_NATIVE_SESSIONS_DELETED='+str(deleted_sessions),flush=True)
        print('FILE_PURGE_COMPLETE_WITH_NATIVE_ENGINE_UNCHANGED',flush=True)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('FILE_PURGE_FAILED='+(str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__),file=sys.stderr)
        sys.exit(1)
