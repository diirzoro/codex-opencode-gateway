/* Native-only discovery facade for the existing Dashboard/Workspace UI.
   No Gateway runtime API, persistent browser catalog or provider-key verifier. */
(() => {
  // Delete obsolete presentation snapshots; never read them as Native state.
  try{
    for(let i=sessionStorage.length-1;i>=0;i--){
      const name=sessionStorage.key(i);
      if(/^og-runtime-v[234]:/.test(name||''))sessionStorage.removeItem(name);
    }
  }catch{}
  const owner=()=>String(currentUser?.id||'');
  async function requireNative(){
    const user=owner();
    if(!user)throw Error('Authentication required');
    if(!window.nativeSession||!await window.nativeSession.ready())throw Error('Pi Coding Agent is not ready');
    if(user!==owner())throw Error('Authenticated session changed');
    return user;
  }
  async function load(id,options){
    const user=await requireNative();
    const result=await window.nativeSession.discovery(id,options);
    if(user!==owner())throw Error('Authenticated session changed');
    return result;
  }
  async function loadAgents(id,options){
    const user=await requireNative();
    if(!window.nativeDirectTest?.active())throw Error('Pi Coding Agent is not ready');
    // Pi command discovery comes from Pi's installed extensions, skills and templates.
    const rows=await window.nativeDirectTest.agents(options);
    if(user!==owner())throw Error('Authenticated session changed');
    return {native:true,workspace_id:String(id),agents:rows.filter(a=>
      a?.name&&!a.hidden&&['primary','all'].includes(a.mode)),default_agent:null};
  }
  const peek=id=>window.nativeSession?.active()?window.nativeSession.peek(id):null;
  function models(snapshot,pid){
    const provider=snapshot?.providers.find(p=>p.id===pid);
    return snapshot?{...snapshot,models:provider?.models||[],connected:provider?.connected===true,allowed:provider?.allowed!==false}:null;
  }
  window.workspaceRuntime={
    load,loadAgents,
    async loadModels(id,pid){
      const snapshot=await load(id);
      const result=models(snapshot,pid);
      if(!result?.connected||result.models.length)return result;
      // A verified link may have been saved before its first Pi model
      // metadata fetch finished. Request ONLY this account's connected
      // provider; Gateway tries a bounded, throttled one-provider import.
      // Never load the global Pi catalog into the workspace.
      const provider=snapshot?.providers?.find(p=>p.id===pid);
      if(provider?.personal_connected!==true)return result;
      const detail=await api('/api/opencode/connections/'+encodeURIComponent(pid)+'/models');
      if(!Array.isArray(detail?.models))throw Error('Invalid saved Pi model list');
      result.models=detail.models.filter(m=>m?.enabled===true&&m.admin_allowed!==false)
        .map(m=>({
          id:m.id,name:m.name||m.id,
          allowed:true,visible:true,enabled:true,
          cost:m.cost||{},
          price_type:m.price_type||'unknown',
          reasoning:m.reasoning===true,context:m.context_window
        }));
      return result;
    },
    peek,peekAgents:peek,
    peekModels(id,pid){return models(peek(id),pid);},
    clear(){window.nativeSession?.invalidate();},
    invalidate(id){window.nativeSession?.invalidate(id);}
  };
})();
