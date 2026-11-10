/* Pi 1.x native wire adapter and existing-UI presentation, not an execution engine. */
(() => {
  let identity='',configuration=null,configurationPending=null,stream=null,streamId='';
  const rows=new Map(),snapshots=new Map(),statuses=new Map(),statusEvents=new Map(),statusReads=new Map();
  const permissionReplies=new Set(),submissionsInFlight=new Map(),sendGenerations=new Map();
  const histories=new Map(),pendingReads=new Map(),discoveryReads=new Map(),selections=new Map(),uncertain=new Map();let epoch=0;
  const owner=()=>String(currentUser?.id||'');
  const label=(en,ar)=>typeof lang!=='undefined'&&lang==='ar'?ar:en;
  const active=()=>configuration?.enabled===true&&identity===owner();
  const current=(id,user)=>activeSession?.id===id&&owner()===user;
  async function ready(){
    const user=owner();if(!user)return false;
    if(identity!==user){clear();identity=user;}
    if(location.hostname==='test.opencode-gateway.codes') {
      // TEST Pi uses native RPC through the existing Nginx connection.
      // No Python feature switch governs provider/agent execution.
      configuration={enabled:true,mode:'pi-test',version:'native'};
    } else if(!configuration) {
      const generation=epoch;configurationPending??=api('/api/native-test/state');let value;
      try{value=await configurationPending;}catch(error){if(generation===epoch)configurationPending=null;throw error;}
      if(generation!==epoch||user!==owner())throw Error('Authenticated account changed');
      configuration=value;configurationPending=null;
      if(typeof value?.native_account_directory==='string')window.__nativeAccountDir=value.native_account_directory;
    }
    if(owner()!==user)throw Error('Authenticated account changed');
    document.getElementById('workspacePage')?.classList.toggle('native-mode',configuration.enabled===true);
    if(configuration.enabled)presentationStyle();
    return configuration.enabled;
  }
  function clear(){epoch++;for(const controller of submissionsInFlight.values())controller.abort();submissionsInFlight.clear();sendGenerations.clear();stream?.close();stream=null;streamId='';identity='';configuration=null;configurationPending=null;document.getElementById('workspacePage')?.classList.remove('native-mode');permissionReplies.clear();for(const map of [rows,snapshots,statuses,statusEvents,statusReads,histories,pendingReads,discoveryReads,selections,uncertain])map.clear();}
  function presentationStyle(){
    if(!document.head||document.getElementById('nativeConversationStyles'))return;
    const style=document.createElement('style');style.id='nativeConversationStyles';style.textContent=`
      :root #workspacePage.native-mode .reference-workspace #agentFeed>article{margin-bottom:12px;padding-block:4px 8px;min-height:36px}
      :root #workspacePage.native-mode #agentFeed .agent-response+.user-bubble{margin-top:12px}
      :root #workspacePage.native-mode #agentFeed :is(p,.agent-progress-note){margin-block:0 6px}
      :root #workspacePage.native-mode .message-content>:last-child{margin-bottom:0}
      :root #workspacePage.native-mode .message-rich{font-size:15px;line-height:1.8;letter-spacing:normal}
      :root #workspacePage.native-mode .message-rich :is(h2,h3,h4,h5,h6){line-height:1.45;margin-block:18px 8px;font-weight:650}
      :root #workspacePage.native-mode .message-rich :is(ul,ol){padding-inline-start:24px;margin-block:8px}
      :root #workspacePage.native-mode .message-rich blockquote{border-inline-start:3px solid var(--primary);padding-inline-start:12px;margin-inline:0;color:var(--muted)}
      :root #workspacePage.native-mode .message-rich hr{border:0;border-block-start:1px solid var(--line);margin-block:16px}
      :root #workspacePage.native-mode .message-rich li{margin-block:5px}
      :root #workspacePage.native-mode .message-rich .message-code-block{margin-block:12px;max-width:100%;overflow:hidden}
      :root #workspacePage.native-mode .message-rich pre{overflow:auto;white-space:pre;line-height:1.6}
      :root #workspacePage.native-mode .assistant-collapsed{max-height:360px;overflow:hidden;mask-image:linear-gradient(#000 85%,transparent)}
      :root #workspacePage.native-mode .assistant-fold-control{margin-block:6px}
      :root #workspacePage.native-mode .message-content{min-width:0;word-break:normal;overflow-wrap:anywhere}
      :root #workspacePage.native-mode :is(.native-activity,.native-permission-group,.chat-questions){min-width:0;max-width:100%;overflow-wrap:anywhere}
      :root #workspacePage.native-mode :is(.chat-approvals,.chat-questions){margin-block:8px}
      :root #workspacePage.native-mode :is(.chat-approvals,.chat-questions) .chat-approval{padding:10px 12px;margin-block:6px}
      :root #workspacePage.native-mode .native-permission-group h3{font-size:14px;margin:6px 0}
      :root #workspacePage.native-mode .native-permission-group ul{margin:4px 0;padding-inline-start:20px}
      :root #workspacePage.native-mode .native-permission-group li{unicode-bidi:plaintext;overflow-wrap:anywhere}
      :root #workspacePage.native-mode .chat-questions{width:min(100%,680px);margin-inline:auto;font-size:13px}
      :root #workspacePage.native-mode .chat-questions .chat-approval{max-height:min(360px,46dvh);overflow:auto;overscroll-behavior:contain;padding:8px 10px;scroll-padding-block:36px}
      :root #workspacePage.native-mode .chat-questions fieldset{margin-block:5px;padding:5px 7px;min-width:0}
      :root #workspacePage.native-mode .chat-questions :is(legend,.question-heading){font-size:13px;line-height:1.4}
      :root #workspacePage.native-mode .chat-questions fieldset>label{flex-direction:row;align-items:center;gap:6px;padding:5px 8px;margin-block:4px;text-align:start;font-size:13px;line-height:1.4;min-height:32px}
      :root #workspacePage.native-mode .chat-questions fieldset>label>input{width:16px;height:16px;min-height:16px;flex:0 0 16px;margin:0}
      :root #workspacePage.native-mode .chat-questions fieldset>label>small{flex-basis:100%;margin-inline-start:22px;font-size:11px;line-height:1.4}
      :root #workspacePage.native-mode .chat-questions input[type=text]{font-size:13px;padding:6px 9px;min-height:32px}
      :root #workspacePage.native-mode .chat-questions .chat-approval-actions{position:sticky;bottom:-8px;background:var(--panel);padding-block:5px;margin-top:4px;z-index:1}
      :root #workspacePage.native-mode .chat-questions .chat-approval-actions button{font-size:12px;padding:5px 8px;min-height:32px}
      :root #workspacePage.native-mode .chat-questions .chat-approval>strong{font-size:13px}
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
  // Pi is the sole persistent owner of session provider/model state and
  // installed commands. Browser selections are transient composer input only.
  function selection(id){return selections.get(id);}
  function select(id,value){
    if(!id)return;
    // Remove obsolete local preferences left by the old client adapter.
    try{localStorage.removeItem(storageKey('selection',id));}catch{}
    selections.set(id,value);
  }
  function remember(row){rows.set(row.id,row);return row;}
  async function context(id){
    if(rows.has(id))return rows.get(id);
    const workspace=activeWorkspace?.id;
    if(!workspace)throw Error('Select the Project before opening its Native session');
    const list=await localProjectSessionRows(workspace);
    const selected=list.find(row=>row.id===id);
    if(selected)return selected;
    throw Error(label('No registered Native session is available for this Project.',
      'لا توجد جلسة Native مسجلة لهذا المشروع.'));
  }
  async function localProjectContext(workspace){
    // Platform returns ownership and directory metadata; no Python Native calls.
    const info=await api('/api/workspaces/'+encodeURIComponent(workspace));
    if(!info?.project_id||!info?.native_directory)
      throw Error('The owned Native workspace directory is unavailable');
    const [association,project]=await Promise.all([
      api('/api/projects/'+encodeURIComponent(info.project_id)+'/native-binding'),
      api('/api/projects/'+encodeURIComponent(info.project_id))
    ]);
    return {projectId:info.project_id,name:project.name,root:info.native_directory,
      binding:association?.binding||null};
  }
  function localProjectRow(workspace,context,live){
    return remember({id:context.projectId,workspace_id:workspace,project_id:context.projectId,
      runtime_id:live.id,title:context.name||live.title||'Project',
      status:'idle',lifecycle:'active',native:true,
      native_directory:context.root,file_base:'file://'+context.root.replace(/\\\\/g,'/')+'/' });
  }
  async function localProjectSessionRows(workspace){
    const ctx=await localProjectContext(workspace);
    if(!ctx.binding)return [];
    if(ctx.binding.workspace_id!==workspace)return [];
    // TEST engine conversion: replace one old ses_* Pi binding with the
    // unique pi_* session belonging to this same owned Project. No duplicate.
    if(ctx.binding.native_session_id.startsWith('ses_')){
      const available=await window.nativeDirectTest.direct('session',{directory:ctx.root});
      const pi=Array.isArray(available)?available.filter(x=>x?.id?.startsWith('pi_')&&x.directory===ctx.root):[];
      if(pi.length===1){
        const changed=await api('/api/projects/'+encodeURIComponent(ctx.projectId)+'/native-binding',{
          method:'POST',body:JSON.stringify({workspace_id:workspace,
            native_session_id:pi[0].id,replace_legacy_opencode:true})
        });
        ctx.binding={...ctx.binding,native_session_id:changed.native_session_id};
      }
    }
    const live=await window.nativeDirectTest.direct('session/'+encodeURIComponent(ctx.binding.native_session_id),
      {directory:ctx.root});
    if(!live?.id||live.id!==ctx.binding.native_session_id||live.directory!==ctx.root)
      throw Error(label('Project session needs explicit recovery; no replacement was created.',
        'جلسة المشروع تحتاج إلى استعادة مقصودة؛ لم تُنشأ جلسة بديلة.'));
    // Project is the only user-facing conversation title. Synchronize through
    // Pi Native itself; Python only owns the administrative Project name.
    let named=live;
    if(ctx.name&&live.title!==ctx.name){
      named=await window.nativeDirectTest.direct(
        'session/'+encodeURIComponent(live.id),
        {method:'PATCH',directory:ctx.root,value:{title:ctx.name}});
      if(named?.id!==live.id)
        throw Error('Pi did not confirm the Project conversation title');
    }
    return [localProjectRow(workspace,ctx,named)];
  }
  async function localCreateProjectSession(workspace,options={}){
    const ctx=await localProjectContext(workspace);
    if(ctx.binding){
      if(ctx.binding.workspace_id!==workspace)
        throw Error('This Project already owns a Native session in another Workspace');
      const list=await localProjectSessionRows(workspace);
      return list[0];
    }
    // A previous TEST conversation may predate the Platform binding table.
    // If its directory uniquely identifies one existing Native session, reuse it
    // and persist the binding instead of starting another conversation.
    const existing=await window.nativeDirectTest.direct('session',{directory:ctx.root});
    if(!Array.isArray(existing))throw Error('Native session inventory is unavailable');
    const candidates=existing.filter(row=>row?.id&&row.directory===ctx.root);
    if(candidates.length){
      const named=candidates.filter(row=>row.title===ctx.name);
      const selected=candidates.length===1?candidates[0]:named.length===1?named[0]:null;
      if(!selected)
        throw Error(label('Several conversations exist in this Project directory. Select the correct Native session before binding; no new session was created.',
          'يوجد أكثر من محادثة في مجلد المشروع. يجب تحديد الجلسة الصحيحة قبل الربط؛ لم تُنشأ جلسة جديدة.'));
      try{
        await api('/api/projects/'+encodeURIComponent(ctx.projectId)+'/native-binding',{
          method:'POST',body:JSON.stringify({workspace_id:workspace,native_session_id:selected.id})
        });
      }catch(error){
        // Concurrent tabs may have bound the same project first.
        const current=await localProjectContext(workspace);
        if(current.binding?.workspace_id===workspace&&current.binding.native_session_id===selected.id)
          return localProjectRow(workspace,current,selected);
        throw error;
      }
      return localProjectRow(workspace,ctx,selected);
    }
    const data=JSON.parse(options.body||'{}');
    const live=await window.nativeDirectTest.direct('session',{
      method:'POST',directory:ctx.root,
      value:{title:ctx.name||data.title||'Project'}
    });
    if(!live?.id||live.directory!==ctx.root)
      throw Error('Native returned an invalid Project session');
    try{
      await api('/api/projects/'+encodeURIComponent(ctx.projectId)+'/native-binding',{
        method:'POST',body:JSON.stringify({workspace_id:workspace,native_session_id:live.id})
      });
    }catch(error){
      throw Error('Native session was created but its Project binding was not confirmed. '+
        'Do not retry creation; recover the existing session. '+error.message);
    }
    return localProjectRow(workspace,ctx,live);
  }
  // Native executes and streams directly through the TEST Nginx endpoint.
  // Workspace session metadata remains in the existing application DB;
  // no Python code processes the prompt or response body.
  function nativeRoot(workspace){
    const record=[...rows.values()].find(row=>String(row.workspace_id)===String(workspace));
    if(record?.native_directory)return record.native_directory;

    return window.nativeDirectTest?.rootFromFile(record?.file_base)
      ||window.nativeDirectTest?.defaultDirectory?.();
  }
  const url=(workspace,path)=>window.nativeDirectTest.url(path,nativeRoot(workspace));
  async function native(workspace,path,body,{signal,timeout=30000}={}){
    // No Python or legacy /native-session fallback. Native is the only engine.
    if(!window.nativeDirectTest?.active?.())throw Error('Pi Native is unavailable');
    const controller=new AbortController(),cancel=()=>controller.abort();
    if(signal?.aborted)controller.abort();
    else signal?.addEventListener('abort',cancel,{once:true});
    const timer=setTimeout(cancel,timeout);
    try{
      return await window.nativeDirectTest.direct(path,{
        method:body===undefined?'GET':'POST',value:body,
        directory:nativeRoot(workspace),signal:controller.signal
      });
    }finally{clearTimeout(timer);signal?.removeEventListener('abort',cancel);}
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
    if(pending){if(messages.some(m=>m.info.id===(pending.messageID||pending))){if(typeof pending==='object'){pending.accepted=true;}uncertain.delete(id);try{sessionStorage.removeItem(storageKey('uncertain',id));}catch{}}else uncertain.set(id,pending);}
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
  async function freshHistory(id){
    // A snapshot already in flight may predate the failed submission. Joining
    // it is not a receipt check. Drain it, then read once; never resend a prompt.
    const generation=epoch,user=owner(),pending=pendingReads.get('history:'+id);
    if(pending){try{await pending;}catch{} }
    if(generation!==epoch||owner()!==user)throw Error('Authenticated account changed');
    return history(id,true);
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
      // Preserve Pi text verbatim. Tool activity is sourced exclusively
      // from native tool parts, never guessed from or appended to chat text.
      const parts=Array.isArray(m.parts)?m.parts:[];
      const tools=new Map();for(const p of parts)if(p.type==='tool'&&p.callID)tools.set(p.callID,p);
      const activity=[...tools.values()].map(p=>toolActivity(p,row));
      // Native expands attachments into synthetic user text (read arguments and
      // file contents). Keep it available to Native, never in the user's bubble.
      // Use the original flag, not text/regex heuristics that could erase a prompt.
      return {id:m.info.id,role:m.info.role,text:parts.filter(p=>p.type==='text'&&!p.ignored&&!(m.info.role==='user'&&p.synthetic===true)).map(p=>p.text||'').join(''),activity,
        ...(m.info.error?{state:m.info.error.name==='MessageAbortedError'?'cancelled':'failed'}:{}),attachments:parts.filter(p=>p.type==='file').map(p=>({name:typeof p.filename==='string'?p.filename.split(/[\\/]/).at(-1)||'Attachment':'Attachment',mime:p.mime}))};
    });
  }
  async function route(path,options){
    if(!active())return null;
    const method=options.method||'GET';let match=path.match(/^\/api\/workspaces\/([^/]+)\/sessions(?:\?.*)?$/);
    if(match){
      const result=method==='POST'
        ?await localCreateProjectSession(match[1],options)
        :await localProjectSessionRows(match[1]);
      if(Array.isArray(result))result.forEach(remember);else remember(result);
      return {value:result};
    }
    if(/^\/api\/sessions(?:\?.*)?$/.test(path)&&method==='GET'){
      const unavailable=[];
      // TEST: a user explicitly opens a project before asking Pi for
      // its conversations. Do not let Native enumerate every account project.
      const workspaces=activeWorkspace?.id?[{id:activeWorkspace.id}]:[];
      const lists=await Promise.all(workspaces.map(async w=>{
        try{return await localProjectSessionRows(w.id);}
        catch(error){
          if([409,410].includes(error.status)){
            unavailable.push({workspace_id:w.id,status:error.status,reason:error.message});
            return [];
          }
          throw error;
        }
      }));
      const value=lists.flat();value.forEach(remember);
      if(unavailable.length){
        const status=document.getElementById('runtimeStatus');
        if(status)status.textContent=label('Some conversations could not be loaded; workspace access needs review.','تعذر تحميل بعض المحادثات؛ يجب مراجعة إمكانية الوصول إلى مساحات العمل.')+' ('+unavailable.length+')';
        window.dispatchEvent(new CustomEvent('native-session-list-warning',{detail:{unavailable}}));
      }
      return {value};
    }
    match=path.match(/^\/api\/sessions\/([0-9a-f-]+)(?:\/(.*?))?(?:\?.*)?$/);if(!match)return null;
    const id=match[1],tail=match[2]||'',row=await context(id),user=owner();
    if(!tail&&method==='PATCH'){
      if(!window.nativeDirectTest?.active?.())throw Error('Pi Native is unavailable');
      const payload=JSON.parse(options.body||'{}');
      const projectId=row.project_id||row.id;
      if(typeof payload.title!=='string'||!payload.title.trim())throw Error('Project name is required');
      const result=await api('/api/projects/'+encodeURIComponent(projectId),{
        method:'PATCH',body:JSON.stringify({name:payload.title.trim()})
      });
      const named=await window.nativeDirectTest.direct(
        'session/'+encodeURIComponent(row.runtime_id),
        {method:'PATCH',directory:nativeRoot(row.workspace_id),value:{title:result.name||payload.title.trim()}});
      if(named?.id!==row.runtime_id)throw Error('Native Project title update was not confirmed');
      const value=remember({...row,title:result.name||payload.title.trim()});
      return {value};
    }
    if((!tail&&method==='DELETE')||['close','archive','restore','reopen'].includes(tail)){
      throw Error(label('Project conversations have no separate deletion or archive. Use Project actions.',
        'لا توجد إدارة منفصلة لحذف أو أرشفة المحادثة. استخدم إجراءات المشروع.'));
    }
    if(!tail||tail==='open'){
      const fresh=tail==='open'
        ?row
        :rows.get(id);
      return {value:{...fresh,status:statuses.get(id)||'idle',execution_status:statuses.get(id)||'idle'}};
    }
    if(tail==='messages'&&method==='GET')return {value:display(await history(id),row)};
    if(tail==='todos')return {value:{supported:true,items:await coalesce('todos:'+id,()=>sessionRequest(id,'todo'))}};
    if(tail==='diff')return {value:await sessionRequest(id,'diff')};
    if(tail==='stop')return {value:await forceStop(id)};
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
    if(!live||typeof live!=='object'||Array.isArray(live))throw Error('Invalid native session status');
    if(epoch!==generation||owner()!==user||statusReads.get(id)!==sequence||(statusEvents.get(id)||0)!==seen||!valid())return;
    statuses.set(id,live[row.runtime_id]?.type&&live[row.runtime_id].type!=='idle'?'submitted':'idle');
  }
  async function start(){
    stop();const id=activeSession?.id,user=owner();if(!id)return;
    const row=await context(id);if(!current(id,user))return;
    const source=new EventSource(url(row.workspace_id,'event'));stream=source;streamId=id;let timer,fileTimer,pending=false,lastMessageRead=0,opened=false,needsSnapshot=false;const eventIDs=new Set(),changedTools=new Set();
    function filesChanged(){clearTimeout(fileTimer);fileTimer=setTimeout(()=>{if(stream===source&&current(id,user))window.refreshNativeFiles?.({workspaceId:row.workspace_id,owner:user});},400);}
    // Coalesce token/part bursts into bounded snapshots. The native SSE
    // transport stays immediate; only expensive full-history reads are paced.
    const MESSAGE_REFRESH_MS=50;
    let dirty={messages:false,status:false,controls:false,todos:false};
    async function flush(){
      timer=null;if(pending||stream!==source||!current(id,user))return;
      const work=dirty;dirty={messages:false,status:false,controls:false,todos:false};pending=true;
      try{
        // Native SSE text must render before slow history/status requests.
        if(work.messages){
          const needsNativeRead=needsSnapshot;needsSnapshot=false;
          await refreshMessages();lastMessageRead=Date.now();
          if(needsNativeRead)void history(id,true).then(()=>{
            if(stream===source&&current(id,user))return refreshMessages();
          }).catch(error=>{if(stream===source&&current(id,user))$('#runtimeStatus').textContent=error.message;});
        }
        if(work.status)void Promise.resolve().then(()=>window.refreshWorkspaceSessionStatus?.()).catch(error=>{if(stream===source&&current(id,user))$('#runtimeStatus').textContent=error.message;});
        if(work.controls)void Promise.resolve().then(()=>refreshPermissions()).catch(error=>{if(stream===source&&current(id,user))$('#runtimeStatus').textContent=error.message;});
        if(work.todos)void Promise.resolve().then(()=>window.refreshWorkspaceTodos?.(true)).catch(error=>{if(stream===source&&current(id,user))$('#runtimeStatus').textContent=error.message;});
      }catch(error){if(current(id,user)&&stream===source)$('#runtimeStatus').textContent=error.message;}
      finally{pending=false;if(stream===source&&current(id,user)&&Object.values(dirty).some(Boolean))schedule();}
    }
    function schedule(){
      if(pending||timer)return;
      const delay=dirty.messages?Math.max(0,MESSAGE_REFRESH_MS-(Date.now()-lastMessageRead)):80;
      timer=setTimeout(flush,delay);
    }
    const credentialAlerts=new Set();
    source.onmessage=event=>{
      if(stream!==source||!current(id,user))return;
      let e;try{e=JSON.parse(event.data);}catch{return;}
      if(e.id){if(eventIDs.has(e.id))return;eventIDs.add(e.id);if(eventIDs.size>2000)eventIDs.delete(eventIDs.values().next().value);}
      if(e.type==='models-dev.refreshed'||e.type==='catalog.updated'){
        snapshots.clear();window.workspaceRuntime?.clear();
        window.refreshWorkspaceChoices?.('',true).catch(error=>{if(current(id,user))$('#runtimeStatus').textContent=error.message;});
        return;
      }
      const p=e.properties||{},session=p.sessionID||p.info?.sessionID||p.part?.sessionID;
      // info.id identifies an individual MESSAGE, not a Native session.
      if(session&&session!==row.runtime_id)return;
      if(!session&&e.type.startsWith('message.')){
        const messageID=p.info?.id||p.part?.messageID||p.messageID;
        if(!histories.get(id)?.messages.some(m=>m.info?.id===messageID))return;
      }
      if(!session&&e.type.startsWith('session.'))return;
      if(e.type==='file.edited'&&relativeFile(p.file,row))filesChanged();
      if(e.type==='message.part.updated'&&p.part?.type==='tool'){
        const activity=toolActivity(p.part,row);if(!['todowrite','todoread'].includes(activity.tool))window.renderWorkspaceEventLine?.('activity',activity);
        if(activity.status==='completed'&&activity.files.some(f=>f.operation!=='inspected')&&!changedTools.has(activity.id)){changedTools.add(activity.id);filesChanged();}
      }
      // Native accepts prompt_async before the provider attempts authentication.
      // Surface the actual provider failure classification even when no text is
      // generated; never expose raw exception bodies that could contain keys.
      const nativeIssue=e.type==='session.error'?p.error:
        e.type==='session.status'&&p.status?.type==='retry'
          ?{name:'RetryError',message:p.status.message}:
        e.type==='message.updated'&&p.info?.role==='assistant'?p.info.error:null;
      if(nativeIssue){
        const failure=window.nativeDirectTest?.classifyError(nativeIssue);
        const readable=failure?.message||label(
          'Pi reported an error from the selected provider.',
          'أبلغ Pi عن خطأ من مزود النموذج.');
        const token=String(failure?.kind||'unknown')+':'+String(p.info?.id||p.messageID||'current');
        const state=document.getElementById('runtimeStatus');
        if(state)state.textContent=readable;
        const submission=document.getElementById('submissionStatus');
        if(submission)submission.textContent=readable;
        if(!credentialAlerts.has(token)){
          credentialAlerts.add(token);
          if(credentialAlerts.size>20)credentialAlerts.delete(credentialAlerts.values().next().value);
          toast(readable);
        }
        // A model/provider error may be delivered as assistant.message.error
        // without a matching session.error event. Ask Native for the true
        // execution state instead of leaving the composer stuck on "working".
        void synchronizeStatus(row,id,()=>stream===source&&current(id,user))
          .then(()=>{
            if(stream!==source||!current(id,user))return;
            if(statuses.get(id)==='idle')statuses.set(id,'failed');
            if(activeSession?.id===id)activeSession.execution_status=statuses.get(id)||'failed';
            return window.refreshWorkspaceSessionStatus?.();
          }).catch(()=>{});
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
    source.onopen=()=>{
      if(!current(id,user)||stream!==source)return;
      void synchronizeStatus(row,id,()=>current(id,user)&&stream===source)
        .catch(error=>{if(current(id,user)&&stream===source)$('#runtimeStatus').textContent=error.message;});
      if(opened)filesChanged();needsSnapshot=opened||!histories.has(id);
      opened=true;dirty={messages:true,status:true,controls:true,todos:true};schedule();
    };
    source.onerror=()=>{if(current(id,user)&&stream===source)$('#runtimeStatus').textContent='Reconnecting to native Pi';};
    const close=source.close.bind(source);source.close=()=>{clearTimeout(timer);clearTimeout(fileTimer);close();};
  }
  function stop(){stream?.close();stream=null;streamId='';}
  async function forceStop(id){
    const user=owner(),generation=epoch;
    sendGenerations.set(id,(sendGenerations.get(id)||0)+1);
    submissionsInFlight.get(id)?.abort();
    return coalesce('abort:'+id,async()=>{
      const row=await context(id);
      if(owner()!==user||epoch!==generation)throw Error('Authenticated account changed');
      // Abort immediately via the EXISTING Pi Native session endpoint.
      // A file-read/history request must never precede or gate cancellation.
      await native(row.workspace_id,'session/'+encodeURIComponent(row.runtime_id)+'/abort',{}, {timeout:8000});
      let stopped=false;
      // Native abort may acknowledge while a running read/model is winding
      // down. Poll authoritative Native status; don't invent local idle.
      for(let attempt=0;attempt<10;attempt++){
        if(owner()!==user||epoch!==generation)throw Error('Authenticated account changed');
        const live=await native(row.workspace_id,'session/status',undefined,{timeout:8000});
        if(!live||typeof live!=='object'||Array.isArray(live))throw Error('Native session status is unavailable');
        const state=live[row.runtime_id];
        if(state===undefined||state?.type==='idle'){stopped=true;break;}
        if(attempt!==9)await new Promise(resolve=>setTimeout(resolve,850));
      }
      if(!stopped)throw Error(label('Native has not confirmed Stop yet. Keep your draft and retry Stop or Recover; no history was deleted.','لم يؤكد Pi التوقف بعد. احتفظ بالمسودة وحاول الإيقاف أو الاستعادة مجددًا؛ لم يُحذف سجل المحادثة.'));
      if(owner()!==user||epoch!==generation)throw Error('Authenticated account changed');
      uncertain.delete(id);try{sessionStorage.removeItem(storageKey('uncertain',id));}catch{}
      statuses.set(id,'idle');if(current(id,user))activeSession.execution_status='idle';
      return {status:'idle'};
    });
  }
  async function send(id,{text,providerID,modelID,agent,variant,files=[]}){
    const row=await context(id);
    if(blocked(id))throw Error(label('Recover this conversation before sending. Your draft is preserved.','استعد هذه المحادثة قبل الإرسال. مسودتك محفوظة.'));
    const user=owner(),sendEpoch=epoch,sendGeneration=sendGenerations.get(id)||0,seenStatus=statusEvents.get(id)||0;select(id,{providerID,modelID,agent,variant});
    if(streamId!==id)await start();
    const bytes=new Uint8Array(14);crypto.getRandomValues(bytes);const alphabet='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';
    const messageID='msg_'+((BigInt(Date.now())*4096n)&0xffffffffffffn).toString(16).padStart(12,'0')+Array.from(bytes,b=>alphabet[b%alphabet.length]).join('');
    const parts=[{type:'text',text},...files.map(f=>({
      type:'file',
      mime:f.mime||({'png':'image/png','jpg':'image/jpeg','jpeg':'image/jpeg','webp':'image/webp','pdf':'application/pdf','txt':'text/plain','json':'application/json'}[String(f.path||'').split('.').at(-1)?.toLowerCase()]||'application/octet-stream'),
      url:f.url||row.file_base+String(f.path).split('/').map(encodeURIComponent).join('/'),
      filename:f.name||String(f.path).split('/').at(-1)
    }))];
    const pending={messageID,text,files:files.map(f=>({path:f.path,mime:f.mime,name:f.name})),providerID,modelID,agent,variant};uncertain.set(id,pending);try{sessionStorage.setItem(storageKey('uncertain',id),JSON.stringify(pending));}catch{}
    const submissionController=new AbortController();submissionsInFlight.set(id,submissionController);
    try{await native(row.workspace_id,'session/'+encodeURIComponent(row.runtime_id)+'/prompt_async',{
      messageID,model:{providerID,modelID},...(variant?{variant}:{}),...(agent?{agent}:{}),parts},{signal:submissionController.signal,timeout:30000});}
    catch(error){
      // A user-initiated Stop/attachment cancellation MUST release the
      // original submission immediately. A message-history GET can itself
      // remain blocked on an interrupted image read; do not await it here.
      // forceStop owns the subsequent Native abort + idle verification and
      // only that path clears the pending message receipt.
      if(submissionController.signal.aborted&&
         (sendGenerations.get(id)||0)!==sendGeneration&&
         owner()===user&&epoch===sendEpoch)
        throw Error(label('Submission interrupted by Stop. The session can resume after Native confirms idle.',
                          'قوطع إرسال المرفق بالإلغاء. يمكن متابعة المحادثة بعد أن يؤكد Pi التوقف.'));
      // The HTTP response can fail after Native accepted an async prompt.
      // Resolve the exact Native message ID against authoritative history
      // before reporting uncertainty. Never send the prompt a second time.
      let confirmed=Boolean(pending.accepted);
      if(!confirmed&&owner()===user&&epoch===sendEpoch){
        try{
          const messages=await freshHistory(id);
          confirmed=Boolean(pending.accepted)||messages.some(message=>message.info?.id===messageID);
        }catch(_historyError){
          // Keep the original transport error and uncertain receipt.
        }
      }
      if(epoch!==sendEpoch||owner()!==user)throw Error('Authenticated account changed');
      if((sendGenerations.get(id)||0)!==sendGeneration)throw Error(label('Submission interrupted by Stop. Review history before sending again.','قوطع الطلب بالإيقاف. راجع السجل قبل الإرسال مجددًا.'));
      if(!confirmed){
        if(owner()===user&&(!error.status||error.status===408||error.status>=500))
          error.message=label('Pi receipt could not be confirmed. Your draft is saved; check session status.','تعذر تأكيد استلام Pi للطلب. المسودة محفوظة؛ تحقق من حالة الجلسة.')+(error.status?' (HTTP '+error.status+')':'');
        else if(owner()===user){uncertain.delete(id);try{sessionStorage.removeItem(storageKey('uncertain',id));}catch{}}
        throw error;
      }
    }finally{if(submissionsInFlight.get(id)===submissionController)submissionsInFlight.delete(id);}

    if(owner()!==user||epoch!==sendEpoch||(sendGenerations.get(id)||0)!==sendGeneration)return;
    
    uncertain.delete(id);try{sessionStorage.removeItem(storageKey('uncertain',id));}catch{}
    if((statusEvents.get(id)||0)===seenStatus)statuses.set(id,'submitted');
    if(activeSession?.id===id)activeSession.execution_status=statuses.get(id)||'submitted';
    // The native acknowledgment is final for submission. Live/reconnect SSE
    // reconciles execution; a second status read cannot undo the acknowledgment.
  }
  // Native owns both cancellation and subsequent execution. Never touch another session.
  async function replaceRunningModel(id,providerID,modelID){
    const row=await context(id),messages=await history(id,true);
    const last=[...messages].reverse().find(m=>m.info?.role==='user'&&m.info?.model);
    const previous=last?.info?.model;
    if(!previous||previous.providerID===providerID&&previous.modelID===modelID)
      throw Error(label('The running model has not changed; wait for this turn or stop it.','لم يتغير النموذج الجاري؛ انتظر انتهاء هذا الرد أو أوقفه.'));
    const live=await native(row.workspace_id,'session/status');
    if(!live||typeof live!=='object'||Array.isArray(live))throw Error('Native session status is unavailable');
    if((live[row.runtime_id]?.type||'idle')==='idle')return {interrupted:false,previous};
    await sessionRequest(id,'abort',{});
    // Confirm native completion before allowing the replacement prompt.
    const check=await native(row.workspace_id,'session/status');
    if(!check||typeof check!=='object'||Array.isArray(check))throw Error('Native session status is unavailable');
    if((check[row.runtime_id]?.type||'idle')!=='idle')throw Error(label('Pi is still stopping. Retry after it becomes idle.','Pi ما زال يوقف التنفيذ؛ أعد المحاولة بعد توقفه.'));
    statuses.set(id,'idle');
    return {interrupted:true,previous};
  }
  function pendingAttachment(id){
    let item=uncertain.get(id);
    if(!item){try{item=JSON.parse(sessionStorage.getItem(storageKey('uncertain',id))||'null');}catch{}}
    if(item&&Array.isArray(item.files)&&item.files.length)return true;
    const messages=histories.get(id)?.messages||[];
    const lastUser=[...messages].reverse().find(m=>m.info?.role==='user');
    // Native history is authoritative for accepted attachments; do not
    // fabricate a separate upload/attachment execution state.
    return Boolean(lastUser?.parts?.some(part=>part.type==='file')&&statuses.get(id)==='submitted');
  }
  async function cancelPendingAttachment(id){
    const user=owner(),generation=epoch;
    // The UI only exposes this action for a known attachment operation.
    // Do NOT query Native history before Stop: a blocked file read can make
    // that request hang and prevent the abort from ever being sent.
    if(!pendingAttachment(id))
      throw Error(label('No attachment task in this conversation.','لا توجد مهمة مرفق في هذه المحادثة.'));
    await forceStop(id);
    if(owner()!==user||generation!==epoch)throw Error('Authenticated account changed');
    if(current(id,user)){activeSession.execution_status='idle';await start();}
    return {cancelled:true};
  }
  async function recover(id,{release=false}={}){
    const user=owner(),generation=epoch;
    const result=await coalesce('recover:'+id,async()=>{
      const row=await context(id);await freshHistory(id);
      await synchronizeStatus(row,id,()=>owner()===user&&epoch===generation);
      if(owner()!==user||epoch!==generation)throw Error('Authenticated account changed');
      return {blocked:blocked(id),status:statuses.get(id)||'idle'};
    });
    if(release&&result.blocked){
      if(result.status!=='idle')throw Error(label('Stop the running conversation before clearing uncertainty.','أوقف المحادثة الجارية قبل إزالة حالة عدم اليقين.'));
      if(owner()!==user||epoch!==generation)throw Error('Authenticated account changed');
      uncertain.delete(id);try{sessionStorage.removeItem(storageKey('uncertain',id));}catch{}
      result.blocked=false;result.released=true;
    }
    if(current(id,user)){activeSession.execution_status=result.status;await start();}
    return result;
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
      // One explicit click for this displayed snapshot only; future requests are
      // never included. Each request still passes the existing server checks.
      if(items.length>1&&names[permission]){
        const batch=document.createElement('button');batch.type='button';batch.dataset.reply='batch-once';batch.textContent=label('Allow displayed requests once','السماح للطلبات المعروضة مرة واحدة')+' ('+items.length+')';
        const keys=items.map(item=>user+':'+id+':'+item.id);batch.disabled=keys.some(key=>permissionReplies.has(key));
        batch.onclick=async()=>{
          if(!current(id,user)||keys.some(key=>permissionReplies.has(key)))return;
          keys.forEach(key=>permissionReplies.add(key));section.querySelectorAll('button').forEach(button=>button.disabled=true);
          try{for(const item of items){if(!current(id,user))break;await api('/api/sessions/'+id+'/permissions/'+encodeURIComponent(item.id),{method:'POST',body:JSON.stringify({reply:'once'})});}}
          catch(error){if(current(id,user))toast(error.message);}
          finally{keys.forEach(key=>permissionReplies.delete(key));if(current(id,user)){box.nativeSignature='';try{await refreshPermissions();}catch(error){section.querySelectorAll('button').forEach(button=>button.disabled=false);toast(error.message);}}}
        };section.append(batch);
      }
      for(const item of items){const actionKey=user+':'+id+':'+item.id;const card=document.createElement('div');card.className='chat-approval';card.dataset.permissionId=item.id;
        const candidates=['read','edit','write','apply_patch'].includes(permission)?[item.metadata?.filepath,...(item.patterns||[])]:['glob','grep','list'].includes(permission)?[item.metadata?.path]:[];
        const paths=[...new Set(candidates.map(value=>relativeFile(value,row)).filter(Boolean))].slice(0,8);
        if(paths.length){const list=document.createElement('ul');for(const path of paths){const li=document.createElement('li');li.textContent=path;li.dir='auto';list.append(li);}card.append(list);}
        // Native direct TEST keeps permission replies in Pi: once/reject only.
        // Gateway's legacy persistent remember endpoint is not a Native feature.
        const rememberFile=false; // Never use Python to read/patch Native permission state.
        const note=document.createElement('small');note.textContent=rememberFile?label('Allow once, or remember these files for later prompts in this conversation. The current run may still ask.','اسمح مرة، أو تذكّر هذه الملفات للرسائل القادمة في هذه المحادثة. قد يظل التشغيل الحالي يطلب الموافقة.'):window.nativeDirectTest?.testHost?.()?label('This Native permission request only.','طلب الإذن هذا داخل Pi فقط.'):label('This request only. Gateway verifies ownership and policy.','لهذا الطلب فقط. تتحقق البوابة من الملكية والسياسة.');card.append(note);
        const controls=document.createElement('div');controls.className='chat-approval-actions';
        for(const [text,reply] of [[label('Allow once','السماح مرة واحدة'),'once'],...(rememberFile?[[label('Remember these files','تذكّر هذه الملفات'),'remember']]:[]),[label('Reject','رفض'),'reject']]){const button=document.createElement('button');button.textContent=text;button.type='button';button.dataset.reply=reply;
          button.disabled=permissionReplies.has(actionKey)||reply==='once'&&!names[permission];
          button.onclick=async()=>{
            if(!current(id,user)||permissionReplies.has(actionKey))return;permissionReplies.add(actionKey);card.dataset.sending='1';card.setAttribute('aria-busy','true');card.querySelectorAll('button').forEach(n=>n.disabled=true);
            try{if(!current(id,user))return;await api('/api/sessions/'+id+'/permissions/'+encodeURIComponent(item.id),{method:'POST',body:JSON.stringify({reply})});if(!current(id,user))return;permissionReplies.delete(actionKey);box.nativeSignature='';await refreshPermissions();}
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
    const directMode=Boolean(window.nativeDirectTest?.active?.());
    // The connection dashboard owns one shared account inventory, backed by
    // Pi's actual Native catalog. Opening a project must not reload it.
    // Use the configured/connected Native providers (cached) for the composer,
    // not the full 7 MB discovery catalog.
    const inventory=directMode?await window.nativeDirectTest.workspaceRegistry():null;
    const [providers,agents]=directMode
      ?[inventory.data,inventory.agents]
      :await Promise.all([native(id,'provider'),native(id,'agent')]);
    if(!Array.isArray(providers.all)||!Array.isArray(providers.connected)||!Array.isArray(agents))
      throw Error('Invalid native discovery schema');
    const connected=new Set(providers.connected);
    // Show the saved Pi provider catalog automatically, including unlinked
    // providers for read-only model browsing. Only verified connections
    // can execute; catalog visibility is never permission to use an API key.
    const first=[...providers.all].filter(
      (p,i,rows)=>p?.id&&rows.findIndex(q=>q?.id===p.id)===i
    ).sort((a,b)=>String(a.name||a.id).localeCompare(String(b.name||b.id)));
    return {native:true,loadedAt:Date.now(),workspace_id:String(id),health:{healthy:true},
      version:configuration.version,status:'ready',errors:{},
      agents:agents.filter(a=>a?.name&&!a.hidden&&['primary','all'].includes(a.mode)),
      default_agent:null,generation:'pi-native',revision:'pi-catalog',
      policy_revision:'pi-native',
      providers:first.map(p=>({
        ...p,connected:connected.has(p.id),allowed:true,visible:true,
        default_model:providers.default?.[p.id],
        models:Object.entries(p.models||{}).filter(([,m])=>m?.enabled!==false)
          .map(([mid,m])=>({...m,id:mid,allowed:true,visible:true}))
      }))};
  }
  window.nativeSession={ready,active,route,start,stop,send,recover,forceStop,pendingAttachment,cancelPendingAttachment,replaceRunningModel,permissions,requests,discovery,select,selection,blocked,invalidate:id=>id?snapshots.delete(id):snapshots.clear(),peek:id=>snapshots.get(id),clear};
  window.addEventListener('authentication-cleared',clear);
  window.addEventListener('account-provider-changed',()=>{snapshots.clear();discoveryReads.clear();});
})();
