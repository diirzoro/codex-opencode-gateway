#!/usr/bin/env node
'use strict';
// Native-only provider discovery regression. The always-running OpenCode server
// owns the provider/model catalog. No Gateway/browser provider registry.
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const app=fs.readFileSync('app.js','utf8');
const workspaceUI=fs.readFileSync('dashboards.js','utf8');
const dashboard=fs.readFileSync('management.js','utf8');
const pageHTML=fs.readFileSync('index.html','utf8');
const testNginx=fs.readFileSync('ops/native-direct/nginx.conf','utf8');
const authLocation=testNginx.slice(testNginx.indexOf('location ^~ /native-direct/api/auth/ {'),
  testNginx.indexOf('location = /native-direct/api/provider/auth {'));
assert(authLocation.includes('proxy_pass http://127.0.0.1:18098;'),
  'Credential mutations must use the existing TEST auth-capable transport');
assert(!authLocation.includes('18097'),'Discovery transport must not handle credential CRUD');
assert(authLocation.includes('auth_request /api/auth/me;'),'Keep Gateway login protection');
assert(authLocation.includes('limit_except PUT DELETE { deny all; }'));
assert(authLocation.includes('proxy_set_header Authorization "";'));
assert(authLocation.includes('proxy_set_header Cookie "";'));
const installer=fs.readFileSync('ops/native-direct/update-existing-test-nginx.sh','utf8');
assert(installer.indexOf('--data \'{}\'')<installer.indexOf('backup='),
  'Check Native schema rejection before modifying TEST routing');
assert(installer.includes('400|422)'));
const iconStart=workspaceUI.indexOf('const composerIcons=');
const iconEnd=workspaceUI.indexOf(';\n  for(const [id,markup]',iconStart);
assert(iconStart>=0&&iconEnd>iconStart,'Workspace composer icons missing');
const iconNames=[...workspaceUI.slice(iconStart,iconEnd).matchAll(/"([a-zA-Z][a-zA-Z0-9_-]+)":/g)].map(row=>row[1]);
assert(!iconNames.includes('composerNewTask'));
for(const id of iconNames){
  const inHTML=pageHTML.includes('id="'+id+'"')||pageHTML.includes("id='"+id+"'");
  const inJS=workspaceUI.includes(".id='"+id+"'")||workspaceUI.includes('.id="'+id+'"')||
    workspaceUI.includes("btn('"+id+"'")||workspaceUI.includes('btn("'+id+'"');
  assert(inHTML||inJS,'Workspace icon points to missing control: '+id);
}
assert(!app.includes('pickerProviders'),'Remove obsolete browser picker registry');
assert(!app.includes('og-native-provider-picker-v1'),'Remove localStorage provider picker');
assert(!app.includes('og-native-model-metadata-v1'),'Remove stale browser model cache');
assert(!app.includes('og-native-agent-metadata-v1'),'Remove stale browser agent cache');
assert(!dashboard.includes('/api/opencode/catalog/providers/'),'Dashboard must not use retired provider API paths');
assert(dashboard.includes('window.nativeDirectTest.configuredProviders()'),'Dashboard must share the Native-derived Workspace inventory');
const directList=dashboard.slice(dashboard.indexOf('async function accountCatalogRows()'),dashboard.indexOf('async function lookup(',dashboard.indexOf('async function accountCatalogRows()')));
assert(!directList.includes("direct('config/providers')"),'Dashboard must not call absent /config/providers');
assert(!directList.includes('visibility()')&&!directList.includes('api('),'Dashboard listing must not wait for Python Gateway');
assert(!app.includes("direct('config/providers')"),'Do not call absent Native /config/providers route');
assert(app.includes("path==='provider'?90000"),'7MB Native provider transfer must not use generic 18s deadline');
for(const obsolete of ['clientVerifiedProviders','deletedAuthSlots','rememberRevoked','verifyProviderModel','NATIVE-VERIFY-']){
  assert(!app.includes(obsolete),'Remove parallel provider state/checker: '+obsolete);
}


const begin=app.indexOf('window.nativeDirectTest=(()=>{');
const end=app.indexOf('\n})();',begin);
assert(begin>=0&&end>begin,'Native browser adapter not found');
const adapter=app.slice(begin,end+5);
const requests=[];
const metadata={
  providers:[
    {id:'opencode',name:'OpenCode',models:{'free-test':{name:'Free test',cost:{input:0,output:0}}}},
    {id:'deepseek',name:'DeepSeek',models:{chat:{name:'DeepSeek Chat'}}},
    {id:'google',name:'Google',models:{gemini:{name:'Gemini'}}}
  ],
  default:{opencode:'free-test'}
};
const agentMetadata=[{name:'build',mode:'primary',prompt:'NATIVE_ONLY'}];
const fullProviderCatalog={
  all:[...metadata.providers,...Array.from({length:75},(_,i)=>({
    id:'native-provider-'+i,name:'Native Provider '+i,models:{['model-'+i]:{name:'Model '+i}}
  }))],
  connected:['deepseek','google'],default:{opencode:'free-test'}
};
const policy={allowed_providers:[],hidden_providers:[],allowed_models:[],hidden_models:{}};
async function fetchMock(address){
  const pathname=new URL(address,'https://test.opencode-gateway.codes').pathname;
  requests.push(pathname);
  const payload=pathname.endsWith('/agent')?agentMetadata:
    pathname.endsWith('/provider')?fullProviderCatalog:null;
  assert(payload!==null,'Unexpected Native route '+pathname);
  return {ok:true,status:200,text:async()=>JSON.stringify(payload)};
}
function createClient(overrides={}){
  const window={nativeSession:null,workspaceRuntime:{clear(){}},dispatchEvent(){}};
  const context={
    window,currentUser:{id:'test-user'},
    location:{hostname:'test.opencode-gateway.codes',origin:'https://test.opencode-gateway.codes'},
    fetch:fetchMock,
    localStorage:{getItem:()=>null,setItem(){},removeItem(){}},
    sessionStorage:{getItem:()=>null,setItem(){},removeItem(){}},
    api:async path=>{assert.equal(path,'/api/opencode/display-policy');return policy;},
    URL,AbortSignal,AbortController,setTimeout,clearTimeout,
    CustomEvent:class CustomEvent{constructor(name,options){this.type=name;this.detail=options?.detail;}},
    invalidateProviderMutation(){},...overrides
  };
  vm.runInNewContext(adapter,context,{timeout:3000});
  return window.nativeDirectTest;
}
(async()=>{
  const native=createClient();
  const ws=await native.workspaceRegistry();
  assert.deepEqual([...ws.data.connected],['opencode','deepseek','google']);
  assert(ws.data.all.some(p=>p.id==='deepseek'));
  assert.equal(requests.length,2,'Workspace should call /provider and /agent only');
  assert(requests.filter(path=>path.endsWith('/provider')).length===1,'Native catalog should be fetched once');
  await native.workspaceRegistry();
  assert.equal(requests.length,2,'Workspace must reuse current-page Native snapshots');
  const full=await native.catalog();
  assert.equal(full.all.length,78,'Full catalog must come from OpenCode Native');
  assert.equal(requests.filter(path=>path.endsWith('/provider')).length,1);
  await native.catalog();
  assert.equal(requests.filter(path=>path.endsWith('/provider')).length,1,
    'Dashboard reopening must reuse the current-page Native response');
  native.forget();
  await native.catalog();
  assert.equal(requests.filter(path=>path.endsWith('/provider')).length,2,
    'Explicit invalidation must request the Native catalog, not browser storage');
  assert(!requests.some(path=>path.startsWith('/api/opencode/catalog/')),
    'No legacy Gateway provider catalog requests');
  const connections=await native.route('/api/opencode/connections');
  assert.deepEqual(Array.from(connections,row=>row.provider_id),['deepseek','google']);
  assert(connections.every(row=>row.verified===false&&row.auth_status==='native_reported_unverified'),
    'Native availability must not claim a validated key or owner');
  const removedHints=[];
  const freshClient=createClient({localStorage:{
    getItem(){throw Error('Provider state must not be read from browser storage');},
    setItem(){throw Error('Provider state must not be written to browser storage');},
    removeItem(key){removedHints.push(key);}
  }});
  const freshInventory=await freshClient.configuredProviders();
  assert.deepEqual([...freshInventory.connected],['opencode','deepseek','google']);
  assert.deepEqual(removedHints,['og-native-revoked-provider-ids:test-user'],
    'Remove the obsolete current-account deletion hint without reading it');
  freshClient.forget();
  assert.deepEqual([...(await freshClient.configuredProviders()).connected],[...freshInventory.connected],
    'Refreshing must use Native, not a browser verification ledger');
  let finishOldRead,providerReads=0;
  const racing=createClient({fetch:async(address,options)=>{
    const path=new URL(address,'https://test.opencode-gateway.codes').pathname;
    if(options.method==='DELETE')return {ok:true,status:200,text:async()=> 'true'};
    assert.equal(path,'/native-direct/api/provider');
    providerReads++;
    if(providerReads===1)return new Promise(resolve=>{finishOldRead=()=>resolve({
      ok:true,status:200,text:async()=>JSON.stringify(fullProviderCatalog)
    });});
    return {ok:true,status:200,text:async()=>JSON.stringify({...fullProviderCatalog,connected:[]})};
  }});
  const stale=racing.catalog();
  const staleRejected=assert.rejects(stale,/state changed/);
  await racing.route('/api/opencode/connections/deepseek',{method:'DELETE'});
  finishOldRead();
  await staleRejected;
  assert.deepEqual([...(await racing.configuredProviders()).connected],['opencode'],
    'A delayed pre-deletion response must not resurrect stale Native availability');
  // Isolated contract fixtures, NOT a real Native credential-store test.
  for(const available of [true,false,null]){
    const calls=[];
    const deleting=createClient({fetch:async(address,options)=>{
      const path=new URL(address,'https://test.opencode-gateway.codes').pathname;
      calls.push([options.method,path]);
      if(options.method==='DELETE')return {ok:true,status:200,text:async()=> 'true'};
      assert.equal(path,'/native-direct/api/provider');
      if(available===null)throw Error('TEST follow-up unavailable');
      return {ok:true,status:200,text:async()=>JSON.stringify({...fullProviderCatalog,connected:available?['deepseek']:[]})};
    }});
    const receipt=await deleting.route('/api/opencode/connections/deepseek',{method:'DELETE'});
    assert.equal(receipt.native_acknowledged,true);
    assert.equal(receipt.credential_deletion_verified,false);
    assert.equal(receipt.credential_deleted,undefined,'Do not claim store deletion from HTTP acknowledgement');
    assert.equal(receipt.provider_available_after_delete,available);
    assert.deepEqual(calls,[['DELETE','/native-direct/api/auth/deepseek'],['GET','/native-direct/api/provider']]);
    if(available!==null){
      const inventory=await deleting.configuredProviders();
      assert(inventory.all.some(p=>p.id==='deepseek'),'Deletion must not remove the provider from Native catalog');
      assert.equal(inventory.connected.includes('deepseek'),available,
        'Do not conceal a Native provider that remains available after DELETE');
      const listings=await deleting.route('/api/opencode/connections');
      assert.equal(listings.some(p=>p.provider_id==='deepseek'),available,
        'Account and Workspace must present the same Native observation');
    }
  }
  let followUps=0;
  const rejected=createClient({fetch:async()=>{followUps++;return {ok:true,status:200,text:async()=> 'false'};}});
  await assert.rejects(rejected.route('/api/opencode/connections/deepseek',{method:'DELETE'}),/did not acknowledge/);
  assert.equal(followUps,1,'Rejected deletion must not be reported successful');
  const owner={id:'owner-A'};
  let hints=0;
  const switched=createClient({currentUser:owner,localStorage:{getItem:()=>null,setItem(){hints++;}},fetch:async()=>{
    owner.id='owner-B';return {ok:true,status:200,text:async()=> 'true'};
  }});
  await assert.rejects(switched.route('/api/opencode/connections/deepseek',{method:'DELETE'}),/Account changed/);
  assert.equal(hints,0,'A late delete must not mark another account as disconnected');
  assert(!dashboard.includes('Verified in this browser session'),'Native availability is not a verified key');
  const runtime=fs.readFileSync('runtime-client.js','utf8');
  assert(!runtime.includes('/api/workspaces/'),'No Python runtime/model discovery fallback');
  assert(!runtime.includes('sessionStorage.getItem')&&!runtime.includes('sessionStorage.setItem'),
    'Do not persist a second provider/model inventory');
  const oldKeys=['og-runtime-v2:A:x','og-runtime-v3:A:x','og-runtime-v4:A:x','unrelated'];
  const agentContext={currentUser:{id:'A'},window:{
    workspaceRuntime:{load(){throw Error('Python fallback');},loadAgents(){throw Error('Python fallback');}},
    nativeSession:{ready:async()=>true,discovery(){throw Error('Agents waited for model discovery');}},
    nativeDirectTest:{active:()=>true,testHost:()=>true,agents:async()=>[
      {name:'build',mode:'primary'},{name:'hidden',mode:'primary',hidden:true},{name:'sub',mode:'subagent'}
    ]}
  },sessionStorage:{get length(){return oldKeys.length;},key:i=>oldKeys[i],
    removeItem:key=>oldKeys.splice(oldKeys.indexOf(key),1)}};
  vm.runInNewContext(runtime.slice(runtime.lastIndexOf('(() => {')),agentContext);
  assert.deepEqual(oldKeys,['unrelated'],'Only obsolete runtime snapshots are removed');
  const agentOnly=await agentContext.window.workspaceRuntime.loadAgents('owned-workspace');
  assert.deepEqual(Array.from(agentOnly.agents,a=>a.name),['build']);
  agentContext.window.nativeDirectTest.agents=async()=>{agentContext.currentUser.id='B';return [];};
  await assert.rejects(agentContext.window.workspaceRuntime.loadAgents('owned-workspace'),/session changed/);
  agentContext.window.nativeSession.ready=async()=>false;
  await assert.rejects(agentContext.window.workspaceRuntime.load('owned-workspace'),/Native is not ready/);
  await assert.rejects(agentContext.window.workspaceRuntime.loadAgents('owned-workspace'),/Native is not ready/);
  await assert.rejects(agentContext.window.workspaceRuntime.loadModels('owned-workspace','deepseek'),/Native is not ready/);
  agentContext.window.nativeSession.ready=async()=>true;
  agentContext.window.nativeSession.active=()=>true;
  const nativeInventory={workspace_id:'owned-workspace',providers:[
    {id:'deepseek',connected:true,allowed:false,models:[{id:'native-model'}]}
  ]};
  agentContext.window.nativeSession.discovery=async()=>nativeInventory;
  agentContext.window.nativeSession.peek=()=>nativeInventory;
  const nativeModels=await agentContext.window.workspaceRuntime.loadModels('owned-workspace','deepseek');
  assert.deepEqual(nativeModels.models,[{id:'native-model'}]);
  assert.equal(nativeModels.allowed,false,'Preserve existing platform restrictions');
  assert.equal(agentContext.window.workspaceRuntime.peekModels('owned-workspace','deepseek').models,nativeModels.models);
  agentContext.window.nativeSession.active=()=>false;
  assert.equal(agentContext.window.workspaceRuntime.peek('owned-workspace'),null);

  // Execute the real file adapter; fake only transport, not the path builder.
  const workspace='11111111-1111-4111-8111-111111111111',fileCalls=[];
  const fileContext={URL,URLSearchParams,AbortSignal,AbortController,FormData,Response,
    location:{hostname:'test.opencode-gateway.codes',origin:'https://test.opencode-gateway.codes'},
    currentUser:{id:'A'},authenticationRevision:1,authenticatedRequests:new Set(),
    activeProject:null,activeSession:null,window:{dispatchEvent(){}},CustomEvent:class{},
    invalidateProviderMutation(){},clearAuthenticatedState(){},
    fetch:async(address)=>{
      const u=new URL(address,'https://test.opencode-gateway.codes');fileCalls.push(u);
      if(u.pathname==='/api/workspaces/'+workspace)return Response.json({id:workspace,native_directory:'/owned/project'});
      assert.equal(u.searchParams.get('directory'),'/owned/project');
      assert(!u.searchParams.get('path').startsWith('/'),'Native requires a relative file path');
      if(u.pathname==='/native-direct/api/file/content')return Response.json({content:'test-content'});
      assert.equal(u.pathname,'/native-direct/api/file');return Response.json([{path:'note.txt',type:'file'}]);
    }
  };
  vm.runInNewContext(app.slice(begin,app.indexOf('function toast(text)'))+'\nthis.callFileApi=api;',fileContext);
  await fileContext.callFileApi('/api/workspaces/'+workspace+'/files?path=');
  assert.equal(fileCalls.at(-1).searchParams.get('path'),'');
  const relative='مجلد/a & b.txt';
  await fileContext.callFileApi('/api/workspaces/'+workspace+'/files/content?path='+encodeURIComponent(relative));
  assert.equal(fileCalls.at(-1).searchParams.get('path'),relative);
  for(const bad of ['../outside','/etc/passwd','a\\b']){
    const before=fileCalls.length;
    await assert.rejects(fileContext.callFileApi('/api/workspaces/'+workspace+'/files?path='+encodeURIComponent(bad)),/Invalid project file path/);
    assert.equal(fileCalls.length,before);
  }
  console.log('NATIVE_DIRECT_CATALOG_REGRESSION_PASS');
})().catch(error=>{console.error(error);process.exitCode=1;});
