#!/usr/bin/env python3
"""Coordinated, operator-run TEST deployment. No SSH, migrations or engine lifecycle.

inspect is read-only. prepare writes root-private backups/candidates only. apply
stages ALL dependencies with Native disabled. activate is a separate step after
staging succeeds; rollback restores only this release's exact preimages.
"""
import argparse
import fcntl
import ast
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
import uuid

APP=Path('/home/tahir/opencode-gateway-test')
SITE=Path('/etc/nginx/sites-available/opencode-gateway-test')
ENABLED_SITE=Path('/etc/nginx/sites-enabled/opencode-gateway-test')
LOCAL=Path('/etc/nginx/conf.d/opencode-native-test-session-local.conf')
SNIPPET=Path('/etc/nginx/snippets/opencode-native-coordinated-test.conf')
FLAG=Path('/etc/opencode-gateway-test/native-release.env')
DROPIN=Path('/etc/systemd/system/opencode-gateway-test.service.d/zzzz-native-release.conf')
PLANS=Path('/var/backups/opencode-native-coordinated-test')
SERVICE='opencode-gateway-test.service'
BASELINE='3d4d52d69464edc57ab7f851d7e6faa67a607091'
BASELINES=(BASELINE,'c0d830bc3abb374d9f5699c445b0195032aba39a','6a04264d94f7b175cf5e0ba087fc9f407a88e693','3cff49ca18e3f9e7850e623cef69522823077a93')
FILES=('app.js','dashboards.js','runtime-client.js','native-session-client.js',
       'backend/app/main.py','backend/app/routes/native_sessions.py',
       'backend/app/routes/agent.py','backend/app/services/opencode.py',
       'management.js','backend/app/routes/workspaces.py','backend/app/services/native_provider_accounts.py',
       'backend/app/services/github.py','backend/app/routes/admin.py',
       'backend/app/services/native_catalog_maintenance.py','enhancements.js',
       'backend/app/services/policy.py','backend/app/services/providers.py',
       'backend/app/services/workspaces.py')

class Stop(RuntimeError):pass

def digest(data):return hashlib.sha256(data).hexdigest()
def run(args,timeout=60):
    result=subprocess.run(args,capture_output=True,timeout=timeout)
    if result.returncode:raise Stop('Command failed: '+args[0]+' '+(args[1] if len(args)>1 else ''))
    return result.stdout

def private_directory(path):
    if path.is_symlink():raise Stop('Unsafe private directory')
    path.mkdir(mode=0o700,parents=True,exist_ok=True)
    st=path.stat()
    if st.st_uid!=0 or stat.S_IMODE(st.st_mode)&0o077:raise Stop('Backup/activation directory must be root-private')

def fingerprint(path):
    if path.is_symlink():raise Stop('Unexpected target symlink: '+str(path))
    if not path.exists():return None
    st=path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1:raise Stop('Target must be an ordinary single-link file')
    return {'sha256':digest(path.read_bytes()),'mode':stat.S_IMODE(st.st_mode),'uid':st.st_uid,'gid':st.st_gid}

def write(path,data,meta):
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):raise Stop('Unsafe target path')
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.native-release-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.chown(name,meta['uid'],meta['gid']);os.chmod(name,meta['mode']);os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)

def git(source,*args,optional=False):
    p=subprocess.run(['git','-c','safe.directory='+str(source),'-C',str(source),*args],capture_output=True,timeout=30)
    if p.returncode:
        if optional:return None
        raise Stop('Reviewed source object is unavailable; fetch updates first')
    return p.stdout

def source_check(source,revision):
    if not re.fullmatch('[0-9a-f]{40}',revision):raise Stop('An exact reviewed commit SHA is required')
    # Reading committed blobs never overwrites TEST's HEAD or local changes.
    if git(source,'rev-parse','--abbrev-ref','HEAD').strip()!=b'updates':raise Stop('Source must be on updates')
    head=git(source,'rev-parse','refs/remotes/origin/updates').decode().strip()
    if head!=revision:raise Stop('Reviewed revision must equal fetched origin/updates')
    git(source,'merge-base','--is-ancestor',BASELINE,revision)

def unit():
    values={}
    for line in run(['systemctl','show',SERVICE,'--no-pager','-p','User','-p','WorkingDirectory','-p','ExecStart','-p','FragmentPath','-p','DropInPaths','-p','MainPID','-p','ActiveState','-p','EnvironmentFiles'],timeout=5).decode().splitlines():
        k,_,v=line.partition('=');values[k]=v
    if values.get('User')!='tahir' or values.get('WorkingDirectory')!=str(APP/'backend') or not re.search(r'--port\s+8001(?:\s|;|$)',values.get('ExecStart','')):
        raise Stop('Unexpected TEST service identity, directory or port')
    return values

def process_environment(values):
    pid=values.get('MainPID','0')
    if not pid.isdigit() or int(pid)<=0:raise Stop('Running TEST Gateway is required to preserve its actual environment')
    try:raw=Path('/proc',pid,'environ').read_bytes()
    except OSError:raise Stop('Cannot privately verify TEST process environment') from None
    return dict(item.split(b'=',1) for item in raw.split(b'\0') if b'=' in item)

def public_environment_check(env):
    db=env.get(b'DATABASE_URL',b'').rsplit(b'/',1)[-1].split(b'?',1)[0]
    if not env.get(b'DATABASE_URL',b'').startswith((b'postgresql://',b'postgresql+psycopg://')) or db!=b'opencode_gateway_test' or env.get(b'PUBLIC_BASE_URL',b'').rstrip(b'/')!=b'https://test.opencode-gateway.codes':
        raise Stop('Running service does not identify the exact TEST DB/domain')

def protected(values):
    paths={APP/'.env',APP/'index.html',APP/'backend/app/config.py',APP/'backend/requirements.txt',Path(values['FragmentPath']),Path('/etc/opencode-native-test.env')}
    paths.update(Path(x) for x in values.get('DropInPaths','').split())
    paths.update(Path(x) for x in values.get('EnvironmentFiles','').split() if x.startswith('/'))
    # Keep originals fingerprinted, never rewrite or print their contents.
    return {str(p):fingerprint(p) for p in paths if p!=DROPIN}

def blocks(text):
    # Quoted/comment braces and regex quantifiers do not delimit Nginx blocks.
    stack=[];result=[];quote=None;comment=False;i=0
    while i<len(text):
        c=text[i]
        if comment:
            if c=='\n':comment=False
        elif quote:
            if c=='\\':i+=1
            elif c==quote:quote=None
        elif c=='#':comment=True
        elif c in '\"\'':quote=c
        elif c=='{':
            quant=re.match(r'\{\d+(?:,\d*)?\}',text[i:])
            if quant:i+=len(quant.group())-1
            else:stack.append(i)
        elif c=='}':
            if not stack:raise Stop('Cannot safely parse existing Nginx blocks')
            start=stack.pop()
            if not stack:result.append((start,i))
        i+=1
    if stack or quote:raise Stop('Cannot safely parse existing Nginx syntax')
    return result

def site_candidate(text):
    candidates=[]
    for start,end in blocks(text):
        body=text[start+1:end]
        names=re.findall(r'(?m)^\s*server_name\s+([^;]+);',body)
        if names!=['test.opencode-gateway.codes']:raise Stop('Site contains an unexpected domain; manual reconciliation required')
        if re.search(r'\blisten\s+(?:[^;]*:)?443\b[^;]*\bssl\b',body):candidates.append((start,end,body))
    if len(candidates)!=1:raise Stop('Expected exactly one TEST TLS server')
    _,end,body=candidates[0]
    if '@native_session_test' in text or '@native_discovery_test' in text or str(SNIPPET) in text:
        raise Stop('Native routing already exists; reconcile it before preparing another deployment')
    if not re.search(r'location\s+/\s*\{[^{}]*proxy_pass\s+http://127\.0\.0\.1:8001\s*;',body):
        raise Stop('Existing Gateway root routing is not the expected TEST route')
    return text[:end]+'    include '+str(SNIPPET)+';\n'+text[end:]

def loopback_candidate(text):
    groups=blocks(text)
    if len(groups)!=1 or not re.search(r'\blisten\s+127\.0\.0\.1:18098\s*;',text):raise Stop('Unexpected loopback session transport')
    if re.search(r'\blisten\s+(?!127\.0\.0\.1:18098\s*;)',text):raise Stop('Additional transport listener requires manual reconciliation')
    lines=re.findall(r'proxy_set_header\s+Authorization\s+"Basic [A-Za-z0-9+/=]+"\s*;',text,re.I)
    if not lines or len(set(lines))!=1:raise Stop('Cannot safely reuse the existing private native Authorization setting')
    if re.search(r'location[^\n]*(permission|question)',text):raise Stop('Permission/question routing already exists; review it first')
    if any(u!='http://127.0.0.2:4097' for u in re.findall(r'proxy_pass\s+([^;\s]+)',text)):
        raise Stop('Unexpected native upstream')
    addition='''
    # Coordinated native TEST release; still loopback-only.
    location ~ "^/(?:permission|question)(?:/[A-Za-z0-9_-]{1,120}/(?:reply|reject))?$" {
        limit_except GET POST { deny all; }
        proxy_pass http://127.0.0.2:4097;
        AUTHORIZATION
        proxy_set_header Cookie "";
        proxy_set_header Host 127.0.0.2:4097;
        proxy_read_timeout 120s;
        add_header Cache-Control "no-store" always;
    }
'''.replace('AUTHORIZATION',lines[0])
    # Management metadata/auth uses the SAME protected native transport. It is
    # not exposed by the browser transport allowlist. No new listener/service.
    management='''
    location ~ "^/(?:auth/[A-Za-z0-9_-]{1,120}|provider/auth|provider/[A-Za-z0-9_-]{1,120}/oauth/(?:authorize|callback)|session/[A-Za-z0-9_-]{1,120}|global/health|experimental/tool/ids|skill|path)$" {
        limit_except GET POST PUT DELETE PATCH { deny all; }
        proxy_pass http://127.0.0.2:4097;
        AUTHORIZATION
        proxy_set_header Cookie "";
        proxy_set_header Host 127.0.0.2:4097;
        proxy_read_timeout 120s;
        add_header Cache-Control "no-store" always;
    }
'''.replace('AUTHORIZATION',lines[0])
    start=groups[0][0]
    text=text[:start+1]+management+text[start+1:]
    groups=blocks(text)
    end=groups[0][1];return text[:end]+addition+text[end:]

def inspection(source,revision):
    source_check(source,revision)
    if git(APP,'rev-parse','--abbrev-ref','HEAD').strip()!=b'updates':raise Stop('Actual TEST checkout is not on updates; refusing deployment')
    if APP.is_symlink() or APP.resolve()!=APP:raise Stop('TEST checkout is a symlink; manual release reconciliation required')
    if ENABLED_SITE.resolve()!=SITE:raise Stop('Enabled TEST site does not point to the expected TEST-only file')
    values=unit();env=process_environment(values);public_environment_check(env)
    native_version()
    files=[]
    for name in FILES:
        before=fingerprint(APP/name);bases=[git(source,'show',base+':'+name,optional=True) for base in BASELINES];after=git(source,'show',revision+':'+name)
        approved=[None if base is None else digest(base) for base in bases]
        # TEST dashboards.js was deliberately restored by 9de0e55; accept only
        # that exact Git-tracked preimage, then stage the reviewed native version.
        # This exception does not relax reconciliation for any other file.
        if name=='dashboards.js':
            restored=git(source,'show','9de0e55:dashboards.js',optional=True)
            if restored is not None:approved.append(digest(restored))
        match=(before is None and None in approved) or before is not None and before['sha256'] in {*approved,digest(after)}
        files.append({'path':name,'actual':before,'approved_baseline_sha256':approved,'candidate_sha256':digest(after),'reconciled':match})
    return values,env,files

def native_version():
    # Reuse protected existing authentication in memory; never echo the config.
    headers=re.findall(r'proxy_set_header\s+Authorization\s+"(Basic [A-Za-z0-9+/=]+)"\s*;',LOCAL.read_text(),re.I)
    if not headers or len(set(headers))!=1:raise Stop('Cannot verify native version with the existing private TEST authentication')
    request=urllib.request.Request('http://127.0.0.2:4097/global/health',headers={'Authorization':headers[0]})
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        with opener.open(request,timeout=5) as response:health=json.loads(response.read(8192))
    except Exception:raise Stop('Native TEST health/version could not be verified; no service was changed') from None
    version=health.get('version','')
    if health.get('healthy') is not True or not re.fullmatch(r'1\.(?:18|19)\.\d+',str(version)):raise Stop('Existing native TEST health/API family requires reconciliation; no installation/upgrade performed')
    return version

def prepare(source,revision):
    values,env,files=inspection(source,revision)
    drift=[f['path'] for f in files if not f['reconciled']]
    if drift:raise Stop('Working TEST changes require merging first: '+', '.join(drift))
    for p in (SNIPPET,FLAG,DROPIN):
        if p.exists() or p.is_symlink():raise Stop('Release-owned configuration path already exists; preserving it: '+str(p))
    private_directory(PLANS);folder=PLANS/uuid.uuid4().hex;private_directory(folder)
    entries=[];uid=(APP.stat().st_uid);gid=APP.stat().st_gid
    payloads={APP/f:git(source,'show',revision+':'+f) for f in FILES}
    for name,data in payloads.items():
        if name.suffix=='.py':ast.parse(data,filename=str(name))
    payloads[SITE]=site_candidate(SITE.read_text()).encode()
    payloads[LOCAL]=loopback_candidate(LOCAL.read_text()).encode()
    payloads[SNIPPET]=git(source,'show',revision+':docs/NATIVE_SESSION_TEST_NGINX.conf')
    payloads[FLAG]=b'OPENCODE_NATIVE_TEST_ENABLED=false\n'
    payloads[DROPIN]=('[Service]\nEnvironmentFile='+str(FLAG)+'\n').encode()
    for index,(path,data) in enumerate(payloads.items()):
        before=fingerprint(path);meta=before or {'uid':uid if path.is_relative_to(APP) else 0,'gid':gid if path.is_relative_to(APP) else 0,'mode':0o600 if path==FLAG else 0o644}
        old=folder/(str(index)+'.before');new=folder/(str(index)+'.after')
        if before:write(old,path.read_bytes(),{'uid':0,'gid':0,'mode':0o600})
        write(new,data,{'uid':0,'gid':0,'mode':0o600})
        entries.append({'path':str(path),'before':before,'after':{**{k:meta[k] for k in ('uid','gid','mode')},'sha256':digest(data)},'old':old.name,'new':new.name})
    plan={'version':1,'revision':revision,'entries':entries,'protected':protected(values),'state':'prepared','initial_active':values['ActiveState']=='active','initial_flag':env.get(b'OPENCODE_NATIVE_TEST_ENABLED',b'').decode().lower()}
    raw=json.dumps(plan,sort_keys=True,indent=2).encode();write(folder/'plan.json',raw,{'uid':0,'gid':0,'mode':0o600})
    return {'plan':str(folder),'review_sha256':digest(raw),'files':[e['path'] for e in entries],'state':'prepared-no-server-change'}

def load(folder):
    if folder.parent!=PLANS or not re.fullmatch('[0-9a-f]{32}',folder.name):raise Stop('Unexpected deployment plan path')
    if folder.is_symlink() or not folder.is_dir() or folder.stat().st_uid!=0 or stat.S_IMODE(folder.stat().st_mode)&0o077:raise Stop('Deployment plan directory is not root-private')
    p=folder/'plan.json';meta=fingerprint(p)
    if not meta or meta['uid']!=0 or meta['mode']&0o077:raise Stop('Deployment plan is not root-private')
    data=p.read_bytes();plan=json.loads(data)
    allowed={str(APP/x) for x in FILES}|{str(x) for x in (SITE,LOCAL,SNIPPET,FLAG,DROPIN)}
    if len(plan['entries'])!=len(allowed) or {e['path'] for e in plan['entries']}!=allowed:raise Stop('Plan target allowlist mismatch')
    for entry in plan['entries']:
        if not re.fullmatch(r'\d+\.after',entry['new']) or not re.fullmatch(r'\d+\.before',entry['old']):raise Stop('Invalid backup name')
        if digest((folder/entry['new']).read_bytes())!=entry['after']['sha256']:raise Stop('Prepared source/configuration changed')
        if entry['before'] and digest((folder/entry['old']).read_bytes())!=entry['before']['sha256']:raise Stop('Original backup changed')
    return plan,digest(data)

def save(folder,plan):write(folder/'plan.json',json.dumps(plan,sort_keys=True,indent=2).encode(),{'uid':0,'gid':0,'mode':0o600})
def check_protected(plan):
    if any(fingerprint(Path(p))!=meta for p,meta in plan['protected'].items()):raise Stop('Original environment/unit configuration changed; preserving the drift')

def check_files(plan,key):
    if any(fingerprint(Path(e['path']))!=e[key] for e in plan['entries']):raise Stop('TEST files changed since review; refusing overwrite')

def health(flag,owner=None):
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        try:
            values=unit();env=process_environment(values);public_environment_check(env)
            if env.get(b'OPENCODE_NATIVE_TEST_ENABLED',b'').decode().lower()!=flag:raise ValueError()
            if owner and env.get(b'OPENCODE_NATIVE_TEST_OWNER_ID',b'').decode()!=owner:raise ValueError()
            with urllib.request.urlopen('http://127.0.0.1:8001/api/health',timeout=2) as r:result=json.load(r)
            if result.get('status')=='ok':return
        except (OSError,ValueError,Stop):pass
        time.sleep(1)
    raise Stop('TEST Gateway/feature-state health verification failed')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def verify_public(folder,plan,enabled):
    # Fresh HTTPS bytes and an unauthenticated Gateway denial prove that the
    # complete UI is served together and no shared native API was exposed.
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    origin='https://test.opencode-gateway.codes'
    for e in plan['entries']:
        path=Path(e['path'])
        if path.parent!=APP or path.suffix!='.js':continue
        req=urllib.request.Request(origin+'/'+path.name+'?v='+e['after']['sha256'][:16],headers={'Cache-Control':'no-cache'})
        with opener.open(req,timeout=10) as response:data=response.read(2*1024*1024+1)
        if digest(data)!=e['after']['sha256']:raise Stop('Public TEST frontend bytes do not match the coordinated release')
    with opener.open(origin+'/',timeout=10) as response:html=response.read(2*1024*1024)
    if enabled and b'native-session-client.js?v=' not in html:raise Stop('Public TEST HTML did not activate its native client')
    try:
        opener.open(origin+'/native-session/00000000-0000-0000-0000-000000000000/provider',timeout=10)
    except urllib.error.HTTPError as error:
        try:body=json.loads(error.read(8192))
        except ValueError:raise Stop('Public native route did not return the Gateway authentication boundary') from None
        if error.code==401 and body.get('detail')=='Authentication required':return
    raise Stop('Public native API is not protected by Gateway login')

def rollback(folder,plan):
    check_protected(plan)
    # Unknown concurrent edits are never overwritten, even during rollback.
    for e in plan['entries']:
        current=fingerprint(Path(e['path']))
        if current not in [e['before'],e['after'],*e.get('previous_after',[])]:raise Stop('Rollback found external drift; backups preserved for manual recovery')
    run(['systemctl','stop',SERVICE])
    for e in reversed(plan['entries']):
        path=Path(e['path'])
        if e['before']:write(path,(folder/e['old']).read_bytes(),e['before'])
        elif path.exists():path.unlink()
    run(['systemctl','daemon-reload'])
    nginx_ok=True
    try:run(['nginx','-t']);run(['systemctl','reload','nginx'])
    except Stop:nginx_ok=False
    if plan['initial_active']:
        run(['systemctl','start',SERVICE]);health(plan['initial_flag'])
    plan['state']='rolled-back' if nginx_ok else 'files-restored-nginx-review-required';save(folder,plan)
    if not nginx_ok:raise Stop('Original TEST files and Gateway restored; Nginx validation/reload needs operator review')

def apply(folder,review):
    plan,actual=load(folder)
    if actual!=review or plan['state']!='prepared':raise Stop('Review digest/state mismatch')
    check_files(plan,'before');check_protected(plan)
    try:
        # Gateway is stopped for the coordinated copy; no partial UI is served.
        run(['systemctl','stop',SERVICE])
        # Persist the disable switch before copying any runtime dependency.
        ordered=sorted(plan['entries'],key=lambda e:0 if e['path'] in {str(FLAG),str(DROPIN)} else 1)
        for e in ordered:
            if fingerprint(Path(e['path']))!=e['before']:raise Stop('Target changed during coordinated copy')
            write(Path(e['path']),(folder/e['new']).read_bytes(),e['after'])
        run(['systemctl','daemon-reload']);run(['nginx','-t']);run(['systemctl','reload','nginx'])
        if not unit().get('DropInPaths','').split() or unit().get('DropInPaths','').split()[-1]!=str(DROPIN):raise Stop('Native activation file would not be the last TEST drop-in')
        run(['systemctl','start',SERVICE]);health('false');check_protected(plan);check_files(plan,'after');verify_public(folder,plan,False)
        plan['state']='staged-disabled';save(folder,plan)
    except Exception:
        rollback(folder,plan);raise Stop('Coordinated staging failed; original TEST files restored') from None
    return {'revision':plan['revision'],'state':plan['state'],'deployed':[e['path'] for e in plan['entries']]}

def activate(folder,owner=None):
    plan,_=load(folder)
    if plan['state']!='staged-disabled':raise Stop('All dependencies must be staged and healthy before activation')
    if owner:raise Stop('Single-owner activation is retired; use authenticated TEST admission')
    check_files(plan,'after');check_protected(plan)
    entry=next(e for e in plan['entries'] if e['path']==str(FLAG))
    try:
        raw=b'OPENCODE_NATIVE_TEST_ENABLED=true\n'
        # Persist the exact new value before mutation so rollback can recognize it.
        entry.setdefault('previous_after',[]).append(dict(entry['after']))
        entry['after']['sha256']=digest(raw);write(folder/entry['new'],raw,{'uid':0,'gid':0,'mode':0o600});save(folder,plan)
        write(FLAG,raw,entry['after']);run(['nginx','-t']);run(['systemctl','restart',SERVICE]);health('true',owner);check_protected(plan);verify_public(folder,plan,True)
        plan['state']='activated-acceptance-pending';save(folder,plan)
    except Exception:
        rollback(folder,plan);raise Stop('Native activation failed; original TEST files restored') from None
    return {'revision':plan['revision'],'state':plan['state'],'acceptance':'Authenticated real prompt/SSE/permission/session-isolation checks still required'}

def deployment_lock():
    path='/run/lock/opencode-native-test-release.lock'
    fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    st=os.fstat(fd)
    if st.st_uid!=0 or stat.S_IMODE(st.st_mode)!=0o600 or st.st_nlink!=1:
        os.close(fd);raise Stop('Unsafe deployment lock')
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:os.close(fd);raise Stop('Another coordinated TEST deployment is active') from None
    return fd

def config_review():
    result={}
    for name,path,builder in [('site',SITE,site_candidate),('loopback',LOCAL,loopback_candidate)]:
        try:builder(path.read_text());result[name]={'supported':True}
        except Stop as error:result[name]={'supported':False,'reason':str(error)}
        except OSError:result[name]={'supported':False,'reason':'Required TEST configuration is unavailable'}
    return result

def review_plan(folder):
    plan,review=load(folder)
    differences=[]
    for entry in plan['entries']:
        if Path(entry['path']).is_relative_to(APP):continue
        old=(folder/entry['old']).read_text() if entry['before'] else ''
        new=(folder/entry['new']).read_text()
        diff=difflib.unified_diff(old.splitlines(),new.splitlines(),fromfile=entry['path']+' before',tofile=entry['path']+' candidate',n=0,lineterm='')
        differences.extend('[REDACTED AUTHORIZATION/SECRET LINE]' if re.search(r'authorization|password|secret|token|api[_-]?key|Basic\s',line,re.I) else line for line in diff)
    return {'revision':plan['revision'],'state':plan['state'],'review_sha256':review,'files':[{'path':e['path'],'before':e['before'],'candidate':e['after']} for e in plan['entries']],'configuration_diff_no_context':differences,'mutation':False}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('operation',choices=['inspect','prepare','review','apply','activate','rollback'])
    parser.add_argument('--source',type=Path);parser.add_argument('--revision');parser.add_argument('--plan',type=Path);parser.add_argument('--review-sha256');parser.add_argument('--owner-id')
    args=parser.parse_args()
    if os.geteuid()!=0:raise Stop('Run through the TEST operator account with authorized root access; do not add general sudo rights')
    lock=None if args.operation in {'inspect','review'} else deployment_lock()
    if args.operation in {'inspect','prepare'}:
        if not args.source or not args.revision:raise Stop('Exact reviewed source and revision are required')
        if args.operation=='inspect':
            _,env,files=inspection(args.source,args.revision)
            result={'revision':args.revision,'files':files,'native_currently_enabled':env.get(b'OPENCODE_NATIVE_TEST_ENABLED',b'false').decode().lower() in {'true','1','yes'},'nginx':{str(p):fingerprint(p) for p in (SITE,LOCAL,SNIPPET)},'activation_paths':{str(p):fingerprint(p) for p in (FLAG,DROPIN)},'config_review':config_review(),'mutation':False}
        else:result=prepare(args.source,args.revision)
    else:
        if not args.plan:raise Stop('A private reviewed plan is required')
        if args.operation=='review':result=review_plan(args.plan)
        elif args.operation=='apply':result=apply(args.plan,args.review_sha256)
        elif args.operation=='activate':
            result=activate(args.plan,args.owner_id)
        else:
            plan,_=load(args.plan);rollback(args.plan,plan);result={'state':'rolled-back','database_or_workspace_changes':False}
    print(json.dumps(result,indent=2))
    if lock is not None:os.close(lock)

if __name__=='__main__':
    try:main()
    except Stop as error:
        print('NATIVE_TEST_RELEASE_STOP: '+str(error),file=sys.stderr);sys.exit(1)
    except (OSError,ValueError,subprocess.SubprocessError):
        # Never print command output, environment values or secret-bearing config.
        print('NATIVE_TEST_RELEASE_STOP: precondition/action failed; original data and private backups preserved. Inspect locally with the TEST operator.',file=sys.stderr)
        sys.exit(1)
