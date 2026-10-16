// Actual frontend functions, isolated DOM/event fixtures; not TEST visual acceptance.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const app=fs.readFileSync('app.js','utf8'),dash=fs.readFileSync('dashboards.js','utf8');
class Element{
 constructor(tag){this.tagName=tag;this.children=[];this.dataset={};this.events={};this.hidden=false;this.open=false;this.isConnected=true;this.scrollTop=0;this.clientHeight=400;this.scrollHeight=1000;}
 append(...items){for(const item of items){item.parentElement=this;this.children.push(item);}}
 setAttribute(k,v){this[k]=v;}
 addEventListener(k,fn){this.events[k]=fn;}
 replaceChildren(...items){this.children=[];this.append(...items);}
 querySelector(){return {textContent:''};}
}
function scrollFixture(){
 const parent=new Element('section'),feed=new Element('div');feed.scrollTop=600;parent.append(feed);
 const frames=[],mutations=[],resizes=[];
 const c={lang:'en',document:{createElement:t=>new Element(t),getElementById:id=>parent.children.find(n=>n.id===id)},window:{addEventListener(){}},requestAnimationFrame:fn=>{frames.push(fn);return frames.length;},MutationObserver:class{constructor(fn){mutations.push(fn);}observe(){}},ResizeObserver:class{constructor(fn){resizes.push(fn);}observe(){}disconnect(){}}};
 vm.createContext(c);vm.runInContext(app.slice(app.indexOf('function workspaceLatestControl('),app.indexOf('// Session-scoped OpenCode tasks')),c);c.workspaceLatestControl(feed);
 return {c,feed,frames,mutations,resizes,button:()=>parent.children.find(n=>n.id==='workspaceJumpLatest'),flush(){while(frames.length)frames.shift()();}};
}
(async()=>{
 let passed=0;
 {const f=scrollFixture();f.feed.scrollHeight=1600;f.mutations[0]();f.resizes[0]();assert.equal(f.frames.length,1);f.flush();assert.equal(f.feed.scrollTop,1600);passed++;}
 {const f=scrollFixture();f.feed.scrollTop=180;f.feed.events.scroll();f.feed.scrollHeight=1700;f.mutations[0]();f.flush();assert.equal(f.feed.scrollTop,180);assert.equal(f.button().hidden,false);passed++;}
 {const f=scrollFixture();f.feed.scrollTop=180;f.feed.events.scroll();f.button().onclick();f.flush();assert.equal(f.feed.scrollTop,1000);f.feed.scrollTop=600;f.feed.events.scroll();assert.equal(f.button().hidden,true);passed++;}
 {const f=scrollFixture();f.feed.scrollHeight=1900;f.resizes[0]();f.flush();assert.equal(f.feed.scrollTop,1900);passed++;}
 {const f=scrollFixture();f.feed.scrollHeight=1500;f.mutations[0]();f.feed.scrollTop=100;f.feed.events.scroll();f.flush();assert.equal(f.feed.scrollTop,100,'user scroll cancels queued follow');passed++;}
 function folders(){
  const calls=[],rendered=[],c={currentUser:{id:'owner'},document:{createElement:t=>new Element(t)},FILE_ICONS:{directory:'<svg></svg>'},tr:en=>en,textElement:(tag,text='',cls='')=>Object.assign(new Element(tag),{textContent:text,className:cls}),text:(tag,en)=>Object.assign(new Element(tag),{textContent:en}),btn:(id,en,ar,click)=>Object.assign(new Element('button'),{id,textContent:en,onclick:click}),openWorkspace:()=>{throw Error('expanding folders must not switch workspace');},api:path=>new Promise((resolve,reject)=>calls.push({path,resolve,reject})),renderFileRows:(...args)=>rendered.push(args)};
  vm.createContext(c);vm.runInContext(dash.slice(dash.indexOf('  function projectFileFolder('),dash.indexOf('  let projectListRevision=')),c);
  return {c,calls,rendered,folder:c.projectFileFolder({id:'p',name:'same-name',repository:'owner/repo',source_type:'github'},{id:'owned-workspace'})};
 }
 {const f=folders();assert.equal(f.calls.length,0);f.folder.open=true;const p=f.folder.events.toggle();f.folder.events.toggle();assert.equal(f.calls.length,1);assert.equal(f.calls[0].path,'/api/workspaces/owned-workspace/files');f.calls[0].resolve([{name:'src',path:'src',type:'directory'}]);await p;assert.equal(f.rendered.length,1);assert.equal(f.rendered[0][2].workspaceId,'owned-workspace');assert.equal(f.rendered[0][2].detachedProject,true);await f.folder.events.toggle();assert.equal(f.calls.length,1);passed++;}
 {const f=folders();f.folder.open=true;const p=f.folder.events.toggle();f.c.currentUser={id:'other'};f.calls[0].resolve([{name:'private'}]);await p;assert.equal(f.rendered.length,0);passed++;}
 {const f=folders();f.folder.open=true;const p=f.folder.events.toggle();f.folder.isConnected=false;f.calls[0].resolve([]);await p;assert.equal(f.rendered.length,0);passed++;}
 {const f=folders();f.folder.open=true;const p=f.folder.events.toggle();f.calls[0].reject(Error('Unavailable'));await p;const retry=f.folder.events.toggle();assert.equal(f.calls.length,2);f.calls[1].resolve([]);await retry;assert.equal(f.rendered.length,1);passed++;}
 for(const changeOwner of [false,true]){
  const calls=[],host=new Element('div'),root=new Element('div'),status=new Element('p');let finish;
  const c={lang:'en',activeWorkspace:{id:'different-project'},currentUser:{id:'owner'},filesTree:root,filesStatus:status,FILE_ICONS:{directory:'<svg></svg>',file:'<svg></svg>'},tr:en=>en,textElement:(tag,text='',cls='')=>Object.assign(new Element(tag),{textContent:text,className:cls}),api:path=>{calls.push(path);return new Promise(resolve=>{finish=resolve;});}};
  vm.createContext(c);vm.runInContext(dash.slice(dash.indexOf('  function renderFileRows('),dash.indexOf('  async function loadFiles(')),c);
  c.renderFileRows(host,[{name:'src',path:'src',type:'directory'}],{workspaceId:'folder-workspace',owner:'owner',root,status,detachedProject:true});
  const button=host.children[0].children[0],children=host.children[0].children[1];const pending=button.onclick();assert.equal(calls[0],'/api/workspaces/folder-workspace/files?path=src');
  if(changeOwner)c.currentUser={id:'new-owner'};finish([]);await pending;
  assert.equal(children.children.length,changeOwner?0:1);passed++;
 }
 console.log(`${passed} passed: 5 follow-scroll and 6 lazy folder/isolation cases (VM, not browser)`);
})().catch(error=>{console.error(error);process.exitCode=1;});
