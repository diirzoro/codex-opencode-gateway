// Actual composer attachment functions in jsdom; no provider/model requests.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const source=fs.readFileSync('dashboards.js','utf8');
function fixture(lang='ar'){
 const {window}=new JSDOM('<form><div id="composerAttachments"></div><textarea id="promptInput"></textarea></form>');
 const {document}=window,calls=[],revoked=[];let picker;
 const create=document.createElement.bind(document);document.createElement=(tag)=>{const node=create(tag);if(tag==='input')picker=node;return node;};
 const c={window,document,lang,FormData:window.FormData,URL:{createObjectURL:()=> 'blob:preview',revokeObjectURL:value=>revoked.push(value)},
  activeWorkspace:{id:'owned'},currentUser:{id:'owner'},sending:false,pendingSubmission:null,attachmentList:document.getElementById('composerAttachments'),
  q:id=>document.getElementById(id),tr:(en,ar)=>lang==='ar'?ar:en,textElement:(tag,text='',cls='')=>Object.assign(document.createElement(tag),{textContent:text,className:cls}),
  api:async(path,options)=>{calls.push([path,options]);return {path:'uploads/'+options.body.get('file').name,size:12};},toast:message=>calls.push(['toast',message]),
  loadStorage:async()=>{},loadFiles:async()=>{},refreshGit:async()=>{}};
 vm.createContext(c);vm.runInContext(source.slice(source.indexOf('  let attachments=[];'),source.indexOf("  q('openTools').onclick")),c);
 return {c,document,calls,revoked,async upload(name,type='application/octet-stream'){await c.openAttachPicker();Object.defineProperty(picker,'files',{value:[new window.File(['test'],name,{type})]});await picker.onchange();}};
}
(async()=>{
 let passed=0;
 {const f=fixture();assert.ok(!source.includes('composer-file-support'));assert.ok(!source.includes('renderFileSupport'));assert.ok(!source.includes('attachmentModels'));assert.equal(f.document.querySelector('details'),null);passed++;}
 for(const [name,type] of [['photo.png','image/png'],['report.pdf','application/pdf'],['report.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document'],['legacy.doc','application/msword']]){
  const f=fixture();await f.upload(name,type);assert.equal(f.calls.filter(row=>row[0]==='/api/workspaces/owned/files/upload').length,1);assert.equal(f.calls.some(row=>row[0]==='toast'),false);assert.equal(f.document.querySelector('.composer-attachment span').firstChild.textContent,name);passed++;
 }
 {const f=fixture();await f.upload('photo.png','image/png');assert.equal(f.document.querySelector('img').getAttribute('src'),'blob:preview');f.document.querySelector('button').click();assert.equal(f.document.querySelector('.composer-attachment'),null);assert.deepEqual(f.revoked,['blob:preview']);assert.equal(f.calls.length,1);passed++;}
 {const f=fixture();await f.upload('report.txt','text/plain');await f.upload('report.txt','text/plain');assert.equal(f.calls.filter(row=>row[0].includes('/files/upload')).length,1);assert.match(f.calls.at(-1)[1],/مرفق بالفعل/);passed++;}
 {const f=fixture();f.c.api=async()=>{throw Error('Upload failed');};await f.upload('report.txt','text/plain');assert.match(f.document.querySelector('.composer-attachment small').textContent,/Upload failed/);passed++;}
 {const f=fixture();vm.runInContext('attachments=Array.from({length:10},(_,i)=>({name:String(i)}))',f.c);await f.upload('extra.txt');assert.equal(f.calls.length,1);assert.match(f.calls[0][1],/10/);passed++;}
 {const f=fixture('en');f.c.sending=true;assert.equal(f.c.window.restoreComposerAttachments([{name:'foreign.txt'}]),undefined);assert.equal(f.document.querySelector('.composer-attachment'),null);passed++;}
 {const f=fixture();f.c.window.restoreComposerAttachments([{name:'<script>bad</script>.txt',path:'uploads/file.txt',size:1,mime:'text/plain'}]);assert.equal(f.document.querySelector('script'),null);assert.match(f.document.querySelector('span').textContent,/<script>/);passed++;}
 {const f=fixture();let finish,started;const ready=new Promise(resolve=>started=resolve);f.c.api=()=>new Promise(resolve=>{finish=resolve;started();});const upload=f.upload('late.txt');await ready;f.c.currentUser={id:'other'};finish({path:'private/late.txt',size:1});await upload;assert.ok(!f.document.querySelector('.composer-attachment').textContent.includes('private/late.txt'));passed++;}
 console.log(`${passed} PASSED / 0 FAILED / 0 SKIPPED: compact composer, actual file-picker uploads, no model gate on upload, thumbnails/removal, duplicate/limit/error/owner guards`);
})().catch(error=>{console.error(error);process.exitCode=1;});
