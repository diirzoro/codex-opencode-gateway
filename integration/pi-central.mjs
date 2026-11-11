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
import { mkdirSync, chmodSync, existsSync, unlinkSync, readFileSync, writeFileSync, renameSync, readdirSync, lstatSync, realpathSync, rmSync, statSync } from "node:fs";
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
const PI_QUEUE_LIMIT=10;
function liveAccountExecution(userId){
  return [...executing].find(worker=>worker.scope?.userId===userId&&
    !worker.closed)||
    [...pool.values()].find(worker=>worker.scope?.userId===userId&&
      (worker.active||worker.running)&&!worker.closed)||null;
}
function projectBusyMessage(worker){
  return "لا يمكنك تشغيل مشروع آخر بينما هناك مهمة قائمة في المشروع «"+
    (worker.title||worker.scope.projectId)+"». أوقف المهمة أو انتظر اكتمالها.";
}
function reserveExecution(agent) {
  // Reserve before set_model/prompt to close the admission race.
  if(agent.active||agent.running||executing.has(agent))
    throw Object.assign(new Error("This project is already running a Pi request"),{status:409});
  const other=liveAccountExecution(agent.scope.userId);
  if(other&&other.id!==agent.id)
    throw Object.assign(new Error(projectBusyMessage(other)),{status:409});
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
function error(res, status, message, receipt) {
  json(res,status,{error:message,...(receipt==="not_submitted"?{receipt:"not_submitted"}:{})});
}
function cleanPath(uri) {
  const url = new URL(uri, "http://localhost");
  return { pathname:url.pathname.replace(/^\/native-direct\/api/,"") || "/", query:url.searchParams };
}
// Pi handles every chat, file, tool and SSE request without a Python lookup.
// Gateway hands account-owned capabilities to this existing UNIX-socket process
// once when a browser opens/renews an authenticated Pi session.
const BOOTSTRAP_HOST="pi-internal";
const PI_COOKIE="pi_test_session";
const PI_SESSION_DURATION_MS=14*60_000;
const browserGrants=new Map();
const pendingTickets=new Map();
function fromGateway(req){
  return req.headers.host===BOOTSTRAP_HOST &&
    !req.headers["x-forwarded-for"]&&!req.headers["x-real-ip"];
}
function browserPrincipal(req){
  const cookie=String(req.headers.cookie||"");
  const id=cookie.match(/(?:^|;\s*)pi_test_session=([0-9a-f-]{36})(?:;|$)/i)?.[1];
  const existing=id?browserGrants.get(id):null;
  if(!existing||existing.expires<=Date.now()){
    if(id)browserGrants.delete(id);
    throw Object.assign(new Error("Pi session expired; reopen the workspace"),{status:401});
  }
  return existing.account;
}
function issueBrowserGrant(res,account){
  const sid=randomUUID();
  browserGrants.set(sid,{account,expires:Date.now()+PI_SESSION_DURATION_MS});
  res.writeHead(204,{"set-cookie":PI_COOKIE+"="+sid+
    "; Path=/native-direct/api/; Max-Age=840; HttpOnly; Secure; SameSite=Strict",
    "cache-control":"no-store"});
  res.end();
}
function revokeBrowserGrants(userId){
  for(const [sid,grant] of browserGrants)
    if(!userId||grant.account.user_id===userId)browserGrants.delete(sid);
  for(const [ticket,entry] of pendingTickets)
    if(!userId||entry.account.user_id===userId)pendingTickets.delete(ticket);
  for(const worker of pool.values())
    if(!userId||worker.scope.userId===userId)try{worker.close();}catch{}
}
async function scope(req,query){
  const directory=query.get("directory");
  if(directory===CATALOG_DIRECTORY){
    const pathname=cleanPath(req.url||"/").pathname;
    if(pathname==="/provider"&&req.method==="GET"&&fromGateway(req))
      return {catalog:true,userId:"internal",testOwner:false};
    const account=browserPrincipal(req);
    return {catalog:true,userId:account.user_id,testOwner:
      process.env.PI_TEST_SINGLE_OWNER_TOOLS==="1"&&account.role==="owner"};
  }
  const account=browserPrincipal(req);
  if(!directory||directory.length>4096)
    throw Object.assign(new Error("Owned project directory required"),{status:400});
  const match=directory.match(/\/([0-9a-f-]{36})\/([0-9a-f-]{36})\/repo\/?$/i);
  if(!match||match[1]!==account.user_id)
    throw Object.assign(new Error("Invalid owned workspace directory"),{status:403});
  const work=(account.workspaces||[]).find(w=>w.id===match[2]&&
    w.directory===directory&&typeof w.project_id==="string");
  if(!work)throw Object.assign(new Error("Workspace not in the Pi account grant"),{status:403});
  if(!existsSync(directory)||realpathSync(directory)!==directory)
    throw Object.assign(new Error("Workspace path unavailable"),{status:404});
  return {directory,workspaceId:work.id,projectId:work.project_id,
    projectName:typeof work.project_name==="string"?
      work.project_name.slice(0,200):"",
    userId:account.user_id,account,testOwner:
    process.env.PI_TEST_SINGLE_OWNER_TOOLS==="1"&&account.role==="owner"};
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

// Official Pi extension pattern (inline, replaceable): never a second service.
// A separately installed todo tool takes precedence over this fallback.
function piTodoExtension(Type){
  return {name:"todo",replaceable:true,factory:pi=>{
    let todos=[],nextId=1;
    const snapshot=()=>todos.map(item=>({...item}));
    const recover=ctx=>{
      todos=[];nextId=1;
      for(const entry of ctx.sessionManager.getBranch()){
        if(entry.type!=="message"||entry.message?.role!=="toolResult"||
           entry.message.toolName!=="todo")continue;
        const details=entry.message.details;
        if(!Array.isArray(details?.todos))continue;
        todos=details.todos.slice(0,32).filter(x=>x&&Number.isInteger(x.id)&&
          typeof x.text==="string").map(x=>({id:x.id,text:x.text.slice(0,220),done:x.done===true}));
        nextId=Number.isInteger(details.nextId)?details.nextId:
          Math.max(0,...todos.map(x=>x.id))+1;
      }
    };
    pi.on("session_start",async(_,ctx)=>recover(ctx));
    pi.on("session_tree",async(_,ctx)=>recover(ctx));
    pi.registerTool({
      name:"todo",label:"Project Todos",
      description:"Track project implementation tasks in Pi session history. Actions: add, list, toggle, clear. Add planned steps and toggle only after real progress.",
      parameters:Type.Object({
        action:Type.Union(["add","list","toggle","clear"].map(value=>Type.Literal(value))),
        text:Type.Optional(Type.String({maxLength:220})),
        id:Type.Optional(Type.Number())
      }),
      execute:async(_callId,args)=>{
        let output="No changes";
        switch(args.action){
          case "add":{
            const text=String(args.text||"").trim();
            if(!text||text.length>220||todos.length>=32){output="Todo text missing or limit reached";break;}
            const item={id:nextId++,text,done:false};todos.push(item);
            output="Added task #"+item.id;break;
          }
          case "toggle":{
            const item=todos.find(x=>x.id===args.id);
            if(!item){output="Task not found";break;}
            item.done=!item.done;output="Task #"+item.id+(item.done?" completed":" reopened");
            break;
          }
          case "clear":todos=[];nextId=1;output="Cleared tasks";break;
          case "list":output=todos.length+" project tasks";break;
        }
        return {content:[{type:"text",text:output}],
          details:{action:args.action,todos:snapshot(),nextId}};
      }
    });
  }};
}
// In-process Pi SDK session: one isolated, in-memory credential runtime per
// project, keeping the existing bridge/socket/routes and persistent Pi JSONL.
class SdkAgent {
  static async create(scope) {
    const sdk=await import("@earendil-works/pi-coding-agent");
    const ai=await import("@earendil-works/pi-ai");
    if(!sdk.ModelRuntime?.create||!sdk.createAgentSession||
       !sdk.SessionManager?.create||!sdk.SessionManager?.list||!sdk.DefaultResourceLoader||!ai.InMemoryCredentialStore)
      throw Object.assign(new Error("Installed Pi SDK lacks isolated runtime/session APIs"),{status:503});
    // Credentials and settings are not read from the shared Pi auth.json.
    const runtime=await sdk.ModelRuntime.create({
      credentials:new ai.InMemoryCredentialStore(),modelsPath:null,allowModelNetwork:false
    });
    const sessionDir=path.join(ROOT,"projects",scope.userId,scope.workspaceId);
    mkdirSync(sessionDir,{recursive:true,mode:0o700});
    // This directory belongs to exactly one Gateway project workspace.
    // The SDK does not accept a custom "id" argument to create(), and
    // open() takes only the native session path. Keep the external Gateway
    // session id deterministic while Pi persists its own native JSONL id.
    const existing=await sdk.SessionManager.list(scope.directory,sessionDir);
    if(existing.length>1)
      throw Object.assign(new Error("Multiple native project sessions require deliberate recovery"),{status:409});
    if(!existing.length && readdirSync(sessionDir).some(name=>name.endsWith(".jsonl")))
      throw Object.assign(new Error("Existing Pi history could not be indexed; recovery required"),{status:409});
    const manager=existing.length?
      sdk.SessionManager.open(existing[0].path):
      sdk.SessionManager.create(scope.directory,sessionDir);
    // Use the complete existing Pi installation for every account.
    // Pi SDK remains the only agent, tool, skill and extension executor.
    const settingsManager=sdk.SettingsManager.inMemory();
    // Reuse installed todo extensions where present. Otherwise load the
    // replacement-friendly Pi extension with native session tool results.
    let todoFallback=[];
    try{
      const {Type}=await import("typebox");
      if(Type?.Object&&Type?.Literal)
        todoFallback=[piTodoExtension(Type)];
    }catch{/* Keep existing Pi SDK tools if typebox is unavailable. */}
    const resourceLoader=new sdk.DefaultResourceLoader({
      extensionFactories:todoFallback,
      cwd:scope.directory,agentDir:PI_AGENT_DIR,settingsManager,
      // appendSystemPrompt is supported by the installed Pi ResourceLoader.
      // The previous systemPromptOverride setting was not applied by Pi SDK.
      appendSystemPrompt:[
        "Current authenticated project name: "+
          (scope.projectName||"not provided")+".\n"+
        "Current project directory: "+scope.directory+".\n"+
        "If asked for the current project name, answer from the name above "+
        "without running read, bash, ls, or filesystem discovery. If the name "+
        "was not provided, say so instead of searching for it.\n"+
        "Use Pi tools only for work that requires them. Do not repeat failed "+
        "tool calls with the same arguments indefinitely. "+
        "Never simulate tool execution or claim files were created without "+
        "a successful tool result. Report relative paths within this project. "+
        "For multi-step work, use the installed Pi todo tool when available."
      ],
      noExtensions:false,noSkills:false,
      noPromptTemplates:false,noContextFiles:false
    });
    await resourceLoader.reload();
    const {session}=await sdk.createAgentSession({
      cwd:scope.directory,agentDir:PI_AGENT_DIR,
      modelRuntime:runtime,sessionManager:manager,settingsManager,
      resourceLoader,noTools:false
    });
    // Activate every tool already registered in Pi, including the seven
    // built-ins and installed extension tools. No new tools or APIs are added.
    if(typeof session.getAllTools==="function"&&
       typeof session.setActiveToolsByName==="function")
      session.setActiveToolsByName(session.getAllTools().map(tool=>tool.name));
    const agent=new SdkAgent(scope,session,runtime);
    // Bind the SDK's existing extension UI channel to the same Pi session.
    // Dialog requests are handled by the existing Workspace question form.
    try{
      if(typeof session.bindExtensions==="function")
        await session.bindExtensions({mode:"rpc",uiContext:agent.extensionUI()});
    }catch(e){agent.close();throw e;}
    return agent;
  }
  constructor(scope,session,runtime){
    this.scope=scope;this.id=projectIdFor(scope);
    this.title=scope.projectName||scope.projectId;
    this.session=session;this.runtime=runtime;
    this.events=new Set();this.busy=false;this.active=false;this.closed=false;
    this.last=Date.now();this.running=null;this.runningModel=null;
    this.credentialProvider=null;this.settledObserved=false;
    this.keepQueueOnStop=false;this.queueContinuationActive=false;
    this.uiRequests=new Map();this.uiWidgets=new Map();
    this.unsub=session.subscribe(event=>this.consume(event));
  }
  emitUI(type,properties={}){
    const line="data: "+JSON.stringify({type:"pi."+type,properties})+"\n\n";
    for(const response of this.events)try{response.write(line);}catch{this.events.delete(response);}
  }
  async askUI(kind,title,options=[],opts={}){
    if(this.closed)return kind==="confirm"?false:undefined;
    const choices=Array.isArray(options)?options.filter(x=>typeof x==="string")
      .slice(0,24).map(x=>x.slice(0,200)):[];
    const timeout=Math.min(300000,Math.max(1000,Number(opts?.timeout)||300000));
    return new Promise(resolve=>{
      const id=randomUUID();
      const request={id,sessionID:this.id,kind,
        questions:[{header:String(title||"Pi needs your input").slice(0,200),
          question:String(title||"Choose an option").slice(0,300),
          options:choices.map(label=>({label})),multiple:false,
          custom:kind==="input"||kind==="editor",
          placeholder:String(opts?.placeholder||"").slice(0,200)}]};
      let done=false;
      const finish=value=>{
        if(done)return;done=true;this.uiRequests.delete(id);
        clearTimeout(timer);opts?.signal?.removeEventListener("abort",aborted);
        resolve(value);
        this.emitUI("ui_question_closed",{id});
      };
      const aborted=()=>finish(kind==="confirm"?false:undefined);
      const timer=setTimeout(aborted,timeout);
      if(opts?.signal?.aborted){aborted();return;}
      opts?.signal?.addEventListener("abort",aborted,{once:true});
      request.answer=payload=>{
        if(payload?.reject){finish(kind==="confirm"?false:undefined);return;}
        const answers=payload?.answers;
        if(!Array.isArray(answers)||!Array.isArray(answers[0]))
          throw Object.assign(new Error("Choose an answer first"),{status:422});
        const chosen=String(answers[0][0]??"").trim().slice(0,2000);
        if(kind==="select"&&!choices.includes(chosen))
          throw Object.assign(new Error("Invalid Pi option"),{status:422});
        if(kind==="confirm"&&!["Yes","No"].includes(chosen))
          throw Object.assign(new Error("Invalid Pi confirmation"),{status:422});
        if((kind==="input"||kind==="editor")&&!chosen)
          throw Object.assign(new Error("A response is required"),{status:422});
        finish(kind==="confirm"?chosen==="Yes":chosen);
      };
      this.uiRequests.set(id,request);
      this.emitUI("ui_question",{id});
    });
  }
  extensionUI(){
    const ignore=()=>{};
    const self=this;
    return {
      select:(title,options,opts)=>self.askUI("select",title,options,opts),
      confirm:(title,message,opts)=>self.askUI("confirm",
        String(title||"Confirmation")+": "+String(message||""),["Yes","No"],opts),
      input:(title,placeholder,opts)=>self.askUI("input",title,[],{...opts,placeholder}),
      editor:(title,prefill)=>self.askUI("editor",title,[],{placeholder:prefill}),
      notify:(message,type)=>self.emitUI("ui_notice",{
        text:String(message||"").slice(0,500),level:String(type||"info")}),
      setWidget:(key,content,options)=>{
        if(typeof key!=="string"||key.length>80)return;
        const lines=Array.isArray(content)?content.filter(x=>typeof x==="string")
          .slice(0,40).map(x=>x.replace(/\x1b\[[0-9;]*m/g,"").slice(0,260)):[];
        if(lines.length)self.uiWidgets.set(key,lines);else self.uiWidgets.delete(key);
        self.emitUI("ui_widget",{key,lines,placement:options?.placement||"aboveEditor"});
      },
      setStatus:(key,message)=>self.emitUI("ui_status",{
        key:String(key||"").slice(0,80),text:String(message||"").slice(0,300)}),
      setWorkingMessage:ignore,setWorkingVisible:ignore,setWorkingIndicator:ignore,
      setHiddenThinkingLabel:ignore,setFooter:ignore,setHeader:ignore,setTitle:ignore,
      onTerminalInput:()=>ignore,pasteToEditor:ignore,setEditorText:ignore,
      getEditorText:()=>"",addAutocompleteProvider:ignore,setEditorComponent:ignore,
      getEditorComponent:()=>undefined,
      get theme(){return undefined;},getAllThemes:()=>[],getTheme:()=>undefined,
      setTheme:()=>({success:false,error:"Web theme is managed by Workspace"}),
      getToolsExpanded:()=>false,setToolsExpanded:ignore,
      custom:async()=>undefined
    };
  }
  pendingUI(){
    return [...this.uiRequests.values()].map(({id,sessionID,questions})=>({id,sessionID,questions}));
  }
  respondUI(id,payload){
    const request=this.uiRequests.get(id);
    if(!request)throw Object.assign(new Error("Pi question expired"),{status:404});
    request.answer(payload);return {answered:true};
  }
  consume(event){
    if(this.closed)return;
    this.last=Date.now();
    if(event.type==="agent_start")this.active=true;
    if(event.type==="agent_settled"){this.active=false;this.settledObserved=true;}
    const serialized=JSON.stringify({type:"pi."+event.type,properties:event});
    for(const res of this.events)try{res.write("data: "+serialized+"\n\n");}catch{this.events.delete(res);}
    if((event.type==="message_end"||event.type==="turn_end")&&event.message?.role==="assistant"&&
       (event.message.stopReason==="error"||event.message.errorMessage)){
      const issue=JSON.stringify({type:"pi.provider_error",
        properties:{kind:piProviderFailure(event.message)}});
      for(const res of this.events)try{res.write("data: "+issue+"\n\n");}catch{this.events.delete(res);}
    }
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
    if(type==="get_queue")return {
      pending:Number(this.session.pendingMessageCount)||0,
      followUps:[...(this.session.getFollowUpMessages?.()||[])].slice(0,PI_QUEUE_LIMIT),
      steering:[...(this.session.getSteeringMessages?.()||[])].slice(0,PI_QUEUE_LIMIT),
      running:!!(this.active||this.running)
    };
    if(type==="queue_prompt"){
      if(!this.active&&!this.running)
        throw Object.assign(new Error("No running Pi task to queue behind"),{status:409});
      if((Number(this.session.pendingMessageCount)||0)>=PI_QUEUE_LIMIT)
        throw Object.assign(new Error("Pi project queue is full (10 messages)"),{status:429});
      if(fields.mode==="steer")await this.session.steer(fields.message,fields.images||[]);
      else await this.session.followUp(fields.message,fields.images||[]);
      this.emitUI("queue_updated",{pending:Number(this.session.pendingMessageCount)||0});
      return {queued:true,pending:Number(this.session.pendingMessageCount)||0};
    }
    if(type==="abort"){
      // Stop only the current Pi run. Never clear the native follow-up/steer
      // queue: the next queued message must run in this SAME project.
      // Pi SDK 1.5.0 abort() settles without automatically waking its queue.
      if(this.queueContinuationActive){
        this.session.agent.abort();
        const pending=Number(this.session.pendingMessageCount)||0;
        this.emitUI("queue_updated",{pending});
        return {stopped:true,continuing:pending>0,pending};
      }
      const previous=this.running;
      this.keepQueueOnStop=true;
      try{
        await this.session.abort();
        if(previous)await previous.catch(()=>{});
        // Let the previous run's cleanup callback finish before taking over
        // this.running. Its credential and execution slot remain reserved
        // whenever Pi still has queued messages.
        await new Promise(resolve=>setImmediate(resolve));
        const pending=Number(this.session.pendingMessageCount)||0;
        if(!pending){
          this.keepQueueOnStop=false;
          this.emitUI("queue_updated",{pending:0});
          return {stopped:true,continuing:false,pending:0};
        }
        // In Pi SDK v1.5.0 abort() leaves this private cancellation latch
        // raised. The native agent_start handler would otherwise abort every
        // queued continuation immediately. Reset ONLY after abort settles.
        if(this.session._agentRunAbortRequested!==true)
          throw new Error("Installed Pi abort state changed; queue preserved for recovery");
        this.session._agentRunAbortRequested=false;
        this.queueContinuationActive=true;
        this.settledObserved=false;
        // The native Pi Agent owns the original queued messages (including
        // attached images). Do not copy, clear, or re-submit them via Python.
        const continuation=Promise.resolve().then(async()=>{
          while(Number(this.session.pendingMessageCount)>0){
            const before=Number(this.session.pendingMessageCount);
            await this.session.agent.continue();
            if(Number(this.session.pendingMessageCount)>=before)
              throw new Error("Pi did not advance its native queue after Stop");
          }
        });
        this.running=continuation;
        continuation.catch(e=>{
          this.emitUI("provider_error",{kind:piProviderFailure(e)});
        }).finally(async()=>{
          this.queueContinuationActive=false;
          this.keepQueueOnStop=false;
          try{await this.clearCredential();}catch{this.close();}
          this.running=null;this.active=false;this.runningModel=null;
          releaseExecution(this);
          if(!this.closed)this.consume({type:"agent_settled",aborted:false});
          this.emitUI("queue_updated",{pending:Number(this.session.pendingMessageCount)||0});
        }).catch(()=>{});
        this.emitUI("queue_updated",{pending,continuing:true});
        return {stopped:true,continuing:true,pending};
      }catch(e){
        this.keepQueueOnStop=false;
        throw e;
      }
    }
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
    run.then(()=>completeAdmission(true)).catch(e=>{
      completeAdmission(false);
      for(const res of this.events)try{res.write("data: "+JSON.stringify({
        type:"pi.provider_error",properties:{kind:piProviderFailure(e)}
      })+"\n\n");}catch{this.events.delete(res);}
    }).finally(async()=>{
      // Stop with pending native work retains the SAME provider credential,
      // model and per-account execution reservation for the queued messages.
      if(this.keepQueueOnStop&&Number(this.session.pendingMessageCount)>0){
        this.running=null;this.active=false;
        return;
      }
      // Otherwise remove the customer's runtime API override after settling.
      try{await this.clearCredential();}
      catch{this.close();}
      this.running=null;this.active=false;this.runningModel=null;
      releaseExecution(this);
      if(!this.closed&&!this.settledObserved)this.consume({type:"agent_settled"});
    }).catch(()=>{});
    await admission;
    return {accepted:true};
  }
  close(){
    if(this.closed)return;this.closed=true;
    for(const request of this.uiRequests.values())try{request.answer({reject:true});}catch{}
    this.uiRequests.clear();this.uiWidgets.clear();
    releaseExecution(this);
    try{this.unsub?.();}catch{}
    try{this.session.dispose();}catch{}
    for(const res of this.events)try{res.end();}catch{}
    this.events.clear();pool.delete(this.id);
  }
}
function piProviderFailure(value){
  const raw=[value?.errorMessage,value?.message,value?.data?.message,value?.code,
    value?.status,value?.statusCode,value?.error?.message].filter(x=>x!=null)
    .map(String).join(" ").slice(0,3000).toLowerCase();
  if(/insufficient[\s_-]*(?:balance|credits?|funds?)|not enough.{0,25}(?:balance|credits?)|balance.{0,30}(?:insufficient|too low)|recharge|top[\s-]?up|no (?:remaining )?credits|credit balance|402|billing[\s_-]*hard[\s_-]*limit/i.test(raw))return "insufficient_balance";
  if(/429|rate[\s_-]*limit|too many requests|quota[\s_-]*exceeded|requests per minute/i.test(raw))return "rate_limited";
  if(/401|unauthori[sz]ed|invalid.{0,20}(?:api[\s_-]*)?key|invalid credentials|authentication failed/i.test(raw))return "invalid_key";
  if(/model.{0,40}(?:not found|unavailable|not supported)|invalid model/i.test(raw))return "model_unavailable";
  if(/403|forbidden|permission denied|access denied/i.test(raw))return "access_denied";
  if(/timeout|timed out|fetch failed|econn|network unreachable/i.test(raw))return "network";
  return "provider_error";
}
function nativeCredential(scope,provider,modelId){
  const account=scope.account;
  if(!account)throw Object.assign(new Error("Pi account grant unavailable"),{status:401});
  const shared=account.shared?.[provider];
  if(shared&&shared.models?.includes(modelId)&&typeof shared.key==="string"&&shared.key)
    return shared.key;
  const personal=account.personal?.[provider];
  if(personal&&personal.models?.includes(modelId)&&typeof personal.key==="string"&&personal.key)
    return personal.key;
  throw Object.assign(new Error("Model is not enabled for the connected Pi account"),{status:403});
}
async function agent(s) {
  const id=projectIdFor(s);
  const current=pool.get(id);
  if(current&&!current.closed){
    // Tool availability is no longer role-dependent; reuse this project's
    // existing Pi SDK session without closing or resetting conversations.
    return current;
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
function piNativeTodos(messages){
  // Only the existing Pi todo extension's tool results represent real state.
  for(let index=messages.length-1;index>=0;index--){
    const message=messages[index];
    if(message?.role!=="toolResult"||message.toolName!=="todo"||
       !Array.isArray(message.details?.todos))continue;
    const items=message.details.todos.slice(0,32)
      .filter(item=>item&&typeof item.text==="string")
      .map(item=>({content:item.text.slice(0,220),
        status:item.done===true?"completed":"pending"}));
    return {supported:true,source:"pi-tool",items};
  }
  return {supported:false,source:"pi-tool",items:[]};
}
function piToolFailureCode(receipt){
  if(!receipt?.isError)return "";
  const content=Array.isArray(receipt.content)?receipt.content
    .filter(x=>x?.type==="text"&&typeof x.text==="string")
    .map(x=>x.text.slice(0,700)).join(" ").toLowerCase():"";
  for(const [code,pattern] of [
    ["ENOENT",/enoent|no such file|file not found|does not exist/],
    ["EACCES",/eacces|eperm|permission denied|access denied/],
    ["ETIMEDOUT",/etimedout|timed out|timeout/],
    ["ENOEXEC",/command not found|executable not found|not recognized as a command/],
    ["ECONNREFUSED",/econnrefused|network is unreachable|could not resolve/],
    ["EINVAL",/invalid arguments|invalid input|validation failed/]
  ])if(pattern.test(content))return code;
  return "";
}
function mapped(messages, id) {
  // Use real Pi toolCall and toolResult records from the native JSONL.
  // Text that merely says "<tool_call>" never becomes an executed tool.
  const receipts=new Map();
  for(const m of messages)if(m?.role==="toolResult"&&typeof m.toolCallId==="string")
    receipts.set(m.toolCallId,m);
  return messages.flatMap((m,index)=>{
    if(!m||m.role==="toolResult")return [];
    const mid="msg_"+createHash("sha256").update(id+":"+index).digest("hex").slice(0,24);
    const content=Array.isArray(m.content)?m.content:[];
    const text=content.length?content.filter(x=>x?.type==="text").map(x=>x.text||"").join("\n"):
      typeof m.content==="string"?m.content:"";
    const parts=[];
    if(text)parts.push({id:"part_"+mid,messageID:mid,sessionID:id,type:"text",text});
    for(const item of content){
      if(item?.type!=="toolCall"||typeof item.id!=="string"||
         typeof item.name!=="string")continue;
      const result=receipts.get(item.id);
      const args=item.arguments&&typeof item.arguments==="object"?item.arguments:{};
      const filePath=typeof args.path==="string"?args.path:
        typeof args.filePath==="string"?args.filePath:"";
      const failureCode=piToolFailureCode(result);
      parts.push({id:"tool_"+mid+"_"+parts.length,messageID:mid,sessionID:id,
        type:"tool",callID:item.id,tool:item.name,
        state:{status:result?(result.isError?"error":"completed"):"pending",
          input:filePath?{filePath}:{},metadata:{},
          ...(failureCode?{error:{code:failureCode}}:{})}});
    }
    return [{info:{id:mid,sessionID:id,
      role:m.role==="assistant"?"assistant":m.role==="user"?"user":"tool",
      time:{created:Date.now()},
      ...(m.role==="assistant"&&(m.stopReason==="error"||m.errorMessage)
        ?{error:{name:"ProviderError",kind:piProviderFailure(m)}}:{})},parts}];
  });
}

// Public metadata only. Gateway PostgreSQL is the sole source of customer
// connected/verified state; this catalog never reads or implies API key status.
function providerCatalog(models,providerDefinitions=[],mode="full",selectedProviderId=""){
  const grouped=new Map();
  for(const model of models){
    if(!model||typeof model.id!=="string"||typeof model.provider!=="string")continue;
    let row=grouped.get(model.provider);
    if(!row){row={id:model.provider,name:model.provider,models:{}};grouped.set(model.provider,row);}
    row.models[model.id]={id:model.id,name:model.name||model.id,
      reasoning:Boolean(model.reasoning),context:model.contextWindow,
      maxTokens:model.maxTokens,cost:model.cost||null};
  }
  for(const provider of providerDefinitions){
    if(typeof provider?.id!=="string"||!provider.id)continue;
    const row=grouped.get(provider.id);
    if(row)row.name=provider.name||row.name;
    else grouped.set(provider.id,{id:provider.id,name:provider.name||provider.id,models:{}});
  }
  // Free-mode snapshots include ALL provider names supplied by installed Pi,
  // but include model details ONLY for selected :free OpenRouter models.
  // This keeps fortnightly Gateway discovery light without concealing Pi
  // providers from the saved, manually searchable registry.
  const all=[...grouped.values()].map(row=>{
    const count=Object.keys(row.models).length;
    const show=mode==="full"||(mode==="provider"&&selectedProviderId===row.id);
    // Minimal periodic seed: only the explicitly free OpenRouter subset is
    // transmitted. Other provider models load once when an admin or customer
    // explicitly links that provider, never during a normal workspace visit.
    const free=mode==="free"&&row.id===selectedProviderId
      ?Object.fromEntries(Object.entries(row.models).filter(([id,m])=>
        id.endsWith(":free")&&m.cost?.input===0&&m.cost?.output===0))
      :{};
    return {...row,model_count:count,models:show?row.models:free};
  });
  return {all,connected:[],default:{}};
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
    const value={models,providers,time:Date.now()};
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
  // A failed gateway credential lookup or model preflight means Pi NEVER
  // received a prompt. Once prompt() is dispatched, an HTTP error can be
  // ambiguous and MUST NOT be labelled as a safe-to-retry rejection.
  let promptDispatched=false;
  try{
    const {pathname,query}=cleanPath(req.url||"/");
    if(pathname==="/health" && req.method==="GET")return json(res,200,{service:"pi-central",status:"ready",activeWorkers:pool.size,maxWorkers:MAX_PROCS,activeExecutions:executing.size,maxActiveExecutions:MAX_ACTIVE_EXECUTIONS});
    if(!["GET","POST","PATCH","PUT","DELETE"].includes(req.method))return error(res,405,"Method not allowed");
    // Restricted control plane: Gateway speaks to Pi over the original UDS.
    // Nginx sends Host test.opencode-gateway.codes, never pi-internal.
    if(pathname==="/internal/bootstrap"&&req.method==="POST"){
      if(!fromGateway(req))return error(res,403,"Local Gateway handoff only");
      const payload=await body(req);
      if(typeof payload?.user_id!=="string"||
         !/^[0-9a-f-]{36}$/i.test(payload.user_id)||
         !Array.isArray(payload.workspaces)||!payload.personal||!payload.shared)
        return error(res,422,"Invalid account handoff");
      const ticket=randomUUID();
      pendingTickets.set(ticket,{account:payload,expires:Date.now()+45000});
      return json(res,200,{ticket});
    }
    if(pathname==="/internal/invalidate"&&req.method==="POST"){
      if(!fromGateway(req))return error(res,403,"Local Gateway invalidation only");
      const payload=await body(req),uid=payload?.user_id;
      if(uid!=null&&(typeof uid!=="string"||!/^[0-9a-f-]{36}$/i.test(uid)))
        return error(res,422,"Invalid account ID");
      revokeBrowserGrants(uid||null);
      return json(res,200,{invalidated:true});
    }
    if(pathname==="/logout"&&req.method==="POST"){
      const raw=String(req.headers.cookie||"");
      const sid=raw.match(/(?:^|;\s*)pi_test_session=([0-9a-f-]{36})(?:;|$)/i)?.[1];
      if(sid)browserGrants.delete(sid);
      res.writeHead(204,{"set-cookie":PI_COOKIE+
        "=; Path=/native-direct/api/; Max-Age=0; HttpOnly; Secure; SameSite=Strict",
        "cache-control":"no-store"});
      res.end();
      return;
    }
    if(pathname==="/bootstrap"&&req.method==="POST"){
      const ticket=String((await body(req))?.ticket||"");
      const grant=pendingTickets.get(ticket);
      if(!grant||grant.expires<=Date.now())
        return error(res,401,"Pi handoff ticket expired");
      pendingTickets.delete(ticket);
      return issueBrowserGrant(res,grant.account);
    }
    const s=await scope(req,query);
    // Signed-in account execution lookup. Works from both the account catalog
    // and project pages without fetching anything through Python.
    if(pathname==="/execution"&&req.method==="GET"){
      const running=liveAccountExecution(s.userId);
      return json(res,200,{running:!!running,
        project_id:running?.scope.projectId||null,
        workspace_id:running?.scope.workspaceId||null,
        project_name:running?.title||null,
        pending:running?Number(running.session?.pendingMessageCount)||0:0});
    }
    if(s.catalog){
      if(pathname==="/provider"&&req.method==="GET") {
        const native=await nativeDiscovery(s.userId);
        // The same /provider endpoint supports compact catalog reads.
        // No extra HTTP route or additional model-registry service.
        const mode=query.get("models");
        const view=["connected","provider","free"].includes(mode)?mode:"full";
        const selected=["provider","free"].includes(view)?(query.get("providerID")||""):"";
        return json(res,200,providerCatalog(native.models,native.providers,view,selected));
      }
      // Discover installed Pi extensions, skills and prompts for all signed-in
      // accounts through Pi itself; no second registry or Python proxy.
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
    // The old OpenCode client polls question/permission queue endpoints.
    // This Pi SDK integration does not create an HTTP approval queue; Pi
    // handles its configured extension/tool lifecycle internally. A queue
    // *read* is empty, not a non-existent "session" 404. Do not invent
    // affirmative permission replies or claim a prompt was approved.
    if(req.method==="GET"&&pathname==="/permission")
      return json(res,200,[]);
    // A Project deletion must NOT instantiate a new Pi session just to
    // remove it. Both GET-after-delete and DELETE are checked against the
    // exact owned workspace before creating any SDK worker.
    const sessionMatch=pathname.match(/^\/session\/(pi_[0-9a-f]{32})$/);
    if(sessionMatch&&(req.method==="GET"||req.method==="DELETE")){
      if(sessionMatch[1]!==projectIdFor(s))return error(res,404,"Session not found");
      const dir=path.resolve(ROOT,"projects",s.userId,s.workspaceId);
      const root=path.resolve(ROOT);
      if(!dir.startsWith(root+path.sep))return error(res,403,"Unsafe session directory");
      if(!existsSync(dir))return error(res,404,"Session not found");
      const rootReal=realpathSync(root),dirReal=realpathSync(dir);
      if(!dirReal.startsWith(rootReal+path.sep)||lstatSync(dir).isSymbolicLink())
        return error(res,403,"Unsafe Pi session path");
      if(req.method==="DELETE"){
        const id=sessionMatch[1],current=pool.get(id);
        if(creating.has(id)||current?.active||current?.running||current?.busy||executing.has(current))
          return error(res,409,"Pi session is busy; stop it before deleting the project");
        if(current)current.close();
        // Only Pi's owned conversation directory is removed here.
        // Gateway's existing DELETE /projects/{id} separately validates
        // ownership and removes the project/worktree/metadata.
        rmSync(dir,{recursive:true,force:false,maxRetries:2,retryDelay:100});
        return json(res,200,{deleted:true,id});
      }
    }
    // File tree reads should not consume an agent process or compete with a
    // running Pi conversation for RPC worker slots.
    if(req.method==="GET"&&["/file","/file/content","/file/status","/vcs"].includes(pathname))
      return json(res,200,projectFileRequest(s,pathname,query));
    const a=await agent(s);
    if(pathname==="/question"&&req.method==="GET")
      return json(res,200,a.pendingUI());
    const questionAnswer=pathname.match(/^\/question\/([0-9a-f-]{36})\/(reply|reject)$/i);
    if(questionAnswer&&req.method==="POST")
      return json(res,200,a.respondUI(questionAnswer[1],
        questionAnswer[2]==="reject"?{reject:true}:await body(req)));
    if(pathname==="/agent"&&req.method==="GET") {
      const native=await a.command("get_commands");
      return json(res,200,nativeCommands(native?.commands||[]));
    }
    if(pathname==="/session" && req.method==="GET")return json(res,200,[{id:a.id,directory:s.directory,title:a.title}]);
    if(pathname==="/session" && req.method==="POST")return json(res,200,{id:a.id,directory:s.directory,title:a.title});
    if(pathname==="/session/status")return json(res,200,{
      [a.id]:{type:a.active||a.running?"busy":"idle",
        pending:Number(a.session.pendingMessageCount)||0}});
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
    if(action==="" && req.method==="GET")return json(res,200,{id:a.id,directory:s.directory,title:a.title});
    // The existing Project rename/restore client uses PATCH on the owned
    // Native session. Pi does not have a second conversation title store:
    // Gateway's Project title remains authoritative. Keep this metadata
    // update in memory; no new session, file or project is created.
    if(action==="" && req.method==="PATCH"){
      const payload=await body(req);
      const title=payload?.title;
      if(typeof title!=="string"||!title.trim()||title.length>200)
        return error(res,422,"Valid Project title required");
      if(a.active||a.running)return error(res,409,"Cannot rename a running Pi conversation");
      a.title=title.trim();
      return json(res,200,{id:a.id,directory:s.directory,title:a.title});
    }
    if(action==="message" && req.method==="GET") {
      const data=await a.command("get_messages");
      return json(res,200,mapped(data?.messages||[],a.id));
    }
    if(action==="todos" && req.method==="GET")
      return json(res,200,piNativeTodos((await a.command("get_messages"))?.messages||[]));
    if(action==="queue"&&req.method==="GET")
      return json(res,200,await a.command("get_queue"));
    // Archived conversations belong to this authenticated project only.
    // Read-only archive browsing never touches source files or starts an AI run.
    if(req.method==="GET"&&(action==="archives"||action.startsWith("archives/"))){
      const archive=path.resolve(ROOT,"projects",s.userId,s.workspaceId,"history-archive");
      const parent=path.resolve(ROOT,"projects",s.userId,s.workspaceId);
      if(!archive.startsWith(parent+path.sep))
        return error(res,403,"Invalid conversation archive directory");
      if(!existsSync(archive))return action==="archives"?
        json(res,200,{archives:[]}):error(res,404,"Archived conversation not found");
      if(lstatSync(archive).isSymbolicLink()||realpathSync(archive)!==archive)
        return error(res,403,"Unsafe conversation archive directory");
      const valid=name=>/^[0-9]{13}-[0-9a-f-]{36}\.jsonl$/i.test(name);
      if(action==="archives"){
        const items=readdirSync(archive,{withFileTypes:true})
          .filter(item=>item.isFile()&&valid(item.name))
          .sort((one,two)=>two.name.localeCompare(one.name)).slice(0,60)
          .map(item=>({id:item.name,archived_at:Number(item.name.slice(0,13)),
            bytes:statSync(path.join(archive,item.name)).size}));
        return json(res,200,{archives:items});
      }
      const name=decodeURIComponent(action.slice("archives/".length));
      if(!valid(name))return error(res,404,"Archived conversation not found");
      const filename=path.join(archive,name);
      if(!existsSync(filename)||lstatSync(filename).isSymbolicLink()||
          !statSync(filename).isFile())return error(res,404,"Archived conversation not found");
      if(statSync(filename).size>8*1024*1024)
        return error(res,413,"Archive is too large for browser preview; the original remains saved");
      const messages=[];
      for(const raw of readFileSync(filename,"utf8").split("\n")){
        if(!raw||messages.length>=250)continue;
        let entry;try{entry=JSON.parse(raw)}catch{continue}
        const msg=entry?.type==="message"?entry.message:null;
        if(!msg||!["user","assistant"].includes(msg.role))continue;
        const content=typeof msg.content==="string"?msg.content:
          Array.isArray(msg.content)?msg.content.filter(x=>x?.type==="text")
            .map(x=>String(x.text||"")).join("\n"):"";
        if(content.trim())messages.push({role:msg.role,text:content.slice(0,14000)});
      }
      return json(res,200,{id:name,archived_at:Number(name.slice(0,13)),
        messages,truncated:messages.length>=250});
    }
    if(action==="reset_context"&&req.method==="POST"){
      const bodyData=await body(req);
      if(bodyData?.confirm!=="RESET_PROJECT_CONTEXT")
        return error(res,422,"Explicit confirmation required");
      if(a.active||a.running||a.busy||executing.has(a)||
         Number(a.session.pendingMessageCount)>0)
        return error(res,409,"أوقف المهمة وانتظر اكتمالها قبل تنظيف سياق المشروع.");
      const id=a.id;
      if(creating.has(id))return error(res,409,"Pi project session is being initialized");
      // Archive the previous native JSONL, not the project's source files.
      // A new Pi session context keeps the SAME external project conversation id.
      const job=(async()=>{
        const dir=path.resolve(ROOT,"projects",s.userId,s.workspaceId);
        const filename=a.session.sessionManager.getSessionFile();
        if(filename&&path.dirname(path.resolve(filename))!==dir)
          throw Object.assign(new Error("Unsafe Pi conversation file"),{status:403});
        const oldFile=filename&&existsSync(filename)?filename:null;
        const archive=path.join(dir,"history-archive");
        const saved=oldFile?path.join(archive,Date.now()+"-"+randomUUID()+".jsonl"):null;
        // Verify both paths BEFORE closing a working session or moving data.
        if(oldFile&&lstatSync(oldFile).isSymbolicLink())
          throw Object.assign(new Error("Unsafe Pi history link"),{status:403});
        if(saved){
          mkdirSync(archive,{recursive:true,mode:0o700});
          if(lstatSync(archive).isSymbolicLink()||realpathSync(archive)!==archive)
            throw Object.assign(new Error("Unsafe Pi archive directory"),{status:403});
        }
        a.close();
        if(saved)renameSync(oldFile,saved);
        try{
          const next=await SdkAgent.create(s);
          pool.set(next.id,next);
          return {reset:true,archived:!!saved,session_id:next.id};
        }catch(e){
          if(saved&&existsSync(saved)&&!existsSync(oldFile))
            renameSync(saved,oldFile);
          throw e;
        }
      })();
      creating.set(id,job);
      try{return json(res,200,await job);}
      finally{if(creating.get(id)===job)creating.delete(id);}
    }
    if(action==="prompt_async" && req.method==="POST") {
      const b=await body(req);
      const {message,images}=piPromptParts(b.parts,s,a.id);
      if((!message.trim()&&!images.length)||message.length>100000)
        return error(res,422,"Prompt required","not_submitted");
      if(!b.model?.providerID||!b.model?.modelID)
        return error(res,422,"Select a verified provider and model from Gateway","not_submitted");
      // One-time Gateway handoff already authorized this account's Pi session.
      // Prompts never fetch a credential or model policy from Python.
      const authorizedKey=nativeCredential(s,b.model.providerID,b.model.modelID);
      // Only ONE project per account may execute. Busy projects may accept
      // bounded native Pi followUps/steering; a different project is rejected.
      const other=liveAccountExecution(s.userId);
      if(other&&other.id!==a.id)
        return error(res,409,projectBusyMessage(other),"not_submitted");
      if(a.active||a.running||executing.has(a)){
        if(a.runningModel?.providerID!==b.model.providerID||
           a.runningModel?.modelID!==b.model.modelID)
          return error(res,409,"رسائل الطابور تستخدم نفس النموذج الجاري. انتظر انتهاء المهمة لتغيير النموذج.","not_submitted");
        // The already-running agent remains selected for queued messages.
        // A composer agent selection does not create a new agent or project.
        if(!["followUp","steer",undefined].includes(b.queueMode))
          return error(res,422,"Invalid Pi queue mode","not_submitted");
        const result=await a.command("queue_prompt",{
          message,images,mode:b.queueMode||"followUp"
        });
        promptDispatched=true;
        return json(res,200,result);
      }
      reserveExecution(a);
      try {
        try{await a.setCredential(b.model.providerID,authorizedKey);}
        catch{throw Object.assign(new Error("Pi credential injection failed"),{status:502});}
        await a.command("set_model",{provider:b.model.providerID,modelId:b.model.modelID});
        a.runningModel={providerID:b.model.providerID,modelID:b.model.modelID};
        // Keep the original Pi command/skill mechanism. Do not invent agents.
        let prompt=message;
        if(b.agent) {
          const commands=await a.command("get_commands");
          const command=(commands?.commands||[]).find(c=>c?.name===b.agent);
          if(!command) {
            releaseExecution(a);
            return error(res,422,"Selected Pi capability is no longer installed","not_submitted");
          }
          prompt="/"+command.name+(message.trim()?" "+message:"");
        }
        promptDispatched=true;
        const accepted=await a.command("prompt",{message:prompt,...(images.length?{images}:{})});
        // Pi can consume an extension command without starting a model run.
        // A started/queued prompt stays reserved until agent_settled or exit.
        if(accepted?.disposition==="handled"){
          a.runningModel=null;releaseExecution(a);
        }
        res.writeHead(204,{"cache-control":"no-store"});res.end();return;
      } catch(e) {
        // Never release an actively running request just because its RPC ack
        // was lost; agent_settled/exit owns that release.
        if(!a.active&&!a.running){a.runningModel=null;releaseExecution(a);}
        throw e;
      }
    }
    if(action==="abort" && req.method==="POST")return json(res,200,await a.command("abort",{},30000));
    return error(res,501,"Pi operation not implemented");
  }catch(e){
    const isPrompt=(req.method==="POST"&&
      /^\/session\/[^/]+\/prompt_async(?:\?|$)/.test(cleanPath(req.url||"/").pathname));
    return error(res,e.status||502,e.message||"Pi adapter error",
      isPrompt&&!promptDispatched?"not_submitted":undefined);
  }
});
server.on("clientError",(_,s)=>s.end("HTTP/1.1 400 Bad Request\r\n\r\n"));
mkdirSync(path.dirname(SOCK),{recursive:true,mode:0o700});
if(existsSync(SOCK))unlinkSync(SOCK);
server.listen(SOCK,()=>{chmodSync(SOCK,0o660);console.log("Pi TEST bridge on UNIX socket");});
setInterval(()=>{for(const a of pool.values())if(!a.active&&!executing.has(a)&&!a.events.size&&Date.now()-a.last>IDLE_MS)a.close();},60000).unref();
setInterval(()=>{
  const current=Date.now();
  for(const [id,entry] of browserGrants)if(entry.expires<=current)browserGrants.delete(id);
  for(const [id,entry] of pendingTickets)if(entry.expires<=current)pendingTickets.delete(id);
},60000).unref();
process.on("SIGTERM",()=>{server.close();for(const a of pool.values())a.close();});
