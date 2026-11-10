/**
 * Pi Central ↔ existing OpenCode-shaped TEST browser transport.
 * TEST ONLY. Pi is the only coding/provider engine; platform lookups only protect project files.
 * Existing bridge/socket only. Gateway owns customer provider connections;
 * Pi SDK executes using per-project in-memory credentials.
 * Workspace execution tools require project process isolation before activation.
 *
 * Run under systemd, same UID as installed Pi. Do not expose on TCP.
 * Nginx must proxy /native-direct/api/ to this UNIX socket, stripping prefix.
 */
import http from "node:http";
import { spawn, execFileSync } from "node:child_process";
import { createHash, randomUUID, timingSafeEqual } from "node:crypto";
import { mkdirSync, chmodSync, existsSync, unlinkSync, readFileSync, writeFileSync, readdirSync, lstatSync, realpathSync } from "node:fs";
import path from "node:path";
import { URL } from "node:url";

const PI = process.env.PI_BINARY || "/home/tahir/pi-test/node_modules/.bin/pi";
const SOCK = process.env.PI_SOCKET || "/run/pi-central/pi.sock";
const ROOT = process.env.PI_SESSIONS_ROOT || "/home/tahir/pi-test/sessions";
const PI_AGENT_DIR = process.env.PI_CODING_AGENT_DIR || "/home/tahir/.pi/agent";
const GATEWAY = process.env.PI_TEST_GATEWAY || "http://127.0.0.1:8001";
const HOST = "test.opencode-gateway.codes";
// Runtime credentials MUST originate from Gateway, not service environment.
// Strip provider key fallbacks before creating Pi SDK model runtimes. Keep
// PI_GATEWAY_INTERNAL_TOKEN untouched (it authenticates internal fetch only).
for(const name of [
  "OPENROUTER_API_KEY","DEEPSEEK_API_KEY","OPENAI_API_KEY","ANTHROPIC_API_KEY",
  "GOOGLE_API_KEY","GEMINI_API_KEY","GROQ_API_KEY","MISTRAL_API_KEY",
  "XAI_API_KEY","TOGETHER_API_KEY","CEREBRAS_API_KEY",
  "FIREWORKS_API_KEY","MOONSHOT_API_KEY","ZAI_API_KEY"
])delete process.env[name];
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
const creating = new Map(); // coalesce concurrent SDK session initialization
const CATALOG_DIRECTORY="/home/tahir/pi-test";
const CATALOG_TTL_MS=60_000;
const modelsSnapshots=new Map();
const commandsSnapshots=new Map();
let nativeDiscoveryPending=null;
let nativeCommandsPending=null;

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
  if(directory===CATALOG_DIRECTORY){
    // The catalog may be called by an authenticated browser or the already
    // existing Gateway maintenance worker. No anonymous discovery.
    const cookie=req.headers.cookie||"";
    if(cookie){
      await gateway(req,"/api/auth/me");
    }else{
      const expected=process.env.PI_GATEWAY_INTERNAL_TOKEN||"";
      const candidate=String(req.headers["x-pi-gateway-token"]||"");
      if(expected.length<32||candidate.length!==expected.length||
         !timingSafeEqual(Buffer.from(expected),Buffer.from(candidate)))
        throw Object.assign(new Error("Gateway catalog authorization required"),{status:401});
    }
    return {catalog:true,userId:"shared"};
  }
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
  // Owner-only TEST tooling is opt-in. Never turn a service-wide toggle into
  // shell/tool access for every account on this shared-UID VPS.
  let testOwner=false;
  if(process.env.PI_TEST_SINGLE_OWNER_TOOLS==="1"){
    const identity=await gateway(req,"/api/auth/me");
    testOwner=identity?.role==="owner"&&String(identity.id)===match[1];
  }
  return {directory,workspaceId:match[2],projectId:String(detail.project_id),userId:match[1],testOwner};
}
// Read only public model definitions. Provider metadata must NEVER open the
// shared auth.json or inspect credentials belonging to the VPS operator.
async function piModels() {
  const {ModelRuntime}=await import("@earendil-works/pi-coding-agent");
  const {InMemoryCredentialStore}=await import("@earendil-works/pi-ai");
  if(!ModelRuntime?.create||!InMemoryCredentialStore)
    throw Object.assign(new Error("Installed Pi catalog API is unavailable"),{status:502});
  return ModelRuntime.create({
    credentials:new InMemoryCredentialStore(),
    modelsPath:path.join(PI_AGENT_DIR,"models.json"),
    allowModelNetwork:false
  });
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

// In-process Pi SDK session: one isolated, in-memory credential runtime per
// project, keeping the existing bridge/socket/routes and persistent Pi JSONL.
class SdkAgent {
  static async create(scope) {
    const sdk=await import("@earendil-works/pi-coding-agent");
    const ai=await import("@earendil-works/pi-ai");
    if(!sdk.ModelRuntime?.create||!sdk.createAgentSession||
       !sdk.SessionManager?.create||!sdk.SessionManager?.list||!ai.InMemoryCredentialStore)
      throw Object.assign(new Error("Installed Pi SDK lacks isolated runtime/session APIs"),{status:503});
    // Credentials and settings are not read from the shared Pi auth.json.
    const runtime=await sdk.ModelRuntime.create({
      credentials:new ai.InMemoryCredentialStore(),modelsPath:null,allowModelNetwork:false
    });
    const sessionDir=path.join(ROOT,"projects",scope.userId,scope.workspaceId);
    mkdirSync(sessionDir,{recursive:true,mode:0o700});
    // Never restore an unrelated older conversation or silently replace a
    // project session after loss of its JSONL file.
    const expectedId=projectIdFor(scope);
    const existing=await sdk.SessionManager.list(scope.directory,sessionDir);
    const exact=existing.find(item=>item.id===expectedId);
    if(!exact&&existing.length)
      throw Object.assign(new Error("Existing Pi session requires deliberate recovery; not creating another"),{status:409});
    const manager=exact?sdk.SessionManager.open(exact.path,sessionDir):
      sdk.SessionManager.create(scope.directory,sessionDir,{id:expectedId});
    const allowTools=scope.testOwner===true;
    const {session}=await sdk.createAgentSession({
      cwd:scope.directory,modelRuntime:runtime,sessionManager:manager,
      settingsManager:sdk.SettingsManager.inMemory(),
      tools:allowTools?["read","bash","edit","write","grep","find","ls"]:[],
      noExtensions:!allowTools,noSkills:!allowTools
    });
    return new SdkAgent(scope,session,runtime);
  }
  constructor(scope,session,runtime){
    this.scope=scope;this.id=projectIdFor(scope);this.title=scope.projectId;
    this.session=session;this.runtime=runtime;
    this.events=new Set();this.busy=false;this.active=false;this.closed=false;
    this.last=Date.now();this.running=null;this.credentialProvider=null;this.settledObserved=false;
    this.unsub=session.subscribe(event=>this.consume(event));
  }
  consume(event){
    if(this.closed)return;
    this.last=Date.now();
    if(event.type==="agent_start")this.active=true;
    if(event.type==="agent_settled"){this.active=false;this.settledObserved=true;}
    const serialized=JSON.stringify({type:"pi."+event.type,properties:event});
    for(const res of this.events)try{res.write("data: "+serialized+"\n\n");}catch{this.events.delete(res);}
    if(event.type==="agent_settled"){
      const now=Date.now();
      for(const res of this.events)try{
        res.write("data: "+JSON.stringify({type:"message.updated",
          properties:{info:{id:"pi-refresh-"+now,sessionID:this.id,role:"assistant",
          time:{created:now}}}})+"\n\n");
        res.write("data: "+JSON.stringify({type:"session.idle",
          properties:{sessionID:this.id}})+"\n\n");
      }catch{}
    }
  }
  async setCredential(provider,key){
    if(this.closed)throw Object.assign(new Error("Pi session ended"),{status:503});
    if(this.credentialProvider && this.credentialProvider!==provider)
      await this.runtime.removeRuntimeApiKey(this.credentialProvider);
    await this.runtime.setRuntimeApiKey(provider,key);
    this.credentialProvider=provider;
  }
  async clearCredential(){
    const provider=this.credentialProvider;
    this.credentialProvider=null;
    if(provider)await this.runtime.removeRuntimeApiKey(provider);
  }
  async command(type,fields={}){
    if(this.closed)throw Object.assign(new Error("Pi session ended"),{status:503});
    this.last=Date.now();
    if(type==="get_state")return {sessionId:this.id,messageCount:this.session.messages.length};
    if(type==="get_messages")return {messages:this.session.messages};
    if(type==="get_commands")return {commands:await nativeCommandDiscovery(this.scope.userId)};
    if(type==="set_model"){
      const model=this.runtime.getModel(fields.provider,fields.modelId);
      if(!model)throw Object.assign(new Error("Selected provider/model not in installed Pi runtime"),{status:422});
      await this.session.setModel(model);
      return {};
    }
    if(type==="abort"){await this.session.abort();return {};}
    if(type!=="prompt")throw Object.assign(new Error("Unsupported Pi SDK command"),{status:501});
    if(this.active||this.running)
      throw Object.assign(new Error("Project already has an active Pi run"),{status:409});
    // Pi SDK prompt() resolves when the full run finishes. Its documented
    // preflightResult(true) confirms prompt acceptance BEFORE model completion.
    const images=Array.isArray(fields.images)?fields.images:[];
    this.settledObserved=false;
    let admissionResolve,admissionReject,admitted=false;
    const admission=new Promise((resolve,reject)=>{
      admissionResolve=resolve;admissionReject=reject;
    });
    const completeAdmission=(accepted)=>{
      if(admitted)return;
      admitted=true;
      if(accepted)admissionResolve();
      else admissionReject(Object.assign(
        new Error("Pi did not accept the prompt"),{status:422}));
    };
    const run=Promise.resolve().then(()=>this.session.prompt(fields.message,{
      ...(images.length?{images}:{}),
      preflightResult:completeAdmission
    }));
    this.running=run;
    run.then(()=>completeAdmission(true)).catch(()=>{
      completeAdmission(false);
      for(const res of this.events)try{res.write("data: "+JSON.stringify({
        type:"pi.error",properties:{message:"Pi execution failed"}
      })+"\n\n");}catch{this.events.delete(res);}
    }).finally(async()=>{
      // Once Pi settles, promptly erase the customer's runtime API override.
      // Capacity stays reserved until the removal completes.
      try{await this.clearCredential();}
      catch{this.close();}
      this.running=null;this.active=false;releaseExecution(this);
      if(!this.closed&&!this.settledObserved)this.consume({type:"agent_settled"});
    }).catch(()=>{});
    await admission;
    return {accepted:true};
  }
  close(){
    if(this.closed)return;this.closed=true;
    releaseExecution(this);
    try{this.unsub?.();}catch{}
    try{this.session.dispose();}catch{}
    for(const res of this.events)try{res.end();}catch{}
    this.events.clear();pool.delete(this.id);
  }
}
async function gatewayCredential(req,scope,provider){
  const token=process.env.PI_GATEWAY_INTERNAL_TOKEN||"";
  if(token.length<32)throw Object.assign(
    new Error("Pi-Gateway internal credential channel is not configured"),{status:503});
  const cookie=req.headers.cookie||"";
  if(!cookie||cookie.length>8192)
    throw Object.assign(new Error("Authentication required"),{status:401});
  let response;
  try{
    response=await fetch(GATEWAY+"/api/opencode/connections/"+encodeURIComponent(provider)+
      "?workspace_id="+encodeURIComponent(scope.workspaceId),{
      redirect:"manual",signal:AbortSignal.timeout(6000),
      headers:{cookie,host:HOST,"x-forwarded-proto":"https",
        "x-pi-gateway-token":token,accept:"application/json"}
    });
  }catch{throw Object.assign(new Error("Gateway credentials unavailable"),{status:503});}
  if(!response.ok)throw Object.assign(
    new Error("Verified account connection unavailable"),{status:response.status===404?403:response.status});
  const data=await response.json();
  if(data.provider_id!==provider||typeof data.key!=="string"||!data.key)
    throw Object.assign(new Error("Invalid Gateway connection response"),{status:502});
  return data.key;
}
async function agent(s) {
  const id=projectIdFor(s);
  const current=pool.get(id);
  if(current&&!current.closed){
    if(current.scope.testOwner===s.testOwner)return current;
    if(current.active||current.running||executing.has(current))
      throw Object.assign(new Error("Project permissions changed during an active run"),{status:409});
    current.close(); // recreate with the updated role, no stale shell tools
  }
  const pending=creating.get(id);
  if(pending)return pending;
  // Include in-flight SDK initializations in the worker cap. Concurrent
  // file/status/prompt requests must not spawn multiple sessions for a project.
  if(pool.size+creating.size>=MAX_PROCS){
    const idle=[...pool.values()].filter(p=>!p.closed&&!p.active&&!p.busy&&!executing.has(p))
      .sort((a,b)=>a.last-b.last)[0];
    if(idle)idle.close();
  }
  if(pool.size+creating.size>=MAX_PROCS)
    throw Object.assign(new Error("Pi worker capacity reached"),{status:429});
  const creatingSession=(async()=>{
    const worker=await SdkAgent.create(s);
    pool.set(id,worker);
    try{await worker.command("get_state");return worker;}
    catch(e){worker.close();throw e;}
  })();
  creating.set(id,creatingSession);
  try{return await creatingSession;}
  finally{if(creating.get(id)===creatingSession)creating.delete(id);}
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
      images.push({type:"image",source:{type:"base64",mediaType:mime,data:match[2]}});
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

function providerCatalog(models,userId,availableProviders=[],providerDefinitions=[],providerStates={},piAvailableModels=[],modelView="full",selectedProviderId=""){
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
    const exposeModels=modelView==="full" ||
      (modelView==="connected"&&available.has(row.id)) ||
      (modelView==="provider"&&selectedProviderId===row.id);
    return {...row,model_count:modelIDs.length,
      models:exposeModels?row.models:{},
      configured:available.has(row.id),
      credential_source:state.source||"none",
      credential_stored:state.stored===true,
      pi_available_models:exposeModels?modelIDs.filter(id=>nativeModels.has(row.id+"\0"+id)):[],
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
    // Metadata only. No listCredentials(), stored auth state, or shared
    // runtime fallback is required to populate Gateway's model catalog.
    const value={models,availableProviders:[],providers,providerStates:{},
      piAvailableModels:[],time:Date.now()};
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
        // The same /provider endpoint supports compact catalog reads.
        // No extra HTTP route or additional model-registry service.
        const mode=query.get("models");
        const view=["connected","provider"].includes(mode)?mode:"full";
        const selected=view==="provider"?(query.get("providerID")||""):"";
        return json(res,200,providerCatalog(native.models,s.userId,native.availableProviders,
          native.providers,native.providerStates,native.piAvailableModels,view,selected));
      }
      // Pi's registered extension/skill/prompt commands are its discoverable
      // capabilities. Do not invent "build", "plan" or other agents.
      if(pathname==="/agent"&&req.method==="GET") {
        const commands=await nativeCommandDiscovery(s.userId);
        return json(res,200,nativeCommands(commands));
      }
      // No browser-accessible credential writes. The retired Pi-native
      // login/logout path used one shared auth.json for all TEST accounts
      // and did not validate upstream keys before saving them.
      // Keep account credentials out of Pi until Gateway-owned storage
      // and account-isolated SDK runtime have been safely implemented.
      if(pathname==="/provider/auth" || /^\/auth\//.test(pathname))
        return error(res,410,"Shared Pi credential endpoints retired. Verified account-owned connections must be managed by Gateway.");
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
      if(!b.model?.providerID||!b.model?.modelID)
        return error(res,422,"Select a verified provider and model from Gateway");
      if(b.agent&&!s.testOwner)
        return error(res,403,"Native skill and extension execution requires isolated TEST owner access");
      // Authenticate on EVERY prompt: deletions/rotations take effect before
      // another request can run. Never fall back to shared Pi credentials.
      const authorizedKey=await gatewayCredential(req,s,b.model.providerID);
      reserveExecution(a);
      try {
        try{await a.setCredential(b.model.providerID,authorizedKey);}
        catch{throw Object.assign(new Error("Pi credential injection failed"),{status:502});}
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
