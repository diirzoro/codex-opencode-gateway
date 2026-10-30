const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('app.js','utf8');
const start=source.indexOf('async function offerExistingAccountRecovery(');
const end=source.indexOf("$('#loginForm').onsubmit=",start);
assert(start>0&&end>start,'Recover-existing-account helper is missing');
const script=source.slice(start,end);
function fixture({approve=true,promptEmail='recover@example.org'}={}){
 const calls=[],messages=[],confirmations=[],entered=[];
 const context={
  lang:'ar',window:{
   requestInput:async prompt=>{entered.push(prompt);return promptEmail;},
   confirmAction:async prompt=>{confirmations.push(prompt);return approve;}
  },
  api:async(path,options)=>{calls.push({path,options});return {message:'If eligible, recovery email will be sent'};},
  apiMessage:(area,text,error)=>messages.push({area,text,error})
 };
 vm.createContext(context);vm.runInContext(script,context);
 return {context,calls,messages,confirmations,entered};
}
(async()=>{
 let f=fixture({approve:false});
 assert.equal(await f.context.offerExistingAccountRecovery('old@example.org','registerMessage'),false);
 assert.equal(f.calls.length,0,'Declining must NEVER send a mail');
 assert.equal(f.confirmations.length,1);
 f=fixture({approve:true});
 assert.equal(await f.context.offerExistingAccountRecovery('old@example.org','registerMessage'),true);
 assert.equal(f.calls.length,1);
 assert.equal(f.calls[0].path,'/api/auth/forgot-password');
 assert.equal(JSON.parse(f.calls[0].options.body).email,'old@example.org');
 assert(f.messages[0].text.includes('60 ثانية'),'One-minute expiry must be explained');
 assert.equal(f.messages[0].text.includes('old@example.org'),false,'Do not reveal account details');
 f=fixture({approve:true,promptEmail:'corrected@example.org'});
 assert.equal(await f.context.offerExistingAccountRecovery('old_username','loginMessage'),true);
 assert.equal(f.entered.length,1);
 assert.equal(JSON.parse(f.calls[0].options.body).email,'corrected@example.org');
 f=fixture({approve:true,promptEmail:'invalid'});
 assert.equal(await f.context.offerExistingAccountRecovery('bad','loginMessage'),false);
 assert.equal(f.calls.length,0,'Invalid mail must NEVER be submitted');
 console.log('PASS explicit YES/NO, no mail before consent, registered-address recovery and one-minute notice');
})().catch(error=>{console.error(error);process.exitCode=1});
