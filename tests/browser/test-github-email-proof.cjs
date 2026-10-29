/* Actual confirmation UI with synthetic independent-inbox API fixtures. */
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const source=fs.readFileSync('enhancements.js','utf8'),start=source.indexOf('window.renderGithubConfirmation='),end=source.indexOf('(function () {',start);
function fixture({fail=false,language='en',errorMessage='Email delivery unavailable',installations=[{id:901,login:'Owned fixture'}]}={}){
 const dom=new JSDOM('<main></main>'),d=dom.window.document,calls=[];
 const c={currentUser:{id:'customer'},lang:language,Option:dom.window.Option,URL,document:d,toast:()=>{},window:{},textElement:(tag,text='',cls='')=>{const n=d.createElement(tag);n.textContent=text;n.className=cls;return n;},api:async(path,options)=>{calls.push({path,body:JSON.parse(options.body||'{}')});if(fail)throw Error(errorMessage);return path.endsWith('/send')?{sent:true,expires_at:new Date(Date.now()+59000).toISOString(),masked_email:'g***@example.com'}:path.endsWith('/verify')?{verified:true}:{connected:true};}};
 vm.createContext(c);vm.runInContext(source.slice(start,end),c);
 c.window.renderGithubConfirmation(d.querySelector('main'),{pending:{connection_id:'new-transaction',github_user_id:101,github_login:'fixture',installations,email_verification:{required:true,verified:false}}},async()=>{});
 const button=t=>[...d.querySelectorAll('button')].find(x=>x.textContent===t);
 return {dom,d,c,calls,button};
}
(async()=>{
 const f=fixture(),checkbox=f.d.querySelector('input[type=checkbox]'),select=f.d.querySelector('select');checkbox.checked=true;select.value='901';select.onchange();assert(f.button('Confirm connection').disabled);
 f.d.querySelector('input[type=email]').value='entered@example.com';await f.button('Verify email and send code').onclick();assert.deepEqual(f.calls[0],{path:'/api/github/pending/email/send',body:{connection_id:'new-transaction',email:'entered@example.com'}});assert(!f.d.body.textContent.includes('g***@example.com'));
 const input=f.d.querySelector('input[autocomplete="one-time-code"]');input.value='123456';await f.button('Verify code').onclick();assert(!f.button('Confirm connection').disabled);assert.equal(input.value,'');assert(input.hidden);await f.button('Confirm connection').onclick();assert.equal(f.calls.at(-1).path,'/api/github/confirm');f.dom.window.close();console.log('PASS identity checkbox cannot bypass OTP; code sent by connection ID and verified before confirmation');
 const fail=fixture({fail:true});fail.d.querySelector('input[type=email]').value='entered@example.com';await fail.button('Verify email and send code').onclick();assert(fail.d.body.textContent.includes('Email delivery unavailable'));assert(fail.button('Confirm connection').disabled);fail.dom.window.close();console.log('PASS real delivery error shown without claiming verification');
 const other=fixture();other.c.currentUser={id:'other'};await other.button('Verify email and send code').onclick();other.d.querySelector('input[autocomplete="one-time-code"]').value='123456';await other.button('Verify code').onclick();assert.equal(other.calls.length,0);other.dom.window.close();console.log('PASS switched Gateway account cannot send or verify stale identity code');
 const invalid=fixture();invalid.d.querySelector('input[autocomplete="one-time-code"]').value='12';await invalid.button('Verify code').onclick();assert.equal(invalid.calls.length,0);invalid.dom.window.close();console.log('PASS malformed code cannot submit');
 const ar=fixture({fail:true,language:'ar',errorMessage:'GitHub email could not be verified. Check the primary email on the selected GitHub account.'});ar.d.querySelector('input[type=email]').value='entered@example.com';await ar.button('التحقق من البريد وإرسال الرمز').onclick();assert(ar.d.body.textContent.includes('تعذر التحقق من البريد'));assert(!ar.d.body.textContent.includes('g***@example.com'));ar.dom.window.close();console.log('PASS Arabic manual-email instructions and mismatch error without email disclosure');
 const empty=fixture();await empty.button('Verify email and send code').onclick();assert.equal(empty.calls.length,0);empty.dom.window.close();console.log('PASS missing manual email cannot request a code');
 const missing=fixture({installations:[]});assert(missing.d.querySelector('input[type=email]'));assert(missing.button('Install on my GitHub account'));assert(!missing.button('Confirm connection'));assert(!missing.d.body.textContent.includes('g***@example.com'));missing.dom.window.close();console.log('PASS manual email verification remains visible before installation, without granting repository access');
 const ticking=fixture();
 ticking.d.querySelector('input[type=email]').value='entered@example.com';
 await ticking.button('Verify email and send code').onclick();
 assert.match(ticking.d.querySelector('.github-email-countdown').textContent,/5[89]s/);
 assert.equal(ticking.button('Verify email and send code').disabled,true);
 ticking.dom.window.close();
 // Restored pending OTP: the stored server expiry is authoritative even after refresh.
 const old=new Date(Date.now()-3000).toISOString();
 const restored=fixture();
 restored.d.querySelector('main').replaceChildren();
 restored.c.window.renderGithubConfirmation(restored.d.querySelector('main'),{pending:{
   connection_id:'expired-token',github_user_id:101,github_login:'fixture',
   installations:[{id:901,login:'Owned'}],
   email_verification:{required:true,verified:false,sent:true,expires_at:old}}},async()=>{});
 assert(restored.d.querySelector('.github-email-countdown').textContent.includes('expired'));
 assert.equal(restored.d.querySelector('input[autocomplete="one-time-code"]').nextSibling.disabled,true);
 restored.dom.window.close();
 console.log('8 GitHub email proof DOM checks passed');
})().catch(e=>{console.error(e);process.exitCode=1});
