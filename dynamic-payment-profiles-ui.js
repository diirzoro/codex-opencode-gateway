/* TEST: administrator-defined payment/bank settings; no automatic checkout. */
(() => {
  const billingTab = document.querySelector('#adminNav [data-admin-view="billing"]');
  const panel = document.querySelector('[data-admin-panel="billing"]');
  if (!panel || !billingTab) return;
  const host = document.createElement('section');
  host.id = 'dynamicPaymentProviders';
  host.className = 'admin-section dynamic-payment-providers';
  panel.prepend(host);
  let revision = 0;
  const tr = (en, ar) => (typeof lang !== 'undefined' && lang === 'ar') ? ar : en;
  const el = (tag, text='', cls='') => {
    const node = document.createElement(tag);
    node.textContent = text;
    if (cls) node.className = cls;
    return node;
  };
  const button = (label, handler, cls='button small') => {
    const b=el('button',label,cls);
    b.type='button';
    b.addEventListener('click',handler);
    return b;
  };
  const categories=[
    ['bank',tr('Bank','بنك')],['wallet',tr('Wallet','محفظة')],
    ['processor',tr('Payment service','خدمة دفع')],
    ['crypto',tr('Digital asset service','خدمة أصول رقمية')],
    ['other',tr('Other / custom','أخرى / مخصّصة')]
  ];
  const modes=[
    ['manual',tr('Manual transfer + receipt review','تحويل يدوي مع مراجعة إيصال')],
    ['hosted',tr('Provider-hosted payment link (configuration only)','رابط دفع لدى مزوّد (إعداد فقط)')],
    ['api',tr('API integration (credentials only)','API (حفظ بيانات الربط فقط)')]
  ];
  const environments=[['test',tr('Test / Sandbox','تجريبي / Sandbox')],
                      ['live',tr('Live credentials — storage only','مفاتيح حقيقية — تخزين فقط')]];
  const fieldKinds=[
    ['text',tr('Text / identifier','نص / معرّف')],
    ['secret',tr('Secret / API key','مفتاح سري / API')],
    ['url',tr('URL','رابط')]
  ];
  const presets=[
    ['merchant_id','Merchant ID','text'],
    ['security_key','Security / signing key','secret'],
    ['api_key','API key','secret'],
    ['webhook_secret','Webhook signing secret','secret'],
    ['iban','IBAN','text'],
    ['swift_bic','SWIFT / BIC','text'],
    ['bank_name','Bank name','text'],
    ['account_name','Account holder','text'],
    ['account_number','Account number','text'],
    ['payment_url','Hosted checkout URL','url']
  ];
  function selectInput(label,options,defaultValue){
    const wrap=el('label',label),s=el('select');
    for(const [value,name] of options){
      const option=el('option',name);option.value=value;s.append(option);
    }
    s.value=defaultValue||options[0][0];
    wrap.append(s);return {wrap,input:s};
  }
  function textInput(label,value='',maxLength=100){
    const wrap=el('label',label),i=el('input');
    i.type='text';i.value=value;i.maxLength=maxLength;i.autocomplete='off';wrap.append(i);
    return {wrap,input:i};
  }
  async function load(){
    const sequence=++revision;
    if(!['admin','owner'].includes(typeof currentUser==='undefined'?'':currentUser?.role))return;
    host.replaceChildren(el('h2',tr('Flexible payment & bank connections','إدارة البنوك وخدمات الدفع الديناميكية')),
      el('p',tr('Add any bank or provider and define the fields it requires. Save Merchant ID, API/security keys, IBAN or custom fields from here. This is encrypted configuration only; it does NOT charge customers, enable a webhook or change existing payment methods.',
        'أضف أي بنك أو مزوّد وحدد الحقول التي يتطلبها. احفظ Merchant ID ومفاتيح API والتوقيع وIBAN أو أي حقول أخرى من هنا. هذه إعدادات مشفّرة فقط ولا تُحصّل من العملاء أو تُفعّل Webhook أو تغيّر وسائل الدفع الحالية.')));
    let data;
    try{ data=await api('/api/admin/payment-gateways/profiles',{cache:'no-store'}); }
    catch(err){if(sequence===revision)host.append(el('p',err.message,'api-message'));return;}
    if(sequence!==revision)return;
    const toolbar=el('div','','dynamic-provider-toolbar');
    toolbar.append(button(tr('+ Add bank / payment provider','+ إضافة بنك / خدمة دفع'),()=>editor(null)));
    host.append(toolbar);
    const list=el('div','','dynamic-provider-cards');host.append(list);
    if(!data.profiles.length)list.append(el('p',tr('No custom providers yet. Choose Add to configure your first provider.',
      'لا توجد خدمات مخصّصة بعد. اضغط إضافة لإنشاء أول خدمة.')));
    for(const profile of data.profiles){
      const card=el('article','','dynamic-provider-card');
      card.append(el('h3',profile.label),
        el('p',profile.slug+' · '+profile.category+' · '+profile.connection_mode+' · '+profile.environment));
      const count=profile.fields.filter(f=>f.configured).length;
      card.append(el('p',tr('Saved fields: ','الحقول المحفوظة: ')+count+'/'+profile.fields.length+
        ' · '+(profile.configured?tr('Required fields filled','الحقول المطلوبة مكتملة'):tr('Draft / incomplete','مسودة / غير مكتمل'))));
      card.append(el('p',tr('Not connected to automatic checkout','غير مربوط بالتحصيل الآلي'),'dynamic-provider-hint'));
      const actions=el('div','','dynamic-provider-actions');
      actions.append(button(tr('Edit fields / credentials','تعديل الحقول والمفاتيح'),()=>editor(profile),'button ghost small'));
      actions.append(button(tr('Delete this draft','حذف المسودة'),async()=>{
        if(typeof window.confirmAction!=='function')return;
        const confirmed=await window.confirmAction(tr(
          'Delete saved configuration for '+profile.label+'? It will NOT delete payment orders or bank accounts.',
          'حذف إعدادات '+profile.label+' المحفوظة؟ لن تُحذف طلبات الدفع أو الحسابات البنكية.'));
        if(!confirmed)return;
        try{
          await api('/api/admin/payment-gateways/profiles/'+encodeURIComponent(profile.slug),{method:'DELETE'});
          await load();
        }catch(error){status.textContent=error.message;}
      },'button ghost small'));
      card.append(actions);list.append(card);
    }
    const status=el('p','','dynamic-provider-feedback');host.append(status);
  }

  function editor(profile){
    host.querySelector('.dynamic-provider-editor')?.remove();
    const area=el('section','','dynamic-provider-editor manage-card');
    area.append(el('h3',profile?tr('Edit provider','تعديل المزوّد'):tr('New bank / payment provider','إضافة بنك أو مزوّد جديد')),
      el('p',tr('All fields are optional unless you choose Required. A draft may be saved incomplete. Store only long-lived merchant keys, NEVER OTP / 2FA codes, passwords for online banking, card numbers or CVV.',
        'كل حقل اختياري ما لم تحدده كمطلوب. يمكن حفظ المسودة ناقصة. أدخل مفاتيح التاجر الدائمة فقط؛ لا تحفظ رموز OTP أو 2FA أو كلمات مرور البنك أو أرقام البطاقات أو CVV.')));
    const form=el('form','','dynamic-provider-form manage-form');
    form.autocomplete='off';
    const name=textInput(tr('Provider / bank name','اسم البنك أو خدمة الدفع'),profile?.label||'',100);
    const slug=textInput(tr('Unique code in English, e.g. bank_uk or my_wallet','رمز مميز بالإنجليزية مثل bank_uk أو my_wallet'),profile?.slug||'',60);
    slug.input.pattern='[a-z][a-z0-9_-]{1,59}';
    slug.input.required=true;name.input.required=true;
    if(profile)slug.input.readOnly=true;
    const category=selectInput(tr('Provider category','نوع الخدمة'),categories,profile?.category||'bank');
    const mode=selectInput(tr('How this provider would be used','طريقة استخدام الخدمة'),modes,profile?.connection_mode||'manual');
    const environment=selectInput(tr('Credential environment','بيئة مفاتيح الربط'),environments,profile?.environment||'test');
    form.append(name.wrap,slug.wrap,category.wrap,mode.wrap,environment.wrap);
    form.append(el('h4',tr('Custom connection fields','حقول الربط المخصّصة')));
    const rows=el('div','','dynamic-provider-fields');form.append(rows);
    const rowControls=[];
    function addField(field={}){
      if(rowControls.filter(r=>r.element.isConnected).length>=30)return;
      const row=el('div','','dynamic-provider-field');
      const key=textInput(tr('Field code (English)','رمز الحقل بالإنجليزية'),field.key||'',48);
      key.input.required=true;key.input.pattern='[a-z][a-z0-9_]{1,47}';
      const label=textInput(tr('Field label','اسم الحقل'),field.label||'',100);label.input.required=true;
      const kind=selectInput(tr('Field type','نوع الحقل'),fieldKinds,field.kind||'text');
      const required=el('label',tr('Required','مطلوب'),'dynamic-provider-check');
      const requiredInput=el('input');requiredInput.type='checkbox';requiredInput.checked=Boolean(field.required);required.prepend(requiredInput);
      const valueWrap=el('label',tr('Value / connection credential','القيمة / بيانات الربط'));
      const value=el('input');value.autocomplete='off';value.maxLength=2048;
      value.value=(field.kind==='secret')?'':(field.value||'');
      valueWrap.append(value);
      const clear=el('label',tr('Erase saved secret','مسح المفتاح المحفوظ'),'dynamic-provider-check');
      const clearInput=el('input');clearInput.type='checkbox';clear.prepend(clearInput);
      clearInput.checked=false;
      const savedSecret=field.kind==='secret'&&field.configured;
      if(savedSecret)kind.input.disabled=true;
      function updateKind(){
        const secret=kind.input.value==='secret';
        value.type=secret?'password':kind.input.value==='url'?'url':'text';
        value.placeholder=secret?(savedSecret?tr('Saved securely · blank retains key','المفتاح محفوظ · اتركه فارغًا للاحتفاظ به'):tr('Enter secret, stored encrypted','أدخل المفتاح وسيُحفظ مشفرًا')):'';
        clear.hidden=!(secret&&savedSecret);
      }
      kind.input.addEventListener('change',updateKind);updateKind();
      const remove=button(tr('Remove field','حذف الحقل'),()=>row.remove(),'button ghost small');
      row.append(key.wrap,label.wrap,kind.wrap,required,valueWrap,clear,remove);
      rows.append(row);
      rowControls.push({element:row,collect:()=>({
        key:key.input.value.trim(),label:label.input.value.trim(),
        kind:kind.input.value,required:requiredInput.checked,
        value:value.value,clear:clearInput.checked
      })});
    }
    for(const field of (profile?.fields||[]))addField(field);
    const addActions=el('div','','dynamic-provider-presets');
    for(const [key,label,kind] of presets){
      addActions.append(button('+ '+label,()=>{
        if(rowControls.some(r=>r.element.isConnected&&r.collect().key===key))return;
        addField({key,label,kind,required:false});
      },'button ghost small'));
    }
    addActions.append(button(tr('+ Custom field','+ حقل آخر'),()=>addField(),'button ghost small'));
    form.append(addActions);
    const note=el('p',tr('Draft only: API credentials are encrypted and never shown again; this form does not enable checkout.',
      'مسودة إعدادات فقط: تُحفظ المفاتيح مشفّرة ولا تُعرض ثانيةً، ولا يُفعّل هذا النموذج التحصيل الآلي.'),'dynamic-provider-hint');
    const feedback=el('p','','dynamic-provider-feedback');
    const controls=el('div','','dynamic-provider-actions');
    const save=el('button',tr('Save encrypted settings','حفظ الإعدادات المشفّرة'),'button');
    save.type='submit';
    controls.append(save,button(tr('Cancel','إلغاء'),()=>area.remove(),'button ghost small'));
    form.append(note,controls,feedback);area.append(form);
    host.append(area);
    area.scrollIntoView({block:'nearest',behavior:'smooth'});
    form.addEventListener('submit',async event=>{
      event.preventDefault();
      const fields=rowControls.filter(r=>r.element.isConnected).map(r=>r.collect());
      if(!fields.length){feedback.textContent=tr('Add at least one field','أضف حقلًا واحدًا على الأقل');return;}
      const body={slug:slug.input.value.trim(),label:name.input.value.trim(),category:category.input.value,
        connection_mode:mode.input.value,environment:environment.input.value,fields};
      save.disabled=true;feedback.textContent=tr('Saving encrypted profile…','جارٍ حفظ الإعدادات المشفّرة…');
      try{
        const url='/api/admin/payment-gateways/profiles'+(profile?'/'+encodeURIComponent(profile.slug):'');
        await api(url,{method:profile?'PUT':'POST',body:JSON.stringify(body)});
        // Wipe all entered secret values from the DOM before redrawing.
        area.querySelectorAll('input[type="password"]').forEach(input=>{input.value='';});
        await load();
      }catch(error){feedback.textContent=error.message;save.disabled=false;}
    });
  }
  billingTab.addEventListener('click',()=>load().catch(()=>{}));
  if(panel.classList.contains('active'))load().catch(()=>{});
})();
