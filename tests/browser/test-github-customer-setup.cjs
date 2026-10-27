/* Existing customer repository UI; controlled native-independent API fixtures. */
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const source=fs.readFileSync('management.js','utf8'),start=source.indexOf('  async function connections('),end=source.indexOf('  async function providers(',start);
async function fixture(status,repos=[]){
 const dom=new JSDOM('<main></main>'),document=dom.window.document,calls=[],redirects=[];let projectForm;
 const node=(tag,text='')=>{const n=document.createElement(tag);n.textContent=text;return n;};
 const c={lang:'en',URL,document,textElement:node,currentUser:{id:'synthetic-owner'},tr:en=>en,window:{focus:()=>{},open:()=>({opener:{},closed:false,document:{body:{}},location:{replace:url=>redirects.push(url)},focus:()=>{},close:()=>{}}),confirmAction:async()=>true},node,section(root,title){const s=node('section');s.append(node('h2',title));root.append(s);return s},row(root,title,detail){root.append(node('p',title+' '+detail))},button(label,run){const b=node('button',label);b.onclick=async()=>{b.disabled=true;try{await run()}finally{b.disabled=false}};return b},async api(path,options={}){calls.push(path);if(path==='/api/github/connect'){assert.equal(options.method,'POST');return {url:'https://github.com/login/oauth/authorize?state=new'}};if(path==='/api/github/status')return status;if(path==='/api/github/repositories')return repos;throw Error('Unexpected API '+path)},form(root,fields,label,run){projectForm={fields,label,run}},open:()=>{},toast:()=>{},openWorkspace:()=>{}};
 vm.createContext(c);const shared=fs.readFileSync('enhancements.js','utf8');vm.runInContext(shared.slice(shared.indexOf('let freshGithubPending='),shared.indexOf('(function () {')),c);vm.runInContext(source.slice(start,end)+'\nglobalThis.load=connections;',c);await c.load(document.querySelector('main'));
 return {dom,document,calls,projectForm,redirects};
}
(async()=>{
 let f=await fixture({configured:false,connected:false});
 assert.equal([...f.document.querySelectorAll('button')].find(b=>b.textContent==='New GitHub connection').disabled,true);
 assert.ok(f.document.body.textContent.includes('sign-in stays unchanged'));assert.ok(f.document.body.textContent.includes('administrator saves'));
 assert.deepEqual(f.calls,['/api/github/status']);f.dom.window.close();
 console.log('PASS unconfigured customer cannot initiate repository authorization or request repositories');
 f=await fixture({configured:true,connected:false});assert.equal(f.document.querySelector('button').disabled,false);assert.equal(f.projectForm,undefined);f.dom.window.close();console.log('PASS configured customer has existing authorization entry point');
 f=await fixture({configured:true,connected:true,account_login:'synthetic-owner'},[]);assert.ok(f.document.body.textContent.includes('No authorized repositories'));assert.equal(f.projectForm,undefined);assert.deepEqual(f.calls,['/api/github/status','/api/github/repositories']);f.dom.window.close();console.log('PASS empty authorized repository list offers guidance without empty workspace form');
 f=await fixture({configured:true,connected:true,account_login:'synthetic-owner'},[{full_name:'synthetic-owner/test-repo'}]);assert.equal(f.projectForm.label,'Create workspace');assert.ok([...f.document.querySelectorAll('button')].some(b=>b.textContent==='Refresh repositories'));f.dom.window.close();console.log('PASS connected customer retains owned repository workspace flow');
 f=await fixture({configured:true,connected:false});await f.document.querySelector('button').onclick();assert.equal(f.calls.at(-1),'/api/github/connect');assert.equal(f.redirects[0],'https://github.com/login/oauth/authorize?state=new');f.dom.window.close();console.log('PASS management button runs while its shared wrapper disables it');
 console.log('5 customer GitHub setup DOM checks passed');
})().catch(error=>{console.error(error);process.exitCode=1});
