// Actual composer submission/retry functions in jsdom; controlled HTTP, no live Agent.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom'),{webcrypto}=require('node:crypto');
const source=fs.readFileSync('dashboards.js','utf8');
const draftBlock=source.slice(source.indexOf('  // Separate the submitted text'),source.indexOf('  const queueView='));
const sendBlock=source.slice(source.indexOf('  async function submitPending(){'),source.indexOf("  q('stopAgent').onclick=async()=>{"));
function setup(){
 const window=new JSDOM('<form id="promptForm"><textarea id="promptInput"></textarea><select id="providerSelect"><option selected>provider</option></select><select id="modelSelect"><option selected>model</option></select></form>',{url:'https://test.example'}).window;
 const document=window.document,calls=[];
 const c={window,document,lang:'en',crypto:webcrypto,sessionStorage:window.sessionStorage,
  currentUser:{id:'owner'},activeWorkspace:{id:'workspace'},activeSession:{id:'session',execution_status:'completed'},
  pendingSubmission:null,sending:false,queuing:false,cancelRequested:false,queueCount:0,
  attachments:[],runtimeReady:true,modelsReady:true,workAccess:true,agent:{value:'build'},sendingPreview:null,
  retrySubmission:{hidden:true},submissionStatus:{textContent:''},q:id=>document.getElementById(id),tr:en=>en,
  attachmentSupport:()=>({blocked:false}),updateSend(){},showSendingPreview(){},clearSendingPreview(){},sentAttachments(){},toast(){},
  refreshEntitlement:async()=>{},createSession:async()=>{},refreshSessionStatus:async()=>{},refreshMessages:async()=>{},
  submissionCurrent:p=>c.currentUser?.id===p.owner&&c.activeWorkspace?.id===p.workspaceId&&c.activeSession?.id===p.sessionId,
  queueFollowup:async payload=>calls.push(['queue',payload]),
  api:async(path,options={})=>{calls.push([path,options]);return {status:'submitted'};}};
 vm.createContext(c);vm.runInContext(draftBlock+sendBlock,c);
 const input=document.getElementById('promptInput'),submit=()=>document.getElementById('promptForm').onsubmit({preventDefault(){}});
 const type=value=>{input.value=value;input.dispatchEvent(new window.Event('input'));};
 return {c,calls,input,submit,type};
}
function defer(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 let n=0;
 {const t=setup(),d=defer();t.input.value='  Sent text  ';t.c.api=()=>d.promise;const p=t.submit();assert.equal(t.input.value,'');await tick();d.resolve({status:'submitted'});await p;assert.equal(t.input.value,'');n++;}
 {const t=setup(),d=defer();t.input.value='Sent';t.c.api=()=>d.promise;const p=t.submit();await tick();t.type('new draft');d.resolve({status:'submitted'});await p;assert.equal(t.input.value,'new draft');n++;}
 {const t=setup(),d=defer();t.input.value='Same';t.c.api=()=>d.promise;const p=t.submit();await tick();t.type('Same');d.resolve({status:'submitted'});await p;assert.equal(t.input.value,'Same');n++;}
 {const t=setup();t.input.value='  Keep formatting\n ';t.c.refreshEntitlement=async()=>{t.c.workAccess=false;};await t.submit();assert.equal(t.input.value,'  Keep formatting\n ');assert.equal(t.calls.length,0);n++;}
 {const t=setup(),d=defer();t.input.value='Rejected';t.c.api=()=>d.promise;const p=t.submit();await tick();d.reject(Object.assign(new Error('Invalid'),{status:422}));await p;assert.equal(t.input.value,'Rejected');assert.equal(t.c.pendingSubmission,null);n++;}
 {const t=setup(),d=defer();t.input.value='Rejected';t.c.api=()=>d.promise;const p=t.submit();await tick();t.type('next');d.reject(Object.assign(new Error('Invalid'),{status:422}));await p;assert.equal(t.input.value,'next');n++;}
 {const t=setup();t.input.value='Uncertain';t.c.api=async()=>{throw new Error('Lost response');};await t.submit();assert.equal(t.input.value,'Uncertain');const id=t.c.pendingSubmission.request_id;t.c.api=async path=>{assert.ok(path.endsWith('/submissions/'+id));return {status:'submitted'};};await t.c.submitPending();assert.equal(t.input.value,'');assert.equal(t.c.pendingSubmission,null);n++;}
 {const t=setup();t.input.value='Uncertain';t.c.api=async()=>{throw new Error('Lost response');};await t.submit();t.type('Uncertain');t.c.api=async()=>({status:'submitted'});await t.c.submitPending();assert.equal(t.input.value,'Uncertain');n++;}
 {const t=setup(),d=defer();t.input.value='Sent';t.c.api=()=>d.promise;const p=t.submit();await tick();t.type('temporary');t.type('');d.reject(new Error('Lost response'));await p;assert.equal(t.input.value,'');n++;}
 {const t=setup(),d=defer();t.input.value='Private';t.c.api=()=>d.promise;const p=t.submit();await tick();t.c.currentUser={id:'other'};d.reject(new Error('Lost response'));await p;assert.equal(t.input.value,'');n++;}
 {const t=setup();t.c.activeSession.execution_status='waiting_approval';t.input.value='Follow up';await t.submit();assert.equal(t.calls[0][0],'queue');assert.equal(t.calls[0][1].text,'Follow up');n++;}
 // First message clears before creating a conversation, not after the POST.
 {const t=setup(),d=defer();t.c.activeSession=null;t.input.value='First message';t.c.createSession=async()=>{await d.promise;t.c.activeSession={id:'created',execution_status:'created'};};const p=t.submit();assert.equal(t.input.value,'');await tick();assert.equal(t.calls.length,0);t.type('Second draft');d.resolve();await p;assert.equal(t.input.value,'Second draft');assert.ok(t.calls[0][0].includes('/created/messages'));assert.equal(JSON.parse(t.calls[0][1].body).text,'First message');n++;}
 {const t=setup(),d=defer();t.input.value='One submission';t.c.api=async(path,options)=>{t.calls.push([path,options]);return d.promise;};const p=t.submit();await tick();t.type('Next');await t.submit();assert.equal(t.calls.length,1);d.resolve({status:'submitted'});await p;assert.equal(t.input.value,'Next');n++;}
 // Keyboard delegates to the same guarded form, including busy -> queue.
 {const t=setup(),line=fs.readFileSync('app.js','utf8').split('\n').find(row=>row.startsWith("const promptInput=$('#promptInput');"));t.c.$=selector=>t.c.document.querySelector(selector);vm.runInContext(line,t.c);let submits=0;t.c.document.getElementById('promptForm').requestSubmit=()=>submits++;t.c.activeSession.execution_status='waiting_approval';assert.equal(t.c.window.workspaceSubmissionBlocked(),true);
  const press=opts=>t.input.dispatchEvent(new t.c.window.KeyboardEvent('keydown',{key:'Enter',cancelable:true,...opts}));press({});assert.equal(submits,1);press({repeat:true});press({shiftKey:true});press({isComposing:true});assert.equal(submits,1);n++;}
 console.log(`${n} PASSED / 0 FAILED / 0 SKIPPED: draft lifecycle, normal/rejected/uncertain submission, receipt retry, new/identical/deleted drafts, account guard and Enter queueing (jsdom, not TEST browser acceptance)`);
})().catch(error=>{console.error(error);process.exitCode=1;});
