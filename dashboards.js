/* Workspace-first client interaction. All operational requests use Gateway APIs. */
(() => {
  window.workspaceFirstEnabled=true;
  const q=id=>document.getElementById(id),tr=(en,ar)=>lang==='ar'?ar:en;
  const admin=()=>['admin','owner'].includes(currentUser?.role);
  const texts=[];
  function text(tag,en,ar,cls){const node=textElement(tag,tr(en,ar),cls);texts.push([node,en,ar]);return node;}
  function btn(id,en,ar,action,cls='button ghost small'){const node=text('button',en,ar,cls);node.id=id;node.type='button';node.onclick=async()=>{try{await action();}catch(error){toast(error.message);}};return node;}
  function title(en,ar){return text('h2',en,ar);}
  const home=document.createElement('main');home.id='workspaceHomePage';home.className='page portal-page';
  home.innerHTML='<div class="workspace-home portal-content"><div class="work-home-heading"></div><div class="home-actions"></div><label class="session-search"><input id="homeSessionSearch" type="search"></label><section><h2 id="homeProjectsTitle"></h2><div id="homeProjects"><p role="status">Loading projects… / جارٍ تحميل المشاريع…</p></div></section><section><h2 id="homeSessionsTitle"></h2><div id="homeSessions"><p role="status">Loading conversations… / جارٍ تحميل المحادثات…</p></div></section></div>';
  q('app-main').append(home);
  home.querySelector('.work-home-heading').append(text('span','YOUR WORKSPACE','مساحة عملك','eyebrow'),text('h1','What will you build today?','ماذا ستبني اليوم؟'),text('p','Open a project, continue a conversation, or start something new.','افتح مشروعًا، أكمل محادثة، أو ابدأ فكرة جديدة.','lead'));
  home.querySelector('.home-actions').append(btn('homeNewProject','New project','مشروع جديد',()=>page('onboarding'),'button'),btn('homeConnections','Settings · Connections','الإعدادات · الاتصالات',()=>openConnections()));
  texts.push([q('homeProjectsTitle'),'Projects / workspaces','المشاريع / مساحات العمل'],[q('homeSessionsTitle'),'Recent conversations','المحادثات الأخيرة']);
  q('homeSessionSearch').setAttribute('aria-label','Search sessions');
  const settings=document.createElement('main');settings.id='connectionsPage';settings.className='page portal-page';
  settings.innerHTML='<div class="portal-content connections-content"><div class="connections-heading"></div><div id="connectionsProviders"></div><div id="connectionsGithub"></div><div id="connectionsRuntime"></div><section id="connectionsWorkspace" class="manage-card"></section></div>';
  q('app-main').append(settings);q('connectionsProviders').innerHTML='<section class="manage-card"><label>Workspace / مساحة العمل<select disabled><option>Restoring workspace… / جارٍ استعادة مساحة العمل…</option></select></label><label>Search providers / البحث عن المزوّدات<input type="search" role="combobox" placeholder="Search providers…"></label><p role="status">Loading OpenCode providers… / جارٍ تحميل مزوّدي OpenCode…</p></section>';settings.querySelector('.connections-heading').append(text('h1','Settings · Connections','الإعدادات · الاتصالات'),text('p','Choose a workspace provider and use its OpenCode authentication method.','اختر مزوّد مساحة العمل واستخدم طريقة المصادقة المتاحة في OpenCode.','lead'),btn('connectionsReturn','Return to workspace','العودة لمساحة العمل',()=>activeWorkspace?page('workspacePage'):page('workspaceHomePage')));
  protectedPages.add('workspaceHomePage');protectedPages.add('connectionsPage');
  Object.assign(copy.en,{workspaceHome:'Workspace / Home',connectionsSettings:'Settings / Connections'});
  Object.assign(copy.ar,{workspaceHome:'مساحة العمل / الرئيسية',connectionsSettings:'الإعدادات / الاتصالات'});
  Object.assign(copy.en,{ui51:'Local project · 50 MB',ui53:'GitHub-backed project',githubHintText:'Choose a repository and branch authorized by your GitHub App connection.'});
  Object.assign(copy.ar,{ui51:'مشروع محلي · 50 MB',ui53:'مشروع مرتبط بـGitHub',githubHintText:'اختر مستودعًا وفرعًا مصرحًا بهما عبر اتصال GitHub App الخاص بك.'});
  Object.assign(copy.en,{accountPageTitle:'My account & profile',accountPageLead:'Your details and preferences, clearly organized.',accountReturnWorkspace:'Return to workspace',accountProfileTab:'My profile',accountSecurityTab:'Security & sign-in',accountDetailsTitle:'My details & preferences',accountDetailsLead:'Contact details and display settings.',accountLanguage:'Language',accountAppearance:'Appearance',accountLight:'Light',accountDark:'Dark',accountAdditional:'Sign-in methods, storage and data policies'});
  Object.assign(copy.ar,{accountPageTitle:'حسابي وملفي الشخصي',accountPageLead:'بياناتك وتفضيلاتك، في مكان واضح وبسيط.',accountReturnWorkspace:'العودة لمساحة العمل',accountProfileTab:'ملفي الشخصي',accountSecurityTab:'الأمان والدخول',accountDetailsTitle:'بياناتي وتفضيلاتي',accountDetailsLead:'معلومات التواصل وإعدادات العرض.',accountLanguage:'اللغة',accountAppearance:'المظهر',accountLight:'فاتح',accountDark:'داكن',accountAdditional:'طرق الدخول والتخزين وسياسات البيانات'});
  Object.assign(copy.en,{adminEmailNav:'Email & Verification',adminEmailCenterTitle:'Email & Verification',adminEmailCenterLead:'Manage email delivery, verification, and support inbox securely.',adminEmailProviders:'Providers',adminEmailServices:'Services',adminEmailInbox:'Support Inbox',adminEmailRefresh:'Refresh status',adminEmailDelivery:'Email Delivery'});
  Object.assign(copy.ar,{adminEmailNav:'البريد والتحقق الإلكتروني',adminEmailCenterTitle:'البريد والتحقق الإلكتروني',adminEmailCenterLead:'إدارة إرسال البريد والتحقق من الحسابات وبريد الدعم بأمان.',adminEmailProviders:'المزوّدون',adminEmailServices:'الخدمات',adminEmailInbox:'بريد الدعم',adminEmailRefresh:'تحديث الحالة',adminEmailDelivery:'إرسال البريد الإلكتروني'});
  Object.assign(copy.en,{adminMailMessagesTitle:'Email messages',adminMailReceived:'Received',adminMailSent:'Sent',adminMailRefresh:'Refresh messages',adminMailConnection:'Connection diagnostics',adminMailConnectionHelp:'Messages are retrieved from Resend, not fabricated.',adminMailReadKey:'Read-capable Resend API key',adminMailSaveKey:'Save encrypted key'});
  Object.assign(copy.ar,{adminMailMessagesTitle:'رسائل البريد الإلكتروني',adminMailReceived:'الوارد',adminMailSent:'المرسل',adminMailRefresh:'تحديث الرسائل',adminMailConnection:'تفاصيل الاتصال',adminMailConnectionHelp:'تُجلب الرسائل من Resend مباشرة ولا تُعرض بيانات وهمية.',adminMailReadKey:'مفتاح Resend بصلاحية القراءة',adminMailSaveKey:'حفظ المفتاح مشفّرًا'});
  Object.assign(copy.en,{subscriptionNoRefund:'Accepted payments cannot be cancelled or refunded.',clientAccountLead:'Personal details and preferences.'});
  Object.assign(copy.ar,{subscriptionNoRefund:'المدفوعات المقبولة غير قابلة للإلغاء أو الاسترداد.',clientAccountLead:'البيانات الشخصية والتفضيلات.'});
  function navButton(id,key,icon,action){const node=document.createElement('button');node.id=id;node.dataset.go=action;node.innerHTML='<svg class="nav-icon"><use href="'+icon+'"/></svg><span data-i18n="'+key+'">'+t(key)+'</span>';node.onclick=()=>page(action);return node;}
  q('clientNav').insertBefore(navButton('clientWorkspaceHome','workspaceHome','#icon-opencode','workspaceHomePage'),q('clientNav').querySelector('button'));
  q('clientNav').querySelector('[data-client-view=dashboard]')?.remove();
  q('clientNav').querySelector('[data-client-view=ai]')?.remove();q('clientNav').querySelector('[data-client-view=github]')?.remove();
  q('clientNav').append(navButton('clientConnections','connectionsSettings','#icon-settings','connectionsPage'));
  const oldClientView=window.openClientView;
  window.openClientView=name=>['ai','github'].includes(name)?openConnections(name==='ai'?'providers':'github'):oldClientView(name);
  q('clientNav').querySelectorAll('[data-client-view]').forEach(button=>button.onclick=()=>window.openClientView(button.dataset.clientView));
  q('adminNav').querySelectorAll('[data-admin-view]').forEach(button=>button.onclick=()=>window.openAdminView(button.dataset.adminView));
  let serviceOwner=null;
  let emailProviderConfig={},emailStatus=null;
  function showEmailProvider(provider){
    const cfg=emailProviderConfig[provider]||{};
    const brevo=provider==='brevo';
    q('adminSmtpHost').value=brevo?'https://api.brevo.com/v3/smtp/email':'smtp.resend.com';
    q('adminSmtpPort').value=brevo?'':'587';q('adminSmtpPort').disabled=brevo;
    q('adminSmtpUsername').value=brevo?'':'resend';q('adminSmtpTls').value=brevo?'https':'starttls';
    q('adminSenderEmail').value=cfg.sender||'no-reply@opencode-gateway.codes';
    q('adminSenderName').value=cfg.sender_name||'OpenCode Gateway';
    q('adminSmtpSecret').value='';
    q('adminSmtpSave').disabled=!['resend','brevo'].includes(provider)||emailStatus?.settings_schema_ready===false||emailStatus?.credential_storage_ready===false;
    q('adminSmtpTest').disabled=!emailStatus?.configured||provider!==emailStatus.provider;
    if(q('adminEmailTransportNote'))q('adminEmailTransportNote').textContent=brevo?
      tr('Brevo uses its HTTPS API key, not an SMTP key. Sender authorization in Brevo is still required. The mailbox below continues to read Resend; switching senders does not migrate mail.','يستخدم Brevo مفتاح API عبر HTTPS وليس مفتاح SMTP. يجب توثيق المرسل لدى Brevo. يظل صندوق البريد أدناه تابعًا لـResend؛ تبديل الإرسال لا ينقل الرسائل.'):
      tr('Resend SMTP defaults are ready. Add the API key and save. Sending-only keys cannot read mail; mailbox access requires an appropriately authorized read key.','إعدادات Resend SMTP جاهزة. أضف مفتاح API واحفظ. مفتاح الإرسال فقط لا يقرأ البريد؛ القراءة تحتاج مفتاحًا بالصلاحية المناسبة.');
  }

  async function loadServiceCenter(){
    if(!admin())return;
    const notice=q('adminServiceNotice');if(!notice)return;
    const owner=currentUser.id;
    if(serviceOwner!==owner){
      serviceOwner=owner;
      for(const id of ['adminInboxMessages','adminMailReader'])q(id)?.replaceChildren();
      for(const id of ['adminComposeTo','adminComposeSubject','adminComposeBody','adminSmtpSecret','adminInboxApiKey'])if(q(id))q(id).value='';
      if(q('adminMailCompose'))q('adminMailCompose').hidden=true;
      if(q('adminMailComposeBackdrop'))q('adminMailComposeBackdrop').hidden=true;
      if(q('adminMailSendReceipt'))q('adminMailSendReceipt').textContent='';
    }
    try{
      const data=await api('/api/admin/service-integrations');if(!admin()||currentUser.id!==owner)return;const e=data.email||{};
      notice.textContent=e.configured?tr('Email configured · delivery not yet tested','البريد مهيّأ · لم يُختبر التسليم بعد'):tr('Email delivery is not configured','إرسال البريد غير مهيّأ');if(e.settings_schema_ready===false)notice.textContent+=' · '+tr('Apply TEST migration 0021 before saving settings','يلزم تطبيق ترحيل TEST رقم 0021 قبل حفظ الإعدادات');
      emailStatus=e;emailProviderConfig=e.provider_configurations||{[e.provider||'resend']:e};
      q('adminEmailProvider').value=['resend','brevo'].includes(e.provider)?e.provider:'smtp';showEmailProvider(q('adminEmailProvider').value);
      q('adminSmtpTest').title=e.configured?tr('Sends one real test email to the specified recipient','يرسل رسالة اختبار حقيقية واحدة إلى العنوان المحدد'):tr('Save the selected provider API key first','احفظ مفتاح API للمزوّد المختار أولاً');
      if(!e.credentials_configured)notice.textContent+=' · '+tr('Selected provider API key is missing. Verification messages cannot be sent.','مفتاح API للمزوّد المختار غير موجود. لا يمكن إرسال رسائل التفعيل.');
      if(e.credential_storage_ready===false)notice.textContent+=' · '+tr('Gateway credential encryption is not configured.','تشفير اعتمادات Gateway غير مُعدّ.');
      if(!q('adminSmtpTestRecipient').value)q('adminSmtpTestRecipient').value=currentUser.email||'';
      q('adminSmtpTest').onclick=async()=>{
      const button=q('adminSmtpTest'),field=q('adminSmtpTestRecipient'),status=q('adminServiceNotice');
      if(button.disabled||!admin())return;
      const to=field.value.trim();if(!to||!field.reportValidity()){status.textContent=tr('Enter a valid test recipient you control.','أدخل بريد اختبار صحيحًا تملكه.');return;}
      const owner=currentUser.id;button.disabled=true;status.textContent=tr('Sending one test email…','جارٍ إرسال رسالة اختبار واحدة…');
      try{
        const result=await api('/api/admin/service-integrations/send-email',{method:'POST',body:JSON.stringify({to,subject:'OpenCode Gateway TEST · email delivery test',body:'This is a test email requested from the TEST administration panel. SMTP acceptance does not prove inbox delivery. No action is required.'})});
        if(!admin()||currentUser.id!==owner)return;
        if(!result.sent)throw Error(tr('Sending was not confirmed.','لم يُؤكد الإرسال.'));
        status.textContent=tr('The selected provider accepted the test email. Check the recipient inbox and spam folder to confirm delivery.','قبل المزوّد المختار رسالة الاختبار. تحقق من الوارد والبريد المزعج لدى المستلم لتأكيد وصولها.');
      }catch(error){if(admin()&&currentUser.id===owner)status.textContent=error.message;}
      finally{if(admin()&&currentUser.id===owner)button.disabled=false;}
    };
    q('adminSmtpSecret').value='';
      const captionsAr={registration_verification:'التحقق من الحساب الجديد',password_reset:'استعادة كلمة المرور',welcome_email:'رسائل الترحيب',subscription_expiry:'انتهاء الاشتراك',low_balance:'انخفاض الرصيد',account_suspension:'تعليق الحساب',payment_receipt:'إيصالات الدفع',renewal_reminder:'تذكير التجديد',system_updates:'تحديث النظام',login_security:'تنبيه دخول جديد',password_changed:'تغيير كلمة المرور',email_changed:'تغيير البريد',payment_failed:'فشل الدفع',trial_expiring:'قرب انتهاء الفترة التجريبية',support_received:'رسالة دعم جديدة',support_unanswered:'رسائل دون رد',service_incident:'أعطال الخدمة',mail_delivery_failure:'فشل تسليم البريد',unusual_activity:'نشاط غير معتاد',backup_status:'حالة النسخ الاحتياطي'};
      const captionsEn={registration_verification:'New account verification',password_reset:'Password reset',welcome_email:'Welcome email',subscription_expiry:'Subscription expiry',low_balance:'Low balance',account_suspension:'Account suspension',payment_receipt:'Payment receipt',renewal_reminder:'Renewal reminder',system_updates:'System updates',login_security:'New sign-in alert',password_changed:'Password changed',email_changed:'Email changed',payment_failed:'Payment failed',trial_expiring:'Trial expiring',support_received:'New support message',support_unanswered:'Unanswered support',service_incident:'Service incidents',mail_delivery_failure:'Mail delivery failure',unusual_activity:'Unusual activity',backup_status:'Backup status'};
      const list=q('adminServiceToggles');list.replaceChildren();list.className='admin-service-table-wrap';
      const table=document.createElement('table');table.className='admin-service-table';
      const head=document.createElement('thead'),header=document.createElement('tr');
      for(const label of [tr('Service','الخدمة'),tr('Enabled','تفعيل'),tr('Actual status','الحالة الفعلية')])header.append(textElement('th',label));
      head.append(header);const rows=document.createElement('tbody');table.append(head,rows);list.append(table);
      for(const item of data.services||[]){
        const caption=(lang==='ar'?captionsAr:captionsEn)[item.id]||item.id;
        const card=document.createElement('tr');
        const toggleCell=document.createElement('td');
        const name=textElement('strong',caption),state=textElement('small');let reportButton=null;
        const describe=()=>{if(reportButton)reportButton.disabled=!item.enabled;state.textContent=item.enabled?tr('Enabled','مفعّل'):tr('Disabled','معطّل');if(item.reason==='Requires an authorized Resend Full access read key')state.textContent+=' · '+tr('Requires authorized Resend inbox reading','يلزم تفويض قراءة صندوق Resend');if(item.reason==='Manual administrator report')state.textContent+=' · '+tr('Manual administrator report','تقرير يدوي من الإدارة');if(item.enabled&&!e.configured)state.textContent+=' · '+tr('Email sender setup required','يلزم إعداد مرسل البريد');};describe();
        const top=document.createElement('td');const label=document.createElement('label');label.textContent=caption;top.append(label);
        const statusCell=document.createElement('td');statusCell.append(state);
        if(item.editable&&item.available){
          const toggle=document.createElement('input');toggle.type='checkbox';toggle.setAttribute('role','switch');toggle.checked=Boolean(item.enabled);
          toggle.id='email-service-'+item.id;toggle.setAttribute('aria-label',caption);label.htmlFor=toggle.id;toggleCell.append(toggle);
          toggle.onchange=async()=>{
            if(!admin()||currentUser.id!==owner)return;
            const previous=Boolean(item.enabled),requested=toggle.checked;toggle.disabled=true;
            try{
              const saved=await api('/api/admin/service-integrations/services/'+encodeURIComponent(item.id),{method:'PUT',body:JSON.stringify({enabled:requested})});
              if(!admin()||currentUser.id!==owner)return;
              item.enabled=Boolean(saved.enabled);toggle.checked=item.enabled;describe();notice.textContent=tr('Service preference saved.','حُفظ إعداد الخدمة.');
            }catch(error){if(admin()&&currentUser.id===owner){toggle.checked=previous;notice.textContent=error.message;}}
            finally{if(admin()&&currentUser.id===owner)toggle.disabled=false;}
          };
        }
        else{const toggle=document.createElement('input');toggle.type='checkbox';toggle.disabled=true;toggle.setAttribute('aria-label',caption);toggleCell.append(toggle);state.textContent=item.reason==='Apply migration 0027'?tr('Requires database migration 0027','يلزم ترحيل قاعدة البيانات 0027'):tr('Not available yet — no active event integration','غير متاحة بعد — لم تُربط بأحداث الخلفية');}
        if(item.available&&item.reason==='Manual administrator report'){
          reportButton=document.createElement('button');reportButton.type='button';reportButton.className='button ghost small';reportButton.textContent=tr('Send report to my admin inbox','إرسال تقرير إلى بريدي الإداري');reportButton.disabled=!item.enabled;
          reportButton.onclick=async()=>{
            const detail=await window.requestInput(tr('Actual report text (no keys or passwords). The report is sent to your own admin email.','نص التقرير الفعلي دون مفاتيح أو كلمات مرور. يُرسل إلى بريد حسابك الإداري.'),'');if(!detail?.trim())return;
            reportButton.disabled=true;
            try{const result=await api('/api/admin/service-integrations/services/'+encodeURIComponent(item.id)+'/report',{method:'POST',body:JSON.stringify({user_id:owner,event_id:crypto.randomUUID(),detail:detail.trim()})});if(currentUser?.id===owner)notice.textContent=result.accepted?tr('Provider accepted the report; delivery is not yet verified.','قبل المزوّد التقرير؛ لم يُتحقق من وصوله بعد.'):tr('Submission is uncertain; do not resend automatically.','نتيجة الإرسال غير مؤكدة؛ لا تُعد الإرسال تلقائيًا.');}catch(error){if(currentUser?.id===owner)notice.textContent=error.message;}finally{if(currentUser?.id===owner)reportButton.disabled=!item.enabled;}
          };statusCell.append(reportButton);
        }
        card.append(top,toggleCell,statusCell);rows.append(card);
      }

    }catch(error){if(admin()&&currentUser.id===owner)notice.textContent=error.message;}
  }
  window.gatewayLoadServiceCenter=loadServiceCenter;
  if(q('adminServiceCenter')){
    q('adminServiceRefresh')?.addEventListener('click',loadServiceCenter);
    q('adminServiceCenter').querySelectorAll('[data-service-tab]').forEach(button=>button.addEventListener('click',()=>{
      const tab=button.dataset.serviceTab;
      q('adminProvidersTab').hidden=tab!=='providers';
      q('adminServicesTab').hidden=tab!=='services';
      q('adminInboxTab').hidden=tab!=='inbox';
      if(tab==='inbox')readSupportInbox();
      q('adminServiceCenter').querySelectorAll('[data-service-tab]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
    }));
    let mailFolder='received';
    let currentDraftId=null;
    let composeReturnFocus=null;
    function setComposeOpen(open,focusId){
      const panel=q('adminMailCompose');
      if(open&&panel.hidden)composeReturnFocus=document.activeElement;
      panel.hidden=!open;q('adminMailComposeBackdrop').hidden=!open;
      if(open&&focusId)q(focusId).focus();
      if(!open&&composeReturnFocus?.isConnected)composeReturnFocus.focus();
    }

    let mailRevision=0, readerRevision=0;
    const mailAlive=owner=>admin()&&currentUser?.id===owner&&q('adminInboxTab')?.isConnected;
    function updateMailFolders(){
      for(const [id,folder] of [['adminMailReceived','received'],['adminMailSent','sent'],['adminMailDrafts','drafts']]){
        if(mailFolder===folder)q(id).setAttribute('aria-current','page');else q(id).removeAttribute('aria-current');
      }
    }
    function filterMail(){
      const term=q('adminMailSearch').value.trim().toLocaleLowerCase();
      for(const row of q('adminInboxMessages').querySelectorAll('[data-mail-search]'))row.hidden=!row.dataset.mailSearch.includes(term);
    }
    function preserveCompose(){
      if(q('adminComposeTo').value||q('adminComposeSubject').value||q('adminComposeBody').value){
        setComposeOpen(true);
        q('adminComposeStatus').textContent=tr('Finish or save the current draft before opening another message.','أكمل المسودة الحالية أو احفظها قبل إنشاء رسالة أخرى.');return false;
      }
      return true;
    }
    async function readSupportInbox(){
      if(!admin())return;
      const owner=currentUser.id,revision=++mailRevision,folder=mailFolder;
      ++readerRevision;updateMailFolders();
      const status=q('adminInboxStatus'),list=q('adminInboxMessages'),reader=q('adminMailReader');
      const current=()=>mailAlive(owner)&&mailRevision===revision&&mailFolder===folder;
      status.textContent=tr('Loading messages…','جارٍ تحميل الرسائل…');list.replaceChildren();reader.replaceChildren();
      q('adminInboxTab').querySelector('.mailbox')?.classList.remove('has-selection');
      reader.append(textElement('p',tr('Select a message to read','اختر رسالة لقراءتها'),'mailbox-empty'));
      try{
        const sent=folder==='sent',drafts=folder==='drafts';
        const endpoint='/api/admin/service-integrations/'+(drafts?'drafts':sent?'sent-emails':'support-inbox');
        const result=await api(endpoint);if(!current())return;
        if(!drafts&&!result.configured){status.textContent=tr('Message access needs a read-capable Resend key. See Connection diagnostics.','قراءة الرسائل تحتاج مفتاح Resend بصلاحية القراءة. راجع تفاصيل الاتصال.');return;}
        status.textContent=tr('Messages: ','الرسائل: ')+result.items.length+(result.has_more?tr(' · Showing the first 50',' · عرض أول 50 رسالة'):'');
        for(const msg of result.items){
          const row=document.createElement('button');row.type='button';row.className='mailbox-row';row.setAttribute('aria-pressed','false');
          const subject=msg.subject||tr('(No subject)','(بدون موضوع)');
          const party=drafts?msg.to:(sent?(Array.isArray(msg.to)?msg.to.join(', '):''):msg.from);
          row.dataset.mailSearch=[subject,party,msg.preview||''].join(' ').toLocaleLowerCase();
          row.append(textElement('strong',subject),textElement('small',party||tr('No recipient','بدون مستلم')),textElement('small',(msg.created_at||msg.updated_at||'')+(sent?' · '+msg.status:'')));
          if(drafts&&msg.preview)row.append(textElement('small',msg.preview));
          row.onclick=async()=>{
            if(!current())return;
            if(drafts&&!preserveCompose())return;
            const token=++readerRevision;
            const selected=()=>current()&&readerRevision===token;
            for(const item of list.querySelectorAll('.mailbox-row'))item.setAttribute('aria-pressed',String(item===row));
            reader.replaceChildren(textElement('p',tr('Loading message…','جارٍ تحميل الرسالة…')));
            q('adminInboxTab').querySelector('.mailbox')?.classList.add('has-selection');
            try{
              const item=await api(endpoint+'/'+encodeURIComponent(msg.id));if(!selected())return;
              if(drafts){
                currentDraftId=item.id;q('adminComposeTo').value=item.to;q('adminComposeSubject').value=item.subject;q('adminComposeBody').value=item.body;
                q('adminComposeStatus').textContent='';setComposeOpen(true);q('adminComposeBody').focus();
              }
              reader.replaceChildren();
              const back=textElement('button',tr('← Back to messages','العودة للرسائل'),'button ghost small');back.type='button';
              back.onclick=()=>{q('adminInboxTab').querySelector('.mailbox')?.classList.remove('has-selection');row.focus();};
              reader.append(back,textElement('h3',subject),textElement('p',party||''));
              const body=textElement('div',drafts?item.body:(item.text||tr('No plain text body available','لا يوجد نص للرسالة')),'support-mail-text');body.dir='auto';reader.append(body);
              if(drafts){
                const remove=textElement('button',tr('Delete draft','حذف المسودة'),'button ghost');remove.type='button';
                remove.onclick=async()=>{
                  if(!selected())return;
                  if(!await window.confirmAction(tr('Delete this saved draft?','حذف هذه المسودة المحفوظة؟')))return;
                  if(!selected())return;remove.disabled=true;
                  try{
                    await api(endpoint+'/'+encodeURIComponent(msg.id),{method:'DELETE'});if(!selected())return;
                    if(currentDraftId===msg.id)currentDraftId=null;
                    await readSupportInbox();
                  }catch(error){if(selected()){toast(error.message);remove.disabled=false;}}
                };reader.append(remove);
              }
              if(!sent&&!drafts){
                const reply=textElement('button',tr('Reply','رد'),'button ghost');reply.type='button';
                reply.onclick=()=>{
                  if(!selected()||!preserveCompose())return;
                  currentDraftId=null;q('adminComposeTo').value=(String(msg.from||'').match(/<([^<>@\s]+@[^<>@\s]+)>/)?.[1]||String(msg.from||'')).trim();
                  q('adminComposeSubject').value=/^re:/i.test(subject)?subject:'Re: '+subject;q('adminComposeBody').value='';
                  q('adminComposeStatus').textContent='';setComposeOpen(true);q('adminComposeBody').focus();
                };reader.append(reply);
              }
            }catch(error){if(selected())reader.replaceChildren(textElement('p',error.message));}
          };
          list.append(row);
        }
        if(!result.items.length)list.append(textElement('p',drafts?tr('No saved drafts.','لا توجد مسودات محفوظة.'):tr('No messages returned by Resend.','لم يُرجع Resend أي رسائل.'),'mailbox-empty'));
        filterMail();
      }catch(error){if(current())status.textContent=error.message;}
    }
    q('adminMailSearch').oninput=filterMail;
    const composePanel=q('adminMailCompose');
    q('adminComposeClose').onclick=()=>setComposeOpen(false);
    q('adminComposeExpand').onclick=()=>{
      const expanded=composePanel.classList.toggle('is-expanded');
      q('adminComposeExpand').setAttribute('aria-pressed',String(expanded));
      q('adminComposeExpand').textContent=expanded?tr('Restore size','حجم عادي'):tr('Expand','تكبير');
    };
    composePanel.addEventListener('keydown',event=>{
      if(event.key==='Escape'){event.preventDefault();setComposeOpen(false);return;}
      if(event.key!=='Tab')return;
      const fields=[...composePanel.querySelectorAll('button,input,textarea,select,[tabindex]')].filter(el=>!el.disabled&&el.tabIndex>=0);
      const first=fields[0],last=fields[fields.length-1];
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
    });

    q('adminMailComposeOpen').onclick=()=>{
      if(q('adminComposeTo').value||q('adminComposeSubject').value||q('adminComposeBody').value){setComposeOpen(true);q('adminComposeBody').focus();return;}
      currentDraftId=null;q('adminComposeTo').value='';q('adminComposeSubject').value='';q('adminComposeBody').value='';
      q('adminComposeStatus').textContent='';setComposeOpen(true);q('adminComposeTo').focus();
    };
    q('adminComposeSaveDraft').onclick=async()=>{
      if(!admin())return;const owner=currentUser.id;
      const button=q('adminComposeSaveDraft'),status=q('adminComposeStatus');
      const draft={to:q('adminComposeTo').value.trim(),subject:q('adminComposeSubject').value.trim(),body:q('adminComposeBody').value};
      button.disabled=true;
      try{
        const url='/api/admin/service-integrations/drafts'+(currentDraftId?'/'+encodeURIComponent(currentDraftId):'');
        const result=await api(url,{method:currentDraftId?'PUT':'POST',body:JSON.stringify(draft)});
        if(!mailAlive(owner))return;
        currentDraftId=null;q('adminComposeTo').value='';q('adminComposeSubject').value='';q('adminComposeBody').value='';
        status.textContent=tr('Draft saved securely.','تم حفظ المسودة مشفرة.');
        setComposeOpen(false);
        mailFolder='drafts';await readSupportInbox();
      }catch(error){status.textContent=error.message;}
      finally{button.disabled=false;}
    };
    q('adminComposeCancel').onclick=()=>{setComposeOpen(false);q('adminComposeStatus').textContent='';};
    q('adminComposeSend').onclick=async()=>{
      const send=q('adminComposeSend'),status=q('adminComposeStatus'),receipt=q('adminMailSendReceipt');
      if(!admin()||send.disabled)return;const owner=currentUser.id;
      const to=q('adminComposeTo').value.trim(),subject=q('adminComposeSubject').value.trim(),body=q('adminComposeBody').value;
      if(!to||!q('adminComposeTo').reportValidity()||!subject||!body.trim()){status.textContent=tr('Recipient, subject, and message are required.','المستلم والموضوع والرسالة مطلوبة.');return;}
      const controls=['adminComposeTo','adminComposeSubject','adminComposeBody','adminComposeSaveDraft'].map(q);
      controls.forEach(control=>control.disabled=true);send.disabled=true;status.textContent=tr('Sending…','جارٍ الإرسال…');receipt.textContent='';
      try{
        const result=await api('/api/admin/service-integrations/send-email',{method:'POST',body:JSON.stringify({to,subject,body})});
        if(!mailAlive(owner))return;
        if(!result.sent)throw Error(tr('Sending was not confirmed. Your draft was kept; no automatic retry was made.','لم يُؤكد الإرسال. احتُفظ بالمسودة ولم تُعد المحاولة تلقائيًا.'));
        q('adminComposeTo').value='';q('adminComposeSubject').value='';q('adminComposeBody').value='';
        const savedId=currentDraftId;currentDraftId=null;
        receipt.textContent=tr('✓ Message accepted for sending to ','✓ قُبلت الرسالة للإرسال إلى ')+to+tr('. Inbox delivery is not yet verified.','؛ وصولها إلى الوارد لم يُتحقق منه بعد.');
        receipt.dataset.state='success';setComposeOpen(false);toast(tr('Message accepted for sending','قُبلت الرسالة للإرسال'));
        if(savedId){
          try{await api('/api/admin/service-integrations/drafts/'+encodeURIComponent(savedId),{method:'DELETE'});}
          catch(error){if(mailAlive(owner))receipt.textContent+=' '+tr('The old saved draft could not be removed.','تعذّر حذف المسودة المحفوظة القديمة.');}
        }
        if(mailAlive(owner)){mailFolder='sent';await readSupportInbox();}
      }catch(error){
        if(mailAlive(owner)){status.textContent=error.message;setComposeOpen(true);}
      }finally{if(mailAlive(owner)){send.disabled=false;controls.forEach(control=>control.disabled=false);}}
    };
    q('adminMailReceived').onclick=()=>{mailFolder='received';readSupportInbox();};
    q('adminMailSent').onclick=()=>{mailFolder='sent';readSupportInbox();};
    q('adminMailDrafts').onclick=()=>{mailFolder='drafts';readSupportInbox();};
    q('adminInboxRead').onclick=readSupportInbox;
    q('adminInboxSaveKey').onclick=async()=>{
      const field=q('adminInboxApiKey'),button=q('adminInboxSaveKey');
      if(!field.value){q('adminInboxStatus').textContent='أدخل مفتاح قراءة البريد أولًا';return;}
      button.disabled=true;
      try{
        await api('/api/admin/service-integrations/inbox-credential',{method:'PUT',body:JSON.stringify({api_key:field.value})});
        q('adminInboxStatus').textContent='تم حفظ مفتاح القراءة مشفرًا';
      }catch(error){q('adminInboxStatus').textContent=error.message;}
      finally{field.value='';button.disabled=false;}
    };
    q('adminSmtpSecret').value='';
    q('adminSmtpSave').onclick=async()=>{
      const button=q('adminSmtpSave'),key=q('adminSmtpSecret');
      const sender=q('adminSenderEmail').value.trim();
      if(!sender){q('adminServiceNotice').textContent='أدخل بريد الإرسال أولًا';return;}
      button.disabled=true;
      try{
        const result=await api('/api/admin/service-integrations/email',{
          method:'PUT',
          body:JSON.stringify({provider:q('adminEmailProvider').value,smtp_from:sender,sender_name:q('adminSenderName').value.trim()||'OpenCode Gateway',...(key.value?{api_key:key.value}:{})})
        });
        key.value='';
        q('adminServiceNotice').textContent=result.configured?'حُفظ مزوّد الإرسال المختار بأمان · Saved securely':'Configuration not ready';
        await loadServiceCenter();
      }catch(error){q('adminServiceNotice').textContent=error.message;}
      finally{key.value='';button.disabled=false;}
    };
    q('adminEmailProvider').onchange=()=>{
      showEmailProvider(q('adminEmailProvider').value);
      q('adminServiceNotice').textContent=tr('Provider selection is not active until saved. Previously saved provider credentials are preserved.','لا يتفعّل اختيار المزوّد إلا بعد الحفظ. تُحفظ بيانات المزوّد السابق للعودة إليه.');
    };
  }
  async function loadHome(){
    const data=await api('/api/dashboard');const projects=q('homeProjects');projects.replaceChildren();
    for(const project of data.projects){for(const workspace of project.workspaces){const row=textElement('div','','home-project-row');row.append(textElement('strong',project.name),textElement('small',(project.repository||tr('Local project','مشروع محلي'))+' · '+workspace.status));if(workspace.cache?.warning||workspace.cache?.expired)row.append(textElement('small',window.workspaceRetentionNotice(workspace.cache),'project-retention-warning'));row.append(btn('home-open-'+workspace.id,'Open workspace','فتح مساحة العمل',()=>openWorkspace(project,workspace)),btn('home-session-'+workspace.id,'New session','جلسة جديدة',async()=>{await openWorkspace(project,workspace);await createWorkspaceSession();}));projects.append(row);}}
    if(!projects.children.length)projects.append(text('p','No projects yet. Create your first workspace.','لا توجد مشاريع بعد. أنشئ مساحة عملك الأولى.','home-empty'));
    const sessions=q('homeSessions');sessions.replaceChildren();
    for(const session of data.recent_sessions){const project=data.projects.find(p=>p.workspaces.some(w=>w.id===session.workspace_id));const workspace=project?.workspaces.find(w=>w.id===session.workspace_id);if(!workspace)continue;const row=btn('home-recent-'+session.id,session.title,session.title,async()=>{await openWorkspace(project,workspace);await selectSession(session);},'home-session-row');row.append(textElement('small',project.name+' · '+session.status));row.dataset.search=(session.title+' '+project.name).toLowerCase();sessions.append(row);}
    if(!sessions.children.length)sessions.append(text('p','No conversations yet. Open a project and start a session.','لا توجد محادثات بعد. افتح مشروعًا وابدأ جلسة.','home-empty'));
    q('homeSessionSearch').placeholder=tr('Search recent sessions…','ابحث في الجلسات الأخيرة…');
    renderEntitlement();q('homeSessionSearch').oninput=()=>sessions.querySelectorAll('[data-search]').forEach(row=>row.hidden=!row.dataset.search.includes(q('homeSessionSearch').value.trim().toLowerCase()));
  }
  async function openConnections(focus){await page('connectionsPage');if(focus)q(focus==='github'?'connectionsGithub':'connectionsProviders').scrollIntoView({block:'start',behavior:'smooth'});}
  window.openConnections=openConnections;
  async function usableWorkspace(workspace){
    const owner=currentUser?.id;
    let available=false;
    try{const owned=await api('/api/workspaces/'+encodeURIComponent(workspace.id));available=owned.id===workspace.id&&owned.files_available!==false;}
    catch(error){if(![403,404,410].includes(error.status))throw error;}
    if(currentUser?.id!==owner)return false;
    if(!available){
      if(activeWorkspace?.id===workspace.id){stopEvents();workspaceSelectionRevision++;activeWorkspace=activeProject=activeSession=null;}
      try{if(localStorage.getItem('og-workspace')===workspace.id)localStorage.removeItem('og-workspace');}catch(error){}
    }
    return available;
  }
  // Sign-in restores owned context without creating a project or replaying work.
  window.openClientWorkspace=async function(){
    if(!currentUser)return page('authPage');
    return openWorkspaceAfterLogin();
  };
  async function loadConnections(){
    const root=q('connectionsProviders'),query=root.querySelector('input[role=combobox]')?.value;
    if(query)root.dataset.providerQuery=query;
    const providersJob=window.renderManagement(root,'providers').catch(error=>{
      const status=root.querySelector('[role=status]');if(status)status.textContent=error.message;
      root.append(btn('retrySettings','Retry','إعادة المحاولة',()=>loadConnections()));
    });
    // GitHub status is independent from Native provider discovery; never block Connections readiness.
    const githubJob=loadConnectionsGithub().catch(error=>{const section=q('connectionsGithub');if(section) section.append(textElement('p',error.message));});
    const runtime=q('connectionsRuntime');runtime.replaceChildren(title('Native OpenCode discovery (TEST)','اكتشاف OpenCode المباشر (TEST)'),text('p','Loading native agents…','جارٍ تحميل الوكلاء مباشرة…'));
    // Connections page: read native agent discovery through Nginx, not the Python
    // workspace runtime. This describes the independent TEST native service only.
    const runtimeJob=(async()=>{
      if(!activeWorkspace?.id){
        if(runtime.isConnected)runtime.lastElementChild.textContent=tr('Select a workspace for native discovery.','اختر مساحة عمل لاكتشاف الوكلاء.');
        return;
      }
      const catalog=await window.workspaceRuntime.loadAgents(activeWorkspace.id);
      const agents=catalog?.agents;
      if(!Array.isArray(agents))throw new Error('Invalid native agents response');
      if(runtime.isConnected)runtime.lastElementChild.textContent=
        tr('Native OpenCode agents via Nginx: ','وكلاء OpenCode المباشرين عبر Nginx: ')+agents.length;
    })().catch(error=>{
      if(runtime.isConnected)runtime.lastElementChild.textContent=
        tr('Native agent discovery unavailable: ','تعذر استدعاء الوكلاء مباشرة: ')+error.message;
    });
    // Let providers determine initial readiness. GitHub and native agents update independently.
    void githubJob;
    void runtimeJob;
    await providersJob;
  }
  let githubConnectionRender=0;
  async function loadConnectionsGithub(){
    const github=q('connectionsGithub'),owner=currentUser?.id,render=++githubConnectionRender;
    github.replaceChildren(title('GitHub account / authorization','حساب GitHub / التفويض'));
    const result=new URLSearchParams(location.search).get('github');
    const messages={
      connected:['GitHub authorization accepted. Check the connected account below.','تم قبول تفويض GitHub. تحقق من الحساب المتصل أدناه.'],
      denied:['You declined GitHub authorization; your projects remain unchanged.','لم توافق على تفويض GitHub، ومشاريعك محفوظة دون تغيير.'],
      'install-required':['First choose at least one repository in the GitHub App installation, then reconnect.','اختر مستودعًا واحدًا على الأقل في تثبيت تطبيق GitHub ثم أعد الربط.'],
      'multiple-installations':['More than one installation is available; select the intended installation first.','توجد تثبيتات متعددة؛ حدد التثبيت الصحيح أولًا.'],
      configuration:['GitHub App credentials or encryption are unavailable on Gateway.','بيانات تطبيق GitHub أو مفتاح التشفير غير متاحة على Gateway.'],
      error:['GitHub authorization could not be confirmed; no new repository was imported.','تعذر تأكيد تفويض GitHub؛ لم يُستورد أي مستودع جديد.']
    };
    const status=await api('/api/github/status');if(owner!==currentUser?.id||render!==githubConnectionRender)return;
    if(messages[result]){
      const message=result==='connected'&&!status.connected
        ?tr('This GitHub connection is no longer active. Start a new link to continue.','هذا الربط مع GitHub لم يعد نشطًا. ابدأ ربطًا جديدًا للمتابعة.')
        :tr(...messages[result]);
      github.append(textElement('p',message,'api-message'));
    }
    github.append(textElement('p',status.connected?(status.account_login||'GitHub'):tr('Not connected','غير متصل')));
    if(!status.configured)github.append(textElement('p',tr('The administrator must configure GitHub App credentials before customer authorization.','يجب أن تكمل الإدارة بيانات تطبيق GitHub قبل تفويض العملاء.'),'api-message'));
    // User authorization is distinct from App installation. Never reinstall
    // merely because Gateway disconnected or an expiring user token was lost.
    if(!status.connected)github.append(textElement('p',
      tr('GitHub is disconnected from your Gateway account. A new explicit link is required before repository access; an installed GitHub App does not mean this account is connected.','GitHub مفصول عن حسابك في Gateway. يلزم بدء ربط جديد صراحةً قبل الوصول للمستودعات؛ بقاء التطبيق مثبتًا على GitHub لا يعني استمرار ربط الحساب.'),
      'muted-small'));
    const authorize=btn('settingsAuthorizeGithub',status.connected?'Reauthorize GitHub':'Start new GitHub link',status.connected?'تجديد تفويض GitHub':'بدء ربط GitHub جديد',async()=>{
      if(!await window.confirmAction(tr('Connect your GitHub account to this Gateway account? GitHub may ask you to approve repository access. Your existing project files stay unchanged.','هل تريد ربط حساب GitHub بحسابك في Gateway؟ قد يطلب GitHub موافقتك على الوصول للمستودعات. ستبقى ملفات مشاريعك كما هي.')))return;
      window.location.assign('/api/github/authorize');
    });
    authorize.disabled=!status.configured;github.append(authorize);
    if(!status.connected||result==='install-required'){
      const install=btn('settingsInstallGithub','Install App / choose repositories','تثبيت التطبيق / اختيار المستودعات',async()=>{
        if(!await window.confirmAction(tr('Open GitHub to install the App or change the repositories you permit?','فتح GitHub لتثبيت التطبيق أو تغيير المستودعات التي تسمح له بالوصول إليها؟')))return;
        window.location.assign('/api/github/install');
      });
      install.disabled=!status.configured;github.append(install);
    }
    if(status.connected){
      github.append(btn('settingsOpenGithubRepository','Choose authorized repository / branch','اختيار مستودع وفرع مصرح بهما',()=>window.openGithubProject()));
      github.append(btn('settingsDisconnectGithub','Disconnect','إلغاء الربط',async()=>{
        if(!await window.confirmAction(tr('Disconnect this Gateway account from GitHub? Imported workspaces and files will remain.','فصل هذا الحساب عن GitHub؟ ستبقى مساحات العمل المستوردة وملفاتها محفوظة.')))return;
        await api('/api/github/disconnect',{method:'POST'});
        // Forget an old success banner after an explicit disconnect.
        const url=new URL(location.href);url.searchParams.delete('github');
        window.history.replaceState(window.history.state,'',url.pathname+url.search+url.hash);
        await loadConnectionsGithub();
      }));
      try{
        const repos=await api('/api/github/repositories');if(owner!==currentUser?.id||render!==githubConnectionRender)return;
        github.append(textElement('p',repos.length
          ?tr('Authorized repositories: ','المستودعات المصرح بها: ')+repos.length+tr('. Choose one explicitly to open a working copy.','. اختر مستودعًا صراحةً لفتح نسخة عمل.')
          :tr('No authorized repositories. Use GitHub installation settings to select repositories.','لا توجد مستودعات مصرح بها. اختر المستودعات في إعدادات تثبيت GitHub.'),'muted-small'));
        if(!repos.length){
          const install=btn('settingsChooseGithubRepositories','Choose repositories in GitHub','اختيار المستودعات في GitHub',async()=>{
            if(await window.confirmAction(tr('Open GitHub installation settings to choose accessible repositories?','فتح إعدادات تثبيت GitHub لاختيار المستودعات المسموح بها؟')))window.location.assign('/api/github/install');
          });github.append(install);
        }
      }catch(error){
        if(owner===currentUser?.id&&render===githubConnectionRender)github.append(textElement('p',error.message,'api-message'));
      }
    }
    github.append(text('p','Only repositories explicitly authorized for this customer may be selected. A GitHub project appears in your workspace after you choose a repository, branch and optional working directories.','يمكن اختيار المستودعات التي فوّضها هذا العميل فقط. يظهر مشروع GitHub في مساحة العمل بعد اختيار المستودع والفرع ومجلدات العمل الاختيارية.'));
  }

  let workAccess=false,entitlement=null,workspaceInitialized=false;
  let updateSend=()=>{},refreshChoices=async()=>{},syncWorkspacePolling=()=>{},loadWorkspaceDetails=()=>{},renderStorage=()=>{};
  let createWorkspaceSession=async()=>{initializeWorkspace();return createWorkspaceSession();};
  const homeAccess=textElement('div','','access-notice');homeAccess.id='homeAccessState';home.querySelector('.work-home-heading').append(homeAccess);
  const workspaceAccess=textElement('div','','access-notice');workspaceAccess.id='workspaceAccessState';q('promptForm').before(workspaceAccess);
  const workspaceDays=textElement('span','','workspace-days');workspaceDays.id='workspaceRemainingDays';workspaceDays.hidden=true;
  function renderEntitlement(){
    if(!entitlement)return;
    const access=entitlement.access,days=access.remaining_days;
    const label=(access.kind==='trial'?tr('Core trial · ','تجربة الأساس · '):tr('Subscription · ','الاشتراك · '))+days+tr(' days left',' يومًا متبقيًا');
    homeAccess.replaceChildren(textElement('span',workAccess?label:tr('Your access has expired. Subscribe to continue.','انتهت مدة الوصول. اشترك للمتابعة.')));
    const advanced=access.advanced_trial;
    homeAccess.append(textElement('span',advanced.state==='not_started'?tr(' · Advanced trial: 10 days from first use',' · المتقدمة: 10 أيام من أول استخدام'):tr(' · Advanced trial: ',' · التجربة المتقدمة: ')+advanced.remaining_days+tr(' days remaining',' يوم متبقٍ')));
    workspaceDays.hidden=false;
    workspaceDays.textContent=workAccess?label:tr('Access expired','انتهت مدة الوصول');
    workspaceDays.title=access.ends_at?tr('Expires: ','تنتهي: ')+new Date(access.ends_at).toLocaleString(lang):'';
    const urgent=workAccess&&(days===2||days===1);
    workspaceDays.dataset.urgency=!workAccess?'expired':urgent?String(days):'';
    workspaceAccess.replaceChildren();workspaceAccess.hidden=true;workspaceAccess.dataset.urgency='';
    const subscribe=()=>window.openClientView('billing');
    if(!workAccess||urgent){
      workspaceAccess.hidden=false;workspaceAccess.dataset.urgency=workspaceDays.dataset.urgency;
      workspaceAccess.append(textElement('span',!workAccess?
        tr('Execution and coding access is frozen until renewal. Account data and payment records are preserved; access expiry does not delete project files.','يُجمّد الوصول للتنفيذ والبرمجة حتى التجديد. بيانات الحساب وسجلات الدفع محفوظة؛ انتهاء الصلاحية لا يحذف ملفات المشروع.'):
        days===1?tr('Access expires within one day. Renew to keep coding without interruption.','ينتهي الوصول خلال يوم واحد. جدّد للاستمرار في البرمجة دون انقطاع.'):
        tr('Two days of access remain. Renew soon to keep coding.','متبقي يومان من الوصول. جدّد قريبًا لمتابعة البرمجة.')),
        btn('workspaceSubscribe','Subscribe / Renew','اشترك / جدّد',subscribe));
      if(!workAccess&&access.account_retention){
        const retention=access.account_retention;
        workspaceAccess.append(textElement('small',tr('Account data is retained for at least ','تُحفظ بيانات الحساب لمدة لا تقل عن ')+retention.minimum_days+tr(' days after expiry, then the customer is archived and operational secrets are removed. Project-file storage follows its separate policy.',' يومًا بعد انتهاء الصلاحية، ثم يُؤرشف العميل وتُنظّف بيانات التشغيل الحساسة. تتبع ملفات المشروع سياسة تخزين مستقلة.')));
      }
      if(!workAccess)homeAccess.append(btn('homeSubscribe','Subscribe / Renew','اشترك / جدّد',subscribe));
    }
    if(workAccess&&!access.advanced_integrations){
      workspaceAccess.hidden=false;
      workspaceAccess.append(textElement('span',tr('Advanced integrations expired. Core access and free platform models remain available.','انتهت تجربة التكاملات المتقدمة. يبقى الوصول الأساسي ونماذج المنصة المجانية متاحين.')),btn('workspaceAdvancedUpgrade','View plans','عرض الخطط',subscribe));
    }
    q('homeNewProject').disabled=!workAccess;q('promptInput').disabled=!workAccess;
    document.querySelectorAll('#workspacePage .new-session,#homeProjects [id^=home-session-],#sessionList .session,#homeSessions [id^=home-recent-]').forEach(n=>n.disabled=!workAccess);
    if(!workAccess){q('sendMessage').disabled=true;q('commitButton').disabled=true;q('pushButton').disabled=true;}
  }
  async function refreshEntitlement(){if(!currentUser||admin())return;entitlement=await api('/api/profile/access');workAccess=entitlement.access.allowed;if(!workAccess){if(activeSession&&!q('stopAgent').disabled){try{await api('/api/sessions/'+activeSession.id+'/stop',{method:'POST'});}catch(error){toast(error.message);}q('stopAgent').disabled=true;}stopEvents();}renderEntitlement();}
  const previousPage=page;page=async function(id){await authReady;await interfaceReady;if(admin()&&['workspaceHomePage','connectionsPage'].includes(id))id='adminPage';if(id==='workspacePage'&&currentUser&&!admin())initializeWorkspace();await previousPage(id);if(!currentUser)return;if(!admin()&&['workspaceHomePage','workspacePage','onboarding'].includes(id))refreshEntitlement().then(()=>updateSend()).catch(error=>toast(error.message));if(!admin()&&id==='workspacePage'&&activeWorkspace){refreshChoices().catch(error=>toast(error.message));loadWorkspaceDetails();}if(admin()){if(q('adminPage').classList.contains('active')&&document.querySelector('[data-admin-panel=billing].active'))await loadPaymentOrders(true);return;}if(q(id)?.classList.contains('active')){if(id==='workspaceHomePage')loadHome().catch(error=>toast(error.message));if(id==='connectionsPage')loadConnections().catch(error=>toast(error.message));}};
  const previousShow=showPage;showPage=function(id){if(id==='adminPage'&&!admin()){toast('Administrator access required');id=currentUser?'workspaceHomePage':'authPage';}if(admin()&&['workspaceHomePage','connectionsPage','workspacePage'].includes(id))id='adminPage';q('sessionSidebar').classList.remove('open');overlay(false);try{if(currentUser)localStorage.setItem('og-page',id);}catch(error){}previousShow(id);syncWorkspacePolling();q('clientWorkspaceHome').classList.toggle('active',['workspaceHomePage','workspacePage'].includes(id));q('clientConnections').classList.toggle('active',id==='connectionsPage');if(['workspaceHomePage','workspacePage','connectionsPage'].includes(id))q('clientNav').querySelectorAll('[data-client-view]').forEach(n=>n.classList.remove('active'));};
  const lazyOpenWorkspace=async function(project,workspace,options={}){
    if(options.navigate===false&&!workspaceInitialized){
      if(!await usableWorkspace(workspace))return;
      // Composer attachment state does not exist until initializeWorkspace() runs.
      // Do not call clearAttachments() during lightweight workspace restoration;
      // doing so aborts restore/settings with "clearAttachments is not defined".
      stopEvents();workspaceSelectionRevision++;activeProject=project;activeWorkspace=workspace;activeSession=null;
      try{localStorage.setItem('og-workspace',workspace.id);}catch(error){}return;
    }
    initializeWorkspace();if(!workspaceInitialized||openWorkspace===lazyOpenWorkspace)throw new Error('Workspace initialization did not complete');return openWorkspace(project,workspace,options);
  };
  openWorkspace=lazyOpenWorkspace;
  const previousOpenGithubProject=window.openGithubProject;
  window.openGithubProject=(...args)=>{initializeWorkspace();if(typeof previousOpenGithubProject!=='function')throw new Error('GitHub project opener is unavailable');return previousOpenGithubProject(...args);};
  function initializeWorkspace(){
    if(workspaceInitialized)return;workspaceInitialized=true;
  const shell=document.querySelector('#workspacePage .workspace-shell'),center=shell.querySelector('.agent-column'),pane=q('sessionSidebar');
  shell.classList.add('workspace-first','reference-workspace');
  q('manageProviders')?.remove();

  const projectbar=center.querySelector('.project-bar');projectbar.querySelector('.statuses').hidden=true;
  projectbar.prepend(text('h1','Workspace','مساحة العمل','workspace-heading'));
  projectbar.querySelector('.repo-title')?.setAttribute('hidden','');
  const context=textElement('div','','composer-context');projectbar.append(context);const workspaceDetails=q('connectionsWorkspace');workspaceDetails.append(title('Workspace details','تفاصيل مساحة العمل'),q('workspaceRepo'),q('workspaceBranch'));const gitState=textElement('span',tr('GitHub: checking…','GitHub: جارٍ التحقق…'));gitState.id='workspaceGithubState';workspaceDetails.append(gitState,q('runtimeStatus'));context.append(workspaceDays);
  const storageChip=textElement('span',tr('Storage: …','التخزين: …'));storageChip.id='workspaceStorage';context.append(storageChip);
  let storageTimer=null,storagePending=null,storageData=null;
  renderStorage=()=>{if(!storageData)return;storageChip.hidden=false;storageChip.title=window.workspaceRetentionNotice(storageData.cache);storageChip.textContent=tr('Storage used: ','التخزين المستخدم: ')+storageData.used_mb+' MB · '+tr('remaining','المتبقي')+' '+(storageData.remaining_bytes/1048576).toFixed(1)+' MB';};
  async function loadStorage(){
    if(!activeWorkspace){storageChip.textContent='';return;}
    const workspaceId=activeWorkspace.id;if(storagePending?.id===workspaceId)return storagePending.promise;
    const promise=(async()=>{try{const s=await api('/api/workspaces/'+workspaceId+'/storage');if(activeWorkspace?.id===workspaceId){storageData=s;renderStorage();}}catch(error){if(activeWorkspace?.id===workspaceId)storageChip.textContent='';}})();
    storagePending={id:workspaceId,promise};try{return await promise;}finally{if(storagePending?.promise===promise)storagePending=null;}
  }
  let dashboardNavReady=false;
  syncWorkspacePolling=function(){
    if(dashboardNavReady)placeDashboardNav();
    const needed=activeWorkspace&&!document.hidden&&q('workspacePage').classList.contains('active');
    if(!needed){clearInterval(storageTimer);storageTimer=null;return;}
    if(!storageTimer)storageTimer=setInterval(()=>loadStorage().catch(()=>{}),15000);
  }
  document.addEventListener('visibilitychange',syncWorkspacePolling);
  const controls=q('promptForm').lastElementChild;controls.classList.add('composer-controls');
  const activity=textElement('section','','workspace-activity');activity.id='workspaceActivity';activity.setAttribute('aria-label',tr('OpenCode activity','نشاط OpenCode'));
  const activityStage=textElement('p','','activity-stage');activityStage.setAttribute('role','status');
  const activitySummary=textElement('div','','activity-summary');
  const capabilityView=document.createElement('details');capabilityView.className='agent-capabilities';capabilityView.append(text('summary','Tools & skills','الأدوات والمهارات'));
  const capabilityBody=textElement('div');capabilityView.append(capabilityBody);workspaceDetails.append(capabilityView);activity.append(activityStage,activitySummary);
  let activitySession=null;
  function keepChatActivity(){const feed=q('agentFeed');if(!activeSession)return;
    if(activitySession!==activeSession.id){activitySession=activeSession.id;activity.dataset.state='';activityStage.textContent=activitySummary.textContent='';}
    const host=[...feed.querySelectorAll(':scope>.agent-response')].at(-1)||feed;
    if(activity.parentElement!==host)host.append(activity);
  }
  new MutationObserver(keepChatActivity).observe(q('agentFeed'),{childList:true});
  let capabilityWorkspace='',capabilityPending=false;
  capabilityView.addEventListener('toggle',async()=>{
    if(!capabilityView.open||!activeWorkspace||capabilityPending||capabilityWorkspace===activeWorkspace.id)return;
    const id=activeWorkspace.id,owner=currentUser?.id;capabilityPending=true;capabilityBody.textContent=tr('Loading workspace OpenCode tools and skills…','جارٍ تحميل أدوات ومهارات OpenCode للمساحة…');
    try{
      const data=await api('/api/workspaces/'+id+'/runtime/capabilities?view=agent');
      if(activeWorkspace?.id!==id||currentUser?.id!==owner)return;
      capabilityBody.replaceChildren(text('p','Reported by this workspace runtime. Agent permissions and admin policy still apply; the agent chooses tools and skills during execution.','مُعلنة من بيئة هذه المساحة. تبقى صلاحيات الوكيل وسياسة الإدارة مطبّقة؛ يختار الوكيل الأدوات والمهارات أثناء التنفيذ.'));
      const tools=textElement('p',tr('Tools: ','الأدوات: ')+(data.tools||[]).map(tool=>tool+(data.tool_policy?.[tool]===false?tr(' (Restricted)',' (مقيّد)'):'')).join(', '));
      const skills=textElement('p',tr('Skills: ','المهارات: ')+(data.skills||[]).map(skill=>skill.name).join(', '));capabilityBody.append(tools,skills);
      if(!data.tools?.length)tools.textContent=tr('No tools reported by OpenCode.','لم يعلن OpenCode عن أدوات.');
      if(!data.skills?.length)skills.textContent=tr('No skills reported by OpenCode.','لم يعلن OpenCode عن مهارات.');
      for(const error of Object.values(data.errors||{}))capabilityBody.append(textElement('p',error.detail));
      if(!Object.keys(data.errors||{}).length)capabilityWorkspace=id;
    }catch(error){if(activeWorkspace?.id===id&&currentUser?.id===owner)capabilityBody.textContent=error.message;}
    finally{capabilityPending=false;}
  });
  const stages={submitted:['Request accepted','تم قبول الطلب'],analyzing:['Analyzing project','تحليل المشروع'],tool_activity:['Tool activity','نشاط أداة'],reading_files:['Reading files','قراءة الملفات'],editing:['Editing file','تعديل ملف'],running_command:['Running command','تشغيل أمر'],running_tests:['Running validation','تشغيل الفحص'],waiting_approval:['Waiting for approval','بانتظار الموافقة'],completed:['Completed','اكتمل'],failed:['Failed','فشل'],cancelled:['Cancelled','أُلغي التنفيذ']};
  const toolNames={read:['Read files','قراءة الملفات'],list:['List files','عرض الملفات'],glob:['Search files','البحث عن الملفات'],grep:['Search content','البحث في المحتوى'],write:['Write files','كتابة الملفات'],edit:['Edit files','تعديل الملفات'],apply_patch:['Apply changes','تطبيق التغييرات'],bash:['Run command','تشغيل أمر'],question:['Ask a question','طلب توضيح'],todowrite:['Update task list','تحديث قائمة المهام'],todoread:['Read task list','قراءة قائمة المهام'],webfetch:['Read web page','قراءة صفحة ويب'],websearch:['Search the web','البحث في الويب']};
  const toolName=tool=>tr(...(toolNames[tool]||['Run tool','تشغيل أداة']));
  const statuses={pending:['Waiting','بانتظار التنفيذ'],running:['Running','قيد التشغيل'],completed:['Completed','اكتمل'],error:['Failed','فشل']};
  const operations={inspected:['Inspected','تم فحصه'],changed:['Changed','تم تغييره'],created:['Created','تم إنشاؤه'],deleted:['Deleted','تم حذفه'],moved:['Moved','تم نقله']};
  const activityLabel=(map,value)=>tr(...(map[value]||['Reported','مُعلن']));
  const workLabel=row=>(row.status==='interrupted'?tr('Execution ended; last reported step: ','انتهى التنفيذ؛ آخر خطوة مُعلنة: '):row.status==='running'?tr('In progress: ','جارٍ '):row.status==='completed'?tr('Completed: ','اكتمل: '):row.status==='error'?tr('Failed: ','تعذّر: '):tr('Waiting: ','بانتظار: '))+toolName(row.tool);
  function activityDetail(row){
    const parts=[];
    if(row.command)parts.push(row.command+(row.command_limited?tr(' (arguments hidden)',' (المعاملات مخفية)'):''));
    for(const file of (row.files||[]).slice(0,5))parts.push(file.path);
    if(Number.isInteger(row.exit_code))parts.push(tr('Exit code: ','رمز الخروج: ')+row.exit_code);
    if(Number.isFinite(row.duration_ms)&&row.duration_ms>=0)parts.push((row.duration_ms/1000).toFixed(1)+tr(' s',' ث'));
    return parts.join(' · ');
  }
  window.renderWorkspaceEventLine=(kind,data={})=>{
    if(kind==='activity'&&['todowrite','todoread'].includes(data.tool)){window.refreshWorkspaceTodos?.();return;}
    keepChatActivity();
    const final=typeof activeSession==='undefined'?null:activeSession?.execution_status;
    if(['completed','failed','cancelled'].includes(final))kind=final;
    activity.dataset.state=kind==='activity'?(data.status||'pending'):kind;
    const label=kind==='activity'?[workLabel(data),activityDetail(data)].filter(Boolean).join(' · '):stages[kind]?activityLabel(stages,kind):activityStage.textContent;
    if(activityStage.textContent!==label)activityStage.textContent=label;
  };
  window.renderMessageActivity=(host,rows)=>{
    rows=rows.filter(row=>!['todowrite','todoread'].includes(row.tool));
    const ended=typeof activeSession!=='undefined'&&['completed','failed','cancelled'].includes(activeSession?.execution_status);
    if(ended)rows=rows.map(row=>['pending','running'].includes(row.status)?{...row,status:'interrupted'}:row);
    if(!rows.length)return;
    const details=document.createElement('details');details.className='message-activity'+(rows.some(row=>row.native)?' native-activity':'');
// Native OpenCode owns tool execution. Keep the UI summary compact;
// show failures by default, but never expose tool arguments automatically.
details.open=rows.some(row=>row.status==='error'||row.native&&['pending','running'].includes(row.status));
if(rows.some(row=>row.native))details.dataset.activityId='group';
const count=rows.length;
details.append(textElement('summary',tr('Tool activity','نشاط الأدوات')+' · '+count));const list=document.createElement('ul');
    for(const row of rows){const item=document.createElement('li'),step=document.createElement('details');step.className='tool-execution';step.dataset.state=row.status;step.open=row.status==='error';
      const heading=textElement('summary',workLabel(row)+(row.native&&row.files?.length?' · '+row.files.slice(0,3).map(f=>f.path).join(', '):''));step.append(heading);
      if(row.native){step.dataset.activityId=row.id;for(const node of [details,step]){if(node.dataset.tracked)continue;node.dataset.tracked='1';const summary=node.querySelector('summary');summary?.addEventListener('click',()=>{node.dataset.userToggled='1';});node.addEventListener('toggle',()=>{if(node.dataset.userToggled)node.dataset.userOpen=String(node.open);});}}
      if(row.command){const pre=textElement('pre','','tool-execution-code'),command=textElement('code',row.command+(row.command_limited?tr(' (arguments hidden)',' (المعاملات مخفية)'):''),'activity-command');pre.dir='ltr';pre.append(command);step.append(pre);}
      const result=textElement('div','','tool-execution-result');
      if(row.status==='error'){
        const explanations={file_not_found:['The requested file/path was not found. Check the project and filename before retrying.','الملف أو المسار المطلوب غير موجود. تحقق من المشروع واسم الملف قبل إعادة المحاولة.'],permission_denied:['Access was denied. Review the requested path and permissions; do not bypass protection.','رُفض الوصول. راجع المسار والصلاحيات دون تجاوز الحماية.'],approval_rejected:['The requested operation was rejected. It was not authorized to continue.','رُفضت الموافقة على العملية؛ لم يُسمح لها بالمتابعة.'],command_not_found:['The required executable was not found in this runtime.','برنامج تشغيل الأمر المطلوب غير موجود في هذه البيئة.'],timeout:['The tool exceeded its time limit. Inspect its result before retrying.','تجاوزت الأداة المهلة. تحقق من نتيجتها قبل إعادة المحاولة.'],unsupported_format:['The tool cannot read this file format. Use a supported format or an authorized reader.','الأداة لا تدعم صيغة هذا الملف. استخدم صيغة مدعومة أو أداة قراءة مناسبة.'],interrupted:['Tool execution was interrupted before it finished. No successful result was confirmed; review the conversation before retrying.','توقف تنفيذ الأداة قبل اكتماله؛ لم تتأكد نتيجة ناجحة. راجع المحادثة قبل إعادة الطلب.'],invalid_arguments:['The tool rejected its input. The agent needs to correct the arguments before trying again.','رفضت الأداة المدخلات؛ يحتاج الوكيل إلى تصحيح معاملات الطلب قبل إعادة المحاولة.'],tool_unavailable:['This tool is unavailable or disabled for the selected agent. Use an available tool without bypassing permissions.','هذه الأداة غير متاحة أو معطلة للوكيل المحدد. استخدم أداة متاحة دون تجاوز الصلاحيات.'],dependency_missing:['A required module or dependency is missing. It must be prepared in the authorized isolated runtime.','وحدة أو اعتمادية مطلوبة غير موجودة؛ يلزم تجهيزها في بيئة التشغيل المعزولة والمصرح بها.'],network_unavailable:['The tool could not reach its required service or resolve its hostname. Check service availability and permitted networking.','تعذر على الأداة الاتصال بالخدمة المطلوبة أو تحديد عنوانها. تحقق من توفر الخدمة والاتصال المسموح به.'],tool_failed:['The operation failed. OpenCode did not provide a recognized cause that can be displayed here. Ask the agent to inspect this failure before retrying.','فشلت العملية، ولم تتوفر تفاصيل واضحة قابلة للعرض عن سببها. اطلب من الوكيل فحص هذا الفشل قبل إعادة المحاولة.']};
        result.append(textElement('p',tr(...(explanations[row.error_kind]||explanations.tool_failed)),'tool-error-explanation'));
      }
      if(Number.isInteger(row.exit_code))result.append(textElement('small',tr('Exit code: ','رمز الخروج: ')+row.exit_code));
      if(Number.isFinite(row.duration_ms)&&row.duration_ms>=0)result.append(textElement('small',(row.duration_ms/1000).toFixed(1)+tr(' s',' ث')));
      for(const key of ['matches','count'])if(Number.isInteger(row[key]))result.append(textElement('small',(key==='matches'?tr('Matches: ','نتائج: '):tr('Items: ','عناصر: '))+row[key]));
      for(const file of row.files||[]){const text=file.path+' · '+(row.status==='completed'?activityLabel(operations,file.operation):tr('Requested','مطلوب'));
        if(row.native&&file.operation!=='deleted'){
          const owner=currentUser?.id,workspaceId=row.workspace_id,link=textElement('button',text,'native-file-link');link.type='button';link.dir='auto';link.title=tr('Open owned Workspace file','فتح ملف مساحة العمل المملوكة');link.onclick=()=>{if(currentUser?.id===owner&&activeWorkspace?.id===workspaceId)window.openWorkspaceFile?.(file.path,{owner,workspaceId});};result.append(link);
        }else result.append(textElement('div',text));
      }step.append(result);item.append(step);list.append(item);
    }details.append(list);host.append(details);
  };
  window.renderActivitySummary=rows=>{
    if(typeof activeSession!=='undefined'&&['completed','failed','cancelled'].includes(activeSession?.execution_status))window.renderWorkspaceEventLine(activeSession.execution_status);
    const files=new Set(),inspected=new Set(),failures=new Set();
    const currentRows=rows.slice(rows.findLastIndex(row=>row.role==='user')+1);
    for(const row of currentRows)for(const entry of row.activity||[]){if(entry.status==='error')failures.add(toolName(entry.tool));if(entry.status==='completed')for(const file of entry.files||[])(file.operation==='inspected'?inspected:files).add(file.path);}
    const changed=files.size?tr('Reported file changes: ','تغييرات الملفات المُعلنة: ')+[...files].slice(0,20).join(', '):'';
    const read=inspected.size?tr('Files inspected: ','الملفات التي فُحصت: ')+[...inspected].slice(0,20).join(', '):'';
    keepChatActivity();const failed=failures.size?tr('Reported tool failures: ','أخطاء الأدوات المُعلنة: ')+[...failures].join(', ')+tr(' — see the error details above.',' — راجع تفاصيل الخطأ أعلاه.'):'';const summary=[changed,read,failed].filter(Boolean).join(' · ');if(activitySummary.textContent!==summary)activitySummary.textContent=summary;window.refreshWorkspaceTodos?.();
  };
  const agent=q('agentSelect');agent.title=tr('Agent','الوكيل');controls.insertBefore(agent,q('providerSelect'));
  const nativeVariant=document.createElement('select');nativeVariant.id='nativeVariantSelect';nativeVariant.hidden=true;nativeVariant.setAttribute('aria-label',tr('Model variant','خيار النموذج'));controls.insertBefore(nativeVariant,q('modelSelect').nextSibling);
  const manualModel=btn('manualNativeModel','Manual model','اختيار نموذج يدوي',async()=>{
    if(!window.nativeSession?.active()||!activeWorkspace)return;
    const owner=currentUser?.id,id=activeWorkspace.id;
    const values=await window.requestForm(tr('Choose from the complete Native catalog','اختيار من كتالوج Native الكامل'),[{name:'provider',label:tr('Native provider ID','معرّف المزوّد في Native'),value:chosenProvider||'',required:true},{name:'model',label:tr('Native model ID','معرّف النموذج في Native'),value:chosenModel||'',required:true}],tr('Select','اختيار'));
    if(!values||currentUser?.id!==owner||activeWorkspace?.id!==id)return;
    const data=await api('/api/workspaces/'+id+'/providers/'+encodeURIComponent(values.provider)+'/models');
    if(currentUser?.id!==owner||activeWorkspace?.id!==id)return;
    if(!data.connected||data.allowed===false||!data.models.some(m=>m.id===values.model&&m.allowed!==false))throw Error(tr('Connect this provider to your account and choose an allowed Native model.','اربط هذا المزوّد بحسابك واختر نموذج Native مسموحًا.'));
    chosenProvider=values.provider;chosenModel=values.model;await refreshChoices(chosenProvider,true);saveNativeSelection();
  });controls.append(manualModel);
  function saveNativeSelection(){if(window.nativeSession?.active()&&activeSession)window.nativeSession.select(activeSession.id,{providerID:q('providerSelect').value,modelID:q('modelSelect').value,agent:agent.value,variant:nativeVariant.value||undefined});}
  function renderNativeVariants(){
    if(!window.nativeSession?.active()){nativeVariant.hidden=true;return;}
    const snapshot=window.workspaceRuntime.peek(activeWorkspace?.id),provider=snapshot?.providers.find(p=>p.id===q('providerSelect').value),model=provider?.models.find(m=>m.id===q('modelSelect').value);
    const previous=window.nativeSession.selection(activeSession?.id),selected=previous?.providerID===provider?.id&&previous?.modelID===model?.id?previous.variant:'';
    nativeVariant.replaceChildren(new Option(tr('Default variant','الخيار الافتراضي'),''));for(const variant of Object.keys(model?.variants||{}))nativeVariant.add(new Option(variant,variant));nativeVariant.value=selected||'';nativeVariant.hidden=nativeVariant.options.length<2;
  }
  nativeVariant.onchange=saveNativeSelection;
  const newTask=textElement('button','','icon-btn');newTask.id='composerNewTask';newTask.type='button';newTask.title=tr('New task','مهمة جديدة');newTask.setAttribute('aria-label',tr('New task','مهمة جديدة'));newTask.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>';newTask.onclick=async()=>{if(!activeWorkspace){toast(tr('Open a workspace first.','افتح مساحة عمل أولاً.'));return;}try{await createSession();toast(tr('New task started in this workspace.','بدأت مهمة جديدة في مساحة العمل.'));}catch(error){toast(error.message)}};
  q('providerSelect').setAttribute('aria-label','Provider');q('modelSelect').setAttribute('aria-label','Model');
  const attach=btn('attachFiles','','',()=>openAttachPicker(),'icon-btn');attach.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21.4 11.05 12.3 20.2a5.5 5.5 0 0 1-7.8-7.8l8.5-8.5a3.6 3.6 0 0 1 5.1 5.1l-8.5 8.5a1.8 1.8 0 0 1-2.6-2.6l7.8-7.8"/></svg>';attach.title=tr('Attach a file to this workspace','أرفق ملفًا في مساحة العمل');attach.setAttribute('aria-label',attach.title);controls.prepend(attach);controls.insertBefore(newTask,agent);
  const attachmentList=textElement('div','','composer-attachments');attachmentList.id='composerAttachments';attachmentList.setAttribute('aria-live','polite');q('promptInput').before(attachmentList);
  let attachments=[];let attachmentRevision=0;
  const clearAttachments=()=>{attachmentRevision++;for(const item of attachments)if(item.preview)URL.revokeObjectURL(item.preview);attachments=[];attachmentList.replaceChildren();};
  const renderAttachments=()=>{
    attachmentList.replaceChildren();for(const item of attachments){const card=textElement('div','','composer-attachment');
      if(item.preview){const image=document.createElement('img');image.src=item.preview;image.alt='';card.append(image);}
      const label=textElement('span',item.name);label.dir='auto';label.append(textElement('small',item.error|| (item.path?item.type+' · '+Math.ceil(item.size/1024)+' KB':tr('Uploading…','جارٍ الرفع…'))));
      const remove=textElement('button','×');remove.type='button';remove.disabled=sending||Boolean(pendingSubmission);remove.setAttribute('aria-label',tr('Remove attachment; keep workspace file','إزالة المرفق مع إبقاء ملف مساحة العمل'));remove.onclick=()=>{if(sending||pendingSubmission)return;attachments=attachments.filter(a=>a!==item);if(item.preview)URL.revokeObjectURL(item.preview);renderAttachments();};card.append(label,remove);attachmentList.append(card);
    }
  };
  window.restoreComposerAttachments=files=>{if(sending||pendingSubmission)return;clearAttachments();attachments=(files||[]).slice(0,10).map(file=>({name:file.name,path:file.path,size:file.size,type:file.mime||tr('File','ملف')}));renderAttachments();};
  const sentAttachments=payload=>{const paths=new Set((payload?.attachments||[]).map(a=>a.path));for(const item of attachments.filter(a=>paths.has(a.path)))if(item.preview)URL.revokeObjectURL(item.preview);attachments=attachments.filter(a=>!paths.has(a.path));renderAttachments();};
  async function openAttachPicker(){
    if(!activeWorkspace||window.workspaceSubmissionBlocked?.())return;
    const picker=document.createElement('input');picker.type='file';picker.multiple=true;picker.hidden=true;
    picker.oncancel=()=>picker.remove();picker.onchange=async()=>{
      const files=[...(picker.files||[])],workspaceId=activeWorkspace.id,owner=currentUser?.id,revision=attachmentRevision;picker.remove();
      if(files.length+attachments.length>10){toast(tr('Attach up to 10 files per message.','أرفق حتى 10 ملفات لكل رسالة.'));return;}
      for(const file of files){
        if(revision!==attachmentRevision||workspaceId!==activeWorkspace?.id||owner!==currentUser?.id)break;
        // The existing upload endpoint writes by name; reject duplicate draft names.
        if(attachments.some(a=>a.name===file.name)){toast(tr('This filename is already attached.','اسم الملف مرفق بالفعل.'));continue;}
        const item={name:file.name,size:file.size,type:file.type||tr('File','ملف'),preview:['image/png','image/jpeg','image/webp','image/gif'].includes(file.type)?URL.createObjectURL(file):null};attachments.push(item);renderAttachments();
        try{const fd=new FormData();fd.append('file',file);const data=await api('/api/workspaces/'+workspaceId+'/files/upload',{method:'POST',body:fd});
          if(revision!==attachmentRevision||workspaceId!==activeWorkspace?.id||owner!==currentUser?.id)continue;item.path=data.path;item.size=data.size;
        }catch(error){if(revision===attachmentRevision)item.error=error.message;}
        if(revision===attachmentRevision)renderAttachments();
      }
      if(revision===attachmentRevision){loadStorage().catch(()=>{});loadFiles().catch(()=>{});refreshGit().catch(()=>{});}
    };document.body.append(picker);picker.click();
  }
  q('openTools').onclick=()=>window.openConnections('providers');q('openTools').title=tr('Open OpenCode provider and workspace setup','\u0641\u062a\u062d \u0625\u0639\u062f\u0627\u062f \u0645\u0632\u0648\u062f OpenCode \u0648\u0645\u0633\u0627\u062d\u0629 \u0627\u0644\u0639\u0645\u0644');q('chatGithub').onclick=()=>openConnections('github');
  // Project, conversations and preview have independent panel tabs.
  const sessionsSection=document.createElement('section');sessionsSection.className='workspace-conversations';sessionsSection.hidden=true;
  const sessionsSummary=text('h3','Conversations','المحادثات'),sessionsCount=textElement('small','','sidebar-count');sessionsSummary.append(sessionsCount);sessionsSection.append(sessionsSummary);
  const sessionsBody=textElement('div','','section-body');
  const newSessionButton=pane.querySelector('.new-session');
  const search=document.createElement('input');search.type='search';search.id='workspaceSessionSearch';search.placeholder=tr('Search sessions','ابحث في الجلسات');search.setAttribute('aria-label','Search sessions');
  search.oninput=()=>renderRuntimeSessions(sessionRows);
  const sessionTabs=textElement('div','','session-filters');let sessionFilter='all',sessionRows=[],sessionListPending=null,sessionCreating=null,sending=false,queuing=false,queueCount=0,queueSignature='',queueRevision=0,historyRevision=0,pendingSubmission=null,cancelRequested=false,statusPending=null;
  for(const [value,en,ar] of [['all','All','الكل'],['active','Active','نشطة'],['closed','Previous / Closed','سابقة / مغلقة'],['archived','Archived','مؤرشفة']]){const tab=btn('sessions-'+value,en,ar,()=>{sessionFilter=value;for(const b of sessionTabs.children)b.setAttribute('aria-pressed',String(b===tab));renderRuntimeSessions(sessionRows);});tab.setAttribute('aria-pressed',String(value===sessionFilter));sessionTabs.append(tab);}
  const closeSessionButton=btn('closeActiveSession','Close / Disconnect','إغلاق / فصل',()=>sessionAction(activeSession,'close'));
  const submissionStatus=textElement('p','','muted-small');submissionStatus.setAttribute('role','status');q('promptForm').before(submissionStatus);
  const recoverConversation=btn('recoverNativeConversation','Recover Conversation','استعادة المحادثة',async()=>{
    const id=activeSession?.id,owner=currentUser?.id;if(!id||!window.nativeSession?.active())return;
    recoverConversation.disabled=true;
    try{
      let result=await window.nativeSession.recover(id);
      if(activeSession?.id!==id||currentUser?.id!==owner)return;
      if(result.blocked&&result.status==='idle'&&await window.confirmAction(tr('Native has no receipt for the previous prompt and is idle. Clear only the local block? Nothing will be sent. Your draft stays saved.','لا يوجد تأكيد للطلب السابق وNative متوقف الآن. إزالة الحظر المحلي فقط؟ لن يُرسل شيء وستبقى المسودة محفوظة.'))){result=await window.nativeSession.recover(id,{release:true});}
      if(activeSession?.id!==id||currentUser?.id!==owner)return;
      await refreshMessages();await window.refreshWorkspaceQuestions?.();await refreshPermissions();
      submissionStatus.textContent=result.blocked?tr('Receipt still uncertain. Draft preserved; no prompt resent.','الاستلام ما زال غير مؤكد. المسودة محفوظة ولم يُعد إرسال الطلب.'):tr('Conversation recovered. Review history; no prompt was resent.','استُعيدت المحادثة. راجع السجل؛ لم يُعد إرسال أي طلب.');
    }finally{recoverConversation.disabled=false;updateSend();}
  });
  // Exceptional receipt-reconciliation action, not a full-width conversation control.
  const recoveryAction=document.createElement('div');
  recoveryAction.hidden=true;
  recoveryAction.style.cssText='width:fit-content;max-width:100%;margin:4px 0 8px auto;';
  recoverConversation.classList.add('small');
  recoverConversation.style.cssText='width:auto;max-width:100%;min-height:32px;padding:5px 12px;white-space:normal;text-align:center;';
  recoveryAction.append(recoverConversation);
  q('promptForm').before(recoveryAction);
  const cancelAttachment=btn('cancelPendingAttachment','Cancel pending attachment','إلغاء طلب المرفق',async()=>{
    const id=activeSession?.id,owner=currentUser?.id;
    if(!id||!window.nativeSession?.pendingAttachment(id))return;
    const confirmed=await window.confirmAction(tr('Cancel the current attachment task in this conversation? OpenCode will stop this session only. The uploaded file and chat history remain saved.','هل تريد إلغاء مهمة قراءة المرفق في هذه المحادثة؟ سيتوقف تنفيذ هذه الجلسة فقط، وسيبقى الملف وسجل المحادثة محفوظين.'));
    if(!confirmed)return;
    cancelAttachment.disabled=true;
    try{
      await window.nativeSession.cancelPendingAttachment(id);
      if(activeSession?.id!==id||currentUser?.id!==owner)return;
      submissionStatus.textContent=tr('Attachment task cancelled. File retained.','أُلغيت مهمة المرفق وبقي الملف محفوظًا.');
      await refreshMessages();await refreshSessionStatus();
    }finally{cancelAttachment.disabled=false;updateSend();}
  });
  cancelAttachment.style.cssText='width:auto;min-height:32px;padding:5px 12px;font-size:12px;';
  recoveryAction.append(cancelAttachment);

  const retrySubmission=btn('retrySubmission','Check / retry same submission','تحقق / أعد نفس الطلب',()=>submitPending());retrySubmission.hidden=true;q('promptForm').before(retrySubmission);
  sessionsBody.append(newSessionButton,sessionTabs,search,q('sessionList'));sessionsSection.append(sessionsBody);
  const filesSection=document.createElement('details');filesSection.className='workspace-side-section workspace-files';filesSection.open=true;
  const filesSummary=text('summary','Project files','ملفات المشروع');
  const filesRefresh=btn('refreshWorkspaceFiles','Refresh files','حدّث الملفات',()=>loadFiles());filesRefresh.classList.add('icon-btn','files-refresh');filesRefresh.title=tr('Refresh files','حدّث الملفات');filesRefresh.setAttribute('aria-label',filesRefresh.title);
  filesRefresh.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();});
  filesSummary.append(filesRefresh);
  // The project folder itself expands the tree; keep the existing refresh control.
  filesSummary.hidden=true;
  const filesTree=textElement('div','','files-tree');filesTree.id='workspaceFilesTree';
  const filesStatus=textElement('p',tr('Open a workspace to see its files.','افتح مساحة عمل لعرض ملفاتها.'),'muted-small');
  const filesBody=textElement('div','','section-body');filesBody.append(filesTree,filesStatus);
  filesSection.append(filesSummary,filesBody);
  const FILE_ICONS={directory:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/></svg>',file:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 2h8l4 4v16H6z"/><path d="M14 2v4h4"/></svg>'};
  function renderFileRows(host,rows,context={workspaceId:activeWorkspace?.id,owner:currentUser?.id,root:filesTree,status:filesStatus}){
    const valid=()=>currentUser?.id===context.owner&&context.root.isConnected&&(context.detachedProject||activeWorkspace?.id===context.workspaceId);
    host.replaceChildren();
    if(!rows.length){host.append(textElement('p',tr('Empty folder','مجلد فارغ'),'muted-small'));return;}
    const sorted=[...rows].sort((a,b)=>(a.type==='directory'?0:1)-(b.type==='directory'?0:1)||a.name.localeCompare(b.name,lang,{numeric:true,sensitivity:'base'}));
    for(const row of sorted){
      const item=textElement('div','','file-item');
      const rowButton=textElement('button','','file-row'+(row.type==='directory'?' is-directory':''));
      rowButton.type='button';rowButton.title=row.path;rowButton.dataset.path=row.path;
      rowButton.innerHTML=FILE_ICONS[row.type==='directory'?'directory':'file']+'<span></span>';rowButton.querySelector('span').textContent=row.name;
      if(row.type==='directory'){
        const children=textElement('div','','file-children');children.hidden=true;rowButton.setAttribute('aria-expanded','false');
        rowButton.onclick=async()=>{if(!valid())return;const opening=children.hidden;children.hidden=!opening;rowButton.setAttribute('aria-expanded',String(opening));if(!opening||children.dataset.loaded)return;children.dataset.loaded='1';try{const childRows=await api('/api/workspaces/'+context.workspaceId+'/files?path='+encodeURIComponent(row.path));if(!valid()||!children.isConnected)return;renderFileRows(children,childRows,context);}catch(error){if(valid()){delete children.dataset.loaded;children.replaceChildren();children.append(textElement('p',error.message,'muted-small'));}}};
        item.append(rowButton,children);
      }else{
        rowButton.onclick=()=>{if(!valid())return;context.root.querySelectorAll('.file-row.selected').forEach(node=>node.classList.remove('selected'));rowButton.classList.add('selected');context.status.textContent=row.path;if(window.nativeSession?.active())window.openWorkspaceFile?.(row.path,{owner:context.owner,workspaceId:context.workspaceId});};
        item.append(rowButton);
      }
      host.append(item);
    }
  }
  let fileLoad=null,fileViewRevision=0,fileView=null;
  window.closeNativeFile=()=>{fileViewRevision++;if(fileView){fileView.close();fileView.remove();fileView=null;}};
  window.addEventListener('authentication-cleared',window.closeNativeFile);
  window.openWorkspaceFile=async(path,expected={owner:currentUser?.id,workspaceId:activeWorkspace?.id})=>{
    if(!window.nativeSession?.active()||currentUser?.id!==expected.owner||activeWorkspace?.id!==expected.workspaceId)return;
    if(typeof path!=='string'||path.startsWith('/')||path.includes('\\')||path.split('/').some(p=>!p||p==='..'||p.startsWith('.env')||['.git','.ssh','.opencode','opencode.json','opencode.jsonc'].includes(p)))return;
    window.closeNativeFile();const revision=fileViewRevision;
    try{
      const value=await api('/api/workspaces/'+encodeURIComponent(expected.workspaceId)+'/files/content?path='+encodeURIComponent(path));
      if(revision!==fileViewRevision||currentUser?.id!==expected.owner||activeWorkspace?.id!==expected.workspaceId)return;
      const dialog=document.createElement('dialog');dialog.className='action-form-dialog native-file-dialog';fileView=dialog;
      const heading=textElement('h2',path);heading.id='nativeFileHeading';dialog.setAttribute('aria-labelledby',heading.id);
      const close=textElement('button',tr('Close','إغلاق'),'button ghost small');close.type='button';close.onclick=()=>window.closeNativeFile();
      const content=textElement('pre',value.content);content.dir='auto';content.tabIndex=0;dialog.append(heading,close,content);q('workspacePage').append(dialog);
      dialog.addEventListener('close',()=>{dialog.remove();if(fileView===dialog)fileView=null;});dialog.showModal();
    }catch(error){if(revision===fileViewRevision&&currentUser?.id===expected.owner&&activeWorkspace?.id===expected.workspaceId)toast(error.message);}
  };
  async function loadFiles(){
    if(!activeWorkspace){filesTree.replaceChildren();filesStatus.textContent=tr('Open a workspace to see its files.','افتح مساحة عمل لعرض ملفاتها.');return;}
    const workspaceId=activeWorkspace.id,owner=currentUser?.id,key=owner+':'+workspaceId;
    if(fileLoad?.key===key)return fileLoad.promise;
    const expanded=[...filesTree.querySelectorAll('.file-row.is-directory[aria-expanded="true"]')].map(n=>n.dataset.path).sort((a,b)=>a.split('/').length-b.split('/').length);
    const selected=filesTree.querySelector('.file-row.selected')?.dataset.path;
    filesStatus.textContent=tr('Loading files…','جارٍ تحميل الملفات…');
    const valid=()=>activeWorkspace?.id===workspaceId&&currentUser?.id===owner;
    const promise=(async()=>{
      try{
        const rows=await api('/api/workspaces/'+workspaceId+'/files');if(!valid())return;
        renderFileRows(filesTree,rows);
        for(const path of expanded){if(!valid())return;const button=[...filesTree.querySelectorAll('.file-row.is-directory')].find(n=>n.dataset.path===path);if(button)await button.onclick();}
        if(!valid())return;const button=[...filesTree.querySelectorAll('.file-row')].find(n=>n.dataset.path===selected);button?.classList.add('selected');
        filesStatus.textContent=rows.length?'':tr('This workspace is empty.','مساحة العمل فارغة.');
      }catch(error){if(valid())filesStatus.textContent=error.message;}
    })();fileLoad={key,promise};try{return await promise;}finally{if(fileLoad?.promise===promise)fileLoad=null;}
  }
  window.refreshNativeFiles=({workspaceId,owner})=>{if(activeWorkspace?.id===workspaceId&&String(currentUser?.id)===String(owner))return loadFiles();};
  const modes=textElement('nav','','workspace-panel-modes');modes.setAttribute('aria-label',tr('Workspace panel','لوحة مساحة العمل'));
  const changesMode=btn('workspaceChanges','Project files','ملفات المشروع',()=>setPanel('changes'));
  const conversationsMode=btn('workspaceConversations','Conversations','المحادثات',()=>setPanel('conversations'));
  const previewMode=btn('workspacePreview','Preview','المعاينة',()=>setPanel('preview'));
  modes.append(conversationsMode,changesMode,previewMode);
  const close=q('closeSessions');modes.append(close);
  const changesPanel=textElement('section','','workspace-changes'),previewPanel=textElement('section','','workspace-preview');
  changesPanel.id='workspaceChangesPanel';previewPanel.id='workspacePreviewPanel';previewPanel.hidden=true;
  const approvalsList=document.createElement('details');approvalsList.className='chat-approval-settings';workspaceDetails.append(approvalsList);
  const questionView=textElement('section','','chat-questions');questionView.hidden=true;let questionSession=null,questionOwner=null,questionSignature='',questionSending=false,questionRevision=0,questionError='';
  window.resetWorkspaceQuestions=()=>{questionRevision++;questionSession=null;questionOwner=null;questionSignature='';questionView.hidden=true;questionView.replaceChildren();};
  function keepQuestions(){if(!questionView.hidden&&activeSession?.id===questionSession&&currentUser?.id===questionOwner&&!questionView.isConnected)q('agentFeed').append(questionView);}
  new MutationObserver(keepQuestions).observe(q('agentFeed'),{childList:true});
  window.refreshWorkspaceQuestions=async()=>{if(!activeSession||questionSending)return;const sessionId=activeSession.id,owner=currentUser?.id,revision=++questionRevision;
    try{const data=await api('/api/sessions/'+sessionId+'/questions');if(revision!==questionRevision||activeSession?.id!==sessionId||currentUser?.id!==owner)return;questionError='';const signature=lang+JSON.stringify(data.requests||[]);
      if(questionSession===sessionId&&questionOwner===owner&&signature===questionSignature){keepQuestions();return;}
      const retained=questionSession===sessionId&&questionOwner===owner?new Map([...questionView.children].map(form=>[form.dataset.requestId,form])):new Map();
      questionSession=sessionId;questionOwner=owner;questionSignature=signature;questionView.hidden=!data.requests?.length;const nextForms=[];
      for(const request of [...new Map((data.requests||[]).map(row=>[row.id,row])).values()]){
        const shape=lang+JSON.stringify(request.questions),old=retained.get(request.id);if(old?.dataset.questionShape===shape){nextForms.push(old);continue;}
        const form=document.createElement('form');form.className='chat-approval';form.dataset.requestId=request.id;form.dataset.questionShape=shape;form.append(textElement('strong',tr('The agent needs your answer','الوكيل ينتظر إجابتك')));const groups=[];
        for(const [index,question] of request.questions.entries()){const fieldset=document.createElement('fieldset');fieldset.append(textElement('legend',question.question||question.header||tr('Choose an answer','اختر إجابة')));if(question.header&&question.question){fieldset.append(textElement('p',question.header,'question-heading'));}const inputs=[];
          for(const option of question.options){const label=document.createElement('label'),input=document.createElement('input');input.type=question.multiple?'checkbox':'radio';input.name='q'+index;input.value=option.label;label.append(input,textElement('span',option.label));if(option.description)label.append(textElement('small',option.description));if(option.recommended===true){const hint=textElement('span',tr('Recommended by agent','موصى به من الوكيل'),'question-recommended');label.append(hint);if(option.description)hint.title=option.description;}fieldset.append(label);inputs.push(input);}
          let custom=null;if(question.custom){custom=document.createElement('input');custom.type='text';custom.maxLength=2000;custom.placeholder=tr('Other — write your choice…','خيار آخر — اكتب إجابتك…');custom.setAttribute('aria-label',custom.placeholder);fieldset.append(custom);if(!question.multiple){custom.oninput=()=>{if(custom.value.trim())inputs.forEach(input=>input.checked=false);};for(const input of inputs)input.onchange=()=>{if(input.checked)custom.value='';};}}groups.push({inputs,custom,multiple:question.multiple});form.append(fieldset);
        }
        const actions=textElement('div','','chat-approval-actions'),submit=textElement('button',tr('Choose and Continue','اختر وتابع'),'button ghost small'),reject=textElement('button',tr('Cancel question','إلغاء السؤال'),'button ghost small');submit.type='submit';reject.type='button';actions.append(submit,reject);form.append(actions);
        const draftKey='og-native-question:'+owner+':'+sessionId+':'+request.id;
        const saveAnswers=()=>{try{sessionStorage.setItem(draftKey,JSON.stringify({shape,groups:groups.map(g=>({values:g.inputs.filter(i=>i.checked).map(i=>i.value),custom:g.custom?.value||''}))}));}catch{}};
        try{const saved=JSON.parse(sessionStorage.getItem(draftKey)||'null');if(saved?.shape===shape)groups.forEach((g,index)=>{const answer=saved.groups?.[index];if(answer){g.inputs.forEach(i=>i.checked=answer.values?.includes(i.value));if(g.custom)g.custom.value=String(answer.custom||'').slice(0,2000);}});}catch{}
        form.addEventListener('input',saveAnswers);form.addEventListener('change',saveAnswers);
        async function send(rejected){if(questionSending||activeSession?.id!==sessionId||currentUser?.id!==owner)return;const answers=groups.map(g=>{const selected=g.inputs.filter(i=>i.checked).map(i=>i.value),custom=g.custom?.value.trim();return [...new Set(custom?(g.multiple?[...selected,custom]:[custom]):selected)];});if(!rejected&&answers.some(a=>!a.length)){toast(tr('Answer every question.','أجب عن كل سؤال.'));return;}
          questionSending=true;form.setAttribute('aria-busy','true');form.querySelectorAll('input,button').forEach(n=>n.disabled=true);
          try{await api('/api/sessions/'+sessionId+'/questions/'+encodeURIComponent(request.id),{method:'POST',body:JSON.stringify({reject:rejected,answers:rejected?[]:answers})});try{sessionStorage.removeItem(draftKey);}catch{}questionSignature='';if(activeSession?.id===sessionId&&currentUser?.id===owner){await refreshSessionStatus();await refreshMessages();}}
          catch(error){if(activeSession?.id===sessionId&&currentUser?.id===owner){toast(error.status===404?tr('This question expired. Refreshing the conversation…','انتهت صلاحية السؤال. جارٍ تحديث المحادثة…'):error.message);if(error.status===404)questionSignature='';form.removeAttribute('aria-busy');form.querySelectorAll('input,button').forEach(n=>n.disabled=false);}}finally{questionSending=false;await window.refreshWorkspaceQuestions();}
        }
        form.onsubmit=event=>{event.preventDefault();send(false);};reject.onclick=()=>send(true);nextForms.push(form);
      }
      for(const form of [...questionView.children])if(!nextForms.includes(form))form.remove();
      let cursor=questionView.firstChild;for(const form of nextForms){if(form===cursor)cursor=cursor.nextSibling;else questionView.insertBefore(form,cursor);}
      if(!questionView.hidden)q('agentFeed').append(questionView);
    }catch(error){if(revision===questionRevision&&activeSession?.id===sessionId&&currentUser?.id===owner&&questionError!==error.message){questionError=error.message;toast(error.message);}}
  };
  const approvalBusy=new Set();let approvalOwner=null,approvalSession=null;
  const inlineApprovals=q('approvalBox');inlineApprovals.classList.add('chat-approvals');inlineApprovals.hidden=true;
  function keepInlineApprovals(){if(!inlineApprovals.hidden&&approvalOwner===currentUser?.id&&approvalSession===activeSession?.id&&!inlineApprovals.isConnected)q('agentFeed').append(inlineApprovals);}
  new MutationObserver(keepInlineApprovals).observe(q('agentFeed'),{childList:true});
  let approvalRenderRevision=0,approvalSignature='';
  async function renderApprovals(rows,sessionId){
    if(window.nativeSession?.active()){approvalOwner=currentUser?.id;approvalSession=sessionId;approvalsList.hidden=true;await window.nativeSession.permissions(inlineApprovals,rows);if(!inlineApprovals.hidden)q('agentFeed').append(inlineApprovals);return;}
    const revision=++approvalRenderRevision;
    // A runtime request has one identity; never duplicate its controls.
    rows=[...new Map(rows.map(request=>[request.id,request])).values()];
    const owner=currentUser?.id;approvalOwner=owner;approvalSession=sessionId;
    if(!activeSession||activeSession.id!==sessionId){approvalSignature='';inlineApprovals.hidden=true;inlineApprovals.replaceChildren();approvalsList.hidden=true;approvalsList.replaceChildren();return;}
    const metadata=await Promise.allSettled([api('/api/sessions/'+sessionId+'/permissions/routine'),api('/api/sessions/'+sessionId+'/permissions/remembered')]);
    if(revision!==approvalRenderRevision||activeSession?.id!==sessionId||currentUser?.id!==owner)return;
    const routineData=metadata[0].status==='fulfilled'?metadata[0].value:null,rememberedData=metadata[1].status==='fulfilled'?metadata[1].value:null;
    const signature=JSON.stringify([owner,sessionId,lang,rows,routineData,rememberedData]);
    if(approvalSignature===signature){if(!inlineApprovals.hidden&&!inlineApprovals.isConnected)q('agentFeed').append(inlineApprovals);return;}
    inlineApprovals.replaceChildren();approvalsList.replaceChildren(textElement('summary',tr('Approval settings for this conversation','إعدادات الموافقة لهذه المحادثة')));approvalsList.hidden=false;
    let routineToggle=null;
    try{if(!routineData)throw new Error('Permission settings unavailable');const routine=routineData;
      const label=document.createElement('label');label.className='routine-permissions';const toggle=document.createElement('input');toggle.type='checkbox';toggle.checked=routine.enabled===true;
      routineToggle=toggle;
      toggle.onchange=async()=>{if(activeSession?.id!==sessionId||currentUser?.id!==owner)return;toggle.disabled=true;try{await api('/api/sessions/'+sessionId+'/permissions/routine',{method:'PUT',body:JSON.stringify({enabled:toggle.checked})});await loadApprovals();}catch(error){toggle.checked=!toggle.checked;toast(error.message);}finally{toggle.disabled=false;}};
      label.append(toggle,textElement('span',tr('Allow routine project-file work; ask before running commands','السماح بأعمال ملفات المشروع المعتادة؛ الموافقة قبل تشغيل الأوامر')));approvalsList.append(label);
    }catch(error){}
    approvalsList.append(textElement('p',tr('Review permission requests directly in the conversation.','راجع طلبات الموافقة مباشرة داخل الدردشة.')));
    if(routineToggle&&!routineData.enabled&&rows.some(request=>request.reviewable&&['read','list','glob','grep','write','edit'].includes(request.permission))){
      const notice=textElement('section','','chat-approval routine-permission-notice');
      notice.append(textElement('strong',tr('Allow existing project-file edits for this conversation','السماح بتعديل ملفات المشروع الموجودة لهذه المحادثة')));
      notice.append(textElement('p',tr('Ordinary reads and new files proceed automatically. Optionally allow edits to existing project files too. Commands, scripts, deletion and protected paths still require review.','القراءة وإنشاء الملفات الجديدة تتم مباشرة. يمكنك السماح أيضًا بتعديل الملفات الموجودة. الأوامر والسكربتات والحذف والمسارات المحمية تبقى للمراجعة.')));
      const routineButton=textElement('button',tr('Allow routine files and continue','السماح بأعمال الملفات والمتابعة'),'button ghost small routine-permission-shortcut');routineButton.type='button';
      routineButton.onclick=async()=>{if(activeSession?.id!==sessionId||currentUser?.id!==owner||routineToggle.disabled)return;routineButton.disabled=true;routineToggle.checked=true;try{await routineToggle.onchange();}finally{routineButton.disabled=false;}};
      notice.append(routineButton,textElement('small',tr('This conversation only. Revoke in Connections → Workspace.','لهذه المحادثة فقط. الإلغاء من الاتصالات ← مساحة العمل.')));inlineApprovals.append(notice);
    }
    for(const request of rows){const key=owner+':'+sessionId+':'+request.id;
      const section=textElement('section','','chat-approval');section.append(textElement('strong',tr('Permission requested: ','طلب موافقة: ')+(toolNames[request.permission]?toolName(request.permission):(request.permission||tr('Operation','عملية')))),textElement('pre',(request.patterns||[]).join('\n')));
      if(!request.reviewable)section.append(textElement('p',tr('Full details are unavailable. Reject this request.','التفاصيل الكاملة غير متاحة. ارفض هذا الطلب.')));
      const buttons=textElement('div','','chat-approval-actions');
      for(const [reply,en,ar,icon] of [['reject','Reject','رفض','×'],['once','Allow once','موافقة مرة واحدة','✓'],['similar','Allow this exact request again','السماح بتكرار هذا الطلب فقط','✓✓']]){
        const button=textElement('button','','button ghost small');button.type='button';button.dataset.reply=reply;
        const mark=textElement('span','','approval-symbol');mark.innerHTML={"reject":"<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M18 6 6 18\"/><path d=\"m6 6 12 12\"/></svg>","once":"<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M20 6 9 17l-5-5\"/></svg>","similar":"<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M18 6 7 17l-5-5\"/><path d=\"m22 10-7.5 7.5L13 16\"/></svg>"}[reply];button.append(mark,textElement('span',tr(en,ar)));button.disabled=approvalBusy.has(key)||(reply!=='reject'&&!request.reviewable)||(reply==='similar'&&!request.rememberable);
        button.onclick=async()=>{if(approvalBusy.has(key)||activeSession?.id!==sessionId||currentUser?.id!==owner)return;approvalBusy.add(key);buttons.querySelectorAll('button').forEach(b=>b.disabled=true);
          try{await api('/api/sessions/'+sessionId+'/permissions/'+encodeURIComponent(request.id),{method:'POST',body:JSON.stringify({reply})});if(activeSession?.id!==sessionId||currentUser?.id!==owner)return;await refreshSessionStatus();await refreshMessages();}
          catch(error){if(currentUser?.id===owner)toast(error.message);}finally{approvalBusy.delete(key);if(activeSession?.id===sessionId&&currentUser?.id===owner)await loadApprovals().catch(()=>{});}
        };buttons.append(button);
      }
      section.append(buttons,textElement('small',tr('This repeat approval covers only the exact reviewed request in this conversation.','هذا السماح بالتكرار يخص الطلب المطابق الذي راجعته في هذه المحادثة فقط.')));
      inlineApprovals.append(section);
    }
    inlineApprovals.hidden=!rows.length;if(rows.length)q('agentFeed').append(inlineApprovals);
    try{const remembered=rememberedData;
      if(remembered?.count){const note=textElement('div','','remembered-approvals');note.append(textElement('span',tr('Matching repeats approved in this conversation.','تم السماح بالطلبات المماثلة في هذه المحادثة.')));
        const clear=btn('clearRememberedApprovals','Clear remembered approvals','إلغاء الموافقات المحفوظة',async()=>{if(activeSession?.id!==sessionId||currentUser?.id!==owner)return;await api('/api/sessions/'+sessionId+'/permissions/remembered',{method:'DELETE'});await loadApprovals();});note.append(clear);approvalsList.append(note);}
    }catch(error){}
    approvalSignature=signature;
  }
  window.renderWorkspaceApprovals=renderApprovals;
  async function loadApprovals(){if(!activeSession){await renderApprovals([],null);return;}return refreshPermissions();}
  const paneResizer=document.createElement('div');paneResizer.className='pane-resizer';paneResizer.title=tr('Drag to resize','اسحب لتغيير الحجم');paneResizer.setAttribute('role','separator');paneResizer.setAttribute('aria-label',paneResizer.title);paneResizer.setAttribute('aria-orientation','vertical');paneResizer.tabIndex=0;
  let paneDragging=false;const dashboardWidth=()=>Math.min(290,Math.max(210,innerWidth*.19));let panelWidth=Math.round(dashboardWidth());
  function panelBounds(){const width=shell.getBoundingClientRect().width||innerWidth,min=drawer()?Math.min(210,Math.max(180,width-120)):210,rail=dashboardWidth();return {min,max:Math.max(min,Math.min(width*.7,width-(drawer()?120:rail+380)))};}
  function setPanelWidth(value){const {min,max}=panelBounds();panelWidth=Math.round(Math.min(Math.max(min,value),Math.max(min,max)));shell.style.setProperty('--panel-w',panelWidth+'px');paneResizer.setAttribute('aria-valuenow',String(panelWidth));paneResizer.setAttribute('aria-valuemin',String(Math.round(min)));paneResizer.setAttribute('aria-valuemax',String(Math.round(Math.max(min,max))));shell.style.gridTemplateColumns='';}
  paneResizer.addEventListener('pointerdown',event=>{if(event.button!==0)return;paneDragging=true;paneResizer.setPointerCapture(event.pointerId);document.body.style.userSelect='none';event.preventDefault();});
  paneResizer.addEventListener('pointermove',event=>{if(!paneDragging)return;const rect=shell.getBoundingClientRect();setPanelWidth(getComputedStyle(shell).direction==='rtl'?event.clientX-rect.left:rect.right-event.clientX);});
  const paneDragEnd=()=>{paneDragging=false;document.body.style.userSelect='';};paneResizer.addEventListener('pointerup',paneDragEnd);paneResizer.addEventListener('pointercancel',paneDragEnd);paneResizer.addEventListener('lostpointercapture',paneDragEnd);
  paneResizer.addEventListener('dblclick',()=>setPanelWidth(dashboardWidth()));
  paneResizer.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight'].includes(event.key))return;event.preventDefault();setPanelWidth(panelWidth+(event.key==='ArrowRight'?-20:20)*(getComputedStyle(shell).direction==='rtl'?-1:1));});
  function clampPanelWidth(){setPanelWidth(panelWidth);if(drawer()&&!pane.classList.contains('open'))shell.style.gridTemplateColumns='';}
  window.addEventListener('resize',clampPanelWidth);setPanelWidth(panelWidth);

  const gitSummary=q('gitSummary'),gitActions=pane.querySelector('.git-actions'),changedFiles=textElement('div','','changed-file-list'),diffView=textElement('pre','','workspace-diff');
  diffView.id='workspaceFileDiff';changesPanel.append(gitSummary,btn('refreshWorkspaceChanges','Refresh changes','حدّث التغييرات',()=>loadChanges()),changedFiles,diffView,gitActions);
  const previewProjectSelect=document.createElement('select');
  previewProjectSelect.setAttribute('aria-label',tr('Select project to preview','اختر المشروع للمعاينة'));
  previewProjectSelect.style.cssText='display:block;box-sizing:border-box;width:100%;max-width:100%;min-width:0;min-height:40px;border-radius:8px;padding:6px 28px 6px 9px;overflow:hidden;text-overflow:ellipsis;background:var(--input-bg,#fff);color:inherit';
  const previewProjectTargets=new Map();
  previewProjectSelect.addEventListener('change',()=>{
    const target=previewProjectTargets.get(previewProjectSelect.value);
    if(target&&target.workspace.id!==activeWorkspace?.id)openWorkspace(target.project,target.workspace);
  });
  const previewIdentity=textElement('div','','preview-project-identity');
  previewIdentity.style.cssText='box-sizing:border-box;min-width:0;width:100%;max-width:100%;padding:10px 12px;margin:8px 0;border:1px solid var(--border-color,#d4d9e1);border-radius:10px;display:flex;flex-direction:column;gap:6px;overflow:hidden;overflow-wrap:anywhere';
  previewIdentity.setAttribute('aria-live','polite');
  function updatePreviewIdentity(){
    const name=activeProject?.name||activeProject?.repository;
    previewIdentity.replaceChildren();
    const heading=document.createElement('strong');
    heading.textContent=name||tr('No project selected','لم يتم تحديد مشروع');
    const details=document.createElement('small');
    details.textContent=activeProject?.branch?tr('Branch: ','الفرع: ')+activeProject.branch:'';
    details.hidden=!activeProject?.branch;
    heading.style.cssText='display:block;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap';
    details.style.cssText='display:block;max-width:100%;overflow-wrap:anywhere';
    previewIdentity.append(heading,details,previewProjectSelect);
    const allowed=Boolean(activeWorkspace?.id&&activeProject?.id);
    if(!allowed){
      previewStatus.textContent=tr('Select a project and workspace to preview.','اختر مشروعًا ومساحة عمل قبل تشغيل المعاينة.');
    }
  }
  const previewPath=document.createElement('input');previewPath.value='index.html';previewPath.setAttribute('aria-label',tr('Preview HTML entry','ملف HTML للمعاينة'));
  const previewStatus=text('p','Select Start to check this project’s preview availability.','اختر التشغيل للتحقق من توفر معاينة هذا المشروع.');
  previewStatus.className='preview-status';previewStatus.setAttribute('role','status');previewStatus.setAttribute('aria-live','polite');
  const frame=document.createElement('iframe');frame.title=tr('Project preview','معاينة المشروع');frame.setAttribute('sandbox','allow-scripts');frame.setAttribute('referrerpolicy','no-referrer');frame.hidden=true;
  let previewRevision=0;
  function setPreviewState(state){
    previewPanel.dataset.state=state;
    const buttons=previewActions.children;
    if(buttons.length!==5)return;
    buttons[0].disabled=state==='loading'||state==='blocked';
    buttons[1].disabled=state==='loading';
    buttons[2].disabled=state!=='ready'&&state!=='loading';
    for(let index=3;index<5;index++)buttons[index].disabled=state!=='ready';
    previewPanel.setAttribute('aria-busy',String(state==='loading'));
  }
  function clearPreview(){previewRevision++;frame.hidden=true;frame.removeAttribute('srcdoc');frame.removeAttribute('src');setPreviewState('idle');}
  async function previewBrowserURL(id){
    const access=await api('/api/workspaces/'+id+'/preview/access',{method:'POST'});
    const url=new URL(access.url),gateway=new URL(location.href);
    if(url.protocol!=='https:'||url.hostname===gateway.hostname||url.username||url.password||!url.pathname.startsWith('/preview/'))throw new Error(tr('A separate secure Preview origin is required.','يلزم عنوان HTTPS مستقل للمعاينة.'));
    return url.href;
  }
  async function startPreview({fresh=false}={}){
    updatePreviewIdentity();
    if(!activeWorkspace?.id||!activeProject?.id){setPreviewState('blocked');return;}
    clearPreview();setPreviewState('loading');const revision=previewRevision,id=activeWorkspace.id;
    previewStatus.textContent=tr('Detecting project…','جارٍ اكتشاف نوع المشروع…');
    try{
      const state=await api('/api/workspaces/'+id+'/preview/status');
      if(activeWorkspace?.id!==id||previewRevision!==revision)return;
      previewPath.hidden=state.mode!=='static';
      if(fresh&&state.state==='running'){
        previewStatus.textContent=tr('Preparing a fresh preview of the current files…','جارٍ تجهيز معاينة جديدة للملفات الحالية…');
        await api('/api/workspaces/'+id+'/preview/stop',{method:'POST'});
        if(activeWorkspace?.id!==id||previewRevision!==revision)return;
      }
      let dynamicError=null;
      if(state.mode!=='static'){
        try {
          const launched=await api('/api/workspaces/'+id+'/preview/start'+(fresh?'?fresh=true':''),{method:'POST'});
          if(activeWorkspace?.id!==id||previewRevision!==revision)return;
          if(launched.url){
            const browserURL=state.browser_access_required?await previewBrowserURL(id):launched.url;
            if(activeWorkspace?.id!==id||previewRevision!==revision)return;
            frame.src=browserURL;frame.hidden=false;setPreviewState('ready');
            previewStatus.textContent=state.browser_access_required?tr('Running application preview · Read link lasts up to 5 minutes; Refresh renews access.','معاينة التطبيق تعمل · رابط القراءة صالح حتى 5 دقائق؛ زر التحديث يجدّد الوصول.'):tr('Running application preview','معاينة التطبيق تعمل');
            return;
          }
          throw new Error(tr('Container started, but no preview URL was returned.','بدأت الحاوية دون رابط معاينة صالح.'));
        } catch(launchError) {
          if(activeWorkspace?.id!==id||previewRevision!==revision)return;
          dynamicError=launchError;
          previewStatus.textContent=tr('Server preview failed; checking HTML fallback…','تعذر تشغيل معاينة الخادم؛ جارٍ فحص بديل HTML…');
        }
      }
      previewStatus.textContent=tr('Loading HTML entry…','جارٍ تحميل صفحة HTML…');
      try {
        const result=await api('/api/workspaces/'+id+'/preview?path='+encodeURIComponent(previewPath.value));
        if(activeWorkspace?.id!==id||previewRevision!==revision)return;
        frame.srcdoc=result.html;frame.hidden=false;setPreviewState('ready');
        previewStatus.textContent=tr('HTML preview · ','معاينة HTML · ')+result.path+
          (state.mode==='static'?'':tr(' · Static fallback; app server is not running.',' · عرض ثابت؛ خادم التطبيق غير مشغّل.'));
      } catch(staticError) {
        if(activeWorkspace?.id!==id||previewRevision!==revision)return;
        if(state.mode!=='static') {
          setPreviewState('blocked');
          previewStatus.textContent=tr('Dynamic preview failed: ','فشل تشغيل المعاينة الديناميكية: ')+
            (dynamicError?.message||tr('Runner unavailable or application did not start.','الخدمة غير متاحة أو التطبيق لم يبدأ.'));
          return;
        }
        throw staticError;
      }
    }catch(error){if(activeWorkspace?.id===id&&previewRevision===revision){clearPreview();setPreviewState('error');previewStatus.textContent=error.message;}}
  }
  async function refreshPreview(){
    if(!frame.hidden && frame.getAttribute('src')){
      const current=new URL(frame.getAttribute('src'),location.href);
      if(current.hostname===new URL(location.href).hostname){
        current.searchParams.set('_preview_refresh',String(Date.now()));frame.src=current.href;
        previewStatus.textContent=tr('Refreshing running preview…','جارٍ تحديث المعاينة الحالية…');return;
      }
      const id=activeWorkspace?.id,revision=previewRevision;
      previewStatus.textContent=tr('Refreshing running preview…','جارٍ تحديث المعاينة الحالية…');
      try{
        const url=await previewBrowserURL(id);
        if(activeWorkspace?.id!==id||previewRevision!==revision)return;
        frame.src=url;
        previewStatus.textContent=tr('Running application preview · Read link lasts up to 5 minutes; Refresh renews access.','معاينة التطبيق تعمل · رابط القراءة صالح حتى 5 دقائق؛ زر التحديث يجدّد الوصول.');
      }catch(error){if(activeWorkspace?.id===id&&previewRevision===revision)previewStatus.textContent=error.message;}
      return;
    }
    await startPreview();
  }
  async function stopPreview(){
    clearPreview();const revision=previewRevision,id=activeWorkspace?.id;
    previewStatus.textContent=tr('Preview stopped.','تم إيقاف المعاينة.');
    if(!id)return;
    try{await api('/api/workspaces/'+id+'/preview/stop',{method:'POST'});}
    catch(error){if(activeWorkspace?.id===id&&previewRevision===revision)previewStatus.textContent=error.message;}
  }
  const previewActions=textElement('div','','preview-actions');
  const fullPreview=btn('expandWorkspacePreview','Full screen','تكبير للشاشة',async()=>{if(frame.hidden){toast(tr('Start the preview first.','ابدأ المعاينة أولًا.'));return;}await frame.requestFullscreen();});
  const newTabPreview=btn('openWorkspacePreviewTab','Open in new tab','فتح في تبويب جديد',()=>{
    if(frame.hidden){toast(tr('Start the preview first.','ابدأ المعاينة أولًا.'));return;}
    const escapeAttr=value=>String(value).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    const path=frame.getAttribute('src');
    // Always preserve the iframe sandbox in a new tab. Never navigate directly
    // to customer-generated HTML under the Gateway origin.
    const source=path?'src="'+escapeAttr(new URL(path,location.href).href)+'"':'srcdoc="'+escapeAttr(frame.srcdoc)+'"';
    const html='<!doctype html><html><head><meta charset="utf-8"><title>Project preview</title><meta name="referrer" content="no-referrer"></head><body style="margin:0;height:100vh"><iframe title="Project preview" sandbox="allow-scripts" referrerpolicy="no-referrer" style="width:100%;height:100%;border:0" '+source+'></iframe></body></html>';
    const url=URL.createObjectURL(new Blob([html],{type:'text/html'})),link=document.createElement('a');
    link.href=url;link.target='_blank';link.rel='noopener noreferrer';link.click();
    setTimeout(()=>URL.revokeObjectURL(url),60000);
  });
  previewActions.append(btn('startWorkspacePreview','Start preview','ابدأ المعاينة',startPreview),btn('refreshWorkspacePreview','Refresh preview','حدّث المعاينة',refreshPreview),btn('stopWorkspacePreview','Stop preview','إيقاف المعاينة',stopPreview),fullPreview,newTabPreview);
  let chatPreviewPending=false;
  window.renderWorkspaceMessageActions=(host,actions,context)=>{
    if(!Array.isArray(actions))return;
    const valid=action=>action?.kind==='preview'&&context.owner===currentUser?.id&&context.sessionId===activeSession?.id&&
      action.session_id===context.sessionId&&action.workspace_id===activeWorkspace?.id&&action.project_id===activeProject?.id&&action.message_id===context.messageId;
    const action=actions.find(valid);if(!action)return;
    const card=textElement('section','','message-preview-action'),status=textElement('small');status.setAttribute('aria-live','polite');
    const button=btn('', 'View changes', 'عرض التغييرات',async()=>{
      if(!valid(action)||chatPreviewPending||window.workspaceSubmissionBlocked?.())return;
      chatPreviewPending=true;button.disabled=true;
      try{
        await setPanel('preview');if(!valid(action))return;
        if(shell.classList.contains('sessions-collapsed')||(drawer()&&!pane.classList.contains('open')))togglePane();
        status.textContent=tr('Opening isolated project preview…','جارٍ فتح المعاينة المعزولة للمشروع…');
        await startPreview({fresh:true});if(valid(action))status.textContent=previewStatus.textContent;
      }catch(error){if(valid(action))status.textContent=error.message;}
      finally{chatPreviewPending=false;button.disabled=!valid(action)||Boolean(window.workspaceSubmissionBlocked?.());}
    },'button ghost small');
    button.disabled=Boolean(window.workspaceSubmissionBlocked?.());card.append(button,status);host.append(card);
  };
  const previewIcons=['<path d="m9 5 10 7-10 7Z"/>','<path d="M20 7v5h-5M20 12a8 8 0 1 0-2 6"/>','<rect x="6" y="6" width="12" height="12" rx="1"/>','<path d="M8 3H3v5M16 3h5v5M21 16v5h-5M8 21H3v-5"/>','<path d="M14 3h7v7M21 3 10 14M10 3H3v18h18v-7"/>'];
  [...previewActions.children].forEach((button,index)=>{const label=button.textContent;button.title=label;button.setAttribute('aria-label',label);button.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+previewIcons[index]+'</svg>';});
  const previewToolbar=textElement('div','','preview-toolbar');previewToolbar.style.cssText='min-width:0;max-width:100%;box-sizing:border-box;flex-wrap:wrap;overflow:hidden';previewToolbar.append(previewPath,previewActions);
  const previewCanvas=textElement('div','','preview-canvas');previewCanvas.append(previewStatus,frame);
  previewPanel.style.minWidth='0';previewPanel.style.overflowX='hidden';
  previewPanel.append(text('h3','Project Preview','معاينة المشروع'),previewIdentity,previewToolbar,previewCanvas);
  setPreviewState('idle');
  const projectRoot=document.createElement('details');projectRoot.className='sidebar-project-root';projectRoot.open=true;
  const projectSummary=document.createElement('summary'),projectName=textElement('strong'),projectKind=textElement('small'),projectBranch=textElement('span','','sidebar-project-branch');
  const projectIcon=textElement('span','','sidebar-project-icon');projectIcon.innerHTML=FILE_ICONS.directory;const projectIdentity=textElement('span','','sidebar-project-identity');projectIdentity.append(projectName,projectKind);projectSummary.append(projectIcon,projectIdentity);projectRoot.append(projectSummary,projectBranch);
  const changesSection=document.createElement('details');changesSection.className='workspace-side-section workspace-change-group';changesSection.open=false;changesSection.append(text('summary','Project changes','تغييرات المشروع'),changesPanel);
  projectRoot.append(filesSection,changesSection);
  let exportSource;
  const sourceDownloads=new Set();
  async function downloadProjectSource(workspace,project){
    const owner=currentUser?.id,id=workspace?.id;
    if(!owner||!id||sourceDownloads.has(id))return;
    sourceDownloads.add(id);
    try{
      toast(tr('Preparing project ZIP…','جارٍ تجهيز ملف المشروع ZIP…'));
      const response=await fetch('/api/workspaces/'+encodeURIComponent(id)+'/export',{credentials:'same-origin'});
      if(currentUser?.id!==owner)return;
      if(!response.ok){let detail='';try{detail=(await response.json()).detail;}catch(error){}throw new Error(typeof detail==='string'&&detail?detail:tr('Project download failed.','تعذر تنزيل المشروع.'));}
      if(!response.headers.get('Content-Type')?.includes('application/zip'))throw new Error(tr('The server did not return a project ZIP. Sign in and retry.','لم يُرجع الخادم ملف ZIP للمشروع. سجل الدخول وأعد المحاولة.'));
      const blob=await response.blob();if(currentUser?.id!==owner)return;
      const url=URL.createObjectURL(blob),link=document.createElement('a');
      link.href=url;link.download=String(project?.name||project?.repository||'project').replace(/[\\/\x00-\x1f\x7f]/g,'-').slice(0,100)+'.zip';
      document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
    }finally{sourceDownloads.delete(id);}
  }
  function projectKindControls(){const github=activeProject?.source_type==='github';changesSection.hidden=!github;if(exportSource){exportSource.hidden=!activeWorkspace;exportSource.disabled=!activeWorkspace;}gitActions.hidden=!github;gitActions.querySelector('#commitButton').hidden=!github;gitActions.querySelector('#pushButton').hidden=!github;}

  function updateProjectIdentity(){updatePreviewIdentity();projectKindControls();projectName.textContent=activeProject?.repository||activeProject?.name||tr('Project','المشروع');projectKind.textContent=activeProject?.source_type==='github'?tr('GitHub working copy','نسخة عمل GitHub'):tr('Local project','مشروع محلي');projectBranch.textContent=tr('Branch: ','الفرع: ')+(activeProject?.branch||'—');projectBranch.hidden=!activeProject?.branch;}
  const projectGroups=textElement('div','','workspace-project-groups'),projectBuckets=new Map();
  for(const [kind,en,ar] of [['local','Workspace','مساحة العمل'],['github','GitHub projects','مشاريع GitHub']]){
    const group=document.createElement('details');group.className='project-source-group';group.open=true;group.dataset.source=kind;
    const list=textElement('div','','project-source-list'),summary=document.createElement('summary'),heading=textElement('span','','project-source-heading'),meta=textElement('span','','project-source-meta');
    heading.append(text('span',en,ar),meta);summary.append(heading);group.append(summary,list);projectGroups.append(group);projectBuckets.set(kind,{group,list,meta,summary});
  }
  const linkGithub=btn('linkWorkspaceGithubProject','Open a GitHub project','فتح مشروع GitHub',()=>window.openGithubProject(),'icon-btn');
  linkGithub.innerHTML='<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>';linkGithub.title=tr('Open a GitHub project','فتح مشروع GitHub');linkGithub.setAttribute('aria-label',linkGithub.title);
  linkGithub.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();});projectBuckets.get('github').summary.append(linkGithub);
  function projectFileFolder(project,workspace){
    const folder=document.createElement('details');folder.className='sidebar-project-root';
    const summary=document.createElement('summary'),icon=textElement('span','','sidebar-project-icon');icon.innerHTML=FILE_ICONS.directory;
    const identity=textElement('span','','sidebar-project-identity');identity.append(textElement('strong',project.repository||project.name),textElement('small',project.source_type==='github'?tr('GitHub working copy','نسخة عمل GitHub'):tr('Local project','مشروع محلي')));summary.append(icon,identity);
    const body=textElement('div','','section-body'),tree=textElement('div','','files-tree'),status=textElement('p','','muted-small');
    const open=btn('project-folder-'+project.id,'Open workspace','فتح مساحة العمل',()=>openWorkspace(project,workspace));open.className='project-folder-link';
    const download=btn('download-project-'+project.id,'Download ZIP','تنزيل ZIP',()=>downloadProjectSource(workspace,project));
    body.append(open,download,tree,status);folder.append(summary,body);let loaded=false,pending=false;
    const owner=currentUser?.id,context={workspaceId:workspace.id,owner,root:tree,status,detachedProject:true};
    folder.addEventListener('toggle',async()=>{
      if(!folder.open||loaded||pending||currentUser?.id!==owner)return;
      pending=true;status.textContent=tr('Loading files…','جارٍ تحميل الملفات…');
      try{const rows=await api('/api/workspaces/'+workspace.id+'/files');if(currentUser?.id!==owner||!folder.isConnected)return;renderFileRows(tree,rows,context);loaded=true;status.textContent='';}
      catch(error){if(currentUser?.id===owner&&folder.isConnected)status.textContent=error.message;}
      finally{pending=false;}
    });
    return folder;
  }
  let projectListRevision=0;
  function placeCurrentProject(){
    const kind=activeProject?.source_type==='github'?'github':'local',bucket=projectBuckets.get(kind);bucket.list.prepend(projectRoot);bucket.meta.append(storageChip);bucket.summary.append(filesRefresh);
    if(storageChip.dataset.workspaceId!==activeWorkspace?.id){storageChip.dataset.workspaceId=activeWorkspace?.id||'';storageChip.hidden=true;storageChip.textContent='';}
    updateProjectIdentity();
  }
  async function loadProjectGroups(){
    const id=activeWorkspace?.id,owner=currentUser?.id,revision=++projectListRevision;if(!id)return;placeCurrentProject();
    try{const data=await api('/api/dashboard');if(activeWorkspace?.id!==id||currentUser?.id!==owner||revision!==projectListRevision)return;
      for(const {list} of projectBuckets.values())list.replaceChildren();placeCurrentProject();
      previewProjectTargets.clear();
      previewProjectSelect.replaceChildren();
      for(const project of data.projects||[]){
        const workspace=project.workspaces?.find(w=>w.status==='ready')||project.workspaces?.[0];
        if(!workspace)continue;
        previewProjectTargets.set(workspace.id,{project,workspace});
        const option=document.createElement('option');
        option.value=workspace.id;
        option.textContent=project.name||project.repository||tr('Project','مشروع');
        previewProjectSelect.append(option);
      }
      previewProjectSelect.value=activeWorkspace?.id||'';
      previewProjectSelect.disabled=!previewProjectTargets.size;
      for(const project of data.projects||[]){if(project.id===activeProject?.id)continue;const workspace=project.workspaces?.find(w=>w.status==='ready')||project.workspaces?.[0];if(!workspace)continue;projectBuckets.get(project.source_type==='github'?'github':'local').list.append(projectFileFolder(project,workspace));}
      for(const [kind,bucket] of projectBuckets){
        if(bucket.list.children.length)continue;
        if(kind==='github'){
          bucket.list.append(textElement('p',tr('No GitHub working copy imported yet. Select an authorized repository and branch.','لم تُستورد نسخة عمل من GitHub بعد. اختر مستودعًا وفرعًا مصرحًا بهما.'),'muted-small'));
          bucket.list.append(btn('selectAuthorizedGithubProject','Choose a GitHub repository','اختيار مستودع GitHub',()=>window.openGithubProject(),'button ghost small'));
        }else bucket.list.append(textElement('p',tr('No projects in this section.','لا توجد مشاريع في هذا القسم.'),'muted-small'));
      }
    }catch(error){if(activeWorkspace?.id===id&&revision===projectListRevision)placeCurrentProject();}
  }
  const projectPanelBrand=textElement('div','','workspace-project-brand');projectPanelBrand.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><use href="#icon-github"/></svg>';projectPanelBrand.append(text('span','Projects & Preview','المشاريع والمعاينة'));
  placeCurrentProject();pane.replaceChildren(projectPanelBrand,modes,sessionsSection,projectGroups,previewPanel);
  const conversationList=sessionsBody.querySelector('#sessionList'),conversationOptions=document.createElement('details');conversationOptions.className='conversation-options';conversationOptions.append(text('summary','Search / filter','بحث / تصفية'),search,sessionTabs);
  sessionsBody.replaceChildren(conversationOptions,conversationList);
  newSessionButton.textContent='+';newSessionButton.title=tr('New conversation','محادثة جديدة');newSessionButton.setAttribute('aria-label',newSessionButton.title);sessionsSummary.append(newSessionButton);sessionsSection.hidden=false;conversationsMode.hidden=false;projectGroups.hidden=true;
  pane.append(paneResizer);
  // Reuse the actual Dashboard navigation and its handlers, never duplicate it.
  const dashboardMenu=document.createElement('dialog');dashboardMenu.className='workspace-dashboard-menu';dashboardMenu.setAttribute('aria-label',tr('Dashboard menu','قائمة لوحة التحكم'));
  const dashboardNav=q('clientNav'),dashboardParent=dashboardNav.parentNode,dashboardNext=dashboardNav.nextSibling;
  const dashboardRail=textElement('aside','','workspace-dashboard-rail');dashboardRail.id='workspaceDashboardRail';const dashboardBrand=textElement('div','OpenCode Gateway','workspace-dashboard-brand');dashboardBrand.insertAdjacentHTML('afterbegin','<svg viewBox="0 0 16 20" aria-hidden="true"><use href="#icon-opencode"/></svg>');dashboardRail.append(dashboardBrand);shell.prepend(dashboardRail);
  function placeDashboardNav(){if(dashboardMenu.open)return;if(q('workspacePage').classList.contains('active')&&!drawer()&&currentUser)dashboardRail.append(dashboardNav);else if(dashboardNav.parentNode!==dashboardParent)dashboardParent.insertBefore(dashboardNav,dashboardNext);}
  window.addEventListener('resize',placeDashboardNav);
  const closeDashboard=btn('closeWorkspaceDashboard','Close dashboard','إغلاق لوحة التحكم',()=>dashboardMenu.close(),'icon');closeDashboard.textContent='×';dashboardMenu.append(closeDashboard);document.body.append(dashboardMenu);
  dashboardMenu.addEventListener('close',placeDashboardNav);
  dashboardNav.addEventListener('click',event=>{if(event.target.closest('button')&&dashboardMenu.open)dashboardMenu.close();});
  const dashboardToggle=btn('openWorkspaceDashboard','Dashboard','لوحة التحكم',()=>{if(!currentUser)return;dashboardMenu.append(dashboardNav);dashboardMenu.showModal();},'workspace-dashboard-toggle');dashboardToggle.innerHTML='<svg class="ui-icon" aria-hidden="true"><use href="#icon-menu"/></svg>';dashboardToggle.setAttribute('aria-label',tr('Open dashboard menu','فتح قائمة لوحة التحكم'));dashboardToggle.title=tr('Dashboard','لوحة التحكم');projectbar.prepend(dashboardToggle);dashboardNavReady=true;placeDashboardNav();

  let panelMode='conversations',changesStamp=0;
  async function loadChanges(){
    if(!activeWorkspace)return;updateProjectIdentity();const id=activeWorkspace.id,stamp=++changesStamp;diffView.textContent=tr('Loading changes…','جارٍ تحميل التغييرات…');
    try{const [state,sessionDiff]=await Promise.all([api('/api/workspaces/'+id+'/git/status'),activeSession?api('/api/sessions/'+activeSession.id+'/diff'):Promise.resolve([])]);if(stamp!==changesStamp||activeWorkspace?.id!==id)return;
      projectBranch.textContent=tr('Branch: ','الفرع: ')+(state.branch||activeProject?.branch||'—');projectBranch.hidden=!state.branch&&!activeProject?.branch;gitSummary.textContent=state.changes.length+' '+tr('working tree changes','تغييرات نسخة العمل')+' · '+(state.branch||'—')+(state.ahead!==undefined?' · '+state.ahead+tr(' unpushed commits',' commits غير مرسلة'):'');gitState.textContent=state.repository?'GitHub · '+state.repository+' → '+state.remote_branch:tr('Local project · stored on Gateway','مشروع محلي · محفوظ في Gateway');syncGit.hidden=reviewPR.hidden=!state.repository;syncGit.disabled=!state.clean||!state.github_access;reviewPR.href=state.repository?'https://github.com/'+state.repository+'/compare/'+encodeURIComponent(state.remote_branch):'#';changedFiles.replaceChildren();
      q('commitButton').disabled=state.clean||activeProject?.source_type!=='github';q('pushButton').disabled=!state.push_available||!state.clean||activeProject?.source_type!=='github';q('pushButton').textContent=tr('Push to ','Push إلى ')+(state.remote_branch||'—');q('pushButton').title=state.repository?state.repository+' / '+state.remote_branch:tr('No GitHub remote','لا يوجد مستودع GitHub');
      const runtimeFiles=new Map((Array.isArray(sessionDiff)?sessionDiff:[]).map(row=>[row.file,row]));const names=new Set([...state.changes.map(row=>row.path),...runtimeFiles.keys()]);
      const folders=new Map([['',changedFiles]]);let fileIndex=0;
      for(const name of [...names].sort((a,b)=>a.localeCompare(b,lang,{numeric:true,sensitivity:'base'}))){const parts=name.split('/');let parent='',host=changedFiles;
        for(const folder of parts.slice(0,-1)){const path=parent?parent+'/'+folder:folder;if(!folders.has(path)){const group=document.createElement('details');group.className='changed-folder';group.open=true;const summary=textElement('summary',folder);const children=textElement('div','','changed-folder-children');group.append(summary,children);host.append(group);folders.set(path,children);}host=folders.get(path);parent=path;}
        const b=btn('changed-'+fileIndex++,parts.at(-1),parts.at(-1),async()=>{const patch=runtimeFiles.get(name)?.patch;if(patch){diffView.textContent=patch;return;}const result=await api('/api/workspaces/'+id+'/diff?path='+encodeURIComponent(name));if(stamp===changesStamp&&activeWorkspace?.id===id)diffView.textContent=result.diff||tr('No textual diff','لا يوجد فرق نصّي');});b.title=name;b.dataset.path=name;host.append(b);
      }
      diffView.textContent=names.size?tr('Select a changed file to review its diff.','اختر ملفًا متغيرًا لمراجعة الفرق.'):tr('No changes in this workspace.','لا توجد تغييرات في مساحة العمل.');
    }catch(error){if(stamp===changesStamp)diffView.textContent=error.message;}
  }
  async function setPanel(mode){panelMode=mode;sessionsSection.hidden=mode!=='conversations';projectGroups.hidden=mode!=='changes';previewPanel.hidden=mode!=='preview';conversationsMode.setAttribute('aria-pressed',String(mode==='conversations'));changesMode.setAttribute('aria-pressed',String(mode==='changes'));previewMode.setAttribute('aria-pressed',String(mode==='preview'));if(mode==='conversations')await refreshSessions();if(mode==='changes')await Promise.all([loadChanges(),loadProjectGroups()]);}
  function drawer(){return matchMedia('(max-width:1100px)').matches;}
  function closePane(){paneDragEnd();pane.classList.remove('open');shell.classList.remove('panel-docked');shell.classList.add('sessions-collapsed');shell.style.gridTemplateColumns='';overlay(false);}
  function togglePane(){const opening=shell.classList.contains('sessions-collapsed')||(drawer()&&!pane.classList.contains('open'));shell.classList.toggle('sessions-collapsed',!opening);pane.classList.toggle('open',opening);shell.classList.toggle('panel-docked',drawer()&&opening);shell.style.gridTemplateColumns='';overlay(false);if(opening){setPanelWidth(panelWidth);if(panelMode==='changes')loadChanges();}}

  copy.en.spaceReadyBody='Start a session to work with OpenCode. Review changes or preview your project in the side panel.';
  copy.ar.spaceReadyBody='ابدأ جلسة للعمل مع OpenCode. راجع التغييرات أو عاين مشروعك في اللوحة الجانبية.';
  q('openSessions').onclick=togglePane;q('openSessions').setAttribute('aria-label',tr('Projects and preview','المشاريع والمعاينة'));q('openSessions').title=tr('Projects and preview','المشاريع والمعاينة');close.onclick=closePane;q('backdrop').addEventListener('click',()=>{pane.classList.remove('open');});
  const events=textElement('div');previewPanel.hidden=true;conversationsMode.setAttribute('aria-pressed','true');changesMode.setAttribute('aria-pressed','false');previewMode.setAttribute('aria-pressed','false');
  refreshGit=async()=>{await loadChanges();q('manageProviders')?.remove();};
  q('commitButton').onclick=async()=>{if(!activeWorkspace||activeProject?.source_type!=='github')return;const message=await window.requestInput(tr('Commit message','رسالة الالتزام'));if(!message?.trim())return;try{await api('/api/workspaces/'+activeWorkspace.id+'/git/commit',{method:'POST',body:JSON.stringify({message:message.trim()})});await loadChanges();}catch(error){toast(error.message);}};
  const syncGit=btn('syncWorkspaceGit','Pull / Sync (fast-forward only)','Pull / Sync (تقديم سريع فقط)',async()=>{if(!activeWorkspace)return;if(!await window.confirmAction(tr('Fetch the selected GitHub branch and fast-forward only? Uncommitted/divergent work is preserved.','جلب فرع GitHub المختار والتقديم السريع فقط؟ تُحفظ الأعمال غير المحفوظة أو المتباعدة.')))return;await api('/api/workspaces/'+activeWorkspace.id+'/git/sync',{method:'POST'});await loadChanges();await loadFiles();});syncGit.hidden=true;
  exportSource=btn('exportWorkspaceSource','Download ZIP','تنزيل المشروع ZIP',()=>downloadProjectSource(activeWorkspace,activeProject));
  projectRoot.insertBefore(exportSource,filesSection);projectKindControls();
  const reviewPR=textElement('a',tr('Review PR / Merge in GitHub','مراجعة PR / Merge في GitHub'),'button ghost small');reviewPR.target='_blank';reviewPR.rel='noopener noreferrer';reviewPR.hidden=true;
  gitActions.append(syncGit,reviewPR,textElement('small',tr('Commit saves locally. Push updates GitHub. PR and merge are reviewed in GitHub; nothing is sent automatically.','Commit يحفظ محليًا. Push يحدّث GitHub. تُراجع PR وMerge في GitHub؛ لا إرسال تلقائي.')));
  let providers=[],chosenAgent='',chosenProvider='',chosenModel='',discovery=0,modelRequest=0,runtimeReady=false,agentsReady=false,modelsReady=false;
  const retryModels=btn('retryWorkspaceModels','Retry models','أعد تحميل النماذج',()=>models());retryModels.hidden=true;controls.append(retryModels);
  // Presentation only: move existing controls with their IDs and handlers intact.
  const composerIcons={"attachFiles":"<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"m16 6-8.414 8.586a2 2 0 0 0 2.829 2.829l8.414-8.586a4 4 0 1 0-5.657-5.657l-8.379 8.551a6 6 0 1 0 8.485 8.485l8.379-8.551\"/></svg>","composerNewTask":"<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7\"/><path d=\"M18.375 2.625a1 1 0 0 1 3 3l-9.013 9.014a2 2 0 0 1-.853.505l-2.873.84a.5.5 0 0 1-.62-.62l.84-2.873a2 2 0 0 1 .506-.852z\"/></svg>","openTools":"<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M10 5H3\"/><path d=\"M12 19H3\"/><path d=\"M14 3v4\"/><path d=\"M16 17v4\"/><path d=\"M21 12h-9\"/><path d=\"M21 19h-5\"/><path d=\"M21 5h-7\"/><path d=\"M8 10v4\"/><path d=\"M8 12H3\"/></svg>","sendMessage":"<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"m5 12 7-7 7 7\"/><path d=\"M12 19V5\"/></svg>","stopAgent":"<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><rect width=\"18\" height=\"18\" x=\"3\" y=\"3\" rx=\"2\"/></svg>","refreshWorkspaceFiles":"<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8\"/><path d=\"M21 3v5h-5\"/><path d=\"M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16\"/><path d=\"M8 16H3v5\"/></svg>","openSessions":"<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><rect width=\"18\" height=\"18\" x=\"3\" y=\"3\" rx=\"2\"/><path d=\"M9 3v18\"/></svg>","closeSessions":"<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M18 6 6 18\"/><path d=\"m6 6 12 12\"/></svg>"};
  for(const [id,markup] of Object.entries(composerIcons))q(id).innerHTML=markup;
  const picks=textElement('div','','composer-picks'),utilities=textElement('div','','composer-utilities'),actions=textElement('div','','composer-actions');
  const selectIcons=['<circle cx="12" cy="7" r="3"/><path d="M5 21v-3a7 7 0 0 1 14 0v3"/>','<path d="M7 18a5 5 0 0 1-1-10 6 6 0 0 1 11-1 5.5 5.5 0 0 1 1 11Z"/>','<path d="m12 3 9 5v8l-9 5-9-5V8Z M3 8l9 5 9-5M12 13v8"/>'];
  [agent,q('providerSelect'),q('modelSelect')].forEach((select,index)=>{const label=textElement('label','','composer-select');label.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">'+selectIcons[index]+'</svg>';label.append(select);picks.append(label);});
  picks.append(nativeVariant);
  utilities.append(attach,newTask);projectPanelBrand.append(q('chatGithub'),q('openTools'));actions.append(q('stopAgent'),q('sendMessage'));
  const choices=textElement('button','','icon-btn composer-choice-toggle');choices.type='button';choices.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg>';choices.setAttribute('aria-label',tr('Agent, provider and model','الوكيل والمزوّد والنموذج'));choices.setAttribute('aria-expanded','false');
  choices.onclick=()=>{const open=picks.classList.toggle('open');choices.setAttribute('aria-expanded',String(open));};
  controls.replaceChildren(utilities,choices,picks,actions,retryModels);
  document.addEventListener('click',event=>{if(!picks.contains(event.target)&&!choices.contains(event.target)){picks.classList.remove('open');choices.setAttribute('aria-expanded','false');}});
  controls.addEventListener('keydown',event=>{if(event.key==='Escape'){picks.classList.remove('open');choices.setAttribute('aria-expanded','false');choices.focus();}});
  window.addEventListener('workspace-provider-disconnected',event=>{
    if(activeWorkspace?.id!==event.detail.workspaceId)return;
    const id=event.detail.providerId;providers=providers.filter(p=>p.id!==id);runtimeReady=false;
    for(const option of [...q('providerSelect').options])if(option.value===id)option.remove();
    if(chosenProvider===id){chosenProvider=chosenModel='';modelRequest++;modelsReady=false;retryModels.hidden=true;q('modelSelect').replaceChildren(new Option(tr('Model','النموذج'),''));}
    updateSend();
  });
  updateSend=function(){
    if(pendingSubmission&&pendingSubmission.owner!==currentUser?.id){pendingSubmission=null;retrySubmission.hidden=true;submissionStatus.textContent='';}
    const selected=providers.find(p=>p.id===q('providerSelect').value);
    agent.disabled=!workAccess||!agentsReady;
    q('providerSelect').disabled=!workAccess||!providers.some(p=>(p.connected||p.id==='opencode')&&p.allowed!==false);
    q('modelSelect').disabled=!workAccess||!modelsReady||!selected?.connected||selected.allowed===false||q('modelSelect').options.length<2;
    const busy=['submitted','waiting_approval'].includes(activeSession?.execution_status);
    renderAttachments();
    attach.disabled=!workAccess||sending||Boolean(pendingSubmission)||busy;attachmentList.querySelectorAll('button').forEach(button=>button.disabled=sending||Boolean(pendingSubmission));
    // OpenCode 1.x does not guarantee that a second prompt_async while a
    // session is already running will execute. Never advertise a Gateway
    // queue in native mode or acknowledge a potentially orphaned prompt.
    const nativeBusy=Boolean(window.nativeSession?.active()&&window.nativeSession.blocked(activeSession?.id));
    manualModel.hidden=!window.nativeSession?.active();
    recoveryAction.hidden=!window.nativeSession?.active()||!activeSession||!window.nativeSession.blocked(activeSession.id);
    cancelAttachment.hidden=!activeSession||!window.nativeSession?.pendingAttachment(activeSession.id);
    q('sendMessage').disabled=sending||queuing||nativeBusy||Boolean(pendingSubmission)||!workAccess||!runtimeReady||!modelsReady||!selected?.connected||selected.allowed===false||!q('modelSelect').value;
    q('sendMessage').title=nativeBusy?tr('OpenCode is busy — send when this turn finishes','OpenCode مشغول — أرسل بعد انتهاء الرد'):!window.nativeSession?.active()&&(busy||queueCount)?tr('Add to conversation queue','إضافة إلى طابور المحادثة'):tr('Send','إرسال');
    q('sendMessage').setAttribute('aria-label',q('sendMessage').title);
    newSessionButton.disabled=newTask.disabled=!workAccess||(!window.nativeSession?.active()&&busy)||sending||Boolean(sessionCreating)||Boolean(pendingSubmission);
    closeSessionButton.disabled=!activeSession||sending||Boolean(pendingSubmission);
    // Unconfirmed Native receipt is still an actionable stop: even an idle
    // runtime needs a verified session-scoped stop to unblock the saved draft.
    q('stopAgent').disabled=(!busy&&!sending&&!pendingSubmission&&!nativeBusy)||Boolean(cancelRequested);
  }
  // Existing entitlement rendering also updates workspace buttons. Reapply the
  // session/submission guards without changing subscription or billing logic.
  const renderAccess=renderEntitlement;renderEntitlement=function(){renderAccess();updateSend();};
  let conversationSelection=0;
  let openingConversation=null;
  function markConversationOpening(){
    for(const button of q('sessionList')?.querySelectorAll?.('.conversation-name')||[])
      button.setAttribute('aria-busy',String(button.id==='conversation-'+openingConversation?.id));
  }
  async function openConversation(row){
    if(row.id===activeSession?.id)return;
    if(openingConversation?.id===row.id&&openingConversation.owner===currentUser?.id)return;
    if(sending||pendingSubmission){toast(tr('Finish or confirm the pending submission before changing sessions.','أكمل أو تحقق من الطلب المعلّق قبل تغيير الجلسة.'));return;}
    const owner=currentUser?.id,revision=++conversationSelection;
    const current=()=>currentUser?.id===owner&&revision===conversationSelection;
    openingConversation={id:row.id,owner};markConversationOpening();
    try{
      if(row.workspace_id&&row.workspace_id!==activeWorkspace?.id){
        const workspace=await api('/api/workspaces/'+encodeURIComponent(row.workspace_id));if(!current())return;
        const project=await api('/api/projects/'+encodeURIComponent(workspace.project_id));if(!current())return;
        await openWorkspace(project,workspace,{navigate:false});if(!current()||activeWorkspace?.id!==workspace.id)return;
      }
      if(row.lifecycle==='archived')await sessionAction(row,'restore');
      if(!current())return;
      await selectSession(row);if(!current()||activeSession?.id!==row.id)return;
      if(!q('workspacePage').classList.contains('active'))await page('workspacePage');
      await loadFiles();if(current())await loadProjectGroups();
    }catch(error){if(current())toast(error.message);}
    finally{if(revision===conversationSelection){openingConversation=null;markConversationOpening();}}
  }
  function renderRuntimeSessions(rows){
    if(!rows)return;sessionsCount.textContent=String(rows.length);sessionRows=[...rows].sort((a,b)=>(Date.parse(b.created_at)||0)-(Date.parse(a.created_at)||0)||String(a.id).localeCompare(String(b.id)));const list=q('sessionList');
    const shown=sessionRows.filter(row=>(sessionFilter==='all'?row.lifecycle!=='archived':(row.lifecycle||'closed')===sessionFilter)&&row.title.toLowerCase().includes(search.value.toLowerCase()));
    const snapshot=JSON.stringify([currentUser?.id,tr('Conversations','المحادثات'),shown.map(row=>[row.id,row.title,row.lifecycle])]);
    if(list.conversationSnapshot===snapshot&&list.childElementCount&&list.querySelectorAll('.conversation-row').length===shown.length){
      for(const item of list.querySelectorAll('.conversation-row')){
        const current=item.dataset.sessionId===activeSession?.id;item.classList.toggle('current',current);
        const name=item.querySelector('.conversation-name');if(current)name.setAttribute('aria-current','true');else name.removeAttribute('aria-current');
      }
      updateSend();return;
    }
    const positions=[];for(let node=list;node&&node!==document.body;node=node.parentElement)positions.push([node,node.scrollTop,node.scrollLeft]);
    const focused=list.contains(document.activeElement)?document.activeElement?.id:null,fragment=document.createDocumentFragment();
    if(!shown.length)fragment.append(textElement('p',tr('No sessions in this category.','لا توجد جلسات في هذا القسم.'),'muted-small'));
    for(const row of shown){
      const current=row.id===activeSession?.id,item=textElement('div','','conversation-row'+(current?' current':''));
      item.dataset.sessionId=row.id;
      const name=btn('conversation-'+row.id,row.title,row.title,()=>openConversation(row));name.className='conversation-name';name.title=row.title;if(current)name.setAttribute('aria-current','true');
      name.setAttribute('aria-busy',String(typeof openingConversation!=='undefined'&&openingConversation?.id===row.id));
      const menu=document.createElement('details');menu.className='conversation-menu';const more=textElement('summary','⋯');more.setAttribute('aria-label',tr('Conversation actions: ','خيارات المحادثة: ')+row.title);menu.append(more);const actions=textElement('div','','session-actions');
      actions.append(btn('rename-session-'+row.id,'Rename','تغيير الاسم',()=>renameConversation(row)));
      if(row.lifecycle==='active')actions.append(btn('close-session-'+row.id,'Close / Disconnect','إغلاق / فصل',()=>sessionAction(row,'close')));
      else if(row.lifecycle==='archived')actions.append(btn('restore-session-'+row.id,'Restore','استعادة',()=>sessionAction(row,'restore')));
      else actions.append(btn('archive-session-'+row.id,'Archive','أرشفة',()=>sessionAction(row,'archive')));
      if(row.lifecycle!=='active')actions.append(btn('delete-session-'+row.id,'Delete from history','حذف من السجل',()=>sessionAction(row,'delete')));
      // Float the actions outside the row layout without changing session actions.
      menu.addEventListener('toggle',()=>{
        if(!menu.open||!menu.isConnected)return;
        for(const other of list.querySelectorAll('.conversation-menu[open]'))if(other!==menu)other.open=false;
        const anchor=more.getBoundingClientRect(),width=190;
        const left=Math.min(Math.max(8,anchor.right-width),window.innerWidth-width-8);
        const spaceBelow=window.innerHeight-anchor.bottom;
        actions.style.left=left+'px';
        actions.style.right='auto';
        actions.style.top=spaceBelow>=130?Math.max(8,anchor.bottom+4)+'px':'auto';
        actions.style.bottom=spaceBelow>=130?'auto':Math.max(8,window.innerHeight-anchor.top+4)+'px';
      });
      menu.append(actions);item.append(name,menu);fragment.append(item);
    }
    list.replaceChildren(fragment);list.conversationSnapshot=snapshot;
    if(focused)q(focused)?.focus({preventScroll:true});
    for(const [node,top,left] of positions){node.scrollTop=top;node.scrollLeft=left;}
    updateSend();
  }
  document.addEventListener('click',event=>{
    for(const menu of document.querySelectorAll('#workspacePage .conversation-menu[open]')){
      if(!menu.contains(event.target))menu.open=false;
    }
  });
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape')for(const menu of document.querySelectorAll('#workspacePage .conversation-menu[open]'))menu.open=false;
  });
  q('sessionList').addEventListener('scroll',()=>{
    for(const menu of q('sessionList').querySelectorAll('.conversation-menu[open]'))menu.open=false;
  },{passive:true});
  refreshSessions=async function(){
    if(!activeWorkspace)return;
    const workspaceId=activeWorkspace.id,owner=currentUser?.id;
    if(sessionListPending?.workspaceId===workspaceId&&sessionListPending.owner===owner)return sessionListPending.promise;
    const history=++historyRevision;
    const promise=(async()=>{
      const runtime=api('/api/workspaces/'+workspaceId+'/sessions?include_archived=true').then(rows=>({rows}),error=>({error}));
      const account=api('/api/sessions?include_archived=true').then(accountRows=>{if(currentUser?.id===owner&&history===historyRevision)renderRuntimeSessions(accountRows);},error=>{if(currentUser?.id===owner&&history===historyRevision)throw error;});
      const [result]=await Promise.all([runtime,account]);if(activeWorkspace?.id!==workspaceId||currentUser?.id!==owner)return;
      if(result.error)throw result.error;const rows=result.rows;
      const current=rows.find(row=>row.id===activeSession?.id);if(current&&current.lifecycle==='active')activeSession={...activeSession,...current};
      if(!activeSession){const open=rows.find(row=>row.lifecycle==='active');if(open)await selectSession(open);}updateSend();return rows;})();
    sessionListPending={workspaceId,owner,promise};try{return await promise;}finally{if(sessionListPending?.promise===promise)sessionListPending=null;}
  };
  async function renameConversation(row){
    const owner=currentUser?.id;
    if(!row||!owner)return;
    const result=await window.requestForm(tr('Rename conversation','تغيير اسم المحادثة'),[
      {name:'title',label:tr('Conversation name','اسم المحادثة'),value:row.title,required:true,maxLength:120}
    ]);
    if(!result||currentUser?.id!==owner)return;
    const title=result.title.trim();if(!title||title===row.title)return;
    const updated=await api('/api/sessions/'+encodeURIComponent(row.id),{method:'PATCH',body:JSON.stringify({title})});
    if(currentUser?.id!==owner)return;
    sessionRows=sessionRows.map(session=>session.id===row.id?{...session,...updated}:session);
    if(activeSession?.id===row.id)activeSession={...activeSession,...updated};
    renderRuntimeSessions(sessionRows);
  }
  async function sessionAction(row,action){
    if(!row||sending||pendingSubmission)return;
    if(action==='delete'&&!await window.confirmAction(tr('Delete from client history? OpenCode history and project files are preserved.','حذف من سجل العميل؟ يبقى سجل OpenCode وملفات المشروع محفوظة.')))return;
    const workspaceId=activeWorkspace?.id;
    const result=await api('/api/sessions/'+row.id+(action==='delete'?'':'/'+action),{method:action==='delete'?'DELETE':'POST'});
    if(activeWorkspace?.id!==workspaceId)return;
    if(row.id===activeSession?.id&&['close','archive','delete'].includes(action)){stopEvents();sessionSelectionRevision++;activeSession=null;window.resetWorkspaceQuestions?.();window.refreshWorkspaceTodos?.(true);renderWorkspaceEmpty();}
    sessionRows=action==='delete'?sessionRows.filter(session=>session.id!==row.id):sessionRows.map(session=>session.id===row.id?{...session,...result}:session);
    renderRuntimeSessions(sessionRows);
    await refreshSessions();updateSend();
  }
  window.addEventListener('workspace-session-lifecycle',event=>{
    const {sessionId,workspaceId,action,result}=event.detail;
    if(activeWorkspace?.id!==workspaceId)return;
    if(activeSession?.id===sessionId&&['close','archive','delete'].includes(action)){stopEvents();sessionSelectionRevision++;activeSession=null;window.resetWorkspaceQuestions?.();window.refreshWorkspaceTodos?.(true);renderWorkspaceEmpty();}
    sessionRows=action==='delete'?sessionRows.filter(row=>row.id!==sessionId):sessionRows.map(row=>row.id===sessionId?{...row,...result}:row);
    renderRuntimeSessions(sessionRows);
  });
  function renderAgents(snapshot){
    agent.title=snapshot.errors?.agents?.detail||tr('Agent','الوكيل');agent.hidden=false;agent.replaceChildren(new Option((snapshot.default_agent==='build'?'Code':snapshot.default_agent==='plan'?'Plan':tr('Agent','الوكيل')),''));
    for(const a of snapshot.agents||[]){const option=new Option((a.name==='build'?'Code':a.name==='plan'?'Plan':a.name)+(a.mode==='subagent'?tr(' · Subagent',' · وكيل فرعي'):''),a.name);option.disabled=Boolean(a.hidden)||!['primary','all'].includes(a.mode);agent.add(option);}
    agentsReady=snapshot.agents!==null;
    agent.value=(snapshot.agents||[]).some(a=>a.name===chosenAgent&&!a.hidden&&['primary','all'].includes(a.mode))?chosenAgent:'';
    chosenAgent=agent.value;agent.onchange=()=>{chosenAgent=agent.value;saveNativeSelection();updateSend();};updateSend();
  }
  function renderProviders(snapshot,preferredProvider=''){
    providers=(snapshot.providers||[]).filter(p=>(p.visible!==false||p.id===preferredProvider||p.id===chosenProvider)&&p.auth_status!=='reauthorization_required'&&!p.locally_disconnected&&p.allowed!==false&&(p.connected||p.id==='opencode'));q('providerSelect').replaceChildren(new Option(tr('Provider','المزوّد'),''));
    for(const p of providers.filter(p=>p.connected||p.id==='opencode')){const option=new Option(p.name+' · '+(p.allowed===false?tr('Restricted','مقيّد'):p.connected?tr('Connected','متصل'):tr('Default provider','المزوّد الافتراضي')),p.id);option.disabled=p.allowed===false;q('providerSelect').add(option);}
    if(preferredProvider)chosenProvider=preferredProvider;
    if(!providers.some(p=>p.id===chosenProvider)){chosenProvider='';chosenModel='';}
    if(!chosenProvider){const configured=snapshot.config?.model;const configuredProvider=providers.find(p=>typeof configured==='string'&&configured.startsWith(p.id+'/'));const connected=providers.filter(p=>p.connected&&p.allowed!==false);chosenProvider=configuredProvider?.id||(window.nativeSession?.active()?connected[0]?.id||'':connected.length===1?connected[0].id:'');if(configuredProvider)chosenModel=configured.slice(configuredProvider.id.length+1);}
    if(providers.some(p=>p.id===chosenProvider))q('providerSelect').value=chosenProvider;
    q('providerSelect').onchange=()=>{chosenProvider=q('providerSelect').value;chosenModel='';models();};q('modelSelect').onchange=()=>{chosenModel=q('modelSelect').value;renderNativeVariants();saveNativeSelection();updateSend();};models();
  }
  refreshChoices=async function(preferredProvider='',force=false){
    if(!activeWorkspace)return;
    const workspaceId=activeWorkspace.id,stamp=++discovery,started=performance.now();
    const current=()=>stamp===discovery&&activeWorkspace?.id===workspaceId;
    runtimeReady=false;updateSend();
    const cached=window.workspaceRuntime.peek(workspaceId),cachedAgents=window.workspaceRuntime.peekAgents(workspaceId);
    if(cached)renderProviders(cached,preferredProvider);if(cachedAgents)renderAgents(cachedAgents);
    q('runtimeStatus').textContent=cached?tr('Refreshing OpenCode…','جارٍ تحديث OpenCode…'):tr('Starting OpenCode…','جارٍ بدء OpenCode…');
    const agentsJob=window.workspaceRuntime.loadAgents(workspaceId).then(snapshot=>{
      if(!current())return;renderAgents(snapshot);
      performance.measure('OpenCode agents populated '+workspaceId,{start:started,end:performance.now()});
    }).catch(error=>{if(current()){agentsReady=false;agent.title=error.message;updateSend();}});
    const providersJob=window.workspaceRuntime.load(workspaceId,{force}).then(snapshot=>{
      if(!current())return;
      runtimeReady=snapshot.health?.healthy===true&&snapshot.providers!==null;
      renderProviders(snapshot,preferredProvider);renderAgents(snapshot);
      q('runtimeStatus').textContent='OpenCode '+snapshot.version+' · '+snapshot.status;
      for(const error of Object.values(snapshot.errors||{}))toast(error.detail);
      performance.measure('OpenCode providers populated '+workspaceId,{start:started,end:performance.now()});
    }).catch(error=>{if(current()){runtimeReady=false;q('runtimeStatus').textContent=error.message;updateSend();toast(error.message);}});
    await Promise.allSettled([agentsJob,providersJob]);
  }
  async function models(){
    const stamp=++modelRequest,workspaceId=activeWorkspace?.id,selected=providers.find(p=>p.id===q('providerSelect').value);
    const current=()=>stamp===modelRequest&&activeWorkspace?.id===workspaceId&&q('providerSelect').value===selected?.id;
    modelsReady=false;retryModels.hidden=true;
    const render=rows=>{
      rows=rows.filter(m=>m.visible!==false||m.id===chosenModel);
      q('modelSelect').replaceChildren(new Option(tr('Model','النموذج'),''));
      for(const model of rows){const option=new Option(model.name||model.id,model.id);option.disabled=model.allowed===false;q('modelSelect').add(option);}
      const preferred=chosenModel||selected?.default_model||'';
      q('modelSelect').value=rows.some(m=>m.id===preferred&&m.allowed!==false)?preferred:(window.nativeSession?.active()?rows.find(m=>m.allowed!==false)?.id||'':'');
    };
    render(selected&&workspaceId?window.workspaceRuntime.peekModels(workspaceId,selected.id)?.models||[]:[]);updateSend();
    if(!runtimeReady||!selected?.connected||selected.allowed===false)return;
    if(q('modelSelect').options.length===1)q('modelSelect').options[0].textContent=tr('Loading models…','جارٍ تحميل النماذج…');
    try{
      const data=await window.workspaceRuntime.loadModels(workspaceId,selected.id);
      if(!current())return;render(data.models);modelsReady=data.allowed!==false&&data.connected===true;
      chosenModel=q('modelSelect').value;q('modelSelect').title=tr('Model','النموذج');renderNativeVariants();updateSend();
    }catch(error){if(current()){q('modelSelect').title=error.message;q('modelSelect').options[0].textContent=tr('Could not load models','تعذر تحميل النماذج');retryModels.hidden=false;updateSend();toast(error.message);}}
  }
  window.refreshWorkspaceChoices=async(preferredProvider='',force=true)=>{if(activeWorkspace&&force)window.workspaceRuntime.invalidate(activeWorkspace.id);return refreshChoices(preferredProvider,force);};
  window.addEventListener('account-provider-changed',event=>{if(currentUser?.id===event.detail.owner&&activeWorkspace&&!sending&&!pendingSubmission)window.refreshWorkspaceChoices(chosenProvider,false).catch(()=>{});});
  let providerCheckPending=false;
  setInterval(async()=>{
    if(window.nativeSession?.active()||providerCheckPending||document.hidden||!currentUser||!activeWorkspace||sending||pendingSubmission||!q('workspacePage').classList.contains('active'))return;
    const id=activeWorkspace.id,owner=currentUser.id,previous=window.workspaceRuntime.peek(id);
    providerCheckPending=true;
    try{if(!previous){await window.refreshWorkspaceChoices(chosenProvider,true);return;}
      const state=await api('/api/workspaces/'+encodeURIComponent(id)+'/runtime/state');
      if(currentUser?.id===owner&&activeWorkspace?.id===id&&(state.policy_revision!==previous.policy_revision||state.revision!==previous.revision||state.generation!==previous.generation))await window.refreshWorkspaceChoices(chosenProvider,true);
    }catch(error){}finally{providerCheckPending=false;}
  },10000);
  openWorkspace=async function(project,workspace,{navigate=true}={}){
    if(admin()){await page('adminPage');return;}
    if(sending||pendingSubmission)throw new Error(tr('Confirm or cancel the pending submission before switching workspaces.','تحقق من الطلب المعلّق أو ألغِه قبل تغيير مساحة العمل.'));
    if(!await usableWorkspace(workspace)){toast(tr('Project files are unavailable. Create or open another project.','ملفات المشروع غير متاحة. أنشئ مشروعًا أو افتح مشروعًا آخر.'));if(navigate)await page('workspaceHomePage');return;}
    saveNativeDraft();window.closeNativeFile?.();if(activeWorkspace?.id!==workspace.id){clearAttachments();storageData=null;storageChip.textContent='';}detailLoads.delete(workspace.id);stopEvents();workspaceSelectionRevision++;activeProject=project;activeWorkspace=workspace;activeSession=null;restoreNativeDraft();window.resetWorkspaceQueue?.();window.resetWorkspaceQuestions?.();window.refreshWorkspaceTodos?.(true);retrySubmission.hidden=true;submissionStatus.textContent='';capabilityView.open=false;capabilityWorkspace='';capabilityBody.replaceChildren();activityStage.textContent=activitySummary.textContent='';try{localStorage.setItem('og-workspace',workspace.id);}catch(error){}
    discovery++;modelRequest++;chosenAgent=chosenProvider=chosenModel='';providers=[];runtimeReady=agentsReady=modelsReady=false;retryModels.hidden=true;q('providerSelect').replaceChildren(new Option(tr('Loading providers…','جارٍ تحميل المزوّدات…'),''));q('modelSelect').replaceChildren(new Option(tr('Model','النموذج'),''));events.replaceChildren();changesStamp++;changedFiles.replaceChildren();diffView.textContent='';clearPreview();previewStatus.textContent=tr('Select Start to check this project’s preview availability.','اختر التشغيل للتحقق من توفر معاينة هذا المشروع.');previewPath.hidden=false;filesTree.replaceChildren();filesStatus.textContent=tr('Loading files…','جارٍ تحميل الملفات…');
    q('stopAgent').disabled=true;q('workspaceRepo').textContent=project.name;q('workspaceBranch').textContent=project.branch||'—';
    renderWorkspaceEmpty();q('promptInput').value=pendingIdea;window.resizeWorkspaceComposer?.();pendingIdea='';agent.hidden=false;agent.replaceChildren(new Option(tr('OpenCode default','افتراضي OpenCode'),''));updateSend();
    if(!navigate){
      syncWorkspacePolling();
      // Conversation navigation keeps the page mounted. Restart discovery for
      // this workspace after resetting its choices; no page() re-entry needed.
      if(q('workspacePage').classList.contains('active'))refreshChoices().catch(error=>toast(error.message));
      return;
    }
    await page('workspacePage');
    window.authSession?.workspaceOpened();

  };
  async function refreshSessionStatus(){
    if(!activeSession)return;const sessionId=activeSession.id,workspaceId=activeWorkspace?.id,owner=currentUser?.id;
    if(statusPending?.sessionId===sessionId)return statusPending.promise;
    const promise=(async()=>{const row=await api('/api/sessions/'+sessionId);if(activeSession?.id!==sessionId||activeWorkspace?.id!==workspaceId||currentUser?.id!==owner)return;
      activeSession={...activeSession,...row};q('runtimeStatus').textContent=row.status;if(['completed','failed','cancelled'].includes(row.execution_status))window.renderWorkspaceEventLine?.(row.execution_status);
      if(!pendingSubmission&&!['submitted','waiting_approval'].includes(row.execution_status)){
        try{sessionStorage.removeItem('og-submit:'+owner+':'+sessionId);}catch(error){}
      }
      sessionRows=sessionRows.map(s=>s.id===row.id?{...s,...row}:s);renderRuntimeSessions(sessionRows);updateSend();await refreshMessageQueue();return row;
    })();statusPending={sessionId,promise};try{return await promise;}finally{if(statusPending?.promise===promise)statusPending=null;}
  }
  window.refreshWorkspaceSessionStatus=refreshSessionStatus;
  let eventRefreshTimer=null;
  window.addEventListener('authentication-cleared',()=>{
    historyRevision++;conversationSelection++;openingConversation=null;
    if(drawer())closePane();window.resetWorkspaceQuestions?.();window.refreshWorkspaceTodos?.(true);window.refreshWorkspaceQueue?.();clearAttachments();clearTimeout(eventRefreshTimer);clearInterval(storageTimer);storageTimer=null;discovery++;modelRequest++;changesStamp++;
    pendingSubmission=null;sending=cancelRequested=false;sessionRows=[];providers=[];chosenAgent=chosenProvider=chosenModel='';
    runtimeReady=agentsReady=modelsReady=workAccess=false;entitlement=null;workspaceDays.hidden=workspaceAccess.hidden=true;workspaceDays.textContent='';workspaceAccess.replaceChildren();homeAccess.replaceChildren();retrySubmission.hidden=retryModels.hidden=true;
    storageData=null;submissionStatus.textContent=storageChip.textContent=activityStage.textContent=activitySummary.textContent='';
    capabilityView.open=false;capabilityWorkspace='';capabilityBody.replaceChildren();changedFiles.replaceChildren();diffView.textContent='';frame.srcdoc='';frame.hidden=true;approvalsList.replaceChildren();detailLoads.clear();updateSend();
  });
  window.addEventListener('workspace-execution-event',event=>{
    if(activeSession?.id!==event.detail.sessionId)return;
    const sessionId=event.detail.sessionId;clearTimeout(eventRefreshTimer);eventRefreshTimer=setTimeout(()=>{if(activeSession?.id!==sessionId)return;refreshSessionStatus().then(row=>{if(!row||activeSession?.id!==row.id)return;refreshMessages().catch(()=>{});if(['failed','completed','cancelled'].includes(row.execution_status)&&panelMode==='changes'&&!shell.classList.contains('sessions-collapsed'))refreshGit().catch(error=>toast(error.message));}).catch(error=>toast(error.message));},50);
  });
  const originalSession=selectSession;selectSession=async function(session){
    if(sending||pendingSubmission){toast(tr('Finish or confirm the pending submission before changing sessions.','أكمل أو تحقق من الطلب المعلّق قبل تغيير الجلسة.'));return;}
    // Restored sessions can arrive before background access initialization.
    // Resolve access for this selection without delaying the page shell.
    if(!workAccess)await refreshEntitlement();
    if(!workAccess){toast(tr('Subscribe to resume this conversation.','اشترك لاستئناف هذه المحادثة.'));return;}
    saveNativeDraft();window.resetWorkspaceQueue?.();activityStage.textContent=activitySummary.textContent='';await originalSession(session);if(activeSession?.id!==session.id)return;
    if(window.nativeSession?.active()){restoreNativeDraft();const selected=window.nativeSession.selection(session.id);chosenProvider=selected?.providerID||activeSession.model?.providerID||'';chosenModel=selected?.modelID||activeSession.model?.id||'';chosenAgent=selected?.agent||activeSession.agent||'';await refreshChoices(chosenProvider);}
    if(drawer())closePane();
    sessionRows=sessionRows.map(row=>row.id===session.id?{...row,...activeSession}:row);
    let saved=null;try{saved=JSON.parse(sessionStorage.getItem('og-submit:'+currentUser.id+':'+session.id)||'null');}catch(error){}
    if(saved?.request_id){pendingSubmission={...saved,owner:currentUser.id,workspaceId:activeWorkspace.id,sessionId:session.id,recovered:true};retrySubmission.hidden=false;submissionStatus.textContent=tr('Checking the previous submission; it will not be resent automatically.','جارٍ التحقق من الطلب السابق؛ لن يُعاد إرساله تلقائيًا.');await submitPending();}
    renderRuntimeSessions(sessionRows);updateSend();window.refreshWorkspaceQueue?.();if(panelMode==='changes'&&!shell.classList.contains('sessions-collapsed'))loadChanges();loadApprovals().catch(()=>{});
  };
  async function createSession({checked=false,title:conversationTitle=''}={}){
    if(sessionCreating)return sessionCreating;
    if(!activeWorkspace)return;
    if(!window.nativeSession?.active()&&(sending||pendingSubmission||sessionRows.some(s=>s.workspace_id===activeWorkspace.id&&['submitted','waiting_approval'].includes(s.execution_status))))throw new Error(tr('Finish or stop running work before creating another conversation.','أكمل التنفيذ الجاري أو أوقفه قبل إنشاء محادثة أخرى.'));
    saveNativeDraft();const workspaceId=activeWorkspace.id,owner=currentUser?.id;
    const promise=(async()=>{if(!checked)await refreshEntitlement();if(!workAccess||activeWorkspace?.id!==workspaceId||currentUser?.id!==owner)return;
      const title=String(conversationTitle).trim().slice(0,120)||q('promptInput').value.trim().slice(0,80)||tr('New session','جلسة جديدة');
      const row=await api('/api/workspaces/'+workspaceId+'/sessions',{method:'POST',body:JSON.stringify({title})});
      if(activeWorkspace?.id!==workspaceId||currentUser?.id!==owner)return;
      // Creation already opens the session server-side. Select once, without a
      // second creation or an auto-restore/open race during list refresh.
      await originalSession(row);if(window.nativeSession?.active()){if(sending)nativeDraftContext=nativeDraftKey();else restoreNativeDraft();}await refreshSessions();return activeSession;
    })();sessionCreating=promise;updateSend();try{return await promise;}finally{if(sessionCreating===promise)sessionCreating=null;updateSend();}
  }
  async function chooseNewConversation(initialKind=null,anchor=newSessionButton){
    if(!currentUser||sending||pendingSubmission)return;
    document.querySelector('.new-conversation-dialog')?.close();
    const owner=currentUser.id,dialog=document.createElement('dialog');dialog.className='new-conversation-dialog';dialog.setAttribute('aria-label',tr('New conversation project','مشروع المحادثة الجديدة'));
    const head=textElement('div','','new-conversation-head'),choices=textElement('div','','new-conversation-kinds'),body=textElement('div','','new-conversation-body'),feedback=textElement('p','','api-message');feedback.setAttribute('role','status');
    const close=btn('newConversationClose','Cancel','إلغاء',()=>dialog.close(),'new-conversation-close');head.append(title('New conversation','محادثة جديدة'),close);dialog.append(head,choices,body,feedback);document.body.append(dialog);let revision=0;
    function position(){const rect=anchor.getBoundingClientRect(),box=dialog.getBoundingClientRect();dialog.style.left=Math.max(12,Math.min(rect.right-box.width,window.innerWidth-box.width-12))+'px';dialog.style.top=Math.max(12,Math.min(rect.bottom+6,window.innerHeight-box.height-12))+'px';}
    const outside=event=>{if(!dialog.contains(event.target)&&!anchor.contains(event.target)&&!sessionSourceMenu.contains(event.target))dialog.close();};
    const escape=event=>{if(event.key==='Escape'){event.preventDefault();dialog.close();anchor.focus();}};
    const signedOut=()=>dialog.close();
    dialog.addEventListener('close',()=>{document.removeEventListener('click',outside);document.removeEventListener('keydown',escape);window.removeEventListener('resize',position);window.removeEventListener('authentication-cleared',signedOut);dialog.remove();},{once:true});
    dialog.show();position();window.addEventListener('resize',position);window.addEventListener('authentication-cleared',signedOut);
    const valid=()=>dialog.open&&currentUser?.id===owner;
    async function start(project,workspace,conversationTitle=''){if(!valid())return;choices.querySelectorAll('button').forEach(b=>b.disabled=true);body.querySelectorAll('button').forEach(b=>b.disabled=true);
      try{if(sending||pendingSubmission)throw new Error(tr('Finish the pending submission first.','أكمل الطلب المعلّق أولًا.'));if(activeWorkspace?.id!==workspace.id)await openWorkspace(project,workspace,{navigate:false});if(!valid()||activeWorkspace?.id!==workspace.id)return;const result=await createSession({title:conversationTitle.trim()||project.name||project.repository});if(result&&valid()){dialog.close();await page('workspacePage');}}
      catch(error){if(valid())feedback.textContent=error.message;}finally{if(valid()){choices.querySelectorAll('button').forEach(b=>b.disabled=false);body.querySelectorAll('button').forEach(b=>b.disabled=false);}}
    }
    async function show(kind){const stamp=++revision;body.replaceChildren();feedback.textContent=tr('Loading projects…','جارٍ تحميل المشاريع…');for(const button of choices.querySelectorAll('button'))button.setAttribute('aria-pressed',String(button.id==='conversation-kind-'+kind));
      if(kind==='github')body.append(btn('newConversationGithubImport','Open GitHub repository…','فتح مستودع GitHub…',()=>{dialog.close();return openRepositoryPicker(async(project,workspace)=>{if(currentUser?.id===owner&&activeWorkspace?.id===workspace.id)await createSession({title:project.name||project.repository});});},'new-conversation-submit'));
      else{const form=document.createElement('form'),label=textElement('label',tr('Project and conversation name','اسم المشروع والمحادثة')),name=document.createElement('input');name.id='newConversationProjectName';name.required=true;name.maxLength=120;label.append(name);const submit=textElement('button',tr('Create project and conversation','إنشاء مشروع ومحادثة'),'new-conversation-submit');submit.type='submit';form.append(label,submit);body.append(form);
        form.onsubmit=async event=>{event.preventDefault();if(!valid()||!form.reportValidity()||submit.disabled||!name.value.trim())return;submit.disabled=true;const requestedName=name.value.trim();try{const result=await api('/api/projects',{method:'POST',body:JSON.stringify({source_type:'blank',project_name:requestedName})});if(valid())await start(result.project,result.workspace,requestedName);}catch(error){if(valid())feedback.textContent=error.message;}finally{submit.disabled=false;}};
      }
      try{const data=await api('/api/dashboard');if(!valid()||stamp!==revision)return;feedback.textContent='';
        const projects=(data.projects||[]).filter(project=>(project.source_type==='github')===(kind==='github')&&project.workspaces?.length);
        if(projects.length){const form=document.createElement('form');form.className='new-conversation-existing';const label=textElement('label',tr('Existing project','مشروع موجود')),select=document.createElement('select');select.id='newConversationExistingProject';select.required=true;const placeholder=document.createElement('option');placeholder.value='';placeholder.textContent=tr('Choose a project','اختر مشروعًا');select.append(placeholder);
          for(const project of projects){const option=document.createElement('option');option.value=project.id;option.textContent=project.repository||project.name;select.append(option);}label.append(select);
          const nameLabel=textElement('label',tr('Conversation name (optional)','اسم المحادثة (اختياري)')),name=document.createElement('input');name.id='newConversationTitle';name.maxLength=120;name.placeholder=tr('Use project name','استخدام اسم المشروع');nameLabel.append(name);
          const submit=textElement('button',tr('Open conversation','فتح محادثة'),'new-conversation-submit');submit.type='submit';form.append(label,nameLabel,submit);body.append(form);
          form.onsubmit=async event=>{event.preventDefault();if(!valid()||!form.reportValidity()||submit.disabled)return;const project=projects.find(p=>p.id===select.value);if(!project)return;const workspace=project.workspaces.find(w=>w.status==='ready')||project.workspaces[0];await start(project,workspace,name.value);};
        }else body.append(textElement('p',tr('No existing projects in this section.','لا توجد مشاريع سابقة في هذا القسم.'),'new-conversation-empty'));
      }catch(error){if(valid()&&stamp===revision)feedback.textContent=error.message;}
      if(valid())position();
    }
    for(const [kind,en,ar] of [['local','Local','محلي'],['github','GitHub','GitHub']])choices.append(btn('conversation-kind-'+kind,en,ar,()=>show(kind),'button ghost small'));
    if(initialKind==='github'||initialKind==='local')await show(initialKind);
    if(valid()){document.addEventListener('click',outside);document.addEventListener('keydown',escape);dialog.querySelector('input,select')?.focus();}
  }
  // Compact source picker; keep existing project/session creation functions unchanged.
  const sessionSourceMenu=document.createElement('div');sessionSourceMenu.className='session-source-menu';sessionSourceMenu.hidden=true;
  sessionSourceMenu.setAttribute('role','group');sessionSourceMenu.setAttribute('aria-label',tr('New conversation source','مصدر المحادثة الجديدة'));
  for(const [kind,en,ar] of [['local','Local project','مشروع محلي'],['github','GitHub','GitHub']]){
    const item=btn('conversation-source-'+kind,en,ar,()=>{sessionSourceMenu.hidden=true;newSessionButton.setAttribute('aria-expanded','false');chooseNewConversation(kind).catch(error=>toast(error.message));},'session-source-option');
    sessionSourceMenu.append(item);
  }
  sessionsSummary.append(sessionSourceMenu);
  newSessionButton.setAttribute('aria-haspopup','true');newSessionButton.setAttribute('aria-expanded','false');
  newSessionButton.onclick=()=>{if(newSessionButton.disabled)return;sessionSourceMenu.hidden=!sessionSourceMenu.hidden;newSessionButton.setAttribute('aria-expanded',String(!sessionSourceMenu.hidden));};
  document.addEventListener('click',event=>{if(!sessionsSummary.contains(event.target)){sessionSourceMenu.hidden=true;newSessionButton.setAttribute('aria-expanded','false');}});
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!sessionSourceMenu.hidden){sessionSourceMenu.hidden=true;newSessionButton.setAttribute('aria-expanded','false');newSessionButton.focus();}});


  const projectMenu=document.createElement('details');projectMenu.className='composer-project-menu';projectMenu.id='composerProjectMenu';
  const projectMenuToggle=document.createElement('summary');projectMenuToggle.setAttribute('aria-label',tr('Projects and connections','المشاريع والربط'));projectMenuToggle.title=tr('Projects and connections','المشاريع والربط');projectMenuToggle.innerHTML='<svg class="ui-icon" aria-hidden="true"><use href="#icon-plus"/></svg>';const projectMenuItems=textElement('div');projectMenu.append(projectMenuToggle,projectMenuItems);
  for(const [kind,en,ar,icon] of [['local','Local project','مشروع محلي','icon-folder'],['github','GitHub','GitHub','icon-github']]){const button=btn('composer-project-'+kind,en,ar,()=>{projectMenu.open=false;return chooseNewConversation(kind,projectMenuToggle).catch(error=>toast(error.message));});button.prepend(textElement('span'));button.firstChild.innerHTML='<svg class="ui-icon" aria-hidden="true"><use href="#'+icon+'"/></svg>';projectMenuItems.append(button);}
  utilities.append(projectMenu);document.addEventListener('click',event=>{if(projectMenu.open&&!projectMenu.contains(event.target))projectMenu.open=false;});document.addEventListener('keydown',event=>{if(event.key==='Escape')projectMenu.open=false;});window.addEventListener('authentication-cleared',()=>{projectMenu.open=false;});

  // Separate the submitted text from the next draft before any network wait.
  // Input revisions protect even an identical new draft (or deliberate deletion).
  let composerDraftRevision=0;
  let nativeDraftContext='';
  const nativeDraftKey=()=>currentUser&&activeWorkspace?'og-native-draft:'+currentUser.id+':'+activeWorkspace.id+':'+(activeSession?.id||'new'):'';
  function saveNativeDraft(){if(!window.nativeSession?.active()||!nativeDraftContext)return;try{localStorage.setItem(nativeDraftContext,JSON.stringify({text:q('promptInput').value,attachments:attachments.filter(a=>a.path&&!a.error)}));}catch{}}
  function restoreNativeDraft(){if(!window.nativeSession?.active())return;const key=nativeDraftKey();if(key===nativeDraftContext)return;nativeDraftContext=key;let value=null;try{value=JSON.parse(localStorage.getItem(key)||'null');}catch{}q('promptInput').value=value?.text||'';attachments=Array.isArray(value?.attachments)?value.attachments:[];composerDraftRevision++;window.resizeWorkspaceComposer?.();renderAttachments();}
  q('promptInput').addEventListener('input',()=>{composerDraftRevision++;saveNativeDraft();});
  window.addEventListener('beforeunload',saveNativeDraft);
  window.addEventListener('authentication-cleared',()=>{nativeDraftContext='';});
  function takeComposerDraft(isCurrent){
    const input=q('promptInput'),value=input.value,revision=composerDraftRevision,storageContext=nativeDraftContext;
    let confirmed=false,restored=false;
    input.value='';window.resizeWorkspaceComposer?.();
    return {
      restore(){
        if(!confirmed&&!restored&&isCurrent()&&composerDraftRevision===revision&&input.value===''){
          input.value=value;restored=true;window.resizeWorkspaceComposer?.();
        }
      },
      confirm(){
        confirmed=true;
        if(window.nativeSession?.active()&&storageContext&&storageContext!==nativeDraftContext){try{const stored=JSON.parse(localStorage.getItem(storageContext)||'null');if(stored?.text===value)localStorage.removeItem(storageContext);}catch{}}
        if(restored&&isCurrent()&&composerDraftRevision===revision&&input.value===value){
          input.value='';window.resizeWorkspaceComposer?.();
        }saveNativeDraft();
      }
    };
  }

  const queueView=document.createElement('details');queueView.className='composer-message-queue';queueView.hidden=true;queueView.setAttribute('aria-label',tr('Queued messages','الرسائل المنتظرة'));attachmentList.before(queueView);
  let queuePolling=false;
  const queueCurrent=(owner,id)=>currentUser?.id===owner&&activeSession?.id===id;
  async function refreshMessageQueue(){
    if(window.nativeSession?.active()){queueCount=0;queueView.hidden=true;return;}
    if(queuePolling)return;
    const owner=currentUser?.id,id=activeSession?.id,revision=++queueRevision;
    if(!id){queueCount=0;queueView.hidden=true;queueView.replaceChildren();queueSignature='';return;}
    queuePolling=true;
    try{
      const data=await api('/api/sessions/'+id+'/queue');
      if(revision!==queueRevision||!queueCurrent(owner,id))return;
      queueCount=(data.items||[]).filter(item=>item.state!=='failed').length;
      const signature=JSON.stringify([owner,id,lang,data]);
      if(signature!==queueSignature){
        const open=queueSignature&&queueView.open;queueView.replaceChildren();queueView.open=Boolean(open);queueView.hidden=!data.items?.length;
        queueView.append(textElement('summary',tr('Queued messages: ','الرسائل المنتظرة: ')+queueCount));
        queueView.append(textElement('small',data.paused?tr('Paused after stop/failure. Resume explicitly when ready.','الطابور متوقف بعد الإيقاف أو الفشل. استأنفه عندما تكون جاهزًا.'):tr('Runs in order after the current task. Pending approvals still block execution.','تُنفّذ بالترتيب بعد المهمة الحالية، مع انتظار الموافقات المطلوبة.')));
        for(const item of data.items||[]){
          const row=textElement('div','','queued-message'),text=textElement('p',item.text);row.append(text);
          const label=item.state==='failed'?tr('Not dispatched; review and resend.','تعذر الإرسال؛ راجع الرسالة وأعد إرسالها.'):item.state==='claimed'?tr('Preparing submission…','جارٍ تجهيز الإرسال…'):tr('Waiting in queue','بانتظار التنفيذ');row.append(textElement('small',label));
          const remove=textElement('button',tr('Remove','إزالة'),'button ghost small');remove.type='button';remove.disabled=item.state==='claimed';
          remove.onclick=async()=>{if(!queueCurrent(owner,id)||remove.disabled)return;remove.disabled=true;try{await api('/api/sessions/'+id+'/queue/'+encodeURIComponent(item.request_id),{method:'DELETE'});queueSignature='';await refreshMessageQueue();}catch(error){if(queueCurrent(owner,id))toast(error.message);}finally{remove.disabled=false;}};row.append(remove);queueView.append(row);
        }
        if(data.paused&&queueCount){const resume=textElement('button',tr('Resume queued messages','استئناف الرسائل المنتظرة'),'button ghost small');resume.type='button';resume.onclick=async()=>{if(!queueCurrent(owner,id))return;resume.disabled=true;try{await api('/api/sessions/'+id+'/queue/dispatch',{method:'POST',body:JSON.stringify({resume:true})});await refreshSessionStatus();}catch(error){if(queueCurrent(owner,id))toast(error.message);}finally{resume.disabled=false;}};queueView.append(resume);}
        queueSignature=signature;
      }
      updateSend();
      if(queueCount&&activeSession.execution_status==='completed')await api('/api/sessions/'+id+'/queue/dispatch',{method:'POST',body:JSON.stringify({resume:false})});
    }catch(error){/* Keep known queue entries on discovery failure; never resend. */}finally{queuePolling=false;}
  }
  window.refreshWorkspaceQueue=refreshMessageQueue;
  window.resetWorkspaceQueue=()=>{queueRevision++;queueCount=0;queueSignature='';queueView.hidden=true;queueView.replaceChildren();};
  window.addEventListener('authentication-cleared',window.resetWorkspaceQueue);
  async function queueFollowup(payload,owner,id){
    if(queuing||!queueCurrent(owner,id))return;queuing=true;updateSend();
    const draft=takeComposerDraft(()=>queueCurrent(owner,id));
    try{
      // Persist only a digest + id for uncertain retries, never message text.
      const bytes=new TextEncoder().encode(JSON.stringify({...payload,request_id:null}));
      const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(value=>value.toString(16).padStart(2,'0')).join('');
      const key='og-queue:'+owner+':'+id;let previous=null;try{previous=JSON.parse(sessionStorage.getItem(key));}catch(error){}
      if(previous?.digest===digest)payload.request_id=previous.request_id;
      try{sessionStorage.setItem(key,JSON.stringify({digest,request_id:payload.request_id}));}catch(error){}
      if(!queueCurrent(owner,id))return;
      await api('/api/sessions/'+id+'/queue',{method:'POST',body:JSON.stringify(payload)});
      if(!queueCurrent(owner,id))return;
      try{sessionStorage.removeItem(key);}catch(error){}
      sentAttachments(payload);draft.confirm();
      submissionStatus.textContent=tr('Added to this conversation’s queue.','أُضيفت إلى طابور هذه المحادثة.');await refreshMessageQueue();
    }catch(error){if(queueCurrent(owner,id)){submissionStatus.textContent=error.message;toast(error.message);}}
    finally{draft.restore();queuing=false;updateSend();}
  }
  const submissionCurrent=p=>currentUser?.id===p.owner&&activeWorkspace?.id===p.workspaceId&&activeSession?.id===p.sessionId;
  let sendingPreview=null;
  function clearSendingPreview(){const preview=sendingPreview;sendingPreview=null;preview?.node.remove();}
  function keepSendingPreview(){
    if(!sendingPreview)return;
    if(currentUser?.id!==sendingPreview.owner||activeWorkspace?.id!==sendingPreview.workspaceId||(sendingPreview.sessionId&&activeSession?.id!==sendingPreview.sessionId)){clearSendingPreview();return;}
    const delivered=[...q('agentFeed').querySelectorAll('.user-bubble[data-message-id]')].some(node=>!sendingPreview.existingIds.has(node.dataset.messageId)&&node.querySelector('.message-content')?.textContent===sendingPreview.text);
    if(delivered){clearSendingPreview();return;}
    if(!sendingPreview.node.isConnected)q('agentFeed').append(sendingPreview.node);
  }
  function showSendingPreview(prompt){
    clearSendingPreview();
    const feed=q('agentFeed');workspaceLatestControl(feed);feed.workspaceFollow.following=true;
    const node=textElement('article','','user-bubble sending-preview');node.dir='auto';
    node.append(textElement('div',prompt,'message-content'));
    const status=textElement('small',tr('Sending…','جارٍ الإرسال…'),'sending-preview-status');status.setAttribute('role','status');node.append(status);
    sendingPreview={node,text:prompt,owner:currentUser.id,workspaceId:activeWorkspace.id,existingIds:new Set([...q('agentFeed').querySelectorAll('[data-message-id]')].map(row=>row.dataset.messageId))};keepSendingPreview();workspaceFollowLatest(feed);
  }
  // Session creation and SSE refreshes rebuild the feed while a POST is pending.
  // Keep one clearly unconfirmed preview without affecting request IDs/retries.
  new MutationObserver(keepSendingPreview).observe(q('agentFeed'),{childList:true});
  window.addEventListener('authentication-cleared',clearSendingPreview);
  async function submitPending(){
    if(!pendingSubmission||sending)return;
    sending=true;updateSend();const pending=pendingSubmission;
    try{
      let result;
      try{result=await api('/api/sessions/'+pending.sessionId+'/submissions/'+pending.request_id);}catch(error){if(error.status!==404)throw error;if(pending.recovered)throw new Error(tr('Submission is not confirmed yet. Check again; no automatic resend occurred.','لم يتأكد الطلب بعد. تحقق مجددًا؛ لم تحدث إعادة إرسال تلقائية.'));}
      if(!result){if(!submissionCurrent(pending))return;result=await api('/api/sessions/'+pending.sessionId+'/messages',{method:'POST',body:JSON.stringify(pending.payload)});}
      if(!submissionCurrent(pending))return;
      sentAttachments(pending.payload);pendingSubmission=null;retrySubmission.hidden=true;submissionStatus.textContent=tr('Submission confirmed.','تم تأكيد الطلب.');
      pending.draft?.confirm();
      await refreshSessionStatus();await refreshMessages();
    }catch(error){if(submissionCurrent(pending)){retrySubmission.hidden=false;submissionStatus.textContent=error.message;toast(error.message);}}
    finally{sending=false;updateSend();}
  }
  window.workspaceSubmissionBlocked=()=>sending||queuing||Boolean(pendingSubmission)||['submitted','waiting_approval'].includes(activeSession?.execution_status);
  q('promptForm').onsubmit=async event=>{
    event.preventDefault();if(sending||queuing||pendingSubmission||!activeWorkspace)return;if(attachments.some(a=>!a.path||a.error)){submissionStatus.textContent=tr('Wait for uploads or remove failed attachments before sending.','انتظر الرفع أو أزل المرفقات التي فشل رفعها قبل الإرسال.');return;}
    const prompt=q('promptInput').value.trim(),provider=q('providerSelect').value,model=q('modelSelect').value,selectedAgent=agent.value,workspaceId=activeWorkspace.id,owner=currentUser?.id;
    if(!prompt)return;if(!runtimeReady||!modelsReady||!provider||!model){toast(tr('Connect a provider and select a model before sending.','اربط مزوّدًا واختر نموذجًا قبل الإرسال.'));return;}
    if(window.nativeSession?.active()){
      if(['submitted','waiting_approval'].includes(activeSession?.execution_status)){
        if(!activeSession?.id)return;
        try{
          await window.nativeSession.replaceRunningModel(activeSession.id,provider,model);
          submissionStatus.textContent=tr('Previous model stopped in this conversation. Submitting to the selected model…','توقف النموذج السابق في هذه المحادثة. جارٍ الإرسال للنموذج المحدد…');
        }catch(error){toast(error.message);submissionStatus.textContent=error.message;return;}
      }
      const draft=takeComposerDraft(()=>currentUser?.id===owner&&activeWorkspace?.id===workspaceId);sending=true;updateSend();
      try{await refreshEntitlement();if(!workAccess)return;if(!activeSession)await createSession({checked:true});
        if(currentUser?.id!==owner||activeWorkspace?.id!==workspaceId||!activeSession)return;
        const sessionId=activeSession.id,nativeFiles=attachments.map(a=>({path:a.path,mime:a.type}));
        await window.nativeSession.send(sessionId,{text:prompt,providerID:provider,modelID:model,agent:selectedAgent,variant:nativeVariant.value||undefined,files:nativeFiles});sentAttachments({attachments:nativeFiles});draft.confirm();
        submissionStatus.textContent=tr('Accepted by native OpenCode','قبله OpenCode الأصلي');await refreshSessionStatus();await refreshMessages();
      }catch(error){toast(error.message);submissionStatus.textContent=error.message;}finally{draft.restore();sending=false;updateSend();}return;
    }
    if(activeSession&&(['submitted','waiting_approval'].includes(activeSession.execution_status)||queueCount)){
      await queueFollowup({request_id:crypto.randomUUID(),text:prompt,provider_id:provider,model_id:model,attachments:attachments.map(item=>({path:item.path})),response_language:lang,...(selectedAgent?{agent_id:selectedAgent}:{})},owner,activeSession.id);return;
    }
    // Synchronous lock precedes entitlement, creation, runtime and network waits.
    const draft=takeComposerDraft(()=>currentUser?.id===owner&&activeWorkspace?.id===workspaceId);
    sending=true;cancelRequested=false;updateSend();submissionStatus.textContent=tr('Submitting…','جارٍ الإرسال…');showSendingPreview(prompt);
    try{
      await refreshEntitlement();if(!workAccess||cancelRequested||activeWorkspace?.id!==workspaceId||currentUser?.id!==owner)return;
      if(!activeSession)await createSession({checked:true});
      if(!activeSession||cancelRequested||activeWorkspace?.id!==workspaceId||currentUser?.id!==owner)return;
      const requestId=crypto.randomUUID(),sessionId=activeSession.id;if(sendingPreview)sendingPreview.sessionId=sessionId;
      const payload={request_id:requestId,text:prompt,provider_id:provider,model_id:model,attachments:attachments.map(a=>({path:a.path})),response_language:lang,...(selectedAgent?{agent_id:selectedAgent}:{})};
      const pending={request_id:requestId,sessionId,workspaceId,owner,payload,draft};pendingSubmission=pending;
      try{sessionStorage.setItem('og-submit:'+owner+':'+sessionId,JSON.stringify({request_id:requestId}));}catch(error){}
      const result=await api('/api/sessions/'+sessionId+'/messages',{method:'POST',body:JSON.stringify(payload)});
      if(!submissionCurrent(pending))return;
      clearSendingPreview();
      sentAttachments(payload);pendingSubmission=null;retrySubmission.hidden=true;activeSession.execution_status=result.status;updateSend();
      draft.confirm();submissionStatus.textContent=tr('Submission confirmed.','تم تأكيد الطلب.');
      await refreshSessionStatus();await refreshMessages();
    }catch(error){
      if(activeWorkspace?.id===workspaceId&&currentUser?.id===owner){
        if(pendingSubmission&&error.status>=400&&error.status<500&&error.status!==408){
          // A definitive rejection did not dispatch this submission. Retain
          // uncertain transport/server outcomes, but let rejected input be fixed.
          try{sessionStorage.removeItem('og-submit:'+owner+':'+pendingSubmission.sessionId);}catch(storageError){}
          pendingSubmission=null;retrySubmission.hidden=true;await refreshSessionStatus().catch(()=>{});
        }
        // A missing response is an uncertain result. Keep the same request ID;
        // checking/retrying this receipt cannot create a second runtime message.
        if(pendingSubmission){retrySubmission.hidden=false;submissionStatus.textContent=tr('Submission result is uncertain. Check or retry this same request.','نتيجة الإرسال غير مؤكدة. تحقق أو أعد هذا الطلب نفسه.');}
        else submissionStatus.textContent=error.message;toast(error.message);
      }
    }finally{draft.restore();clearSendingPreview();sending=false;cancelRequested=false;updateSend();}
  };
  q('stopAgent').onclick=async()=>{
    if(cancelRequested)return;cancelRequested=true;updateSend();
    try{
      if(pendingSubmission){await api('/api/sessions/'+pendingSubmission.sessionId+'/submissions/'+pendingSubmission.request_id);}
      if(activeSession){await api('/api/sessions/'+activeSession.id+'/stop',{method:'POST'});pendingSubmission=null;retrySubmission.hidden=true;await refreshSessionStatus();await refreshMessages();submissionStatus.textContent=tr('Execution cancelled. Completed actions and files are preserved.','أُلغي التنفيذ. تبقى الإجراءات المكتملة والملفات محفوظة.');}
    }catch(error){cancelRequested=false;toast(error.message);}finally{if(!sending)cancelRequested=false;updateSend();}
  };
  async function openRepositoryPicker(onReady=null){
    const dialog=document.createElement('dialog');dialog.className='workspace-repository-dialog';dialog.setAttribute('aria-label',tr('GitHub repository and branch','مستودع وفرع GitHub'));
    const close=btn('repositoryClose','Close','إغلاق',()=>dialog.close()),feedback=textElement('p',tr('Loading authorized repositories…','جارٍ تحميل المستودعات المصرّح بها…'),'api-message');feedback.setAttribute('role','status');
    dialog.append(title('GitHub repository / branch','مستودع GitHub / الفرع'),close,text('p','Your repository stays in GitHub. OpenCode works on a server-side working copy. Commit and push are separate explicit actions.','يبقى المستودع في GitHub. يعمل OpenCode على نسخة عمل بالخادم. Commit وPush إجراءان منفصلان باختيارك.'),feedback);
    document.body.append(dialog);dialog.addEventListener('close',()=>dialog.remove(),{once:true});dialog.showModal();
    try{
      const state=await api('/api/github/status');if(!dialog.open)return;
      if(!state.connected){feedback.textContent=tr('Connect GitHub in Settings first.','اربط GitHub من الإعدادات أولًا.');dialog.append(btn('repositoryConnect','Settings · GitHub','الإعدادات · GitHub',()=>{dialog.close();openConnections('github');}));return;}
      const repos=await api('/api/github/repositories');if(!dialog.open)return;
      const form=document.createElement('form'),repository=document.createElement('select'),branch=document.createElement('select'),name=document.createElement('input');
      repository.id='workspaceRepository';branch.id='workspaceRemoteBranch';name.id='workspaceProjectName';name.maxLength=120;name.value=q('projectName').value;
      function field(en,ar,input){const label=textElement('label',tr(en,ar));label.append(input);form.append(label);}
      field('Repository','المستودع',repository);field('Branch','الفرع',branch);field('Project name','اسم المشروع',name);
      const workingPaths=document.createElement('input');workingPaths.placeholder='src, tests';workingPaths.maxLength=2000;field('Working directories (comma-separated)','مجلدات العمل (مفصولة بفواصل)',workingPaths);
      const fullCopy=document.createElement('input');fullCopy.type='checkbox';fullCopy.id='repositoryFullCopy';field('I explicitly want the complete working copy','أوافق صراحةً على استيراد نسخة العمل كاملة',fullCopy);
      form.append(textElement('p',tr('This list shows repositories accessible to your connected GitHub account. Only the repository and branch you submit are imported; listing another repository does not import it.','تعرض القائمة المستودعات المتاحة لحساب GitHub المتصل. يُستورد المستودع والفرع اللذان تختارهما فقط؛ ظهور مستودع آخر لا يعني استيراده.')));
      form.append(textElement('p',tr('Choose working directories, or explicitly allow a complete shallow copy. Selected directories include root files; include dependencies and tests you need. Git history/blobs still count toward the working-copy limit. No files or remote branches are deleted.','اختر مجلدات العمل، أو وافق صراحةً على نسخة كاملة بتاريخ مختصر. المجلدات المختارة تشمل ملفات الجذر؛ اختر التبعيات والفحوص اللازمة. بيانات Git تحتسب ضمن حد نسخة العمل. لا تُحذف ملفات أو فروع بعيدة.')));
      name.required=repository.required=branch.required=true;branch.disabled=true;repository.add(new Option(tr('Choose repository','اختر مستودعًا'),''));
      for(const r of repos)repository.add(new Option(r.full_name+(r.private?tr(' · Private',' · خاص'):''),r.full_name));
      const submit=textElement('button',tr('Create GitHub-backed project','إنشاء مشروع مرتبط بـGitHub'),'button');submit.type='submit';submit.disabled=true;form.append(submit);dialog.append(form);feedback.textContent='';let revision=0;
      repository.onchange=async()=>{
        const selected=repository.value,stamp=++revision;branch.replaceChildren();branch.disabled=submit.disabled=true;if(!selected)return;
        feedback.textContent=tr('Loading branches…','جارٍ تحميل الفروع…');
        try{const branches=await api('/api/github/branches?repository='+encodeURIComponent(selected));if(!dialog.open||stamp!==revision)return;for(const b of branches)branch.add(new Option(b.name,b.name));const preferred=repos.find(r=>r.full_name===selected)?.default_branch;if(branches.some(b=>b.name===preferred))branch.value=preferred;name.value=name.value||selected.split('/').pop();branch.disabled=false;submit.disabled=!branches.length;feedback.textContent='';}catch(error){if(stamp===revision)feedback.textContent=error.message;}
      };
      form.onsubmit=async event=>{event.preventDefault();if(!form.reportValidity()||submit.disabled)return;const paths=workingPaths.value.split(',').map(path=>path.trim()).filter(Boolean);if(!paths.length&&!fullCopy.checked){feedback.textContent=tr('Choose working directories or explicitly allow the complete copy.','اختر مجلدات العمل أو وافق صراحةً على النسخة الكاملة.');return;}submit.disabled=true;feedback.textContent=tr('Preparing a shallow working copy…','جارٍ تجهيز نسخة عمل بتاريخ مختصر…');try{const result=await api('/api/projects',{method:'POST',body:JSON.stringify({source_type:'github',repository:repository.value,branch:branch.value,project_name:name.value,working_paths:paths})});if(!dialog.open)return;dialog.close();await openWorkspace(result.project,result.workspace);if(typeof onReady==='function')await onReady(result.project,result.workspace);}catch(error){if(dialog.open)feedback.textContent=error.message;else toast(error.message);}finally{submit.disabled=false;}};
    }catch(error){if(dialog.open)feedback.textContent=error.message;}
  }
  window.openGithubProject=openRepositoryPicker;
  const detailLoads=new Map();
  loadWorkspaceDetails=function(){
    const workspace=activeWorkspace;if(!workspace)return;
    if(Date.now()-(detailLoads.get(workspace.id)||0)<10000)return;
    detailLoads.set(workspace.id,Date.now());
    loadStorage().catch(()=>{});
    loadFiles().catch(()=>{});
    loadProjectGroups().catch(()=>{});
    refreshSessions().catch(error=>toast(error.message));
    refreshGit().catch(error=>toast(error.message));
  };
  let workspaceLanguage=lang;const workspacePrefs=applyPrefs;applyPrefs=()=>{workspacePrefs();if(workspaceLanguage!==lang&&activeSession){updateProjectIdentity();renderRuntimeSessions(sessionRows);refreshMessages().catch(()=>{});loadApprovals().catch(()=>{});}workspaceLanguage=lang;};
  createWorkspaceSession=createSession;
  if(activeProject){q('workspaceRepo').textContent=activeProject.name;q('workspaceBranch').textContent=activeProject.branch||'—';}
  }
  const refundPolicy=text('p','Accepted payments cannot be cancelled or refunded.','المدفوعات المقبولة غير قابلة للإلغاء أو الاسترداد.','refund-policy');refundPolicy.id='subscriptionRefundPolicy';document.querySelector('#landing .pricing').append(refundPolicy);
  const prefs=applyPrefs;applyPrefs=()=>{prefs();for(const [node,en,ar] of texts){if(!node.firstChild)node.textContent=tr(en,ar);else if(node.firstChild.nodeType===3)node.firstChild.textContent=tr(en,ar);}q('homeSessionSearch').placeholder=tr('Search recent sessions…','ابحث في الجلسات الأخيرة…');renderEntitlement();renderStorage();if(q('accountLanguage'))q('accountLanguage').value=lang;if(q('accountAppearance'))q('accountAppearance').value=dark?'dark':'light';document.querySelectorAll('[data-account-en]').forEach(node=>node.textContent=lang==='ar'?node.dataset.accountAr:node.dataset.accountEn);};
  // The wordmark is a landing-page navigation control for every role.
  const brand=document.querySelector('#app-header .header-brand');if(brand){brand.setAttribute('role','button');brand.tabIndex=0;brand.setAttribute('aria-label','OpenCode Gateway — Home');brand.style.cursor='pointer';brand.onclick=()=>page('landing');brand.onkeydown=event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();page('landing');}};}
  const paymentOrders=document.createElement('section');paymentOrders.id='clientPaymentOrders';document.querySelector('[data-client-panel=billing]').append(paymentOrders);
  const adminOrders=document.createElement('section');adminOrders.id='adminPaymentOrders';document.querySelector('[data-admin-panel=billing]').append(adminOrders);
  let paymentLoadCounter=0,paymentArchived=false;
  async function loadPaymentOrders(platform=false){
    const host=platform?adminOrders:paymentOrders;const token=String(++paymentLoadCounter);host.dataset.paymentLoad=token;
    host.replaceChildren(title(platform?'Payment review':'Subscription and payment history',platform?'مراجعة المدفوعات':'سجل الاشتراكات والمدفوعات'));
    if(!platform){const tabs=textElement('nav','','session-filters');for(const [archived,en,ar] of [[false,'Current','الحالية'],[true,'Archived','المؤرشفة']]){const tab=btn('payments-'+(archived?'archived':'current'),en,ar,()=>{paymentArchived=archived;loadPaymentOrders();});tab.setAttribute('aria-pressed',String(paymentArchived===archived));tabs.append(tab);}host.append(tabs);}
    const list=await api(platform?'/api/billing/admin/orders':'/api/billing/orders?archived='+paymentArchived);
    if(host.dataset.paymentLoad!==token)return;
    const ACTION_ICONS={view:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2.06 12.35a1 1 0 0 1 0-.7C3.42 8.1 7.22 5 12 5s8.58 3.1 9.94 6.65a1 1 0 0 1 0 .7C20.58 15.9 16.78 19 12 19s-8.58-3.1-9.94-6.65Z"/><circle cx="12" cy="12" r="3"/></svg>',resume:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>',cancel:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>',remove:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/></svg>',archive:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3h18v4H3zM5 7v14h14V7M9 12h6"/></svg>',restore:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3h18v4H3zM5 7v14h14V7M12 17v-7m-3 3 3-3 3 3"/></svg>',confirm:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',reject:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="m15 9-6 6M9 9l6 6"/></svg>'};
    const act=(id,icon,label,action)=>{const b=textElement('button','','icon-btn');b.id=id;b.type='button';b.title=label;b.setAttribute('aria-label',label);b.innerHTML=icon;b.onclick=async()=>{b.disabled=true;try{await action();}catch(error){toast(error.message)}finally{b.disabled=false;}};return b;};
    for(const order of list){
      const row=textElement('div','','manage-row');
      const statuses={awaiting_payment:tr('Awaiting payment','بانتظار الدفع'),pending_review:tr('Awaiting acceptance','بانتظار القبول'),paid:tr('Accepted payment','دفع مقبول'),sandbox_paid:tr('Test payment accepted','دفع تجريبي مقبول'),failed:tr('Payment failed','فشل الدفع'),cancelled:tr('Request cancelled','طلب ملغى'),rejected:tr('Payment rejected','دفع مرفوض')};
      row.append(textElement('strong',order.plan_name+' · '+order.currency+' '+(order.amount_cents/100).toFixed(2)),textElement('span',(order.email?order.email+' · ':'')+(statuses[order.status]||tr('Payment being checked','جارٍ التحقق من الدفع'))));
      if(order.created_at)row.append(textElement('small',tr('Requested: ','تاريخ الطلب: ')+new Date(order.created_at).toLocaleString(lang==='ar'?'ar-u-nu-latn':'en')));
      if(order.paid_at)row.append(textElement('small',tr('Accepted: ','تاريخ القبول: ')+new Date(order.paid_at).toLocaleString(lang==='ar'?'ar-u-nu-latn':'en')));
      if(order.payment_reference)row.append(textElement('small',order.payment_reference));
      if(order.sender_name)row.append(textElement('small',tr('Sender: ','المرسل: ')+order.sender_name));
      if(order.sender_email)row.append(textElement('small',order.sender_email));
      if(order.sender_bank)row.append(textElement('small',tr('From bank: ','البنك المرسل: ')+order.sender_bank));
      if(order.sender_account)row.append(textElement('small',tr('From account: ','الحساب المرسل: ')+order.sender_account));
      if(order.payer_name)row.append(textElement('small',tr('Payer: ','الدافع: ')+order.payer_name));
      if(order.transfer_date)row.append(textElement('small',order.transfer_date));
      if(order.amount_sent_cents)row.append(textElement('small',tr('Sent: ','المُرسل: ')+(order.amount_sent_cents/100).toFixed(2)+' '+order.currency));
      if(order.billing_note)row.append(textElement('small',order.billing_note));
      if(order.reject_reason)row.append(textElement('small',tr('Rejected: ','مرفوض: ')+order.reject_reason));
      const actions=textElement('div','','manage-actions');
      if(order.has_receipt){const rl=textElement('a','','icon-btn');rl.href='/api/billing/orders/'+order.id+'/receipt';rl.target='_blank';rl.rel='noopener noreferrer';rl.title=tr('View receipt','عرض الإيصال');rl.setAttribute('aria-label',rl.title);rl.innerHTML=ACTION_ICONS.view;actions.append(rl);}
      if(platform&&order.status==='pending_review'){
        actions.append(act('confirm-'+order.id,ACTION_ICONS.confirm,tr('Verify receipt / Activate','تأكيد الاستلام / التفعيل'),async()=>{const reference=await window.requestInput(tr('After verifying the transfer was received, enter its receipt reference.','بعد التحقق من استلام التحويل، أدخل مرجع الاستلام.'));if(!reference)return;await api('/api/billing/admin/orders/'+order.id+'/confirm',{method:'POST',body:JSON.stringify({reference})});await loadPaymentOrders(true);}));
        actions.append(act('reject-'+order.id,ACTION_ICONS.reject,tr('Reject','رفض'),async()=>{const reason=await window.requestInput(tr('Rejection reason','سبب الرفض'));if(!reason?.trim())return;await api('/api/billing/admin/orders/'+order.id+'/reject',{method:'POST',body:JSON.stringify({reason:reason.trim()})});await loadPaymentOrders(true);}));
      }
      if(!platform&&order.provider_order_id&&!['paid','sandbox_paid'].includes(order.status))actions.append(act('capture-'+order.id,ACTION_ICONS.confirm,tr('Confirm PayPal payment','تأكيد دفع PayPal'),async()=>{const verified=await api('/api/billing/orders/'+order.id+'/paypal/capture',{method:'POST'});await refreshCustomerBilling();toast(verified.status==='sandbox_paid'?tr('Sandbox payment verified. Real subscription unchanged.','تم التحقق من الدفع التجريبي دون تفعيل اشتراك حقيقي.'):tr('Payment verified. Subscription active.','تم التحقق من الدفع وتفعيل الاشتراك.'));}));
      if(!platform&&order.status==='awaiting_payment')actions.append(act('resume-'+order.id,ACTION_ICONS.resume,tr('Payment instructions','تعليمات الدفع'),()=>beginCheckout(order.plan_id,order.method_id)));
      if(!platform&&['awaiting_payment','pending_review','failed','rejected'].includes(order.status)&&!order.provider_capture_id&&!order.paid_at){
        const cancel=act('cancel-'+order.id,ACTION_ICONS.cancel,tr('Cancel unpaid request','إلغاء الطلب غير المقبول'),async()=>{if(!await window.confirmAction(tr('Cancel this request before payment acceptance?','إلغاء الطلب قبل قبول الدفع؟')))return;await api('/api/billing/orders/'+order.id+'/cancel',{method:'POST'});await loadPaymentOrders();});
        if(order.provider_order_id){cancel.disabled=true;cancel.hidden=true;api('/api/billing/orders/'+order.id+'/cancellation-status').then(state=>{if(host.dataset.paymentLoad===token){cancel.hidden=!state.can_cancel;cancel.disabled=!state.can_cancel;}}).catch(()=>{});}actions.append(cancel);
      }
      if(!platform&&!window.reactivationAccount&&!order.provider_order_id&&['failed','cancelled','rejected'].includes(order.status))actions.append(act('remove-'+order.id,ACTION_ICONS.remove,tr('Remove from history','حذف من السجل'),async()=>{if(!await window.confirmAction(tr('Remove this payment from your history?','حذف هذا الدفع من سجلك؟')))return;await api('/api/billing/orders/'+order.id,{method:'DELETE'});await loadPaymentOrders();}));
      if(!platform)actions.append(act('archive-payment-'+order.id,order.archived_at?ACTION_ICONS.restore:ACTION_ICONS.archive,order.archived_at?tr('Restore to current history','استعادة إلى السجل الحالي'):tr('Archive payment record','أرشفة العملية'),async()=>{await api('/api/billing/orders/'+order.id+'/archive',{method:'POST',body:JSON.stringify({archived:!order.archived_at})});await loadPaymentOrders();}));
      if(actions.children.length)row.append(actions);
      host.append(row);
    }
    if(!list.length)host.append(text('p',platform?tr('No payments to review','لا توجد مدفوعات للمراجعة'):tr('No payments yet. Successful payments stay here as records.','لا توجد مدفوعات بعد. تبقى المدفوعات الناجحة هنا كسجلات.')));
  }
  window.loadReactivationOrders=()=>loadPaymentOrders();
  async function refreshCustomerBilling(){
    if(window.reactivationAccount)return window.openReactivation();
    await oldClientView('billing');await loadPaymentOrders();
  }
  async function beginCheckout(planId,methodId){
    const [plans]=await Promise.all([api('/api/plans',{cache:'no-store'})]);
    const plan=plans.find(p=>p.id===planId);if(!plan)return toast(tr('Plan unavailable','الخطة غير متاحة'));
    const methods=await api('/api/billing/available-methods?plan_id='+encodeURIComponent(planId)+'&include_unavailable=true');
    if(!methods.some(m=>m.details.checkout_mode==='paypal'))methods.push({id:'unavailable-paypal',kind:'paypal',label:'PayPal',available:false,details:{checkout_mode:'paypal'}});
    const reasonCopy={provider_not_connected:tr('Provider is not connected','المزود غير متصل'),processor_not_connected:tr('Payment processor is not connected','معالج الدفع غير متصل'),details_not_configured:tr('Receiving details are not configured','بيانات الاستلام غير مهيأة')};const PAY_ICONS={paypal:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M7 5.8h5.9c2 0 3.3 1.2 3.1 3-.3 2.3-2.1 3.8-4.4 3.8H9.4L8.4 18h-2.6l1-6.4H5L7 5.8Z"/><path d="m12.6 8.6 1.4 1.2c1.8-1.2 4-.3 4.5 1.9.5 2.3-1.2 4.2-3.4 4.2h-1.7l-.5 3.1h-2.4l1.2-7.4h1.6"/></svg>',googlepay:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12a7 7 0 1 1-2.1-4.9"/><path d="M18.2 7.5H11.6"/><path d="M19.6 8.2 17 11.2"/></svg>',binance:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M12 3.5 19.5 7.8v8.4L12 20.5l-7.5-4.3V7.8L12 3.5Z"/><path d="M12 8.8 15 10.5v3L12 15.2 9 13.5v-3l3-1.7Z"/><path d="M9.5 8.5h5"/></svg>',bank:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18M3 10h18M5 10l7-6 7 6M6.5 14h1.8v3.5H6.5Zm4.6 0h1.8v3.5h-1.8Zm4.6 0h1.8v3.5h-1.8Z"/></svg>',wallet:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v1H7a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-6a1 1 0 0 0-1-1h-4m-6-5h6"/></svg>'};const payIcon=kind=>{const s=document.createElement('span');s.className='pay-icon';s.setAttribute('aria-hidden','true');s.innerHTML=PAY_ICONS[kind]||PAY_ICONS.wallet;return s;};
    const dialog=document.createElement('dialog');dialog.className='workspace-repository-dialog checkout-dialog';dialog.setAttribute('aria-label',tr('Subscription checkout','دفع الاشتراك'));
    dialog.append(title('Subscribe / Payment','الاشتراك / الدفع'),btn('checkoutClose','Close','إغلاق',()=>dialog.close()));
    const choices=textElement('div','','checkout-plans');for(const p of plans.filter(p=>p.active!==false)){
      const choiceLabel=(window.planDisplayName?window.planDisplayName(p):p.name)+' · '+(window.planDisplayPrice?window.planDisplayPrice(p):(p.currency+' '+(p.price_cents/100).toFixed(2)))+' · '+(window.planDisplayTerm?window.planDisplayTerm(p):(p.duration_days+' days'));const choice=btn('checkoutPlan-'+p.id,choiceLabel,choiceLabel,()=>{dialog.close();beginCheckout(p.id);});choice.setAttribute('aria-pressed',String(p.id===planId));choices.append(choice);
    }dialog.append(choices);
    const summary=textElement('section','','checkout-summary');summary.append(textElement('strong',window.planDisplayName?window.planDisplayName(plan):plan.name),text('span','Total','الإجمالي'),textElement('b',window.planDisplayPrice?window.planDisplayPrice(plan):(plan.currency+' '+(plan.price_cents/100).toFixed(2))),textElement('span',window.planDisplayTerm?window.planDisplayTerm(plan):(plan.duration_days+' days')));dialog.append(summary);
    dialog.append(text('p','Choose a payment method. Your access activates after receipt is verified.','اختر وسيلة دفع. يُفعّل الوصول بعد التحقق من الاستلام.','checkout-lead'));
    const select=document.createElement('select');select.id='checkoutMethod';select.hidden=true;
    const noteWrap=text('label','Billing note (optional)','ملاحظة دفع (اختياري)');noteWrap.htmlFor='checkoutNote';const noteInput=document.createElement('input');noteInput.id='checkoutNote';noteInput.maxLength=500;noteInput.autocomplete='off';noteWrap.append(noteInput);
    const rows=textElement('fieldset','','checkout-methods');rows.append(text('legend','Payment method','وسيلة الدفع'));
    for(const method of methods){select.add(new Option(method.label,method.id));const label=textElement('label','','checkout-method');const radio=document.createElement('input');radio.type='radio';radio.name='payment-method';radio.value=method.id;radio.checked=method.id===(methodId||methods[0]?.id);const cardName=textElement('strong',method.label);cardName.prepend(payIcon(method.kind));const baseSub=method.details.checkout_mode==='paypal'?tr('PayPal · official checkout · card / PayPal account','PayPal · دفع رسمي · بطاقة / حساب PayPal'):method.details.checkout_mode==='link'?(method.kind==='googlepay'?tr('Google Pay · hosted by your payment processor','Google Pay · عبر مزوّد الدفع'):tr('Secure hosted checkout','دفع عبر صفحة مزود الدفع')):(method.kind==='binance'?tr('Binance Pay · USDT transfer','Binance Pay · تحويل USDT'):(method.kind==='bank'?tr('Bank transfer','تحويل بنكي'):tr('Wallet transfer','تحويل محفظة')));const copy=textElement('span');copy.append(cardName,textElement('small',method.available?baseSub:tr('Not connected','غير متصل')+' · '+(reasonCopy[method.available_reason]||'')));label.append(radio,copy);rows.append(label);radio.onchange=()=>{select.value=radio.value;};}
    if(methodId&&methods.some(m=>m.id===methodId))select.value=methodId;
    const body=textElement('section','','checkout-receipt');body.setAttribute('aria-live','polite');
    const showError=error=>{let status=body.querySelector('.checkout-error');if(!status){status=textElement('p','','api-message show error checkout-error');status.setAttribute('role','alert');body.prepend(status);}status.textContent=error.message||String(error);};
    const renderProviderForm=method=>{
      const dl=document.createElement('dl');dl.className='checkout-details';
      for(const [label,value] of [[tr('Plan','الخطة'),plan.name],[tr('Amount','المبلغ'),(plan.price_cents/100).toFixed(2)],[tr('Currency','العملة'),plan.currency]]){dl.append(textElement('dt',label),textElement('dd',String(value)));}
      body.replaceChildren(dl);const phead=textElement('strong',method.label);phead.prepend(payIcon(method.kind));body.prepend(phead);
      const pfield=(labelText,id,type,extra)=>{const wrap=text('label',labelText,labelText);wrap.htmlFor=id;const inp=document.createElement('input');inp.id=id;inp.type=type;inp.required=true;Object.assign(inp,extra||{});wrap.append(inp);body.append(wrap);return inp;};
      const payerName=pfield(tr('Your full name','اسمك الكامل'),'payerName','text',{maxLength:150,autocomplete:'name',value:(currentUser||window.reactivationAccount)?.username||''});
      const payerEmail=pfield(tr('Your email','بريدك الإلكتروني'),'payerEmail','email',{maxLength:254,autocomplete:'email',value:(currentUser||window.reactivationAccount)?.email||''});
      const locationField=(en,ar,id)=>{const wrap=text('label',en,ar),control=document.createElement('select');control.id=id;wrap.htmlFor=id;control.add(new Option(tr('Select','اختر'),''));wrap.append(control);body.append(wrap);return control;};
      const payerCountry=locationField('Country','الدولة','payerCountry'),payerRegion=locationField('Region / governorate','المحافظة / المنطقة','payerRegion'),payerCity=locationField('City / district','المدينة / المديرية','payerCity');payerCountry.required=true;
      let locationRevision=0;
      const fillLocation=(control,items,selectedName,localize=false)=>{control.replaceChildren(new Option(tr('Select','اختر'),''));for(const item of items){let label=item.name;if(localize&&item.code){try{label=new Intl.DisplayNames([lang],{type:'region'}).of(item.code)||item.name;}catch(error){}}const option=new Option(label,String(item.id));option.dataset.name=item.name;control.add(option);if(item.name===selectedName)control.value=String(item.id);}control.disabled=!items.length;control.required=items.length>0;control.parentElement.hidden=!items.length;};
      const loadChildren=async(prefill=false)=>{const revision=++locationRevision;go2.disabled=true;payerRegion.replaceChildren(new Option(tr('Select','اختر'),''));payerCity.replaceChildren(new Option(tr('Select','اختر'),''));payerRegion.disabled=payerCity.disabled=true;payerRegion.required=payerCity.required=false;
        try{const account=currentUser||window.reactivationAccount;if(!payerCountry.value)return;const regions=await api('/api/locations/countries/'+payerCountry.value+'/regions');if(revision!==locationRevision||!body.contains(payerCountry))return;fillLocation(payerRegion,regions,prefill?account?.region:null);if(payerRegion.value){const cities=await api('/api/locations/regions/'+payerRegion.value+'/cities');if(revision===locationRevision&&body.contains(payerCountry))fillLocation(payerCity,cities,prefill?account?.city:null);}else payerCity.parentElement.hidden=true;
        }catch(error){showError(error);}finally{if(revision===locationRevision)go2.disabled=false;}};
      payerCountry.onchange=()=>loadChildren();payerRegion.onchange=async()=>{const revision=++locationRevision;go2.disabled=true;payerCity.replaceChildren(new Option(tr('Select','اختر'),''));payerCity.disabled=true;payerCity.required=false;try{if(payerRegion.value){const cities=await api('/api/locations/regions/'+payerRegion.value+'/cities');if(revision===locationRevision&&body.contains(payerCountry))fillLocation(payerCity,cities,null);}else payerCity.parentElement.hidden=true;}catch(error){showError(error);}finally{if(revision===locationRevision)go2.disabled=false;}};
      const go2=textElement('button',method.kind==='googlepay'?tr('Pay with Google Pay','الدفع عبر Google Pay'):method.kind==='paypal'?tr('Pay with PayPal','الدفع عبر PayPal'):tr('Pay directly through bank / card','الدفع المباشر عبر البنك / البطاقة'),'button checkout-hosted-link');go2.type='button';
      if(!method.available)body.append(text('p','This payment method is currently unavailable. Choose another method or contact support.','وسيلة الدفع هذه غير متاحة حاليًا. اختر وسيلة أخرى أو تواصل مع الدعم.','checkout-lead'));
      body.append(go2);go2.disabled=true;
      (async()=>{try{const countries=await api('/api/locations/countries');if(!body.contains(payerCountry))return;fillLocation(payerCountry,countries,(currentUser||window.reactivationAccount)?.country,true);payerCountry.parentElement.hidden=false;payerCountry.required=true;if(!countries.length)throw new Error(tr('No countries are configured. Contact administration.','لا توجد دول مهيأة. تواصل مع الإدارة.'));await loadChildren(true);}catch(error){showError(error);go2.disabled=true;}})();
      let latestOrder=null;
      const validPayer=()=>!go2.disabled&&[payerName,payerEmail,payerCountry,payerRegion,payerCity].every(field=>!field.required||field.reportValidity());
      const createProviderOrder=async()=>{body.querySelector('.checkout-error')?.remove();if(!method.available)throw new Error(tr('Could not connect to PayPal. No payment was made.','تعذر الربط مع PayPal. لم يتم خصم أي مبلغ.'));const result=await api('/api/billing/checkout',{method:'POST',body:JSON.stringify({plan_id:planId,method_id:method.id,billing_note:noteInput.value.trim(),payer_name:payerName.value.trim(),payer_email:payerEmail.value.trim(),country_id:Number(payerCountry.value),region_id:payerRegion.value?Number(payerRegion.value):null,city_id:payerCity.value?Number(payerCity.value):null})});latestOrder=result.order;confirmButton.hidden=!latestOrder?.provider_order_id;return result;};
      const confirmOrder=async(providerId)=>{if(!latestOrder?.id||providerId&&providerId!==latestOrder.provider_order_id)throw new Error(tr('Payment order does not match. Refresh checkout.','طلب الدفع غير مطابق. أعد فتح الدفع.'));const verified=await api('/api/billing/orders/'+latestOrder.id+'/paypal/capture',{method:'POST'});dialog.close();await refreshCustomerBilling();toast(verified.status==='sandbox_paid'?tr('Sandbox payment verified. Real subscription unchanged.','تم التحقق من الدفع التجريبي دون تفعيل اشتراك حقيقي.'):tr('Payment verified. Subscription active.','تم التحقق من الدفع وتفعيل الاشتراك.'));};
      const confirmButton=btn('confirmPayPalPayment','Confirm PayPal payment','تأكيد دفع PayPal',()=>confirmOrder());confirmButton.hidden=true;body.append(confirmButton);
      go2.onclick=async()=>{if(!validPayer())return;if(!method.available){showError(new Error(method.kind==='paypal'?tr('Could not connect to PayPal. No payment was made.','تعذر الربط مع PayPal. لم يتم خصم أي مبلغ.'):tr('Could not connect to the bank or payment processor. No payment was made.','تعذر الربط مع البنك أو مزوّد الدفع. لم يتم خصم أي مبلغ.')));return;}go2.disabled=true;try{const result=await createProviderOrder();if(result.automatic_processing&&result.approval_url)window.location.assign(result.approval_url);else if(result.payment_url){const link=textElement('a',tr('Open the payment provider page','فتح صفحة مزود الدفع'),'button checkout-hosted-link');link.href=result.payment_url;link.target='_blank';link.rel='noopener noreferrer';body.append(link);}}catch(error){showError(error);}finally{go2.disabled=false;}};
      if(method.details.checkout_mode==='paypal'){
        const host=textElement('div');host.id='paypalButtonHost';host.setAttribute('aria-label','PayPal');body.append(host);
        (async()=>{try{const status=await api('/api/billing/paypal/status');if(!body.contains(host))return;if(!status.client_id){host.append(text('p','The official PayPal form could not load because payment setup is incomplete.','تعذر تحميل نموذج PayPal الرسمي لأن إعداد الدفع غير مكتمل.','checkout-lead'));return;}
          const pp=await new Promise((resolve,reject)=>{if(window.paypal)return resolve(window.paypal);const script=document.createElement('script');script.src='https://www.paypal.com/sdk/js?client-id='+encodeURIComponent(status.client_id)+'&currency='+encodeURIComponent(plan.currency)+'&intent=capture&components=buttons&enable-funding=card';script.onload=()=>window.paypal?resolve(window.paypal):reject(new Error('paypal-sdk'));script.onerror=()=>reject(new Error('paypal-sdk'));document.head.append(script);});if(!body.contains(host))return;
          await pp.Buttons({style:{layout:'vertical'},onClick:(data,actions)=>{if(!validPayer())return actions.reject();if(!method.available||!status.configured){showError(new Error(tr('Could not connect to PayPal. No payment was made.','تعذر الربط مع PayPal. لم يتم خصم أي مبلغ.')));return actions.reject();}return actions.resolve();},createOrder:async()=>{try{const result=await createProviderOrder();if(!result.automatic_processing||!result.order?.provider_order_id)throw new Error(tr('PayPal order is unavailable.','طلب PayPal غير متاح.'));return result.order.provider_order_id;}catch(error){showError(error);throw error;}},onApprove:async data=>{try{await confirmOrder(data.orderID);}catch(error){showError(error);}},onCancel:async()=>{if(!latestOrder?.id)return;try{await api('/api/billing/orders/'+latestOrder.id+'/cancel',{method:'POST'});await loadPaymentOrders();toast(tr('Unaccepted payment request cancelled.','تم إلغاء طلب الدفع قبل قبوله.'));}catch(error){showError(error);}},onError:()=>{if(!body.querySelector('.checkout-error'))showError(new Error(tr('PayPal could not complete this payment. No subscription activated.','تعذر إتمام الدفع عبر PayPal دون تفعيل الاشتراك.')));}}).render(host);go2.hidden=true;
        }catch(error){host.replaceChildren();go2.hidden=false;body.append(text('p','PayPal buttons could not load. Continue through the official payment page.','تعذر تحميل أزرار PayPal. يمكنك المتابعة إلى صفحة الدفع الرسمية.','checkout-lead'));}})();
      }
    };
    const renderManualForm=method=>{
      const mhead=textElement('strong',method.label);mhead.prepend(payIcon(method.kind));body.replaceChildren(mhead);
      if(method.kind==='bank')body.append(text('p','Transfer to the account holder below, then upload your proof of transfer.','حوّل إلى صاحب الحساب أدناه، ثم ارفع إثبات التحويل.','checkout-lead'));
      const labels={account_name:tr('Recipient','المستفيد'),account_reference:tr('Recipient account / address','حساب المستفيد / العنوان'),iban:tr('IBAN','الآيبان'),branch:tr('Branch','الفرع'),bank_name:tr('Bank','البنك'),currency:tr('Currency','العملة'),network:tr('Network','الشبكة'),instructions:tr('Instructions','التعليمات')};
      if(method.kind==='binance'){labels.account_reference=tr('Binance wallet address or username','عنوان محفظة Binance أو اسم المستخدم');const bAmt=tr('Amount: ','المبلغ: ')+'$'+((plan.price_cents/100).toFixed(2))+' USD',bUsdt=tr('USDT to pay (fixed 1 USD = 1 USDT parity): ','مبلغ USDT المطلوب (تعادل ثابت 1 دولار = 1 USDT): ')+((plan.price_cents/100).toFixed(2))+' USDT',bSend=tr('Send USDT from your Binance account to the address above, then attach the transfer screenshot below.','أرسل USDT من حساب Binance الخاص بك إلى العنوان أعلاه، ثم أرفق لقطة شاشة للتحويل أدناه.');body.append(text('p',bAmt,bAmt),text('p',bUsdt,bUsdt),text('p',bSend,bSend,'checkout-lead'));}
      const details=document.createElement('dl');details.className='checkout-details';for(const [key,label] of Object.entries(labels)){const value=method.details[key];if(value)details.append(textElement('dt',label),textElement('dd',value));}body.append(details);
      const form=document.createElement('form');form.dataset.paymentForm='customer';
      const mkField=(labelText,id,type,extra)=>{const wrap=text('label',labelText,labelText);wrap.htmlFor=id;const inp=document.createElement('input');inp.id=id;inp.type=type;inp.required=true;Object.assign(inp,extra||{});wrap.append(inp);form.append(wrap);return inp;};
      const sender=mkField(tr('Sender name (account holder)','اسم المُرسل (صاحب الحساب)'),'paymentSender','text',{maxLength:150,autocomplete:'off'});
      const senderEmail=mkField(tr('Sender email','بريد المُرسل'),'paymentSenderEmail','email',{maxLength:254,autocomplete:'off'});
      const senderBank=mkField(tr('Sender bank name','اسم بنك المُرسل'),'paymentSenderBank','text',{maxLength:150,autocomplete:'off'});
      const senderAccount=mkField(tr('Sender account number / IBAN','رقم حساب المُرسل / الآيبان'),'paymentSenderAccount','text',{maxLength:200,autocomplete:'off'});
      const reference=mkField(tr('Transaction / reference number','رقم العملية / المرجع'),'paymentReference','text',{minLength:3,maxLength:200,autocomplete:'off'});
      const tdate=mkField(tr('Transfer date','تاريخ التحويل'),'paymentDate','date',{});
      const sent=mkField(tr('Amount sent','المبلغ المُرسل'),'paymentSent','number',{min:'0.01',step:'0.01'});
      const fileWrap=text('label','Receipt screenshot (PNG, JPEG, WebP or PDF, up to 5 MB)','صورة الإيصال (PNG أو JPEG أو WebP أو PDF حتى 5 ميجابايت)');fileWrap.htmlFor='paymentReceipt';const receipt=document.createElement('input');receipt.id='paymentReceipt';receipt.type='file';receipt.required=true;receipt.accept='.png,.jpg,.jpeg,.webp,.pdf';fileWrap.append(receipt);form.append(fileWrap);
      const send=text('button','Submit payment for review','إرسال الدفع للمراجعة','button');send.type='submit';form.append(send);
      form.onsubmit=async event=>{event.preventDefault();send.disabled=true;try{
        if(!receipt.files.length)throw new Error(tr('Attach the receipt screenshot first.','أرفق صورة الإيصال أولاً.'));
        const result=await api('/api/billing/checkout',{method:'POST',body:JSON.stringify({plan_id:planId,method_id:method.id,billing_note:noteInput.value.trim()})});
        const fd=new FormData();fd.append('file',receipt.files[0]);
        const up=await fetch('/api/billing/orders/'+result.order.id+'/receipt',{method:'POST',body:fd,credentials:'same-origin'});
        if(!up.ok)throw new Error((await up.json().catch(()=>({}))).detail||'Receipt upload failed');
        await api('/api/billing/orders/'+result.order.id+'/reference',{method:'PUT',body:JSON.stringify({reference:reference.value,sender_name:sender.value,sender_email:senderEmail.value,sender_bank:senderBank.value,sender_account:senderAccount.value,transfer_date:tdate.value,amount_sent_cents:Math.round(Number(sent.value)*100)})});
        dialog.close();await refreshCustomerBilling();
        toast(tr('Payment submitted. Status: pending verification.','أُرسل الدفع. الحالة: بانتظار التحقق.'));
      }catch(error){showError(error);}finally{send.disabled=false;}};
      body.append(form);
    };
    const go=btn('createPaymentOrder','Next step','الخطوة التالية',async()=>{
      const method=methods.find(m=>m.id===select.value);
      if(!method){toast(tr('Choose a payment method first.','اختر وسيلة الدفع أولاً.'));return;}
      rows.hidden=true;choices.hidden=true;go.hidden=true;noteWrap.hidden=true;
      if(method.details.checkout_mode==='paypal'||method.details.checkout_mode==='link')renderProviderForm(method);
      else renderManualForm(method);
    });go.disabled=!methods.length;
    if(!methods.length)dialog.append(text('p','No payment method is configured for this plan yet.','لم تُعدّ وسيلة دفع لهذه الخطة بعد.'));
    dialog.append(rows,select,noteWrap,go,body,textElement('small',tr('Payment for: ','الدفع لحساب: ')+(currentUser||window.reactivationAccount).email),text('p','Accepted payments cannot be cancelled or refunded.','المدفوعات المقبولة غير قابلة للإلغاء أو الاسترداد.','refund-policy'));
    document.body.append(dialog);dialog.onclose=()=>dialog.remove();dialog.showModal();
  }
  window.beginCheckout=beginCheckout;
  authReady.then(async()=>{const params=new URLSearchParams(location.search);const ret=params.get('payment_return'),cancel=params.get('payment_cancel');if(!ret&&!cancel)return;history.replaceState(null,'',location.pathname+location.hash);if(window.reactivationAccount){await window.loadManagement();await window.openReactivation();}else if(!currentUser){page('authPage');return;}else await window.openClientView('billing');try{await loadPaymentOrders()}catch(error){toast(error.message)}if(cancel){try{await api('/api/billing/orders/'+encodeURIComponent(cancel)+'/cancel',{method:'POST'});await loadPaymentOrders();toast(tr('Unaccepted payment request cancelled.','تم إلغاء طلب الدفع قبل قبوله.'));}catch(error){toast(error.message);}return}try{const order=await api('/api/billing/orders/'+encodeURIComponent(ret));const status=order&&order.status;if(status==='paid')toast(tr('Payment verified. Subscription active.','تم التحقق من الدفع وتفعيل الاشتراك.'));else if(status==='sandbox_paid')toast(tr('Sandbox payment recorded. Real subscription unchanged.','سُجل الدفع التجريبي دون تفعيل اشتراك حقيقي.'));else if(status)toast(tr('Payment is pending verification. Press Confirm PayPal payment in Payment orders.','الدفع بانتظار التحقق. اضغط تأكيد دفع PayPal في طلبات الدفع.'));else toast(tr('Returned from PayPal. Confirm your payment in Payment orders.','عدت من PayPal. أكد الدفع من طلبات الدفع.'))}catch(error){toast(error.message)}}).catch(error=>toast(error.message));
  setInterval(async()=>{if(!currentUser||admin()||!document.querySelector('#workspacePage.active,#workspaceHomePage.active'))return;try{await refreshEntitlement();}catch(error){toast(error.message);}},30000);
  document.addEventListener('click',event=>{if(event.target.closest('#clientNav [data-client-view=billing]'))loadPaymentOrders().catch(e=>toast(e.message));if(event.target.closest('#adminNav [data-admin-view=billing]'))loadPaymentOrders(true).catch(e=>toast(e.message));});
  matchMedia('(max-width:1100px)').addEventListener('change',()=>{q('sessionSidebar').classList.remove('open');overlay(false);});
  applyPrefs();
  if(document.documentElement.dataset.restorePage==='workspacePage')initializeWorkspace();
  q('promptInput').disabled=true;q('homeNewProject').disabled=true;
  window.showBootstrapFrame?.();
})();
