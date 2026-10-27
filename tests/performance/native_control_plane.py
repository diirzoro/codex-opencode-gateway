"""Synthetic local benchmark only: no network, server, users or model execution.
Run from repo root: PYTHONPATH=backend:. python tests/performance/native_control_plane.py
"""
import os
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://fixture:fixture@127.0.0.1/fixture')
import json, statistics, tempfile, time, argparse, re, subprocess, resource
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from collections import Counter
from sqlalchemy import event
from pytest import MonkeyPatch
from backend.tests.test_native_control_plane import boundary, authenticated
from backend.app.services import workspaces, policy, native_provider_accounts
from backend.app.routes import native_sessions

def stats(values):
    ordered=sorted(values)
    return {'p50_ms':round(statistics.median(ordered),3),'p95_ms':round(ordered[min(len(ordered)-1,int(len(ordered)*.95))],3)}

def run(baseline=None):
    if baseline:
        if not re.fullmatch(r'[0-9a-f]{40}',baseline):raise ValueError('Use an exact committed preimage SHA')
        # Load only the three committed module preimages in this disposable
        # Python process. Never checkout/reset/write the working repository.
        for module,path in [(workspaces,'backend/app/services/workspaces.py'),(policy,'backend/app/services/policy.py'),(native_sessions,'backend/app/routes/native_sessions.py')]:
            source=subprocess.check_output(['git','show',baseline+':'+path],text=True)
            exec(compile(source,path,'exec'),module.__dict__)
    with tempfile.TemporaryDirectory(prefix='gateway-perf-') as tmp, MonkeyPatch.context() as patch, ExitStack() as cleanup:
        generator=boundary.__wrapped__(patch,Path(tmp));client,owners,_,engine,config=next(generator)
        cleanup.callback(generator.close)
        owner=owners[0];calls=[];queries=[]
        rules=policy.native_session_permissions(SimpleNamespace(allowed_tools='[]',allowed_models='[]',allowed_providers='[]'),owner.root)
        def metadata(method,path,root,data=None):
            calls.append(path)
            if path=='/experimental/tool/ids':return ['read','write','question','todowrite']
            if path=='/session/ses_a':return {'id':'ses_a','directory':str(root),'permission':rules}
            raise AssertionError(path)
        patch.setattr(native_sessions,'metadata',metadata)
        patch.setattr(native_provider_accounts,'require_model',lambda *a:None)
        def trace(connection,cursor,statement,parameters,context,executemany):
            if statement.lstrip().lower().startswith('select'):queries.append(statement)
        event.listen(engine,'before_cursor_execute',trace)
        path=f'/native-session/{owner.workspace}/session/ses_a/prompt_async'
        body={'messageID':'msg_synthetic','model':{'providerID':'fixture','modelID':'fixture'},'parts':[{'type':'text','text':'Synthetic: not forwarded or executed'}]}
        times=[];cpu=[]
        for i in range(31):
            calls.clear();queries.clear();started=time.perf_counter();cpu_started=time.process_time()
            response=authenticated(client,path,owner,config,'POST',body)
            elapsed=(time.perf_counter()-started)*1000
            assert response.status_code==200,response.text
            assert response.headers['x-accel-redirect']=='@native_session_test'
            if i:times.append(elapsed);cpu.append((time.process_time()-cpu_started)*1000)
        result={'scope':'local SQLite/HTTP + controlled Native metadata, no engine/network',
                'authorization':{**stats(times),'samples':len(times),'native_metadata':dict(Counter(calls)),'sql_selects':len(queries),'process_cpu_p50_ms':round(statistics.median(cpu),3)},'source':baseline or 'working-tree','process_peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
        result['protected_file_http']={}
        for name in ('.env.production','auth.json','private.key'):
            (owner.root/name).write_text('synthetic-protected-marker')
            result['protected_file_http'][name]=authenticated(client,f'/api/workspaces/{owner.workspace}/files/content?path='+name,owner,config).status_code
        event.remove(engine,'before_cursor_execute',trace)
        generator.close()
    with tempfile.TemporaryDirectory(prefix='gateway-quota-') as tmp, MonkeyPatch.context() as patch:
        base=Path(tmp);root=base/'owner'/'workspace'/'repo';root.mkdir(parents=True)
        for d in range(30):
            folder=root/str(d);folder.mkdir()
            for i in range(100):(folder/str(i)).write_bytes(b'x'*64)
        patch.setattr(workspaces,'settings',SimpleNamespace(workspace_root=base))
        row=SimpleNamespace(user_id='owner',id='workspace',status='ready',project=SimpleNamespace(source_type='blank'))
        quota=[]
        for i in range(16):
            started=time.perf_counter();workspaces.require_quota_headroom(row);elapsed=(time.perf_counter()-started)*1000
            if i:quota.append(elapsed)
        result['quota_3000_files']={**stats(quota),'files':3000,'samples':len(quota)}
        with (root/'large.bin').open('wb') as handle:handle.truncate(workspaces.WORKSPACE_QUOTA_BYTES+1)
        quota=[]
        for i in range(16):
            started=time.perf_counter()
            try:workspaces.require_quota_headroom(row)
            except Exception as error:assert getattr(error,'status_code',None)==413
            else:raise AssertionError('quota bypass')
            if i:quota.append((time.perf_counter()-started)*1000)
        result['quota_over_limit']={**stats(quota),'samples':len(quota)}
    print(json.dumps(result,indent=2))
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--baseline-ref');run(parser.parse_args().baseline_ref)
