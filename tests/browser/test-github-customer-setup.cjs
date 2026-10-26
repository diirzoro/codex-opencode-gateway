/* Existing customer repository UI; controlled native-independent API fixtures. */
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const source=fs.readFileSync('management.js','utf8'),start=source.indexOf('  async function connections('),end=source.indexOf('  async function providers(',start);
async function fixture(status,repos=[]){
 const dom=new JSDOM('<main></main>'),document=dom.window.document,calls=[];let projectForm;
 const node=(tag,text='')=>{const n=document.createElement(tag);n.textContent=text;return n;};
 const c={tr:en=>en,window:dom.window,node,section(root,title){const s=node('section');s.append(node('h2',title));root.append(s);return s},row(root,title,detail){root.append(node('p',title+' '+detail))},button(label,run){const b=node('button',label);b.onclick=run;return b},async api(path){calls.push(path);if(path==='/api/github/status')return status;if(path==='/api/github/repositories')return repos;throw Error('Unexpected API '+path)},form(root,fields,label,run){projectForm={fields,label,run}},open:()=>{},toast:()=>{},openWorkspace:()=>{}};
 vm.createContext(c);vm.runInContext(source.slice(start,end)+'\nglobalThis.load=connections;',c);await c.load(document.querySelector('main'));
 return {dom,document,calls,projectForm};
}
(async()=>{
 let f=await fixture({configured:false,connected:false});
 assert.equal([...f.document.querySelectorAll('button')].find(b=>b.textContent==='Authorize GitHub').disabled,true);
 assert.ok(f.document.body.textContent.includes('sign-in stays unchanged'));assert.ok(f.document.body.textContent.includes('administrator saves'));
 assert.deepEqual(f.calls,['/api/github/status']);f.dom.window.close();
 console.log('PASS unconfigured customer cannot initiate repository authorization or request repositories');
 f=await fixture({configured:true,connected:false});assert.equal(f.document.querySelector('button').disabled,false);assert.equal(f.projectForm,undefined);f.dom.window.close();console.log('PASS configured customer has existing authorization entry point');
 f=await fixture({configured:true,connected:true,account_login:'synthetic-owner'},[]);assert.ok(f.document.body.textContent.includes('No authorized repositories'));assert.equal(f.projectForm,undefined);assert.deepEqual(f.calls,['/api/github/status','/api/github/repositories']);f.dom.window.close();console.log('PASS empty authorized repository list offers guidance without empty workspace form');
 f=await fixture({configured:true,connected:true,account_login:'synthetic-owner'},[{full_name:'synthetic-owner/test-repo'}]);assert.equal(f.projectForm.label,'Create workspace');assert.ok([...f.document.querySelectorAll('button')].some(b=>b.textContent==='Refresh repositories'));f.dom.window.close();console.log('PASS connected customer retains owned repository workspace flow');
 console.log('4 customer GitHub setup DOM checks passed');
})().catch(error=>{console.error(error);process.exitCode=1});
