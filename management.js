/* Owned account management; all durable data goes through the authenticated API. */
(() => {
  const translations=new Map();
  const tr=(en,ar)=>{translations.set(en,[en,ar]);translations.set(ar,[en,ar]);return lang==='ar'?ar:en};
  const node=(tag,text='',cls='')=>{const n=textElement(tag,text,cls);if(translations.has(text)){const [en,ar]=translations.get(text);n.dataset.managementEn=en;n.dataset.managementAr=ar}return n};
  const priorPreferences=applyPrefs;applyPrefs=function(){priorPreferences();$$('[data-management-en]').forEach(n=>{for(const child of n.childNodes)if(child.nodeType===3)child.textContent=lang==='ar'?n.dataset.managementAr:n.dataset.managementEn})};
  const button=(label,run)=>{const b=node('button',label,'button ghost');b.type='button';b.onclick=async()=>{b.disabled=true;try{await run()}catch(e){toast(e.message)}finally{b.disabled=false}};return b};
  const section=(root,title)=>{const s=node('section','','manage-card');s.append(node('h2',title));root.append(s);return s};
  const input=(form,label,name,type='text',value='')=>{const l=node('label',label),i=node('input');i.name=name;i.type=type;i.value=value;l.append(i);form.append(l);return i};
  const select=(form,label,name,options)=>{const l=node('label',label),i=node('select');i.name=name;options.forEach(([v,t])=>i.add(new Option(t,v)));l.append(i);form.append(l);return i};
  const form=(root,fields,label,run)=>{const f=node('form','','manage-form');fields(f);const b=node('button',label,'button');b.type='submit';f.append(b);f.onsubmit=async e=>{e.preventDefault();b.disabled=true;try{await run(Object.fromEntries(new FormData(f)),f);if(f.formDialog?.open)f.formDialog.close()}catch(error){let status=f.querySelector('[role=alert]');if(!status){status=node('p');status.setAttribute('role','alert');f.append(status)}status.textContent=error.message;toast(error.message)}finally{b.disabled=false}};root.append(f);if(root.classList.contains('recovery-box'))return f;window.mountFormDialog(root,f,root.querySelector('h2')?.textContent||label);return f};
  const gridMap=new WeakMap();
  const gridIcon=(id,label)=>{const svg=document.createElementNS('http://www.w3.org/2000/svg','svg'),use=document.createElementNS('http://www.w3.org/2000/svg','use');svg.classList.add('ui-icon');svg.setAttribute('aria-hidden','true');use.setAttribute('href','#'+id);svg.append(use);return svg};
  const row=(root,title,detail,actions=[])=>{let grid=gridMap.get(root);if(!grid){const wrap=node('div','','manage-grid-wrap'),table=node('table','','manage-grid'),head=node('thead'),tr=node('tr');for(const label of [trLabel('Record','السجل'),trLabel('Details','التفاصيل'),trLabel('Actions','الإجراءات')])tr.append(node('th',label));head.append(tr);const tbody=node('tbody');table.append(head,tbody);wrap.append(table);root.append(wrap);grid={tbody};gridMap.set(root,grid)}const tr=node('tr','','manage-grid-row'),titleCell=node('th',title),detailCell=node('td',detail),actionCell=node('td'),actionsBox=node('div','','manage-actions');titleCell.scope='row';for(const action of actions){const label=action.textContent.trim();if(!label)continue;const iconId=/delete|disable|disconnect|remove|archive|suspend/i.test(label)?'icon-trash':/edit|change|rename/i.test(label)?'icon-edit':/view|open|details/i.test(label)?'icon-eye':/connect|authorize/i.test(label)?'icon-link':null;if(iconId){action.classList.add('grid-crud-button');action.title=label;action.setAttribute('aria-label',label);const icon=gridIcon(iconId,label);action.replaceChildren(icon)}else action.classList.add('grid-row-action');actionsBox.append(action)}actionCell.append(actionsBox);tr.append(titleCell,detailCell,actionCell);grid.tbody.append(tr)};
  const trLabel=(en,ar)=>lang==='ar'?ar:en;
  function signOut(){clearAuthenticatedState()}
  const admin=()=>['admin','owner'].includes(currentUser?.role);

  const main=node('main','','page portal-page');main.id='managementPage';protectedPages.add(main.id);
  const header=node('header','','portal-header');header.append(button(tr('← Back','← رجوع'),()=>page(authenticatedHome())),node('strong','Pi Gateway'),button(tr('Workspace','مساحة العمل'),()=>page(activeWorkspace?'workspacePage':'onboarding')));
  const body=node('div','','manage-body');main.append(header,body);document.querySelector('#app-main').append(main);
  async function render(root,name,isPlatform=false){
    await authReady;if(!currentUser)return page('authPage');
    if(isPlatform&&!admin())throw new Error('Administrator access required');
    if(name==='providers'&&!isPlatform&&root.providerView?.workspaceId===(root.dataset.connectionWorkspace||'')&&root.providerView.owner===currentUser.id)return root.providerView.refresh(false);
    root.providerController?.abort();root.replaceChildren();root.dataset.managementSection=name;
    const loader={security,billing,connections,roles,locations,logs,providers,lifecycle,nativeCatalog}[name];
    if(!loader)throw new Error('Unknown section');
    try{await loader(root,isPlatform)}catch(e){root.append(node('p',e.message))}
  }
  async function open(name='security',isPlatform=false){
    await authReady;if(!currentUser)return page('authPage');
    if(isPlatform&&!admin()){toast('Administrator access required');return}
    if(!admin()&&['connections','providers'].includes(name))return window.openConnections(name==='providers'?'providers':'github');
    const client={security:'security',billing:'billing',connections:'github',providers:'ai',logs:'account',lifecycle:'account'};
    const administration={security:'security',billing:'billing',connections:'github',roles:'users',locations:'settings',logs:'audit'};
    if(isPlatform)return window.openAdminView(administration[name]);
    if(admin()&&['security','logs','lifecycle'].includes(name))return window.openAdminView(name==='security'?'security':'account');
    if(admin()&&name==='providers')return window.openAdminView('policy');
    return window.openClientView(client[name]);
  }
  async function nativeCatalog(body,platform=false){
    // TEST models and provider cache are managed only by Pi Native.
    // Do not expose the legacy Gateway/Python refresh scheduler in TEST.
    if(location.hostname==='test.opencode-gateway.codes'||!platform||!admin())return;
    const box=section(body,tr('Native catalog maintenance','صيانة فهرس Pi'));
    const note=node('p',tr('Uses Pi’s own cache refresh. The running service may retain its current model snapshot; conversations are not restarted.','يستخدم تحديث Cache الأصلي في Pi. قد تحتفظ الخدمة الجارية بفهرسها الحالي؛ لا تُعاد تشغيل المحادثات.'));box.append(note);
    const state=node('p');state.setAttribute('role','status');box.append(state);
    const days=select(box,tr('Maintenance interval','دورية الصيانة'),'interval_days',[['7',tr('Every 7 days','كل 7 أيام')],['14',tr('Every 14 days','كل 14 يومًا')]]);
    function display(value){days.value=String(value.interval_days);state.textContent=tr('Last result: ','آخر نتيجة: ')+({not_attempted:tr('Not run yet','لم يُنفذ بعد'),running:tr('Running','جارٍ التنفيذ'),failed:tr('Refresh failed; last working catalog retained','فشل التحديث؛ يبقى آخر فهرس صالح'),cli_completed_reload_unverified:tr('Cache command completed; live reload unverified','اكتمل أمر Cache؛ إعادة التحميل الحية غير مثبتة')}[value.outcome]||tr('Unknown','غير معروف'))+(value.last_attempt_at?' · '+new Date(value.last_attempt_at*1000).toLocaleString():'')+(value.available===false?tr(' · Native service context requires operator inspection',' · يلزم فحص سياق الخدمة الفعلي من المشغّل'):'');}
    display(await api('/api/admin/native/catalog-maintenance'));
    box.append(button(tr('Save interval','حفظ الدورية'),async()=>display(await api('/api/admin/native/catalog-maintenance',{method:'PUT',body:JSON.stringify({interval_days:Number(days.value)})}))),
      button(tr('Refresh native cache','تحديث Cache الأصلي'),async()=>display(await api('/api/admin/native/catalog-maintenance/refresh',{method:'POST'}))));
  }
  async function security(body,platform=false){
    const change=section(body,tr('Change password','تغيير كلمة المرور'));
    form(change,f=>{input(f,tr('Current password','كلمة المرور الحالية'),'current_password','password').required=true;const n=input(f,tr('New password: 8+, number and symbol','كلمة جديدة: 8 أحرف، رقم ورمز'),'new_password','password');n.minLength=8;n.required=true},tr('Change and sign out','تغيير وتسجيل الخروج'),async values=>{await api('/api/account/password',{method:'PUT',body:JSON.stringify(values)});signOut()});
    const sessions=section(body,tr('Active sessions','الجلسات النشطة'));
    for(const s of await api('/api/account/sessions'))row(sessions,tr(s.current?'This session':'Other session',s.current?'الجلسة الحالية':'جلسة أخرى'),new Date(s.created_at).toLocaleString(),[button(tr('Sign out','تسجيل الخروج'),async()=>{await api('/api/account/sessions/'+s.id,{method:'DELETE'});if(s.current)signOut();else await open('security')})]);
    const twoFactor=section(body,tr('Two-factor authentication','المصادقة الثنائية'));
    twoFactor.append(node('p',tr('Not available yet. Two-factor authentication is not implemented.','غير متاحة بعد. لم يُنفّذ إعداد المصادقة الثنائية.')));
    const devices=section(body,tr('Devices','الأجهزة'));
    devices.append(node('p',tr('Device identification is not available yet. Use Active sessions above to revoke a sign-in.','معلومات الأجهزة غير متاحة بعد. يمكنك إلغاء تسجيل الدخول من الجلسات النشطة أعلاه.')));
    await logs(body,false,true);
  }
  async function lifecycle(body){
    const close=section(body,tr('Suspend or request deletion','تعليق الحساب أو طلب حذفه'));close.append(node('p',tr('Access stops immediately. Files remain for administrator review. An administrator must reactivate a suspended account.','يتوقف الوصول فورًا، وتبقى الملفات لمراجعة الإدارة. إعادة تنشيط الحساب تتم بواسطة الإدارة.')));
    form(close,f=>{input(f,tr('Your username','اسم المستخدم'),'confirmation').required=true;input(f,tr('Current password','كلمة المرور الحالية'),'password','password').required=true;select(f,tr('Action','الإجراء'),'action',[['suspend',tr('Suspend','تعليق')],['delete',tr('Request deletion','طلب الحذف')]])},tr('Confirm','تأكيد'),async values=>{if(!await window.confirmAction(tr('Disable access to this account?','تعطيل الوصول إلى هذا الحساب؟')))return;await api('/api/account/lifecycle',{method:'POST',body:JSON.stringify(values)});signOut()});
  }
  async function billing(body,platform=false){
    if(!platform){
      body.dataset.billingRole='customer';
      const box=section(body,tr('Accepted payment methods','وسائل الدفع المتاحة'));
      box.append(node('p',tr('Choose a plan above to open checkout. Select a method configured by the platform and complete payment for your account.','اختر خطة من الأعلى لفتح نموذج الدفع، ثم اختر وسيلة أعدّتها المنصة وأكمل الدفع لحسابك.')));
      const methods=await api('/api/billing/available-methods?include_unavailable=true');
      for(const m of methods)row(box,m.label,m.available?(m.details.checkout_mode==='paypal'?tr('PayPal · verified online payment','PayPal · دفع إلكتروني موثّق'):m.details.checkout_mode==='link'?tr('Hosted checkout · receipt verification required','دفع عبر رابط · يتطلب التحقق من الاستلام'):tr('Bank / wallet transfer · receipt verification required','تحويل بنكي / محفظة · يتطلب التحقق من الاستلام')):tr('Not connected — provider setup required','غير متصل — يتطلب إعداد المزود'));
      if(!methods.length)box.append(node('p',tr('Administration has not configured a payment method yet.','لم تُعدّ الإدارة وسيلة دفع بعد.')));
      return;
    }
    if(!admin())throw new Error('Administrator access required');
    body.dataset.billingRole='admin';
    const box=section(body,tr('Platform receiving methods','وسائل استلام المنصة'));
    box.append(node('p',tr('Configure where the platform receives payments. Customers choose these methods at checkout; they cannot edit them. These methods use manual receipt verification. Google Pay needs a processor-hosted checkout link; Binance transfers require receipt review. Do not enter card numbers, CVV or private keys.','أعدّ وسائل استلام مدفوعات المنصة. يختارها العميل أثناء الدفع ولا يستطيع تعديلها. هذه الوسائل تتطلب التحقق اليدوي من الاستلام. لا تدخل أرقام بطاقات أو CVV أو مفاتيح خاصة.')));
    const paymentStatus=await api('/api/billing/paypal/status');box.append(node('p',tr('PayPal API: '+(paymentStatus.configured?'configured':'merchant setup required')+' · '+paymentStatus.environment,'PayPal API: '+(paymentStatus.configured?'مهيأ':'يتطلب إعداد التاجر')+' · '+paymentStatus.environment)));const query=platform?'?platform=true':'',items=await api('/api/billing/methods'+query),plans=await api('/api/plans');let editing=null;
    // The dynamic provider catalogue is the only supported creation/editing UI.
    // Retain legacy method rows for historical orders, never delete their data.
    const profilesPanel=section(body,tr('Saved dynamic providers','المزودون المحفوظون ديناميكيًا'));
    const gotoDynamic=()=>{const target=document.getElementById('dynamicPaymentProviders');if(target){target.scrollIntoView({behavior:'smooth',block:'start'});document.getElementById('dynamicProviderAdd')?.focus();}};
    profilesPanel.append(button(tr('Manage providers in the new form','إدارة الخدمات من النموذج الجديد'),gotoDynamic));
    try{
      const catalogue=await api('/api/admin/payment-gateways/method-catalog',{cache:'no-store'});
      for(const provider of (catalogue.methods||[])){
        const state=provider.status==='enabled_manual'?tr('Enabled · receipt verification','مفعّل · مراجعة الإيصال')
          :provider.status==='configured_unverified'?tr('Configured · not verified','محفوظ · لم يتم التحقق')
          :provider.status==='draft'?tr('Incomplete draft','مسودة غير مكتملة')
          :provider.status==='enabled_existing'?tr('Existing enabled method','وسيلة سابقة مفعّلة')
          :tr('Existing disabled method','وسيلة سابقة معطلة');
        row(profilesPanel,provider.label,(provider.category||'other')+' · '+provider.connection_mode+' · '+(provider.environment||'—')+' · '+state);
      }
      if(!(catalogue.methods||[]).length)profilesPanel.append(node('p',tr('No saved payment methods yet.','لا توجد وسائل دفع محفوظة.')));
    }catch(error){profilesPanel.append(node('p',tr('Unable to load payment catalogue: ','تعذر تحميل قائمة الدفع: ')+error.message));}
    const editor=section(body,tr('Add or edit method','إضافة وسيلة أو تعديلها'));
    editor.hidden=true; // Legacy modal is retired; existing backend remains for compatibility.
    const f=form(editor,f=>{select(f,tr('Type','النوع'),'kind',[['paypal','PayPal'],['googlepay','Google Pay'],['binance','Binance'],['bank',tr('Bank account','حساب بنكي')],['wallet',tr('Wallet','محفظة')],['other',tr('Other','أخرى')]]);input(f,tr('Label','الاسم'),'label').required=true;select(f,tr('Checkout','طريقة الدفع'),'checkout_mode',[['manual',tr('Bank / wallet transfer','تحويل بنكي / محفظة')],['link',tr('Hosted payment link / PayPal','رابط دفع / PayPal')],['paypal',tr('PayPal API — verified payment','PayPal API — دفع موثّق')]]);input(f,tr('Payment link (HTTPS)','رابط الدفع (HTTPS)'),'payment_url','url');select(f,tr('Plan for this link','الخطة الخاصة بالرابط'),'plan_id',[['',tr('All plans (transfers only)','كل الخطط (التحويل فقط)')],...plans.filter(p=>p.active!==false).map(p=>[String(p.id),p.name+' · '+p.currency+' '+(p.price_cents/100).toFixed(2)])]);select(f,tr('Bank shortcut','اختيار البنك'),'bank_shortcut',[['','—'],['Al-Qutaibi','القطيبي · Al-Qutaibi'],['Al-Kuraimi','الكريمي · Al-Kuraimi']]);for(const [n,en,ar] of [['account_name','Account holder','صاحب الحساب'],['account_reference','Email / account number / wallet / Binance Pay ID','البريد / رقم الحساب / المحفظة / معرّف Binance Pay'],['iban','IBAN (optional)','الآيبان (اختياري)'],['branch','Branch (optional)','الفرع (اختياري)'],['bank_name','Bank name','اسم البنك'],['currency','Currency','العملة'],['network','Wallet network','شبكة المحفظة'],['instructions','Instructions','التعليمات']])input(f,tr(en,ar),n,'text',n==='currency'?'USD':'');select(f,tr('Status','الحالة'),'enabled',[['true',tr('Enabled','مفعّل')],['false',tr('Disabled','معطّل')]]);input(f,tr('Available countries (2-letter codes, comma separated, empty = all countries)','الدول المتاحة (رموز من حرفين مفصولة بفواصل، فارغ = كل الدول)'),'available_country_codes')},tr('Save method','حفظ الوسيلة'),async values=>{values.enabled=values.enabled==='true';values.plan_id=values.plan_id?Number(values.plan_id):null;values.available_country_codes=String(values.available_country_codes||'').split(',').map(s=>s.trim().toUpperCase()).filter(Boolean);delete values.bank_shortcut;if(values.kind!=='bank')values.bank_name='';if(!['wallet','binance'].includes(values.kind))values.network='';if(values.checkout_mode!=='link')values.payment_url='';await api('/api/billing/methods'+(editing?'/'+editing:'')+query,{method:editing?'PUT':'POST',body:JSON.stringify(values)});await open('billing',platform)});
    f.dataset.paymentForm='platform';
    const guidance=node('p','','payment-setup-guidance');guidance.setAttribute('role','note');f.prepend(guidance);
    const examples={label:['Example: Al-Qutaibi bank transfer','مثال: تحويل بنك القطيبي'],account_name:['Example: your legal account name','مثال: اسمك المسجل في الحساب'],account_reference:['Example: receiving email, account number or Binance UID','مثال: بريد الاستلام أو رقم الحساب أو معرّف Binance'],payment_url:['https://checkout.your-provider.example/plan-monthly','https://checkout.your-provider.example/plan-monthly'],bank_name:['Example: Al-Qutaibi / Al-Kuraimi','مثال: القطيبي / الكريمي'],network:['Example: Binance internal transfer / agreed token network','مثال: تحويل Binance الداخلي / شبكة العملة المتفق عليها'],instructions:['Explain how to pay, currency, and receipt reference. Examples are not real receiving details.','وضح طريقة الدفع والعملة ومرجع الإيصال. الأمثلة ليست بيانات استلام حقيقية.']};
    for(const [name,[en,ar]] of Object.entries(examples))f.elements[name].placeholder=tr(en,ar);
    function paymentGuidance(){const kind=f.elements.kind.value,mode=f.elements.checkout_mode.value;const copy=kind==='googlepay'?['Create a checkout link with a payment processor that supports Google Pay. Paste its HTTPS URL and select the matching plan/currency. Enable only after testing.','أنشئ رابط دفع لدى مزود يدعم Google Pay. أدخل رابط HTTPS وحدد الخطة والعملة المطابقتين. فعّله بعد الاختبار فقط.']:mode==='paypal'?['Backend setup required: PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, PAYPAL_MERCHANT_ID, PAYPAL_ENVIRONMENT=sandbox, PUBLIC_BASE_URL. Put values in the private backend environment and restart. Use PAYPAL_SANDBOX_DECLINE=true for a sandbox-issued decline test; never in live. Email alone does not connect the merchant API.','يلزم إعداد الخلفية: PAYPAL_CLIENT_ID وPAYPAL_CLIENT_SECRET وPAYPAL_MERCHANT_ID وPAYPAL_ENVIRONMENT=sandbox وPUBLIC_BASE_URL. ضع القيم في بيئة الخلفية الخاصة وأعد التشغيل. لاختبار رفض تجريبي استخدم PAYPAL_SANDBOX_DECLINE=true في Sandbox فقط. البريد وحده لا يربط واجهة التاجر.']:mode==='link'?['Create a real payment link in your merchant service. Match its price and currency to the selected plan. The client pays on that service, then submits a receipt. Administration verifies payment before activation.','أنشئ رابط دفع حقيقي من خدمة التاجر. طابق السعر والعملة مع الخطة المختارة. يدفع العميل في صفحة الخدمة ثم يرسل مرجع الإيصال، وتتحقق الإدارة قبل التفعيل.']:kind==='binance'?['Enter your confirmed Binance receiving email or UID. State the accepted asset/network and exact amount in instructions. Check the actual transaction in Binance before confirming a receipt. This is a manual transfer, not Binance Pay API.','أدخل بريد استلام Binance أو UID الموثق. وضح العملة والشبكة والمبلغ في التعليمات. تحقق من العملية داخل Binance قبل تأكيد الإيصال. هذا تحويل يدوي وليس ربط Binance Pay API.']:['Enter the real recipient name, account number/address, currency and transfer instructions. Customers submit references; administration checks the actual receipt. Never enter card details or private keys.','أدخل اسم المستفيد ورقم الحساب أو العنوان والعملة وتعليمات التحويل الحقيقية. يرسل العميل مرجع العملية وتتحقق الإدارة من الاستلام. لا تدخل بيانات بطاقات أو مفاتيح خاصة.'];guidance.textContent=tr(...copy);}

    function methodFields(){const kind=f.elements.kind.value;for(const name of ['bank_name','network'])f.elements[name].parentElement.hidden=name==='bank_name'?kind!=='bank':!['wallet','binance'].includes(kind);}
    const originalMethodFields=methodFields;methodFields=function(){originalMethodFields();const linked=f.elements.checkout_mode.value==='link';for(const name of ['payment_url','plan_id']){f.elements[name].parentElement.hidden=!linked;f.elements[name].required=linked&&f.elements.enabled.value==='true';}f.elements.bank_shortcut.parentElement.hidden=f.elements.kind.value!=='bank';paymentGuidance();};f.elements.enabled.onchange=methodFields;f.elements.checkout_mode.onchange=methodFields;f.elements.bank_shortcut.onchange=()=>{if(f.elements.bank_shortcut.value){f.elements.bank_name.value=f.elements.bank_shortcut.value;f.elements.label.value=f.elements.bank_shortcut.value;}};f.elements.kind.onchange=()=>{if(f.elements.kind.value==='googlepay')f.elements.checkout_mode.value='link';methodFields();};methodFields();
    editor.append(button(tr('New method','وسيلة جديدة'),()=>{editing=null;f.reset();methodFields();f.openDialog()}));
    const presets=node('div','','manage-actions');editor.append(node('p',tr('Start with an example below. Examples are disabled drafts: replace every example value and configure the provider before enabling.','ابدأ بأحد الأمثلة أدناه. الأمثلة مسودات معطّلة: استبدل القيم وأكمل إعداد المزود قبل التفعيل.')),presets);
    for(const [label,kind,mode,bank] of [['PayPal','paypal','paypal',''],['Google Pay','googlepay','link',''],['Binance','binance','manual',''],['Al-Qutaibi','bank','manual','Al-Qutaibi'],['Al-Kuraimi','bank','manual','Al-Kuraimi']])presets.append(button(tr('Example: '+label,'مثال: '+label),()=>{editing=null;f.reset();const draft={kind,label,checkout_mode:mode,enabled:'false',currency:'USD',bank_name:bank,account_name:'EXAMPLE_REPLACE_ACCOUNT_NAME',account_reference:kind==='googlepay'?'':'EXAMPLE_REPLACE_RECEIVING_ACCOUNT',network:kind==='binance'?'EXAMPLE_REPLACE_ASSET_AND_NETWORK':'',payment_url:mode==='link'?'https://checkout.example.com/your-plan':'',plan_id:'',instructions:tr('EXAMPLE: replace receiver details, specify the accepted currency/asset and exact amount; verify receipt before activation.','مثال: استبدل بيانات المستفيد وحدد العملة والمبلغ، وتحقق من الاستلام قبل التفعيل.')};for(const [name,value] of Object.entries(draft))f.elements[name].value=value;methodFields();f.openDialog();}));

    // Combined catalogue above owns the saved-method list; no duplicate rows.
    if(!items.length)box.append(node('p',tr('No saved methods','لا توجد وسائل محفوظة')));
    if(!platform){const receiving=section(body,tr('Platform receiving methods','وسائل الاستلام في المنصة'));for(const m of await api('/api/billing/available-methods'))row(receiving,m.label,Object.values(m.details).filter(Boolean).join(' · '))}
  }
  async function connections(body,platform=false){const box=section(body,tr('GitHub connections','اتصالات GitHub'));if(platform){const connections=await api('/api/admin/connections');if(!connections.length)box.append(node('p',tr('No customer GitHub connections yet. App settings are shown above.','لا توجد اتصالات GitHub للعملاء بعد. إعدادات التطبيق معروضة أعلاه.')));for(const c of connections)row(box,c.login,c.user_id,[button(tr('Disconnect','إلغاء الربط'),async()=>{if(!await window.confirmAction(tr('Disconnect this account and revoke its GitHub credentials? All project files remain.','فصل هذا الحساب وإبطال اعتمادات GitHub؟ تبقى جميع ملفات مشاريعه.')))return;await api('/api/admin/connections/'+c.user_id,{method:'DELETE'});await open('connections',true)})]);return}
    box.append(node('p',tr('Connect your own GitHub account and choose its repositories. This authorizes repository access only; your Gateway sign-in stays unchanged.','اربط حساب GitHub الخاص بك واختر مستودعاته. هذا تفويض للمستودعات فقط؛ يبقى تسجيل دخولك إلى Gateway كما هو.')));
    const status=await api('/api/github/status');row(box,status.github_login||status.account_login||tr('Not connected','غير متصل'),status.configured?tr('GitHub App configured','تطبيق GitHub مهيأ'):tr('Administrator must configure the GitHub App','يجب على الإدارة إعداد تطبيق GitHub'));
    window.renderGithubConfirmation(box,status,()=>open('connections'));
    const linkOwner=currentUser?.id;
    const authorize=button(tr('New GitHub connection','ربط GitHub جديد'),async()=>{
      await window.startFreshGithubConnection({isCurrent:()=>currentUser?.id===linkOwner});
    });authorize.disabled=!status.configured;box.append(authorize);
    box.append(node('p',tr('GitHub may remember its own browser login. Use “Use a different account” on GitHub to switch; Gateway cannot clear github.com cookies.','قد يتذكر GitHub تسجيل دخوله في المتصفح. اختر «Use a different account» لتغييره؛ لا يستطيع Gateway مسح جلسة github.com.')));
    if(!status.configured)box.append(node('p',tr('Repository connection will be available after the administrator saves the App credentials and configures secure credential storage. No customer API token is needed in this form.','سيصبح ربط المستودعات متاحًا بعد حفظ الإدارة بيانات التطبيق وإعداد التخزين الآمن للاعتمادات. لا تحتاج إلى إدخال رمز API خاص بك في هذا النموذج.')));
    for(const [en,ar] of [['Repositories','المستودعات'],['Branches','الفروع']]){const s=section(body,tr(en,ar));if(!status.connected)s.append(node('p',tr('Connect and authorize GitHub to access your repositories and branches.','اربط GitHub وفوّضه للوصول إلى مستودعاتك وفروعها.')));}
    if(status.connected){box.append(button(tr('Refresh repositories','تحديث المستودعات'),()=>open('connections')));box.append(button(tr('Disconnect GitHub','إلغاء ربط GitHub'),async()=>{if(!await window.disconnectGithubWithReview())return;await open('connections')}));
      const repos=await api('/api/github/repositories');let repository,branch;
      if(!repos.length){box.append(node('p',tr('No authorized repositories found. Review the repositories selected for the GitHub App in your GitHub account, then refresh.','لم توجد مستودعات مفوّضة. راجع المستودعات المختارة لتطبيق GitHub في حسابك على GitHub ثم حدّث القائمة.')));return}
      form(box,f=>{repository=select(f,tr('Repository','المستودع'),'repository',[['',tr('Choose repository','اختر مستودعًا')],...repos.map(r=>[r.full_name,r.full_name])]);repository.required=true;branch=select(f,tr('Branch','الفرع'),'branch',[]);branch.required=true;input(f,tr('Project name','اسم المشروع'),'project_name').required=true;repository.onchange=async()=>{branch.replaceChildren();if(!repository.value)return;try{for(const b of await api('/api/github/branches?repository='+encodeURIComponent(repository.value)))branch.add(new Option(b.name,b.name))}catch(e){toast(e.message)}}},tr('Create workspace','إنشاء مساحة عمل'),async values=>{const result=await api('/api/projects',{method:'POST',body:JSON.stringify({...values,source_type:'github'})});await openWorkspace(result.project,result.workspace)});
    }
  }
  async function providers(body,platform=false){
    const controller=new AbortController();body.providerController=controller;
    const view={owner:currentUser.id,workspaceId:body.dataset.connectionWorkspace||'',ready:false,refresh:null};body.providerView=view;
    const alive=()=>body.isConnected&&body.providerView===view&&currentUser?.id===view.owner;
    const workspaceSettings=section(body,tr('Runtime / workspace settings','إعدادات وقت التشغيل ومساحة العمل'));
    const picker=select(workspaceSettings,tr('Workspace','مساحة العمل'),'workspace',[['',tr('Account connections · all projects','اتصالات الحساب · كل المشاريع')]]);
    picker.disabled=true;
    if(activeWorkspace)picker.add(new Option(activeProject?.name||tr('Selected workspace','مساحة العمل المختارة'),activeWorkspace.id));
    picker.value=view.workspaceId;
    const box=section(body,tr('Connect verified providers','ربط المزوّدين الموثقين'));
    // Existing Gateway maintenance owns Pi metadata refresh every 14 days.
    // Account and new-provider views read only saved PostgreSQL data.
    let catalogRequested=false,catalogLoading=false;
    box.append(node('p',tr('Gateway verifies each supported API key with the real provider before encrypting it for your account. A catalog entry is not a connection.','يتحقق Gateway من مفتاح API لدى المزوّد الحقيقي قبل حفظه مشفرًا لحسابك. ظهور المزوّد في الفهرس لا يعني اتصاله.')));
    const comboWrap=node('div','','provider-combo'),combo=node('input');combo.type='search';
    combo.value=body.dataset.providerQuery||'';combo.placeholder=tr('Search providers…','ابحث عن المزوّدات…');combo.setAttribute('role','combobox');combo.setAttribute('aria-expanded','false');combo.autocomplete='off';combo.setAttribute('aria-label',combo.placeholder);
    const options=node('div','','provider-combo-options');options.hidden=true;comboWrap.append(combo,options);box.append(comboWrap);
    comboWrap.hidden=true;
    const progress=node('p','','provider-loading');progress.setAttribute('role','status');progress.setAttribute('aria-live','polite');box.append(progress);
    const status=node('p',tr('Choose a provider to inspect its connection.','اختر مزوّدًا لفحص اتصاله.'),'provider-combo-status');box.append(status);
    status.hidden=true;
    // The provider catalog remains hidden until "Connect a new provider".
    // Existing connections always load from Gateway PostgreSQL.
    const catalogCount=node('p','','provider-catalog-count');box.append(catalogCount);
    // One compact native select, not dozens of provider tiles.
    const catalogList=node('select','','provider-catalog-picker');
    catalogList.setAttribute('aria-label',tr('Choose a provider','اختر المزوّد'));
    box.append(catalogList);
    catalogList.hidden=true;catalogCount.hidden=true;
    const platformBox=section(body,tr('Pi Gateway models · managed by administrator','نماذج Pi Gateway · تديرها الإدارة'));
    const connectedBox=section(body,tr('My verified provider connections','اتصالات مزوّداتي الموثقة'));
    const contextCurrent=()=>!workspaceId||activeWorkspace?.id===workspaceId;
    let workspaceId=view.workspaceId,base='/api/workspaces/'+workspaceId+'/providers/';
    let snapshot=workspaceId?window.workspaceRuntime.peek(workspaceId):null,workspaces=[],projects=[],selectedProviderId='';
    let searchRows=[],searchQuery='',searchTimer=null,searchAbort=null,searchSequence=0,optionsOpen=false;
    const searchState=node('p','','provider-search-status');searchState.setAttribute('role','status');comboWrap.after(searchState);
    searchState.hidden=true;
    // Default view: saved PostgreSQL connections only. The new-link button
    // reveals cached providers without invoking Pi.
    async function accountCatalogRows(){
      const result=await api('/api/opencode/catalog/providers?connected_only='+
        String(!catalogRequested));
      const connected=new Set(result.connected||[]);
      return (result.all||[]).filter(p=>p&&typeof p.id==='string').map(p=>({
        id:p.id,name:p.name||p.id,
        model_count:p.model_count??Object.keys(p.models||{}).length,
        connected:connected.has(p.id),personal_connected:p.personal_connected===true,
        platform:p.platform===true,platform_models:p.platform_models||[],
        credit_status:p.credit_status||'unknown',
        verified:p.verified===true,stale:p.stale===true,
         api_key_supported:p.api_key_supported===true,
        last_synced_at:p.last_synced_at||null,visible:true,allowed:true
      })).sort((a,b)=>Number(b.connected)-Number(a.connected)||
        a.name.localeCompare(b.name));
    }
    async function lookup(kind,value,signal){
      if(signal?.aborted||!alive()||!contextCurrent())
        throw new DOMException('Workspace changed','AbortError');
      const term=value.trim().toLowerCase();
      const rows=snapshot?.providers||[];
      if(kind==='resolve'){
        const found=rows.find(p=>p.id.toLowerCase()===term)||
          rows.find(p=>p.name.toLowerCase()===term);
        if(!found)throw Error('Provider not found in saved catalog: '+value);
        return [found];
      }
      return rows.filter(p=>p.id.toLowerCase().includes(term)||
        p.name.toLowerCase().includes(term));
    }
    const retry=button(tr('Retry','إعادة المحاولة'),()=>refresh(true));retry.hidden=true;box.append(retry);
    const message=(text,error=false)=>{progress.textContent=text;progress.classList.toggle('connection-error',error);retry.hidden=!error;};
    // Account-owned Gateway credential actions. No Pi auth.json mutations.
    let providerMutation=false;
    async function openGatewayLogin(p,replaceExisting=false){
      if(!alive()||providerMutation)return;
      const host=node('div'),f=node('form','','manage-form');
      const key=input(f,tr('API key for ','مفتاح API للمزوّد ')+(p.name||p.id),'api_key');
      key.type='password';key.required=true;key.autocomplete='off';key.maxLength=8192;
      f.append(node('p',tr('The key is verified with the provider before encrypted storage. It is never returned to your browser.','يتم التحقق من المفتاح لدى المزوّد قبل حفظه مشفرًا، ولا يُعاد إلى المتصفح.')));
      const feedback=node('p','','provider-feedback');feedback.setAttribute('role','status');f.append(feedback);
      const submit=node('button',replaceExisting?tr('Verify and replace','تحقق واستبدل'):tr('Verify and connect','تحقق واربط'),'button');
      submit.type='submit';f.append(submit);
      host.append(f);document.body.append(host);
      const dialog=window.mountFormDialog(host,f,replaceExisting?tr('Replace provider key','استبدال مفتاح المزوّد'):tr('Connect provider','ربط المزوّد'));
      f.dialogTrigger.hidden=true;
      f.onsubmit=async event=>{
        event.preventDefault();
        if(providerMutation||!alive()||!dialog.open||!f.reportValidity())return;
        providerMutation=true;submit.disabled=true;
        feedback.textContent=tr('Checking the provider…','جارٍ التحقق من المزوّد…');
        const value=key.value;key.value='';
        try{
          const result=await api('/api/opencode/connections'+(replaceExisting?'/'+encodeURIComponent(p.id):''),{
            method:replaceExisting?'PUT':'POST',body:JSON.stringify({provider_id:p.id,api_key:value})});
          if(result?.provider_id!==p.id||result.auth_status!=='verified')
            throw Error(tr('Provider did not confirm authentication','لم يؤكد المزوّد صلاحية المفتاح'));
          dialog.close();await reload();
          message(tr('Verified and saved for your account','تم التحقق والحفظ لحسابك فقط'));
        }catch(error){if(dialog.open)feedback.textContent=error.message||String(error);}
        finally{providerMutation=false;submit.disabled=false;}
      };
      dialog.addEventListener('close',()=>{key.value='';host.remove()},{once:true});
      f.openDialog();
    }
    async function disconnectGateway(p){
      if(providerMutation||!p.connected||!alive())return;
      if(!await window.confirmAction(tr('Delete your saved '+(p.name||p.id)+' key? Pi will reject further requests using this connection.','حذف مفتاح '+(p.name||p.id)+' المحفوظ لحسابك؟ لن يقبل Pi استخدام هذا الاتصال بعد الحذف.')))return;
      providerMutation=true;
      try{
        await api('/api/opencode/connections/'+encodeURIComponent(p.id),{method:'DELETE'});
        await reload();
        message(tr('Connection deleted from your account','تم حذف الاتصال من حسابك'));
      }catch(error){message(error.message||String(error),true);}
      finally{providerMutation=false;}
    }
    function piStateLabel(p){
      if(p.platform&&!p.personal_connected)return tr('Pi Gateway platform model · administrator-managed','نموذج منصة Pi Gateway · تديره الإدارة');
      if(!p.connected)return tr('Available in catalog · not connected','متاح في الفهرس · غير متصل')+
        (p.stale?' · '+tr('Catalog refresh overdue','تحديث الفهرس متأخر'):'');
      return tr('Verified for this account','موثق لهذا الحساب')+' · '+(p.credit_status||'unknown')+
        (p.stale?' · '+tr('Model catalog older than 14 days','فهرس النماذج أقدم من 14 يومًا'):'');
    }
    function renderSelected(p){
      status.replaceChildren(node('strong',p.name||p.id),
        node('span',piStateLabel(p)+' · '+String(p.model_count??0)+' '+tr('models','نموذج')));
      if(!view.ready)return;
      const actions=node('div','','manage-actions');
      if(p.personal_connected){
        actions.append(button(tr('Replace API key','استبدال مفتاح API'),()=>openGatewayLogin(p,true).catch(error=>message(error.message,true))));
        actions.append(button(tr('Delete connection','حذف الاتصال'),()=>disconnectGateway(p)));
      }else{
        if(p.api_key_supported){
           actions.append(button(tr('Connect personal API key','ربط مفتاح API شخصي'),
             ()=>openGatewayLogin(p).catch(error=>message(error.message,true))));
         }else{
           actions.append(node('p',tr('Verified API-key linking is not yet supported for this Pi provider.','التحقق من مفتاح API الشخصي غير مدعوم لهذا المزوّد حاليًا.')));
         }
      }
      status.append(actions);
    }
    function renderPlatform(){
      platformBox.replaceChildren(node('h2',tr('Pi Gateway models · managed by administrator','نماذج Pi Gateway · تديرها الإدارة')));
      const rows=(snapshot?.providers||[]).filter(p=>p.platform);
      if(!rows.length){
        platformBox.append(node('p',tr('No shared Pi models have been enabled yet.','لم تفعّل الإدارة نماذج Pi مشتركة بعد.')));
        return;
      }
      platformBox.append(node('p',tr('These shared models are managed by the administrator. Customers cannot disable or remove them.','هذه النماذج تديرها الإدارة، ولا يستطيع العميل تعطيلها أو حذفها.')));
      for(const p of rows){
        const detail=node('details','','provider-connected-detail');
        const summary=node('summary','','provider-connected-summary');
        summary.append(node('strong',p.name||p.id),node('small',
          String(p.platform_models?.length||0)+' '+tr('platform models · locked','نموذج منصة · ثابت')));
        const list=node('div','','provider-connected-content');
        for(const id of p.platform_models||[])list.append(node('p','✓ '+id));
        detail.append(summary,list);platformBox.append(detail);
      }
    }
    function renderConnected(){
      connectedBox.replaceChildren(node('h2',tr('My verified provider connections','اتصالات مزوّداتي الموثقة')));
      const rows=(snapshot?.providers||[]).filter(p=>p.personal_connected);
      if(!rows.length){
        connectedBox.append(node('p',tr('No verified providers are connected to your account.','لا توجد مزوّدات موثقة مربوطة بحسابك.')));
        return;
      }
      for(const p of rows){
        const details=node('details','','provider-connected-detail');
        const summary=node('summary','','provider-connected-summary');
        summary.append(node('strong',p.name||p.id),node('small',
          String(p.model_count||0)+' '+tr('models · click to manage','نموذج · اضغط لإدارة النماذج')));
        const content=node('div','','provider-connected-content');
        const actions=node('div','','manage-actions');
        actions.append(button(tr('Replace API key','استبدال مفتاح API'),
          ()=>openGatewayLogin(p,true).catch(error=>message(error.message,true))));
        actions.append(button(tr('Disconnect','حذف الاتصال'),()=>disconnectGateway(p)));
        const models=node('div','','provider-connected-models');
        content.append(actions,models);
        details.append(summary,content);connectedBox.append(details);
        details.addEventListener('toggle',async()=>{
          if(!details.open||details.dataset.modelsLoaded||!alive())return;
          details.dataset.modelsLoaded='loading';
          models.textContent=tr('Loading saved provider models…','جارٍ تحميل النماذج المحفوظة…');
          try{
            const response=await api('/api/opencode/connections/'+encodeURIComponent(p.id)+'/models');
            if(!alive()||!details.isConnected)return;
            details.dataset.modelsLoaded='yes';models.replaceChildren();
            if(!response.models?.length){
              models.append(node('p',tr('No models are available for this provider.','لا توجد نماذج متاحة لهذا المزوّد.')));
              return;
            }
            const modelSearch=node('input','','provider-model-search');modelSearch.type='search';
            modelSearch.placeholder=tr('Filter this provider’s models…','ابحث في نماذج هذا المزوّد…');
            const rowsBox=node('div','','provider-model-choice-list');
            const items=response.models.map(m=>{
              const label=node('label','','provider-model-choice'),toggle=node('input');
              toggle.type='checkbox';toggle.checked=m.enabled===true;
              toggle.disabled=m.admin_allowed===false;
              const title=node('span',m.name||m.id);
              const hint=m.admin_allowed===false
                ?node('small',tr('Restricted by administrator','معطّل من الإدارة'))
                :node('small',m.id);
              label.append(toggle,title,hint);
              toggle.addEventListener('change',async()=>{
                const intended=toggle.checked;toggle.disabled=true;
                try{
                  await api('/api/opencode/connections/'+encodeURIComponent(p.id)+'/models',{
                    method:'POST',body:JSON.stringify({model_id:m.id,enabled:intended})
                  });
                  window.nativeDirectTest?.forget({keepSession:true});
                  invalidateOwnedWorkspaceProviders();
                  if(window.refreshWorkspaceChoices)
                    window.refreshWorkspaceChoices('',false).catch(()=>{});
                }catch(error){toggle.checked=!intended;toast(error.message);}
                finally{toggle.disabled=m.admin_allowed===false;}
              });
              rowsBox.append(label);return {label,model:m};
            });
            modelSearch.addEventListener('input',()=>{
              const term=modelSearch.value.trim().toLowerCase();
              for(const {label,model} of items)
                label.hidden=!!term&&!String(model.name||model.id).toLowerCase().includes(term)
                  &&!model.id.toLowerCase().includes(term);
            });
            models.append(node('p',tr('Enable only the models you want in your Workspace.','فعّل النماذج التي تريد ظهورها في مساحة عملك فقط.')),
              modelSearch,rowsBox);
          }catch(error){
            delete details.dataset.modelsLoaded;
            if(details.isConnected)models.textContent=error.message||String(error);
          }
        });
      }
    }
    const renderOptions=()=>{
      const query=(combo.value||'').trim().toLowerCase();
      if(!catalogRequested){
        catalogList.replaceChildren();catalogCount.textContent='';return;
      }
      const rows=(snapshot?.providers||[]).filter(p=>!p.personal_connected&&
        (!query||p.id.toLowerCase().includes(query)||p.name.toLowerCase().includes(query)));
      const selected=selectedProviderId;
      catalogList.replaceChildren(new Option(tr('Select a provider…','اختر المزوّد…'),''),
        ...rows.map(p=>new Option(p.name||p.id,p.id)));
      if(rows.some(p=>p.id===selected))catalogList.value=selected;
      catalogCount.textContent=tr('Providers available: ','المزوّدون المتاحون: ')+rows.length;
      options.hidden=true;combo.setAttribute('aria-expanded','false');
    };
    catalogList.addEventListener('change',()=>{
      const p=(snapshot?.providers||[]).find(row=>row.id===catalogList.value);
      if(p){selectedProviderId=p.id;renderSelected(p);}
    });
    function stopSearch(){searchSequence++;clearTimeout(searchTimer);searchAbort?.abort();searchRows=[];searchQuery='';searchState.textContent='';}
    function scheduleSearch(){
      if(!catalogRequested)return;
      stopSearch();renderOptions();const query=combo.value.trim().toLowerCase();
      if(query.length<2||!view.ready)return;
      const sequence=searchSequence;searchTimer=setTimeout(async()=>{
        searchAbort=new AbortController();searchState.textContent=tr('Searching saved providers…','جارٍ البحث في المزوّدين المحفوظين…');
        try{
          const rows=await lookup('search',query,searchAbort.signal);
          if(sequence!==searchSequence)return;searchRows=rows;searchQuery=query;renderOptions();
          searchState.textContent=rows.length?tr('Saved catalog results','نتائج الفهرس المحفوظ'):tr('No matching provider in the saved catalog.','لا يوجد مزوّد مطابق في الفهرس المحفوظ.');
        }catch(error){if(sequence===searchSequence&&error.name!=='AbortError')searchState.textContent=error.message;}
      },350);
    }
    controller.signal.addEventListener('abort',stopSearch,{once:true});
    async function refresh(force=false){
      if(!alive())return;
      view.ready=false;
      message(tr('Loading saved connections…','جارٍ تحميل الاتصالات المحفوظة…'));
      try{
        const rows=await accountCatalogRows();
        if(!alive()||!contextCurrent())return;
        snapshot={providers:rows};
        view.ready=true;
        renderOptions();renderConnected();renderPlatform();
        const selected=rows.find(p=>p.id===selectedProviderId);
        if(selected)renderSelected(selected);
        if(catalogRequested&&combo.value.trim().length>=2)scheduleSearch();
        if(catalogRequested&&!rows.length){
          message(tr('The Pi catalog has not been stored yet; TEST maintenance will retry automatically.',
            'لم يُحفظ فهرس مزوّدي Pi بعد؛ ستعيد صيانة TEST المحاولة تلقائيًا.'),true);
        }else{
          message(tr('Saved connections ready','الاتصالات المحفوظة جاهزة')+' · '+
            rows.filter(p=>p.personal_connected).length);
        }
      }catch(error){if(alive()){message(error.message,true);renderOptions();}}
    }
    const browse=button(tr('Connect a new provider','ربط مزوّد جديد'),async()=>{
      if(catalogLoading||!alive())return;
      if(catalogRequested){combo.focus();return;}
      catalogLoading=true;browse.disabled=true;
      message(tr('Loading available providers and models…',
        'جارٍ تحميل المزوّدين ونماذجهم…'));
      try{
        // Display the already-saved PostgreSQL snapshot. No user-facing
        // action causes Pi to fetch the multi-provider inventory.
        catalogRequested=true;
        comboWrap.hidden=false;catalogCount.hidden=false;
        catalogList.hidden=false;status.hidden=false;searchState.hidden=true;
        await refresh(true);
      }catch(error){if(alive())message(error.message,true);}
      finally{catalogLoading=false;browse.disabled=false;}
    });
    box.insertBefore(browse,comboWrap);
    // Retry a saved-database read only; automatic maintenance handles Pi.
    retry.onclick=()=>catalogRequested?refresh(true):browse.click();
    function invalidateOwnedWorkspaceProviders(){
      // Account connections are shared across all of this user's workspaces.
      // Clear stale composer snapshots without changing active project/session.
      for(const workspace of workspaces){
        if(workspace?.id)window.workspaceRuntime.invalidate(workspace.id);
      }
    }
    async function reload(){
      invalidateOwnedWorkspaceProviders();
      if(window.refreshWorkspaceChoices)window.refreshWorkspaceChoices('',false).catch(()=>{});
      return refresh(true);
    }
    view.refresh=refresh;
    combo.addEventListener('input',()=>{body.dataset.providerQuery=combo.value;optionsOpen=true;scheduleSearch();});
    combo.addEventListener('focus',()=>{optionsOpen=false;renderOptions();});
    combo.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();optionsOpen=false;stopSearch();options.hidden=true;combo.setAttribute('aria-expanded','false');}});
    document.addEventListener('click',event=>{if(!comboWrap.contains(event.target)){optionsOpen=false;stopSearch();options.hidden=true;combo.setAttribute('aria-expanded','false');}},{signal:controller.signal});
    box.append(button(tr('Refresh saved connections','تحديث الاتصالات المحفوظة'),()=>refresh(true)));
    async function initialize(){
      message(tr('Loading saved connections…','جارٍ تحميل الاتصالات المحفوظة…'));renderOptions();renderConnected();
      // Account discovery must not wait for Python workspace/project requests.
      if(!body.dataset.connectionWorkspace){await refresh();return;}
      try{
        const [owned,projectRows]=await Promise.all([api('/api/workspaces'),api('/api/projects'),window.workspaceContextReady||Promise.resolve()]);
        if(!alive())return;workspaces=owned;projects=projectRows;
        picker.replaceChildren(new Option(tr('Account connections · all projects','اتصالات الحساب · كل المشاريع'),''));
        for(const w of workspaces)picker.add(new Option((projects.find(p=>p.id===w.project_id)?.name||tr('Workspace','مساحة العمل'))+' · '+w.status,w.id));
        // Account connections never depend on a remembered project/runtime.
        const selected=workspaces.find(w=>w.id===body.dataset.connectionWorkspace);
        workspaceId=selected?.id||'';view.workspaceId=workspaceId;picker.value=workspaceId;picker.disabled=false;
        base='/api/workspaces/'+workspaceId+'/providers/';
        if(!workspaceId){await refresh();return;}
        snapshot=window.workspaceRuntime.peek(workspaceId);renderOptions();await refresh();
      }catch(error){if(alive())message(error.message,true);}
    }
    picker.onchange=async()=>{
      const w=workspaces.find(w=>w.id===picker.value);view.ready=false;
      body.dataset.connectionWorkspace=w?.id||'';
      if(!w){await open('providers');return;}
      try{const project=projects.find(p=>p.id===w.project_id)||await api('/api/projects/'+w.project_id);await openWorkspace(project,w,{navigate:false});await open('providers');}catch(error){message(error.message,true);}
    };
    await initialize();
  }

  async function roles(body,platform=false){const box=section(body,tr('User roles','أدوار المستخدمين'));for(const u of await api('/api/admin/users'))row(box,u.username,u.role,[...(currentUser.role==='owner'&&u.id!==currentUser.id&&u.role!=='owner'?[button(tr('Change role','تغيير الدور'),async()=>{const picked=await window.requestForm(tr('Change role','تغيير الدور'),[{name:'role',label:tr('Role','الدور'),value:u.role,options:['admin','support','finance','customer']}]);const role=picked?.role;if(!role)return;await api('/api/admin/users/'+u.id+'/role',{method:'PUT',body:JSON.stringify({role})});await open('roles',true)})]:[])]);box.append(node('p',tr('Only an owner can assign roles. Finance can manage platform payment methods through its authorized API. Support currently has account-only access.','المالك وحده يعيّن الأدوار. دور المالية يتيح إدارة وسائل المنصة عبر واجهته المصرح بها. الدعم يمتلك حاليًا صلاحيات الحساب الشخصي فقط.')))}
  function clientActivityLabel(action){
    const labels={
      'password.changed':['Password changed','تم تغيير كلمة المرور'],
      'password.reset':['Password reset','تمت إعادة تعيين كلمة المرور'],
      'password.recovery_delivery_unavailable':['Password recovery message could not be sent','تعذر إرسال رسالة استعادة كلمة المرور'],
      'session.revoked':['Sign-in session ended','تم إنهاء جلسة دخول'],
      'account.reactivation_verified':['Account reactivation verified','تم تأكيد طلب إعادة تفعيل الحساب'],
      'account.reactivation_completed':['Account reactivated','تمت إعادة تفعيل الحساب'],
      'account.suspended':['Account suspended','تم تعليق الحساب'],
      'account.deletion_requested':['Account deletion requested','تم طلب حذف الحساب'],
      'billing.method_created':['Payment method added','تمت إضافة وسيلة دفع'],
      'billing.method_updated':['Payment method updated','تم تحديث وسيلة الدفع'],
      'billing.method_deleted':['Payment method removed','تم حذف وسيلة الدفع'],
      'github.disconnected':['GitHub disconnected','تم إلغاء ربط GitHub'],
      'role.changed':['Account permissions updated','تم تحديث صلاحيات الحساب'],
      'marketing.opt_in':['Marketing messages enabled','تم تفعيل الرسائل التسويقية'],
      'marketing.opt_out':['Marketing messages disabled','تم إيقاف الرسائل التسويقية']
    };
    return tr(...(labels[String(action).split(':')[0]]||(String(action).startsWith('provider')?['Provider connection activity','نشاط اتصال بأحد المزوّدات']:['Account activity recorded','تم تسجيل نشاط متعلق بالحساب'])));
  }
  async function logs(body,platform=false,securityOnly=false){
    const box=section(body,tr(platform?'Audit log':securityOnly?'Login / security activity':'Account activity',platform?'سجل الإجراءات':securityOnly?'نشاط الدخول والأمان':'نشاط الحساب'));
    const timeline=!platform&&!securityOnly&&Boolean(body.closest('[data-client-panel="account"]'));
    if(securityOnly)box.append(node('p',tr('Recorded password and session security actions. Login event tracking is not available yet.','إجراءات كلمة المرور والجلسات المسجلة. تتبع أحداث تسجيل الدخول غير متاح بعد.')));
    const list=timeline?node('ol','','account-activity-list'):null;if(list)box.append(list);
    let before;
    async function load(){
      const items=await api((platform?'/api/admin/logs':'/api/account/logs')+(before?'?before='+before:''));
      for(const r of items.filter(r=>platform||(/^(password|session|auth|security|role)\./.test(r.action)===securityOnly))){
        if(list){const item=node('li'),icon=node('span','','account-activity-icon');icon.append(gridIcon(String(r.action).startsWith('billing')?'icon-file':'icon-clock'));const text=node('div'),date=node('time',new Date(r.created_at).toLocaleString(lang==='ar'?'ar-u-nu-latn':'en'));date.dateTime=r.created_at;text.append(node('strong',clientActivityLabel(r.action)),date);item.append(icon,text);list.append(item);}
        else row(box,platform?r.action:clientActivityLabel(r.action),new Date(r.created_at).toLocaleString());
      }
      if(list&&!list.children.length&&!box.querySelector('.account-activity-empty'))box.append(node('p',tr('No account activity yet.','لا يوجد نشاط للحساب بعد.'),'account-activity-empty'));
      before=items.at(-1)?.id;more.hidden=items.length<100;
    }
    const more=button(tr('Older records','سجلات أقدم'),load);body.append(more);await load();
  }

  async function locations(body,platform=false){const box=section(body,tr('Locations','المواقع'));let kind='countries',editing=null;const picker=select(box,tr('Type','النوع'),'type',[['countries',tr('Countries','الدول')],['regions',tr('Regions','المناطق')],['cities',tr('Cities','المدن')]]),list=node('div');box.append(list);const editor=section(body,tr('Location details','بيانات الموقع'));let parent;
    const f=form(editor,f=>{input(f,tr('Name','الاسم'),'name').required=true;input(f,tr('Country code','رمز الدولة'),'code');parent=select(f,tr('Parent location','الموقع الأب'),'parent_id',[]);select(f,tr('Enabled','مفعّل'),'enabled',[['true',tr('Yes','نعم')],['false',tr('No','لا')]])},tr('Save','حفظ'),async values=>{values.enabled=values.enabled==='true';values.parent_id=values.parent_id?Number(values.parent_id):null;values.code=values.code||null;await api('/api/admin/locations/'+kind+(editing?'/'+editing:''),{method:editing?'PUT':'POST',body:JSON.stringify(values)});await refresh()});
    const choice=select(list,tr('Choose a location','اختر الموقع'),'selected_location',[['',tr('Select from the list','اختر من القائمة')]]);
    const actions=node('div','','row-between');list.append(actions);
    let records=[];
    function selected(){return records.find(r=>String(r.id)===choice.value)}
    actions.append(
      button(tr('Edit selected','تعديل المحدد'),()=>{
        const r=selected();if(!r)return;
        editing=r.id;
        for(const [k,v] of Object.entries({...r,parent_id:r.country_id||r.region_id||'',enabled:String(r.enabled)}))
          if(f.elements.namedItem(k))f.elements.namedItem(k).value=v;
        f.openDialog();
      }),
      button(tr('Disable selected','تعطيل المحدد'),async()=>{
        const r=selected();if(!r)return;
        await api('/api/admin/locations/'+kind+'/'+r.id,{method:'DELETE'});
        await refresh();
      })
    );
    async function refresh(){
      editing=null;f.reset();parent.replaceChildren(new Option('—',''));
      if(kind!=='countries')for(const p of await api('/api/admin/locations/'+(kind==='regions'?'countries':'regions')))parent.add(new Option(p.name,p.id));
      records=await api('/api/admin/locations/'+kind);
      choice.replaceChildren(new Option(tr('Select from the list','اختر من القائمة'),''));
      for(const r of records)choice.add(new Option(r.name+' · '+(r.enabled?tr('Enabled','مفعّل'):tr('Disabled','معطّل')),String(r.id)));
    }
    picker.onchange=()=>{kind=picker.value;refresh().catch(e=>toast(e.message))};await refresh();
  }
  const github=$('#chatGithub');if(github)github.onclick=()=>open('connections');
  const oldRefreshGit=refreshGit;refreshGit=async function(){await oldRefreshGit();const b=$('#manageProviders');if(b)b.onclick=()=>open('providers')};
  const welcome=$('#welcomePrompt');const connect=button(tr('Connect GitHub · choose repository & branch','اربط GitHub · اختر المستودع والفرع'),()=>open('connections'));connect.classList.add('landing-connect');const logo=document.createElementNS('http://www.w3.org/2000/svg','svg');const use=document.createElementNS('http://www.w3.org/2000/svg','use');use.setAttribute('href','#icon-github');logo.append(use);connect.prepend(logo);welcome.after(connect);
  const recovery=node('section','','manage-card recovery-box');recovery.hidden=true;$('#authPage').append(recovery);let resetToken=new URLSearchParams(location.hash.slice(1)).get('reset-password');if(resetToken)history.replaceState(null,'',location.pathname+location.search);
  const billingPanel=document.querySelector('[data-client-panel=billing]'),billingParent=billingPanel.parentNode,billingNext=billingPanel.nextSibling;
  function restoreBilling(){
    if(billingPanel.parentNode!==billingParent)billingParent.insertBefore(billingPanel,billingNext?.parentNode===billingParent?billingNext:null);
    billingPanel.classList.remove('active');$('#billingCancel').hidden=true;
  }
  function resetRecovery(){restoreBilling();window.passwordRecoveryActive=false;recovery.hidden=true;$('#authPage .auth-shell').hidden=false;}
  function finishPasswordReset(form){
    if(form?.elements?.password)form.elements.password.value='';
    resetToken=null;
    clearAuthenticatedState('authPage');resetRecovery();window.openAuthLogin();
    apiMessage('loginMessage',tr('Password reset. Sign in with your username or email and new password.','تم تعيين كلمة المرور. ادخل باسم المستخدم أو البريد وكلمة المرور الجديدة.'));
  }
  function showRecoveredAccountCode(data){
    // Pending accounts remain inactive until this fresh OTP is verified.
    resetToken=null;window.passwordRecoveryActive=true;
    document.getElementById('authDialog')?.close();
    showPage('authPage');$('#authPage .auth-shell').hidden=true;recovery.hidden=false;
    recovery.replaceChildren(
      node('h2',tr('Confirm your email','تأكيد البريد الإلكتروني')),
      node('p',tr('Enter the six-digit code sent to your email. Your 30-day trial begins only after verification.',
        'أدخل رمز التفعيل المكون من ستة أرقام المرسل إلى بريدك. تبدأ التجربة المجانية لمدة 30 يومًا بعد التحقق.'))
    );
    let challenge=data.verification_challenge;
    form(recovery,f=>{
      const code=input(f,tr('Six-digit activation code','رمز التفعيل المكون من 6 أرقام'),'code','text');
      code.required=true;code.minLength=6;code.maxLength=6;code.pattern='[0-9]{6}';
      code.inputMode='numeric';code.autocomplete='one-time-code';
    },tr('Verify and activate account','التحقق وتفعيل الحساب'),async(values,f)=>{
      const result=await api('/api/auth/verify-email-code',{
        method:'POST',body:JSON.stringify({challenge_id:challenge,code:values.code})});
      f.elements.code.value='';
      resetRecovery();renderProfile(result);
      await openWorkspaceAfterLogin();
    });
    recovery.append(button(tr('Resend activation code','إعادة إرسال رمز التفعيل'),async()=>{
      const result=await api('/api/auth/resend-verification-code',{
        method:'POST',body:JSON.stringify({challenge_id:challenge})});
      challenge=result.verification_challenge;
      toast(tr('A new code was sent to your email.','تم إرسال رمز جديد إلى بريدك المسجّل.'));
    }));
    recovery.append(button(tr('Back to login','العودة لتسجيل الدخول'),()=>closeRecovery().catch(error=>toast(error.message))));
  }
  async function closeRecovery(){
    if(window.reactivationAccount)await window.logoutSession();
    resetToken=null;resetRecovery();window.openAuthLogin();window.scrollTo(0,0);
  }
  window.addEventListener('authentication-cleared',()=>{window.reactivationAccount=null;resetRecovery();});
  window.openReactivation=async()=>{
    await authReady;
    const state=await api('/api/auth/reactivation',{allowAnonymous:true});
    window.reactivationAccount=state;window.passwordRecoveryActive=true;
    document.getElementById('authDialog')?.close();
    showPage('authPage');$('#authPage .auth-shell').hidden=true;recovery.hidden=false;
    // Email verification is complete. Billing is never part of activation.
    restoreBilling();
    recovery.replaceChildren(
      node('h2',tr('Reactivate your account','إعادة تفعيل حسابك')),
      node('p',tr('Email verified. Set a new password to activate your account. Subscription and payment are separate after login.',
        'تم التحقق من البريد. عيّن كلمة مرور جديدة لتفعيل الحساب. الاشتراك والدفع عمليتان منفصلتان بعد الدخول.'))
    );
    form(recovery,f=>{
      const i=input(f,tr('New password: 8+, number and symbol','كلمة مرور جديدة: 8 أحرف ورقم ورمز'),'password','password');
      i.required=true;i.minLength=8;i.maxLength=128;i.autocomplete='new-password';
    },tr('Activate account','تفعيل الحساب'),async(values,f)=>{
      await api('/api/auth/reactivation/password',{method:'POST',body:JSON.stringify(values)});
      f.elements.password.value='';
      window.reactivationAccount=null;
      finishPasswordReset(f);
    });
    recovery.append(button(tr('Back to login','رجوع للدخول'),()=>closeRecovery().catch(error=>toast(error.message))));
  };
  async function recover(reset=false){
    await authReady;window.passwordRecoveryActive=true;document.getElementById('authDialog')?.close();showPage('authPage');$('#authPage .auth-shell').hidden=true;recovery.hidden=false;
    recovery.replaceChildren(node('h2',tr(reset?'Reset password':'Recover password',reset?'إعادة تعيين كلمة المرور':'استعادة كلمة المرور')));
    let archived=false,activationRequired=false;
    if(reset){
      const status=node('p',tr('Checking recovery link…','جارٍ التحقق من رابط الاستعادة…'));status.setAttribute('role','status');recovery.append(status);
      try{const state=await api('/api/auth/recovery-status',{method:'POST',body:JSON.stringify({token:resetToken})});
        archived=state.reactivation_required===true;
        activationRequired=state.account_activation_required===true;status.remove();}
      catch(error){status.textContent=error.message;status.setAttribute('role','alert');recovery.append(button(tr('Back to recovery','العودة للاستعادة'),()=>recover()));return;}
    }
    if(archived){
      recovery.append(node('p',tr('Verify ownership using this email link, then set a new password. Payment is not required for activation.','أثبت ملكية الحساب باستخدام رابط البريد، ثم عيّن كلمة مرور جديدة. الدفع ليس شرطًا للتفعيل.')));
      form(recovery,()=>{},tr('Verify email and continue','إثبات البريد والمتابعة'),async()=>{
        const state=await api('/api/auth/reactivation/verify',{method:'POST',body:JSON.stringify({token:resetToken})});resetToken=null;clearAuthenticatedState();window.reactivationAccount=state;await window.openReactivation();
      });
    }else{
      if(activationRequired)recovery.append(node('p',tr(
        'Your previous account has not been activated. This email link proves mailbox ownership. Set a NEW password to activate the account; the old password will stop working.',
        'حسابك السابق لم يُفعّل بعد. يثبت رابط البريد ملكيتك للعنوان. عيّن كلمة مرور جديدة لتفعيل الحساب؛ لن تبقى كلمة المرور القديمة صالحة.'
      )));
      form(recovery,f=>{const i=input(f,tr(reset?'New password: 8+, number and symbol':'Account email',reset?'كلمة جديدة: 8 أحرف ورقم ورمز':'بريد الحساب'),reset?'password':'email',reset?'password':'email');i.required=true;if(reset){i.minLength=8;i.maxLength=128;i.autocomplete='new-password';}},tr(reset?'Reset':'Send recovery link',reset?'إعادة تعيين':'إرسال رابط الاستعادة'),async(values,f)=>{
        const data=await api(reset?'/api/auth/reset-password':'/api/auth/forgot-password',{method:'POST',body:JSON.stringify(reset?{token:resetToken,password:values.password}:values)});
        if(reset){if(data?.activation_required)showRecoveredAccountCode(data);else finishPasswordReset(f);}
        else toast(tr('If an eligible account matches, a recovery link will be emailed. Archived customers can verify ownership to renew.','إذا وُجد حساب مؤهل، سيُرسل رابط استعادة إلى البريد. يمكن للعميل المؤرشف إثبات الملكية للتجديد.'));
      });
    }
    recovery.append(button(tr('Back to login','رجوع للدخول'),()=>closeRecovery().catch(error=>toast(error.message))));window.scrollTo(0,0);
  }
  const forgot=$('#authForgotPassword');if(forgot){forgot.disabled=false;forgot.textContent=tr('Forgot password?','نسيت كلمة المرور؟');forgot.onclick=()=>recover()}
  window.renderManagement=render;
  window.openManagement=open;
  if(resetToken)recover(true).catch(error=>toast(error.message));
})();
