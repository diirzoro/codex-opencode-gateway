/* Actual identity-confirmation renderer with synthetic DOM/API; not live OAuth. */
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const source=fs.readFileSync('enhancements.js','utf8'),start=source.indexOf('window.renderGithubConfirmation='),end=source.indexOf('(function () {',start);
function fixture({fail=false}={}){
 const dom=new JSDOM('<main></main>'),d=dom.window.document,calls=[];let refreshes=0;
 const c={currentUser:{id:'customer'},lang:'en',Option:dom.window.Option,URL,document:d,toast:()=>{},window:{},textElement:(tag,text='',cls='')=>{const n=d.createElement(tag);n.textContent=text;n.className=cls;return n;},api:async(path,options)=>{calls.push({path,body:JSON.parse(options.body||'{}')});if(fail)throw Error('Synthetic failure');return {connected:true};}};
 vm.createContext(c);vm.runInContext(source.slice(start,end),c);
 const pending={connection_id:'new-transaction',github_user_id:101,github_login:'<img src=x onerror=attack()>',installations:[{id:901,login:'Owned fixture'}]};
 c.window.renderGithubConfirmation(d.querySelector('main'),{pending},async()=>refreshes++);
 return {dom,d,c,calls,pending,refreshes:()=>refreshes};
}
(async()=>{
 const f=fixture(),button=[...f.d.querySelectorAll('button')].find(x=>x.textContent==='Confirm connection');
 assert.equal(f.calls.length,0);assert(button.disabled);assert.equal(f.d.querySelector('img'),null);
 const input=f.d.querySelector('input'),select=f.d.querySelector('select');input.checked=true;input.onchange();assert(button.disabled);select.value='901';select.onchange();assert(!button.disabled);
 await button.onclick();assert.equal(f.calls.length,1);assert.equal(f.calls[0].path,'/api/github/confirm');assert.deepEqual(f.calls[0].body,{connection_id:'new-transaction',github_user_id:101,installation_id:901});assert.equal(f.refreshes(),1);f.dom.window.close();console.log('PASS exact identity plus installation require explicit confirmation; identity text cannot inject HTML');
 const other=fixture();other.c.currentUser={id:'different-user'};const b=[...other.d.querySelectorAll('button')].find(x=>x.textContent==='Confirm connection');b.disabled=false;await b.onclick();assert.equal(other.calls.length,0);other.dom.window.close();console.log('PASS switched Gateway account cannot submit stale identity confirmation');
 const error=fixture({fail:true}),i=error.d.querySelector('input'),s=error.d.querySelector('select');i.checked=true;s.value='901';s.onchange();const e=[...error.d.querySelectorAll('button')].find(x=>x.textContent==='Confirm connection');await e.onclick();assert.equal(i.checked,true);assert.equal(s.value,'901');assert(error.d.body.textContent.includes('Synthetic failure'));assert(!e.disabled);error.dom.window.close();console.log('PASS failed confirmation preserves choice and shows genuine error');
 const cancel=fixture();await [...cancel.d.querySelectorAll('button')].find(x=>x.textContent==='Cancel / choose another account').onclick();assert.deepEqual(cancel.calls.map(x=>x.path),['/api/github/disconnect']);assert.equal(cancel.refreshes(),1);cancel.dom.window.close();console.log('PASS cancel revokes pending transaction without confirming it');
 console.log('4 identity confirmation DOM checks passed');
})().catch(e=>{console.error(e);process.exitCode=1});
