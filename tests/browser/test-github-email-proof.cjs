/* Actual confirmation UI with synthetic independent-inbox API fixtures. */
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const source=fs.readFileSync('enhancements.js','utf8'),start=source.indexOf('window.renderGithubConfirmation='),end=source.indexOf('(function () {',start);
function fixture({fail=false}={}){
 const dom=new JSDOM('<main></main>'),d=dom.window.document,calls=[];
 const c={currentUser:{id:'customer'},lang:'en',Option:dom.window.Option,URL,document:d,toast:()=>{},window:{},textElement:(tag,text='',cls='')=>{const n=d.createElement(tag);n.textContent=text;n.className=cls;return n;},api:async(path,options)=>{calls.push({path,body:JSON.parse(options.body||'{}')});if(fail)throw Error('Email delivery unavailable');return path.endsWith('/send')?{sent:true,masked_email:'g***@example.com'}:path.endsWith('/verify')?{verified:true}:{connected:true};}};
 vm.createContext(c);vm.runInContext(source.slice(start,end),c);
 c.window.renderGithubConfirmation(d.querySelector('main'),{pending:{connection_id:'new-transaction',github_user_id:101,github_login:'fixture',installations:[{id:901,login:'Owned fixture'}],email_verification:{required:true,verified:false}}},async()=>{});
 const button=t=>[...d.querySelectorAll('button')].find(x=>x.textContent===t);
 return {dom,d,c,calls,button};
}
(async()=>{
 const f=fixture(),checkbox=f.d.querySelector('input[type=checkbox]'),select=f.d.querySelector('select');checkbox.checked=true;select.value='901';select.onchange();assert(f.button('Confirm connection').disabled);
 await f.button('Send GitHub email code').onclick();assert.deepEqual(f.calls[0],{path:'/api/github/pending/email/send',body:{connection_id:'new-transaction'}});assert(f.d.body.textContent.includes('g***@example.com'));
 const input=f.d.querySelector('input[autocomplete="one-time-code"]');input.value='123456';await f.button('Verify code').onclick();assert(!f.button('Confirm connection').disabled);assert.equal(input.value,'');assert(input.hidden);await f.button('Confirm connection').onclick();assert.equal(f.calls.at(-1).path,'/api/github/confirm');f.dom.window.close();console.log('PASS identity checkbox cannot bypass OTP; code sent by connection ID and verified before confirmation');
 const fail=fixture({fail:true});await fail.button('Send GitHub email code').onclick();assert(fail.d.body.textContent.includes('Email delivery unavailable'));assert(fail.button('Confirm connection').disabled);fail.dom.window.close();console.log('PASS real delivery error shown without claiming verification');
 const other=fixture();other.c.currentUser={id:'other'};await other.button('Send GitHub email code').onclick();other.d.querySelector('input[autocomplete="one-time-code"]').value='123456';await other.button('Verify code').onclick();assert.equal(other.calls.length,0);other.dom.window.close();console.log('PASS switched Gateway account cannot send or verify stale identity code');
 const invalid=fixture();invalid.d.querySelector('input[autocomplete="one-time-code"]').value='12';await invalid.button('Verify code').onclick();assert.equal(invalid.calls.length,0);invalid.dom.window.close();console.log('PASS malformed code cannot submit');
 console.log('4 GitHub email proof DOM checks passed');
})().catch(e=>{console.error(e);process.exitCode=1});
