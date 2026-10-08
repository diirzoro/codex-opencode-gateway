/* User/workspace-scoped discovery. Cached UI may render while runtime state is verified. */
(() => {
  const states=new Map(),prefix='og-runtime-v4:',freshFor=60000;
  // Retire snapshots from before curated discovery, including old full-model data.
  try{for(let i=sessionStorage.length-1;i>=0;i--){const name=sessionStorage.key(i);if(name?.startsWith('og-runtime-v2:')||name?.startsWith('og-runtime-v3:'))sessionStorage.removeItem(name);}}catch(error){}
  const user=()=>typeof currentUser==='undefined'?'':String(currentUser?.id||'');
  const key=id=>prefix+encodeURIComponent(user())+':'+encodeURIComponent(id);
  function stateFor(id){
    const cacheKey=key(id);let state=states.get(cacheKey);
    if(!state){
      state={cacheKey,snapshot:null,agents:null,models:new Map(),modelPending:new Map(),checked:0,revision:0,pending:{},validation:null};
      try{const saved=JSON.parse(sessionStorage.getItem(cacheKey)||'null');if(saved?.workspace_id===String(id)&&user())state.snapshot=saved;}catch(error){}
      if(state.snapshot)state.agents=state.snapshot;
      states.set(cacheKey,state);
    }
    return state;
  }
  const sameRuntime=(one,two)=>one?.generation===two?.generation&&one?.revision===two?.revision;
  async function validate(id,state){
    if(state.checked&&Date.now()-state.checked<freshFor)return true;
    if(state.validation)return state.validation;
    const revision=state.revision,owner=user();
    state.validation=api('/api/workspaces/'+encodeURIComponent(id)+'/runtime/state').then(meta=>{
      if(meta.workspace_id!==String(id))throw new Error('Unexpected workspace runtime');
      if(user()!==owner)throw new Error('Authenticated session changed');
      if(revision!==state.revision)return false;
      if(!sameRuntime(state.snapshot||state.agents,meta)||(state.snapshot&&state.snapshot.policy_revision!==meta.policy_revision)){
        state.snapshot=state.agents=null;state.models.clear();try{sessionStorage.removeItem(state.cacheKey);}catch(error){}return false;
      }
      if(!meta.cache_valid)return false;
      state.checked=Date.now();return true;
    }).finally(()=>{state.validation=null;});
    return state.validation;
  }
  async function load(id,kind,{force=false}={}){
    if(!user())throw new Error('Authentication required');
    const owner=user(),state=stateFor(id),revision=state.revision;
    const pending=state.pending[kind];
    if(pending){
      if(pending.revision===revision){const result=await pending.promise;if(user()!==owner)throw new Error('Authenticated session changed');return revision===state.revision?result:load(id,kind,{force:true});}
      await pending.promise.catch(()=>{});return load(id,kind,{force:true});
    }
    const run=(async()=>{
      if(!force&&state[kind]&&await validate(id,state)&&state[kind])return state[kind];
      const started=performance.now(),suffix=kind==='agents'?'/agents':'';
      const result=await api('/api/workspaces/'+encodeURIComponent(id)+'/runtime'+suffix+(force&&kind==='snapshot'?'?refresh=true':''));
      if(result.workspace_id!==String(id))throw new Error('Unexpected workspace runtime');
      if(user()!==owner)throw new Error('Authenticated session changed');
      if(revision===state.revision){
        // A concurrent full snapshot is authoritative if an older agent reply arrives last.
        if(kind==='agents'&&state.snapshot&&!sameRuntime(state.snapshot,result))return state.snapshot;
        state[kind]=result;
        if(kind==='snapshot'){
          for(const [providerId,models] of state.models)if(!sameCatalog(models,result))state.models.delete(providerId);
          state.agents=result;
          state.checked=Object.keys(result.errors||{}).length?0:Date.now();
          if(!Object.keys(result.errors||{}).length){try{sessionStorage.setItem(key(id),JSON.stringify(result));}catch(error){}}
        }
      }
      performance.measure('OpenCode '+kind+' '+id,{start:started,end:performance.now()});
      return result;
    })();
    const promise=run.finally(()=>{if(state.pending[kind]?.promise===promise)delete state.pending[kind];});
    state.pending[kind]={revision,promise};
    const result=await promise;
    if(user()!==owner)throw new Error('Authenticated session changed');
    return revision===state.revision?result:load(id,kind,{force:true});
  }
  const sameCatalog=(one,two)=>sameRuntime(one,two)&&one?.policy_revision===two?.policy_revision;
  async function loadModels(id,providerId){
    if(!user())throw new Error('Authentication required');
    const owner=user(),state=stateFor(id),revision=state.revision;
    const pending=state.modelPending.get(providerId);
    if(pending?.revision===revision)return pending.promise;
    const run=(async()=>{
      const snapshot=await load(id,'snapshot');
      if(owner!==user()||revision!==state.revision)throw new Error('Workspace state changed; retry model loading');
      const cached=state.models.get(providerId);
      if(cached&&sameCatalog(cached,snapshot))return cached;
      const result=await api('/api/workspaces/'+encodeURIComponent(id)+'/providers/'+encodeURIComponent(providerId)+'/models');
      if(result.workspace_id!==String(id)||result.provider_id!==providerId)throw new Error('Unexpected workspace provider models');
      if(owner!==user())throw new Error('Authenticated session changed');
      if(revision!==state.revision)throw new Error('Runtime state changed; retry model loading');
      if(!sameCatalog(result,state.snapshot)){
        if(sameCatalog(snapshot,state.snapshot))window.workspaceRuntime.invalidate(id);
        throw new Error('Runtime state changed; retry model loading');
      }
      if(!Array.isArray(result.models))throw new Error('Invalid OpenCode model response');
      state.models.set(providerId,result);return result;
    })();
    const promise=run.finally(()=>{if(state.modelPending.get(providerId)?.promise===promise)state.modelPending.delete(providerId);});
    state.modelPending.set(providerId,{revision,promise});return promise;
  }
  window.workspaceRuntime={
    load(id,options){return load(id,'snapshot',options);},
    loadAgents(id,options){return load(id,'agents',options);},
    loadModels,
    peekModels(id,providerId){const state=stateFor(id),models=state.models.get(providerId);return models&&sameCatalog(models,state.snapshot)?models:null;},
    invalidate(id){const state=stateFor(id);state.snapshot=state.agents=null;state.models.clear();state.checked=0;state.revision++;try{sessionStorage.removeItem(key(id));}catch(error){}},
    peek(id){return stateFor(id).snapshot;},
    peekAgents(id){return stateFor(id).agents;},
    clear(){states.clear();try{for(let i=sessionStorage.length-1;i>=0;i--){const name=sessionStorage.key(i);if(name?.startsWith(prefix))sessionStorage.removeItem(name);}}catch(error){}}
  };
})();
