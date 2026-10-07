/* Unit fixtures for bootstrap single-flight; no external-provider success is simulated. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
function client(api){const sandbox={window:{},api,performance:{now:()=>Date.now(),measure:()=>{}},Date};vm.createContext(sandbox);vm.runInContext(fs.readFileSync('runtime-client.js','utf8'),sandbox);return sandbox.window.workspaceRuntime;}
test('bootstrap coalesces callers, caches warm state and isolates workspaces',async()=>{
 const calls=[];const runtime=client(async url=>{calls.push(url);await new Promise(r=>setTimeout(r,5));return {workspace_id:url};});
 const [one,two]=await Promise.all([runtime.load('one'),runtime.load('one')]);assert.equal(one,two);assert.equal(calls.length,1);
 await runtime.load('one');assert.equal(calls.length,1);await runtime.load('two');assert.equal(calls.length,2);
 runtime.invalidate('one');await runtime.load('one');assert.equal(calls.length,3);
});
test('auth invalidation during bootstrap waits then fetches fresh state',async()=>{
 let release;let calls=0;const runtime=client(async()=>{calls++;if(calls===1)await new Promise(r=>{release=r;});return {revision:calls};});
 const old=runtime.load('one');runtime.invalidate('one');const fresh=runtime.load('one',{force:true});release();await old;
 assert.equal((await fresh).revision,2);assert.equal((await runtime.load('one')).revision,2);
});
