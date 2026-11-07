/* OpenCode Native TEST, browser -> Nginx -> OpenCode. No Gateway APIs. */
(()=>{
'use strict';
const byId=id=>document.getElementById(id);
const root='/native-direct/api/';
const directory='/var/lib/opencode-native-test/workspace';
const address=name=>root+name+'?directory='+encodeURIComponent(directory);
const feedback=(id,value,bad=false)=>{const node=byId(id);node.textContent=value;node.classList.toggle('error',bad)};
let snapshot=null,currentSession='',events=null,parts=new Map(),nativeFailureSeen=false;
async function native(name,method='GET',value){
 const request={method,credentials:'same-origin',cache:'no-store'};
 if(value!==undefined){request.headers={'Content-Type':'application/json'};request.body=JSON.stringify(value);}
 const response=await fetch(address(name),request);
 if(!response.ok)throw Error('Native HTTP '+response.status);
 if(response.status===204)return null;
 return response.json();
}
async function catalog(){
 feedback('connectStatus','جارٍ القراءة من كتالوج OpenCode Native الأصلي...');
 try {
  const next=await native('provider');
  if(!Array.isArray(next.all))throw Error('كتالوج OpenCode غير صالح');
  snapshot=next;
  const list=next.all.slice(0,50);
  const deepseek=next.all.find(v=>v.id==='deepseek');
  if(deepseek&&!list.some(v=>v.id==='deepseek'))list.unshift(deepseek);
  const sel=byId('provider'),value=sel.value;
  sel.replaceChildren(...list.slice(0,50).map(v=>new Option(v.name||v.id,v.id)));
  sel.value=list.some(v=>v.id===value)?value:'deepseek';
  refreshModels();
  feedback('connectStatus','قراءة Native ناجحة. أول 50 مزودًا. DeepSeek: '+(next.connected?.includes('deepseek')?'اعتماد موجود في Native (لا يثبت صلاحيته)':'لا يوجد اعتماد'));
 }catch(error){feedback('connectStatus',error.message,true)}
}
function refreshModels(){
 const item=snapshot?.all?.find(v=>v.id===byId('provider').value);
 const models=Object.keys(item?.models||{});
 const choices=models.length?models:['deepseek-chat','deepseek-reasoner'];
 const sel=byId('model'),prior=sel.value;
 sel.replaceChildren(...choices.map(v=>new Option(v,v)));
 sel.value=choices.includes(prior)?prior:choices.includes('deepseek-chat')?'deepseek-chat':choices[0];
}
function failure(value){
 const raw=[value?.name,value?.message,value?.data?.message,value?.data?.statusCode,value?.status].filter(v=>v!=null).join(' ').slice(0,2200);
 if(/401|unauthoriz|incorrect.{0,25}key|invalid.{0,30}(api.?key|token|credential)/i.test(raw))
  return 'رفض المزود مفتاح API: غير صالح أو غير مصرح به (401).';
 if(/403|forbidden|permission.denied/i.test(raw))
  return 'المفتاح لا يملك الصلاحيات المطلوبة لدى هذا المزود (403).';
 if(/429|quota|rate.limit|billing|balance|insufficient|free usage exceeded/i.test(raw))
  return 'رفض المزود الطلب بسبب حدود الاستخدام أو الرصيد.';
 if(/model.{0,30}(not.found|unavailable|not.supported)|invalid.model/i.test(raw))
  return 'النموذج غير متاح في حساب هذا المزود.';
 return 'فشل اختبار المفتاح في OpenCode Native. لا يعني التخزين نجاح المصادقة.';
}
async function showHistory(id){
 const items=await native('session/'+encodeURIComponent(id)+'/message');
 const replies=items.filter(m=>m.info?.role==='assistant');
 const text=replies.flatMap(m=>(m.parts||[]).filter(p=>p.type==='text').map(p=>p.text||'')).join('\n');
 if(text)byId('answer').textContent=text;
 if(replies.some(m=>m.info?.error)){nativeFailureSeen=true;feedback('chatStatus',failure(replies.find(m=>m.info?.error).info.error),true);}
}
function onEvent(event){
 let item;try{item=JSON.parse(event.data)}catch{return}
 const p=item.properties||{},sid=p.sessionID||p.info?.sessionID||p.part?.sessionID;
 if(sid!==currentSession)return;
 if(item.type==='message.part.updated'&&p.part?.type==='text'){
  parts.set(p.part.id,p.part.text||'');
  byId('answer').textContent=[...parts.values()].join('\n');
 }
 if(item.type==='message.part.delta'&&p.field==='text'){
  parts.set(p.partID,(parts.get(p.partID)||'')+(p.delta||''));
  byId('answer').textContent=[...parts.values()].join('\n');
 }
 if(item.type==='session.status'&&p.status?.type==='retry'){nativeFailureSeen=true;feedback('chatStatus',failure({message:p.status.message}),true);}
 if(item.type==='session.error'){nativeFailureSeen=true;feedback('chatStatus',failure(p.error),true);}
 if(item.type==='session.idle'){
  byId('stop').disabled=true;
  if(!nativeFailureSeen)feedback('chatStatus','انتهى OpenCode من معالجة الرسالة.');
  showHistory(currentSession).catch(()=>{});
 }
}
async function send(){
 const providerID=byId('provider').value,modelID=byId('model').value,txt=byId('prompt').value.trim();
 if(!providerID||!modelID||!txt)return;
 byId('send').disabled=true;byId('answer').textContent='';parts.clear();nativeFailureSeen=false;
 try{
  const session=await native('session','POST',{title:'Native direct TEST'});
  if(!session?.id)throw Error('فشل إنشاء جلسة Native');
  currentSession=session.id;
  events?.close();
  events=new EventSource(address('event'),{withCredentials:true});
  events.onmessage=onEvent;
  await new Promise(resolve=>setTimeout(resolve,400));
  await native('session/'+encodeURIComponent(currentSession)+'/prompt_async','POST',{
   model:{providerID,modelID},parts:[{type:'text',text:txt}]
  });
  byId('stop').disabled=false;
  feedback('chatStatus','استلم OpenCode الرسالة. جارٍ انتظار رد '+providerID+'/'+modelID);
 }catch(error){feedback('chatStatus',error.message,true)}
 finally{byId('send').disabled=false}
}
async function stop(){
 if(!currentSession)return;
 try{await native('session/'+encodeURIComponent(currentSession)+'/abort','POST',{});feedback('chatStatus','أوقف OpenCode الطلب.');}
 catch(error){feedback('chatStatus',error.message,true)}
 finally{byId('stop').disabled=true}
}
byId('provider').addEventListener('change',refreshModels);
byId('refresh').addEventListener('click',catalog);
byId('send').addEventListener('click',send);
byId('stop').addEventListener('click',stop);
window.addEventListener('pagehide',()=>events?.close());
catalog();
})();