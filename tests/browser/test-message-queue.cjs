// Actual queue controls/functions with jsdom and controlled API; no live Agent.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom'),{webcrypto}=require('node:crypto');
const source=fs.readFileSync('dashboards.js','utf8');
const block=source.slice(source.indexOf('  // Separate the submitted text'),source.indexOf('  const submissionCurrent='));
function setup(){
 const window=new JSDOM('<form><div id="attachments"></div><textarea id="promptInput"></textarea></form>',{url:'https://test.example'}).window;
 const document=window.document,calls=[],items=[];
 const c={window,document,crypto:webcrypto,TextEncoder,sessionStorage:window.sessionStorage,
  currentUser:{id:'owner'},activeSession:{id:'session',execution_status:'submitted'},
  queueRevision:0,queueCount:0,queueSignature:'',queuing:false,lang:'en',
  attachmentList:document.getElementById('attachments'),submissionStatus:document.createElement('p'),
  tr:(en,ar)=>c.lang==='ar'?ar:en,q:id=>document.getElementById(id),
  textElement:(tag,value='',cls='')=>Object.assign(document.createElement(tag),{textContent:value,className:cls}),
  updateSend(){},sentAttachments(){},refreshSessionStatus:async()=>{},toast:message=>calls.push(['toast',message]),
  api:async(path,options={})=>{calls.push([path,options.method,options.body]);if(options.method==='POST'&&path.endsWith('/queue')){const data=JSON.parse(options.body);if(!items.some(item=>item.request_id===data.request_id))items.push({request_id:data.request_id,text:data.text,state:'queued'});return {status:'queued'};}if(!options.method)return {paused:c.activeSession?.execution_status==='failed',items:[...items]};if(options.method==='DELETE'){items.splice(items.findIndex(item=>path.endsWith(item.request_id)),1);return {};}return {status:'submitted'};}};
 vm.createContext(c);vm.runInContext(block,c);return {c,calls,items,document};
}
const payload=text=>({request_id:webcrypto.randomUUID(),text,provider_id:'opencode',model_id:'model',attachments:[]});
(async()=>{
 const {c,calls,items,document}=setup();const input=document.getElementById('promptInput');input.value='Follow-up';
 await c.queueFollowup(payload(input.value),'owner','session');
 assert.equal(items.length,1);assert.equal(input.value,'');assert.equal(c.queueCount,1);
 assert.equal(document.querySelector('.composer-message-queue').hidden,false);assert.equal(document.querySelector('.composer-message-queue').open,false);
 assert.equal(calls.filter(call=>call[0].endsWith?.('/dispatch')).length,0);
 assert.match(c.submissionStatus.textContent,/Added/);
 c.activeSession.execution_status='waiting_approval';input.value='One more';await c.queueFollowup(payload(input.value),'owner','session');assert.equal(items.length,2);assert.equal(calls.filter(call=>call[0].endsWith?.('/dispatch')).length,0);
 c.activeSession.execution_status='completed';await c.refreshMessageQueue();const automatic=calls.filter(call=>call[0].endsWith?.('/dispatch')).at(-1);assert.deepEqual(JSON.parse(automatic[2]),{resume:false});
 c.activeSession.execution_status='failed';await c.refreshMessageQueue();const resume=[...document.querySelectorAll('button')].find(button=>button.textContent==='Resume queued messages');assert.ok(resume);await resume.onclick();assert.deepEqual(JSON.parse(calls.filter(call=>call[0].endsWith?.('/dispatch')).at(-1)[2]),{resume:true});
 const remove=[...document.querySelectorAll('button')].find(button=>button.textContent==='Remove');const before=calls.length;c.currentUser={id:'other'};await remove.onclick();assert.equal(calls.length,before);
 c.currentUser={id:'owner'};await remove.onclick();assert.equal(items.length,1);
 c.window.resetWorkspaceQueue();assert.equal(document.querySelector('.composer-message-queue').hidden,true);assert.equal(c.queueCount,0);
 // Lost response: identical retry reuses its durable id; local storage has no text.
 const retry=setup();retry.document.getElementById('promptInput').value='Secret customer prompt';let fail=true;const api=retry.c.api;
 retry.c.api=async(path,options={})=>{if(options.method==='POST'&&path.endsWith('/queue')&&fail){await api(path,options);throw new Error('network interrupted');}return api(path,options);};
 await retry.c.queueFollowup(payload('Secret customer prompt'),'owner','session');assert.equal(retry.items.length,1);const saved=retry.c.sessionStorage.getItem('og-queue:owner:session');assert.ok(saved);assert.ok(!saved.includes('Secret customer prompt'));
 fail=false;await retry.c.queueFollowup(payload('Secret customer prompt'),'owner','session');assert.equal(retry.items.length,1);assert.equal(retry.c.sessionStorage.getItem('og-queue:owner:session'),null);
 // The next draft is independent while enqueue waits, including identical text.
 const typing=setup();const queuedInput=typing.document.getElementById('promptInput');queuedInput.value='Queued text';let releaseQueue;const realQueueApi=typing.c.api;
 typing.c.api=async(path,options={})=>{if(options.method==='POST'&&path.endsWith('/queue'))await new Promise(resolve=>releaseQueue=resolve);return realQueueApi(path,options);};
 const queued=typing.c.queueFollowup(payload('Queued text'),'owner','session');assert.equal(queuedInput.value,'');
 while(!releaseQueue)await new Promise(resolve=>setImmediate(resolve));queuedInput.value='Queued text';queuedInput.dispatchEvent(new typing.c.window.Event('input'));releaseQueue();await queued;assert.equal(queuedInput.value,'Queued text');
 const rejected=setup();rejected.document.getElementById('promptInput').value='Keep queue draft';rejected.c.api=async()=>{throw new Error('queue unavailable');};await rejected.c.queueFollowup(payload('Keep queue draft'),'owner','session');assert.equal(rejected.document.getElementById('promptInput').value,'Keep queue draft');
 // Late queue responses may not leak content into another account's composer.
 const stale=setup();let release;stale.c.api=()=>new Promise(resolve=>release=resolve);const task=stale.c.refreshMessageQueue();stale.c.currentUser={id:'other'};release({items:[{request_id:'private',text:'private',state:'queued'}]});await task;assert.ok(!stale.document.body.textContent.includes('private'));
 assert.ok(source.includes('event.preventDefault();if(sending||queuing||pendingSubmission||!activeWorkspace)return;'));
 assert.ok(source.includes("window.workspaceSubmissionBlocked=()=>sending||queuing||Boolean(pendingSubmission)||['submitted','waiting_approval'].includes(activeSession?.execution_status);"));
 const sendLine=source.split('\n').find(line=>line.includes("q('sendMessage').disabled="));assert.ok(!sendLine.includes('||busy||'));assert.ok(source.includes("['submitted','waiting_approval'].includes(activeSession.execution_status)||queueCount"));
 console.log('10 PASSED / 0 FAILED / 0 SKIPPED: busy/approval queueing, collapsed composer queue, completion dispatch, explicit failed-state resume, cancellation/account guards, uncertain idempotent retry without local text, stale response isolation, enabled queue submission');
})().catch(error=>{console.error(error);process.exitCode=1;});
