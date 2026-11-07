// Verify that Dashboard and Workspace reuse one OpenCode Native inventory.
// No Python AI route, external provider, server or database required.
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../../app.js'),'utf8');
const managementSource=fs.readFileSync(path.join(__dirname,'../../management.js'),'utf8');
assert(!source.includes('يوجد مفتاح لهذا المزود في مخزن OpenCode المشترك. لن يتم استبداله'),
  'Native connected metadata must never be mistaken for saved API key proof');
assert(source.includes('value.replace_existing!==true'),
  'Shared Native PUT must require explicit user confirmation');
assert(managementSource.includes('replace_existing:Boolean(window.nativeDirectTest?.active())'),
  'Native key dialog must send the explicit confirmation marker');
assert(managementSource.includes('p.public_free'),
  'Free OpenCode models must not display credential deletion actions');
const nativeSessionSource=fs.readFileSync(path.join(__dirname,'../../native-session-client.js'),'utf8');
assert(nativeSessionSource.includes('const directSessionTransport=()=>false'),
  'Workspace Native session transport must use authenticated Gateway ownership routing');
assert(!nativeSessionSource.includes('window.nativeDirectTest?.active()'),
  'Workspace must not call the Basic-auth-protected Native direct session endpoint');
assert(nativeSessionSource.includes("'/native-session/'+encodeURIComponent(workspace)+'/'+path"),
  'Workspace messages and SSE must retain the existing X-Accel Native route');
const nativeGatewaySource=fs.readFileSync(path.join(__dirname,'../../backend/app/routes/native_sessions.py'),'utf8');
assert(!nativeGatewaySource.includes("TEST Native discovery is direct-only; Gateway discovery is disabled"),
  'Workspace model discovery must not return 410 to the authorized Native transport');
assert(nativeGatewaySource.includes("response=await run_in_threadpool(authorize_native"),
  'Native session transport must authorize owner before X-Accel forwarding');
const gatewaySource=fs.readFileSync(path.join(__dirname,'../../backend/app/main.py'),'utf8');
// TEST must not import/mount the Python AI queue/agent execution module.
assert(!gatewaySource.includes('from .routes import workspaces, agent,'),
  'Legacy Python agent must not be eagerly imported in TEST');
assert(!gatewaySource.includes('from .routes import agent')
  && !gatewaySource.includes('app.include_router(agent.router)'),
  'Python AI router must be entirely removed');
for(const retired of ['backend/app/routes/agent.py','backend/app/services/message_queue.py',
  'backend/app/services/opencode.py','backend/app/services/opencode_catalog.py',
  'backend/app/services/account_provider_runtime.py','backend/app/services/session_recovery.py']){
  assert(!fs.existsSync(path.join(__dirname,'../../',retired)),
    'Legacy Python AI module still present: '+retired);
}
assert(!gatewaySource.includes('native_catalog_maintenance.sweep'),
  'Gateway must not schedule Native catalog refresh in Python');
assert(!gatewaySource.includes('native_sessions.sweep_expired_native_history'),
  'Gateway must not schedule native-history deletion in Python');

const start=source.indexOf('window.nativeDirectTest=(()=>{');
const end=source.indexOf('\n\nconst api=async(',start);
assert(start>=0&&end>start,'Native adapter boundaries changed');
const adapterSource=source.slice(start,end);
const calls={configured:0,full:0,agents:0,policy:0,authDelete:0};
const response=data=>({ok:true,status:200,text:async()=>JSON.stringify(data)});
const win={nativeSession:{invalidate(){}},workspaceRuntime:{clear(){}},dispatchEvent(){}};
const provider={id:'demo',name:'Demo',models:{one:{name:'One'}}};
const external={id:'outside',name:'Other Native auth',models:{own:{name:'Native Model'}}};
const free={id:'opencode',name:'OpenCode',source:'custom',
  models:{free:{name:'Native Free Model',cost:{input:0,output:0}}}};
const sandbox={
 window:win,location:{hostname:'test.opencode-gateway.codes',origin:'https://test.opencode-gateway.codes'},
 URL,AbortSignal,console,CustomEvent:class CustomEvent{constructor(type,options){this.type=type;this.detail=options?.detail;}},
 policyRead:()=>{calls.policy++;return {allowed_providers:[],hidden_providers:[],allowed_models:[],hidden_models:{},updated_at:'test'};},
 fetch:async (url,options={})=>{
   const p=new URL(url,'https://test.opencode-gateway.codes').pathname;
   if(p.endsWith('/config/providers')){calls.configured++;return response({providers:[provider,free],default:{demo:'one',opencode:'free'}});}
   if(p.endsWith('/provider')){
     calls.full++;
     // Simulates OpenCode's stale /provider.connected after DELETE /auth.
     return response({all:[provider,free,external],connected:['demo','outside'],default:{demo:'one',opencode:'free'}});
   }
   if(p.endsWith('/auth/demo')&&options.method==='DELETE'){
     calls.authDelete++;
     return response(true);
   }
   if(p.endsWith('/agent')){calls.agents++;return response([{name:'build',mode:'primary',hidden:false}]);}
   throw Error('Unexpected Native route '+p);
 }
};
const setup="const currentUser={id:'00000000-0000-0000-0000-000000000001'};const api=async path=>{if(path!=='/api/opencode/display-policy')throw Error('Unexpected Gateway AI route: '+path);return policyRead();};const invalidateProviderMutation=()=>{};\n";
vm.runInNewContext(setup+adapterSource,sandbox);
(async()=>{
 const adapter=win.nativeDirectTest;
 const initial=await adapter.workspaceRegistry();
 assert.equal(initial.data.connected.join(','),'opencode',
   '/config/providers does not prove the demo provider has a key');
 const dashboard=await adapter.route('/api/opencode/catalog/providers/page?limit=50&offset=0');
 assert.equal(dashboard.connected_items.length,1);
 assert.equal(dashboard.connected_items[0].public_free,true);
 assert.equal(calls.configured,1,'Dashboard and Workspace should share Native configured inventory');
 assert.equal(calls.full,0,'Initial view must not download the full provider catalog');
 assert.equal(calls.agents,1);
 assert.equal(calls.policy,1);
 await adapter.catalog();
 const afterDiscoveryPage=await adapter.route('/api/opencode/catalog/providers/page?limit=50&offset=0');
 assert.equal(afterDiscoveryPage.connected_items.some(p=>p.id==='outside'),true,
   'Dashboard can manage Native auth not present in /config/providers');
 const discovered=await adapter.workspaceRegistry();
 assert.equal(discovered.data.connected.includes('outside'),false,
   'A global Native auth entry must not auto-join every Workspace');
 assert.equal(discovered.data.connected.includes('demo'),true,
   'Only Native /provider.connected can establish candidate connection');
 const removed=await adapter.route('/api/opencode/connections/demo',{method:'DELETE'});
 assert.equal(removed.native_acknowledged,true,'DELETE must trust Native acknowledgement, not cached provider list');
 assert.equal(calls.authDelete,1);
 await adapter.catalog();
 const after=await adapter.workspaceRegistry();
 assert.equal(after.data.connected.includes('demo'),false,
   'Stale OpenCode connected cache must not turn a deleted key into a phantom connection');
 assert.equal(after.data.connected.includes('opencode'),true,'Native free models remain available');
 console.log('NATIVE_PROVIDER_INVENTORY_CACHE_TEST_PASSED');
})().catch(e=>{console.error(e);process.exitCode=1;});
