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
assert(gatewaySource.includes("if settings.public_base_url.rstrip('/') != 'https://test.opencode-gateway.codes':\\n    from .routes import agent".replace('\\n','\\n')),
  'Legacy Python AI router must be imported only for non-TEST deployments');
assert(!gatewaySource.includes('native_catalog_maintenance.sweep'),
  'Gateway must not schedule Native catalog refresh in Python');
assert(!gatewaySource.includes('native_sessions.sweep_expired_native_history'),
  'Gateway must not schedule native-history deletion in Python');

const start=source.indexOf('window.nativeDirectTest=(()=>{');
const end=source.indexOf('\n\nconst api=async(',start);
assert(start>=0&&end>start,'Native adapter boundaries changed');
const adapterSource=source.slice(start,end);
const calls={configured:0,full:0,agents:0,policy:0};
const response=data=>({ok:true,status:200,text:async()=>JSON.stringify(data)});
const win={nativeSession:{invalidate(){}},workspaceRuntime:{clear(){}},dispatchEvent(){}};
const sandbox={
 window:win,location:{hostname:'test.opencode-gateway.codes',origin:'https://test.opencode-gateway.codes'},
 URL,AbortSignal,console,
 policyRead:()=>{calls.policy++;return {allowed_providers:[],hidden_providers:[],allowed_models:[],hidden_models:{},updated_at:'test'};},
 fetch:async url=>{
   const p=new URL(url,'https://test.opencode-gateway.codes').pathname;
   if(p.endsWith('/config/providers')){calls.configured++;return response({providers:[{id:'demo',name:'Demo',models:{one:{name:'One'}}}],default:{demo:'one'}});}
   if(p.endsWith('/provider')){calls.full++;return response({all:[],connected:[],default:{}});}
   if(p.endsWith('/agent')){calls.agents++;return response([{name:'build',mode:'primary',hidden:false}]);}
   throw Error('Unexpected Native route '+p);
 }
};
const setup="const currentUser={id:'00000000-0000-0000-0000-000000000001'};const api=async path=>{if(path!=='/api/opencode/display-policy')throw Error('Unexpected Gateway AI route: '+path);return policyRead();};\n";
vm.runInNewContext(setup+adapterSource,sandbox);
(async()=>{
 const adapter=win.nativeDirectTest;
 const first=await adapter.workspaceRegistry();
 assert.equal(first.data.connected[0],'demo');
 const dashboard=await adapter.route('/api/opencode/catalog/providers/page?limit=50&offset=0');
 assert.equal(dashboard.connected_items.length,1);
 await adapter.workspaceRegistry();
 assert.equal(calls.configured,1,'Configured inventory should be fetched once');
 assert.equal(calls.full,0,'Workspace and first Dashboard paint must not download full catalog');
 assert.equal(calls.agents,1);
 assert.equal(calls.policy,1);
 await adapter.route('/api/opencode/catalog/providers/page?query=other');
 assert.equal(calls.full,1,'Search can fetch Native discovery once');
 adapter.forget();
 await adapter.workspaceRegistry();
 assert.equal(calls.configured,2,'Native inventory invalidated after provider mutation');
 console.log('NATIVE_PROVIDER_INVENTORY_CACHE_TEST_PASSED');
})().catch(e=>{console.error(e);process.exitCode=1;});
