/* Actual shared API response handling, controlled HTTP fixtures, no browser credentials. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('app.js','utf8');
const block=source.slice(source.indexOf('const api=async('),source.indexOf('function toast('));
async function request(path,status,marker){
 const c={window:{},authenticationRevision:1,authenticatedRequests:new Set(),AbortController,FormData,currentUser:null,
  invalidateProviderMutation(){},clearAuthenticatedState(){},
  fetch:async()=>new Response(JSON.stringify({detail:'Synthetic metadata refusal'}),{status,headers:{'Content-Type':'application/json',...(marker?{'X-Native-Request-Outcome':marker}:{})}})};
 vm.createContext(c);vm.runInContext(block+'\nthis.runApi=api;',c);
 try{await c.runApi(path,{method:'POST',body:'{}'});return null;}catch(error){return error;}
}
(async()=>{
 let n=0;
 for(const status of [408,502,503,504]){const e=await request('/native-session/owned/session/ses_a/prompt_async',status,'not-forwarded');assert.equal(e.status,status);assert.equal(e.nativeNotForwarded,true);assert.equal(e.message,'Synthetic metadata refusal');n++;}
 for(const path of ['/api/github/confirm','/api/workspaces/owned']){const e=await request(path,503,'not-forwarded');assert.equal(e.nativeNotForwarded,false);n++;}
 for(const marker of [null,'forwarded','unknown']){const e=await request('/native-session/owned/session/ses_a/prompt_async',502,marker);assert.equal(e.nativeNotForwarded,false);n++;}
 assert.equal(await request('/native-session/owned/session/ses_a/prompt_async',200,'not-forwarded'),null);n++;
 console.log(`${n} shared API receipt checks passed; controlled HTTP, not TEST acceptance`);
})().catch(error=>{console.error(error);process.exitCode=1;});
