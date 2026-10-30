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
  const header=node('header','','portal-header');header.append(button(tr('← Back','← رجوع'),()=>page(authenticatedHome())),node('strong','OpenCode Gateway'),button(tr('Workspace','مساحة العمل'),()=>page(activeWorkspace?'workspacePage':'onboarding')));
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
    if(!platform||!admin())return;
    const box=section(body,tr('Native catalog maintenance','صيانة فهرس OpenCode'));
    const note=node('p',tr('Uses OpenCode’s own cache refresh. The running service may retain its current model snapshot; conversations are not restarted.','يستخدم تحديث Cache الأصلي في OpenCode. قد تحتفظ الخدمة الجارية بفهرسها الحالي؛ لا تُعاد تشغيل المحادثات.'));box.append(note);
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
    const editor=section(body,tr('Add or edit method','إضافة وسيلة أو تعديلها'));
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

    for(const m of items)row(box,m.label,m.kind+' · '+(m.enabled?tr('Enabled','مفعّل'):tr('Disabled','معطّل')),[button(tr('Edit','تعديل'),()=>{editing=m.id;f.reset();for(const [k,v] of Object.entries({...m.details,kind:m.kind,label:m.label,enabled:String(m.enabled)}))if(f.elements.namedItem(k))f.elements.namedItem(k).value=v;methodFields();f.openDialog()}),button(tr('Delete','حذف'),async()=>{if(!await window.confirmAction(tr('Delete saved method?','حذف الوسيلة المحفوظة؟')))return;await api('/api/billing/methods/'+m.id+query,{method:'DELETE'});await open('billing',platform)})]);
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
    const box=section(body,tr('Connect an AI provider','ربط مزوّد ذكاء'));
    box.append(node('p',tr('Popular providers and your connected providers are shown first. Search or add another provider by name. Connect once for your account and use it across your projects.','تظهر المزوّدات الشائعة والمتصلة أولاً. ابحث أو أضف مزوّدًا آخر باسمه. اربط المزوّد مرة لحسابك واستخدمه في مشاريعك.')));
    const comboWrap=node('div','','provider-combo'),combo=node('input');combo.type='search';
    combo.value=body.dataset.providerQuery||'';combo.placeholder=tr('Search providers…','ابحث عن المزوّدات…');combo.setAttribute('role','combobox');combo.setAttribute('aria-expanded','false');combo.autocomplete='off';combo.setAttribute('aria-label',combo.placeholder);
    const options=node('div','','provider-combo-options');options.hidden=true;comboWrap.append(combo,options);box.append(comboWrap);
    const progress=node('p','','provider-loading');progress.setAttribute('role','status');progress.setAttribute('aria-live','polite');box.append(progress);
    const status=node('p',tr('Choose a provider to inspect its connection.','اختر مزوّدًا لفحص اتصاله.'),'provider-combo-status');box.append(status);
    const connectedBox=section(body,tr('Connected providers','المزوّدات المتصلة'));
    const contextCurrent=()=>!workspaceId||activeWorkspace?.id===workspaceId;
    let workspaceId=view.workspaceId,base='/api/workspaces/'+workspaceId+'/providers/';
    let snapshot=workspaceId?window.workspaceRuntime.peek(workspaceId):null,metadataReady=false,workspaces=[],projects=[],selectedProviderId='';
    let searchRows=[],searchQuery='',searchTimer=null,searchAbort=null,searchSequence=0,optionsOpen=false;
    const searchState=node('p','','provider-search-status');searchState.setAttribute('role','status');comboWrap.after(searchState);
    // The main catalog stays at 50. Every other Native ID/name is available
    // through manual resolution; connected providers have their own section.
    const sameCatalog=data=>data.workspace_id===workspaceId&&data.generation===snapshot?.generation&&data.revision===snapshot?.revision&&data.policy_revision===snapshot?.policy_revision;
    async function lookup(kind,value,signal){
      if(!workspaceId){
        if(kind==='resolve'){const result=await api('/api/opencode/catalog/providers/resolve?name='+encodeURIComponent(value),{signal});if(!alive()||!contextCurrent())throw new DOMException('Workspace changed','AbortError');return [result];}
        const url='/api/opencode/catalog/providers/page?limit=50&query='+encodeURIComponent(value);
        const result=await api(url,{signal});
        if(!alive()||!contextCurrent())throw new DOMException('Workspace changed','AbortError');
        return result.items;
      }
      const data=await api(base+kind+'?'+(kind==='search'?'query':'name')+'='+encodeURIComponent(value),{signal});
      if(!alive()||!contextCurrent())throw new DOMException('Workspace changed','AbortError');
      if(!data.native&&!sameCatalog(data)){
        view.ready=false;customButton.disabled=true;window.workspaceRuntime.invalidate(workspaceId);
        message(tr('OpenCode state changed. Refresh before connecting.','تغيّرت حالة OpenCode. حدّث الحالة قبل الربط.'),true);
        throw new Error(tr('OpenCode state changed. Close this dialog and refresh before connecting.','تغيّرت حالة OpenCode. أغلق النافذة وحدّث الحالة قبل الربط.'));
      }
      return data.providers;
    }
    const retry=button(tr('Retry','إعادة المحاولة'),()=>metadataReady?refresh(true):initialize());retry.hidden=true;box.append(retry);
    const message=(text,error=false)=>{progress.textContent=text;progress.classList.toggle('connection-error',error);retry.hidden=!error;};
    const setFeedback=(element,text,kind='status')=>{
      element.textContent=text;element.hidden=!text;element.dataset.kind=kind;
      element.setAttribute('role',kind==='error'?'alert':'status');element.setAttribute('aria-live',kind==='error'?'assertive':'polite');
    };
    const showError=(f,error)=>{let st=f.querySelector('.provider-feedback');if(!st){st=node('p','','provider-feedback');f.append(st)}setFeedback(st,error.message,'error')};
    const openAuthDialog=async(p,resolved=false)=>{
      const reauthorizing=!workspaceId&&p.reauthorize===true;
      if(!view.ready||!alive()||!contextCurrent()||view.connecting)return;
      view.connecting=true;
      const host=node('div');document.body.append(host);
      const dlg=document.createElement('dialog');dlg.className='action-form-dialog provider-auth-dialog';dlg.dataset.formDialog='';
      dlg.addEventListener('keydown',event=>event.stopPropagation());
      const head=document.createElement('header');head.className='action-dialog-head';
      const heading=node('h2',tr('Connect ','ربط ')+(p.name||p.id));heading.id='provider-auth-'+(crypto.randomUUID?.()||Date.now());dlg.setAttribute('aria-labelledby',heading.id);head.append(heading);
      const close=document.createElement('button');close.type='button';close.className='icon';close.textContent='×';close.setAttribute('aria-label',tr('Close','إغلاق'));close.onclick=()=>dlg.close();head.append(close);
      const body=document.createElement('div');body.className='action-dialog-body';
      const methodArea=node('div');body.append(methodArea);
      const feedback=node('p','','provider-feedback');feedback.hidden=true;body.append(feedback);
      const foot=document.createElement('div');foot.className='action-form-actions';
      const cancel=document.createElement('button');cancel.type='button';cancel.className='button ghost';cancel.textContent=tr('Cancel','إلغاء');cancel.onclick=()=>dlg.close();foot.append(cancel);
      dlg.append(head,body,foot);host.append(dlg);
      const discovery=new AbortController(),onAbort=()=>dlg.close();controller.signal.addEventListener('abort',onAbort,{once:true});
      dlg.addEventListener('close',()=>{discovery.abort();controller.signal.removeEventListener('abort',onAbort);for(const input of dlg.querySelectorAll('input[type=password]'))input.value='';view.connecting=false;host.remove();},{once:true});
      const currentDialog=()=>alive()&&contextCurrent()&&dlg.open;
      body.append(node('p',tr('Credentials are stored on the server. Configuration alone does not verify provider access; test it with a native prompt.','تُحفظ الاعتمادات على الخادم. حفظ الإعداد لا يثبت صلاحية الوصول؛ تحقّق بإرسال طلب أصلي.')));
      dlg.showModal();setFeedback(feedback,tr('Loading OpenCode authentication methods…','جارٍ تحميل طرق مصادقة OpenCode…'));
      let choices,accountOptions=null;
      try{
        if(!workspaceId){const authStarted=performance.now();accountOptions=await api("/api/opencode/connections/"+encodeURIComponent(p.id)+"/options",{signal:discovery.signal});window.gatewayProviderTimings={...window.gatewayProviderTimings,auth_request_ms:performance.now()-authStarted};}
        else {if(!resolved)p=(await lookup('resolve',p.id,discovery.signal))[0];if(snapshot?.native)accountOptions=await api('/api/opencode/connections/'+encodeURIComponent(p.id)+'/options',{signal:discovery.signal});}
        if(!currentDialog())return;
        if(p.allowed===false)throw new Error(tr('This provider is restricted by platform policy.','هذا المزوّد مقيّد بسياسة المنصة.'));
        choices=accountOptions?accountOptions.auth_methods:p.auth_methods;
        if(!Array.isArray(choices)||!choices.length)throw new Error(tr('No authentication methods reported by OpenCode.','لم يعلن OpenCode عن طرق مصادقة.'));
        setFeedback(feedback,'');
      }catch(error){if(currentDialog()&&error.name!=='AbortError')setFeedback(feedback,error.message,'error');return;}
      const methodPicker=select(body,tr('OpenCode authentication method','طريقة مصادقة OpenCode'),'auth_method',choices.map((m,i)=>[String(i),m.label||(['api','key'].includes(m.type)?tr('API key','مفتاح API'):m.type)]));
      if(reauthorizing){
        for(const option of [...methodPicker.options])if(choices[Number(option.value)]?.type!=='oauth')option.remove();
        if(!methodPicker.options.length){setFeedback(feedback,tr('No OAuth method is available.','لا توجد طريقة OAuth متاحة.'),'error');return;}
        methodPicker.value=methodPicker.options[0].value;
      }
      body.prepend(methodPicker.parentElement);
      function renderMethod(){
        methodArea.replaceChildren();setFeedback(feedback,'');const index=Number(methodPicker.value),method=choices[index];
        const keyMethod=['api','key'].includes(method.type);
        if(!keyMethod&&method.type!=='oauth'){setFeedback(feedback,tr('This authentication type is not supported by the installed OpenCode HTTP API: ','نوع المصادقة غير مدعوم في واجهة OpenCode المثبتة: ')+method.type,'warning');return;}
        const f=node('form','','manage-form');methodArea.append(f);const promptInputs=[];
        for(const prompt of method.prompts||[]){
          let field;if(prompt.type==='select')field=select(f,prompt.message,prompt.key,prompt.options.map(o=>[o.value,o.label]));
          else if(prompt.type==='text'){field=input(f,prompt.message,prompt.key);field.placeholder=prompt.placeholder||'';}
          else{setFeedback(feedback,tr('Unsupported auth prompt: ','حقل مصادقة غير مدعوم: ')+prompt.type,'warning');continue;}
          promptInputs.push({prompt,field});
        }
        const updatePrompts=()=>{const values=Object.fromEntries(new FormData(f));for(const {prompt,field} of promptInputs){const condition=prompt.when;field.parentElement.hidden=Boolean(condition)&&(condition.op==='eq'?values[condition.key]!==condition.value:values[condition.key]===condition.value);field.disabled=field.parentElement.hidden;}};
        f.addEventListener('change',updatePrompts);updatePrompts();
        let submitting=false;
        if(keyMethod&&accountOptions?.credential_storage_ready===false){setFeedback(feedback,tr('Provider connection is unavailable: secure credential storage needs administrator repair. Your API key has not been rejected by the provider.','الربط غير متاح: التخزين الآمن للاعتمادات يحتاج إصلاحًا من المدير. لم يرفض المزوّد مفتاح API الخاص بك.'),'error');return;}
        if(keyMethod){
          const key=input(f,tr('API key (server-side only)','مفتاح API (على الخادم فقط)'),'api_key','password');key.required=true;key.autocomplete='new-password';
          f.append(node('p',accountOptions?.native?tr('OpenCode stores the credential. Verify access with a native conversation; saving does not test a paid model.','يحفظ OpenCode الاعتماد. تحقّق من الوصول بمحادثة أصلية؛ الحفظ لا يختبر نموذجًا مدفوعًا.'):tr('OpenCode validates the key with a real model request. Provider charges may apply.','يتحقق OpenCode من المفتاح بطلب نموذج فعلي؛ قد تُحتسب رسوم لدى المزوّد.'),'provider-note'));
        }
        const submit=node('button',keyMethod?(accountOptions?.native?tr('Connect provider','ربط المزوّد'):tr('Validate and connect','تحقق واربط')):tr('Authorize with OpenCode','تفويض عبر OpenCode'),'button');submit.type='submit';f.append(submit);
        const currentForm=()=>currentDialog()&&view.ready&&methodArea.contains(f);
        f.onsubmit=async event=>{
          event.preventDefault();if(submitting||!currentForm()||!f.reportValidity())return;
          const values=Object.fromEntries(new FormData(f));submitting=true;submit.disabled=methodPicker.disabled=true;f.setAttribute('aria-busy','true');
          try{
            if(keyMethod){
              setFeedback(feedback,tr('Saving the credential through OpenCode…','جارٍ حفظ المفتاح عبر OpenCode…'));
              const result=await api((workspaceId?base:'/api/opencode/connections/')+encodeURIComponent(p.id)+'/credentials',{method:'POST',body:JSON.stringify({api_key:values.api_key,model_id:null,method:index,inputs:Object.fromEntries(promptInputs.filter(({field})=>!field.disabled).map(({prompt,field})=>[prompt.key,field.value]))})});
              f.reset();if(!alive()||!contextCurrent())return;
              if(result.connected!==true||result.persisted!==true)throw new Error(tr('OpenCode connection and credential storage were not confirmed.','لم يتم تأكيد اتصال OpenCode وحفظ المفتاح.'));
              dlg.close();toast(result.verified===false?tr('Credential configured. Send a native prompt to verify access.','حُفظ الاعتماد. أرسل طلبًا أصليًا للتحقق من صلاحية الوصول.'):tr('Provider connected.','تم ربط المزوّد.'));await reload();
            }else{
              setFeedback(feedback,tr('Starting OpenCode authorization…','جارٍ بدء تفويض OpenCode…'));
              const authorization=await api((workspaceId?base:'/api/opencode/connections/')+encodeURIComponent(p.id)+'/oauth/authorize',{method:'POST',body:JSON.stringify({method:index,inputs:values,...(reauthorizing?{reauthorize:true}:{})})});
              if(!currentForm())return;
              if(!authorization||!['auto','code'].includes(authorization.method))throw new Error(tr('OpenCode did not return a supported OAuth authorization flow.','لم يُرجع OpenCode مسار تفويض OAuth مدعومًا.'));
              let url;if(authorization.url){url=new URL(authorization.url);if(url.protocol!=='https:'||['localhost','127.0.0.1','::1'].includes(url.hostname))throw new Error(tr('OpenCode returned an unsupported authorization URL','أعاد OpenCode رابط تفويض غير مدعوم'));}
              const area=node('div','','provider-oauth');f.replaceWith(area);setFeedback(feedback,'');area.append(node('p',authorization.instructions||''));
              if(url){const link=node('a',tr('Open provider authorization','افتح تفويض المزوّد'));link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';area.append(link);}
              let code;if(authorization.method==='code')code=input(area,tr('Authorization code','رمز التفويض'),'code');
              area.append(button(tr('Complete authorization','أكمل التفويض'),async()=>{
                if(!currentDialog()||!view.ready)return;
                setFeedback(feedback,tr('Completing OpenCode authorization…','جارٍ إكمال تفويض OpenCode…'));
                try{
                  const result=await api((workspaceId?base:'/api/opencode/connections/')+encodeURIComponent(p.id)+'/oauth/callback',{method:'POST',body:JSON.stringify({method:index,...(code?{code:code.value}:{})})});
                  if(!alive()||!contextCurrent())return;
                  if(result.connected!==true)throw new Error(tr('OpenCode did not confirm the OAuth connection.','لم يؤكد OpenCode اتصال OAuth.'));
                  if(code)code.value='';dlg.close();toast(result.deferred_workspace_count?tr('Connected; refresh active workspaces to synchronize.','تم الربط؛ حدّث مساحات العمل النشطة للمزامنة.'):tr('Provider connected.','تم ربط المزوّد.'));await reload();
                }catch(error){if(currentDialog())setFeedback(feedback,error.message,'error');}
              }));
            }
          }catch(error){
            window.workspaceRuntime.invalidate(workspaceId);
            if(currentDialog())setFeedback(feedback,error.message,'error');
            if(alive()&&contextCurrent()&&window.refreshWorkspaceChoices)window.refreshWorkspaceChoices('',false).catch(()=>{});
          }finally{submitting=false;f.removeAttribute('aria-busy');methodPicker.disabled=false;submit.disabled=false;}
        };
      }
      methodPicker.onchange=renderMethod;renderMethod();methodPicker.focus();
    };
    function renderSelected(p){
      const state=p.auth_status==='reauthorization_required'?tr('Authorization required','يلزم إعادة التفويض'):
        p.auth_status==='refresh_required'?tr('Token expired · refresh or reauthorize','انتهى التوكن · جدّد أو أعد التفويض'):p.verified===true?tr('Tested','تم اختباره'):p.auth_status==='configured'?tr('Configured · not tested','مهيأ · لم يُختبر'):p.connected?tr('Connected · not tested','متصل · لم يُختبر'):tr('Disconnected','غير متصل');
      const restriction=p.allowed===false?' · '+tr('Restricted','مقيّد'):'';
      status.replaceChildren(node('strong',p.name||p.id),node('span',state+restriction+' · '+String(p.model_count??p.models?.length??0)+' '+tr('models','نموذج')));
      if(!view.ready){status.append(node('span',tr('Refreshing workspace state…','جارٍ تحديث حالة مساحة العمل…')));return;}
      const act=node('div','','manage-actions');
      if(p.connected)act.append(button(tr('Disconnect / delete key','فصل / حذف المفتاح'),()=>disconnect(p)));
      else if(p.allowed!==false)act.append(button(tr('Connect','ربط'),()=>openAuthDialog(p)));
      else act.append(node('span',tr('Restricted by platform policy','مقيّد بسياسة المنصة')));
      if(!workspaceId&&p.auth_type==='oauth'&&p.allowed!==false)act.append(button(tr('Reauthorize','إعادة التفويض'),()=>openAuthDialog({...p,reauthorize:true})));
      status.append(act);
    }
    async function disconnect(p){
      if(!alive()||!contextCurrent()||!view.ready)return;
      await api(workspaceId?base+encodeURIComponent(p.id):
        '/api/opencode/connections/'+encodeURIComponent(p.id),{method:'DELETE'});
      if(!alive()||!contextCurrent())return;
      view.ready=false;
      snapshot={...snapshot,providers:snapshot.providers.map(row=>row.id===p.id?{...row,connected:false}:row)};
      searchRows=searchRows.map(row=>row.id===p.id?{...row,connected:false}:row);
      renderConnected();renderOptions();
      if(selectedProviderId===p.id)renderSelected({...p,connected:false});
      toast(tr('Provider disconnected. Its saved key was deleted.','فُصل المزوّد وحُذف مفتاحه المحفوظ.'));await reload();
    }
    function renderConnected(){
      connectedBox.replaceChildren(node('h2',tr('Connected providers','المزوّدات المتصلة')));
      const selected=(snapshot?.providers||[]).find(p=>p.id===selectedProviderId);
      if(selected)renderSelected(selected);
      const rows=(snapshot?.providers||[]).filter(p=>p.connected);
      if(!rows.length){connectedBox.append(node('p',tr('No connected providers.','لا توجد مزوّدات متصلة.')));return;}
      for(const p of rows){
        const item=node('div','','manage-actions');item.append(node('strong',p.name||p.id),node('span',p.verified===true?tr('Tested','تم اختباره'):tr('Configured · not tested','مهيأ · لم يُختبر')));
        if(p.allowed===false)item.append(node('span',tr('Restricted','مقيّد')));
        const remove=button(tr('Disconnect / delete key','فصل / حذف المفتاح'),()=>disconnect(p));remove.disabled=!view.ready;item.append(remove);connectedBox.append(item);
      }
    }
    const renderOptions=()=>{
      const renderStarted=performance.now();
      const query=(combo.value||'').trim().toLowerCase();const previous=new Map([...options.children].map(n=>[n.dataset.providerId,n]));
      const available=[...(snapshot?.providers||[]),...(searchQuery===query?searchRows:[])];
      const rows=[...new Map(available.map(p=>[p.id,p])).values()].filter(p=>(query||p.visible!==false)&&(!query||(p.name||'').toLowerCase().includes(query)||(p.id||'').toLowerCase().includes(query))).slice(0,50);
      for(const p of rows){
        const state=p.verified===true?tr('Tested','تم اختباره'):p.auth_status==='configured'?tr('Configured · not tested','مهيأ · لم يُختبر'):p.connected?tr('Connected · not tested','متصل · لم يُختبر'):tr('Disconnected','غير متصل');
        const restriction=p.allowed===false?' · '+tr('Restricted','مقيّد'):'';
        const o=previous.get(p.id)||node('button','','provider-combo-option');previous.delete(p.id);o.dataset.providerId=p.id;o.textContent=(p.name||p.id)+' · '+state+restriction;o.type='button';
        o.onclick=()=>{
          if(!alive()||!contextCurrent())return;
          combo.value='';body.dataset.providerQuery='';optionsOpen=false;options.hidden=true;combo.setAttribute('aria-expanded','false');
          stopSearch();
          selectedProviderId=p.id;renderSelected(p);
        };
        options.append(o);
      }
      for(const old of previous.values())old.remove();
      options.hidden=!optionsOpen||!rows.length;combo.setAttribute('aria-expanded',String(!options.hidden));
      window.gatewayProviderTimings={...window.gatewayProviderTimings,render_sync_ms:performance.now()-renderStarted,rendered_options:rows.length};
    };
    function stopSearch(){searchSequence++;clearTimeout(searchTimer);searchAbort?.abort();searchRows=[];searchQuery='';searchState.textContent='';}
    function scheduleSearch(){
      stopSearch();renderOptions();const query=combo.value.trim().toLowerCase();
      if(query.length<2||!view.ready)return;
      const sequence=searchSequence;searchTimer=setTimeout(async()=>{
        searchAbort=new AbortController();searchState.textContent=tr('Searching OpenCode providers…','جارٍ البحث في مزوّدي OpenCode…');
        try{
          const rows=await lookup('search',query,searchAbort.signal);
          if(sequence!==searchSequence)return;searchRows=rows;searchQuery=query;renderOptions();
          searchState.textContent=rows.length?tr('OpenCode search results','نتائج بحث OpenCode'):tr('No matching OpenCode provider. Enter its exact name or ID with Add custom provider.','لا يوجد مزوّد مطابق. أدخل الاسم أو المعرّف الدقيق عبر إضافة مزوّد مخصص.');
        }catch(error){if(sequence===searchSequence&&error.name!=='AbortError')searchState.textContent=error.message;}
      },350);
    }
    controller.signal.addEventListener('abort',stopSearch,{once:true});
    const customButton=button(tr('Add Provider Manually','إضافة مزوّد يدويًا'),()=>{
      const host=node('div'),f=node('form','','manage-form');
      const pid=input(f,tr('Provider name or ID','اسم المزوّد أو معرّفه'),'provider_id');pid.required=true;pid.maxLength=200;pid.placeholder='OpenAI / openai / …';
      f.append(node('p',tr('Search any provider in OpenCode by its original name or ID. Saving credentials configures the connection; a native prompt is required to test access.','ابحث عن أي مزوّد في OpenCode باسمه أو معرّفه الأصلي. حفظ الاعتماد يهيئ الاتصال؛ يلزم طلب أصلي لاختبار صلاحية الوصول.')));
      const validationState=node('p','','provider-feedback');setFeedback(validationState,'');f.append(validationState);
      const save=node('button',tr('Choose authentication method','اختر طريقة المصادقة'),'button');save.type='submit';f.append(save);host.append(f);document.body.append(host);
      const dlg=window.mountFormDialog(host,f,tr('Add Provider Manually','إضافة مزوّد يدويًا'));dlg.classList.add('provider-auth-dialog');f.dialogTrigger.hidden=true;
      dlg.addEventListener('keydown',event=>event.stopPropagation());
      const current=()=>alive()&&view.ready&&contextCurrent()&&dlg.open;
      f.onsubmit=async event=>{
        event.preventDefault();if(!current()||save.disabled||!f.reportValidity())return;save.disabled=true;setFeedback(validationState,tr('Checking the OpenCode provider…','جارٍ فحص المزوّد في OpenCode…'));
        try{
          const rows=await lookup('resolve',pid.value.trim());if(!current())return;const p=rows[0];if(!p)throw new Error(tr('Provider was not found in OpenCode.','المزوّد غير موجود في OpenCode.'));
          if(p.allowed===false)throw new Error(tr('This provider is restricted by platform policy.','هذا المزوّد مقيّد بسياسة المنصة.'));
          selectedProviderId=p.id;dlg.close();await openAuthDialog(p,true);
        }catch(error){if(error.name!=='AbortError')showError(f,error);}finally{save.disabled=false;}
      };
      dlg.addEventListener('close',()=>host.remove(),{once:true});f.openDialog();
    });customButton.disabled=true;box.append(customButton);
    async function refresh(force=false){
      if(!alive())return;
      if(!workspaceId){
        view.ready=false;
        message(tr('Loading account providers…','جارٍ تحميل مزوّدات الحساب…'));
        try{
          const catalog=await api('/api/opencode/catalog/providers/page?limit=50&offset=0',{signal:controller.signal});
          if(!alive()||workspaceId)return;
          snapshot={providers:[...new Map([...(catalog.items||[]),...(catalog.connected_items||[])].map(p=>[p.id,p])).values()]};
          view.ready=true;customButton.disabled=false;
          renderOptions();renderConnected();
          message(tr('OpenCode providers ready','مزوّدو OpenCode جاهزون')+' · '+catalog.total);
          const selected=snapshot.providers.find(p=>p.id===selectedProviderId);if(selected)renderSelected(selected);
        }catch(error){if(alive()&&error.name!=='AbortError')message(error.message,true);}
        return;
      }
      view.ready=false;customButton.disabled=true;
      status.querySelectorAll('button').forEach(button=>button.disabled=true);
      renderConnected();
      message(snapshot?tr('Refreshing OpenCode providers…','جارٍ تحديث مزوّدي OpenCode…'):tr('Loading OpenCode providers…','جارٍ تحميل مزوّدي OpenCode…'));
      try{
        if(force)window.workspaceRuntime.invalidate(workspaceId);
        const next=await window.workspaceRuntime.load(workspaceId,{force});
        if(!alive()||!contextCurrent())return;
        if(next.providers===null)throw new Error(next.errors?.provider_data?.detail||'OpenCode provider discovery failed');
        snapshot=next;view.ready=true;customButton.disabled=false;
        message(tr('Popular and connected OpenCode providers ready','المزوّدات الشائعة والمتصلة جاهزة')+' · '+snapshot.providers.length);renderOptions();renderConnected();
        let selected=snapshot.providers.find(p=>p.id===selectedProviderId);
        if(!selected&&selectedProviderId){try{selected=(await lookup('resolve',selectedProviderId))[0];}catch(error){if(error.name!=='AbortError')status.textContent=error.message;}}
        if(selected)renderSelected(selected);if(combo.value.trim().length>=2)scheduleSearch();
        if(window.refreshWorkspaceChoices)window.refreshWorkspaceChoices('',false).catch(()=>{});
      }catch(error){if(alive()){message(error.message,true);renderOptions();}}
    }
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
    combo.addEventListener('focus',()=>{optionsOpen=true;scheduleSearch();});
    combo.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();optionsOpen=false;stopSearch();options.hidden=true;combo.setAttribute('aria-expanded','false');}});
    document.addEventListener('click',event=>{if(!comboWrap.contains(event.target)){optionsOpen=false;stopSearch();options.hidden=true;combo.setAttribute('aria-expanded','false');}},{signal:controller.signal});
    box.append(button(tr('Refresh OpenCode state','حدّث حالة OpenCode'),()=>metadataReady?refresh(true):initialize()));
    async function initialize(){
      message(snapshot?tr('Refreshing OpenCode providers…','جارٍ تحديث OpenCode…'):tr('Loading OpenCode providers…','جارٍ تحميل مزوّدي OpenCode…'));renderOptions();renderConnected();
      // Account discovery must not wait for Python workspace/project requests.
      if(!body.dataset.connectionWorkspace){await refresh();return;}
      try{
        const [owned,projectRows]=await Promise.all([api('/api/workspaces'),api('/api/projects'),window.workspaceContextReady||Promise.resolve()]);
        if(!alive())return;workspaces=owned;projects=projectRows;metadataReady=true;
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
  async function closeRecovery(){
    if(window.reactivationAccount)await window.logoutSession();
    resetToken=null;resetRecovery();window.openAuthLogin();window.scrollTo(0,0);
  }
  window.addEventListener('authentication-cleared',()=>{window.reactivationAccount=null;resetRecovery();});
  window.openReactivation=async()=>{
    await authReady;
    const state=await api('/api/auth/reactivation',{allowAnonymous:true});window.reactivationAccount=state;window.passwordRecoveryActive=true;
    document.getElementById('authDialog')?.close();showPage('authPage');$('#authPage .auth-shell').hidden=true;recovery.hidden=false;
    restoreBilling();recovery.replaceChildren(node('h2',tr('Reactivate your account','إعادة تفعيل حسابك')),
      node('p',tr('Email ownership verified. This short-lived session allows renewal only; workspace access remains unavailable.','تم إثبات ملكية البريد. تسمح هذه الجلسة القصيرة بالتجديد فقط؛ الوصول لمساحة العمل غير متاح.')));
    if(state.payment_verified){
      recovery.append(node('p',tr('Payment verified. Set a fresh password, then sign in normally.','تم التحقق من الدفع. عيّن كلمة مرور جديدة ثم سجّل الدخول بالطريقة المعتادة.')));
      form(recovery,f=>{const i=input(f,tr('New password: 8+, number and symbol','كلمة جديدة: 8 أحرف ورقم ورمز'),'password','password');i.required=true;i.minLength=8;i.maxLength=128;i.autocomplete='new-password';},tr('Set password','تعيين كلمة المرور'),async(values,f)=>{
        await api('/api/auth/reactivation/password',{method:'POST',body:JSON.stringify(values)});f.elements.password.value='';
        await window.logoutSession();resetRecovery();toast(tr('Account reactivated. Sign in with your fresh password.','تمت إعادة تفعيل الحساب. سجّل الدخول بكلمة المرور الجديدة.'));
      });
    }else{
      billingPanel.classList.add('active');$('#billingCancel').hidden=true;recovery.append(billingPanel);
      await window.loadReactivationBilling();await window.loadReactivationOrders();
      recovery.append(button(tr('Check payment status','التحقق من حالة الدفع'),()=>window.openReactivation().catch(error=>{apiMessage('billingMessage',error.message,true)})));
    }
    recovery.append(button(tr('Exit / request a new recovery link','خروج / طلب رابط استعادة جديد'),()=>closeRecovery().catch(error=>toast(error.message))));
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
      recovery.append(node('p',tr('Your preserved account is archived. Verify ownership to renew; normal access requires verified payment and a fresh password.','حسابك المحفوظ مؤرشف. أثبت الملكية للتجديد؛ يتطلب الدخول العادي دفعًا موثّقًا وكلمة مرور جديدة.')));
      form(recovery,()=>{},tr('Verify email and renew','إثبات البريد والتجديد'),async()=>{
        const state=await api('/api/auth/reactivation/verify',{method:'POST',body:JSON.stringify({token:resetToken})});resetToken=null;clearAuthenticatedState();window.reactivationAccount=state;await window.openReactivation();
      });
    }else{
      if(activationRequired)recovery.append(node('p',tr(
        'Your previous account has not been activated. This email link proves mailbox ownership. Set a NEW password to activate the account; the old password will stop working.',
        'حسابك السابق لم يُفعّل بعد. يثبت رابط البريد ملكيتك للعنوان. عيّن كلمة مرور جديدة لتفعيل الحساب؛ لن تبقى كلمة المرور القديمة صالحة.'
      )));
      form(recovery,f=>{const i=input(f,tr(reset?'New password: 8+, number and symbol':'Account email',reset?'كلمة جديدة: 8 أحرف ورقم ورمز':'بريد الحساب'),reset?'password':'email',reset?'password':'email');i.required=true;if(reset){i.minLength=8;i.maxLength=128;i.autocomplete='new-password';}},tr(reset?'Reset':'Send recovery link',reset?'إعادة تعيين':'إرسال رابط الاستعادة'),async(values,f)=>{
        const data=await api(reset?'/api/auth/reset-password':'/api/auth/forgot-password',{method:'POST',body:JSON.stringify(reset?{token:resetToken,password:values.password}:values)});
        if(reset){finishPasswordReset(f);}
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
