/* Executes the real shared helper and customer view with synthetic owned data. */
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const source=fs.readFileSync('dashboards.js','utf8'),enhancement=fs.readFileSync('enhancements.js','utf8');
const helper=enhancement.slice(enhancement.indexOf('let freshGithubPending='),enhancement.indexOf('(function () {'));
async function fixture({connected=false,confirm=true,blocked=false,fail=false,defer=false}={}){
 const dom=new JSDOM('<section id="connectionsGithub"></section>'),d=dom.window.document,calls=[],redirects=[],prompts=[],errors=[],popups=[];let liveConnected=connected,resolve;
 const node=(tag,t='')=>{const n=d.createElement(tag);n.textContent=t;return n;};
 const c={currentUser:{id:'owner'},lang:'en',URLSearchParams,URL,document:d,location:{search:'',href:'https://test.example/'},toast:m=>errors.push(m),
  window:{focus:()=>{},history:{replaceState:()=>{}},open:(url,target,features)=>{assert.equal(url,'about:blank');assert.equal(target,'_blank');assert.match(features,/popup/);if(blocked)return null;const p={opener:{},closed:false,document:{body:{}},focus:()=>{},close(){this.closed=true;},location:{replace:u=>{assert.equal(p.opener,null);redirects.push(u);}}};popups.push(p);return p;},confirmAction:async text=>{if(text.startsWith('Start a new'))assert.equal(popups.length,1,'popup reserved before first await');prompts.push(text);return confirm;},location:{assign:()=>{throw Error('same-tab navigation forbidden');}}},
  q:id=>d.getElementById(id),tr:en=>en,title:en=>node('h2',en),textElement:node,text:(tag,en)=>node(tag,en),
  btn:(id,en,ar,run)=>{const n=node('button',en);n.id=id;n.onclick=run;return n;},
  api:async(path,options={})=>{calls.push([path,options.method||'GET']);if(path==='/api/github/disconnect'){liveConnected=false;return null;}if(path==='/api/github/status')return {configured:true,connected:liveConnected,account_login:'synthetic'};if(path==='/api/github/repositories')return [];if(path==='/api/github/connect'){if(fail)throw Error('Synthetic server failure');if(defer)return new Promise(r=>resolve=r);return {url:'https://github.com/login/oauth/authorize?state=new&prompt=select_account'};}throw Error(path);}};
 vm.createContext(c);vm.runInContext(helper,c);const a=source.indexOf('  let githubConnectionRender=0;'),b=source.indexOf('  let workAccess=',a);vm.runInContext(source.slice(a,b)+'\nglobalThis.load=loadConnectionsGithub;',c);await c.load();return {dom,d,c,calls,redirects,prompts,errors,popups,resolve:v=>resolve(v)};
}
(async()=>{
 let passed=0;const pass=s=>{console.log('PASS '+s);passed++;};
 for(const connected of [false,true]){
  const f=await fixture({connected});assert.equal(f.d.querySelectorAll('#settingsAuthorizeGithub').length,1);assert.equal(f.d.querySelector('#settingsInstallGithub'),null);
  await f.d.querySelector('#settingsAuthorizeGithub').onclick();assert.deepEqual(f.calls.at(-1),['/api/github/connect','POST']);assert.equal(f.redirects.length,1);assert(!f.popups[0].closed);assert(f.d.body.textContent.includes('same account'));f.dom.window.close();pass('single explicit fresh link opens separate window; connected='+connected);
 }
 for(const options of [{confirm:false},{blocked:true},{fail:true}]){
  const f=await fixture(options);await f.d.querySelector('#settingsAuthorizeGithub').onclick();assert.equal(f.redirects.length,0);if(!options.fail)assert(!f.calls.some(([p])=>p==='/api/github/connect'));if(f.popups.length)assert(f.popups[0].closed);if(options.blocked||options.fail)assert.equal(f.errors.length,1);f.dom.window.close();pass('cancel/block/error closes blank window without same-tab fallback: '+JSON.stringify(options));
 }
 const f=await fixture({defer:true});const first=f.c.window.startFreshGithubConnection();await new Promise(r=>setImmediate(r));await f.c.window.startFreshGithubConnection();assert.equal(f.calls.filter(([p])=>p==='/api/github/connect').length,1);f.c.currentUser={id:'other'};f.resolve({url:'https://github.com/login/oauth/authorize'});await first;assert.equal(f.redirects.length,0);assert(f.popups[0].closed);f.dom.window.close();pass('duplicate click coalescing and account-switch cancellation');
 const closed=await fixture({defer:true});const pending=closed.c.window.startFreshGithubConnection();await new Promise(r=>setImmediate(r));closed.popups[0].closed=true;closed.resolve({url:'https://github.com/login/oauth/authorize'});await pending;assert.equal(closed.redirects.length,0);closed.dom.window.close();pass('closed popup never reopens or replaces original tab');
 const bad=await fixture({defer:true});const unsafe=bad.c.window.startFreshGithubConnection();await new Promise(r=>setImmediate(r));bad.resolve({url:'https://attacker.invalid/login/oauth/authorize'});await unsafe;assert.equal(bad.redirects.length,0);assert(bad.popups[0].closed);bad.dom.window.close();pass('rejects foreign redirect target');
 const disconnected=await fixture({connected:true});await disconnected.d.querySelector('#settingsDisconnectGithub').onclick();assert(disconnected.d.body.textContent.includes('Not connected'));await disconnected.d.querySelector('#settingsAuthorizeGithub').onclick();assert.equal(disconnected.redirects.length,1);disconnected.dom.window.close();pass('fresh link remains usable immediately after disconnect');
 for(const file of ['dashboards.js','management.js']){const content=fs.readFileSync(file,'utf8');assert(content.includes('window.startFreshGithubConnection({isCurrent:'));assert(!content.includes('window.location.assign(next.url)'));}pass('customer and management reuse shared safe window flow');
 console.log(passed+' fresh GitHub DOM checks passed');
})().catch(error=>{console.error(error);process.exitCode=1});
