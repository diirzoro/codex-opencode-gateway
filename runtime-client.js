/* One workspace-scoped bootstrap cache. Auth changes invalidate only that workspace. */
(() => {
  const states=new Map();
  window.workspaceRuntime={
    async load(id,{force=false}={}){
      let state=states.get(id);
      if(!state){state={snapshot:null,loaded:0,pending:null,revision:0};states.set(id,state);}
      if(state.pending){if(state.pendingRevision===state.revision)return state.pending;await state.pending.catch(()=>{});return this.load(id,{force:true});}
      if(!force&&state.snapshot&&Date.now()-state.loaded<10000)return state.snapshot;
      const revision=state.revision,started=performance.now();state.pendingRevision=revision;
      state.pending=api('/api/workspaces/'+encodeURIComponent(id)+'/runtime').then(snapshot=>{
        if(state.revision===revision){state.snapshot=snapshot;state.loaded=Date.now();}
        performance.measure('OpenCode bootstrap '+id,{start:started,end:performance.now()});
        return snapshot;
      }).finally(()=>{state.pending=null;});
      return state.pending;
    },
    invalidate(id){const state=states.get(id);if(state){state.snapshot=null;state.loaded=0;state.revision++;}},
    peek(id){return states.get(id)?.snapshot;},
    clear(){states.clear();}
  };
})();
