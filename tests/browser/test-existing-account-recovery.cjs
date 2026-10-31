const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('app.js','utf8');
const enhancements=fs.readFileSync('enhancements.js','utf8');
// Regression: enhancements must never replace the canonical OTP form handler.
assert.equal((source.match(/\$\('#registerForm'\)\.onsubmit\s*=/g)||[]).length,1,
  'app.js must own exactly one registration submit handler');
assert(!/\$\('#registerForm'\)\.onsubmit\s*=/.test(enhancements),
  'enhancements.js must not overwrite the staged registration/OTP handler');
assert(source.includes("['pending_email','pending_verification']")||
       source.includes("['pending_email', 'pending_verification']"),
  'canonical registration handler must recognize pending_verification');
console.log('PASS one canonical registration handler; no legacy OTP override');

// TEST-only landing presentation guard: four plans must never wrap into 2 x 2.
const landingCss=fs.readFileSync('styles.css','utf8');
const landingHtml=fs.readFileSync('index.html','utf8');
assert.match(landingCss,/#landing \.pricing-cards\s*\{[^}]*display:grid;[^}]*grid-template-columns:repeat\(4,minmax\(0,1fr\)\)/s,
  'Landing must display four equal-width columns on desktop');
assert.match(landingCss,/#landing \.pricing-cards>\.price-card\s*\{[^}]*min-width:0;/s,
  'Individual landing pricing cards must not force wrapping');
assert.match(landingCss,/@media\(max-width:560px\)[\s\S]*?#landing \.pricing-cards\s*\{grid-template-columns:repeat\(4,220px\)/,
  'On phones, four cards remain side-by-side in a horizontally scrollable row');
assert(landingHtml.includes('styles.css?v=20261031-dynamic-providers-test'), 'Pricing CSS must be cache-busted');
assert(landingHtml.includes('enhancements.js?v=20261031-four-pricing-cards-test'), 'Pricing copy JS must be cache-busted');
assert(enhancements.includes("disclaimer.textContent=platformOnlyNote()"),
  'Full disclaimer that AI APIs/models are not included must be shown after pricing cards');
assert(enhancements.includes("providerExamples=[") && enhancements.includes("code:'custom'"),
  'Optional payment templates must retain unrestricted custom-provider entry');
assert(!landingHtml.includes('src="payment-gateways-ui.js'),
  'Fixed-provider settings panel must not replace TEST dynamic admin configuration');
console.log('PASS TEST four pricing columns, swipe row, dynamic provider templates/custom option, and API disclaimer');

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

// CI-protected browser test entry includes the TEST-only dialog regression.
require('./test-dynamic-provider-dialog.cjs');
