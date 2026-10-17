#!/usr/bin/env python3
"""Read-only TEST runtime probe; no app import, DB, model call or raw body output."""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import uuid

FIELDS={'success','error','errors','issues','name','code','message','data','detail','type'}
CATEGORIES={'ValidationError','ZodError','UnknownError','NotFoundError','ProviderAuthError'}
CODES={'invalid_type','invalid_value','invalid_union','invalid_string','too_small','too_big',
       'unrecognized_keys','custom','invalid_format','invalid_literal'}
PATHS={'query','param','params','body','directory','sessionID','permissionID','permission',
       'patterns','tool','messageID','callID','id','path'}


def summarize(payload):
    if isinstance(payload,list):return {'shape':'list','count':len(payload)}
    if not isinstance(payload,dict):return {'shape':type(payload).__name__}
    output={'shape':'object','fields':sorted(key if key in FIELDS else '[other]' for key in payload)[:12]}
    name=payload.get('name')
    output['category']=name if isinstance(name,str) and name in CATEGORIES else 'unclassified'
    error=payload.get('error')
    if isinstance(error,dict):
        name=error.get('name')
        if isinstance(name,str) and name in CATEGORIES:output['category']=name
    candidates=[payload,error] if isinstance(error,dict) else [payload]
    output['issues']=[]
    for item in candidates:
        issues=item.get('issues',item.get('errors',[]))
        if not isinstance(issues,list):continue
        for issue in issues[:10]:
            if not isinstance(issue,dict):continue
            code=issue.get('code');path=issue.get('path',[])
            output['issues'].append({'code':code if isinstance(code,str) and code in CODES else '[other]',
                                    'path':[part if isinstance(part,str) and part in PATHS else '[other]'
                                            for part in path[:8]] if isinstance(path,list) else []})
    # Never output validation messages, input values, commands, filenames or bodies.
    return output


def descendant(pid,ancestor):
    for _ in range(12):
        if pid==ancestor:return True
        if pid<=1:return False
        try:
            status=(Path('/proc')/str(pid)/'status').read_text()
            pid=int(next(line.split(':',1)[1] for line in status.splitlines() if line.startswith('PPid:')))
        except (OSError,ValueError,StopIteration):return False
    return False


def probe(target):
    target=str(uuid.UUID(target))
    gateway=int(subprocess.check_output(['systemctl','show','opencode-gateway-test.service',
                                        '-p','MainPID','--value'],text=True).strip())
    if gateway<=1:raise RuntimeError('TEST Gateway is not running')
    candidates=[]
    for process in Path('/proc').iterdir():
        if not process.name.isdecimal() or not descendant(int(process.name),gateway):continue
        try:
            args=(process/'cmdline').read_bytes().split(b'\0')
            if b'serve' not in args or b'--port' not in args:continue
            env=dict(part.split(b'=',1) for part in (process/'environ').read_bytes().split(b'\0') if b'=' in part)
            home=Path(env.get(b'HOME',b'').decode())
            if target not in home.parts:continue
            hostname=args[args.index(b'--hostname')+1]
            if hostname!=b'127.0.0.1':continue
            port=int(args[args.index(b'--port')+1]);password=env.get(b'OPENCODE_SERVER_PASSWORD')
            if not 1<=port<=65535 or not password:continue
            candidates.append((port,password,str((process/'cwd').resolve())))
        except (OSError,ValueError,IndexError,UnicodeError):continue
    if len(candidates)!=1:raise RuntimeError('Expected one running TEST workspace runtime; found '+str(len(candidates)))
    port,password,directory=candidates[0]
    auth=base64.b64encode(b'opencode:'+password).decode()
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for label,query in [('workspace_context','?'+urllib.parse.urlencode({'directory':directory})),('without_directory','')]:
        request=urllib.request.Request('http://127.0.0.1:'+str(port)+'/permission'+query,
                                       headers={'Authorization':'Basic '+auth,'Accept':'application/json'})
        try:response=opener.open(request,timeout=10)
        except urllib.error.HTTPError as error:response=error
        with response:
            body=response.read(32769)
            try:details=summarize(json.loads(body)) if len(body)<=32768 else {'shape':'oversized'}
            except (ValueError,UnicodeError):details={'shape':'non_json'}
            print(json.dumps({'probe':label,'status':response.code,**details},ensure_ascii=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace_id');args=parser.parse_args()
    try:probe(args.workspace_id)
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        # Known setup errors are finite; do not print arbitrary exception messages.
        print('BLOCKED: TEST runtime probe unavailable ('+type(error).__name__+'). Open the target TEST workspace and verify its ID; do not restart services.')
        raise SystemExit(1)
