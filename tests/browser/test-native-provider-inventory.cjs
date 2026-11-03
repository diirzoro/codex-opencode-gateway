// Verify that Dashboard and Workspace reuse one OpenCode Native inventory.
// No Python AI route, external provider, server or database required.
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../../app.js'),'utf8');
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
     return response({all:[provider,free],connected:['demo'],default:{demo:'one',opencode:'free'}});
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
 const discovered=await adapter.workspaceRegistry();
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
