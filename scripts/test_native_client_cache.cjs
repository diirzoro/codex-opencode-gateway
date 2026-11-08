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
assert(dashboard.includes('window.nativeDirectTest.catalog()'),'Dashboard must call OpenCode Native catalog');
const directList=dashboard.slice(dashboard.indexOf('async function accountCatalogRows()'),dashboard.indexOf('async function lookup(',dashboard.indexOf('async function accountCatalogRows()')));
assert(!directList.includes('configuredProviders()'),'Dashboard must not wait for absent /config/providers');
assert(!directList.includes('visibility()')&&!directList.includes('api('),'Dashboard listing must not wait for Python Gateway');
assert(!app.includes("direct('config/providers')"),'Do not call absent Native /config/providers route');
assert(app.includes("path==='provider'?90000"),'7MB Native provider transfer must not use generic 18s deadline');


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
function createClient(){
  const window={nativeSession:null,workspaceRuntime:{clear(){}},dispatchEvent(){}};
  const context={
    window,currentUser:{id:'test-user'},
    location:{hostname:'test.opencode-gateway.codes',origin:'https://test.opencode-gateway.codes'},
    fetch:fetchMock,
    localStorage:{getItem:()=>null,setItem(){},removeItem(){}},
    sessionStorage:{getItem:()=>null,setItem(){},removeItem(){}},
    api:async path=>{assert.equal(path,'/api/opencode/display-policy');return policy;},
    URL,AbortSignal,AbortController,setTimeout,clearTimeout,
    CustomEvent:class CustomEvent{constructor(name,options){this.type=name;this.detail=options?.detail;}}
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
  console.log('NATIVE_DIRECT_CATALOG_REGRESSION_PASS');
})().catch(error=>{console.error(error);process.exitCode=1;});
