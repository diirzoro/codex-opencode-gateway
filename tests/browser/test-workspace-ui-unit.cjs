// Actual frontend functions in a minimal DOM. Not visual/browser acceptance.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element{
 constructor(tag){this.tagName=tag;this.children=[];this.hidden=false;this.open=false;this.value='';this.checked=false;this.disabled=false;this.textContent='';this.parentElement=null;this.isConnected=false;}
 append(...nodes){for(const n of nodes){n.parentElement=this;n.isConnected=true;this.children.push(n);}}
 prepend(n){this.children.unshift(n);n.parentElement=this;}
 replaceChildren(...nodes){for(const n of this.children)n.isConnected=false;this.children=[];this.append(...nodes);}
 setAttribute(){}
 querySelector(selector){return this.querySelectorAll(selector)[0];}
 querySelectorAll(selector){const tags=selector.split(',');return this.children.flatMap(n=>[...(tags.includes(n.tagName)?[n]:[]),...n.querySelectorAll(selector)]);}
 insertBefore(n,before){n.parentElement=this;n.isConnected=true;const at=this.children.indexOf(before);this.children.splice(at<0?this.children.length:at,0,n);}
}
const source=fs.readFileSync('app.js','utf8'),dash=fs.readFileSync('dashboards.js','utf8');
function todo(){
 const parent=new Element('div'),form=new Element('form');parent.append(form);const calls=[];
 const c={currentUser:{id:'owner'},activeSession:{id:'A'},lang:'en',Date,api:path=>new Promise(resolve=>calls.push({path,resolve})),document:{createElement:tag=>new Element(tag),getElementById:id=>id==='promptForm'?form:parent.children.find(n=>n.id===id)}};
 vm.createContext(c);vm.runInContext(source.slice(source.indexOf('let todoLastCheck='),source.indexOf('async function refreshMessages()'))+';this.refresh=refreshWorkspaceTodos;',c);
 return {c,parent,form,calls,refresh:()=>c.refresh(true),panel:()=>parent.children.find(n=>n.id==='workspaceTodoPanel')};
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 {const f=todo(),p=f.refresh();f.calls[0].resolve({supported:true,items:[{content:'Done',status:'completed'},{content:'Doing',status:'in_progress'},{content:'Next',status:'pending'},{content:'Stopped',status:'cancelled'}]});await p;assert.equal(f.panel().open,false);assert.equal(f.parent.children.at(-2),f.panel());assert.match(f.panel().querySelector('summary').textContent,/1\/4 completed/);assert.equal(f.panel().querySelectorAll('li').length,4);}
 {const f=todo(),old=f.refresh();f.c.activeSession={id:'B'};const b=f.refresh();f.c.activeSession={id:'A'};const current=f.refresh();f.calls[2].resolve({supported:true,items:[{content:'new A',status:'completed'}]});await current;f.calls[0].resolve({supported:true,items:[{content:'stale A',status:'pending'}]});f.calls[1].resolve({supported:true,items:[{content:'stale B',status:'pending'}]});await Promise.all([old,b]);assert.equal(f.panel().querySelector('li').textContent,'new A');f.c.activeSession=null;await f.refresh();assert.equal(f.panel().hidden,true);}
 {const f=todo(),a=f.refresh(),b=f.refresh();assert.equal(f.calls.length,1);f.calls[0].resolve({supported:true,items:[]});await Promise.all([a,b]);assert.equal(f.panel().hidden,true);assert.ok(!dash.includes("const todoView="),'duplicate chat Todo renderer must be removed');}
 let questionChecks=0;
 for(const scenario of ['single','multiple','expired']){
  const feed=new Element('div'),post=[],notes=[];let current=[{id:'q',questions:[{question:'Choose',header:'Agent',multiple:scenario==='multiple',custom:true,options:[{label:'Blue',description:'Agent reason',recommended:true},{label:'Green',description:'Other',recommended:false}]}]}],finish;
  const c={activeSession:{id:'session'},currentUser:{id:'owner'},lang:'en',tr:en=>en,textElement:(tag,text='',cls='')=>{const e=new Element(tag);e.textContent=text;e.className=cls;return e;},document:{createElement:tag=>new Element(tag)},MutationObserver:class{observe(){}},q:()=>feed,toast:m=>notes.push(m),refreshSessionStatus:async()=>{},refreshMessages:async()=>{},window:{},api:async(path,opts)=>{if(!opts)return {requests:current};post.push(JSON.parse(opts.body));return new Promise((resolve,reject)=>{finish=()=>{current=[];scenario==='expired'?reject(Object.assign(new Error('expired'),{status:404})):resolve({accepted:true});};});}};
  vm.createContext(c);vm.runInContext(dash.slice(dash.indexOf("  const questionView="),dash.indexOf('  const approvalBusy=')),c);await c.window.refreshWorkspaceQuestions();const form=feed.querySelector('form');const inputs=form.querySelectorAll('input');assert.ok(inputs.every(i=>!i.checked));assert.match(form.querySelectorAll('button')[0].textContent,/Choose and Continue/);
  inputs[0].checked=true;if(scenario==='multiple')inputs.at(-1).value='Custom';
  form.onsubmit({preventDefault(){}});form.onsubmit({preventDefault(){}});assert.equal(post.length,1);assert.deepEqual(post[0].answers[0],scenario==='multiple'?['Blue','Custom']:['Blue']);finish();await flush();assert.equal(feed.children.at(-1).hidden,true);if(scenario==='expired')assert.match(notes[0],/expired/);questionChecks++;
 }
 let loginChecks=0;
 for(const kind of ['customer','empty','admin','owner-change']){
  const actions=[],c={currentUser:{id:'owner',role:kind==='admin'?'admin':'customer'},activeWorkspace:null,page:async p=>actions.push(p),restoreWorkspaceContext:async()=>{if(kind==='owner-change')c.currentUser={id:'new'};return kind==='empty'?{workspace:null}:{workspace:{id:'w'},project:{id:'p'},session:{id:'s'}};},api:async()=>({id:'s'}),openWorkspace:async(p,w)=>{c.activeWorkspace=w;actions.push('workspace');},selectSession:async()=>actions.push('session'),toast:()=>{}};
  vm.createContext(c);vm.runInContext(source.slice(source.indexOf('async function openWorkspaceAfterLogin()'),source.indexOf("$('#loginForm').onsubmit")),c);await c.openWorkspaceAfterLogin();assert.deepEqual(actions,kind==='customer'?['workspace','session']:kind==='empty'?['workspaceHomePage']:kind==='admin'?['adminPage']:[]);loginChecks++;
 }
 {
  let count=0,release;const c={currentUser:{id:'owner',role:'customer'},activeWorkspace:null,page:async()=>{},restoreWorkspaceContext:()=>{count++;return new Promise(resolve=>{release=resolve;});},openWorkspace:async()=>{},selectSession:async()=>{},toast:()=>{}};
  vm.createContext(c);vm.runInContext(source.slice(source.indexOf('async function openWorkspaceAfterLogin()'),source.indexOf("$('#loginForm').onsubmit")),c);
  const one=c.openWorkspaceAfterLogin(),two=c.openWorkspaceAfterLogin();assert.equal(count,1);release({workspace:null});await Promise.all([one,two]);loginChecks++;
 }
 console.log(`11 passed: 3 Todo lifecycle, ${questionChecks} question submission, ${loginChecks} login routing cases (VM, not browser)`);
})().catch(error=>{console.error(error);process.exitCode=1;});
