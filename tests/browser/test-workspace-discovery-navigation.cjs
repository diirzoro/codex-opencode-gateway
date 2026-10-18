// Exercise actual mounted-page workspace switch and discovery, without a cold runtime blocking selection.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('dashboards.js','utf8');
function fixture({visible=true,allowed=true}={}){
 const nodes=new Map(),calls=[],pending=[];
 const node=()=>({textContent:'',hidden:false,disabled:false,value:'',classList:{contains:()=>visible},replaceChildren(){}});
 const c={admin:()=>false,sending:false,pendingSubmission:null,activeWorkspace:{id:'old'},activeSession:{id:'old-session'},currentUser:{id:'owner'},
  usableWorkspace:async()=>allowed,tr:en=>en,toast:m=>calls.push(['error',m]),q:id=>{if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);},
  clearAttachments(){},storageChip:node(),storageData:{},detailLoads:new Map(),stopEvents(){},workspaceSelectionRevision:0,window:{},retrySubmission:node(),submissionStatus:node(),capabilityView:node(),capabilityBody:node(),activityStage:node(),activitySummary:node(),
  localStorage:{setItem(){}},discovery:0,modelRequest:0,chosenAgent:'old',chosenProvider:'old',chosenModel:'old',providers:[],runtimeReady:true,agentsReady:true,modelsReady:true,retryModels:node(),events:node(),changesStamp:0,changedFiles:node(),diffView:node(),
  clearPreview(){},previewStatus:node(),previewPath:node(),filesTree:node(),filesStatus:node(),renderWorkspaceEmpty(){},pendingIdea:'',agent:node(),updateSend(){},Option:function(text,value){return {text,value};},
  syncWorkspacePolling(){calls.push(['poll']);},page:async id=>calls.push(['page',id]),performance:{now:()=>0,measure(){}},
  renderAgents:snapshot=>calls.push(['agents',snapshot.workspace_id]),renderProviders:snapshot=>calls.push(['providers',snapshot.workspace_id])};
 c.window.workspaceRuntime={peek:()=>null,peekAgents:()=>null,loadAgents:id=>new Promise((resolve,reject)=>pending.push({kind:'agents',id,resolve,reject})),load:id=>new Promise((resolve,reject)=>pending.push({kind:'providers',id,resolve,reject}))};
 vm.createContext(c);
 vm.runInContext(source.slice(source.indexOf('  refreshChoices=async function('),source.indexOf('  async function models(')),c);
 vm.runInContext(source.slice(source.indexOf('  openWorkspace=async function('),source.indexOf('  async function refreshSessionStatus(')),c);
 return {c,calls,pending,nodes};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{let passed=0;
 {const f=fixture();await f.c.openWorkspace({id:'project'},{id:'two'},{navigate:false});assert.deepEqual(f.pending.map(p=>[p.kind,p.id]),[['agents','two'],['providers','two']]);assert.equal(f.calls.some(c=>c[0]==='page'),false);assert.equal(f.c.activeWorkspace.id,'two');passed++;}
 {const f=fixture();await f.c.openWorkspace({id:'p'},{id:'two'},{navigate:false});f.pending[0].resolve({workspace_id:'two'});await tick();assert.equal(f.calls.some(c=>c[0]==='agents'),true);assert.equal(f.calls.some(c=>c[0]==='providers'),false);passed++;}
 {const f=fixture();await f.c.openWorkspace({id:'p'},{id:'two'},{navigate:false});await f.c.openWorkspace({id:'p3'},{id:'three'},{navigate:false});for(const p of f.pending.slice(0,2))p.resolve({workspace_id:'two',health:{healthy:true},providers:[],errors:{},version:'test',status:'ready'});await tick();assert.equal(f.calls.some(c=>['agents','providers'].includes(c[0])),false);assert.equal(f.c.activeWorkspace.id,'three');passed++;}
 {const f=fixture({visible:false});await f.c.openWorkspace({id:'p'},{id:'two'},{navigate:false});assert.equal(f.pending.length,0);assert.equal(f.calls.some(c=>c[0]==='page'),false);passed++;}
 {const f=fixture();await f.c.openWorkspace({id:'p'},{id:'two'});assert.equal(f.pending.length,0);assert.deepEqual(f.calls,[['page','workspacePage']]);passed++;}
 {const f=fixture({allowed:false});await f.c.openWorkspace({id:'p'},{id:'two'},{navigate:false});assert.equal(f.pending.length,0);assert.equal(f.c.activeWorkspace.id,'old');passed++;}
 {const f=fixture();f.c.pendingSubmission={};await assert.rejects(f.c.openWorkspace({id:'p'},{id:'two'},{navigate:false}),/pending/);assert.equal(f.pending.length,0);passed++;}
 {const f=fixture();await f.c.openWorkspace({id:'p'},{id:'two'},{navigate:false});f.pending[0].reject(Error('Agents unavailable'));f.pending[1].reject(Error('Runtime unavailable'));await tick();assert.equal(f.c.agentsReady,false);assert.equal(f.c.runtimeReady,false);assert.equal(f.nodes.get('runtimeStatus').textContent,'Runtime unavailable');passed++;}
 console.log(`${passed} PASSED: mounted switch discovery, incremental agents, nonblocking selection, stale results, hidden/default navigation, ownership and submission guards, honest failure`);
})().catch(error=>{console.error(error);process.exitCode=1;});
