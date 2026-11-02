/* Help chat: independent of email verification, password reset and GitHub login. */
(() => {
  'use strict';
  const tr=(ar,en)=>document.documentElement.lang==='en'?en:ar;
  const e=(tag,content,cls)=>{const n=document.createElement(tag);if(content!==undefined)n.textContent=content;if(cls)n.className=cls;return n;};
  const api=async(path,options={})=>{
    const r=await fetch('/api/help'+path,{credentials:'same-origin',headers:{'Content-Type':'application/json'},cache:'no-store',...options});
    if(!r.ok)throw Error((await r.json().catch(()=>({}))).detail||'Request failed');
    return r.json();
  };
  const css=e('style');css.textContent=`
  #ogHelpOpen{position:fixed;right:20px;bottom:20px;z-index:15000;border:0;border-radius:30px;background:#2563eb;color:#fff;padding:14px 20px;font-weight:700;box-shadow:0 9px 30px #0004;cursor:pointer}
  #ogHelpPanel{position:fixed;right:20px;bottom:82px;width:min(390px,calc(100vw - 24px));height:min(570px,calc(100dvh - 112px));background:var(--panel,#fff);color:var(--text,#222);border:1px solid var(--border,#ddd);border-radius:18px;box-shadow:0 20px 65px #0004;z-index:15001;display:flex;flex-direction:column;overflow:hidden}
  #ogHelpPanel[hidden],#ogHelpAdmin[hidden]{display:none!important}
  #ogHelpPanel header{display:flex;justify-content:space-between;align-items:center;padding:13px 17px;background:var(--panel2,#f3f4f6)}
  #ogHelpContent{padding:14px;overflow:auto;flex:1;display:flex;flex-direction:column;gap:10px}
  #ogHelpPanel button,#ogHelpAdmin button{cursor:pointer}
  .og-help-item{border:1px solid var(--border,#ddd);border-radius:12px;padding:11px;text-align:start;background:transparent;color:inherit}
  .og-help-bubble{max-width:90%;padding:9px 12px;border-radius:12px;background:var(--panel2,#eee);white-space:pre-wrap;overflow-wrap:anywhere}
  .og-help-bubble.mine{align-self:flex-end;background:#dbeafe;color:#172554}
  .og-help-form{padding:12px;display:grid;gap:8px}
  .og-help-form input,.og-help-form textarea,.og-help-form select,#ogHelpAdmin input,#ogHelpAdmin textarea{padding:9px;border:1px solid var(--border,#ccc);border-radius:8px;background:var(--panel,#fff);color:inherit;width:100%;box-sizing:border-box}
  .og-help-primary{background:#2563eb;color:white;border:0;border-radius:9px;padding:9px}
  #ogHelpAdmin{border:1px solid var(--border,#ddd);border-radius:14px;margin:16px 0;padding:14px}
  #ogHelpAdmin .og-help-ticket{display:block;width:100%;margin:6px 0}
  `;document.head.append(css);
  const toggle=e('button','Help · مساعدة');toggle.id='ogHelpOpen';toggle.type='button';toggle.hidden=true;
  const panel=e('section');panel.id='ogHelpPanel';panel.hidden=true;panel.setAttribute('aria-label',tr('المساعدة','Help'));
  const heading=e('header');const title=e('strong','OpenCode Help');const close=e('button','×');close.type='button';close.setAttribute('aria-label','Close');heading.append(title,close);
  const body=e('div');body.id='ogHelpContent';panel.append(heading,body);
  document.body.append(toggle,panel);
  let config=null,active=null,visible=false;
  function open(){visible=true;panel.hidden=false;renderHome().catch(showError);}
  function shut(){visible=false;panel.hidden=true;}
  toggle.addEventListener('click',()=>visible?shut():open());close.addEventListener('click',shut);
  function button(text,callback,cls='og-help-item'){const x=e('button',text,cls);x.type='button';x.onclick=callback;return x;}
  function showError(error){body.append(e('p',String(error.message||error)));}
  async function renderHome(){
    body.replaceChildren();
    config=await api('/settings');if(!config.enabled){body.append(e('p',tr('المساعدة غير متاحة حاليًا','Help is unavailable')));return;}
    body.append(e('p',config.welcome));
    const tickets=await api('/tickets');
    body.append(button(tr('+ رسالة جديدة','+ New request'),newTicket,'og-help-primary'));
    if(tickets.items.length)body.append(e('strong',tr('رسائلي','My tickets')));
    for(const t of tickets.items)body.append(button(t.subject+' · '+t.status,()=>openTicket(t.id)));
  }
  function newTicket(){
    body.replaceChildren();body.append(button(tr('العودة','Back'),()=>renderHome().catch(showError)));
    const form=e('form',undefined,'og-help-form'),category=e('select'),subject=e('input'),message=e('textarea'),submit=e('button',tr('إرسال','Send'),'og-help-primary');
    subject.placeholder=tr('عنوان الرسالة','Subject');subject.maxLength=180;subject.required=true;
    message.placeholder=tr('اكتب الشكوى أو المقترح','Write your message');message.rows=5;message.maxLength=5000;message.required=true;
    for(const c of config.categories){const option=e('option',c);option.value=c;category.append(option);}
    submit.type='submit';form.append(category,subject,message,submit);body.append(form);
    form.onsubmit=async ev=>{ev.preventDefault();submit.disabled=true;try{
      const t=await api('/tickets',{method:'POST',body:JSON.stringify({category:category.value,subject:subject.value,message:message.value})});
      await openTicket(t.id);
    }catch(err){showError(err);submit.disabled=false;}};
  }
  async function openTicket(id){
    active=id;body.replaceChildren();
    const result=await api('/tickets/'+encodeURIComponent(id));const t=result.ticket;
    body.append(button(tr('العودة','Back'),()=>renderHome().catch(showError)));
    body.append(e('strong',t.subject+' · '+t.status));
    for(const m of result.messages){const bubble=e('div',m.body,'og-help-bubble'+(m.author_role==='customer'?' mine':''));body.append(bubble);}
    if(t.status!=='closed'){
      const form=e('form',undefined,'og-help-form'),input=e('textarea'),send=e('button',tr('إرسال رد','Send reply'),'og-help-primary');
      input.required=true;input.maxLength=5000;input.rows=2;send.type='submit';form.append(input,send);body.append(form);
      form.onsubmit=async ev=>{ev.preventDefault();send.disabled=true;try{await api('/tickets/'+encodeURIComponent(id)+'/messages',{method:'POST',body:JSON.stringify({message:input.value})});await openTicket(id);}catch(err){showError(err);send.disabled=false;}};
    }
  }
  const admin=e('section');admin.id='ogHelpAdmin';admin.hidden=true;
  const adminRoot=document.querySelector('[data-admin-panel="billing"]')?.parentElement || document.querySelector('#adminPage');
  if(adminRoot)adminRoot.append(admin);
  async function adminLoad(){
    if(!adminRoot)return;
    const role=typeof currentUser==='object'&&currentUser?.role;
    if(!['admin','owner'].includes(role))return;
    admin.hidden=false;admin.replaceChildren(e('h2',tr('الشكاوى والمقترحات','Help Inbox')));
    const settings=await api('/settings');
    const configForm=e('form',undefined,'og-help-form'),welcome=e('input'),categories=e('input'),enabled=e('input'),save=e('button',tr('حفظ إعدادات Help','Save Help settings'),'og-help-primary');
    welcome.value=settings.welcome;categories.value=settings.categories.join(', ');enabled.type='checkbox';enabled.checked=settings.enabled;enabled.style.width='auto';save.type='submit';
    configForm.append(e('label',tr('رسالة الترحيب','Welcome message')),welcome,e('label',tr('أنواع الطلبات (افصل بفاصلة)','Categories (comma separated)')),categories,e('label',tr('تفعيل نافذة Help','Enable Help')),enabled,save);
    configForm.onsubmit=async ev=>{ev.preventDefault();try{await api('/admin/settings',{method:'PUT',body:JSON.stringify({enabled:enabled.checked,welcome:welcome.value,categories:categories.value.split(',').map(x=>x.trim()).filter(Boolean)})});await adminLoad();}catch(err){alert(err.message);}};
    admin.append(configForm);
    const items=(await api('/admin/tickets')).items;
    admin.append(e('h3',tr('الرسائل الواردة','Incoming requests')));
    for(const t of items){admin.append(button(t.subject+' · '+t.status,()=>adminTicket(t.id),'og-help-item og-help-ticket'));}
    if(!items.length)admin.append(e('p',tr('لا توجد رسائل','No tickets')));
  }
  async function adminTicket(id){
    admin.replaceChildren(button(tr('العودة للصندوق','Back to inbox'),()=>adminLoad().catch(()=>{})));
    const result=await api('/tickets/'+encodeURIComponent(id));
    admin.append(e('h3',result.ticket.subject));
    for(const m of result.messages)admin.append(e('p',(m.author_role==='customer'?'👤 ':'🛟 ')+m.body));
    const statuses=e('select');for(const x of ['open','pending','resolved','closed']){const opt=e('option',x);opt.value=x;statuses.append(opt);}statuses.value=result.ticket.status;
    statuses.onchange=async()=>{await api('/admin/tickets/'+encodeURIComponent(id)+'/status',{method:'PATCH',body:JSON.stringify({status:statuses.value})});await adminTicket(id);};
    admin.append(statuses);
    if(result.ticket.status!=='closed'){
      const form=e('form',undefined,'og-help-form'),message=e('textarea'),send=e('button',tr('إرسال الرد','Reply'),'og-help-primary');message.required=true;message.maxLength=5000;send.type='submit';form.append(message,send);admin.append(form);
      form.onsubmit=async ev=>{ev.preventDefault();await api('/tickets/'+encodeURIComponent(id)+'/messages',{method:'POST',body:JSON.stringify({message:message.value})});await adminTicket(id);};
    }
  }
  async function check(){
    try{const r=await fetch('/api/help/settings',{credentials:'same-origin',cache:'no-store'});toggle.hidden=!r.ok;if(r.ok){config=await r.json();if(!config.enabled)toggle.hidden=true;}}
    catch{toggle.hidden=true;}
    const role=typeof currentUser==='object'&&currentUser?.role;
    if(['admin','owner'].includes(role))adminLoad().catch(()=>{});
  }
  window.addEventListener('load',check);document.addEventListener('click',ev=>{if(ev.target?.closest?.('[data-admin-view]'))setTimeout(check,50);});
})();
