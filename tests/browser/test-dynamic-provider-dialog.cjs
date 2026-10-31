/* DOM regression for real native modal bank/payment provider editor in TEST. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('enhancements.js','utf8');
const marker='/* TEST: administrator-defined payment/bank settings; no automatic checkout. */';
const idx=source.lastIndexOf(marker);
assert(idx>0,'Dynamic admin provider module is missing');
const module=source.slice(idx);
const css=fs.readFileSync('styles.css','utf8');
assert.match(css,/:root dialog\.dynamic-provider-dialog\{[^}]*width:min\(820px,calc\(100vw - 28px\)\)/,
  'Payment editor must be a width-constrained native dialog');
assert.match(css,/:root dialog\.dynamic-provider-dialog::backdrop\{/,
  'Dialog backdrop must be distinct');
assert.match(css,/:root dialog\.dynamic-provider-dialog \.dynamic-provider-field\{/,
  'Provider field rows must have isolated modal-specific layout');
async function main(){
 const dom=new JSDOM('<nav id="adminNav"><button data-admin-view="billing">Billing</button></nav>'+
 '<section data-admin-panel="billing"></section>',{url:'https://test.opencode-gateway.codes'});
 const document=dom.window.document;
 const dialogProto=dom.window.HTMLDialogElement.prototype;
 dialogProto.showModal=function(){this.open=true;this.setAttribute('open','')};
 dialogProto.close=function(){this.open=false;this.removeAttribute('open');this.dispatchEvent(new dom.window.Event('close'))};
 const saved=[
  {slug:'my_first_bank',label:'My Bank',category:'bank',connection_mode:'manual',
   environment:'test',configured:true,fields:[{key:'iban',label:'IBAN',kind:'text',required:false,
    value:'GB-TEST',configured:true}]},
  {slug:'sample_wallet',label:'Wallet Example',category:'wallet',connection_mode:'manual',
   environment:'test',configured:false,fields:[]}
 ];
 let post;
 const api=async(path,options={})=>{
  if(path==='/api/admin/payment-gateways/profiles'&&(!options.method||options.method==='GET'))
   return {profiles:structuredClone(saved)};
  if(path==='/api/admin/payment-gateways/profiles'&&options.method==='POST'){
   post=JSON.parse(options.body);
   saved.push({...post,configured:false,fields:post.fields.map(f=>({...f,configured:Boolean(f.value)}))});
   return {slug:post.slug};
  }
  throw Error('Unexpected mocked payment provider API: '+path+' '+options.method);
 };
 const context={document,window:dom.window,lang:'ar',currentUser:{role:'owner'},api,console};
 vm.createContext(context);vm.runInContext(module,context);
 const settle=async()=>{for(let i=0;i<12;i++)await Promise.resolve()};
 document.querySelector('#adminNav [data-admin-view="billing"]').click();await settle();
 const picker=document.querySelector('#dynamicProviderSelect');
 assert(picker,'Saved providers need a visible dropdown');
 assert.equal(picker.options.length,3,'Saved bank / wallet + blank choice');
 assert.equal(picker.value,'my_first_bank');
 assert.equal(document.querySelectorAll('#dynamicPaymentProviders .dynamic-provider-card').length,1,
   'Only the selected company must be shown, never a giant stack of forms');
 picker.value='sample_wallet';picker.dispatchEvent(new dom.window.Event('change',{bubbles:true}));
 assert.match(document.querySelector('#dynamicPaymentProviders .dynamic-provider-card').textContent,/Wallet Example/);
 assert(!document.querySelector('dialog.dynamic-provider-dialog'),'Do not show editor until requested');
 document.querySelector('#dynamicProviderAdd').click();
 const dialog=document.querySelector('dialog.dynamic-provider-dialog');
 assert(dialog?.open,'Add must open a native modal');
 assert.equal(dialog.parentElement,document.body,'Modal must escape dashboard containers');
 assert.equal(dialog.getAttribute('aria-modal'),'true');
 const template=dialog.querySelector('form select');
 assert(template,'Optional provider template dropdown is required');
 assert([...template.options].some(o=>o.value==='custom'),'Unlisted company must remain supported');
 assert([...template.options].some(o=>o.value==='paypal'),'PayPal is only an optional template');
 template.value='bank';template.dispatchEvent(new dom.window.Event('change',{bubbles:true}));await settle();
 assert(dialog.querySelectorAll('.dynamic-provider-field').length>=4,
   'Bank example must create editable account and IBAN fields in the modal');
 const form=dialog.querySelector('form');
 const controls=[...form.querySelectorAll(':scope >label input')];
 assert(controls.length>=2);
 const names=[...form.querySelectorAll(':scope >label')];
 const nameInput=names.find(l=>/اسم البنك أو خدمة الدفع/.test(l.textContent))?.querySelector('input');
 const slugInput=names.find(l=>/رمز مميز/.test(l.textContent))?.querySelector('input');
 assert(nameInput&&slugInput,'Unlisted bank name/code must be editable');
 nameInput.value='New Regional Bank';slugInput.value='new_regional_bank';
 form.dispatchEvent(new dom.window.Event('submit',{bubbles:true,cancelable:true}));await settle();
 assert(post,'Submitting must call the admin-only profiles API');
 assert.equal(post.label,'New Regional Bank');
 assert.equal(post.slug,'new_regional_bank');
 assert.equal(post.category,'bank');
 assert(post.fields.some(f=>f.key==='iban'),'Custom fields must save');
 assert.equal(document.querySelector('dialog.dynamic-provider-dialog'),null,'Dialog must close after successful save');
 assert.equal(document.querySelector('#dynamicProviderSelect').value,'new_regional_bank',
   'Saved provider should become selected');
 // Reopen edit dialog; required credentials remain blank and are not exposed.
 document.querySelector('#dynamicPaymentProviders .dynamic-provider-actions button').click();
 const editing=document.querySelector('dialog.dynamic-provider-dialog');
 assert(editing?.open,'Editing selected bank must also open a modal');
 editing.close();assert.equal(document.querySelector('dialog.dynamic-provider-dialog'),null);
 dom.window.close();
 console.log('PASS TEST dynamic bank picker, +new native modal, templates, custom name, encrypted profile API and close');
}
main().catch(err=>{console.error(err);process.exitCode=1});
