// Async lifecycle regression only; not browser visual acceptance.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('dashboards.js','utf8');
const code=source.slice(source.indexOf('  let previewRevision=0;'),source.indexOf('  const previewActions='));
function fixture(){
  const requests=[];
  const context={activeWorkspace:{id:'owned'},previewStatus:{textContent:''},previewPath:{value:'index.html',hidden:false},frame:{hidden:true,srcdoc:'',removeAttribute(){}},tr:(en)=>en,api(path,options){return new Promise((resolve,reject)=>requests.push({path,options,resolve,reject}));}};
  vm.createContext(context);vm.runInContext(code+';globalThis.controls={startPreview,stopPreview,clearPreview};',context);
  return {context,requests,...context.controls};
}
(async()=>{
  {const f=fixture(),started=f.startPreview();assert.equal(f.requests.length,1);const stopped=f.stopPreview();f.requests[1].resolve({state:'stopped'});await stopped;f.requests[0].resolve({mode:'static'});await started;assert.equal(f.requests.length,2);assert.equal(f.context.frame.hidden,true);}
  {const f=fixture(),started=f.startPreview();f.requests[0].resolve({mode:'static'});await new Promise(resolve=>setImmediate(resolve));assert.equal(f.requests.length,2);const stopped=f.stopPreview();f.requests[2].resolve({});await stopped;f.requests[1].resolve({html:'stale application',path:'index.html'});await started;assert.equal(f.context.frame.srcdoc,'');assert.equal(f.context.frame.hidden,true);}
  {const f=fixture(),started=f.startPreview();f.requests[0].resolve({mode:'isolated_runner_required',framework:'vite'});await started;assert.equal(f.context.previewPath.hidden,true);assert.equal(f.context.frame.hidden,true);assert.equal(f.requests.length,1);assert.match(f.context.previewStatus.textContent,/No application was started/);}
  console.log('3 passed: stale detection, stale render after Stop, truthful blocked dynamic state');
})().catch(error=>{console.error(error);process.exitCode=1;});
