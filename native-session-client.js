/* OpenCode 1.x native wire adapter and existing-UI presentation, not an execution engine. */
(() => {
  let identity='',configuration=null,configurationPending=null,stream=null;
  const rows=new Map(),snapshots=new Map(),statuses=new Map(),statusEvents=new Map(),statusReads=new Map();
  const permissionReplies=new Set();
  const histories=new Map(),pendingReads=new Map(),discoveryReads=new Map(),selections=new Map(),uncertain=new Map();let epoch=0;
  const owner=()=>String(currentUser?.id||'');
  const label=(en,ar)=>typeof lang!=='undefined'&&lang==='ar'?ar:en;
  const active=()=>configuration?.enabled===true&&identity===owner();
  const current=(id,user)=>activeSession?.id===id&&owner()===user;
  async function ready(){
    const user=owner();if(!user)return false;
    if(identity!==user){clear();identity=user;}
    if(!configuration){const generation=epoch;configurationPending??=api('/api/native-test/state');let value;try{value=await configurationPending;}catch(error){if(generation===epoch)configurationPending=null;throw error;}if(generation!==epoch||user!==owner())throw Error('Authenticated account changed');configuration=value;configurationPending=null;}
    if(owner()!==user)throw Error('Authenticated account changed');
    document.getElementById('workspacePage')?.classList.toggle('native-mode',configuration.enabled===true);
    if(configuration.enabled)presentationStyle();
    return configuration.enabled;
  }
  function clear(){epoch++;stream?.close();stream=null;identity='';configuration=null;configurationPending=null;document.getElementById('workspacePage')?.classList.remove('native-mode');permissionReplies.clear();for(const map of [rows,snapshots,statuses,statusEvents,statusReads,histories,pendingReads,discoveryReads,selections,uncertain])map.clear();}
  function presentationStyle(){
    if(!document.head||document.getElementById('nativeConversationStyles'))return;
    const style=document.createElement('style');style.id='nativeConversationStyles';style.textContent=`
      :root #workspacePage.native-mode .reference-workspace #agentFeed>article{margin-bottom:12px;padding-block:4px 8px;min-height:36px}
      :root #workspacePage.native-mode #agentFeed .agent-response+.user-bubble{margin-top:12px}
      :root #workspacePage.native-mode #agentFeed :is(p,.agent-progress-note){margin-block:0 6px}
      :root #workspacePage.native-mode .message-content>:last-child{margin-bottom:0}
      :root #workspacePage.native-mode .message-content{min-width:0;word-break:normal;overflow-wrap:anywhere}
      :root #workspacePage.native-mode :is(.native-activity,.native-permission-group,.chat-questions){min-width:0;max-width:100%;overflow-wrap:anywhere}
      :root #workspacePage.native-mode :is(.chat-approvals,.chat-questions){margin-block:8px}
      :root #workspacePage.native-mode :is(.chat-approvals,.chat-questions) .chat-approval{padding:10px 12px;margin-block:6px}
      :root #workspacePage.native-mode .native-permission-group h3{font-size:14px;margin:6px 0}
      :root #workspacePage.native-mode .native-permission-group ul{margin:4px 0;padding-inline-start:20px}
      :root #workspacePage.native-mode .native-permission-group li{unicode-bidi:plaintext;overflow-wrap:anywhere}
      :root #workspacePage.native-mode .chat-questions fieldset{margin-block:8px;padding:8px 10px}
      :root #workspacePage.native-mode .chat-questions fieldset>label{flex-direction:row;align-items:center;gap:8px;padding:8px 10px;text-align:start}
      :root #workspacePage.native-mode .chat-questions fieldset>label>input{width:16px;height:16px;min-height:16px;flex:0 0 16px;margin:0}
      :root #workspacePage.native-mode .chat-questions fieldset>label>small{flex-basis:100%;margin-inline-start:24px}
      :root #workspacePage.native-mode .native-activity{margin-top:4px;font-size:13px}
      :root #workspacePage.native-mode .native-activity>summary{cursor:pointer;padding-block:4px}
      :root #workspacePage.native-mode .native-activity .tool-execution{margin:4px 0}
      :root #workspacePage.native-mode .native-activity .tool-execution>summary{padding:7px 10px;unicode-bidi:plaintext}
      :root #workspacePage.native-mode .native-file-link{display:block;max-width:100%;font:inherit;text-align:start;white-space:normal;overflow-wrap:anywhere;color:var(--primary);background:none;border:0;padding:4px 0;cursor:pointer;text-decoration:underline}
      :root #workspacePage.native-mode .native-file-dialog{width:min(880px,92vw);max-height:85dvh}
      :root #workspacePage.native-mode .native-file-dialog pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:60dvh;overflow:auto;text-align:start}
      :root #workspacePage.native-mode .message-table-wrap{max-width:100%;overflow:auto;margin:8px 0;overscroll-behavior-inline:contain}
      :root #workspacePage.native-mode .message-table-wrap table{border-collapse:collapse;min-width:100%;font-size:14px}
      :root #workspacePage.native-mode .message-table-wrap :is(th,td){border:1px solid var(--line);padding:6px 9px;min-width:100px;max-width:360px;overflow-wrap:anywhere;text-align:start}
      :root #workspacePage.native-mode :is(summary,button,input):focus-visible{outline:2px solid var(--primary);outline-offset:3px}
      @media(max-width:600px){:root #workspacePage.native-mode .reference-workspace #agentFeed>article{padding-inline-start:40px}:root #workspacePage.native-mode .reference-workspace #agentFeed>.user-bubble{padding-inline-start:0;padding-inline-end:40px}:root #workspacePage.native-mode .message-avatar{width:28px;height:28px}}
    `;document.head.append(style);
  }
  const storageKey=(kind,id)=>'og-native-'+kind+':'+owner()+':'+id;
  function selection(id){if(!selections.has(id)){try{selections.set(id,JSON.parse(localStorage.getItem(storageKey('selection',id))||'null'));}catch{}}return selections.get(id);}
  function select(id,value){if(!id)return;selections.set(id,value);try{localStorage.setItem(storageKey('selection',id),JSON.stringify(value));}catch{}const row=rows.get(id);if(row){row.model={providerID:value.providerID,id:value.modelID,variant:value.variant};row.agent=value.agent;}}
  function remember(row){const saved=selection(row.id);if(saved)row={...row,model:{providerID:saved.providerID,id:saved.modelID,variant:saved.variant},agent:saved.agent};rows.set(row.id,row);return row;}
  async function context(id){if(rows.has(id))return rows.get(id);const generation=epoch,user=owner(),value=await api('/api/native-test/sessions/'+encodeURIComponent(id));if(generation!==epoch||owner()!==user)throw Error('Authenticated account changed');return remember(value);}
  const url=(workspace,path)=>'/native-session/'+encodeURIComponent(workspace)+'/'+path;
  async function native(workspace,path,body){
    return api(url(workspace,path),body===undefined?{}:{method:'POST',body:JSON.stringify(body)});
  }
  async function sessionRequest(id,suffix,body){const row=await context(id);return native(row.workspace_id,'session/'+encodeURIComponent(row.runtime_id)+(suffix?'/'+suffix:''),body);}
  async function coalesce(key,read){
    if(pendingReads.has(key))return pendingReads.get(key);
    const generation=epoch,user=owner(),promise=(async()=>{const value=await read();if(generation!==epoch||owner()!==user)throw Error('Authenticated account changed');return value;})();
    pendingReads.set(key,promise);try{return await promise;}finally{if(pendingReads.get(key)===promise)pendingReads.delete(key);}
  }
  function reduce(messages,e){
    const p=e.properties||{};
    if(e.type==='message.updated'&&p.info?.id){const old=messages.find(m=>m.info.id===p.info.id);if(old)old.info=p.info;else messages.push({info:p.info,parts:[]});return true;}
    if(e.type==='message.removed'){const at=messages.findIndex(m=>m.info.id===p.messageID);if(at>=0)messages.splice(at,1);return true;}
    if(e.type==='message.part.updated'&&p.part){const m=messages.find(m=>m.info.id===p.part.messageID);if(!m)return false;const at=m.parts.findIndex(v=>v.id===p.part.id);if(at>=0)m.parts[at]=p.part;else m.parts.push(p.part);return true;}
    if(e.type==='message.part.removed'){const m=messages.find(m=>m.info.id===p.messageID);if(m)m.parts=m.parts.filter(v=>v.id!==p.partID);return true;}
    if(e.type==='message.part.delta'){const m=messages.find(m=>m.info.id===p.messageID),part=m?.parts.find(v=>v.id===p.partID);if(!part||!['text','reasoning'].includes(part.type)||p.field!=='text'||typeof p.delta!=='string')return false;part.text=(part.text||'')+p.delta;return true;}
    return false;
  }
  function reconcile(id,messages){
    const last=messages.findLast(m=>m.info.role==='user'&&m.info.model)?.info;
    if(last&&!selection(id))select(id,{providerID:last.model.providerID,modelID:last.model.modelID,agent:last.agent,variant:last.model.variant});
    let pending=uncertain.get(id);try{pending??=JSON.parse(sessionStorage.getItem(storageKey('uncertain',id))||'null');}catch{}
    if(pending){if(messages.some(m=>m.info.id===(pending.messageID||pending))){uncertain.delete(id);sessionStorage.removeItem(storageKey('uncertain',id));}else uncertain.set(id,pending);}
  }
  async function history(id,force=false){
    if(pendingReads.has('history:'+id))return pendingReads.get('history:'+id);
    if(!force&&histories.has(id))return histories.get(id).messages;
    return coalesce('history:'+id,async()=>{const generation=epoch,previous=histories.get(id),state=previous||{messages:[],journal:null};
      state.journal=[];histories.set(id,state);
      try{const messages=await sessionRequest(id,'message');if(!Array.isArray(messages))throw Error('Invalid native message snapshot');if(generation!==epoch)return [];const journal=state.journal;state.messages=messages;for(const event of journal)reduce(state.messages,event);reconcile(id,state.messages);return state.messages;}
      catch(error){if(!previous&&epoch===generation)histories.delete(id);throw error;}finally{state.journal=null;}
    });
  }
  async function requests(kind,id){if(!id)return [];const row=await context(id),data=await coalesce('requests:'+kind+':'+row.workspace_id,()=>native(row.workspace_id,kind));if(!Array.isArray(data))throw Error('Invalid native request list');return data.filter(x=>x.sessionID===row.runtime_id).map(x=>kind==='question'?{...x,questions:x.questions.map(q=>({...q,custom:q.custom!==false}))}:x);}
  function relativeFile(value,row){
    if(typeof value!=='string'||!value||value.length>1000||/[\x00-\x1f\x7f\\]/.test(value)||!row?.file_base)return null;
    let root;try{root=decodeURIComponent(new URL(row.file_base).pathname);}catch{return null;}
    let path=value;if(path.startsWith('file:')){try{const uri=new URL(path);if(uri.host||uri.search||uri.hash)return null;path=decodeURIComponent(uri.pathname);}catch{return null;}}
    if(path.startsWith('/')){if(!path.startsWith(root))return null;path=path.slice(root.length);}
    else if(path.startsWith(root.slice(1)))path=path.slice(root.length-1);
    const parts=path.replace(/^\.\//,'').split('/');
    if(parts.some(p=>!p||p==='.'||p==='..'||p.startsWith('.env')||['.git','.ssh','.opencode','.aws','.config','auth.json','credentials.json','opencode.json','opencode.jsonc'].includes(p)||/\.(pem|key)$/i.test(p))||/^[A-Za-z]:/.test(path))return null;
    return parts.join('/');
  }
  function toolError(state){
    const raw=(typeof state.error==='string'?state.error:state.error?.code||'').slice(0,2000).toLowerCase();
    for(const [kind,pattern] of [['approval_rejected',/user rejected|permissionrejected/],['permission_denied',/eacces|eperm|access denied|permission denied|prevents you/],['file_not_found',/enoent|file not found|does not exist|no such file/],['interrupted',/abort|cancel|interrupt/],['timeout',/timed out|timeout/],['invalid_arguments',/invalid.*(?:input|arguments)|validationerror|zoderror/],['tool_unavailable',/unavailable tool|tool not found|tool is disabled/],['network_unavailable',/econnrefused|enotfound|network is unreachable/]])if(pattern.test(raw))return kind;
    return 'tool_failed';
  }
  function toolActivity(part,row){
    const state=part.state||{},input=state.input||{},metadata=state.metadata||{},files=[];
    const add=(value,operation)=>{const path=relativeFile(value,row);if(path&&!files.some(f=>f.path===path&&f.operation===operation))files.push({path,operation});};
    if(['read','edit','write','multiedit'].includes(part.tool))add(input.filePath,part.tool==='read'?'inspected':'changed');
    if(part.tool==='apply_patch'&&Array.isArray(metadata.files))for(const file of metadata.files.slice(0,50)){const operation={add:'created',update:'changed',delete:'deleted',move:'moved'}[file?.type];if(operation){add(file.relativePath||file.filePath,operation);if(file.movePath)add(file.movePath,'moved');}}
    const status=['pending','running','completed','error'].includes(state.status)?state.status:'pending';
    const result={native:true,workspace_id:row?.workspace_id,id:part.callID,tool:part.tool,status,stage:'tool_activity',files};
    if(['completed','error'].includes(status)&&Number.isFinite(state.time?.start)&&Number.isFinite(state.time?.end)&&state.time.end>=state.time.start)result.duration_ms=state.time.end-state.time.start;
    if(status==='error')result.error_kind=toolError(state);
    // Native output, diff, preview, title and arbitrary metadata can contain
    // credentials/file contents. Only these bounded numeric facts are displayed.
    for(const key of ['matches','count'])if(Number.isInteger(metadata[key])&&metadata[key]>=0)result[key]=metadata[key];
    return result;
  }
  function display(messages,row){
    if(!Array.isArray(messages))throw Error('Invalid native message snapshot');
    return messages.map(m=>{
      // Preserve OpenCode text verbatim. Tool activity is sourced exclusively
      // from native tool parts, never guessed from or appended to chat text.
      const parts=Array.isArray(m.parts)?m.parts:[];
      const tools=new Map();for(const p of parts)if(p.type==='tool'&&p.callID)tools.set(p.callID,p);
      const activity=[...tools.values()].map(p=>toolActivity(p,row));
      return {id:m.info.id,role:m.info.role,text:parts.filter(p=>p.type==='text'&&!p.ignored).map(p=>p.text||'').join(''),activity,
        ...(m.info.error?{state:m.info.error.name==='MessageAbortedError'?'cancelled':'failed'}:{}),attachments:parts.filter(p=>p.type==='file').map(p=>({name:p.filename||'Attachment',mime:p.mime}))};
    });
  }
  async function route(path,options){
    if(!active())return null;
    const method=options.method||'GET';let match=path.match(/^\/api\/workspaces\/([^/]+)\/sessions(?:\?.*)?$/);
    if(match){const result=await api('/api/native-test/workspaces/'+match[1]+'/sessions',options);if(Array.isArray(result))result.forEach(remember);else remember(result);return {value:result};}
    if(/^\/api\/sessions(?:\?.*)?$/.test(path)&&method==='GET'){
      const workspaces=await api('/api/workspaces'),lists=await Promise.all(workspaces.map(async w=>{try{return await api('/api/native-test/workspaces/'+w.id+'/sessions');}catch(error){if([409,410].includes(error.status))return [];throw error;}}));
      const value=lists.flat();value.forEach(remember);return {value};
    }
    match=path.match(/^\/api\/sessions\/([0-9a-f-]+)(?:\/(.*?))?(?:\?.*)?$/);if(!match)return null;
    const id=match[1],tail=match[2]||'',row=await context(id),user=owner();
    if(!tail&&method==='PATCH'){const value=await api('/api/native-test/sessions/'+id,options);remember({...row,...value});return {value};}
    if((!tail&&method==='DELETE')||['close','archive','restore','reopen'].includes(tail))return {value:await api('/api/native-test/sessions/'+id+'/visibility/'+(tail||'delete'),{method:'POST'})};
    if(!tail||tail==='open'){const fresh=tail==='open'?remember(await api('/api/native-test/sessions/'+encodeURIComponent(id))):rows.get(id);return {value:{...fresh,status:statuses.get(id)||'idle',execution_status:statuses.get(id)||'idle'}};}
    if(tail==='messages'&&method==='GET')return {value:display(await history(id),row)};
    if(tail==='todos')return {value:{supported:true,items:await coalesce('todos:'+id,()=>sessionRequest(id,'todo'))}};
    if(tail==='diff')return {value:await sessionRequest(id,'diff')};
    if(tail==='stop'){await sessionRequest(id,'abort',{});statuses.set(id,'idle');return {value:{status:'idle'}};}
    if(tail==='questions')return {value:{requests:await requests('question',id)}};
    if(tail==='permissions')return {value:await requests('permission',id)};
    const reply=tail.match(/^(questions|permissions)\/([^/]+)$/);
    if(reply&&method==='POST'){
      const body=JSON.parse(options.body),kind=reply[1]==='questions'?'question':'permission';
      const operation=kind==='question'&&body.reject?'reject':'reply';
      const data=kind==='question'?(body.reject?{}:{answers:body.answers}):{reply:body.reply};
      const value=await native(row.workspace_id,kind+'/'+encodeURIComponent(reply[2])+'/'+operation,data);
      if(user!==owner())throw Error('Authenticated account changed');return {value};
    }
    if(tail==='queue'||tail.startsWith('submissions/'))throw Error('This native version has no Gateway queue or submission receipt. Check native history before resending.');
    throw Error('This history action is not migrated to native TEST yet; conversation data was preserved.');
  }
  async function synchronizeStatus(row,id,valid=()=>true){
    const generation=epoch,user=owner(),seen=statusEvents.get(id)||0,sequence=(statusReads.get(id)||0)+1;
    statusReads.set(id,sequence);
    const live=await coalesce('status:'+row.workspace_id,()=>native(row.workspace_id,'session/status'));
    if(epoch!==generation||owner()!==user||statusReads.get(id)!==sequence||(statusEvents.get(id)||0)!==seen||!valid())return;
    statuses.set(id,live[row.runtime_id]?.type&&live[row.runtime_id].type!=='idle'?'submitted':'idle');
  }
  async function start(){
    stop();const id=activeSession?.id,user=owner();if(!id)return;
    const row=await context(id);if(!current(id,user))return;
    const source=new EventSource(url(row.workspace_id,'event'));stream=source;let timer,fileTimer,pending=false,lastMessageRead=0,opened=false,needsSnapshot=false;const eventIDs=new Set(),changedTools=new Set();
    function filesChanged(){clearTimeout(fileTimer);fileTimer=setTimeout(()=>{if(stream===source&&current(id,user))window.refreshNativeFiles?.({workspaceId:row.workspace_id,owner:user});},400);}
    // Coalesce token/part bursts into bounded snapshots. The native SSE
    // transport stays immediate; only expensive full-history reads are paced.
    const MESSAGE_REFRESH_MS=50;
    let dirty={messages:false,status:false,controls:false,todos:false};
    async function flush(){
      timer=null;if(pending||stream!==source||!current(id,user))return;
      const work=dirty;dirty={messages:false,status:false,controls:false,todos:false};pending=true;
      try{
        if(work.status)await window.refreshWorkspaceSessionStatus?.();
        if(stream!==source||!current(id,user))return;
        if(work.messages){if(needsSnapshot){needsSnapshot=false;await history(id,true);}await refreshMessages();lastMessageRead=Date.now();}
        if(work.controls)await refreshPermissions();
        if(work.todos)await window.refreshWorkspaceTodos?.(true);
      }catch(error){if(current(id,user)&&stream===source)$('#runtimeStatus').textContent=error.message;}
      finally{pending=false;if(stream===source&&current(id,user)&&Object.values(dirty).some(Boolean))schedule();}
    }
    function schedule(){
      if(pending||timer)return;
      const delay=dirty.messages?Math.max(0,MESSAGE_REFRESH_MS-(Date.now()-lastMessageRead)):80;
      timer=setTimeout(flush,delay);
    }
    source.onmessage=event=>{
      if(stream!==source||!current(id,user))return;
      let e;try{e=JSON.parse(event.data);}catch{return;}
      if(e.id){if(eventIDs.has(e.id))return;eventIDs.add(e.id);if(eventIDs.size>2000)eventIDs.delete(eventIDs.values().next().value);}
      if(e.type==='models-dev.refreshed'||e.type==='catalog.updated'){
        snapshots.clear();window.workspaceRuntime?.clear();
        window.refreshWorkspaceChoices?.('',true).catch(error=>{if(current(id,user))$('#runtimeStatus').textContent=error.message;});
        return;
      }
      const p=e.properties||{},session=p.sessionID||p.info?.sessionID||p.part?.sessionID||p.info?.id;
      if(session&&session!==row.runtime_id)return;
      if(e.type==='file.edited'&&relativeFile(p.file,row))filesChanged();
      if(e.type==='message.part.updated'&&p.part?.type==='tool'){
        const activity=toolActivity(p.part,row);if(!['todowrite','todoread'].includes(activity.tool))window.renderWorkspaceEventLine?.('activity',activity);
        if(activity.status==='completed'&&activity.files.some(f=>f.operation!=='inspected')&&!changedTools.has(activity.id)){changedTools.add(activity.id);filesChanged();}
      }
      if(['session.status','session.idle','session.error'].includes(e.type))statusEvents.set(id,(statusEvents.get(id)||0)+1);
      if(e.type==='session.status')statuses.set(id,p.status?.type==='idle'?'idle':'submitted');
      if(e.type==='session.idle')statuses.set(id,'idle');
      if(e.type==='session.error')statuses.set(id,'failed');
      if(e.type.startsWith('message.')){const state=histories.get(id);if(state){state.journal?.push(e);if(!reduce(state.messages,e))needsSnapshot=true;reconcile(id,state.messages);}else needsSnapshot=true;dirty.messages=true;}
      if(e.type.startsWith('session.'))dirty.status=true;
      if(/^(permission|question)\./.test(e.type))dirty.controls=true;
      if(e.type.startsWith('todo.'))dirty.todos=true;
      if(Object.values(dirty).some(Boolean))schedule();
    };
    source.onopen=async()=>{
      if(!current(id,user)||stream!==source)return;
      try{await synchronizeStatus(row,id,()=>current(id,user)&&stream===source);}
      catch(error){if(current(id,user)&&stream===source)$('#runtimeStatus').textContent=error.message;}
      if(current(id,user)&&stream===source){if(opened)filesChanged();needsSnapshot=opened||!histories.has(id);opened=true;dirty={messages:true,status:true,controls:true,todos:true};schedule();}
    };
    source.onerror=()=>{if(current(id,user)&&stream===source)$('#runtimeStatus').textContent='Reconnecting to native OpenCode';};
    const close=source.close.bind(source);source.close=()=>{clearTimeout(timer);clearTimeout(fileTimer);close();};
  }
  function stop(){stream?.close();stream=null;}
  async function send(id,{text,providerID,modelID,agent,variant,files=[]}){
    const row=await context(id);
    if(blocked(id))throw Error('Native receipt is uncertain. Reconnect and check history before resending.');
    const user=owner();select(id,{providerID,modelID,agent,variant});
    const bytes=new Uint8Array(14);crypto.getRandomValues(bytes);const alphabet='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';
    const messageID='msg_'+((BigInt(Date.now())*4096n)&0xffffffffffffn).toString(16).padStart(12,'0')+Array.from(bytes,b=>alphabet[b%alphabet.length]).join('');
    const parts=[{type:'text',text},...files.map(f=>({type:'file',mime:f.mime||({'png':'image/png','jpg':'image/jpeg','jpeg':'image/jpeg','webp':'image/webp','pdf':'application/pdf'}[f.path.split('.').at(-1)]||'application/octet-stream'),url:row.file_base+f.path.split('/').map(encodeURIComponent).join('/'),filename:f.path.split('/').at(-1)}))];
    try{await native(row.workspace_id,'session/'+encodeURIComponent(row.runtime_id)+'/prompt_async',{
      messageID,model:{providerID,modelID},...(variant?{variant}:{}),...(agent?{agent}:{}),parts});}
    catch(error){if(owner()===user&&(!error.status||error.status>=500)){const pending={messageID,text,files,providerID,modelID,agent,variant};uncertain.set(id,pending);try{sessionStorage.setItem(storageKey('uncertain',id),JSON.stringify(pending));}catch{}error.message='Native receipt is uncertain. Draft preserved; check history before resending.';}throw error;}
    if(owner()!==user)return;
    statuses.set(id,'submitted');
    if(activeSession?.id===id)activeSession.execution_status='submitted';
    // The native acknowledgment is final for submission. Live/reconnect SSE
    // reconciles execution; a second status read cannot undo the acknowledgment.
  }
  function blocked(id){if(uncertain.has(id))return true;try{return Boolean(sessionStorage.getItem(storageKey('uncertain',id)));}catch{return false;}}
  async function permissions(box,provided){
    const id=activeSession?.id,user=owner();if(!id||!box)return;
    const pending=[...new Map((provided||await requests('permission',id)).map(item=>[item.id,item])).values()];if(!current(id,user))return;
    const row=await context(id);if(!current(id,user))return;
    const signature=user+':'+id+':'+(typeof lang==='undefined'?'en':lang)+':'+JSON.stringify(pending);if(box.nativeSignature===signature)return;box.nativeSignature=signature;box.replaceChildren();box.hidden=!pending.length;
    const names={read:['Read file','قراءة ملف'],edit:['Edit file','تعديل ملف'],write:['Write file','كتابة ملف'],apply_patch:['Apply file changes','تطبيق تغييرات الملفات'],glob:['Find files','البحث عن الملفات'],grep:['Search content','البحث في المحتوى'],list:['List files','عرض الملفات'],question:['Question','سؤال'],todowrite:['Update tasks','تحديث المهام'],todoread:['Read tasks','قراءة المهام']};
    const groups=new Map();for(const item of pending){const key=item.permission;let group=groups.get(key);if(!group){group=[];groups.set(key,group);}group.push(item);}
    for(const [permission,items] of groups){
      const section=document.createElement('section');section.className='native-permission-group';
      const heading=document.createElement('h3');heading.textContent=label('Permission requested: ','طلب موافقة: ')+(names[permission]?label(...names[permission]):label('Restricted operation','عملية مقيّدة'))+' · '+items.length;section.append(heading);
      for(const item of items){const actionKey=user+':'+id+':'+item.id;const card=document.createElement('div');card.className='chat-approval';card.dataset.permissionId=item.id;
        const candidates=['read','edit','write','apply_patch'].includes(permission)?[item.metadata?.filepath,...(item.patterns||[])]:['glob','grep','list'].includes(permission)?[item.metadata?.path]:[];
        const paths=[...new Set(candidates.map(value=>relativeFile(value,row)).filter(Boolean))].slice(0,8);
        if(paths.length){const list=document.createElement('ul');for(const path of paths){const li=document.createElement('li');li.textContent=path;li.dir='auto';list.append(li);}card.append(list);}
        const note=document.createElement('small');note.textContent=label('This request only. Gateway verifies ownership and policy.','لهذا الطلب فقط. تتحقق البوابة من الملكية والسياسة.');card.append(note);
        const controls=document.createElement('div');controls.className='chat-approval-actions';
        for(const [text,reply] of [[label('Allow once','السماح مرة واحدة'),'once'],[label('Reject','رفض'),'reject']]){const button=document.createElement('button');button.textContent=text;button.type='button';button.dataset.reply=reply;
          button.disabled=permissionReplies.has(actionKey)||reply==='once'&&!names[permission];
          button.onclick=async()=>{
            if(!current(id,user)||permissionReplies.has(actionKey))return;permissionReplies.add(actionKey);card.dataset.sending='1';card.setAttribute('aria-busy','true');card.querySelectorAll('button').forEach(n=>n.disabled=true);
            try{await api('/api/sessions/'+id+'/permissions/'+encodeURIComponent(item.id),{method:'POST',body:JSON.stringify({reply})});if(!current(id,user))return;permissionReplies.delete(actionKey);box.nativeSignature='';await refreshPermissions();}
            catch(error){permissionReplies.delete(actionKey);if(!current(id,user))return;delete card.dataset.sending;card.removeAttribute('aria-busy');card.querySelectorAll('button').forEach(n=>n.disabled=n.dataset.reply==='once'&&!names[permission]);toast(error.message);}
          };controls.append(button);
        }card.append(controls);section.append(card);
      }box.append(section);
    }
  }
  async function discovery(id,{force=false}={}){
    if(!force&&snapshots.has(id)&&Date.now()-snapshots.get(id).loadedAt<60000)return snapshots.get(id);
    if(discoveryReads.has(id))return discoveryReads.get(id);
    const generation=epoch,user=owner(),job=loadDiscovery(id).then(value=>{if(generation!==epoch||user!==owner())throw Error('Authenticated account changed');snapshots.set(id,value);return value;});discoveryReads.set(id,job);
    try{return await job;}finally{if(discoveryReads.get(id)===job)discoveryReads.delete(id);}
  }
  async function loadDiscovery(id){
    const [providers,agents]=await Promise.all(['provider','agent'].map(path=>native(id,path)));
    if(!Array.isArray(providers.all)||!Array.isArray(providers.connected)||!Array.isArray(agents))throw Error('Invalid native discovery schema');
    const result={native:true,loadedAt:Date.now(),workspace_id:String(id),health:{healthy:true},version:configuration.version,status:'ready',errors:{},agents,default_agent:null,
      generation:'native-test',revision:'live',policy_revision:'native',providers:[...providers.all,...(providers.connected_entries||[])].map(p=>({...p,...providers.gateway_auth_status?.[p.id],connected:providers.connected.includes(p.id),allowed:true,
        default_model:providers.default?.[p.id],models:Object.values(p.models||{}).map(m=>({...m,allowed:true}))}))};
    return result;
  }
  window.nativeSession={ready,active,route,start,stop,send,permissions,requests,discovery,select,selection,blocked,invalidate:id=>id?snapshots.delete(id):snapshots.clear(),peek:id=>snapshots.get(id),clear};
  window.addEventListener('authentication-cleared',clear);
})();
