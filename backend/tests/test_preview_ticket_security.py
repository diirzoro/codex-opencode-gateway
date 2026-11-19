"""Exercise real encrypted preview grants against session/tenant boundaries.

No database, browser, Docker, network or customer files are accessed.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import json
import uuid
import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from app.services import preview_access as access

@pytest.fixture
def context(monkeypatch):
    now=datetime(2026,11,16,14,0,tzinfo=timezone.utc)
    owner,session_id,workspace_id,project_id=[uuid.uuid4() for _ in range(4)]
    user=SimpleNamespace(id=owner)
    session=SimpleNamespace(id=session_id,user_id=owner,user=user,revoked_at=None)
    project=SimpleNamespace(user_id=owner,archived_at=None)
    workspace=SimpleNamespace(id=workspace_id,user_id=owner,project_id=project_id,
                              project=project,status='ready')
    cipher=Fernet(Fernet.generate_key())
    monkeypatch.setattr(access,'_cipher',lambda:cipher)
    monkeypatch.setattr(access,'origins',lambda:('https://gateway.example','https://preview.example'))
    monkeypatch.setattr(access,'idle_expires_at',lambda s:now+timedelta(hours=1))
    monkeypatch.setattr(access,'normal_access_ready',lambda u:True)
    lease={'value':'a'*64}
    monkeypatch.setattr(access,'_lease',lambda w:lease['value'])
    def owned(db,model,identifier,user_id):
        if identifier!=workspace.id or user_id!=workspace.user_id:
            raise HTTPException(404,'Not found')
        return workspace
    monkeypatch.setattr(access.workspaces,'owned',owned)
    db=SimpleNamespace(get=lambda model,key:session if key==session.id else None)
    request=SimpleNamespace(url='https://preview.example/preview/placeholder/')
    minted=access.mint(workspace,session,user,now=now)
    token=minted['url'].split('/preview/')[1].rstrip('/')
    return SimpleNamespace(now=now,user=user,session=session,workspace=workspace,
                           db=db,request=request,token=token,cipher=cipher,lease=lease)

def authorize(c,token=None,now=None):
    return access.authorize(token or c.token,c.request,c.db,now=now or c.now)

def altered(c,**changes):
    payload=json.loads(c.cipher.decrypt_at_time(c.token.encode(),ttl=300,current_time=int(c.now.timestamp())))
    payload.update(changes)
    return c.cipher.encrypt_at_time(json.dumps(payload).encode(),int(c.now.timestamp())).decode()

def test_owner_with_current_session_and_lease_is_authorized(context):
    workspace,origin,lease=authorize(context)
    assert workspace is context.workspace
    assert origin=='https://gateway.example' and lease=='a'*64

@pytest.mark.parametrize('seconds',[300,301,901])
def test_expired_grant_is_rejected(context,seconds):
    with pytest.raises(HTTPException) as error:
        authorize(context,now=context.now+timedelta(seconds=seconds))
    assert error.value.status_code==401

def test_tampered_ciphertext_is_rejected(context):
    token=context.token
    replacement='A' if token[30]!='A' else 'B'
    with pytest.raises(HTTPException) as error:
        authorize(context,token[:30]+replacement+token[31:])
    assert error.value.status_code==401

@pytest.mark.parametrize('token',['not-a-token','../secret','x'*2049])
def test_invalid_grant_encoding_is_rejected(context,token):
    with pytest.raises(HTTPException) as error: authorize(context,token)
    assert error.value.status_code==401

def test_revoked_session_immediately_invalidates_grant(context):
    context.session.revoked_at=context.now
    with pytest.raises(HTTPException) as error: authorize(context)
    assert error.value.status_code==401

def test_unknown_session_is_rejected(context):
    with pytest.raises(HTTPException) as error:
        authorize(context,altered(context,sid=str(uuid.uuid4())))
    assert error.value.status_code==401

def test_session_cannot_be_rebound_to_another_user(context):
    with pytest.raises(HTTPException) as error:
        authorize(context,altered(context,uid=str(uuid.uuid4())))
    assert error.value.status_code==401

def test_another_workspace_is_not_authorized(context):
    with pytest.raises(HTTPException) as error:
        authorize(context,altered(context,wid=str(uuid.uuid4())))
    assert error.value.status_code==404

def test_another_project_is_not_authorized(context):
    with pytest.raises(HTTPException) as error:
        authorize(context,altered(context,pid=str(uuid.uuid4())))
    assert error.value.status_code==401

def test_project_owner_is_rechecked_at_read_time(context):
    context.workspace.project.user_id=uuid.uuid4()
    with pytest.raises(HTTPException) as error: authorize(context)
    assert error.value.status_code==404

@pytest.mark.parametrize('status',['archived','deleted','cache_expired'])
def test_inaccessible_workspace_invalidates_existing_grant(context,status):
    context.workspace.status=status
    with pytest.raises(HTTPException) as error: authorize(context)
    assert error.value.status_code==404

def test_archived_project_invalidates_existing_grant(context):
    context.workspace.project.archived_at=context.now
    with pytest.raises(HTTPException) as error: authorize(context)
    assert error.value.status_code==404

def test_runtime_restart_invalidates_previous_grant(context):
    context.lease['value']='b'*64
    with pytest.raises(HTTPException) as error: authorize(context)
    assert error.value.status_code==401

@pytest.mark.parametrize('changes',[{'purpose':'other'},{'origin':'https://attacker.example'}])
def test_grant_purpose_and_origin_cannot_change(context,changes):
    with pytest.raises(HTTPException) as error: authorize(context,altered(context,**changes))
    assert error.value.status_code==401

def test_gateway_origin_cannot_serve_customer_preview(context):
    context.request.url='https://gateway.example/preview/placeholder/'
    with pytest.raises(HTTPException) as error: authorize(context)
    assert error.value.status_code==404

# Client explorer boundaries: run the existing JavaScript adapter without
# starting Pi, making network requests or loading an SDK/model.
_CLIENT_FILE_HARNESS = r'''
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const source=fs.readFileSync(input.source,'utf8');
const root=fs.realpathSync(input.root),other=fs.realpathSync(input.other);
const scope={directory:root};
const sandbox={path,process,Buffer,TextDecoder,URLSearchParams,setTimeout,clearTimeout,...fs,fsConstants:fs.constants,
  execFileSync(){throw Error('No Git or model execution in file boundary tests');}};
const run=vm.createContext(sandbox);
vm.runInContext(source.slice(source.indexOf('function workspaceFile('),source.indexOf('function piNativeTodos(')),run);
const query=name=>new URLSearchParams({path:name});
const read=name=>run.projectFileRequest(scope,'/file/content',query(name));
const list=name=>run.projectFileRequest(scope,'/file',query(name));
const reject=(fn,status)=>assert.throws(fn,e=>e.status===status && !e.message.includes(other));
fs.mkdirSync(path.join(root,'sub'));
fs.writeFileSync(path.join(root,'sub','file.txt'),'OWN_FILE');
fs.writeFileSync(path.join(other,'file.txt'),'OTHER_ACCOUNT_CANARY');
const own=path.join(root,'sub','file.txt'),outside=path.join(other,'file.txt');
const action=input.action;
if(action==='own'){
 assert.equal(read('sub/file.txt').content,'OWN_FILE');
 assert.equal(list('sub')[0].path,'sub/file.txt');
 assert.equal(fs.readFileSync(own,'utf8'),'OWN_FILE');
}else if(action==='policy'){
 for(const name of ['../file.txt','/etc/hostname','sub/../../file.txt','sub\\file.txt','.git/config','.env'])reject(()=>read(name),400);
}else if(action==='symlink'){
 fs.symlinkSync(outside,path.join(root,'outside.txt'));reject(()=>read('outside.txt'),403);
 assert.equal(list('').some(x=>x.name==='outside.txt'),false);
}else if(action==='hardlink'){
 fs.linkSync(outside,path.join(root,'linked.txt'));reject(()=>read('linked.txt'),403);
}else if(action==='fifo'){
 // proc pseudo-files are not used: make a disposable FIFO with a fixed tool.
 const {execFileSync}=await import('node:child_process');
 execFileSync('mkfifo',[path.join(root,'pipe')]);reject(()=>read('pipe'),404);
}else if(action==='large'){
 fs.writeFileSync(own,Buffer.alloc(1024*1024+1,65));reject(()=>read('sub/file.txt'),413);
}else if(action==='binary'){
 fs.writeFileSync(own,Buffer.from([0,1,2]));reject(()=>read('sub/file.txt'),415);
 fs.writeFileSync(own,Buffer.from([0xff]));reject(()=>read('sub/file.txt'),415);
}else if(action==='missing'){
 reject(()=>read('missing'),404);reject(()=>read('sub'),404);
}else if(action==='grow'){
 sandbox.fstatSync=fd=>{const info=fs.fstatSync(fd);fs.appendFileSync(own,Buffer.alloc(1024*1024,65));return info;};
 reject(()=>read('sub/file.txt'),413);
}else if(['leaf-race','directory-race','list-race','root-race'].includes(action)){
 const original=run.workspaceFile;let changed=false;
 run.workspaceFile=(...args)=>{
  const result=original(...args);
  if(!changed){changed=true;
   if(action==='leaf-race'){fs.unlinkSync(own);fs.symlinkSync(outside,own);}
   else if(action==='root-race'){fs.renameSync(root,root+'-held');fs.symlinkSync(other,root);}
   else{fs.renameSync(path.join(root,'sub'),path.join(root,'held'));fs.symlinkSync(other,path.join(root,'sub'));}
  }
  return result;
 };
 reject(()=>action==='list-race'?list('sub'):read('sub/file.txt'),403);
}else if(action==='fd-cleanup'){
 const before=fs.readdirSync('/proc/self/fd').length;
 for(let i=0;i<30;i++){assert.equal(read('sub/file.txt').content,'OWN_FILE');reject(()=>read('missing'),404);}
 assert.equal(fs.readdirSync('/proc/self/fd').length,before);
 }else if(action==='git-status'){
 const {execFileSync,spawn}=await import('node:child_process');
 const env={PATH:'/usr/bin:/bin',HOME:'/nonexistent',GIT_CONFIG_NOSYSTEM:'1',GIT_CONFIG_GLOBAL:'/dev/null'};
 const git=args=>execFileSync('/usr/bin/git',args,{cwd:root,env,stdio:['ignore','pipe','ignore']});
 git(['init','--quiet']);git(['add','sub/file.txt']);
 git(['-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','fixture']);
 fs.writeFileSync(own,'MODIFIED_OWN_FILE');
 const hook=path.join(root,'.git','test-fsmonitor');
 fs.writeFileSync(hook,'#!/bin/sh\nprintf bad > ./hook-fired\n');fs.chmodSync(hook,0o755);
 git(['config','core.fsmonitor',hook]);
 process.env.PI_GATEWAY_INTERNAL_TOKEN='TEST_TOKEN_MUST_NOT_REACH_GIT';
 process.env.OPENAI_API_KEY='TEST_KEY_MUST_NOT_REACH_GIT';
 process.env.GIT_CONFIG_COUNT='1';process.env.GIT_CONFIG_KEY_0='core.fsmonitor';process.env.GIT_CONFIG_VALUE_0=hook;
 let calls=0;
 sandbox.spawn=(program,args,opts)=>{
  calls++;assert.equal(program,'/usr/bin/git');assert.equal(opts.env.PI_GATEWAY_INTERNAL_TOKEN,undefined);
  assert.equal(opts.env.OPENAI_API_KEY,undefined);assert.equal(opts.env.GIT_CONFIG_COUNT,undefined);
  assert.equal(opts.env.HOME,'/nonexistent');assert.ok(args.includes('core.hooksPath=/dev/null'));
  assert.ok(args.includes('core.fsmonitor=false'));assert.ok(args.includes('credential.helper='));
  return spawn(program,args,opts);
 };
 const status=await run.projectFileRequest(scope,'/file/status',query(''));
 assert.deepEqual(JSON.parse(JSON.stringify(status)),[{status:'M',path:'sub/file.txt'}]);
 const branch=await run.projectFileRequest(scope,'/vcs',query(''));
 assert.ok(branch.branch);assert.equal(calls,2);assert.equal(fs.existsSync(path.join(root,'hook-fired')),false);
}else if(action==='git-async'||action==='git-output-bound'||action==='git-errors'){
 const {spawn}=await import('node:child_process');
 sandbox.spawn=(_program,_args,opts)=>spawn(process.execPath,['-e',
  action==='git-async'?'setTimeout(()=>process.stdout.write("fixture"),180)':
  action==='git-output-bound'?'process.stdout.write("A".repeat(1100000));setInterval(()=>{},1000)':
  'process.stderr.write("PRIVATE_BACKEND_ERROR");process.exitCode=1'],opts);
 const pending=run.projectFileRequest(scope,'/vcs',query(''));
 if(action==='git-async'){
  const first=await Promise.race([pending.then(()=> 'git'),new Promise(resolve=>setTimeout(()=>resolve('timer'),30))]);
  assert.equal(first,'timer');assert.equal((await pending).branch,'fixture');
 }else{
  const result=await pending;assert.equal(result.branch,'');
  assert.equal(JSON.stringify(result).includes('PRIVATE_BACKEND_ERROR'),false);
 }
}else if(action.startsWith('context-')){
 fs.writeFileSync(path.join(path.dirname(root),'AGENTS.md'),'PARENT_CONTEXT_MUST_NOT_LOAD');
 if(action==='context-own'){
  fs.writeFileSync(path.join(root,'AGENTS.md'),'OWN_CONTEXT');
  const result=run.projectContextFiles(scope);
  assert.equal(result.length,1);assert.equal(result[0].content,'OWN_CONTEXT');
 }else{
  if(action==='context-link')fs.symlinkSync(outside,path.join(root,'AGENTS.md'));
  assert.equal(run.projectContextFiles(scope).length,0);
 }
}else if(action==='owner-scope'){
 const account={user_id:input.ownerB,workspaces:[{id:input.workspaceB,project_id:input.projectB,directory:other}]};
 sandbox.browserPrincipal=()=>account;
 sandbox.CATALOG_DIRECTORY='/unused-catalog';
 vm.runInContext(source.slice(source.indexOf('async function scope('),source.indexOf('// Read only public model definitions.')),run);
 const queryA=new URLSearchParams({directory:root});
 await assert.rejects(()=>run.scope({},queryA),e=>e.status===403);
 const result=await run.scope({},new URLSearchParams({directory:other}));
 assert.equal(result.directory,other);assert.equal(result.userId,input.ownerB);
}else throw Error('Unknown test');
console.log('PASS');
'''

@pytest.mark.parametrize('action',[
    'own','policy','symlink','hardlink','fifo','large','binary','missing','grow',
    'leaf-race','directory-race','list-race','root-race','fd-cleanup','owner-scope',
    'git-status','git-async','git-output-bound','git-errors',
    'context-own','context-link','context-ancestor'])
def test_client_explorer_pins_owned_files_and_bounds_reads(tmp_path, action):
    import os
    import shutil
    import subprocess
    from pathlib import Path
    if os.name != 'posix' or not Path('/proc/self/fd').exists():
        pytest.skip('Linux descriptor-relative client file access')
    node=shutil.which('node')
    if not node:
        pytest.skip('Node runtime unavailable')
    owner_a, owner_b, workspace_a, workspace_b, project_b=[str(uuid.uuid4()) for _ in range(5)]
    root=tmp_path/owner_a/workspace_a/'repo'
    other=tmp_path/owner_b/workspace_b/'repo'
    root.mkdir(parents=True);other.mkdir(parents=True)
    payload=dict(source=str(Path(__file__).resolve().parents[2]/'integration/pi-central.mjs'),
                 root=str(root),other=str(other),action=action,
                 ownerB=owner_b,workspaceB=workspace_b,projectB=project_b)
    result=subprocess.run([node,'--input-type=module','-e',_CLIENT_FILE_HARNESS],
                          input=json.dumps(payload),text=True,capture_output=True,timeout=8)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='PASS'

@pytest.mark.parametrize('supported',[True,False])
def test_client_project_settings_cannot_silently_trust_repository_code(supported):
    import shutil
    import subprocess
    from pathlib import Path
    node=shutil.which('node')
    if not node:
        pytest.skip('Node runtime unavailable')
    source=str(Path(__file__).resolve().parents[2]/'integration/pi-central.mjs')
    script=r'''
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const source=fs.readFileSync(input.source,'utf8');
const start=source.indexOf('const settingsManager=sdk.SettingsManager.inMemory();');
const end=source.indexOf('// Reuse installed todo extensions where present.',start);
assert.ok(start>=0&&end>start);
let trusted=true,calls=0;
const manager=input.supported?{setProjectTrusted(value){trusted=value;calls++;}}:{};
const context={sdk:{SettingsManager:{inMemory:()=>manager}}};
if(input.supported){
 vm.runInNewContext(source.slice(start,end),context);
 assert.equal(trusted,false);assert.equal(calls,1);
}else assert.throws(()=>vm.runInNewContext(source.slice(start,end),context),e=>e.status===503);
console.log('PASS');
'''
    result=subprocess.run([node,'--input-type=module','-e',script],
                          input=json.dumps(dict(source=source,supported=supported)),
                          text=True,capture_output=True,timeout=5)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='PASS'

# Exercise the staged project's real Node IPC/lifecycle. These tests do not
# simulate successful OS containment: the namespace mount requires a VPS gate.
@pytest.mark.parametrize('action',['plan','rpc','cancel','stuck-cancel','root-mismatch','launcher-failure'])
def test_project_tool_boundary_protocol_and_fail_closed(tmp_path, action):
    import shutil
    import subprocess
    from pathlib import Path
    node=shutil.which('node')
    if not node:
        pytest.skip('Node runtime unavailable')
    root=tmp_path/'project';root.mkdir()
    other=tmp_path/'other';other.mkdir()
    fixture=tmp_path/'tools.mjs'
    fixture.write_text(r'''
import fs from 'node:fs';
try{fs.fstatSync(3);throw Error('Host project descriptor leaked');}
catch(e){if(e.code!=='EBADF')throw e;}
let calls=0;
const definition=name=>({name,async execute(id,args,signal,update,context){
 if(args.stuck)return new Promise(()=>{});
 if(args.wait)return new Promise((resolve,reject)=>{
  signal.addEventListener('abort',()=>reject(Error('cancelled')),{once:true});
 });
 update?.({content:[{type:'text',text:'progress'}]});
 return {content:[{type:'text',text:JSON.stringify({calls:++calls,cwd:context.cwd,
  leaked:process.env.PROJECT_CANARY||null,input:context.model?.input})}]};
}});
export function createAllToolDefinitions(){
 return Object.fromEntries(['read','bash','edit','write','grep','find','ls','powershell']
  .map(name=>[name,definition(name)]));
}
''',encoding='utf8')
    script=r'''
import fs from 'node:fs';import path from 'node:path';import vm from 'node:vm';
import {spawn} from 'node:child_process';import {pathToFileURL} from 'node:url';
import {randomUUID} from 'node:crypto';import assert from 'node:assert/strict';
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const source=fs.readFileSync(input.source,'utf8');
const section=source.slice(source.indexOf('const PROJECT_SANDBOX_ENABLED='),source.indexOf('class SdkAgent {'));
let spawns=0,child;
const context={process,Buffer,path,setTimeout,clearTimeout,randomUUID,
 withWorkspaceDirectory(scope,relative,operation){
  const fd=fs.openSync(input.action==='root-mismatch'?input.other:input.root,'r');
  try{return operation(fd);}finally{fs.closeSync(fd);}
 },spawn(file,args,options){
  spawns++;
  assert.equal(file,'/usr/local/libexec/pi-project-bwrap');
  assert.equal(options.env.PROJECT_CANARY,undefined);
  assert.equal(options.env.NODE_OPTIONS,undefined);
  if(input.action==='launcher-failure')return spawn('/nonexistent-pi-boundary',[],options);
  const code=args.at(-1).replace(
   'file:///opt/pi/node_modules/@earendil-works/pi-coding-agent/dist/core/tools/index.js',
   pathToFileURL(input.fixture).href);
  child=spawn(process.execPath,['--input-type=module','-e',code],{
   ...options,cwd:input.root,stdio:['pipe','pipe','pipe',options.stdio[3]]});
  return child;
 }};
vm.createContext(context);vm.runInContext(section,context);
const plan=vm.runInContext('projectSandboxPlan',context);
const directory='/var/lib/opencode-workspaces/owner/project/repo';
const p=plan({directory},'/usr/bin/node');
assert.ok(p.args.includes('--unshare-net'));assert.ok(p.args.includes('--unshare-pid'));
assert.ok(p.args.includes('--clearenv'));assert.equal(p.env.HOME,'/tmp/home');
assert.ok(!p.args.includes('/run'));assert.ok(!p.args.includes('/etc'));
assert.throws(()=>plan({directory:'/home/other'},'/usr/bin/node'));
assert.throws(()=>plan({directory:directory+'/../other'},'/usr/bin/node'));
assert.throws(()=>plan({directory},'/home/tahir/node'));
// The local runtime path is different; keep production validation and substitute
// only the runtime argument in this isolated protocol harness.
vm.runInContext('const originalPlan=projectSandboxPlan;projectSandboxPlan=scope=>originalPlan(scope,"/usr/bin/node")',context);
const Boundary=vm.runInContext('ProjectToolSandbox',context);
const boundary=new Boundary({directory});
process.env.PROJECT_CANARY='never-forward-provider-or-control-secrets';
let updates=0;
try{
 if(input.action==='plan'){
  const sdk={};
  for(const name of ['Read','Bash','Edit','Write','Grep','Find','Ls','PowerShell'])
   sdk['create'+name+'ToolDefinition']=()=>({name:name.toLowerCase(),execute(){throw Error('Host execution forbidden');}});
  const defs=boundary.definitions(sdk);assert.equal(defs.length,8);
  assert.equal(spawns,0); // Definitions/catalog creation must not start a worker.
 }else if(['launcher-failure','root-mismatch'].includes(input.action)){
  await assert.rejects(boundary.execute('read','x',{},null));
  assert.equal(spawns,1);assert.equal(boundary.closed,true);
 }else{
  const result=await boundary.execute('read','x',{},null,()=>updates++,{
   model:{input:['text'],apiKey:'secret',headers:{Authorization:'secret'}},credentials:{secret:true}});
  const first=JSON.parse(result.content[0].text);
  assert.equal(first.calls,1);assert.equal(first.leaked,null);assert.equal(first.cwd,input.root);
  assert.deepEqual(first.input,['text']);assert.equal(updates,1);
  const second=await boundary.execute('bash','y',{},null);
  assert.equal(JSON.parse(second.content[0].text).calls,2);assert.equal(spawns,1);
  if(input.action==='cancel'){
   const controller=new AbortController();
   const pending=boundary.execute('bash','z',{wait:true},controller.signal);
   setTimeout(()=>controller.abort(),80);
   await assert.rejects(pending,/cancelled/);
   assert.equal(boundary.pending.size,0);
   const again=await boundary.execute('ls','after-stop',{},null);
   assert.equal(JSON.parse(again.content[0].text).calls,3);assert.equal(spawns,1);
  }
  if(input.action==='stuck-cancel'){
   const controller=new AbortController();
   const pending=boundary.execute('bash','stuck',{stuck:true},controller.signal);
   setTimeout(()=>controller.abort(),80);
   await assert.rejects(pending,/closed/);
   const again=await boundary.execute('ls','after-forced-stop',{},null);
   assert.equal(JSON.parse(again.content[0].text).calls,1);assert.equal(spawns,2);
  }
  assert.equal(boundary.pending.size,0);
 }
}finally{boundary.close();delete process.env.PROJECT_CANARY;}
assert.equal(boundary.closed,true);
await assert.rejects(boundary.execute('read','closed',{},null));
console.log('PASS');
'''
    result=subprocess.run([node,'--input-type=module','-e',script],
        input=json.dumps(dict(source=str(Path(__file__).resolve().parents[2]/'integration/pi-central.mjs'),
                              root=str(root),other=str(other),fixture=str(fixture),action=action)),
        capture_output=True,text=True,timeout=12)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='PASS'
