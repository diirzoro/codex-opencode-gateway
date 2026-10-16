const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');const src=fs.readFileSync('app.js','utf8'),c={};vm.createContext(c);vm.runInContext(src.slice(src.indexOf('function workspaceMessagePresentation('),src.indexOf('async function refreshMessages(){')),c);const render=c.workspaceMessagePresentation;
assert.equal(render({role:'assistant',text:'',state:'completed',activity:[{tool:'todowrite'}]},false,null).omit,true);
const metadata=render({role:'assistant',text:'',state:'completed',activity:[{tool:'write',files:[{path:'app.js'}]}]},false,null);assert.equal(metadata.omit,false);assert.equal(metadata.feedback,false);assert.equal(metadata.activity.length,1);
const failure=render({role:'assistant',text:'',state:'failed'},false,null);assert.equal(failure.feedback,true);assert.equal(failure.state,'failed');
const final=render({role:'assistant',text:'',state:'completed'},true,'completed');assert.equal(final.feedback,true);assert.equal(final.omit,false);
const waiting=render({role:'assistant',text:'',state:'working'},true,'waiting_approval');assert.equal(waiting.state,'waiting_approval');assert.equal(waiting.feedback,true);
assert.equal(render({role:'assistant',text:'اكتب الخطوة الحقيقية',activity:[]},true,'submitted').hasText,true);assert.equal(render({role:'user',text:'',attachments:[{name:'image.png'}]},false,null).omit,false);
console.log('6 passed: Todo-only noise omitted, metadata retained without filler, errors/final-empty/approval waits visible, actual narration and user attachments preserved (VM)');
