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
const sandbox={path,process,Buffer,TextDecoder,URLSearchParams,setTimeout,clearTimeout,PROJECT_SANDBOX_ENABLED:false,...fs,fsConstants:fs.constants,
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

@pytest.mark.parametrize('attack',['normal','symlink','hardlink','fifo','parent-race','growing','export'])
def test_backend_owned_file_access_uses_pinned_descriptors(tmp_path,monkeypatch,attack):
    from app.services import workspaces as files
    from pathlib import Path
    import os,zipfile
    root=tmp_path/'repo';root.mkdir();(root/'sub').mkdir()
    own=root/'sub'/'file.txt';own.write_text('OWN_CANARY')
    other=tmp_path/'foreign';other.mkdir();secret=other/'file.txt';secret.write_text('FOREIGN_CANARY')
    workspace=SimpleNamespace(status='ready')
    monkeypatch.setattr(files,'root_for',lambda *args,**kwargs:root)
    monkeypatch.setattr(files,'quota_bytes',lambda *args:1024*1024)
    if attack=='normal':
        assert files.content(workspace,'sub/file.txt')=='OWN_CANARY'
        return
    if attack=='export':
        (root/'sub'/'link.txt').symlink_to(secret)
        archive=files.export(workspace)
        try:
            with zipfile.ZipFile(archive) as result:
                assert result.namelist()==['sub/file.txt']
                assert result.read('sub/file.txt')==b'OWN_CANARY'
        finally:archive.unlink()
        return
    if attack in {'symlink','hardlink','fifo'}:
        own.unlink()
        if attack=='symlink':own.symlink_to(secret)
        elif attack=='hardlink':os.link(secret,own)
        else:os.mkfifo(own)
    elif attack=='parent-race':
        original=files.safe_path;changed=False
        def swap(*args):
            nonlocal changed
            result=original(*args)
            if not changed:
                changed=True;(root/'sub').rename(root/'held');(root/'sub').symlink_to(other)
            return result
        monkeypatch.setattr(files,'safe_path',swap)
    else:
        original=files.os.fstat
        def grow(fd):
            result=original(fd)
            with own.open('ab') as output:output.write(b'A'*1000001)
            return result
        monkeypatch.setattr(files.os,'fstat',grow)
    with pytest.raises(HTTPException) as error:files.content(workspace,'sub/file.txt')
    assert error.value.status_code in {403,413}
    assert 'FOREIGN_CANARY' not in str(error.value.detail)

def test_project_network_acl_rejects_private_metadata_and_unapproved_hosts():
    import subprocess,shutil
    from pathlib import Path
    node=shutil.which('node')
    if not node:pytest.skip('Node runtime unavailable')
    script=r'''
import fs from 'node:fs';import net from 'node:net';import vm from 'node:vm';import assert from 'node:assert/strict';
const source=fs.readFileSync(process.argv[1],'utf8'),context=vm.createContext({net,URL});
vm.runInContext(source.slice(source.indexOf('function publicProjectAddress('),source.indexOf('function projectNetworkBridge(')),context);
for(const ip of ['127.0.0.1','10.0.0.1','172.16.1.1','192.168.1.2','169.254.169.254','168.63.129.16','100.64.0.1','0.0.0.0','198.18.0.1','::1','fe80::1','fc00::1','::ffff:127.0.0.1','2001:db8::1','2002:7f00:1::'])
 assert.equal(context.publicProjectAddress(ip),false,ip);
for(const ip of ['1.1.1.1','8.8.8.8','2606:4700:4700::1111'])assert.equal(context.publicProjectAddress(ip),true,ip);
for(const authority of ['localhost:443','169.254.169.254:443','github.com.evil.invalid:443','github.com:80','github.com:443@localhost','github.com.:443','GITHUB.COM:443\r\nHost: localhost'])
 assert.throws(()=>context.projectEgressTarget(authority));
assert.equal(context.projectEgressTarget('registry.npmjs.org:443'),'registry.npmjs.org');
assert.equal(context.projectEgressTarget('pypi.org:443'),'pypi.org');
console.log('PASS');
'''
    result=subprocess.run([node,'--input-type=module','-e',script,str(Path(__file__).resolve().parents[2]/'integration/pi-central.mjs')],capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stderr

@pytest.mark.parametrize('attack',['normal','link','race','cleanup-link'])
def test_pi_attachment_staging_cannot_follow_replaced_parent(tmp_path,attack):
    import subprocess,shutil
    from pathlib import Path
    node=shutil.which('node')
    if not node:pytest.skip('Node runtime unavailable')
    root=tmp_path/'repo';other=tmp_path/'foreign';root.mkdir();other.mkdir()
    script=r'''
import fs from 'node:fs';import path from 'node:path';import vm from 'node:vm';import assert from 'node:assert/strict';import {randomUUID} from 'node:crypto';
const input=JSON.parse(fs.readFileSync(0,'utf8')),source=fs.readFileSync(input.source,'utf8');
const scope={directory:input.root},session='pi_'+ 'a'.repeat(32);
const sandbox={...fs,path,process,Buffer,URL,TextDecoder,randomUUID,fsConstants:fs.constants,console:{warn(){}}};
const context=vm.createContext(sandbox);
vm.runInContext(source.slice(source.indexOf('function cleanPiStagedDirectories('),source.indexOf('function piNativeTodos(')),context);
const parts=[{type:'file',filename:'note.txt',url:'data:text/plain;base64,'+Buffer.from('OWN_UPLOAD').toString('base64')}];
const base=path.join(input.root,'.pi-uploads');
if(input.attack==='link')fs.symlinkSync(input.other,base);
if(input.attack==='race'){
 let swapped=false;
 sandbox.mkdirSync=(target,options)=>{
  fs.mkdirSync(target,options);
  if(!swapped){swapped=true;fs.renameSync(base,base+'-held');fs.symlinkSync(input.other,base);}
 };
}
if(['link','race'].includes(input.attack)){
 assert.throws(()=>context.piPromptParts(parts,scope,session),error=>error.status===403);
 assert.deepEqual(fs.readdirSync(input.other),[]);
}else{
 const result=context.piPromptParts(parts,scope,session);
 const filename=path.join(result.staged[0],'note.txt');assert.equal(fs.readFileSync(filename,'utf8'),'OWN_UPLOAD');
 if(input.attack==='cleanup-link'){
  const canary=path.join(input.other,'file.txt');fs.writeFileSync(canary,'FOREIGN_CANARY');
  fs.renameSync(base,base+'-held');fs.symlinkSync(input.other,base);
  context.cleanPiStagedDirectories(scope,session,result.staged);
  assert.equal(fs.readFileSync(canary,'utf8'),'FOREIGN_CANARY');
 }else{
  context.cleanPiFinishedFiles(scope,session);assert.equal(fs.existsSync(filename),false);
 }
}
console.log('PASS');
'''
    result=subprocess.run([node,'--input-type=module','-e',script],input=json.dumps(dict(source=str(Path(__file__).resolve().parents[2]/'integration/pi-central.mjs'),root=str(root),other=str(other),attack=attack)),capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stderr

def test_inline_images_reject_large_pixel_dimensions_before_sdk_decoding():
    import subprocess,shutil
    from pathlib import Path
    node=shutil.which('node')
    if not node:pytest.skip('Node runtime unavailable')
    script=r'''
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const source=fs.readFileSync(process.argv[1],'utf8'),context=vm.createContext({Buffer});
vm.runInContext(source.slice(source.indexOf('function piImagePixels('),source.indexOf('function piPromptParts(')),context);
const png=Buffer.alloc(24);png.writeUInt32BE(200,16);png.writeUInt32BE(100,20);
assert.equal(context.piImagePixels(png,'image/png'),20000);
png.writeUInt32BE(100000,16);assert.throws(()=>context.piImagePixels(png,'image/png'),e=>e.status===422);
assert.throws(()=>context.piImagePixels(Buffer.from([255,216,255,217]),'image/jpeg'),e=>e.status===422);
const webp=Buffer.alloc(30);webp.write('VP8X',12);webp.writeUInt32LE(10,16);
webp.writeUIntLE(199,24,3);webp.writeUIntLE(99,27,3);
assert.equal(context.piImagePixels(webp,'image/webp'),20000);
webp.writeUIntLE(0xffffff,24,3);assert.throws(()=>context.piImagePixels(webp,'image/webp'),e=>e.status===422);
'''
    result=subprocess.run([node,'--input-type=module','-e',script,str(Path(__file__).resolve().parents[2]/'integration/pi-central.mjs')],capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stderr

@pytest.mark.parametrize('action',['allowed','private-dns','host-address','unapproved','cancel-dns'])
def test_project_egress_bridge_pins_dns_and_closes_cancelled_tunnels(tmp_path,action):
    import subprocess,shutil
    from pathlib import Path
    node=shutil.which('node')
    if not node:pytest.skip('Node runtime unavailable')
    script=r'''
import fs from 'node:fs';import net from 'node:net';import http2 from 'node:http2';import vm from 'node:vm';
import {Duplex,PassThrough} from 'node:stream';import assert from 'node:assert/strict';
const input=JSON.parse(fs.readFileSync(0,'utf8')),source=fs.readFileSync(input.source,'utf8');
let connects=0,lookups=0,resolveDns;
const context=vm.createContext({URL,http2,Date,Set,Buffer,setTimeout,clearTimeout,
 networkInterfaces:()=>({host:[{address:input.action==='host-address'?'1.1.1.1':'127.0.0.1'}]}),
 net:{isIP:net.isIP,connect(options){
  connects++;assert.equal(options.host,'1.1.1.1');assert.equal(options.port,443);
  const socket=new Duplex({read(){},write(chunk,encoding,callback){this.push(chunk);callback();}});
  socket.setTimeout=()=>socket;queueMicrotask(()=>socket.emit('connect'));return socket;
 }},lookupAddress:async()=>{
  lookups++;
  if(input.action==='cancel-dns')await new Promise(resolve=>resolveDns=resolve);
  return [{address:input.action==='private-dns'?'169.254.169.254':'1.1.1.1',family:4}];
 }});
vm.runInContext(source.slice(source.indexOf('function publicProjectAddress('),source.indexOf('function projectToolResourceLimits(')),context);
const upstream=new PassThrough(),downstream=new PassThrough();
const bridge=context.projectNetworkBridge(Duplex.from({readable:upstream,writable:downstream}));
const client=http2.connect('http://fixture',{createConnection:()=>Duplex.from({readable:downstream,writable:upstream})});client.on('error',()=>{});
const request=client.request({':method':'CONNECT',':authority':input.action==='unapproved'?'localhost:443':'registry.npmjs.org:443'});request.on('error',()=>{});
try{
 if(input.action==='cancel-dns'){
  while(!resolveDns)await new Promise(resolve=>setTimeout(resolve,1));
  request.close();await new Promise(resolve=>setTimeout(resolve,10));resolveDns();
  await new Promise(resolve=>setTimeout(resolve,10));assert.equal(connects,0);
 }else{
  const status=await new Promise((resolve,reject)=>{request.once('response',headers=>resolve(headers[':status']));request.once('error',reject);});
  assert.equal(status,input.action==='allowed'?200:403);
  if(input.action==='allowed'){
   const echoed=new Promise(resolve=>request.once('data',value=>resolve(value.toString())));
   request.write('OWN_PACKAGE_PAYLOAD');assert.equal(await echoed,'OWN_PACKAGE_PAYLOAD');
   assert.equal(connects,1);assert.equal(lookups,1);
  }else assert.equal(connects,0);
 }
}finally{request.close();client.destroy();bridge.close();}
'''
    result=subprocess.run([node,'--input-type=module','-e',script],input=json.dumps(dict(source=str(Path(__file__).resolve().parents[2]/'integration/pi-central.mjs'),socket=str(tmp_path/'egress.sock'),action=action)),capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stderr

def test_login_revocation_runs_once_after_commit_and_discards_rollback(monkeypatch):
    from sqlalchemy.orm import Session
    from app.routes import management
    calls=[]
    monkeypatch.setattr(management,'_ai_pi_invalidate',lambda user_id,**kw:calls.append((str(user_id),kw)))
    first,second=SimpleNamespace(id=uuid.uuid4()),SimpleNamespace(id=uuid.uuid4())
    with Session() as db:
        monkeypatch.setattr(db,'execute',lambda *args,**kwargs:None)
        db.begin();management.revoke(db,first);management.revoke(db,first)
        assert calls==[]
        db.commit();assert calls==[(str(first.id),{'revoke_login':True})]
        db.begin();management.revoke(db,first);db.rollback()
        db.begin();management.revoke(db,second);db.commit()
        assert calls==[(str(first.id),{'revoke_login':True}),(str(second.id),{'revoke_login':True})]

def test_provider_inventory_does_not_wait_for_optional_agent_discovery():
    import subprocess,shutil
    from pathlib import Path
    node=shutil.which('node')
    if not node:pytest.skip('Node runtime unavailable')
    script=r'''
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const source=fs.readFileSync(process.argv[1],'utf8');let finishAgents,events=0,providerCalls=0;
const context=vm.createContext({ownerScope:()=> 'owner',presentationRevision:1,agentsSnapshot:null,
 agents:()=>new Promise(resolve=>finishAgents=resolve),
 configuredProviders:async()=>{providerCalls++;return {providers:['fixture']};},
 window:{dispatchEvent(){events++;}},CustomEvent:class{}});
vm.runInContext(source.slice(source.indexOf('let workspaceSnapshot=null,workspacePending=null;'),source.indexOf('// Restore the original provider-error classification')),context);
const [first,second]=await Promise.all([context.workspaceRegistry(),context.workspaceRegistry()]);
assert.equal(first,second);assert.equal(providerCalls,1);assert.equal(first.data.providers[0],'fixture');
assert.equal(first.agents.length,0);assert.equal(events,0);
finishAgents([{name:'ready-later'}]);await new Promise(resolve=>setImmediate(resolve));
assert.equal(first.agents[0].name,'ready-later');assert.equal(events,1);
'''
    result=subprocess.run([node,'--input-type=module','-e',script,str(Path(__file__).resolve().parents[2]/'app.js')],capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stderr

@pytest.mark.parametrize('action',['normal','large','stderr'])
def test_administrative_git_output_is_bounded_before_gateway_allocation(tmp_path,action):
    import sys,os
    from app.services import workspaces
    code={'normal':'print("OWN_STATUS")','large':'import sys;sys.stdout.write("A"*5000000)',
          'stderr':'import sys;sys.stderr.write("PRIVATE_ERROR");sys.exit(1)'}[action]
    if action=='large':
        with pytest.raises(HTTPException) as error:
            workspaces._bounded_git_result([sys.executable,'-c',code],tmp_path,dict(os.environ),())
        assert error.value.status_code==413
    else:
        result=workspaces._bounded_git_result([sys.executable,'-c',code],tmp_path,dict(os.environ),())
        assert result.stdout==('OWN_STATUS\n' if action=='normal' else '')
        assert result.stderr==''

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
const context={process,Buffer,path,setTimeout,clearTimeout,randomUUID,PI_AGENT_DIR:'/operator/agent',
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

@pytest.mark.parametrize('action',[
    'control-token','origin-binding','expired','late-handoff','login-revocation',
    'workspace-scope','lease-expiry','renewal-order','live-only-scope'])
def test_customer_pi_authority_is_local_session_bound_and_revocable(action):
    import shutil
    import subprocess
    from pathlib import Path
    node=shutil.which('node')
    if not node: pytest.skip('Node runtime unavailable')
    script=r'''
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
import {randomUUID,timingSafeEqual} from 'node:crypto';
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const source=fs.readFileSync(input.source,'utf8');
let clock=1800000000000,next=0;const timers=new Map(),pool=new Map();
class Clock extends Date{static now(){return clock;}}
const context={Date:Clock,Buffer,URL,randomUUID,timingSafeEqual,pool,
 PROJECT_SANDBOX_ENABLED:true,
 process:{env:{PI_GATEWAY_LIVE_TOKEN:'a'.repeat(48),PI_GATEWAY_TEST_TOKEN:'b'.repeat(48)}},
 setTimeout(fn,ms){const id=++next;timers.set(id,{fn,ms});return id;},
 clearTimeout(id){timers.delete(id);}};
vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('const BOOTSTRAP_HOST='),source.indexOf('async function scope(')),context);
const run=code=>vm.runInContext(code,context);
const account={user_id:randomUUID(),auth_session_id:randomUUID(),auth_created_at:clock-5000,
 origin:'https://opencode-gateway.codes',issued_at:clock-100,expires_at:clock+10000,
 workspaces:[{id:randomUUID(),project_id:randomUUID(),directory:'/owned/project'}]};
context.account=account;
const request={headers:{host:'opencode-gateway.codes'}};
const response={writeHead(status,headers){this.status=status;this.headers=headers;},end(){}};
context.request=request;context.response=response;
function issue(value=account){context.account=value;run('issueBrowserGrant(response,account,request)');}
if(input.action==='live-only-scope'){
 context.process.env.PI_PROJECT_SANDBOX_ORIGIN=account.origin;
 assert.equal(run('projectSandboxEnabled(account.origin)'),true);
 assert.equal(run('projectSandboxEnabled("https://test.opencode-gateway.codes")'),false);
 assert.equal(run('projectSandboxEnabled(undefined)'),false);
 const req={headers:{host:'pi-internal','x-pi-gateway-origin':account.origin}};context.req=req;
 assert.equal(run('fromGateway(req)'),false);
 req.headers['x-pi-gateway-token']='a'.repeat(48);assert.equal(run('fromGateway(req)'),true);
 req.headers['x-pi-gateway-origin']='https://test.opencode-gateway.codes';
 delete req.headers['x-pi-gateway-token'];delete context.process.env.PI_GATEWAY_TEST_TOKEN;
 assert.equal(run('fromGateway(req)'),true);
 delete req.headers['x-pi-gateway-origin'];
 assert.equal(run('gatewayOrigin(req)'),'https://test.opencode-gateway.codes');
}else if(input.action==='control-token'){
 const req={headers:{host:'pi-internal','x-pi-gateway-origin':account.origin}};
 context.req=req;
 assert.equal(run('fromGateway(req)'),false);
 req.headers['x-pi-gateway-token']='a'.repeat(48);assert.equal(run('fromGateway(req)'),true);
 req.headers['x-pi-gateway-token']='b'.repeat(48);assert.equal(run('fromGateway(req)'),false);
 req.headers['x-pi-gateway-token']='a'.repeat(48);req.headers['x-forwarded-for']='127.0.0.1';
 assert.equal(run('fromGateway(req)'),false);
 delete req.headers['x-forwarded-for'];delete context.process.env.PI_GATEWAY_LIVE_TOKEN;
 assert.equal(run('fromGateway(req)'),false);
}else if(input.action==='origin-binding'){
 issue();const cookie=response.headers['set-cookie'].split(';')[0];
 context.req={headers:{host:'test.opencode-gateway.codes',cookie}};
 assert.throws(()=>run('browserPrincipal(req)'),e=>e.status===401);
}else if(input.action==='expired'){
 account.expires_at=clock;assert.throws(()=>issue(),e=>e.status===401);
}else if(input.action==='late-handoff'){
 issue();clock+=100;
 run('revokeBrowserGrants(account.user_id,account.origin)');
 assert.throws(()=>issue(),e=>e.status===401);
 const renewed={...account,issued_at:clock+1,expires_at:clock+20000};clock+=2;
 issue(renewed);assert.equal(response.status,204);
}else if(input.action==='login-revocation'){
 issue();clock+=100;
 run('revokeBrowserGrants(account.user_id,account.origin,null,true)');
 account.issued_at=clock+1;account.expires_at=clock+20000;clock+=2;
 assert.throws(()=>issue(),e=>e.status===401); // Late bootstrap with old login.
 account.auth_session_id=randomUUID();account.auth_created_at=clock+1;
 account.issued_at=clock+2;clock+=3;issue();
}else if(input.action==='renewal-order'){
 issue();const old={...account};clock+=100;
 account.issued_at=clock;account.expires_at=clock+20000;issue();
 assert.throws(()=>issue(old),e=>e.status===401);
}else{
 issue();let closed=0;
 const scope={account,userId:account.user_id,workspaceId:account.workspaces[0].id,
  projectId:account.workspaces[0].project_id,directory:account.workspaces[0].directory};
 context.scope=scope;pool.set('worker',{scope,close(){closed++;}});
 assert.equal(run('assertProjectAuthority(scope)').user_id,account.user_id);
 if(input.action==='workspace-scope'){
  scope.directory='/other/customer';
  assert.throws(()=>run('assertProjectAuthority(scope)'),e=>e.status===401);
 }else{
  clock=account.expires_at+1;
  for(const timer of [...timers.values()])timer.fn();
  assert.equal(closed,1);
  assert.throws(()=>run('assertProjectAuthority(scope)'),e=>e.status===401);
 }
}
console.log('PASS');
'''
    result=subprocess.run([node,'--input-type=module','-e',script],
        input=json.dumps(dict(source=str(Path(__file__).resolve().parents[2]/'integration/pi-central.mjs'),action=action)),
        capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='PASS'
