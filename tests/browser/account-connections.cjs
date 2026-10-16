// Browser regression over real frontend files with explicitly mocked Gateway APIs.
// NODE_PATH=<playwright modules> CHROMIUM_EXECUTABLE=<binary> node tests/browser/account-connections.cjs
const {chromium}=require('playwright'),fs=require('fs'),path=require('path'),http=require('http'),assert=require('assert');
const root=path.resolve(__dirname,'../..');
const server=http.createServer((req,res)=>{const file=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname.replace(/\/$/,'/index.html'));if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return;}try{res.setHeader('Content-Type',file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));}catch{res.writeHead(404).end();}});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--disable-features=Vulkan']});
 try{for(const missing of [false,true]){
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript({content:'if(window.top===window){'+fs.readFileSync(path.join(__dirname,'fixture.js'),'utf8')+`
   const oldResponse=window.previewResponse;window.auditCalls=[];
   window.previewResponse=url=>{const p=new URL(url,location.origin).pathname;
    if(p==='/api/auth/me')return {data:window.previewProfile};
    if(p==='/api/workspaces')return {data:${missing}?[window.previewProject.workspaces[0]]:[]};
    if(p==='/api/projects')return {data:${missing}?[window.previewProject]:[]};
    if(p==='/api/workspaces/1'&&${missing})return {data:{...window.previewProject.workspaces[0],files_available:false}};
    if(p==='/api/dashboard'&&!${missing})return {data:{projects:[],recent_sessions:[]}};
    if(p==='/api/opencode/catalog/providers')return {data:[{id:'example',name:'Example',allowed:true,connected:window.auditConnected===true,model_count:1}]};
    if(p==='/api/opencode/connections/example/options')return {data:{provider_id:'example',auth_methods:[{type:'api',label:'API key'}],models:[{id:'example-model',name:'Example model'}]}};
    if(p.includes('/runtime')&&${missing})return {status:409,data:{detail:'Workspace files are missing'}};
    return oldResponse(url);};
   window.fetch=async(url,opts={})=>{window.auditCalls.push(String(url));
    if(String(url)==='/api/opencode/connections/example/credentials'&&opts.method==='POST'){window.auditConnected=true;return new Response(JSON.stringify({connected:true,persisted:true,deferred_workspace_count:1,last4:'1234',validated_model:'example-model'}),{status:200,headers:{'Content-Type':'application/json'}});}
    if(String(url)==='/api/opencode/connections/example'&&opts.method==='DELETE'){window.auditConnected=false;return new Response(null,{status:204});}
    const {data,status=200}=window.previewResponse(String(url));return new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});};
   localStorage.clear();
  }`});
  await page.goto('http://127.0.0.1:'+server.address().port);
  await page.evaluate(async(missing)=>{await navigationReady;
   if(missing){activeWorkspace=window.previewProject.workspaces[0];activeProject=window.previewProject;}
   await window.openConnections('providers');
  },missing);
  await page.locator('.provider-loading').filter({hasText:'مزوّدات الحساب جاهزة'}).waitFor({timeout:3000});
  const combo=page.locator('input[role=combobox]');await combo.click();await combo.fill('E');
  const option=page.locator('.provider-combo-option').filter({hasText:'Example'});await option.waitFor();await option.click();
  await page.locator('.provider-combo-status').getByRole('button',{name:'ربط',exact:true}).click({timeout:2500});
  await page.locator('.provider-auth-dialog').waitFor();
  await page.locator('.provider-auth-dialog input[name=api_key]').fill('fixture-only-key1234');
  await page.locator('.provider-auth-dialog select[name=model_id]').selectOption('example-model');
  await page.locator('.provider-auth-dialog button[type=submit]').click();
  await page.locator('.provider-auth-dialog').waitFor({state:'detached'});
  assert((await page.locator('#toast').innerText()).includes('تحتاج تحديثًا'));
  await page.locator('.provider-combo-status span').filter({hasText:/^متصل ·/}).waitFor();
  assert((await page.evaluate(()=>window.auditCalls)).some(p=>p==='/api/opencode/connections/example/options'));
  assert(!(await page.evaluate(()=>window.auditCalls)).some(p=>p.includes('/providers/resolve')));
  // Same account view remains usable across layout/language changes.
  await page.evaluate(async()=>{lang='en';applyPrefs();await window.openConnections('providers');});
  assert.equal(await page.locator('html').getAttribute('dir'),'ltr');
  await page.locator('.provider-loading').filter({hasText:'Account providers ready'}).waitFor();
  await page.setViewportSize({width:390,height:844});
  assert(await page.locator('input[role=combobox]').isVisible());
  const inputBox=await page.locator('input[role=combobox]').boundingBox();
  assert(inputBox.x>=0&&inputBox.x+inputBox.width<=391);
  await page.evaluate(async()=>{lang='ar';applyPrefs();await window.openConnections('providers');});
  assert.equal(await page.locator('html').getAttribute('dir'),'rtl');
  await page.getByRole('button',{name:'فصل / حذف المفتاح',exact:true}).first().click();
  await page.locator('.provider-loading').filter({hasText:'مزوّدات الحساب جاهزة'}).waitFor();
  assert.equal(await page.evaluate(()=>window.auditConnected),false);
  await combo.click();await combo.fill('E');
  await page.locator('.provider-combo-option').filter({hasText:'Example'}).click();
  await page.locator('.provider-combo-status').getByRole('button',{name:'ربط',exact:true}).click();
  await page.locator('.provider-auth-dialog input[name=api_key]').fill('reconnect-fixture5678');
  await page.locator('.provider-auth-dialog select[name=model_id]').selectOption('example-model');
  await page.locator('.provider-auth-dialog button[type=submit]').click();
  await page.locator('.provider-auth-dialog').waitFor({state:'detached'});
  assert.equal(await page.evaluate(()=>window.auditConnected),true);
  await page.locator('.provider-combo-status span').filter({hasText:/^متصل ·/}).waitFor();
  if(process.env.AUDIT_SCREENSHOT_DIR){fs.mkdirSync(process.env.AUDIT_SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.AUDIT_SCREENSHOT_DIR,'connections-'+(missing?'missing-project':'no-project')+'.png'),fullPage:true});}
  assert.deepEqual(errors,[]);
  console.log('PASS account provider selection/auth options with '+(missing?'missing project files':'no project'));
  await page.close();
 }
 for(const scenario of ['deleted','missing','available']){
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript({content:'if(window.top===window){'+fs.readFileSync(path.join(__dirname,'fixture.js'),'utf8')+`
   const oldResponse=window.previewResponse;window.auditCalls=[];
   window.previewResponse=url=>{const p=new URL(url,location.origin).pathname;
    if(p==='/api/auth/me')return {data:window.previewProfile};
    if(p==='/api/projects/1')return {data:window.previewProject};
    if(p==='/api/workspaces/1')return ${scenario==='deleted'?"{status:404,data:{detail:'Not found'}}":`{data:{...window.previewProject.workspaces[0],files_available:${scenario==='available'}}}`};
    return oldResponse(url);};
   window.fetch=async(url,opts={})=>{window.auditCalls.push(String(url));const {data,status=200}=window.previewResponse(String(url));return new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});};
   localStorage.clear();localStorage.setItem('og-page','workspacePage');localStorage.setItem('og-workspace','1');
  }`});
  await page.goto('http://127.0.0.1:'+server.address().port);
  await page.evaluate(()=>navigationReady);
  assert.equal(await page.evaluate(()=>document.querySelector('.page.active')?.id),scenario==='available'?'workspacePage':'workspaceHomePage');
  if(scenario!=='available'){
   assert.equal(await page.evaluate(()=>localStorage.getItem('og-workspace')),null);
   assert(!(await page.evaluate(()=>window.auditCalls)).some(p=>p.includes('/runtime')));
   await page.locator('#homeNewProject').click();await page.locator('#onboarding.active').waitFor();
  }
  assert.deepEqual(errors,[]);console.log('PASS workspace restoration: '+scenario);
  await page.close();
 }
 {
  const page=await browser.newPage();
  await page.addInitScript({content:'if(window.top===window){'+fs.readFileSync(path.join(__dirname,'fixture.js'),'utf8')+`
   const oldResponse=window.previewResponse;window.auditCalls=[];
   window.previewResponse=url=>String(url)==='/api/auth/register'?{data:{...window.previewProfile,status:'pending_email'}}:oldResponse(url);
   window.fetch=async(url,opts={})=>{window.auditCalls.push({url:String(url),method:opts.method||'GET'});
    if(String(url)==='/api/profile'&&opts.method==='PATCH')return new Response(JSON.stringify({detail:'Authentication required'}),{status:401});
    const {data,status=200}=window.previewResponse(String(url));return new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});};localStorage.clear();
  }`});
  await page.goto('http://127.0.0.1:'+server.address().port);
  await page.evaluate(async()=>{await navigationReady;await page('authPage');});
  await page.locator('[data-auth-tab=register]').click();
  await page.locator('#registerEmail').fill('fixture@example.org');
  await page.locator('#registerPassword').fill('Fixture!Pass123');
  await page.locator('#registerPhone').fill('777123456');
  await page.locator('#registerPostal').selectOption('+967');
  await page.locator('#registerSubmit').click();
  await page.locator('#registerMessage').filter({hasText:'رابط التفعيل'}).waitFor({timeout:2500});
  assert(!(await page.evaluate(()=>window.auditCalls)).some(c=>c.url==='/api/profile'&&c.method==='PATCH'));
  assert.equal(await page.locator('#registerPassword').inputValue(),'');
  console.log('PASS pending email signup waits for verification without profile PATCH');await page.close();
 }
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
