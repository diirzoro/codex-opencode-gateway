/**
 * Real Pi RPC responsiveness benchmark (TEST sandbox only).
 * 1) Benchmarks existing always-on central service /health over UNIX socket.
 * 2) Runs exactly one short OpenRouter prompt in an isolated no-tools Pi process.
 * 3) Reports timing (start, prompt acceptance, first text, settlement), not credentials.
 *
 * Usage: node integration/pi-benchmark.mjs
 * Env: PI_BINARY, PI_MODEL, PI_PROVIDER, PI_SOCKET, PI_CWD, PI_TIMEOUT_MS
 */
import http from "node:http";
import {spawn} from "node:child_process";
import {performance} from "node:perf_hooks";
import {mkdirSync} from "node:fs";
const socket=process.env.PI_SOCKET||"/run/pi-central/pi.sock";
const pi=process.env.PI_BINARY||"/home/tahir/pi-test/node_modules/.bin/pi";
const provider=process.env.PI_PROVIDER||"openrouter";
const model=process.env.PI_MODEL||"openai/gpt-4o-mini";
const workspace=process.env.PI_CWD||"/home/tahir/pi-test";
const timeout=Math.max(10000,Math.min(120000,Number(process.env.PI_TIMEOUT_MS)||90000));
const p=()=>Number(performance.now().toFixed(1));
async function healthOnce(){
 return new Promise((resolve,reject)=>{
  const start=performance.now();
  const req=http.get({socketPath:socket,path:"/health",timeout:5000},res=>{
   let chunks="";res.on("data",b=>chunks+=b.toString());res.on("end",()=>resolve({
    status:res.statusCode,ms:Number((performance.now()-start).toFixed(1)),
    data:chunks.slice(0,400)
   }));
  });
  req.on("timeout",()=>req.destroy(new Error("Health timeout")));
  req.on("error",reject);
 });
}
async function main(){
 const health=[];
 for(let i=0;i<5;i++){health.push(await healthOnce());}
 const values=health.map(x=>x.ms).sort((a,b)=>a-b);
 console.log("SERVICE_HEALTH",JSON.stringify({
  responses:health.map(x=>x.status),median_ms:values[2],
  min_ms:values[0],max_ms:values[4],body:health.at(-1).data
 }));
 if(health.some(x=>x.status!==200))throw new Error("Central service is not ready");
 const t0=performance.now();
 let start=null,accepted=null,firstText=null,settled=null,error=null,buf="",eventCount=0,preview="";
 const child=spawn(pi,["--mode","rpc","--no-session","--no-tools",
   "--provider",provider,"--model",model,"--thinking","off"],{
   cwd:workspace,stdio:["pipe","pipe","pipe"],env:{...process.env,PI_SKIP_VERSION_CHECK:"1"}
 });
 // No stderr content or environment variables are printed: credentials stay private.
 child.stderr.resume();
 let requested=false;
 function request(){
  if(requested)return;
  requested=true;
  child.stdin.write(JSON.stringify({id:"bench-prompt",type:"prompt",
   message:"Reply with exactly one word: READY"})+"\n");
 }
 let done=false;
 const timer=setTimeout(()=>finish(new Error("Pi benchmark timeout")),timeout);
 function finish(e){
  if(done)return;done=true;clearTimeout(timer);
  try{child.kill("SIGTERM");}catch{}
  const ms=n=>n===null?null:Number((n-t0).toFixed(1));
  console.log("PI_BENCHMARK",JSON.stringify({
   provider,model,first_rpc_event_ms:ms(start),prompt_ack_ms:ms(accepted),
   first_text_ms:ms(firstText),settled_ms:ms(settled),events:eventCount,
   response_preview:preview.slice(0,120),error:e?.message||error||null
  }));
  process.exitCode=e||error?1:0;
 }
 child.on("error",finish);
 child.on("exit",(code)=>{if(!done)finish(new Error("Pi exited before completion (code "+code+")"));});
 child.stdout.setEncoding("utf8");
 child.stdout.on("data",chunk=>{
  buf+=chunk;
  if(buf.length>1_000_000)return finish(new Error("RPC output too large"));
  let pos;while((pos=buf.indexOf("\n"))!==-1){
   const line=buf.slice(0,pos).replace(/\r$/,"");buf=buf.slice(pos+1);
   let e;try{e=JSON.parse(line);}catch{continue;}
   eventCount++;
   if(start===null)start=performance.now();
   if(e.type==="response"&&e.id==="bench-state"){
    if(!e.success)return finish(new Error("get_state failed"));
    request();continue;
   }
   if(e.type==="response"&&e.id==="bench-prompt"){
    if(!e.success){error=String(e.error||"Prompt rejected");return finish(new Error(error));}
    accepted=performance.now();
    if(e.data?.disposition==="handled")return finish(new Error("Prompt handled without model run"));
    continue;
   }
   if(e.type==="message_update"&&e.assistantMessageEvent?.type==="text_delta"){
    firstText ??=performance.now();
    preview+=e.assistantMessageEvent.delta||"";
   }
   if(e.type==="agent_settled"){
    settled=performance.now();
    if(!preview) {
      // No response text is not silently reported as success.
      child.stdin.write(JSON.stringify({id:"bench-final",type:"get_last_assistant_text"})+"\n");
    } else return finish();
   }
   if(e.type==="response"&&e.id==="bench-final"){
    preview=String(e.data?.text||"");
    return finish(preview?undefined:new Error("Agent settled without assistant text"));
   }
  }
 });
 child.stdin.write(JSON.stringify({id:"bench-state",type:"get_state"})+"\n");
}
main().catch(e=>{console.error("BENCHMARK_ERROR",e.message);process.exitCode=1;});
