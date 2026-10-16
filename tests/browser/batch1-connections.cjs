// Batch 1 only: no real provider requests, screenshots or signup journeys.
const {chromium}=require('playwright'),fs=require('fs'),path=require('path'),http=require('http'),assert=require('assert');
const root=path.resolve(__dirname,'../..');
const server=http.createServer((req,res)=>{
 const target=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname.replace(/\/$/,'/index.html'));
 if(!target.startsWith(root+path.sep)){res.writeHead(403).end();return;}
 try{res.setHeader('Content-Type',target.endsWith('.js')?'application/javascript':target.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(target));}catch{res.writeHead(404).end();}
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--disable-features=Vulkan']});
 try{
  for(const scenario of ['reauthorize','composer']){
   const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.addInitScript({content:'if(window.top===window){'+fs.readFileSync(path.join(__dirname,'fixture.js'),'utf8')+`
    const original=window.previewResponse;window.calls=[];window.remoteRevision=1;window.connected=false;window.authStatus='refresh_required';
    window.snapshot=()=>({workspace_id:'1',generation:'batch1',revision:window.remoteRevision,policy_revision:'p'+window.remoteRevision,status:'ready',version:'1.18.32',health:{healthy:true,version:'1.18.32'},agents:[{name:'build',mode:'primary'}],config:{},errors:{},providers:[{id:'opencode',name:'OpenCode',connected:true,allowed:true},...(window.connected?[{id:'example',name:'Example',connected:true,allowed:true,auth_status:window.authStatus}]:[])]});
    window.previewResponse=url=>{const p=new URL(url,location.origin).pathname;
     if(p==='/api/auth/me')return {data:window.previewProfile};
     if(p==='/api/workspaces'||p==='/api/projects')return {data:[]};
     if(p==='/api/projects/1')return {data:window.previewProject};
     if(p==='/api/opencode/catalog/providers')return {data:[{id:'example',name:'Example',connected:true,allowed:true,model_count:1,auth_type:'oauth',auth_status:window.authStatus}]};
     if(p==='/api/opencode/connections/example/options')return {data:{auth_methods:[{type:'api',label:'API key'},{type:'oauth',label:'OAuth'}],models:[]}};
     if(['/runtime','/runtime/agents','/runtime/state'].some(s=>p.endsWith(s)))return {data:{...window.snapshot(),cache_valid:true}};
     if(p.endsWith('/providers/opencode/models'))return {data:{...window.snapshot(),provider_id:'opencode',connected:true,allowed:true,default_model:'preview',models:[{id:'preview',name:'Preview model',allowed:true}]}};
     return original(url);};
    window.fetch=async(url,opts={})=>{const p=new URL(url,location.origin).pathname;window.calls.push({path:p,method:opts.method||'GET'});
     if(p.endsWith('/oauth/authorize')){window.authorization=JSON.parse(opts.body);return Response.json({method:'code',url:'https://provider.invalid/oauth',instructions:'Fixture authorization'});}
     if(p.endsWith('/oauth/callback')){window.authStatus='connected';return Response.json({connected:true,persisted:true});}
     if(p.endsWith('/connections/example/credentials')){window.connected=true;window.authStatus='connected';window.remoteRevision++;return Response.json({connected:true,persisted:true});}
     const {data,status=200}=window.previewResponse(String(url));return Response.json(data,{status});};
    localStorage.clear();
   }`});
   await page.goto('http://127.0.0.1:'+server.address().port);
   if(scenario==='reauthorize'){
    await page.evaluate(async()=>{await navigationReady;await window.openConnections('providers');});
    const combo=page.locator('input[role=combobox]');await combo.click();await combo.fill('E');
    await page.locator('.provider-combo-option').filter({hasText:'Example'}).click();
    await page.getByRole('button',{name:'إعادة التفويض',exact:true}).click();
    await page.locator('.provider-auth-dialog select[name=auth_method]').waitFor();
    assert.equal(await page.locator('.provider-auth-dialog select[name=auth_method] option').count(),1);
    assert.equal(await page.locator('.provider-auth-dialog select[name=auth_method]').inputValue(),'1');
    await page.locator('.provider-auth-dialog button[type=submit]').click();
    await page.locator('.provider-oauth input[name=code]').fill('fixture-code');
    await page.getByRole('button',{name:'أكمل التفويض',exact:true}).click();
    await page.locator('.provider-auth-dialog').waitFor({state:'detached'});
    assert.deepEqual(await page.evaluate(()=>window.authorization),{method:1,inputs:{},reauthorize:true});
    console.log('PASS Batch 1: explicit OAuth reauthorization without project; native method index retained');
   }else{
    await page.evaluate(async()=>{await window.openWorkspacePreview();});
    const session=await page.evaluate(()=>activeSession.id);
    await page.evaluate(()=>api('/api/opencode/connections/example/credentials',{method:'POST',body:'{}'}));
    await page.locator('#providerSelect option[value=example]').waitFor({state:'attached'});
    await page.evaluate(()=>{window.authStatus='reauthorization_required';window.remoteRevision++;});
    try{await page.locator('#providerSelect option[value=example]').waitFor({state:'detached',timeout:16000});}
    catch(error){console.error('COMPOSER DIAGNOSTIC',await page.evaluate(()=>({hidden:document.hidden,activePage:document.querySelector('.page.active')?.id,workspace:activeWorkspace?.id,cache:window.workspaceRuntime.peek('1'),calls:window.calls.slice(-12)})));throw error;}
    assert.equal(await page.evaluate(()=>activeSession.id),session);
    assert((await page.evaluate(()=>window.calls)).some(c=>c.path.endsWith('/runtime/state')));
    console.log('PASS Batch 1: account mutation refreshes Composer; remote auth failure refreshes availability without changing session');
   }
   assert.deepEqual(errors,[]);await page.close();
  }
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
