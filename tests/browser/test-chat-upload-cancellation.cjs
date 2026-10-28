const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const source=fs.readFileSync('dashboards.js','utf8'),start=source.indexOf('  let attachments=[];let attachmentRevision=0;'),end=source.indexOf("  q('openTools').onclick",start);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function fixture(){
 const dom=new JSDOM('<div id="attachments"></div>'),d=dom.window.document,calls=[];let aborted=false;
 const c={document:d,window:{nativeSession:{active:()=>true},workspaceSubmissionBlocked:()=>false},currentUser:{id:'owner-a'},activeWorkspace:{id:'workspace-a'},activeSession:{id:'session-a'},sending:false,pendingSubmission:null,attachmentList:d.querySelector('#attachments'),AbortController,AbortSignal,FormData:dom.window.FormData,URL,setTimeout,clearTimeout,toast:()=>{},saveNativeDraft:()=>{},loadStorage:async()=>{},createSession:async()=>{},tr:(en,ar)=>en,textElement:(tag,text='',cls='')=>{const e=d.createElement(tag);e.textContent=text;e.className=cls;return e;},api:async(path,options)=>{calls.push({path,options});if(options.method==='POST')return {id:'upload-a'};if(options.method==='DELETE')return {removed:true};if(options.method==='PUT')return new Promise((resolve,reject)=>{options.signal.addEventListener('abort',()=>{aborted=true;reject(Error('Aborted'));},{once:true});});}};
 vm.createContext(c);vm.runInContext(source.slice(start,end),c);
 await vm.runInContext('openAttachPicker()',c);
 const picker=d.querySelector('input[type=file]');Object.defineProperty(picker,'files',{value:[new dom.window.File(['synthetic attachment'],'qa.txt',{type:'text/plain'})]});const pending=picker.onchange();await tick();
 return {dom,d,c,calls,pending,aborted:()=>aborted};
}
(async()=>{
 const f=await fixture();const cancel=[...f.d.querySelectorAll('button')].find(e=>e.textContent==='Cancel upload');assert(cancel&&!cancel.disabled);await cancel.onclick();await f.pending;
 assert(f.aborted());assert.equal(f.calls.filter(x=>x.options.method==='DELETE').length,1);assert.equal(f.calls.find(x=>x.options.method==='PUT').options.headers['Content-Type'],'application/octet-stream');assert(f.d.body.textContent.includes('temporary attachment removed'));
 assert(!f.calls.some(x=>x.path.includes('/stop')||x.path.includes('/abort')||x.path.includes('/files/upload')));f.dom.window.close();console.log('PASS pending transfer really aborts; exact owned slot removed; Native execution not aborted');
 const other=await fixture();other.c.currentUser={id:'owner-b'};const remove=other.d.querySelector('button');await remove.onclick();await other.pending;assert(other.aborted());assert(!other.calls.some(x=>x.options.method==='DELETE'));other.dom.window.close();console.log('PASS account switch cannot delete a previous owner attachment through the new identity');
 const r=await fixture();vm.runInContext('window.restoreComposerAttachments([])',r.c);await r.pending;assert(r.aborted());assert(!r.d.querySelector('.composer-attachment'));r.dom.window.close();console.log('PASS switching draft cancels pending bytes; late results cannot restore old attachments');
})().catch(error=>{console.error(error);process.exitCode=1});
