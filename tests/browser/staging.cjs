// Real FastAPI/PostgreSQL-compatible/OpenCode staging. No Gateway API mocks.
const {chromium}=require('playwright'),assert=require('assert'),fs=require('fs'),path=require('path');
assert.equal(process.env.AUDIT_DISPOSABLE_DB,'1');
const origin='http://127.0.0.1:'+process.env.AUDIT_STAGING_PORT;
// External web fonts may be unavailable in the isolated environment.
process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY='1';
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--disable-features=Vulkan']});
 let page;const responses=[];
 try{
  page=await browser.newPage({viewport:{width:1366,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{const p=new URL(r.url()).pathname;if(p.startsWith('/api/'))responses.push({path:p,status:r.status()});});
  await page.goto(origin);await page.evaluate(async()=>{await navigationReady;await window.openAuthLogin();});
  await page.locator('[data-auth-tab=register]').click();
  const email='browser-'+Date.now()+'@example.org';
  await page.locator('#registerEmail').fill(email);await page.locator('#registerPassword').fill('Fixture!Pass123');
  await page.locator('#registerPostal').selectOption('+967');await page.locator('#registerPhone').fill('777123456');
  await page.locator('#registerSubmit').click();await page.locator('#registerMessage').filter({hasText:'رابط التفعيل'}).waitFor();
  const mail=JSON.parse(fs.readFileSync(process.env.AUDIT_MAILBOX,'utf8'));assert.equal(mail.email,email);
  await page.goto(origin+'/api/auth/verify-email?token='+encodeURIComponent(mail.token));
  await page.evaluate(async()=>{await navigationReady;await window.openAuthLogin();});
  await page.locator('#loginIdentity').fill(email);await page.locator('#loginPassword').fill('Fixture!Pass123');
  await page.locator('#loginSubmit').click();await page.locator('#workspaceHomePage.active').waitFor();
  const create=async name=>{await page.locator('#homeNewProject').click();await page.locator('#projectName').fill(name);await page.locator('#sourceType').selectOption('blank');await page.locator('#createProjectForm button[type=submit]').click();await page.locator('#workspacePage.active').waitFor();};
  await page.locator('#clientConnections').click();await page.locator('input[role=combobox]').waitFor();
  await page.locator('.provider-loading').filter({hasText:'مزوّدات الحساب جاهزة'}).waitFor({timeout:45000});
  const combo=page.locator('input[role=combobox]');await combo.click();await combo.fill('OpenAI');
  await page.locator('.provider-combo-option').filter({hasText:/^OpenAI ·/}).first().click();
  await page.locator('.provider-combo-status').getByRole('button',{name:'ربط',exact:true}).click();
  await page.locator('.provider-auth-dialog select[name=auth_method]').waitFor({timeout:45000});
  assert(await page.locator('.provider-auth-dialog select[name=auth_method] option').count()>0);
  await page.locator('.provider-auth-dialog').getByRole('button',{name:'إغلاق',exact:true}).click();
  if(process.env.AUDIT_SCREENSHOT_DIR){fs.mkdirSync(process.env.AUDIT_SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.AUDIT_SCREENSHOT_DIR,'real-staging-connections.png'),fullPage:true});}
  await page.evaluate(()=>window.openClientWorkspace());
  await create('Browser QA project');
  const owned=await page.evaluate(()=>({uid:currentUser.id,wid:activeWorkspace.id}));
  // Move only this newly-created fixture's directory; never delete customer files.
  const repo=path.join(process.env.WORKSPACE_ROOT,owned.uid,owned.wid,'repo');
  assert(repo.startsWith(process.env.WORKSPACE_ROOT+path.sep));fs.renameSync(repo,repo+'.audit-saved');
  await page.evaluate(()=>localStorage.setItem('og-page','workspacePage'));
  await page.reload();await page.locator('#workspaceHomePage.active').waitFor();
  assert.equal(await page.evaluate(()=>localStorage.getItem('og-workspace')),null);
  await create('Browser QA replacement');
  assert.notEqual(await page.evaluate(()=>activeWorkspace.id),owned.wid);
  assert.deepEqual(errors,[]);
  if(process.env.AUDIT_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.AUDIT_SCREENSHOT_DIR,'real-staging-workspace.png'),fullPage:true});
  console.log('PASS REAL STAGING: signup/verification/login, new project, owned OpenCode provider options, missing-file recovery and replacement project; no model/payment calls');
 }catch(e){
  console.error('STAGING DIAGNOSTIC',JSON.stringify({providerText:page?await page.locator('.provider-loading').allTextContents():[],responses}));
  if(page&&process.env.AUDIT_SCREENSHOT_DIR){fs.mkdirSync(process.env.AUDIT_SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.AUDIT_SCREENSHOT_DIR,'real-staging-failure.png'),fullPage:true,timeout:5000}).catch(()=>console.error('Failure screenshot unavailable'));}
  throw e;
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
