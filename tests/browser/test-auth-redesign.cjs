// Test actual Auth wiring in a VM; not browser geometry or external OAuth/SMTP.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('app.js','utf8'),management=fs.readFileSync('management.js','utf8');
class Element{constructor(){this.children=[];this.dataset={};}append(...nodes){this.children.push(...nodes);}}
{
 const media={matches:false,addEventListener(kind,fn){this.change=fn;}},workflow=new Element(),card=new Element(),authDialog=new Element(),authPage={querySelector(){return workflow;},append(node){this.dialog=node;}};
 const c={authPage,card,authDialog,element:()=>new Element(),matchMedia:()=>media,t:()=> 'Why OpenCode Gateway?'};vm.createContext(c);
 vm.runInContext(source.slice(source.indexOf("    const columns=element('div','','auth-dialog-columns')"),source.indexOf("    const closeBtn=card.querySelector")),c);
 const columns=authDialog.children[0],benefits=columns.children[0];assert.equal(benefits.open,true);assert.equal(benefits.children[1],workflow);assert.equal(columns.children[1],card);media.matches=true;media.change();assert.equal(benefits.open,false);benefits.open=true;assert.equal(benefits.open,true);media.matches=false;media.change();assert.equal(benefits.open,true);
}
{
 const original=()=>{},forgot={disabled:true},resend={onclick:original};let called=0;
 const c={$:selector=>selector==='#authForgotPassword'?forgot:resend,tr:en=>en,recover(){called++;}};vm.createContext(c);vm.runInContext(management.slice(management.indexOf('  const forgot='),management.indexOf('  window.renderManagement=')),c);
 assert.equal(forgot.disabled,false);forgot.onclick();assert.equal(called,1);assert.equal(resend.onclick,original);
}
{
 const identity={value:'owner'},password={value:'secret'},remember={checked:true},submit={disabled:false},form={};let opened=0,request,remembered;
 const c={$:selector=>({'#loginForm':form,'#loginSubmit':submit,'#loginPassword':password,'#rememberIdentity':remember})[selector],value:()=>identity.value,api:async(path,opts)=>{request={path,body:JSON.parse(opts.body)};return {id:'owned'};},renderProfile(){},openWorkspaceAfterLogin:async()=>{opened++;},localStorage:{setItem(key,value){remembered={key,value};},removeItem(){}},apiMessage(){}};
 vm.createContext(c);vm.runInContext(source.slice(source.indexOf("$('#loginForm').onsubmit="),source.indexOf("$('#resendEmailVerification').onclick=")),c);
 c.form=form;
 (async()=>{await form.onsubmit({preventDefault(){},currentTarget:{reportValidity:()=>true}});assert.equal(request.path,'/api/auth/login');assert.deepEqual(request.body,{identity:'owner',password:'secret'});assert.equal(password.value,'');assert.equal(remembered.key,'og-login-identity');assert.equal(remembered.value,'owner');assert.equal(opened,1);assert.equal(submit.disabled,false);})().catch(error=>{console.error(error);process.exitCode=1;});
}
{
 const buttons=[{dataset:{socialLogin:'github'}},{dataset:{socialLogin:'google'}}],c={$$:()=>buttons,location:{assign(path){c.path=path;}}};vm.createContext(c);
 const line=source.split('\n').find(line=>line.startsWith("$$('[data-social-login]').forEach"));vm.runInContext(line,c);for(const b of buttons){assert.equal(b.disabled,true);if(b.dataset.socialLogin==='github'){assert.equal(b.hidden,true);assert.equal(b.onclick,undefined);}else{b.onclick();assert.equal(c.path,'/api/auth/social/google/start');}}
 assert.ok(!fs.readFileSync('index.html','utf8').includes('data-social-login="github"'));
 assert.ok(fs.readFileSync('index.html','utf8').includes('data-social-login="google"'));
}
{
 const c={copy:{en:{},ar:{}},localStorage:{getItem(){return null;}}};vm.createContext(c);vm.runInContext(source.slice(source.indexOf("Object.assign(copy.en,{benefitsTitle:"),source.indexOf('\nlet socialOptions')),c);
 for(const language of ['en','ar'])for(const key of ['benefitsTitle','authBenefitsToggle',...Array.from({length:4},(_,i)=>['b'+(i+1)+'t','b'+(i+1)+'d']).flat(),'forgotPassword','resendVerification'])assert.ok(c.copy[language][key]);assert.match(c.copy.ar.b4d,/تأكيد بريدك/);assert.match(c.copy.en.b4d,/platform subscription/);
}
{
 const identity={value:''},remember={checked:false},c={localStorage:{getItem:key=>{assert.equal(key,'og-login-identity');return 'remembered-user';}},$:selector=>selector==='#loginIdentity'?identity:remember};vm.createContext(c);vm.runInContext(source.split('\n').find(line=>line.startsWith('try{const remembered=localStorage.getItem')),c);assert.equal(identity.value,'remembered-user');assert.equal(remember.checked,true);
}
console.log('6 scenarios passed: responsive disclosure, recovery/resend separation, login payload/remember/redirect, native OAuth callbacks, bilingual benefits');
