/* Real review controller; synthetic API + DOM. No external authorization/data. */
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const source=fs.readFileSync('enhancements.js','utf8');
const code=source.slice(source.indexOf('window.disconnectGithubWithReview='),source.indexOf('// Explicit server-verified identity confirmation'));
function fixture({failure=false,confirm=true,switchAccount=false}={}){
 const dom=new JSDOM('<main></main>'),d=dom.window.document,calls=[],messages=[];
 dom.window.HTMLDialogElement.prototype.showModal=function(){};dom.window.HTMLDialogElement.prototype.close=function(){};
 const c={window:{confirmAction:async()=>confirm},currentUser:{id:'owner'},lang:'en',document:d,toast:m=>messages.push(m),textElement:(tag,t='',cls='')=>{const e=d.createElement(tag);e.textContent=t;e.className=cls;return e;}};
 c.api=async(path,opts={})=>{const body=JSON.parse(opts.body||'{}');calls.push({path,body});
  if(path==='/api/github/disconnect/workspaces')return {connection_id:'new-link',workspaces:[{id:'owned',name:'<img src=x>',repository:'owner/repo',branch:'main',snapshot:'before',changes:[{status:' M',path:'draft.txt'}],ahead:1}]};
  if(body.action==='save'){if(failure)throw Error('Push rejected; files preserved');if(switchAccount)c.currentUser={id:'other'};return {verified:true,snapshot:'after'};}
  if(body.action==='delete')return {deleted:true};
  if(path==='/api/github/disconnect')return {grant_revocation:'verified'};throw Error(path);
 };
 vm.createContext(c);vm.runInContext(code,c);
 return {dom,d,c,calls,messages,open:()=>c.window.disconnectGithubWithReview(),button:prefix=>[...d.querySelectorAll('button')].find(x=>x.textContent.startsWith(prefix))};
}
(async()=>{
 const tick=()=>new Promise(r=>setImmediate(r));let passed=0;const pass=x=>{passed++;console.log('PASS '+x);};
 const f=fixture(),p=f.open();await tick();assert(!f.d.querySelector('img'));await f.button('Save to GitHub').onclick();assert.equal(await p,true);assert.deepEqual(f.calls.slice(1).map(x=>x.body.action||'disconnect'),['save','delete','disconnect']);assert.equal(f.calls[2].body.snapshot,'after');assert.equal(f.calls[3].body.connection_id,'new-link');assert(!f.d.querySelector('dialog'));f.dom.window.close();pass('review → verified save → exact copy delete → bound disconnect; no HTML injection');
 const keep=fixture(),k=keep.open();await tick();await keep.button('Disconnect and keep').onclick();assert.equal(await k,true);assert.equal(keep.calls.length,2);keep.dom.window.close();pass('keep copies never calls save or delete');
 const fail=fixture({failure:true}),q=fail.open();await tick();await fail.button('Save to GitHub').onclick();assert(fail.d.body.textContent.includes('Push rejected'));assert(!fail.calls.some(x=>x.body.action==='delete'||x.path==='/api/github/disconnect'));await fail.button('Cancel').onclick();assert.equal(await q,false);fail.dom.window.close();pass('push failure preserves copy and authorization; error visible');
 const changed=fixture({switchAccount:true}),r=changed.open();await tick();await changed.button('Save to GitHub').onclick();assert(!changed.calls.some(x=>x.body.action==='delete'||x.path==='/api/github/disconnect'));await changed.button('Cancel').onclick();await r;changed.dom.window.close();pass('account switch after save cannot delete or disconnect');
 const denied=fixture({confirm:false}),s=denied.open();await tick();await denied.button('Save to GitHub').onclick();assert.equal(denied.calls.length,1);await denied.button('Cancel').onclick();await s;denied.dom.window.close();pass('declined irreversible-action confirmation causes no writes');
 console.log(passed+' disconnect review DOM checks passed');
})().catch(e=>{console.error(e);process.exitCode=1});
