/**
 * Pi Central ↔ existing OpenCode-shaped TEST browser transport.
 * TEST ONLY. Pi is the only coding/provider engine; platform lookups only protect project files.
 * Existing bridge only; native Pi owns the shared provider configuration.
 * Workspace execution tools require project process isolation before activation.
 *
 * Run under systemd, same UID as installed Pi. Do not expose on TCP.
 * Nginx must proxy /native-direct/api/ to this UNIX socket, stripping prefix.
 */
import http from "node:http";
import { spawn } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { mkdirSync, chmodSync, existsSync, unlinkSync, readFileSync, writeFileSync, renameSync } from "node:fs";
import path from "node:path";
import { URL } from "node:url";

const PI = process.env.PI_BINARY || "/home/tahir/pi-test/node_modules/.bin/pi";
const SOCK = process.env.PI_SOCKET || "/run/pi-central/pi.sock";
const ROOT = process.env.PI_SESSIONS_ROOT || "/home/tahir/pi-test/sessions";
const PI_AGENT_DIR = process.env.PI_CODING_AGENT_DIR || "/home/tahir/.pi/agent";
const GATEWAY = process.env.PI_TEST_GATEWAY || "http://127.0.0.1:8001";
const HOST = "test.opencode-gateway.codes";
const MAX_PROCS = 2;
const IDLE_MS = 10 * 60_000;
const pool = new Map();
const CATALOG_DIRECTORY="/home/tahir/pi-test";
const CATALOG_TTL_MS=60_000;
const modelsSnapshots=new Map();

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
  const directory=query.get("directory");
  // Catalogue and agent discovery come straight from installed Pi, not Python.
  // Existing Nginx is the web entry boundary for this private socket.
  if(directory===CATALOG_DIRECTORY)return {catalog:true,userId:"shared"};
  if(!directory || directory.length>4096)
    throw Object.assign(new Error("Owned project directory required"),{status:400});
  // One narrow platform lookup establishes the workspace-file ownership;
  // it never manages providers, models, agent state, or conversations.
  const match=directory.match(/\/([0-9a-f-]{36})\/repo\/?$/i);
  if(!match)throw Object.assign(new Error("Invalid workspace directory"),{status:403});
  const who=await gateway(req,"/api/auth/me");
  const detail=await gateway(req,"/api/workspaces/"+encodeURIComponent(match[1]));
  if(detail.native_directory!==directory || !detail.project_id)
    throw Object.assign(new Error("Workspace not owned"),{status:403});
  return {directory,workspaceId:match[1],projectId:String(detail.project_id),userId:String(who.id)};
}
// The installed Pi auth.json is the sole shared provider-credential store.
// The web bridge does not create per-user copies or Gateway provider records.
function credentials() {
  const file=path.join(PI_AGENT_DIR,"auth.json");
  if(!existsSync(file))return {};
  const data=JSON.parse(readFileSync(file,"utf8"));
  if(!data||typeof data!=="object"||Array.isArray(data))
    throw new Error("Invalid installed Pi auth configuration");
  return data;
}
function writeCredentials(data) {
  const file=path.join(PI_AGENT_DIR,"auth.json");
  const temp=path.join(PI_AGENT_DIR,".auth-"+process.pid+"-"+Date.now()+".tmp");
  try {
    writeFileSync(temp,JSON.stringify(data),{mode:0o600,flag:"wx"});
    chmodSync(temp,0o600);
    renameSync(temp,file);
    chmodSync(file,0o600);
  } finally {if(existsSync(temp))unlinkSync(temp);}
  modelsSnapshots.clear();
}
function releaseProviderWorkers() {
  const workers=[...pool.values()].filter(a=>!a.closed);
  if(workers.some(a=>a.active))
    throw Object.assign(new Error("Stop active Pi responses before changing shared provider configuration"),{status:409});
  for(const a of workers)a.close();
}
function projectIdFor(s) {
  return "pi_"+createHash("sha256").update(HOST+"\0"+s.userId+"\0"+s.workspaceId+"\0"+s.projectId).digest("hex").slice(0,32);
}
class Agent {
  constructor(s) {
    this.scope=s; this.id=projectIdFor(s);this.title=s.projectId;
    this.events=new Set();this.buf="";this.requests=[];this.busy=false;this.last=Date.now();
    this.closed=false;this.active=false;
    const sessionDir=path.join(ROOT,"projects",s.userId,s.workspaceId);
    if(!s.catalog)mkdirSync(sessionDir,{recursive:true,mode:0o700});
    // Keep Pi's own built-in tools, extensions, skills and prompt templates.
    // No alternate tool executor or credential/configuration service.
    const args=["--mode","rpc",...(s.catalog?["--no-session"]:["--session-id",this.id,"--session-dir",sessionDir]),
      "--name",s.projectId];
    const env={PATH:process.env.PATH,HOME:process.env.HOME||"/home/tahir",
      LANG:process.env.LANG||"C.UTF-8",PI_SKIP_VERSION_CHECK:"1",PI_TELEMETRY:"0",
      PI_CODING_AGENT_DIR:PI_AGENT_DIR};
    this.child=spawn(PI,args,{cwd:s.directory,stdio:["pipe","pipe","pipe"],env});
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
      if(x.type==="response") {
        // Pi RPC's documented response key is "command"; it may omit request id.
        // Serialize requests to avoid matching a response to another caller.
        const p=this.requests.shift();
        if(p) {
          clearTimeout(p.timer);this.busy=false;
          x.success?p.resolve(x.data):p.reject(new Error(
            typeof x.error==="string"?x.error:x.error?.message||"Pi RPC command failed"));
          this.drain();
        }
      } else if(x.type!=="response") {
        if(x.type==="agent_start")this.active=true;
        if(x.type==="agent_settled")this.active=false;
        for(const res of this.events) {
          // Native Pi events are sent without invented OpenCode success states.
          try{res.write("data: "+JSON.stringify({type:"pi."+x.type,properties:x})+"\n\n");}catch{this.events.delete(res);}
        }
        if(x.type==="agent_settled") {
          for(const res of this.events)try{
            res.write("data: "+JSON.stringify({type:"message.updated",properties:{
              info:{id:"pi-refresh-"+Date.now(),sessionID:this.id,role:"assistant",
                time:{created:Date.now()}}}})+"\n\n");
            res.write("data: "+JSON.stringify({type:"session.idle",properties:{sessionID:this.id}})+"\n\n");
          }catch{}
        }
      }
    }
  }
  command(type, fields={}, ms=15000) {
    if(this.closed)return Promise.reject(new Error("Pi stopped"));
    this.last=Date.now();
    return new Promise((resolve,reject)=>{
      this.requests.push({type,fields,ms,resolve,reject});
      this.drain();
    });
  }
  drain() {
    if(this.busy||this.closed||!this.requests.length)return;
    this.busy=true;
    const next=this.requests[0];
    next.timer=setTimeout(()=>{
      // A lost RPC response means process state is uncertain. Never resend blindly.
      this.close();
    },next.ms);
    this.child.stdin.write(JSON.stringify({type:next.type,...next.fields})+"\n",err=>{
      if(err)this.close();
    });
  }
  close() {
    if(this.closed)return;this.closed=true;
    for(const p of this.requests){clearTimeout(p.timer);p.reject(new Error("Pi exited or timed out"));}
    this.requests=[];
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
  try { await a.command("get_state"); return a; }
  catch(e) { a.close(); throw e; }
}
async function body(req) {
  let s="";for await(const part of req){s+=part;if(s.length>12*1024*1024)throw Object.assign(new Error("Body too large"),{status:413});}
  try{return s?JSON.parse(s):{};}catch{throw Object.assign(new Error("Invalid JSON"),{status:400});}
}
function piPromptParts(rawParts, scope, sessionId) {
  // The existing browser form sends file parts as data URLs or file:// URLs.
  // Images go directly to Pi RPC; other files are staged *inside* the owned
  // Pi workspace and referenced by path for Pi's native tools to inspect.
  const parts=Array.isArray(rawParts)?rawParts:[];
  const messages=[], images=[];
  for(const p of parts) {
    if(p?.type==="text") {
      if(typeof p.text==="string")messages.push(p.text);
      continue;
    }
    if(p?.type!=="file")continue;
    const filename=path.basename(String(p.filename||"attachment")).replace(/[\x00-\x1F]/g,"_").slice(0,140)||"attachment";
    const source=String(p.url||"");
    if(source.startsWith("file:")) {
      const u=new URL(source);
      if(u.protocol!=="file:"||u.hostname||u.search||u.hash)
        throw Object.assign(new Error("Invalid workspace file reference"),{status:422});
      const absolute=path.resolve(decodeURIComponent(u.pathname));
      const root=path.resolve(scope.directory);
      if(!absolute.startsWith(root+path.sep))
        throw Object.assign(new Error("File is outside the selected workspace"),{status:422});
      messages.push("Attached workspace file: "+path.relative(root,absolute));
      continue;
    }
    const match=/^data:([^;,]+);base64,([A-Za-z0-9+/=]+)$/.exec(source);
    if(!match)throw Object.assign(new Error("Unsupported file data. Upload an existing workspace file or an inline attachment."),{status:422});
    const mime=match[1].toLowerCase();
    const data=Buffer.from(match[2],"base64");
    if(data.length>8*1024*1024)
      throw Object.assign(new Error("Attachment exceeds 8 MB"),{status:413});
    if(["image/png","image/jpeg","image/webp"].includes(mime)){
      images.push({type:"image",data:match[2],mimeType:mime});
      messages.push("Attached image: "+filename);
      continue;
    }
    const target=path.join(scope.directory,".pi-uploads",sessionId,randomUUID(),filename);
    mkdirSync(path.dirname(target),{recursive:true,mode:0o700});
    writeFileSync(target,data,{mode:0o600,flag:"wx"});
    messages.push("Attached file for Pi tools to inspect: "+path.relative(scope.directory,target));
  }
  return {message:messages.join("\n"),images};
}
function mapped(messages, id) {
  return messages.map((m,index)=>{
    const text=Array.isArray(m.content) ? m.content.filter(x=>x.type==="text").map(x=>x.text||"").join("\n"):typeof m.content==="string"?m.content:"";
    const mid="msg_"+createHash("sha256").update(id+":"+index).digest("hex").slice(0,24);
    return {info:{id:mid,sessionID:id,role:m.role==="assistant"?"assistant":m.role==="user"?"user":"tool",time:{created:Date.now()}},
      parts:[{id:"part_"+mid,messageID:mid,sessionID:id,type:"text",text}]};
  });
}

function providerCatalog(models,userId){
  // Pi model availability is not authentication. A model in the catalog must
  // NEVER imply that an account has an API key or a verified connection.
  const grouped=new Map();
  for(const model of models){
    if(!model || typeof model.id!=="string" || typeof model.provider!=="string")continue;
    const id=model.provider;
    // Retired OpenCode Native itself is not a provider in this TEST platform.
    if(id==="opencode")continue;
    let row=grouped.get(id);
    if(!row){row={id,name:id,models:{}};grouped.set(id,row);}
    row.models[model.id]={id:model.id,name:model.name||model.id,reasoning:Boolean(model.reasoning),
      context:model.contextWindow,maxTokens:model.maxTokens,cost:model.cost||null};
  }
  const all=[...grouped.values()];
  const native=credentials();
  const connected=all.filter(row=>native[row.id]?.type==="api_key" &&
    typeof native[row.id]?.key==="string" && native[row.id].key.length>0).map(row=>row.id);
  // Key presence is NOT evidence the remote provider accepts it.
  return {all,connected,default:{},verification:"pi_configured_unverified"};
}
async function configuredModels(userId){
  const cached=modelsSnapshots.get(userId);
  if(cached&&Date.now()-cached.time<CATALOG_TTL_MS)return cached.models;
  const a=new Agent({directory:CATALOG_DIRECTORY,workspaceId:"catalog",
    projectId:"catalog",userId,catalog:true});
  try {
    const data=await a.command("get_available_models");
    const models=Array.isArray(data?.models)?data.models:[];
    modelsSnapshots.set(userId,{models,time:Date.now()});
    return models;
  }finally{a.close();}
}
const server=http.createServer(async(req,res)=>{
  try{
    const {pathname,query}=cleanPath(req.url||"/");
    if(pathname==="/health" && req.method==="GET")return json(res,200,{service:"pi-central",status:"ready",activeWorkers:pool.size});
    if(!["GET","POST","PATCH","PUT","DELETE"].includes(req.method))return error(res,405,"Method not allowed");
    const s=await scope(req,query);
    if(s.catalog){
      if(pathname==="/provider"&&req.method==="GET")
        return json(res,200,providerCatalog(await configuredModels(s.userId),s.userId));
      if(pathname==="/agent"&&req.method==="GET")
        return json(res,200,[{name:"build",mode:"primary",hidden:false}]);
      if(pathname==="/provider/auth"&&req.method==="GET") {
        const result={};
        for(const p of providerCatalog(await configuredModels(s.userId),s.userId).all)
          result[p.id]=[{type:"api",label:"API key"}];
        return json(res,200,result);
      }
      const auth=pathname.match(/^\/auth\/([a-zA-Z0-9._-]{1,120})$/);
      if(auth&&["PUT","DELETE"].includes(req.method)) {
        const provider=auth[1];
        if(["__proto__","prototype","constructor"].includes(provider))return error(res,400,"Invalid provider");
        const stored=credentials();
        if(req.method==="PUT"){
          const payload=await body(req);
          if(payload?.type!=="api"||typeof payload.key!=="string"||
            !payload.key.trim()||payload.key.length>8192)
            return error(res,422,"Invalid Pi API credential");
          releaseProviderWorkers();
          stored[provider]={type:"api_key",key:payload.key.trim()};
        }else{
          releaseProviderWorkers();
          delete stored[provider];
        }
        writeCredentials(stored);
        return json(res,200,true);
      }
      return error(res,404,"Pi account endpoint not found");
    }
    const a=await agent(s);
    if(pathname==="/session" && req.method==="GET")return json(res,200,[{id:a.id,directory:s.directory,title:a.title}]);
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
      const {message,images}=piPromptParts(b.parts,s,a.id);
      if((!message.trim()&&!images.length)||message.length>100000)
        return error(res,422,"Prompt required");
      if(b.model?.providerID&&b.model?.modelID)
        await a.command("set_model",{provider:b.model.providerID,modelId:b.model.modelID});
      await a.command("prompt",{message,...(images.length?{images}:{})});
      res.writeHead(204,{"cache-control":"no-store"});res.end();return;
    }
    if(action==="abort" && req.method==="POST"){await a.command("abort",{},30000);return json(res,200,true);}
    return error(res,501,"Pi operation not implemented");
  }catch(e){return error(res,e.status||502,e.message||"Pi adapter error");}
});
server.on("clientError",(_,s)=>s.end("HTTP/1.1 400 Bad Request\r\n\r\n"));
mkdirSync(path.dirname(SOCK),{recursive:true,mode:0o700});
if(existsSync(SOCK))unlinkSync(SOCK);
server.listen(SOCK,()=>{chmodSync(SOCK,0o660);console.log("Pi TEST bridge on UNIX socket");});
setInterval(()=>{for(const a of pool.values())if(!a.active&&!a.events.size&&Date.now()-a.last>IDLE_MS)a.close();},60000).unref();
process.on("SIGTERM",()=>{server.close();for(const a of pool.values())a.close();});
