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
import { spawn, execFileSync } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { mkdirSync, chmodSync, existsSync, unlinkSync, readFileSync, writeFileSync, readdirSync, lstatSync, realpathSync } from "node:fs";
import path from "node:path";
import { URL } from "node:url";

const PI = process.env.PI_BINARY || "/home/tahir/pi-test/node_modules/.bin/pi";
const SOCK = process.env.PI_SOCKET || "/run/pi-central/pi.sock";
const ROOT = process.env.PI_SESSIONS_ROOT || "/home/tahir/pi-test/sessions";
const PI_AGENT_DIR = process.env.PI_CODING_AGENT_DIR || "/home/tahir/.pi/agent";
const GATEWAY = process.env.PI_TEST_GATEWAY || "http://127.0.0.1:8001";
const HOST = "test.opencode-gateway.codes";
// A bounded pool reuses idle Pi workers rather than rejecting the next workspace.
// Keep the default pool small on the shared 1-vCPU/4-GB TEST VPS.
const MAX_PROCS = Math.max(1,Math.min(32,Number(process.env.PI_MAX_WORKERS)||2));
const MAX_ACTIVE_EXECUTIONS = Math.max(1,Math.min(MAX_PROCS,Number(process.env.PI_MAX_ACTIVE_EXECUTIONS)||1));
const executing = new Set();
function reserveExecution(agent) {
  // Reserve before set_model/prompt to close the admission race.
  if(agent.active||executing.has(agent))
    throw Object.assign(new Error("This project is already running a Pi request"),{status:409});
  if(executing.size>=MAX_ACTIVE_EXECUTIONS)
    throw Object.assign(new Error("Pi coding capacity reached; retry after the running task settles"),{status:429});
  executing.add(agent);
}
function releaseExecution(agent) { executing.delete(agent); }
const IDLE_MS = 10 * 60_000;
const pool = new Map();
const CATALOG_DIRECTORY="/home/tahir/pi-test";
const CATALOG_TTL_MS=60_000;
const modelsSnapshots=new Map();
const commandsSnapshots=new Map();
let nativeDiscoveryPending=null;
let nativeCommandsPending=null;
let piInventoryRevision=0;

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
  if (!response.ok) {
    // Preserve the genuine Gateway result; a missing workspace is a 404,
    // not a misleading 503 from the Pi provider or session engine.
    const status=response.status;
    throw Object.assign(new Error("Project lookup returned HTTP "+status),
      {status: [400,401,403,404,410].includes(status)?status:502});
  }
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
  const match=directory.match(/\/([0-9a-f-]{36})\/([0-9a-f-]{36})\/repo\/?$/i);
  if(!match)throw Object.assign(new Error("Invalid workspace directory"),{status:403});
  // The existing project endpoint already checks the logged-in owner's
  // cookie. No separate Python auth/me or AI service check is required.
  const detail=await gateway(req,"/api/workspaces/"+encodeURIComponent(match[2]));
  if(detail.native_directory!==directory || detail.id!==match[2] || !detail.project_id)
    throw Object.assign(new Error("Workspace not owned"),{status:403});
  return {directory,workspaceId:match[2],projectId:String(detail.project_id),userId:match[1]};
}
// The installed Pi SDK owns provider login, logout, and credential storage.
// No custom auth.json reader/writer or Gateway provider ledger exists here.
async function piModels() {
  const {ModelRuntime}=await import("@earendil-works/pi-coding-agent");
  if(!ModelRuntime?.create)
    throw Object.assign(new Error("Installed Pi ModelRuntime API is unavailable"),{status:502});
  return ModelRuntime.create({
    authPath:path.join(PI_AGENT_DIR,"auth.json"),
    modelsPath:path.join(PI_AGENT_DIR,"models.json"),
    allowModelNetwork:false
  });
}
// A successful Pi login means Pi saved/configured the credential. It does
// NOT mean the upstream API key passed a real inference request. No duplicate
// credential store, test prompt, custom validator, or provider account ledger.
function refreshNativeCatalog() {
  piInventoryRevision++;
  modelsSnapshots.clear();
  // Commands are installed Pi skills/extensions, not provider credentials;
  // login/logout must not invent or alter the agent/skill inventory.
  nativeDiscoveryPending=null;
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
        if(x.type==="agent_settled"){this.active=false;releaseExecution(this);}
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
    this.child.kill("SIGTERM");releaseExecution(this);pool.delete(this.id);
  }
}
async function agent(s) {
  const id=projectIdFor(s);
  let a=pool.get(id);
  if(a && !a.closed)return a;
  // An idle Pi RPC worker can be closed without touching its native
  // conversation files. Reopen it when that project is selected again.
  if(pool.size>=MAX_PROCS){
    const idle=[...pool.values()].filter(p=>!p.closed&&!p.active&&!p.busy&&!executing.has(p))
      .sort((a,b)=>a.last-b.last)[0];
    if(idle)idle.close();
  }
  if(pool.size>=MAX_PROCS)
    throw Object.assign(new Error("Every Pi worker is currently executing; retry shortly"),{status:503});
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
// Existing project-file explorer transport. File contents are workspace data,
// not a second coding agent or Python file processor. The Pi agent itself uses
// its installed native read/edit/write/bash tools during conversations.
function workspaceFile(scope,relative,allowRoot=false) {
  if(typeof relative!=="string"||relative.length>1000||relative.includes("\\")
    ||relative.includes("\0")||relative.startsWith("/")
    ||relative.split("/").some(p=>p===".."||p===".git"||p===".ssh"
      ||p===".pi"||p.startsWith(".env")||p==="auth.json"))
    throw Object.assign(new Error("Invalid project file path"),{status:400});
  const root=realpathSync(scope.directory);
  const target=path.resolve(root,relative||".");
  if(target!==root&&!target.startsWith(root+path.sep))
    throw Object.assign(new Error("Project file outside workspace"),{status:403});
  if(target===root&&!allowRoot)
    throw Object.assign(new Error("Specify a project file"),{status:400});
  let file;
  try{file=realpathSync(target);}catch(e){
    if(e.code==="ENOENT")throw Object.assign(new Error("Project file not found"),{status:404});
    throw e;
  }
  if(file!==root&&!file.startsWith(root+path.sep))
    throw Object.assign(new Error("Project file outside workspace"),{status:403});
  return file;
}
function projectFileRequest(scope,pathname,query) {
  const relative=query.get("path")||"";
  if(pathname==="/file"){
    const dir=workspaceFile(scope,relative,true);
    if(!lstatSync(dir).isDirectory())
      throw Object.assign(new Error("Not a project directory"),{status:404});
    return readdirSync(dir,{withFileTypes:true})
      .filter(x=>!x.isSymbolicLink()&&![".git",".ssh",".pi","auth.json"].includes(x.name)
        &&!x.name.startsWith(".env"))
      .slice(0,2000).map(x=>({name:x.name,
        path:[relative,x.name].filter(Boolean).join("/"),
        type:x.isDirectory()?"directory":"file"}));
  }
  if(pathname==="/file/content"){
    const file=workspaceFile(scope,relative);
    if(!lstatSync(file).isFile())
      throw Object.assign(new Error("Not a regular project file"),{status:404});
    if(lstatSync(file).size>1024*1024)
      throw Object.assign(new Error("File exceeds 1 MB preview limit"),{status:413});
    const data=readFileSync(file);
    if(data.includes(0))throw Object.assign(new Error("Binary file cannot be previewed as text"),{status:415});
    return {content:new TextDecoder("utf-8",{fatal:true}).decode(data)};
  }
  // Read-only Git information for the existing project panel; model edits and
  // shell commands still execute with Pi's native tools, never this route.
  const git=(args)=>execFileSync("git",args,{cwd:scope.directory,encoding:"utf8",
    timeout:8000,maxBuffer:1024*1024,stdio:["ignore","pipe","ignore"]}).trim();
  if(pathname==="/vcs"){
    try{return {branch:git(["branch","--show-current"])};}catch{return {branch:""};}
  }
  if(pathname==="/file/status"){
    try{
      const output=git(["status","--porcelain=v1","-uno"]);
      return output.split("\n").filter(Boolean).map(line=>({
        status:line.slice(0,2).trim()||"modified",
        path:line.slice(3).replace(/^"(.*)"$/,"$1")
      }));
    }catch{return [];}
  }
  throw Object.assign(new Error("Unsupported project file operation"),{status:404});
}
function mapped(messages, id) {
  return messages.map((m,index)=>{
    const text=Array.isArray(m.content) ? m.content.filter(x=>x.type==="text").map(x=>x.text||"").join("\n"):typeof m.content==="string"?m.content:"";
    const mid="msg_"+createHash("sha256").update(id+":"+index).digest("hex").slice(0,24);
    return {info:{id:mid,sessionID:id,role:m.role==="assistant"?"assistant":m.role==="user"?"user":"tool",time:{created:Date.now()}},
      parts:[{id:"part_"+mid,messageID:mid,sessionID:id,type:"text",text}]};
  });
}

function providerCatalog(models,userId,availableProviders=[],providerDefinitions=[],providerStates={},piAvailableModels=[]){
  // Pi model availability is not authentication. A model in the catalog must
  // NEVER imply that an account has an API key or a verified connection.
  const grouped=new Map();
  for(const model of models){
    if(!model || typeof model.id!=="string" || typeof model.provider!=="string")continue;
    const id=model.provider;
    // The Pi provider named "opencode" (if listed) is a model source,
    // not the retired standalone OpenCode coding engine.
    let row=grouped.get(id);
    if(!row){row={id,name:id,models:{}};grouped.set(id,row);}
    row.models[model.id]={id:model.id,name:model.name||model.id,reasoning:Boolean(model.reasoning),
      context:model.contextWindow,maxTokens:model.maxTokens,cost:model.cost||null};
  }
  // Provider registry comes from installed Pi, including providers without a key.
  for(const provider of providerDefinitions){
    if(!provider?.id||typeof provider.id!=="string")continue;
    const row=grouped.get(provider.id);
    if(row)row.name=provider.name||row.name;
    else grouped.set(provider.id,{id:provider.id,name:provider.name||provider.id,models:{}});
  }
  // Only installed Pi can report configuration and model availability.
  // Neither saved credentials nor getAvailableSnapshot proves remaining credits.
  const nativeModels=new Set(piAvailableModels);
  const available=new Set(availableProviders);
  const all=[...grouped.values()].map(row=>{
    const state=providerStates[row.id]||{};
    const modelIDs=Object.keys(row.models||{});
    return {...row,configured:available.has(row.id),
      credential_source:state.source||"none",
      credential_stored:state.stored===true,
      pi_available_models:modelIDs.filter(id=>nativeModels.has(row.id+"\0"+id)),
      credit_status:"unknown",verified:false};
  });
  // Exact provider IDs only. A DeepSeek model under OpenRouter is not
  // a direct DeepSeek provider connection.
  const connected=all.filter(row=>row.configured).map(row=>row.id);
  return {all,connected,default:{}};
}
async function nativeDiscovery(userId) {
  const cached=modelsSnapshots.get(userId);
  if(cached&&Date.now()-cached.time<CATALOG_TTL_MS)return cached;
  if(nativeDiscoveryPending)return nativeDiscoveryPending;
  // Provider and credential lookup is native Pi SDK ONLY. It never waits for
  // session, agent, extension, or prompt-template discovery.
  const revision=piInventoryRevision;
  const pending=(async()=>{
    const runtime=await piModels();
    const models=runtime.getModels();
    const providers=runtime.getProviders().map(provider=>({
      id:provider.id,name:provider.name||provider.id,
      auth_methods:[
        ...(provider.auth?.apiKey?.login?["apiKey"]:[]),
        ...(provider.auth?.oauth?.login?["oauth"]:[])
      ]
    }));
    if(!Array.isArray(models)||!Array.isArray(providers)||!providers.length)
      throw Object.assign(new Error("Installed Pi provider registry is unavailable"),{status:502});
    const credentials=await runtime.listCredentials();
    const stored=new Set(credentials.map(row=>row.providerId));
    const providerStates=Object.fromEntries(providers.map(p=>{
      const status=runtime.getProviderAuthStatus(p.id);
      return [p.id,{configured:status.configured===true,
        stored:stored.has(p.id),source:status.source||"none"}];
    }));
    const availableProviders=providers.filter(p=>providerStates[p.id].configured).map(p=>p.id);
    // Pi's "available" means credentials/model access as reported by Pi,
    // never verified account credits or a successful completion.
    const piAvailableModels=runtime.getAvailableSnapshot()
      .filter(m=>m?.provider&&m?.id).map(m=>m.provider+"\0"+m.id);
    if(revision!==piInventoryRevision)
      throw Object.assign(new Error("Pi provider state changed; refresh"),{status:409});
    const value={models,availableProviders,providers,providerStates,
      piAvailableModels,time:Date.now()};
    modelsSnapshots.set(userId,value);
    return value;
  })();
  nativeDiscoveryPending=pending;
  try{return await pending;}finally{if(nativeDiscoveryPending===pending)nativeDiscoveryPending=null;}
}
async function nativeCommandDiscovery(userId){
  const cached=commandsSnapshots.get(userId);
  if(cached&&Date.now()-cached.time<CATALOG_TTL_MS)return cached.commands;
  if(nativeCommandsPending)return nativeCommandsPending;
  // Commands/skills belong to Pi RPC; independent of provider logins.
  const pending=(async()=>{
    const a=new Agent({directory:CATALOG_DIRECTORY,workspaceId:"catalog",
      projectId:"catalog",userId,catalog:true});
    try{
      const response=await a.command("get_commands");
      if(!Array.isArray(response?.commands))
        throw Object.assign(new Error("Pi command registry did not respond"),{status:502});
      commandsSnapshots.set(userId,{commands:response.commands,time:Date.now()});
      return response.commands;
    }finally{a.close();}
  })();
  nativeCommandsPending=pending;
  try{return await pending;}finally{if(nativeCommandsPending===pending)nativeCommandsPending=null;}
}
function nativeCommands(commands) {
  return commands.filter(c=>c&&typeof c.name==="string"
    &&/^[a-zA-Z0-9_][a-zA-Z0-9_.:-]{0,119}$/.test(c.name)
    &&["extension","skill","prompt"].includes(c.source))
    .map(c=>({name:c.name,mode:"primary",hidden:false,
      source:c.source,description:String(c.description||"").slice(0,400)}));
}
const server=http.createServer(async(req,res)=>{
  try{
    const {pathname,query}=cleanPath(req.url||"/");
    if(pathname==="/health" && req.method==="GET")return json(res,200,{service:"pi-central",status:"ready",activeWorkers:pool.size,maxWorkers:MAX_PROCS,activeExecutions:executing.size,maxActiveExecutions:MAX_ACTIVE_EXECUTIONS});
    if(!["GET","POST","PATCH","PUT","DELETE"].includes(req.method))return error(res,405,"Method not allowed");
    const s=await scope(req,query);
    if(s.catalog){
      if(pathname==="/provider"&&req.method==="GET") {
        const native=await nativeDiscovery(s.userId);
        return json(res,200,providerCatalog(native.models,s.userId,native.availableProviders,
          native.providers,native.providerStates,native.piAvailableModels));
      }
      // Pi's registered extension/skill/prompt commands are its discoverable
      // capabilities. Do not invent "build", "plan" or other agents.
      if(pathname==="/agent"&&req.method==="GET") {
        const commands=await nativeCommandDiscovery(s.userId);
        return json(res,200,nativeCommands(commands));
      }
      if(pathname==="/provider/auth"&&req.method==="GET"){
        const discovered=await nativeDiscovery(s.userId);
        const methods={};
        for(const p of discovered.providers)
          methods[p.id]=[
            ...(p.auth_methods.includes("apiKey")?[{type:"api",label:"Pi API key"}]:[]),
            ...(p.auth_methods.includes("oauth")?[{type:"oauth",label:"Pi account sign-in"}]:[])
          ];
        return json(res,200,methods);
      }
      const auth=pathname.match(/^\/auth\/([a-zA-Z0-9._-]{1,120})$/);
      if(auth&&["PUT","DELETE"].includes(req.method)){
        const providerId=auth[1];
        // This is the same installed ModelRuntime invoked by Pi's terminal
        // "auth login" / "auth logout"; Pi alone persists credentials.
        const runtime=await piModels();
        const provider=runtime.getProvider(providerId);
        if(!provider)return error(res,404,"Provider is not registered in installed Pi");
        if(req.method==="PUT"){
          const payload=await body(req);
          if(payload?.type!=="api"||typeof payload.key!=="string"||
             !payload.key.trim()||payload.key.length>8192)
            return error(res,422,"API key required");
          if(!provider.auth?.apiKey?.login)
            return error(res,422,"This Pi provider has no native API-key login");
          // Do not claim remote key validation or reject a provider because
          // an unrelated provider exposes a similarly named model.
          if(runtime.getProviderAuthStatus(providerId).configured)
            return error(res,409,"Pi reports this provider is already configured");
          const key=payload.key.trim();
          await runtime.login(providerId,"api_key",{
            signal:AbortSignal.timeout(30000),
            prompt:async question=>{
              if(question.type==="secret"||question.type==="text")return key;
              throw Object.assign(new Error("Pi login requires an unsupported interactive step"),{status:422});
            },
            notify:()=>{}
          });
          refreshNativeCatalog();
          // Read Pi's own persisted credential state after its login resolves.
          // No custom key validator, request to the provider, or local record.
          const confirmed=await piModels();
          const saved=await confirmed.listCredentials();
          if(!saved.some(item=>item.providerId===providerId)||
             !confirmed.getProviderAuthStatus(providerId).configured)
            return error(res,502,"Pi login returned but Pi did not confirm saved credentials");
          return json(res,200,{provider:providerId,configured:true,verified:false,source:"pi"});
        }
        await runtime.logout(providerId);
        refreshNativeCatalog();
        const confirmed=await piModels();
        const saved=await confirmed.listCredentials();
        if(saved.some(item=>item.providerId===providerId))
          return error(res,502,"Pi logout returned but Pi still reports stored credentials");
        // Pi may continue to use an environment/model-config key after logout.
        return json(res,200,{provider:providerId,
          configured:confirmed.getProviderAuthStatus(providerId).configured,
          credentialRemoved:true,source:"pi"});
      }
      return error(res,404,"Pi account endpoint not found");
    }
    // File tree reads should not consume an agent process or compete with a
    // running Pi conversation for RPC worker slots.
    if(req.method==="GET"&&["/file","/file/content","/file/status","/vcs"].includes(pathname))
      return json(res,200,projectFileRequest(s,pathname,query));
    const a=await agent(s);
    if(pathname==="/agent"&&req.method==="GET") {
      const native=await a.command("get_commands");
      return json(res,200,nativeCommands(native?.commands||[]));
    }
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
      reserveExecution(a);
      try {
        if(b.model?.providerID&&b.model?.modelID)
          await a.command("set_model",{provider:b.model.providerID,modelId:b.model.modelID});
        // Keep the original Pi command/skill mechanism. Do not invent agents.
        let prompt=message;
        if(b.agent) {
          const commands=await a.command("get_commands");
          const command=(commands?.commands||[]).find(c=>c?.name===b.agent);
          if(!command) {
            releaseExecution(a);
            return error(res,422,"Selected Pi capability is no longer installed");
          }
          prompt="/"+command.name+(message.trim()?" "+message:"");
        }
        const accepted=await a.command("prompt",{message:prompt,...(images.length?{images}:{})});
        // Pi can consume an extension command without starting a model run.
        // A started/queued prompt stays reserved until agent_settled or exit.
        if(accepted?.disposition==="handled")releaseExecution(a);
        res.writeHead(204,{"cache-control":"no-store"});res.end();return;
      } catch(e) {
        // Never release an actively running request just because its RPC ack
        // was lost; agent_settled/exit owns that release.
        if(!a.active)releaseExecution(a);
        throw e;
      }
    }
    if(action==="abort" && req.method==="POST"){await a.command("abort",{},30000);return json(res,200,true);}
    return error(res,501,"Pi operation not implemented");
  }catch(e){return error(res,e.status||502,e.message||"Pi adapter error");}
});
server.on("clientError",(_,s)=>s.end("HTTP/1.1 400 Bad Request\r\n\r\n"));
mkdirSync(path.dirname(SOCK),{recursive:true,mode:0o700});
if(existsSync(SOCK))unlinkSync(SOCK);
server.listen(SOCK,()=>{chmodSync(SOCK,0o660);console.log("Pi TEST bridge on UNIX socket");});
setInterval(()=>{for(const a of pool.values())if(!a.active&&!executing.has(a)&&!a.events.size&&Date.now()-a.last>IDLE_MS)a.close();},60000).unref();
process.on("SIGTERM",()=>{server.close();for(const a of pool.values())a.close();});
