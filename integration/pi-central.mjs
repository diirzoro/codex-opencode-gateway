/**
 * Pi Central ↔ existing OpenCode-shaped TEST browser transport.
 * TEST ONLY. No Python AI proxy; Gateway is used strictly as auth/ownership oracle.
 * IMPORTANT: This adapter is designed for a single TEST host and is not a
 * production multi-tenant sandbox. Pi tools are deliberately disabled.
 *
 * Run under systemd, same UID as installed Pi. Do not expose on TCP.
 * Nginx must proxy /native-direct/api/ to this UNIX socket, stripping prefix.
 */
import http from "node:http";
import { spawn } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { mkdirSync, chmodSync, existsSync, unlinkSync } from "node:fs";
import path from "node:path";
import { URL } from "node:url";

const PI = process.env.PI_BINARY || "/home/tahir/pi-test/node_modules/.bin/pi";
const SOCK = process.env.PI_SOCKET || "/run/pi-central/pi.sock";
const ROOT = process.env.PI_SESSIONS_ROOT || "/home/tahir/pi-test/sessions";
const GATEWAY = process.env.PI_TEST_GATEWAY || "http://127.0.0.1:8001";
const HOST = "test.opencode-gateway.codes";
const MAX_PROCS = 2;
const IDLE_MS = 10 * 60_000;
const pool = new Map();
const json = (res, status, value) => {
  res.writeHead(status, { "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store", "x-content-type-options": "nosniff" });
  res.end(JSON.stringify(value));
};
function error(res, status, message) { json(res,status,{error:message}); }
function cleanPath(uri) {
  const url = new URL(uri, "http://localhost");
  return { pathname:url.pathname.replace(/^\/native-direct\/api/,"") || "/", query:url.searchParams };
}
async function gateway(req, endpoint) {
  const c=req.headers.cookie || "";
  if (!c || c.length > 8192) throw Object.assign(new Error("Authentication required"), {status:401});
  const ctrl = AbortSignal.timeout(5000);
  let response;
  try {
    response=await fetch(GATEWAY+endpoint, { signal:ctrl, redirect:"manual",
      headers:{cookie:c,host:HOST,"x-forwarded-proto":"https",accept:"application/json"} });
  } catch { throw Object.assign(new Error("Gateway unavailable"),{status:503}); }
  if (!response.ok) throw Object.assign(new Error(response.status===401?"Unauthorized":"Access denied"),
    {status:response.status===401?401:response.status===403?403:503});
  return response.json();
}
async function scope(req, query) {
  // Only Platform-owned paths are admitted; never run an arbitrary user URL directory.
  await gateway(req,"/api/auth/me");
  const directory=query.get("directory");
  if (!directory || directory.length>4096) throw Object.assign(new Error("Owned project directory required"),{status:400});
  const list=await gateway(req,"/api/workspaces");
  if (!Array.isArray(list) || list.length>500) throw Object.assign(new Error("Workspace inventory unavailable"),{status:503});
  for(const row of list) {
    if (!row?.id) continue;
    const detail=await gateway(req,"/api/workspaces/"+encodeURIComponent(row.id));
    if (detail.native_directory === directory && detail.project_id) {
      return { directory, workspaceId:String(row.id), projectId:String(detail.project_id) };
    }
  }
  throw Object.assign(new Error("Workspace not owned"),{status:403});
}
function projectIdFor(s) {
  return "pi_"+createHash("sha256").update(HOST+"\0"+s.workspaceId+"\0"+s.projectId).digest("hex").slice(0,32);
}
class Agent {
  constructor(s) {
    this.scope=s; this.id=projectIdFor(s); this.pending=new Map();
    this.events=new Set();this.buf="";this.serial=0;this.last=Date.now();
    this.closed=false;this.active=false;
    const sessionDir=path.join(ROOT,s.workspaceId);
    mkdirSync(sessionDir,{recursive:true,mode:0o700});
    this.child=spawn(PI,["--mode","rpc","--session-id",this.id,
      "--session-dir",sessionDir,"--no-tools","--name",s.projectId],{
        cwd:s.directory,stdio:["pipe","pipe","pipe"],env:process.env });
    this.child.stdout.setEncoding("utf8");
    this.child.stdout.on("data",data=>this.consume(data));
    this.child.stderr.on("data",()=>{}); // never expose secrets or stderr to clients
    this.child.on("error",()=>this.close());
    this.child.on("exit",()=>this.close());
  }
  consume(chunk) {
    this.last=Date.now();this.buf+=chunk;
    if(this.buf.length>4_000_000){this.close();return;}
    let n;
    while((n=this.buf.indexOf("\n"))>=0) {
      const line=this.buf.slice(0,n);this.buf=this.buf.slice(n+1);
      let x;try{x=JSON.parse(line);}catch{continue;}
      if(x.type==="response" && this.pending.has(x.id)) {
        const p=this.pending.get(x.id);this.pending.delete(x.id);clearTimeout(p.timer);
        x.success?p.resolve(x.data):p.reject(new Error(x.error||"Pi command failed"));
      } else if(x.type!=="response") {
        if(x.type==="agent_start")this.active=true;
        if(x.type==="agent_end"||x.type==="agent_settled")this.active=false;
        for(const res of this.events) {
          // Native Pi events are sent without invented OpenCode success states.
          try{res.write("data: "+JSON.stringify({type:"pi."+x.type,properties:x})+"\n\n");}catch{this.events.delete(res);}
        }
        if(x.type==="agent_end"||x.type==="agent_settled") {
          for(const res of this.events)try{res.write('data: {"type":"session.idle","properties":{"sessionID":"'+this.id+'"}}\n\n');}catch{}
        }
      }
    }
  }
  command(type, fields={}, ms=15000) {
    if(this.closed)return Promise.reject(new Error("Pi stopped"));
    this.last=Date.now();
    const id="req-"+(++this.serial)+"-"+randomUUID();
    return new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{this.pending.delete(id);reject(new Error("Pi timeout"));},ms);
      this.pending.set(id,{resolve,reject,timer});
      this.child.stdin.write(JSON.stringify({id,type,...fields})+"\n",err=>{
        if(err){clearTimeout(timer);this.pending.delete(id);reject(err);}
      });
    });
  }
  close() {
    if(this.closed)return;this.closed=true;
    for(const p of this.pending.values()){clearTimeout(p.timer);p.reject(new Error("Pi exited"));}
    this.pending.clear();
    for(const res of this.events)try{res.end();}catch{}
    this.events.clear();
    this.child.kill("SIGTERM");pool.delete(this.id);
  }
}
async function agent(s) {
  const id=projectIdFor(s);
  let a=pool.get(id);
  if(a && !a.closed)return a;
  if(pool.size>=MAX_PROCS)throw Object.assign(new Error("All Pi workers busy"),{status:503});
  a=new Agent(s);pool.set(id,a);
  await a.command("get_state");
  return a;
}
async function body(req) {
  let s="";for await(const part of req){s+=part;if(s.length>128_000)throw Object.assign(new Error("Body too large"),{status:413});}
  try{return s?JSON.parse(s):{};}catch{throw Object.assign(new Error("Invalid JSON"),{status:400});}
}
function mapped(messages, id) {
  return messages.map((m,index)=>{
    const text=Array.isArray(m.content) ? m.content.filter(x=>x.type==="text").map(x=>x.text||"").join("\n"):typeof m.content==="string"?m.content:"";
    const mid="msg_"+createHash("sha256").update(id+":"+index).digest("hex").slice(0,24);
    return {info:{id:mid,sessionID:id,role:m.role==="assistant"?"assistant":m.role==="user"?"user":"tool",time:{created:Date.now()}},
      parts:[{id:"part_"+mid,messageID:mid,sessionID:id,type:"text",text}]};
  });
}
const server=http.createServer(async(req,res)=>{
  try{
    const {pathname,query}=cleanPath(req.url||"/");
    if(pathname==="/health" && req.method==="GET")return json(res,200,{service:"pi-central",status:"ready",activeWorkers:pool.size});
    if(req.method!=="GET" && req.method!=="POST")return error(res,405,"Method not allowed");
    const s=await scope(req,query);
    const a=await agent(s);
    if(pathname==="/session" && req.method==="GET")return json(res,200,[{id:a.id,directory:s.directory,title:s.projectId}]);
    if(pathname==="/session" && req.method==="POST")return json(res,200,{id:a.id,directory:s.directory,title:s.projectId});
    if(pathname==="/session/status")return json(res,200,{[a.id]:{type:a.active?"busy":"idle"}});
    if(pathname==="/event") {
      res.writeHead(200,{"content-type":"text/event-stream","cache-control":"no-cache, no-store",
        connection:"keep-alive","x-accel-buffering":"no"});
      a.events.add(res);res.write(": connected\n\n");
      const t=setInterval(()=>{try{res.write(": ping\n\n");}catch{}},20000);
      req.on("close",()=>{clearInterval(t);a.events.delete(res);});
      return;
    }
    const m=pathname.match(/^\/session\/([A-Za-z0-9_-]+)(?:\/(.*))?$/);
    if(!m || m[1]!==a.id)return error(res,404,"Session not found");
    const action=m[2]||"";
    if(action==="" && req.method==="GET")return json(res,200,{id:a.id,directory:s.directory,title:s.projectId});
    if(action==="message" && req.method==="GET") {
      const data=await a.command("get_messages");
      return json(res,200,mapped(data?.messages||[],a.id));
    }
    if(action==="prompt_async" && req.method==="POST") {
      const b=await body(req);
      const message=(b.parts||[]).filter(x=>x.type==="text").map(x=>x.text||"").join("\n");
      if(!message.trim()||message.length>100000)return error(res,422,"Prompt required");
      if(b.model?.providerID&&b.model?.modelID)
        await a.command("set_model",{provider:b.model.providerID,modelId:b.model.modelID});
      await a.command("prompt",{message});
      res.writeHead(204,{"cache-control":"no-store"});res.end();return;
    }
    if(action==="abort" && req.method==="POST"){await a.command("abort",{},30000);return json(res,200,true);}
    return error(res,501,"Pi operation not implemented");
  }catch(e){return error(res,e.status||502,e.message||"Pi adapter error");}
});
server.on("clientError",(_,s)=>s.end("HTTP/1.1 400 Bad Request\r\n\r\n"));
mkdirSync(path.dirname(SOCK),{recursive:true,mode:0o700});
if(existsSync(SOCK))unlinkSync(SOCK);
server.listen(SOCK,()=>{chmodSync(SOCK,0o600);console.log("Pi TEST bridge on UNIX socket");});
setInterval(()=>{for(const a of pool.values())if(!a.active&&!a.events.size&&Date.now()-a.last>IDLE_MS)a.close();},60000).unref();
process.on("SIGTERM",()=>{server.close();for(const a of pool.values())a.close();});
