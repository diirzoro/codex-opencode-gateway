const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const src=fs.readFileSync('enhancements.js','utf8');
const a=src.indexOf('  function openAdminAccountRemoval('),b=src.indexOf('  async function gridUsers()',a);
assert(a>=0&&b>a,'Admin removal must have its own deliberate two-choice UI');
const snippet=src.slice(a,b);
async function fixture(status='active'){
 const {window}=new JSDOM('<main></main>');
 const user={id:'synthetic-user',username:'sample_user',role:'customer',status};
 const calls=[],messages=[],modal={close(){this.closed=true;},closed:false};
 let choices,reloads=0,typed='sample_user',allowed=true;
 const context={
  document:window.document,window:{requestInput:async()=>typed,confirmAction:async()=>allowed},
  tr:(en,ar)=>ar,gridUsers:async()=>{reloads++;},
  textElement:(tag,text='',className='')=>{const el=window.document.createElement(tag);el.textContent=text;el.className=className;return el;},
  openModal:(title,body,actions)=>{choices=actions;messages.push(body.textContent);return modal;},
  api:async(path,options)=>{
   calls.push({path,method:options.method,body:options.body});
   if(path.endsWith('/delete-permanently'))return {database_row_deleted:true,deleted:true};
   return {archived:true,data_preserved:true};
  },
 };
 vm.createContext(context);vm.runInContext(snippet,context);
 context.openAdminAccountRemoval(user);
 assert.equal(choices.length,2);
 assert.match(choices[0].textContent,/أرشفة/);
 assert.match(choices[1].textContent,/نهائي/);
 return {window,user,calls,choices,modal,messages,setName:n=>typed=n,reloads:()=>reloads};
}
(async()=>{
 let f=await fixture('active');
 await f.choices[0].onclick();
 assert.deepEqual(f.calls.map(x=>[x.path,x.method]),[['/api/admin/users/synthetic-user','DELETE']]);
 assert(f.modal.closed&&f.reloads()===1);f.window.close();
 f=await fixture('active');
 await f.choices[1].onclick();
 assert.equal(f.calls.length,0,'Permanent delete must refuse an active account until separately archived');
 assert.match(f.messages[0],/حذف سجل/);f.window.close();
 f=await fixture('archived');
 assert.equal(f.choices[0].disabled,true);
 f.setName('incorrect');await f.choices[1].onclick();
 assert.equal(f.calls.length,0,'Wrong typed username cannot mutate account');
 f.setName('sample_user');await f.choices[1].onclick();
 assert.deepEqual(f.calls.map(x=>[x.path,x.method]),[
  ['/api/admin/users/synthetic-user/delete-permanently','POST']]);
 assert.deepEqual(JSON.parse(f.calls[0].body),{confirm_username:'sample_user',confirmation:'DELETE PERMANENTLY'});
 assert(f.modal.closed&&f.reloads()===1);f.window.close();
 f=await fixture('identity_released');
 assert(f.choices[0].disabled);assert(!f.choices[1].disabled);
 await f.choices[1].onclick();
 assert.equal(f.calls.length,1);
 assert.equal(f.calls[0].method,'POST');f.window.close();
 console.log('PASS admin archive separate from physically deleting empty user row with double confirmation and no implicit archive');
})().catch(e=>{console.error(e);process.exitCode=1});
