const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('app.js','utf8');
const fn=source.slice(source.indexOf('async function refreshPermissions(){'),source.indexOf("$('#promptForm').onsubmit="));
function setup(){
 const c={activeSession:{id:'session'},currentUser:{id:'owner'},permissionPending:null,permissionFailureNotice:null,
  requests:[],notices:[],stops:0,renders:[],questions:0,
  api:async()=>{throw Object.assign(new Error('OpenCode returned HTTP 400 [reference bdb8fb154931]'),{status:502});},
  stopEvents(){c.stops++;},toast(message){c.notices.push(message);},
  window:{renderWorkspaceApprovals:async(rows,id)=>c.renders.push([rows,id]),refreshWorkspaceQuestions:async()=>c.questions++}};
 vm.createContext(c);vm.runInContext(fn,c);return c;
}
(async()=>{
 const c=setup();await assert.rejects(c.refreshPermissions(),/HTTP 400/);
 assert.equal(c.stops,0);assert.equal(c.renders.length,0);assert.equal(c.notices.length,1);assert.equal(c.permissionPending,null);
 // Changing diagnostic references must not flood the user with the same toast.
 c.api=async()=>{throw Object.assign(new Error('OpenCode returned HTTP 400 [reference 123456abcdef]'),{status:502});};
 await assert.rejects(c.refreshPermissions());assert.equal(c.notices.length,1);assert.equal(c.stops,0);
 // Successful retry renders actual pending approvals and restores question polling.
 c.api=async()=>[{id:'pending',permission:'bash',patterns:['node server.js']}];
 await c.refreshPermissions();assert.equal(c.renders.length,1);assert.equal(c.renders[0][0][0].id,'pending');assert.equal(c.questions,1);assert.equal(c.permissionFailureNotice,null);
 c.api=async()=>{throw new Error('new failure');};await assert.rejects(c.refreshPermissions());assert.equal(c.notices.length,2);
 // Ignore both successful and failed responses belonging to a previous user.
 for(const failure of [false,true]){
  const stale=setup();let release;stale.api=()=>new Promise((resolve,reject)=>release=failure?reject:resolve);
  const task=stale.refreshPermissions();stale.currentUser={id:'other'};release(failure?new Error('private error'):[{id:'private'}]);
  if(failure)await assert.rejects(task);else await task;
  assert.equal(stale.notices.length,0);assert.equal(stale.renders.length,0);assert.equal(stale.stops,0);
 }
 // Concurrent poll callers share one API request and one render.
 const shared=setup();let release,calls=0;shared.api=()=>{calls++;return new Promise(resolve=>release=resolve);};
 const first=shared.refreshPermissions(),second=shared.refreshPermissions();release([]);await Promise.all([first,second]);assert.equal(calls,1);assert.equal(shared.renders.length,1);
 shared.activeSession=null;await shared.refreshPermissions();assert.equal(calls,1);
 console.log('6 PASSED / 0 FAILED / 0 SKIPPED: stream preservation, notice dedup, retry recovery, cross-user stale success/error, poll coalescing and no-session guard (actual function/controlled API)');
})().catch(error=>{console.error(error);process.exitCode=1;});
