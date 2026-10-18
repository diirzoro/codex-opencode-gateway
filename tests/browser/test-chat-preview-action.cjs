// Actual chat card callbacks in jsdom; no automatic start or popup.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const source=fs.readFileSync('dashboards.js','utf8');
function fixture(){
 const {window}=new JSDOM('<main><article></article><section id="shell" class="sessions-collapsed"><aside id="pane"></aside></section></main>'),{document}=window,calls=[];
 const c={window,document,currentUser:{id:'owner'},activeSession:{id:'session',execution_status:'completed'},activeWorkspace:{id:'workspace'},activeProject:{id:'project'},
  shell:document.getElementById('shell'),pane:document.getElementById('pane'),previewStatus:{textContent:'Preview ready'},tr:(en,ar)=>c.lang==='ar'?ar:en,lang:'ar',
  textElement:(tag,text='',cls='')=>Object.assign(document.createElement(tag),{textContent:text,className:cls}),
  btn:(id,en,ar,fn,cls)=>{const b=Object.assign(document.createElement('button'),{textContent:c.tr(en,ar),className:cls,onclick:fn});return b;},
  setPanel:async mode=>calls.push(['panel',mode]),drawer:()=>false,togglePane:()=>{calls.push(['open']);c.shell.classList.remove('sessions-collapsed');},startPreview:async options=>calls.push(['start',options.fresh])};
 window.workspaceSubmissionBlocked=()=>['submitted','waiting_approval'].includes(c.activeSession.execution_status);
 vm.createContext(c);vm.runInContext(source.slice(source.indexOf('  let chatPreviewPending=false;'),source.indexOf('  const previewIcons=')),c);
 const action={kind:'preview',workspace_id:'workspace',project_id:'project',session_id:'session',message_id:'answer'},context={owner:'owner',sessionId:'session',messageId:'answer'},host=document.querySelector('article');
 return {c,calls,host,action,context,render(){window.renderWorkspaceMessageActions(host,[action],context);}};
}
(async()=>{let passed=0;
 {const f=fixture();f.render();assert.equal(f.calls.length,0);assert.equal(f.host.querySelector('button').textContent,'عرض التغييرات');await f.host.querySelector('button').onclick();assert.deepEqual(f.calls,[['panel','preview'],['open'],['start',true]]);assert.match(f.host.textContent,/Preview ready/);passed++;}
 for(const key of ['workspace_id','project_id','session_id','message_id']){const f=fixture();f.action[key]='foreign';f.render();assert.equal(f.host.children.length,0);assert.equal(f.calls.length,0);passed++;}
 {const f=fixture();f.render();f.c.currentUser={id:'other'};await f.host.querySelector('button').onclick();assert.equal(f.calls.length,0);passed++;}
 {const f=fixture();f.c.activeSession.execution_status='waiting_approval';f.render();assert.equal(f.host.querySelector('button').disabled,true);await f.host.querySelector('button').onclick();assert.equal(f.calls.length,0);passed++;}
 {const f=fixture();let finish,started;const ready=new Promise(r=>started=r);f.c.startPreview=()=>{started();return new Promise(r=>finish=r);};f.render();const b=f.host.querySelector('button'),first=b.onclick();await ready;await b.onclick();assert.equal(f.calls.filter(row=>row[0]==='panel').length,1);finish();await first;assert.equal(b.disabled,false);passed++;}
 {const f=fixture();f.c.setPanel=async()=>{f.c.activeWorkspace={id:'other'};};f.render();await f.host.querySelector('button').onclick();assert.equal(f.calls.length,0);passed++;}
 {const f=fixture();f.action.url='javascript:alert(1)';f.c.lang='en';f.render();assert.equal(f.host.querySelector('a'),null);assert.equal(f.host.querySelector('button').textContent,'View changes');passed++;}
 console.log(`${passed} PASSED / 0 FAILED / 0 SKIPPED: click-only owned Preview cards, current session/project/account checks, approval blocking, stale/duplicate guards and inert URLs`);
})().catch(error=>{console.error(error);process.exitCode=1;});
