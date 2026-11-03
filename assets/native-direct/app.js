/* OpenCode Native TEST, browser -> Nginx -> OpenCode. No Gateway APIs. */
(()=>{
'use strict';
const byId=id=>document.getElementById(id);
const root='/native-direct/api/';
const directory='/var/lib/opencode-native-test/workspace';
const address=name=>root+name+'?directory='+encodeURIComponent(directory);
const feedback=(id,value,bad=false)=>{const node=byId(id);node.textContent=value;node.classList.toggle('error',bad)};
let snapshot=null,currentSession='',events=null,parts=new Map();
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
  feedback('connectStatus','قراءة Native ناجحة. أول 50 مزودًا. DeepSeek: '+(next.connected?.includes('deepseek')?'متصل':'غير متصل'));
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
async function connect(){
 const provider=byId('provider').value,secret=byId('apiKey').value.trim();
 if(!provider||!secret){feedback('connectStatus','أدخل مفتاح المزود.',true);return}
 const button=byId('connect');button.disabled=true;
 feedback('connectStatus','جارٍ حفظ مفتاح المزود في OpenCode Native مباشرة...');
 try{
  const accepted=await native('auth/'+encodeURIComponent(provider),'PUT',{type:'api',key:secret});
  if(accepted!==true)throw Error('لم يؤكد OpenCode حفظ المفتاح.');
  byId('apiKey').value='';
  feedback('connectStatus','أكد Native حفظ المفتاح مباشرة. اختبر DeepSeek بإرسال رسالة.');
 }catch(error){feedback('connectStatus',error.message,true)}
 finally{button.disabled=false}
}
async function showHistory(id){
 const items=await native('session/'+encodeURIComponent(id)+'/message');
 const replies=items.filter(m=>m.info?.role==='assistant');
 const text=replies.flatMap(m=>(m.parts||[]).filter(p=>p.type==='text').map(p=>p.text||'')).join('\n');
 if(text)byId('answer').textContent=text;
 if(replies.some(m=>m.info?.error))feedback('chatStatus','أبلغ OpenCode عن خطأ من المزود. راجع الرصيد ومفتاح API.',true);
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
 if(item.type==='session.status'&&p.status?.type==='retry')feedback('chatStatus','Native يعيد المحاولة. افحص رصيد المزود.');
 if(item.type==='session.error')feedback('chatStatus','حدث خطأ داخل OpenCode أو لدى المزود.',true);
 if(item.type==='session.idle'){
  byId('stop').disabled=true;
  feedback('chatStatus','انتهى OpenCode من معالجة الرسالة.');
  showHistory(currentSession).catch(()=>{});
 }
}
async function send(){
 const providerID=byId('provider').value,modelID=byId('model').value,txt=byId('prompt').value.trim();
 if(!providerID||!modelID||!txt)return;
 byId('send').disabled=true;byId('answer').textContent='';parts.clear();
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
byId('connect').addEventListener('click',connect);
byId('refresh').addEventListener('click',catalog);
byId('send').addEventListener('click',send);
byId('stop').addEventListener('click',stop);
window.addEventListener('pagehide',()=>events?.close());
catalog();
})();