#!/usr/bin/env node
'use strict';
// Regression guard for OpenCode Native provider discovery. No test credentials,
// Gateway model registry or additional AI service. Runs with Node built-ins.
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const app=fs.readFileSync('app.js','utf8');
const workspaceUI=fs.readFileSync('dashboards.js','utf8');
const pageHTML=fs.readFileSync('index.html','utf8');
const iconStart=workspaceUI.indexOf('const composerIcons=');
const iconEnd=workspaceUI.indexOf(';\n  for(const [id,markup]',iconStart);
assert(iconStart>=0&&iconEnd>iconStart,'Workspace composer icons missing');
const iconNames=[...workspaceUI.slice(iconStart,iconEnd).matchAll(/"([a-zA-Z][a-zA-Z0-9_-]+)":/g)].map(row=>row[1]);
assert(!iconNames.includes('composerNewTask'),'Removed New Task icon must not be restored');
for(const id of iconNames){
  const inHTML=pageHTML.includes('id="'+id+'"')||pageHTML.includes("id='"+id+"'");
  const inJS=workspaceUI.includes(".id='"+id+"'")||workspaceUI.includes('.id="'+id+'"')||
    workspaceUI.includes("btn('"+id+"'")||workspaceUI.includes('btn("'+id+'"');
  assert(inHTML||inJS,'Workspace icon points to missing control: '+id);
}

const begin=app.indexOf('window.nativeDirectTest=(()=>{');
const end=app.indexOf('\n})();',begin);
assert(begin>=0&&end>begin,'Native browser adapter not found');
const adapter=app.slice(begin,end+5);

const storage=()=>{
  const entries=new Map();
  return {
    getItem:key=>entries.get(key)??null,
    setItem:(key,value)=>entries.set(key,String(value)),
    removeItem:key=>entries.delete(key),
    key:index=>[...entries.keys()][index]??null,
    get length(){return entries.size;}
  };
};
const sessionStorage=storage(),localStorage=storage(),requests=[];
const metadata={
  providers:[
    {id:'opencode',name:'OpenCode',models:{'free-test':{name:'Free test',cost:{input:0,output:0}}}},
    {id:'deepseek',name:'DeepSeek',models:{chat:{name:'DeepSeek Chat'}}},
    {id:'google',name:'Google',models:{gemini:{name:'Gemini'}}}
  ],
  default:{opencode:'free-test'}
};
const agentMetadata=[{name:'build',mode:'primary',prompt:'DO_NOT_CACHE_THIS'}];
async function fetchMock(address){
  const pathname=new URL(address,'https://test.opencode-gateway.codes').pathname;
  requests.push(pathname);
  const payload=pathname.endsWith('/config/providers')?metadata:
    pathname.endsWith('/agent')?agentMetadata:null;
  assert(payload!==null,'Unexpected Native route '+pathname);
  return {ok:true,status:200,text:async()=>JSON.stringify(payload)};
}
const platformPolicy={allowed_providers:[],hidden_providers:[],allowed_models:[],hidden_models:{},updated_at:'test'};
function createClient(){
  const window={nativeSession:null,workspaceRuntime:{clear(){}}};
  const context={
    window,currentUser:{id:'test-user'},
    location:{hostname:'test.opencode-gateway.codes',origin:'https://test.opencode-gateway.codes'},
    localStorage,sessionStorage,fetch:fetchMock,
    api:async path=>{
      assert.equal(path,'/api/opencode/display-policy');
      return platformPolicy;
    },
    URL,AbortSignal,AbortController,setTimeout,clearTimeout
  };
  vm.runInNewContext(adapter,context,{timeout:3000});
  return window.nativeDirectTest;
}
(async()=>{
  const first=createClient();
  const initial=await first.workspaceRegistry();
  assert.deepEqual([...initial.data.connected],['opencode'],
    'Only built-in OpenCode may be available without a client-verified key');
  assert(initial.data.all.some(p=>p.id==='deepseek'),'DeepSeek remains searchable');
  assert(initial.data.all.some(p=>p.id==='google'),'Google remains searchable');
  assert.equal(requests.length,2,'First load must use only lightweight Native provider and agent endpoints');
  assert(requests.every(path=>!path.endsWith('/provider')),'Full provider catalog loaded during workspace first paint');
  await first.workspaceRegistry();
  assert.equal(requests.length,2,'Project navigation must reuse browser memory');
  const reopened=createClient();
  const saved=await reopened.workspaceRegistry();
  assert.deepEqual([...saved.data.connected],['opencode'],
    'A browser refresh must not make unknown providers appear connected');
  assert.equal(requests.length,2,'Tab metadata cache must avoid extra Native fetches');
  const cached=sessionStorage.getItem('og-native-model-metadata-v1:test-user');
  assert(cached&&cached.includes('free-test'),'Native metadata must be cached');
  assert(!cached.includes('DO_NOT_CACHE_THIS'),'Agent prompts must not be cached');
  reopened.forget({fresh:true});
  await reopened.workspaceRegistry();
  assert.equal(requests.length,4,'Explicit refresh must bypass both Native metadata caches');
  console.log('NATIVE_BROWSER_CATALOG_CACHE_REGRESSION_PASS');
})().catch(error=>{console.error(error);process.exitCode=1;});
