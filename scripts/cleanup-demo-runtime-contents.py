#!/usr/bin/env python3
"""Remove orphan demo per-account/per-project legacy runtime paths; preserve keeper account credential stores."""
import argparse
import os
from pathlib import Path
import shutil
import sys
import uuid

from sqlalchemy import create_engine, text
from cleanup_demo_users_projects import connection_url

ROOTS={"TEST":Path("/var/lib/opencode-runtime-test"),"LIVE":Path("/var/lib/opencode-runtime")}

def is_id(value):
    try:return str(uuid.UUID(value))==value.lower()
    except (ValueError,AttributeError):return False

def checked(root,child):
    if not root.is_dir() or root.is_symlink():raise RuntimeError("RUNTIME_ROOT_UNSAFE")
    if child.parent!=root or child.is_symlink():raise RuntimeError("RUNTIME_CHILD_UNSAFE")
    if child.exists() and not child.is_dir():raise RuntimeError("RUNTIME_ITEM_NOT_DIRECTORY")
    return child

def keeper_ids(conn):
    if conn.execute(text("SELECT count(*) FROM users")).scalar_one()!=2:
        raise RuntimeError("USER_CLEANUP_NOT_COMPLETED")
    if conn.execute(text("SELECT count(*) FROM projects")).scalar_one()!=0 or \
       conn.execute(text("SELECT count(*) FROM workspaces")).scalar_one()!=0 or \
       conn.execute(text("SELECT count(*) FROM workspace_sessions")).scalar_one()!=0:
        raise RuntimeError("PROJECT_OR_SESSION_RECREATED_ABORT")
    rows=conn.execute(text("SELECT id,username FROM users")).mappings().all()
    if {str(row["username"]).lower() for row in rows}!={"admin","testuser"}:
        raise RuntimeError("UNEXPECTED_KEEP_ACCOUNTS")
    return {str(row["id"]).lower() for row in rows}

def plan(root,keepers):
    deleted=[]
    preserve=[]
    for owner in sorted(root.iterdir()):
        if not is_id(owner.name):continue
        checked(root,owner)
        if owner.name.lower() not in keepers:
            deleted.append(owner)
            continue
        allow_runtime=str(uuid.uuid5(uuid.NAMESPACE_URL,"opencode-gateway-account:"+owner.name))
        for child in sorted(owner.iterdir()):
            if is_id(child.name):
                checked(owner,child)
                if child.name!=allow_runtime:deleted.append(child)
                else:preserve.append(child)
            else:
                # Account-owned native-account, account-workdir, auth or config
                # must not be deleted by a project cleanup.
                preserve.append(child)
    return deleted,preserve

def main():
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=("audit","apply"))
    mode=p.parse_args().mode
    if os.geteuid()==0:raise RuntimeError("RUN_AS_TAHIR_NOT_ROOT")
    for side,root in ROOTS.items():
        engine=create_engine(connection_url(side),pool_pre_ping=True)
        try:
            with engine.connect() as conn:
                if conn.execute(text("SELECT current_database()")).scalar_one()!=("opencode_gateway_test" if side=="TEST" else "opencode_gateway"):
                    raise RuntimeError("WRONG_DATABASE")
                keepers=keeper_ids(conn)
            if not root.is_dir() or root.is_symlink():raise RuntimeError("RUNTIME_ROOT_UNSAFE")
            delete,preserve=plan(root,keepers)
            print(side+"_LEGACY_RUNTIME_ORPHANS="+str(len(delete)),flush=True)
            print(side+"_ACCOUNT_RUNTIME_ITEMS_PRESERVED="+str(len(preserve)),flush=True)
            if mode=="apply":
                for entry in delete:
                    checked(entry.parent,entry)
                    shutil.rmtree(entry)
                left,_=plan(root,keepers)
                if left:raise RuntimeError(side+"_ORPHAN_RUNTIME_REMAIN")
                print(side+"_LEGACY_RUNTIME_CLEANUP=PASS",flush=True)
        finally:engine.dispose()
    print("RUNTIME_CLEANUP="+("APPLIED" if mode=="apply" else "AUDITED"),flush=True)

if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("RUNTIME_CLEANUP_FAILED="+(str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__),file=sys.stderr)
        sys.exit(1)
