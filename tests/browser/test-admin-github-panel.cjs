/* Actual admin loader + final registration; controlled API/DOM, not TEST login. */
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const source=fs.readFileSync('enhancements.js','utf8');
const start=source.indexOf('  let adminGithubLoad=null;'),end=source.indexOf('\n  async function loadAdminBilling()',start);
function fixture({statusError=false,configError=false,ready=true,legacy=false}={}){
 const dom=new JSDOM(`<section data-admin-panel="github"><h1>GitHub Integration Settings</h1>${legacy?'':'<div id="adminGithubPanel"></div>'}</section>`),document=dom.window.document,calls=[];
 const c={document,window:dom.window,currentUser:{id:'admin-a',role:'admin'},tr:en=>en,Map,Promise,
 textElement(tag,text='',cls=''){const n=document.createElement(tag);n.textContent=text;n.className=cls;return n;},
 async api(path){calls.push(path);if(path==='/api/auth/social/options')return {github:true};if(path==='/api/github/status'){if(statusError)throw Error('Status failed');return {configured:true,connected:false};}if(configError)throw Error('Diagnostics missing');return {editable:true,settings_schema_ready:true,credential_storage_ready:true,configured:true,app_id:123,client_id:'public-client',secrets:{private_key:true},database:{checked:true,ready,missing:ready?[]:['github_auth_states'],revisions:['0022_email_service_policies']}};}};
 c.window.renderManagement=async(root,name,platform)=>{assert.equal(root.id,'adminGithubConnections');assert.equal(platform,true);root.replaceChildren(c.textElement('h2','GitHub connections'));};
 vm.createContext(c);vm.runInContext(source.slice(start,end)+'\nglobalThis.load=loadAdminGithubAdmin;',c);
 return {c,calls,document,dom,async run(){await c.load();},close(){dom.window.close();}};
}
(async()=>{
 let count=0;async function test(name,run){await run();console.log('PASS '+name);count++;}
 await test('final registered loader preserves canonical GitHub settings instead of clearing parent',async()=>{
 const assignment=source.match(/^  ADMIN_LOADERS.github=.*;$/m)[0];assert.equal(assignment,'  ADMIN_LOADERS.github=loadAdminGithubAdmin;');
 const f=fixture();f.c.ADMIN_LOADERS={};vm.runInContext(assignment,f.c);await f.c.ADMIN_LOADERS.github();assert.equal(f.document.querySelector('input[aria-label="App ID"]').value,'123');assert.ok(f.document.querySelector('h1'));assert.ok(f.document.getElementById('adminGithubPanel'));assert.ok(f.document.body.textContent.includes('database schema is ready'));assert.equal(f.document.querySelector('button[type=submit]').disabled,false);f.close();});
 await test('duplicate navigation coalesces requests',async()=>{const f=fixture();await Promise.all([f.run(),f.run()]);assert.equal(f.calls.length,2);f.close();});
 await test('configuration remains visible when account status fails',async()=>{const f=fixture({statusError:true});await f.run();assert.equal(f.document.querySelector('input[aria-label="App ID"]').value,'123');assert.ok(f.document.body.textContent.includes('Status failed'));f.close();});
 await test('settings skeleton and error stay visible when backend is outdated',async()=>{const f=fixture({configError:true});await f.run();assert.equal(f.document.querySelectorAll('#adminGithubPanel input[aria-label]').length,13);assert.ok(f.document.body.textContent.includes('Diagnostics missing'));assert.equal(f.document.querySelector('button').disabled,true);f.close();});
 await test('legacy removed host rebuilt; missing migration is explicit and prevents authorize',async()=>{const f=fixture({legacy:true,ready:false});await f.run();assert.ok(f.document.getElementById('adminGithubPanel'));assert.ok(f.document.body.textContent.includes('github_auth_states'));assert.equal([...f.document.querySelectorAll('button')].find(b=>b.textContent==='Authorize my GitHub account').disabled,true);f.close();});
 await test('customer cannot request admin diagnostics',async()=>{const f=fixture();f.c.currentUser.role='customer';await f.run();assert.equal(f.calls.length,0);f.close();});
 await test('account switching discards late privileged response',async()=>{const f=fixture();const resolvers=[];f.c.api=()=>new Promise(r=>resolvers.push(r));const pending=f.run();f.c.currentUser={id:'other',role:'customer'};resolvers.forEach(resolve=>resolve({configured:true,app_id:'PRIVATE_ADMIN_VALUE'}));await pending;assert.ok(!f.document.body.textContent.includes('PRIVATE_ADMIN_VALUE'));assert.equal(f.document.querySelector('input[aria-label="App ID"]').value,'');f.close();});

 await test('admin edits persist through the existing PUT and secret inputs clear on success',async()=>{
 const f=fixture();await f.run();let saved;
 const original=f.c.api;f.c.api=async(path,options)=>{if(options?.method==='PUT'){saved=JSON.parse(options.body);return {saved:true};}return original(path);};
 f.document.querySelector('input[aria-label="App ID"]').value='5470256';
 f.document.querySelector('input[aria-label="App Slug"]').value='opencode-gateway-test-diirzoro';
 f.document.querySelector('input[aria-label="OAuth Client ID"]').value='test-client';
 f.document.querySelector('input[name=client_secret]').value='synthetic-not-real';
 await f.document.querySelector('form').onsubmit({preventDefault(){}});
 assert.equal(saved.app_id,5470256);assert.equal(saved.private_key,null);assert.equal(saved.client_secret,'synthetic-not-real');
 assert.equal(f.document.querySelector('input[name=client_secret]').value,'');assert.ok(!f.document.body.textContent.includes('synthetic-not-real'));f.close();});
 await test('official Native settings are read-only public metadata, without personal App defaults or automatic activation',async()=>{
 const f=fixture();await f.run();const url=f.document.querySelector('input[aria-label="MCP server URL"]');
 assert.equal(url.value,'https://api.githubcopilot.com/mcp/');assert.equal(url.readOnly,true);
 assert.equal(f.document.querySelector('input[aria-label="Transport"]').value,'remote');
 assert.ok(f.document.body.textContent.includes('have not been verified'));
 assert.ok(!f.document.body.textContent.includes('5470256'));assert.ok(!source.includes('Iv23liGSq3yRR7okVSQJ'));
 assert.equal(f.calls.some(path=>path.includes('/mcp')),false);f.close();});
 await test('empty server settings stay empty instead of impersonating an official or personal OAuth App',async()=>{
 const f=fixture();const original=f.c.api;f.c.api=async(path)=>path==='/api/admin/github-configuration'?{editable:true,settings_schema_ready:true,credential_storage_ready:false,configured:false,database:{checked:true,ready:true}}:original(path);
 await f.run();for(const name of ['App ID','App Slug','OAuth Client ID'])assert.equal(f.document.querySelector('input[aria-label="'+name+'"]').value,'');
 assert.equal(f.document.querySelector('button[type=submit]').disabled,true);assert.ok(f.document.body.textContent.includes('encryption is not configured'));f.close();});
 console.log(count+' admin GitHub DOM checks passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
