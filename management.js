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
  const form=(root,fields,label,run)=>{const f=node('form','','manage-form');fields(f);const b=node('button',label,'button');b.type='submit';f.append(b);f.onsubmit=async e=>{e.preventDefault();b.disabled=true;try{await run(Object.fromEntries(new FormData(f)),f);if(f.formDialog?.open)f.formDialog.close()}catch(error){let status=f.querySelector('[role=alert]');if(!status){status=node('p');status.setAttribute('role','alert');f.append(status)}status.textContent=error.message;toast(error.message)}finally{b.disabled=false}};root.append(f);window.mountFormDialog(root,f,root.querySelector('h2')?.textContent||label);if(root.closest('.recovery-box'))f.openDialog();return f};
  const gridMap=new WeakMap();
  const gridIcon=(id,label)=>{const svg=document.createElementNS('http://www.w3.org/2000/svg','svg'),use=document.createElementNS('http://www.w3.org/2000/svg','use');svg.classList.add('ui-icon');svg.setAttribute('aria-hidden','true');use.setAttribute('href','#'+id);svg.append(use);return svg};
  const row=(root,title,detail,actions=[])=>{let grid=gridMap.get(root);if(!grid){const wrap=node('div','','manage-grid-wrap'),table=node('table','','manage-grid'),head=node('thead'),tr=node('tr');for(const label of [trLabel('Record','السجل'),trLabel('Details','التفاصيل'),trLabel('Actions','الإجراءات')])tr.append(node('th',label));head.append(tr);const tbody=node('tbody');table.append(head,tbody);wrap.append(table);root.append(wrap);grid={tbody};gridMap.set(root,grid)}const tr=node('tr','','manage-grid-row'),titleCell=node('th',title),detailCell=node('td',detail),actionCell=node('td'),actionsBox=node('div','','manage-actions');titleCell.scope='row';for(const action of actions){const label=action.textContent.trim();if(!label)continue;const iconId=/delete|disable|disconnect|remove|archive|suspend/i.test(label)?'icon-trash':/edit|change|rename/i.test(label)?'icon-edit':/view|open|details/i.test(label)?'icon-eye':/connect|authorize/i.test(label)?'icon-link':null;if(iconId){action.classList.add('grid-crud-button');action.title=label;action.setAttribute('aria-label',label);const icon=gridIcon(iconId,label);action.replaceChildren(icon)}else action.classList.add('grid-row-action');actionsBox.append(action)}actionCell.append(actionsBox);tr.append(titleCell,detailCell,actionCell);grid.tbody.append(tr)};
  const trLabel=(en,ar)=>lang==='ar'?ar:en;
  function signOut(){window.workspaceRuntime?.clear();currentUser=null;activeWorkspace=null;activeSession=null;activeProject=null;stopEvents();updateNavigation();showPage('authPage')}
  const admin=()=>['admin','owner'].includes(currentUser?.role);

  const main=node('main','','page portal-page');main.id='managementPage';protectedPages.add(main.id);
  const header=node('header','','portal-header');header.append(button(tr('← Back','← رجوع'),()=>page(authenticatedHome())),node('strong','OpenCode Gateway'),button(tr('Workspace','مساحة العمل'),()=>page(activeWorkspace?'workspacePage':'onboarding')));
  const body=node('div','','manage-body');main.append(header,body);document.querySelector('#app-main').append(main);
  async function render(root,name,isPlatform=false){
    await authReady;if(!currentUser)return page('authPage');
    if(isPlatform&&!admin())throw new Error('Administrator access required');
    root.replaceChildren();root.dataset.managementSection=name;
    const loader={security,billing,connections,roles,locations,logs,providers,lifecycle}[name];
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
  async function connections(body,platform=false){const box=section(body,tr('GitHub connections','اتصالات GitHub'));if(platform){for(const c of await api('/api/admin/connections'))row(box,c.login,c.user_id,[button(tr('Disconnect','إلغاء الربط'),async()=>{if(!await window.confirmAction('Disconnect this account?'))return;await api('/api/admin/connections/'+c.user_id,{method:'DELETE'});await open('connections',true)})]);return}
    const status=await api('/api/github/status');row(box,status.account_login||tr('Not connected','غير متصل'),status.configured?tr('GitHub App configured','تطبيق GitHub مهيأ'):tr('Administrator must configure the GitHub App','يجب على الإدارة إعداد تطبيق GitHub'));
    const authorize=button(tr('Authorize GitHub','تفويض GitHub'),()=>{window.location.assign('/api/github/install')});authorize.disabled=!status.configured;box.append(authorize);
    for(const [en,ar] of [['Repositories','المستودعات'],['Branches','الفروع']]){const s=section(body,tr(en,ar));if(!status.connected)s.append(node('p',tr('Connect and authorize GitHub to access your repositories and branches.','اربط GitHub وفوّضه للوصول إلى مستودعاتك وفروعها.')));}
    if(status.connected){box.append(button(tr('Disconnect GitHub','إلغاء ربط GitHub'),async()=>{await api('/api/github/disconnect',{method:'POST'});await open('connections')}));
      const repos=await api('/api/github/repositories');let repository,branch;
      form(box,f=>{repository=select(f,tr('Repository','المستودع'),'repository',[['',tr('Choose repository','اختر مستودعًا')],...repos.map(r=>[r.full_name,r.full_name])]);repository.required=true;branch=select(f,tr('Branch','الفرع'),'branch',[]);branch.required=true;input(f,tr('Project name','اسم المشروع'),'project_name').required=true;repository.onchange=async()=>{branch.replaceChildren();if(!repository.value)return;try{for(const b of await api('/api/github/branches?repository='+encodeURIComponent(repository.value)))branch.add(new Option(b.name,b.name))}catch(e){toast(e.message)}}},tr('Create workspace','إنشاء مساحة عمل'),async values=>{const result=await api('/api/projects',{method:'POST',body:JSON.stringify({...values,source_type:'github'})});await openWorkspace(result.project,result.workspace)});
    }
  }
  async function providers(body,platform=false){
    body.replaceChildren();
    const workspaceSettings=section(body,tr('Runtime / workspace settings','إعدادات وقت تشغيل مساحة العمل'));
    const [workspaces,projects]=await Promise.all([api('/api/workspaces'),api('/api/projects')]);
    const picker=select(workspaceSettings,tr('Workspace','مساحة العمل'),'workspace',[['',tr('Select workspace','اختر مساحة عمل')],...workspaces.map(w=>[w.id,(projects.find(p=>p.id===w.project_id)?.name||tr('Workspace','مساحة العمل'))+' · '+w.status])]);
    picker.value=activeWorkspace?.id||'';
    picker.onchange=async()=>{const w=workspaces.find(w=>w.id===picker.value);if(!w)return;try{activeWorkspace=w;activeProject=projects.find(p=>p.id===w.project_id);activeSession=null;stopEvents();await providers(body,platform);}catch(error){toast(error.message);}};
    if(!activeWorkspace){workspaceSettings.append(node('p',tr('Select a workspace to inspect OpenCode.','اختر مساحة عمل لفحص OpenCode.')));return;}
    const workspaceId=activeWorkspace.id,base='/api/workspaces/'+workspaceId+'/providers/';
    let snapshot=await window.workspaceRuntime.load(workspaceId);
    if(activeWorkspace?.id!==workspaceId)return;
    const box=section(body,tr('OpenCode providers','مزوّدو OpenCode'));body.insertBefore(box,body.firstChild);
    const list=select(box,tr('Provider','المزوّد'),'provider',[]),credentialArea=node('div','','provider-credential-area');box.append(credentialArea);
    const capabilities=section(body,tr('OpenCode workspace capabilities','خصائص مساحة OpenCode'));
    const summary=node('p'),details=node('details'),detailTitle=node('summary',tr('Providers, agents, models, sessions, permissions and tools','المزوّدون والوكلاء والنماذج والجلسات والصلاحيات والأدوات')),metadata=node('pre');details.append(detailTitle,metadata);capabilities.append(summary,details);
    async function refresh(preferred=list.value){
      window.workspaceRuntime.invalidate(workspaceId);snapshot=await window.workspaceRuntime.load(workspaceId,{force:true});
      if(activeWorkspace?.id!==workspaceId)return;
      populate(preferred);
      if(window.refreshWorkspaceChoices)await window.refreshWorkspaceChoices(preferred,false);
    }
    function populate(preferred=''){
      list.replaceChildren(new Option(tr('Choose a provider','اختر مزوّدًا'),''));
      for(const p of snapshot.providers||[])list.add(new Option(p.name+' · '+(p.connected?tr('Connected','متصل'):tr('Not connected','غير متصل'))+(p.allowed===false?tr(' · Restricted by platform',' · مقيّد من المنصة'):''),p.id));
      list.value=preferred;summary.textContent='OpenCode '+snapshot.version+' · '+snapshot.status+' · '+snapshot.workspace_id;
      // Safe metadata only; the backend never returns auth credentials or private paths.
      metadata.textContent='';details.ontoggle=()=>{if(details.open)metadata.textContent=JSON.stringify({identity:snapshot.identity,generation:snapshot.generation,health:snapshot.health,config:snapshot.config,providers:snapshot.providers,auth_methods:snapshot.auth_methods,agents:snapshot.agents,default_agent:snapshot.default_agent,sessions:snapshot.sessions,permissions:snapshot.permissions,questions:snapshot.questions,session_status:snapshot.session_status,tools:snapshot.tools,tool_policy:snapshot.tool_policy,vcs:snapshot.vcs,mcp:snapshot.mcp,lsp:snapshot.lsp,formatters:snapshot.formatters,errors:snapshot.errors},null,2);};if(details.open)details.ontoggle();
      renderCredential();
    }
    function renderCredential(){
      credentialArea.replaceChildren();const provider=snapshot.providers?.find(p=>p.id===list.value);if(!provider)return;
      credentialArea.append(node('p',provider.connected?tr('Connected in this OpenCode workspace','متصل في مساحة OpenCode هذه'):tr('Not connected in this OpenCode workspace','غير متصل في مساحة OpenCode هذه')));
      const models=node('details'),modelTitle=node('summary',tr('Models and provider metadata','النماذج وبيانات المزوّد')),modelData=node('pre',JSON.stringify(provider,null,2));models.append(modelTitle,modelData);credentialArea.append(models);
      if(provider.allowed===false){credentialArea.append(node('p',tr('Available in OpenCode; restricted by platform policy.','متاح في OpenCode؛ مقيّد بسياسة المنصة.')));return;}
      if(provider.connected){credentialArea.append(button(tr('Disconnect provider','فصل المزوّد'),async()=>{await api(base+encodeURIComponent(provider.id),{method:'DELETE'});await refresh(provider.id);}));return;}
      if(snapshot.auth_methods===null){credentialArea.append(node('p',tr('OpenCode authentication discovery failed. Refresh the workspace before connecting.','تعذر اكتشاف طرق مصادقة OpenCode. حدّث مساحة العمل قبل الربط.')));return;}
      const methods=snapshot.auth_methods?.[provider.id]||[];
      // OpenCode's supported /auth endpoint accepts native API keys when no plugin
      // contributes custom methods. Keep the returned auth_methods catalog intact.
      const choices=methods.length?methods:[{type:'api',label:tr('OpenCode API key endpoint','نقطة مصادقة API key في OpenCode')}];
      const methodPicker=select(credentialArea,tr('OpenCode authentication method','طريقة مصادقة OpenCode'),'auth_method',choices.map((m,i)=>[String(i),m.label||m.type]));
      const methodArea=node('div');credentialArea.append(methodArea);
      function renderMethod(){
        methodArea.replaceChildren();const index=Number(methodPicker.value),method=choices[index];
        if(!['api','oauth'].includes(method.type)){methodArea.append(node('p',tr('This authentication type is not supported by the installed OpenCode HTTP API: ','نوع المصادقة غير مدعوم في واجهة OpenCode المثبتة: ')+method.type));return;}
        const f=node('form','','manage-form');methodArea.append(f);const promptInputs=[];
        for(const prompt of method.prompts||[]){
          let field;if(prompt.type==='select')field=select(f,prompt.message,prompt.key,prompt.options.map(o=>[o.value,o.label]));
          else if(prompt.type==='text'){field=input(f,prompt.message,prompt.key);field.placeholder=prompt.placeholder||'';}
          else {f.append(node('p',tr('Unsupported auth prompt: ','حقل مصادقة غير مدعوم: ')+prompt.type));continue;}
          promptInputs.push({prompt,field});
        }
        const updatePrompts=()=>{const values=Object.fromEntries(new FormData(f));for(const {prompt,field} of promptInputs){const condition=prompt.when;field.parentElement.hidden=Boolean(condition)&&(condition.op==='eq'?values[condition.key]!==condition.value:values[condition.key]===condition.value);field.disabled=field.parentElement.hidden;}};
        f.addEventListener('change',updatePrompts);updatePrompts();
        if(method.type==='api'){
          const key=input(f,tr('API key (server-side only)','مفتاح API (على الخادم فقط)'),'api_key','password');key.required=true;key.autocomplete='new-password';
          const model=select(f,tr('Model for real credential validation (may incur usage)','نموذج للتحقق الحقيقي من المفتاح (قد يحتسب استخدامًا)'),'model_id',(provider.models||[]).filter(m=>m.allowed!==false&&(!m.modalities?.output||m.modalities.output.includes('text'))).map(m=>[m.id,m.name||m.id]));
          model.required=true;if(provider.default_model)model.value=provider.default_model;
        }
        const submit=node('button',method.type==='api'?tr('Validate and connect','تحقق واربط'):tr('Authorize with OpenCode','تفويض عبر OpenCode'),'button');submit.type='submit';f.append(submit);
        f.onsubmit=async event=>{event.preventDefault();submit.disabled=true;try{
          const values=Object.fromEntries(new FormData(f));
          if(method.type==='api'){
            await api(base+encodeURIComponent(provider.id)+'/credentials',{method:'POST',body:JSON.stringify({api_key:values.api_key,model_id:values.model_id,...(methods.length?{method:index}:{}),inputs:Object.fromEntries(promptInputs.filter(({field})=>!field.disabled).map(({prompt,field})=>[prompt.key,field.value]))})});f.reset();await refresh(provider.id);
          }else{
            const authorization=await api(base+encodeURIComponent(provider.id)+'/oauth/authorize',{method:'POST',body:JSON.stringify({method:index,inputs:values})});
            f.remove();const area=node('div');methodArea.append(area);area.append(node('p',authorization.instructions||''));
            if(authorization.url){const url=new URL(authorization.url);if(url.protocol!=='https:'||['localhost','127.0.0.1','::1'].includes(url.hostname))throw new Error('OpenCode returned an unsupported authorization URL');const link=node('a',tr('Open provider authorization','افتح تفويض المزوّد'));link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';area.append(link);}
            let code;if(authorization.method==='code'){const label=node('label',tr('Authorization code','رمز التفويض'));code=node('input');code.autocomplete='off';label.append(code);area.append(label);}
            area.append(button(tr('Complete authorization','أكمل التفويض'),async()=>{await api(base+encodeURIComponent(provider.id)+'/oauth/callback',{method:'POST',body:JSON.stringify({method:index,...(code?{code:code.value}:{})})});if(code)code.value='';await refresh(provider.id);}));
          }
        }catch(error){toast(error.message);}finally{submit.disabled=false;}};
      }
      methodPicker.onchange=renderMethod;renderMethod();
    }
    list.onchange=renderCredential;populate();
    capabilities.append(button(tr('Refresh OpenCode state','حدّث حالة OpenCode'),()=>refresh()));
  }
  async function roles(body,platform=false){const box=section(body,tr('User roles','أدوار المستخدمين'));for(const u of await api('/api/admin/users'))row(box,u.username,u.role,[...(currentUser.role==='owner'&&u.id!==currentUser.id&&u.role!=='owner'?[button(tr('Change role','تغيير الدور'),async()=>{const picked=await window.requestForm(tr('Change role','تغيير الدور'),[{name:'role',label:tr('Role','الدور'),value:u.role,options:['admin','support','finance','customer']}]);const role=picked?.role;if(!role)return;await api('/api/admin/users/'+u.id+'/role',{method:'PUT',body:JSON.stringify({role})});await open('roles',true)})]:[])]);box.append(node('p',tr('Only an owner can assign roles. Finance can manage platform payment methods through its authorized API. Support currently has account-only access.','المالك وحده يعيّن الأدوار. دور المالية يتيح إدارة وسائل المنصة عبر واجهته المصرح بها. الدعم يمتلك حاليًا صلاحيات الحساب الشخصي فقط.')))}
  async function logs(body,platform=false,securityOnly=false){const box=section(body,tr(platform?'Audit log':securityOnly?'Login / security activity':'Account activity',platform?'سجل الإجراءات':securityOnly?'نشاط الدخول والأمان':'نشاط الحساب'));if(securityOnly)box.append(node('p',tr('Recorded password and session security actions. Login event tracking is not available yet.','إجراءات كلمة المرور والجلسات المسجلة. تتبع أحداث تسجيل الدخول غير متاح بعد.')));let before;async function load(){const items=await api((platform?'/api/admin/logs':'/api/account/logs')+(before?'?before='+before:''));for(const r of items.filter(r=>platform||(/^(password|session|auth|security|role)\./.test(r.action)===securityOnly)))row(box,r.action,new Date(r.created_at).toLocaleString());before=items.at(-1)?.id;more.hidden=items.length<100}const more=button(tr('Older records','سجلات أقدم'),load);body.append(more);await load()}
  async function locations(body,platform=false){const box=section(body,tr('Locations','المواقع'));let kind='countries',editing=null;const picker=select(box,tr('Type','النوع'),'type',[['countries',tr('Countries','الدول')],['regions',tr('Regions','المناطق')],['cities',tr('Cities','المدن')]]),list=node('div');box.append(list);const editor=section(body,tr('Location details','بيانات الموقع'));let parent;
    const f=form(editor,f=>{input(f,tr('Name','الاسم'),'name').required=true;input(f,tr('Country code','رمز الدولة'),'code');parent=select(f,tr('Parent location','الموقع الأب'),'parent_id',[]);select(f,tr('Enabled','مفعّل'),'enabled',[['true',tr('Yes','نعم')],['false',tr('No','لا')]])},tr('Save','حفظ'),async values=>{values.enabled=values.enabled==='true';values.parent_id=values.parent_id?Number(values.parent_id):null;values.code=values.code||null;await api('/api/admin/locations/'+kind+(editing?'/'+editing:''),{method:editing?'PUT':'POST',body:JSON.stringify(values)});await refresh()});
    async function refresh(){editing=null;f.reset();list.replaceChildren();parent.replaceChildren(new Option('—',''));if(kind!=='countries')for(const p of await api('/api/admin/locations/'+(kind==='regions'?'countries':'regions')))parent.add(new Option(p.name,p.id));for(const r of await api('/api/admin/locations/'+kind))row(list,r.name,r.enabled?tr('Enabled','مفعّل'):tr('Disabled','معطّل'),[button(tr('Edit','تعديل'),()=>{editing=r.id;for(const [k,v] of Object.entries({...r,parent_id:r.country_id||r.region_id||'',enabled:String(r.enabled)}))if(f.elements.namedItem(k))f.elements.namedItem(k).value=v;f.openDialog()}),button(tr('Disable','تعطيل'),async()=>{await api('/api/admin/locations/'+kind+'/'+r.id,{method:'DELETE'});await refresh()})])}
    picker.onchange=()=>{kind=picker.value;refresh().catch(e=>toast(e.message))};await refresh();
  }
  const github=$('#chatGithub');if(github)github.onclick=()=>open('connections');
  const oldRefreshGit=refreshGit;refreshGit=async function(){await oldRefreshGit();const b=$('#manageProviders');if(b)b.onclick=()=>open('providers')};
  const welcome=$('#welcomePrompt');const connect=button(tr('Connect GitHub · choose repository & branch','اربط GitHub · اختر المستودع والفرع'),()=>open('connections'));connect.classList.add('landing-connect');const logo=document.createElementNS('http://www.w3.org/2000/svg','svg');const use=document.createElementNS('http://www.w3.org/2000/svg','use');use.setAttribute('href','#icon-github');logo.append(use);connect.prepend(logo);welcome.after(connect);
  const tools=node('div','','manage-actions workspace-links');tools.append(button(tr('Switch workspace','تبديل مساحة العمل'),()=>window.openClientView('projects')),button(tr('Another repository','مستودع آخر'),()=>page('onboarding')));$('#promptForm').before(tools);
  const recovery=node('section','','manage-card recovery-box');recovery.hidden=true;$('#authPage').append(recovery);let resetToken=new URLSearchParams(location.hash.slice(1)).get('reset-password');if(resetToken)history.replaceState(null,'',location.pathname+location.search);
  function closeRecovery(){window.passwordRecoveryActive=false;recovery.hidden=true;$('#authPage .auth-shell').hidden=false;window.scrollTo(0,0)}
  function recover(reset=false){window.passwordRecoveryActive=true;document.getElementById('authDialog')?.close();showPage('authPage');$('#authPage .auth-shell').hidden=true;recovery.hidden=false;recovery.replaceChildren(node('h2',tr(reset?'Reset password':'Recover password',reset?'إعادة تعيين كلمة المرور':'استعادة كلمة المرور')));form(recovery,f=>{const i=input(f,tr(reset?'New password: 8+, number and symbol':'Account email',reset?'كلمة جديدة: 8 أحرف ورقم ورمز':'بريد الحساب'),reset?'password':'email',reset?'password':'email');i.required=true;if(reset)i.minLength=8},tr(reset?'Reset':'Send recovery link',reset?'إعادة تعيين':'إرسال رابط الاستعادة'),async values=>{const data=await api(reset?'/api/auth/reset-password':'/api/auth/forgot-password',{method:'POST',body:JSON.stringify(reset?{token:resetToken,password:values.password}:values)});toast(data.message);if(reset){resetToken=null;closeRecovery();signOut()}});recovery.append(button(tr('Back to login','رجوع للدخول'),closeRecovery));window.scrollTo(0,0)}
  const forgot=$('#authPage .auth-form .text-link');if(forgot){forgot.disabled=false;forgot.textContent=tr('Forgot password?','نسيت كلمة المرور؟');forgot.onclick=()=>recover()}
  window.renderManagement=render;
  window.openManagement=open;
  if(resetToken)recover(true);
})();
