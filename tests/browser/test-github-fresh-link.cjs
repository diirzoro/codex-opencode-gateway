/* Actual UI functions with synthetic owned data; not live OAuth acceptance. */
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const source=fs.readFileSync('dashboards.js','utf8');
async function fixture(connected=false,confirm=true){
 const dom=new JSDOM('<section id="connectionsGithub"></section>'),d=dom.window.document,calls=[],redirects=[];
 const node=(tag,t='')=>{const n=d.createElement(tag);n.textContent=t;return n;};
 const c={currentUser:{id:'owner'},URLSearchParams,URL,location:{search:'',href:'https://test.example/'},
  window:{confirmAction:async()=>confirm,location:{assign:u=>redirects.push(u)}},q:id=>d.getElementById(id),tr:en=>en,title:en=>node('h2',en),textElement:node,text:(tag,en)=>node(tag,en),
  btn:(id,en,ar,run)=>{const n=node('button',en);n.id=id;n.onclick=run;return n;},
  api:async(path,options={})=>{calls.push([path,options.method||'GET']);if(path==='/api/github/status')return {configured:true,connected,account_login:'synthetic'};if(path==='/api/github/repositories')return [];if(path==='/api/github/connect')return {url:'https://github.com/login/oauth/authorize?state=new&prompt=select_account'};throw Error(path);}};
 vm.createContext(c);const a=source.indexOf('  let githubConnectionRender=0;'),b=source.indexOf('  let workAccess=',a);vm.runInContext(source.slice(a,b)+'\nglobalThis.load=loadConnectionsGithub;',c);await c.load();return {dom,d,c,calls,redirects};
}
(async()=>{
 for(const connected of [false,true]){
  const f=await fixture(connected);assert.equal(f.d.querySelectorAll('#settingsAuthorizeGithub').length,1);assert.equal(f.d.querySelector('#settingsInstallGithub'),null);assert.equal(f.d.querySelector('#settingsChooseGithubRepositories'),null);
  assert.equal(f.d.querySelector('#settingsAuthorizeGithub').textContent,'New GitHub connection');await f.d.querySelector('#settingsAuthorizeGithub').onclick();assert.deepEqual(f.calls.at(-1),['/api/github/connect','POST']);assert.equal(f.redirects.length,1);assert(f.d.body.textContent.includes('Previous link cleared'));f.dom.window.close();console.log('PASS one fresh link button, explicit POST and stale catalog clearing: connected='+connected);
 }
 const f=await fixture(false,false);await f.d.querySelector('#settingsAuthorizeGithub').onclick();assert(!f.calls.some(([p])=>p==='/api/github/connect'));assert.equal(f.redirects.length,0);f.dom.window.close();console.log('PASS cancellation preserves current connection');
 const enhancement=fs.readFileSync('enhancements.js','utf8'),helper=enhancement.slice(enhancement.indexOf('let freshGithubPending='),enhancement.indexOf('(function () {'));
 const calls=[],redirects=[];let resolve;
 const c={currentUser:{id:'a'},lang:'en',document:{getElementById:()=>null},textElement:()=>{},toast:()=>{},window:{confirmAction:async()=>true,location:{assign:u=>redirects.push(u)}},api:async(path,options)=>{calls.push([path,options.method]);return new Promise(r=>resolve=r);}};
 vm.createContext(c);vm.runInContext(helper,c);const first=c.window.startFreshGithubConnection();await new Promise(r=>setImmediate(r));await c.window.startFreshGithubConnection();assert.equal(calls.length,1);c.currentUser={id:'b'};resolve({url:'https://github.com/fixture'});await first;assert.equal(redirects.length,0);console.log('PASS admin helper coalesces repeated clicks and ignores redirect after account switch');
 assert(!enhancement.includes("window.location = '/api/github/install'"));assert(!enhancement.includes("location.assign('/api/github/install')"));console.log('PASS admin and legacy shortcuts do not bypass fresh POST');
 console.log('5 fresh GitHub DOM checks passed');
})().catch(error=>{console.error(error);process.exitCode=1});
