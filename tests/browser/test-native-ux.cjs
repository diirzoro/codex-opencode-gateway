/* Real client/render functions, synthetic Native fixtures. Not TEST acceptance. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const clientSource=fs.readFileSync('native-session-client.js','utf8'),dash=fs.readFileSync('dashboards.js','utf8'),app=fs.readFileSync('app.js','utf8');
let passed=0;
async function test(name,run){await run();passed++;console.log('PASS '+name);}
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function fixture(){
 const dom=new JSDOM('<main id="workspacePage"><div id="agentFeed"></div><div id="runtimeStatus"></div><div id="approvalBox"></div></main>',{url:'https://test.opencode-gateway.codes'}),w=dom.window,d=w.document;
 const id='11111111-1111-4111-8111-111111111111',row={id,workspace_id:'workspace-a',runtime_id:'ses_a',file_base:'file:///owned/a/'};
 const state={calls:[],events:[],files:0,permissions:[],questions:[],history:[{info:{id:'u1',role:'user'},parts:[{type:'text',text:'Synthetic test'}]},{info:{id:'a1',role:'assistant'},parts:[{id:'text1',type:'text',text:''}]}]};
 const textElement=(tag,text='',className='')=>{const n=d.createElement(tag);n.textContent=text;n.className=className;return n;};
 const c={window:w,document:d,currentUser:{id:'owner-a'},activeWorkspace:{id:'workspace-a'},activeSession:{id,execution_status:'submitted'},lang:'en',localStorage:w.localStorage,sessionStorage:w.sessionStorage,crypto:require('node:crypto').webcrypto,URL,Uint8Array,setTimeout,clearTimeout,Date,console,
  $:q=>d.querySelector(q),textElement,tr:(en)=>en,toast:()=>{},refreshPermissions:async()=>{},refreshMessages:async()=>c.window.nativeSession.route('/api/sessions/'+id+'/messages',{}),};
 c.api=async(path,options={})=>{state.calls.push({path,options});
  if(path==='/api/native-test/state')return {enabled:true,version:'1.19.4'};
  if(path==='/api/native-test/sessions/'+id)return row;
  if(path.endsWith('/message'))return structuredClone(state.history);
  if(path.endsWith('/permission'))return structuredClone(state.permissions);
  if(path.endsWith('/question'))return structuredClone(state.questions);
  if(path.endsWith('/session/status'))return {};
  if(/\/permissions\/|\/questions\//.test(path))return state.reply?state.reply():{};
  throw Error('Unexpected fixture API '+path);
 };
 c.EventSource=class {constructor(){state.events.push(this)}close(){this.closed=true}};
 w.refreshNativeFiles=()=>{state.files++};w.renderWorkspaceEventLine=()=>{};
 vm.createContext(c);vm.runInContext(clientSource,c);
 const load=()=>c.window.nativeSession.route('/api/sessions/'+id+'/messages',{});
 return {dom,w,d,c,state,row,id,async ready(){await w.nativeSession.ready();return load();},load,close(){w.nativeSession.stop();dom.window.close();}};
}
function nativePart(tool,input,status='completed',extra={}){return {type:'tool',callID:'call1',id:'part1',tool,state:{status,input,time:{start:1000,end:2500},...extra}};}
async function main(){
 await test('Native file activity uses owned relative paths and discards contents/secrets',async()=>{
  const f=fixture();f.state.history[1].parts.push(nativePart('write',{filePath:'/owned/a/src/main.js'}));
  f.state.history[1].parts[1]=nativePart('write',{filePath:'/owned/a/src/main.js',password:'secret'},'completed',{output:'PRIVATE CONTENT',metadata:{preview:'secret',diff:'PRIVATE DIFF',count:2}});
  const value=await f.ready(),a=value.value[1].activity[0];assert.equal(a.files[0].path,'src/main.js');assert.equal(a.files[0].operation,'changed');assert.equal(a.duration_ms,1500);assert.equal(a.count,2);assert(!/secret|PRIVATE|password|\/owned\//.test(JSON.stringify(a)));f.close();
 });
 await test('Foreign, traversal and protected file paths stay out of cards',async()=>{
  const f=fixture();f.state.history[1].parts.push(...['/owned/b/private.txt','../b/private.txt','/owned/a/.env.local','/owned/a/id.pem','/owned/a/.opencode/tool.ts'].map((filePath,i)=>({...nativePart('read',{filePath}),callID:'c'+i,id:'p'+i})));
  const result=await f.ready();assert(result.value[1].activity.every(a=>!a.files.length));f.close();
 });
 await test('Native tool call IDs deduplicate and error text becomes a finite explanation',async()=>{
  const f=fixture();f.state.history[1].parts.push(nativePart('read',{filePath:'/owned/a/a.txt'},'running'),nativePart('read',{filePath:'/owned/a/a.txt'},'error',{error:'EACCES /private/key sk-never-show',metadata:{output:'secret'}}));
  const value=await f.ready();assert.equal(value.value[1].activity.length,1);assert.equal(value.value[1].activity[0].error_kind,'permission_denied');assert(!JSON.stringify(value.value[1].activity).includes('never-show'));f.close();
 });
 await test('Native patch operations come from structured file metadata',async()=>{
  const f=fixture();f.state.history[1].parts.push(nativePart('apply_patch',{patchText:'not copied'},'completed',{metadata:{files:[{relativePath:'src/a.txt',type:'add'},{filePath:'/owned/a/b.txt',type:'delete'},{relativePath:'../foreign',type:'update'}]}}));
  const value=await f.ready(),files=value.value[1].activity[0].files;assert.equal(files.length,2);assert.equal(files[0].operation,'created');assert.equal(files[1].operation,'deleted');f.close();
 });
 await test('200 native deltas retain one history request and do not refresh files',async()=>{
  const f=fixture();await f.ready();await f.w.nativeSession.start();const source=f.state.events[0];
  for(let i=0;i<200;i++)source.onmessage({data:JSON.stringify({id:'e'+i,type:'message.part.delta',properties:{sessionID:'ses_a',messageID:'a1',partID:'text1',field:'text',delta:'x'}})});
  await sleep(100);assert.equal(f.state.calls.filter(c=>c.path.endsWith('/message')).length,1);assert.equal(f.state.files,0);assert.equal((await f.load()).value[1].text.length,200);f.close();
 });
 await test('Confirmed native changes coalesce explorer refresh without history polling',async()=>{
  const f=fixture();await f.ready();await f.w.nativeSession.start();const source=f.state.events[0];
  for(let i=0;i<4;i++)source.onmessage({data:JSON.stringify({id:'f'+i,type:'file.edited',properties:{file:'/owned/a/new.txt'}})});
  source.onmessage({data:JSON.stringify({type:'file.edited',properties:{file:'/owned/b/foreign.txt'}})});
  await sleep(450);assert.equal(f.state.files,1);assert.equal(f.state.calls.filter(c=>c.path.endsWith('/message')).length,1);f.close();
 });
 await test('Account clearing cancels a pending file refresh and the old stream',async()=>{
  const f=fixture();await f.ready();await f.w.nativeSession.start();const source=f.state.events[0];source.onmessage({data:JSON.stringify({type:'file.edited',properties:{file:'/owned/a/a.txt'}})});
  f.w.nativeSession.clear();f.c.currentUser={id:'owner-b'};await sleep(450);assert.equal(f.state.files,0);assert(source.closed);assert.equal(f.w.nativeSession.peek('workspace-a'),undefined);f.close();
 });
 await test('Permissions deduplicate, group and localize, with no Shell or always approval',async()=>{
  const f=fixture();await f.ready();f.c.lang='ar';const a={id:'per1',permission:'read',patterns:['/owned/a/a.txt']},b={id:'per2',permission:'bash',patterns:['secret command']};
  await f.w.nativeSession.permissions(f.d.getElementById('approvalBox'),[a,a,b]);
  assert.equal(f.d.querySelectorAll('[data-permission-id]').length,2);assert(f.d.getElementById('approvalBox').textContent.includes('السماح مرة واحدة'));assert(!f.d.getElementById('approvalBox').textContent.includes('secret command'));
  assert(f.d.querySelector('[data-permission-id=per2] [data-reply=once]').disabled);assert.equal(f.d.querySelectorAll('[data-reply=always]').length,0);f.close();
 });
 await test('Pending one-time replies cannot be submitted twice',async()=>{
  const f=fixture();await f.ready();let finish;f.state.reply=()=>new Promise(resolve=>finish=resolve);const box=f.d.getElementById('approvalBox'),pending=[{id:'per1',permission:'read',patterns:['/owned/a/a.txt']}];
  await f.w.nativeSession.permissions(box,pending);const button=box.querySelector('[data-reply=once]');const first=button.onclick();await button.onclick();assert.equal(f.state.calls.filter(x=>x.path.includes('/permissions/')).length,1);finish({});await first;f.close();
 });
 await test('Compact styles stay scoped to Native, preserve Todo and avoid external assets',async()=>{
  const f=fixture();await f.ready();const css=f.d.getElementById('nativeConversationStyles').textContent;assert(css.includes('#workspacePage.native-mode'));assert(!/workspaceTodoPanel|https?:/.test(css));assert(f.d.getElementById('workspacePage').classList.contains('native-mode'));f.w.nativeSession.clear();assert(!f.d.getElementById('workspacePage').classList.contains('native-mode'));f.close();
 });
 await test('Markdown tables are accessible text-only and keep code/list formatting',async()=>{
  const f=fixture();f.c.feedAction=()=>f.d.createElement('button');vm.runInContext(app.slice(app.indexOf('function renderAgentText('),app.indexOf('function workspaceMessagePresentation(')),f.c);
  const host=f.d.createElement('div');f.c.renderAgentText(host,'| الملف | الحالة |\n| --- | --- |\n| `src/a.js` | **اكتمل** |\n| <script>secret()</script> | long'+('x'.repeat(150))+' |\n\n- One\n- Two');
  assert.equal(host.querySelectorAll('table tbody tr').length,2);assert.equal(host.querySelector('[role=region]').tabIndex,0);assert.equal(host.querySelectorAll('script').length,0);assert.equal(host.querySelectorAll('li').length,2);assert(host.textContent.includes('<script>'));f.close();
 });
 await test('Native activity shows live paths and navigates via the owned file handler only',async()=>{
  const f=fixture();f.c.keepChatActivity=()=>{};f.c.activity=f.d.createElement('section');f.c.activityStage=f.d.createElement('p');f.c.activitySummary=f.d.createElement('div');vm.runInContext(dash.slice(dash.indexOf('  const stages='),dash.indexOf("  const agent=q('agentSelect')")),f.c);
  const opened=[];f.w.openWorkspaceFile=(...args)=>opened.push(args);const host=f.d.createElement('article');f.w.renderMessageActivity(host,[{native:true,workspace_id:'workspace-a',id:'call',tool:'read',status:'running',files:[{path:'src/a.js',operation:'inspected'}]}]);
  assert(host.querySelector('.native-activity').open);assert(host.querySelector('.tool-execution>summary').textContent.includes('src/a.js'));host.querySelector('.native-file-link').click();assert.equal(opened.length,1);f.c.currentUser={id:'owner-b'};host.querySelector('.native-file-link').click();assert.equal(opened.length,1);f.close();
 });

 await test('File explorer coalesces loads and the viewer treats file contents as inert text',async()=>{
  const f=fixture();await f.ready();f.c.q=id=>f.d.getElementById(id);f.c.filesTree=f.d.createElement('div');f.c.filesStatus=f.d.createElement('p');f.d.getElementById('workspacePage').append(f.c.filesTree,f.c.filesStatus);
  f.w.HTMLDialogElement.prototype.showModal=function(){this.open=true};f.w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new f.w.Event('close'))};
  const original=f.c.api;let requests=0;
  f.c.api=async(path,options)=>{if(path.endsWith('/files')){requests++;return [{name:'a.txt',path:'a.txt',type:'file'}]};if(path.includes('/files/content'))return {path:'a.txt',content:'<script>synthetic()</script>'};return original(path,options)};
  vm.runInContext(dash.slice(dash.indexOf('  const FILE_ICONS='),dash.indexOf("  const modes=textElement('nav'"))+';globalThis.loadFileFixture=loadFiles;',f.c);
  await Promise.all([f.c.loadFileFixture(),f.c.loadFileFixture()]);assert.equal(requests,1);
  await f.w.openWorkspaceFile('a.txt',{owner:'owner-a',workspaceId:'workspace-a'});assert.equal(f.d.querySelector('dialog pre').textContent,'<script>synthetic()</script>');assert.equal(f.d.querySelectorAll('dialog script').length,0);
  const count=f.state.calls.length;await f.w.openWorkspaceFile('../foreign',{owner:'owner-a',workspaceId:'workspace-a'});assert.equal(f.state.calls.length,count);f.close();
 });
 await test('A late file-view response is discarded after account switching',async()=>{
  const f=fixture();await f.ready();f.c.q=id=>f.d.getElementById(id);f.c.filesTree=f.d.createElement('div');f.c.filesStatus=f.d.createElement('p');
  const original=f.c.api;let finish;f.c.api=async(path,options)=>path.includes('/files/content')?new Promise(resolve=>finish=resolve):original(path,options);
  vm.runInContext(dash.slice(dash.indexOf('  const FILE_ICONS='),dash.indexOf("  const modes=textElement('nav'")),f.c);
  const job=f.w.openWorkspaceFile('a.txt',{owner:'owner-a',workspaceId:'workspace-a'});f.c.currentUser={id:'owner-b'};finish({content:'synthetic owner-a content'});await job;
  assert.equal(f.d.querySelector('dialog'),null);assert(!f.d.body.textContent.includes('owner-a content'));f.close();
 });
 await test('Native multi-question choices and custom drafts survive another pending request',async()=>{
  const f=fixture();await f.ready();f.c.q=id=>f.d.getElementById(id);f.c.MutationObserver=f.w.MutationObserver;
  const question={question:'Choose a colour',header:'Colour',options:[{label:'Blue',description:'Cool',recommended:true},{label:'Green'}],custom:true};
  const original=f.c.api;let pending=[{id:'que1',questions:[question,{...question,multiple:true}]}],answers;
  f.c.refreshSessionStatus=async()=>{};f.c.api=async(path,options)=>{if(path.endsWith('/questions'))return {requests:pending};if(path.includes('/questions/')){answers=JSON.parse(options.body);pending=[];return {}};return original(path,options)};
  vm.runInContext(dash.slice(dash.indexOf("  const questionView=textElement('section'"),dash.indexOf('  const approvalBusy=')),f.c);
  await f.w.refreshWorkspaceQuestions();const first=f.d.querySelector('[data-request-id=que1]');first.querySelector('input[type=radio]').checked=true;first.querySelector('input[type=checkbox]').checked=true;first.querySelectorAll('input[type=text]')[1].value='Custom synthetic colour';
  pending=[...pending,{id:'que2',questions:[question]}];await f.w.refreshWorkspaceQuestions();assert.equal(f.d.querySelector('[data-request-id=que1]'),first);assert.equal(first.querySelectorAll('input[type=text]')[1].value,'Custom synthetic colour');
  first.onsubmit({preventDefault(){}});await sleep(10);assert.deepEqual(answers.answers,[['Blue'],['Blue','Custom synthetic colour']]);assert.equal(answers.reject,false);f.close();
 });


 await test('Native attachment expansion is hidden by synthetic flag, preserving the exact user prompt and file chip',async()=>{
  const f=fixture(),text='هل تستطيع القراءة؟ Called the Read tool with the following input: example';
  f.state.history[0].parts=[{type:'text',text},{type:'text',synthetic:true,text:'Called the Read tool with the following input: /private/absolute/path'},{type:'text',synthetic:true,text:'<path>/private/path</path> SYNTHETIC_SECRET'},{type:'file',filename:'/owned/a/config.txt',mime:'text/plain'}];
  const result=await f.ready();assert.equal(result.value[0].text,text);assert.equal(result.value[0].attachments[0].name,'config.txt');assert(!JSON.stringify(result.value).includes('SYNTHETIC_SECRET'));
  assert(f.state.history[0].parts[2].text.includes('SYNTHETIC_SECRET')); // UI projection never rewrites Native storage/input
  await f.w.nativeSession.start();f.state.events[0].onmessage({data:JSON.stringify({type:'message.part.updated',properties:{part:{id:'synthetic-late',messageID:'u1',sessionID:'ses_a',type:'text',synthetic:true,text:'LATE_SYNTHETIC_SECRET'}}})});
  await sleep(80);assert.equal((await f.load()).value[0].text,text);f.close();
 });
 await test('Remembered file decision uses Native session policy management then once, never upstream always',async()=>{
  const f=fixture();await f.ready();const original=f.c.api;f.c.api=async(path,options={})=>{if(path.endsWith('/remember')){f.state.calls.push({path,options});return {remembered:true}}return original(path,options)};
  const box=f.d.getElementById('approvalBox');await f.w.nativeSession.permissions(box,[{id:'per1',permission:'edit',patterns:['/owned/a/a.txt']}]);
  await box.querySelector('[data-reply=remember]').onclick();const calls=f.state.calls.filter(c=>c.path.includes('/permissions/'));assert.equal(calls.length,2);assert(calls[0].path.endsWith('/remember'));assert.equal(JSON.parse(calls[1].options.body).reply,'once');f.close();
 });
 await test('Denied remember cannot approve the pending file operation',async()=>{
  const f=fixture();await f.ready();const original=f.c.api;f.c.api=async(path,options)=>{if(path.endsWith('/remember'))throw Error('Protected file');return original(path,options)};
  const box=f.d.getElementById('approvalBox');await f.w.nativeSession.permissions(box,[{id:'per1',permission:'edit',patterns:['/owned/a/a.txt']}]);await box.querySelector('[data-reply=remember]').onclick();assert.equal(f.state.calls.filter(c=>c.path.includes('/permissions/')).length,0);assert(!box.querySelector('[data-reply=remember]').disabled);f.close();
 });
 await test('Native question cards have bounded height, compact rows and accessible overflow without changing Todo',async()=>{
  const f=fixture();await f.ready();const css=f.d.getElementById('nativeConversationStyles').textContent;assert(css.includes('max-height:min(360px,46dvh)'));assert(css.includes('overflow:auto;overscroll-behavior:contain'));assert(css.includes('min-height:32px'));assert(!css.includes('workspaceTodoPanel'));f.close();
 });

 await test('One-click group approval covers only displayed requests and uses once for each owned request',async()=>{
  const f=fixture();await f.ready();const box=f.d.getElementById('approvalBox');
  const pending=[{id:'per1',permission:'read',patterns:['/owned/a/a.txt']},{id:'per2',permission:'read',patterns:['/owned/a/b.txt']}];
  await f.w.nativeSession.permissions(box,pending);const batch=box.querySelector('[data-reply=batch-once]');f.state.permissions.push({id:'new-not-displayed',permission:'read',patterns:['/owned/a/c.txt']});
  await batch.onclick();const calls=f.state.calls.filter(c=>c.path.includes('/permissions/'));assert.equal(calls.length,2);assert(calls.every(c=>JSON.parse(c.options.body).reply==='once'));assert(calls.every(c=>!c.path.includes('new-not-displayed')));f.close();
 });
 console.log(passed+' Native UX cases passed; controlled fixtures, not TEST account acceptance');
}
main().catch(error=>{console.error(error);process.exitCode=1});
