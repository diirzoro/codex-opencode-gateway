// Real refreshSessions orchestration, controlled runtime/catalog timing.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('dashboards.js','utf8');
function fixture(){
 const requests=[],rendered=[],c={activeWorkspace:{id:'one'},currentUser:{id:'owner'},activeSession:{id:'selected'},historyRevision:0,sessionListPending:null,sessionRows:[{id:'existing'}],
  renderRuntimeSessions:rows=>{rendered.push(rows);c.sessionRows=rows;},selectSession:async()=>{},updateSend(){},api:path=>new Promise((resolve,reject)=>requests.push({path,resolve,reject}))};
 vm.createContext(c);vm.runInContext(source.slice(source.indexOf('  refreshSessions=async function(){'),source.indexOf('  async function renameConversation(')),c);return {c,requests,rendered};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{let passed=0;
 {const f=fixture(),pending=f.c.refreshSessions();f.requests[1].resolve([{id:'all-owned'}]);await tick();assert.equal(f.rendered[0][0].id,'all-owned');f.requests[0].resolve([]);await pending;passed++;}
 {const f=fixture(),pending=f.c.refreshSessions();f.requests[1].resolve([{id:'all-owned'}]);f.requests[0].reject(Error('Cold runtime unavailable'));await assert.rejects(pending,/Cold runtime/);assert.equal(f.c.sessionRows[0].id,'all-owned');passed++;}
 {const f=fixture(),pending=f.c.refreshSessions();f.requests[0].resolve([]);f.requests[1].reject(Error('History unavailable'));await assert.rejects(pending,/History unavailable/);assert.equal(f.c.sessionRows[0].id,'existing');assert.equal(f.rendered.length,0);passed++;}
 {const f=fixture(),first=f.c.refreshSessions(),second=f.c.refreshSessions();assert.equal(f.requests.length,2);f.requests[1].resolve([]);f.requests[0].resolve([]);await Promise.all([first,second]);passed++;}
 {const f=fixture(),first=f.c.refreshSessions();f.c.activeWorkspace={id:'two'};const second=f.c.refreshSessions();f.requests[3].resolve([{id:'newest-history'}]);f.requests[2].resolve([]);await second;f.requests[1].resolve([{id:'old-history'}]);f.requests[0].resolve([]);await first;assert.equal(f.c.sessionRows[0].id,'newest-history');passed++;}
 {const f=fixture(),pending=f.c.refreshSessions();f.c.currentUser={id:'other'};f.requests[1].resolve([{id:'foreign-history'}]);f.requests[0].resolve([]);await pending;assert.equal(f.rendered.length,0);passed++;}
 {const f=fixture(),pending=f.c.refreshSessions();f.c.currentUser={id:'other'};f.requests[1].reject(Error('Old account error'));f.requests[0].reject(Error('Old workspace error'));await pending;assert.equal(f.rendered.length,0);passed++;}
 {const block=source.slice(source.indexOf('  openWorkspace=async function('),source.indexOf('  async function refreshSessionStatus('));assert.ok(!block.includes('sessionRows=[]'));assert.ok(source.includes("pendingSubmission=null;sending=cancelRequested=false;sessionRows=[]"));passed++;}
 console.log(`${passed} PASSED / 0 FAILED / 0 SKIPPED: history visible before cold runtime, retained on errors/workspace switch, coalescing and stale-account/request guards`);
})().catch(error=>{console.error(error);process.exitCode=1;});
