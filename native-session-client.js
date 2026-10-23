/* OpenCode 1.x native wire adapter and existing-UI presentation, not an execution engine. */
(() => {
  let identity='',configuration=null,stream=null;const rows=new Map(),snapshots=new Map(),statuses=new Map(),statusEvents=new Map(),statusReads=new Map();let epoch=0;
  const owner=()=>String(currentUser?.id||'');
  const active=()=>configuration?.enabled===true&&identity===owner();
  const current=(id,user)=>activeSession?.id===id&&owner()===user;
  async function ready(){
    const user=owner();if(!user)return false;
    if(identity!==user){clear();identity=user;}
    if(!configuration)configuration=await api('/api/native-test/state');
    if(owner()!==user)throw Error('Authenticated account changed');
    return configuration.enabled;
  }
  function clear(){epoch++;stream?.close();stream=null;identity='';configuration=null;rows.clear();snapshots.clear();statuses.clear();statusEvents.clear();statusReads.clear();}
  function remember(row){rows.set(row.id,row);return row;}
  async function context(id){if(rows.has(id))return rows.get(id);return remember(await api('/api/native-test/sessions/'+encodeURIComponent(id)));}
  const url=(workspace,path)=>'/native-session/'+encodeURIComponent(workspace)+'/'+path;
  async function native(workspace,path,body){
    return api(url(workspace,path),body===undefined?{}:{method:'POST',body:JSON.stringify(body)});
  }
  async function sessionRequest(id,suffix,body){const row=await context(id);return native(row.workspace_id,'session/'+encodeURIComponent(row.runtime_id)+(suffix?'/'+suffix:''),body);}
  async function requests(kind,id){if(!id)return [];const row=await context(id),data=await native(row.workspace_id,kind);if(!Array.isArray(data))throw Error('Invalid native request list');return data.filter(x=>x.sessionID===row.runtime_id);}
  function display(messages){
    if(!Array.isArray(messages))throw Error('Invalid native message snapshot');
    return messages.map(m=>({id:m.info.id,role:m.info.role,text:m.parts.filter(p=>p.type==='text').map(p=>p.text||'').join(''),
      activity:m.parts.filter(p=>p.type==='tool').map(p=>({id:p.id,tool:p.tool,status:p.state?.status,stage:'tool_activity'}))}));
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
    if(!tail||tail==='open'){const fresh=remember(await api('/api/native-test/sessions/'+encodeURIComponent(id)));return {value:{...fresh,status:statuses.get(id)||'idle',execution_status:statuses.get(id)||'idle'}};}
    if(tail==='messages'&&method==='GET')return {value:display(await sessionRequest(id,'message'))};
    if(tail==='todos')return {value:{items:await sessionRequest(id,'todo')}};
    if(tail==='diff')return {value:await sessionRequest(id,'diff')};
    if(tail==='stop'){await sessionRequest(id,'abort',{});return {value:{status:'idle'}};}
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
    const live=await native(row.workspace_id,'session/status');
    if(epoch!==generation||owner()!==user||statusReads.get(id)!==sequence||(statusEvents.get(id)||0)!==seen||!valid())return;
    statuses.set(id,live[row.runtime_id]?.type&&live[row.runtime_id].type!=='idle'?'submitted':'idle');
  }
  async function start(){
    stop();const id=activeSession?.id,user=owner();if(!id)return;
    const row=await context(id);if(!current(id,user))return;
    const source=new EventSource(url(row.workspace_id,'event'));stream=source;let timer,pending=false,lastMessageRead=0;
    // Coalesce token/part bursts into bounded snapshots. The native SSE
    // transport stays immediate; only expensive full-history reads are paced.
    const MESSAGE_REFRESH_MS=650;
    let dirty={messages:false,status:false,controls:false,todos:false};
    async function flush(){
      timer=null;if(pending||stream!==source||!current(id,user))return;
      const work=dirty;dirty={messages:false,status:false,controls:false,todos:false};pending=true;
      try{
        if(work.status)await window.refreshWorkspaceSessionStatus?.();
        if(stream!==source||!current(id,user))return;
        if(work.messages){await refreshMessages();lastMessageRead=Date.now();}
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
      const p=e.properties||{},session=p.sessionID||p.info?.sessionID||p.part?.sessionID||p.info?.id;
      if(session&&session!==row.runtime_id)return;
      if(['session.status','session.idle','session.error'].includes(e.type))statusEvents.set(id,(statusEvents.get(id)||0)+1);
      if(e.type==='session.status')statuses.set(id,p.status?.type==='idle'?'idle':'submitted');
      if(e.type==='session.idle')statuses.set(id,'idle');
      if(e.type==='session.error')statuses.set(id,'failed');
      if(e.type.startsWith('message.'))dirty.messages=true;
      if(e.type.startsWith('session.'))dirty.status=true;
      if(/^(permission|question)\./.test(e.type))dirty.controls=true;
      if(e.type.startsWith('todo.'))dirty.todos=true;
      if(Object.values(dirty).some(Boolean))schedule();
    };
    source.onopen=async()=>{
      if(!current(id,user)||stream!==source)return;
      try{await synchronizeStatus(row,id,()=>current(id,user)&&stream===source);}
      catch(error){if(current(id,user)&&stream===source)$('#runtimeStatus').textContent=error.message;}
      if(current(id,user)&&stream===source){dirty={messages:true,status:true,controls:true,todos:true};schedule();}
    };
    source.onerror=()=>{if(current(id,user)&&stream===source)$('#runtimeStatus').textContent='Reconnecting to native OpenCode';};
    const close=source.close.bind(source);source.close=()=>{clearTimeout(timer);close();};
  }
  function stop(){stream?.close();stream=null;}
  async function send(id,{text,providerID,modelID,agent,files=[]}){
    const row=await context(id);
    const parts=[{type:'text',text},...files.map(f=>({type:'file',mime:f.mime||({'png':'image/png','jpg':'image/jpeg','jpeg':'image/jpeg','webp':'image/webp','pdf':'application/pdf'}[f.path.split('.').at(-1)]||'application/octet-stream'),url:row.file_base+f.path.split('/').map(encodeURIComponent).join('/'),filename:f.path.split('/').at(-1)}))];
    await native(row.workspace_id,'session/'+encodeURIComponent(row.runtime_id)+'/prompt_async',{
      model:{providerID,modelID},...(row.model?.providerID===providerID&&row.model?.id===modelID&&row.model.variant?{variant:row.model.variant}:{}),...(agent?{agent}:{}),parts});
    // A failed status lookup cannot undo a native 204 acknowledgment or invite
    // an accidental resend of an already accepted prompt. SSE/history reconcile.
    try{await synchronizeStatus(row,id);}
    catch(error){if(active())$('#runtimeStatus').textContent=error.message;}
  }
  async function permissions(box,provided){
    const id=activeSession?.id,user=owner();if(!id||!box)return;const pending=provided||await requests('permission',id);if(!current(id,user))return;
    box.replaceChildren();box.hidden=!pending.length;
    for(const item of pending){const card=document.createElement('div');card.className='chat-approval';
      const title=document.createElement('strong');title.textContent=item.permission;card.append(title);
      for(const [label,reply] of [['Allow once','once'],['Reject','reject']]){const b=document.createElement('button');b.textContent=label;b.type='button';b.onclick=async()=>{if(!current(id,user))return;b.disabled=true;try{await api('/api/sessions/'+id+'/permissions/'+encodeURIComponent(item.id),{method:'POST',body:JSON.stringify({reply})});await permissions(box);}catch(error){b.disabled=false;toast(error.message);}};card.append(b);}box.append(card);
    }
  }
  async function discovery(id){
    const [providers,agents]=await Promise.all(['provider','agent'].map(path=>native(id,path)));
    if(!Array.isArray(providers.all)||!Array.isArray(providers.connected)||!Array.isArray(agents))throw Error('Invalid native discovery schema');
    const result={native:true,workspace_id:String(id),health:{healthy:true},version:'1.18.32',status:'ready',errors:{},agents,default_agent:null,
      generation:'native-test',revision:'live',policy_revision:'native',providers:providers.all.map(p=>({...p,connected:providers.connected.includes(p.id),allowed:true,
        default_model:providers.default?.[p.id],models:Object.values(p.models||{}).map(m=>({...m,allowed:true}))}))};
    snapshots.set(id,result);return result;
  }
  window.nativeSession={ready,active,route,start,stop,send,permissions,requests,discovery,peek:id=>snapshots.get(id),clear};
  window.addEventListener('authentication-cleared',clear);
})();
