const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const doc=new JSDOM('<body><section id="connectionsWorkspace"></section><main id="agentFeed"></main><div id="approvalBox"></div></body>').window.document;
const settings=doc.createElement('details');doc.getElementById('connectionsWorkspace').append(settings);const calls=[];
const textElement=(tag,value='',cls='')=>{const e=doc.createElement(tag);e.textContent=value;e.className=cls;return e;};
const c={lang:'en',approvalRenderRevision:0,approvalSignature:'',toolNames:{read:true,edit:true},toolName:t=>t==='edit'?'Edit files':'Read files',document:doc,currentUser:{id:'owner'},activeSession:{id:'session'},approvalBusy:new Set(),inlineApprovals:doc.getElementById('approvalBox'),approvalsList:settings,tr:en=>en,textElement,q:id=>doc.getElementById(id),btn:(id,en,ar,onclick)=>Object.assign(textElement('button',en),{id,onclick}),api:async(path,options={})=>{calls.push([path,options.method]);return path.endsWith('/routine')?{enabled:true}:{count:1};},refreshSessionStatus:async()=>{},refreshMessages:async()=>{},loadApprovals:async()=>{},toast(){}};vm.createContext(c);const src=fs.readFileSync('dashboards.js','utf8');vm.runInContext(src.slice(src.indexOf('  async function renderApprovals('),src.indexOf('  window.renderWorkspaceApprovals=')),c);
(async()=>{
 await c.renderApprovals([],'session');assert.equal(c.inlineApprovals.hidden,true);assert.equal(doc.getElementById('agentFeed').children.length,0);assert.equal(settings.parentNode.id,'connectionsWorkspace');assert.ok(settings.querySelector('.remembered-approvals'));assert.equal(c.inlineApprovals.querySelector('.remembered-approvals'),null);
 await c.renderApprovals([{id:'request',permission:'edit',patterns:['src/app.js'],reviewable:true,rememberable:true}],'session');assert.equal(c.inlineApprovals.hidden,false);assert.equal(c.inlineApprovals.parentNode.id,'agentFeed');assert.equal(c.inlineApprovals.querySelectorAll('[data-reply]').length,3);
 const previousCard=c.inlineApprovals.firstChild;await c.renderApprovals([{id:'request',permission:'edit',patterns:['src/app.js'],reviewable:true,rememberable:true}],'session');assert.equal(c.inlineApprovals.firstChild,previousCard);
 await settings.querySelector('#clearRememberedApprovals').onclick();assert.ok(calls.some(([path,method])=>path==='/api/sessions/session/permissions/remembered'&&method==='DELETE'));
 const before=calls.length;c.currentUser={id:'other'};await settings.querySelector('#clearRememberedApprovals').onclick();assert.equal(calls.length,before);
 c.currentUser={id:'owner'};c.api=async(path,options={})=>{calls.push([path,options.method,options.body]);return path.endsWith('/routine')?{enabled:false}:{count:0};};
 await c.renderApprovals([{id:'routine-request',permission:'edit',patterns:['index.html'],reviewable:true,rememberable:true}],'session');
 const shortcut=c.inlineApprovals.querySelector('.routine-permission-shortcut');assert.ok(shortcut);const beforeEnable=calls.filter(x=>x[1]==='PUT').length;assert.equal(beforeEnable,0);
 await shortcut.onclick();const puts=calls.filter(x=>x[1]==='PUT');assert.equal(puts.length,1);assert.equal(puts[0][0],'/api/sessions/session/permissions/routine');assert.deepEqual(JSON.parse(puts[0][2]),{enabled:true});assert.equal(calls.filter(x=>x[1]==='POST').length,0);
 c.currentUser={id:'other'};await shortcut.onclick();assert.equal(calls.filter(x=>x[1]==='PUT').length,1);
 c.currentUser={id:'owner'};await c.renderApprovals([{id:'command',permission:'bash',patterns:['npm install'],reviewable:true,rememberable:true}],'session');assert.equal(c.inlineApprovals.querySelector('.routine-permission-shortcut'),null);
 // Four distinct files get one consent control, never four copies of it.
 const files=['README.md','nested.html','style.css','app.js'].map((name,index)=>({id:'file-'+index,permission:index?'edit':'read',patterns:[name],reviewable:true,rememberable:true}));
 await c.renderApprovals(files,'session');
 assert.equal(c.inlineApprovals.querySelectorAll('.routine-permission-notice').length,1);
 assert.equal(c.inlineApprovals.querySelectorAll('.routine-permission-shortcut').length,1);
 assert.equal(c.inlineApprovals.querySelectorAll('[data-reply="once"]').length,4);
 assert.match(c.inlineApprovals.querySelector('[data-reply="similar"]').textContent,/exact request/);
 // Repeated runtime IDs are one card. Distinct IDs must still be reviewable,
 // even when their patterns match; never merge or approve them by filename.
 await c.renderApprovals([files[0],files[0],{...files[0],id:'distinct-request'}],'session');
 assert.equal(c.inlineApprovals.querySelectorAll('[data-reply="once"]').length,2);
 // One explicit click, including a double-click while saving, makes one PUT.
 let release;const saved=new Promise(resolve=>release=resolve);let enabled=false;
 c.api=async(path,options={})=>{calls.push([path,options.method,options.body]);if(options.method==='PUT'){await saved;enabled=true;return {enabled:true};}return path.endsWith('/routine')?{enabled}:{count:0};};
 c.loadApprovals=async()=>c.renderApprovals([], 'session');
 const enable=c.inlineApprovals.querySelector('.routine-permission-shortcut');const count=calls.filter(x=>x[1]==='PUT').length;
 const first=enable.onclick();await enable.onclick();assert.equal(calls.filter(x=>x[1]==='PUT').length,count+1);release();await first;
 assert.equal(c.inlineApprovals.hidden,true);assert.equal(settings.querySelector('input').checked,true);
 assert.equal(calls.filter(x=>x[1]==='POST').length,0);
 // Settings remain scoped to the conversation: a new one has its own opt-in.
 c.activeSession={id:'new-session'};enabled=false;await c.renderApprovals(files,'new-session');
 assert.equal(settings.querySelector('input').checked,false);assert.equal(c.inlineApprovals.querySelectorAll('.routine-permission-shortcut').length,1);
 console.log('13 PASSED / 0 FAILED / 0 SKIPPED: original inline/settings controls, stable cards, revocation/owner guards, explicit routine opt-in with no permission POST, no command shortcut (jsdom/controlled API)');
})().catch(e=>{console.error(e);process.exitCode=1;});
