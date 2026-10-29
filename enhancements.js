// Local Gateway enhancements. Loaded after app.js; it upgrades existing views with
// real backend data (client dashboard, GitHub connection, provider credentials, push)
// without altering the current layout or markup.
// One explicit fresh link for admin and legacy dashboard entry points.
let freshGithubPending=false;
window.startFreshGithubConnection=async function(options={}){
  const tr=(en,ar)=>lang==='ar'?ar:en;
  if(freshGithubPending)return;
  const owner=currentUser?.id;
  if(!owner)return;
  const valid=()=>currentUser?.id===owner&&(!options.isCurrent||options.isCurrent());
  freshGithubPending=true;
  try{
    // Same-tab redirect avoids stranded about:blank windows and ambiguity
    // between the user's Gateway account and a separate OAuth popup.
    const next=await api('/api/github/connect',{method:'POST'});
    if(!valid())return;
    const target=new URL(next.url);
    if(target.protocol!=='https:'||target.hostname!=='github.com'||
       target.pathname!=='/login/oauth/authorize')
      throw new Error(tr('Invalid GitHub authorization address.','عنوان تفويض GitHub غير صالح.'));
    // Returning through /api/github/callback restores the Gateway page.
    window.location.assign(target.href);
  }catch(error){
    toast(error.message);
  }finally{
    freshGithubPending=false;
  }
};
// Discard displayed connection metadata in this and other tabs after mutation.
window.addEventListener('storage',event=>{
  if(event.key==='og-github-revision:'+currentUser?.id)window.dispatchEvent(new CustomEvent('gateway-github-changed',{detail:{owner:currentUser?.id}}));
});
window.addEventListener('gateway-github-changed',event=>{
  if(event.detail?.owner!==currentUser?.id)return;
  for(const id of ['connectionsGithub','clientGithubPanel']){
    const box=document.getElementById(id);if(box)box.replaceChildren(textElement('p',lang==='ar'?'تغير اتصال GitHub. افتح الاتصالات للتحقق.':'GitHub connection changed. Reopen Connections to verify.'));
  }
});
// One explicit review for customer, admin and legacy Disconnect entry points.
window.disconnectGithubWithReview=async function(){
  if(window.githubDisconnectReviewOpen)return false;
  const owner=currentUser?.id,tr=(en,ar)=>lang==='ar'?ar:en;
  if(!owner)return false;
  window.githubDisconnectReviewOpen=true;
  let dialog;
  try{
    const plan=await api('/api/github/disconnect/workspaces');
    if(currentUser?.id!==owner)return false;
    dialog=document.createElement('dialog');dialog.className='manage-card';
    dialog.style.cssText='width:min(680px,92vw);max-height:85vh;overflow:auto;box-sizing:border-box';
    dialog.setAttribute('aria-labelledby','githubDisconnectTitle');
    const title=textElement('h3',tr('Disconnect GitHub','فصل GitHub'));title.id='githubDisconnectTitle';
    dialog.append(title,textElement('p',tr('Revoke this GitHub account’s authorization for this app. Select imported copies to save and delete, or preserve them for 73 hours. Unsaved work stays protected. Internal projects and conversations remain.','إلغاء تفويض حساب GitHub لهذا التطبيق. اختر نسخ المشاريع لحفظها وحذفها، أو احتفظ بها 73 ساعة. تبقى التعديلات غير المحفوظة محمية، والمشاريع الداخلية والمحادثات محفوظة.')));
    const selected=[],table=document.createElement('table'),head=document.createElement('thead'),hr=document.createElement('tr');
    for(const label of [tr('Select','اختيار'),tr('Project / destination','المشروع / وجهة الحفظ'),tr('Review','المراجعة')])hr.append(textElement('th',label));head.append(hr);table.append(head);
    const tbody=document.createElement('tbody');table.append(tbody);
    for(const copy of plan.workspaces){
      const row=document.createElement('tr'),choice=document.createElement('input');choice.type='checkbox';choice.checked=!copy.blocked;choice.disabled=!!copy.blocked;choice.setAttribute('aria-label',copy.name);
      const cell=document.createElement('td');cell.append(choice);row.append(cell);
      const name=textElement('td',copy.name+' · '+copy.repository+' → '+copy.branch),review=document.createElement('td');name.style.overflowWrap='anywhere';
      if(copy.blocked)review.textContent=copy.blocked;
      else{
        const details=document.createElement('details');details.append(textElement('summary',copy.changes.length+tr(' changed files',' ملفات متغيرة')+' · '+(copy.ahead??'?')+tr(' unpushed commits',' commits غير مرفوعة')));
        const list=document.createElement('ul');list.style.cssText='max-height:160px;overflow:auto;overflow-wrap:anywhere';
        for(const item of copy.changes)list.append(textElement('li',item.status+' '+item.path));details.append(list);review.append(details);
      }
      row.append(name,review);tbody.append(row);selected.push({copy,choice});
    }
    const wrap=document.createElement('div');wrap.style.overflowX='auto';wrap.append(table);if(plan.workspaces.length)dialog.append(wrap);
    const feedback=textElement('p');feedback.setAttribute('role','status');feedback.setAttribute('aria-live','polite');
    const save=textElement('button',tr('Save to GitHub, delete selected copies and disconnect','حفظ إلى GitHub وحذف النسخ المختارة ثم الفصل'),'button');
    const keep=textElement('button',tr('Disconnect and keep files for 73 hours','فصل والاحتفاظ بالملفات 73 ساعة'),'button ghost');
    const cancel=textElement('button',tr('Cancel','إلغاء'),'button ghost');for(const b of [save,keep,cancel])b.type='button';
    save.disabled=!selected.some(x=>!x.copy.blocked);
    dialog.append(feedback,save,keep,cancel);document.body.append(dialog);dialog.showModal();
    return await new Promise(resolve=>{
      let busy=false,deleted=0;
      const finish=value=>{dialog.close();resolve(value);};
      cancel.onclick=()=>{if(!busy)finish(false);};
      dialog.oncancel=event=>{event.preventDefault();if(!busy)finish(false);};
      const execute=async remove=>{
        if(busy||currentUser?.id!==owner)return;
        const copies=selected.filter(x=>x.choice.checked&&!x.copy.blocked).map(x=>x.copy);
        if(remove&&!copies.length){feedback.textContent=tr('Select at least one working copy.','اختر نسخة مشروع واحدة على الأقل.');return;}
        busy=true;save.disabled=keep.disabled=cancel.disabled=true;
        try{
          const message=remove?tr('Commit and push the reviewed changes to the listed branches, verify them, then permanently delete these LOCAL copies: ','حفظ التعديلات ومزامنتها إلى الفروع المعروضة والتحقق منها، ثم حذف هذه النسخ المحلية نهائيًا: ')+copies.map(x=>x.name).join(', '):tr('Revoke the GitHub grant for this account and app? Files remain; GitHub’s browser login is unaffected.','إلغاء تفويض حساب GitHub لهذا التطبيق؟ تبقى الملفات، ولا يتغير تسجيل دخول GitHub في المتصفح.');
          if(!await window.confirmAction(message))return;
          for(const copy of remove?copies:[]){
            if(currentUser?.id!==owner)throw Error(tr('Account changed; operation stopped.','تغير الحساب؛ توقفت العملية.'));
            feedback.textContent=tr('Saving and verifying: ','حفظ والتحقق: ')+copy.name;
            const path='/api/github/disconnect/workspaces/'+encodeURIComponent(copy.id);
            const saved=await api(path,{method:'POST',body:JSON.stringify({connection_id:plan.connection_id,snapshot:copy.snapshot,action:'save'})});
            if(!saved.verified||!saved.snapshot)throw Error(tr('Remote save was not verified. Files preserved.','لم يُثبت الحفظ البعيد؛ الملفات محفوظة.'));
            if(currentUser?.id!==owner)throw Error(tr('Account changed; files preserved.','تغير الحساب؛ الملفات محفوظة.'));
            const result=await api(path,{method:'POST',body:JSON.stringify({connection_id:plan.connection_id,snapshot:saved.snapshot,action:'delete'})});
            if(!result.deleted)throw Error(tr('Local cleanup was not confirmed.','لم يُؤكد حذف النسخة المحلية.'));deleted++;
          }
          if(currentUser?.id!==owner)throw Error(tr('Account changed; operation stopped.','تغير الحساب؛ توقفت العملية.'));
          const result=await api('/api/github/disconnect',{method:'POST',body:JSON.stringify({connection_id:plan.connection_id})});
          toast(result.grant_revocation==='verified'?tr('Disconnected. GitHub grant revoked.','تم الفصل وإلغاء تفويض GitHub.'):tr('Disconnected locally. GitHub grant revocation needs review.','تم الفصل محليًا؛ إلغاء تفويض GitHub يحتاج مراجعة.'));
          finish(true);
        }catch(error){feedback.textContent=error.message+(deleted?tr(' Verified local copies already removed: ',' عدد النسخ المحفوظة التي حُذفت بالفعل: ')+deleted:'');}
        finally{busy=false;save.disabled=!selected.some(x=>!x.copy.blocked);keep.disabled=cancel.disabled=false;}
      };
      save.onclick=()=>execute(true);keep.onclick=()=>execute(false);
    });
  }catch(error){toast(error.message);return false;}
  finally{if(dialog)dialog.remove();window.githubDisconnectReviewOpen=false;}
};

// Explicit server-verified identity confirmation shared by customer/admin views.
window.renderGithubConfirmation=function(root,status,refresh){
  if(!status.pending)return;
  const item=status.pending,owner=currentUser?.id,tr=(en,ar)=>lang==='ar'?ar:en;
  const errorText=error=>{
    if(lang!=='ar')return error.message;
    if(error.message.startsWith('This GitHub account is already connected'))return 'حساب GitHub هذا مرتبط حاليًا بحساب آخر في OpenCode Gateway، ولا يمكن ربطه بحسابين في الوقت نفسه.\n\nيرجى تسجيل الدخول إلى حساب Gateway المرتبط بهذا GitHub وإجراء Disconnect أولًا، أو اختيار حساب GitHub آخر.\n\nتسجيل الخروج وحده لا يفصل ربط GitHub.';
    if(error.message.startsWith('GitHub email could not be verified'))return 'تعذر التحقق من البريد. راجع البريد الأساسي لحساب GitHub الذي اخترته.';
    if(error.message.startsWith('GitHub email verification is unavailable'))return 'التحقق من بريد GitHub غير متاح. يلزم فحص صلاحية قراءة البريد وخدمة الإرسال.';
    if(error.message==='Incorrect GitHub verification code')return 'رمز التحقق من GitHub غير صحيح.';
    if(error.message.startsWith('GitHub code is expired'))return 'رمز GitHub منتهي أو غير متاح. اطلب رمزًا جديدًا.';
    if(error.message.startsWith('GitHub connection verification is disabled'))return 'خدمة التحقق من ربط GitHub معطلة من الإدارة؛ لا يمكن إنشاء ربط جديد.';
    if(error.message.startsWith('Wait before requesting'))return 'انتظر قبل محاولة التحقق من بريد GitHub مرة أخرى.';
    if(error.message.startsWith('Verify the code sent'))return 'تحقق من رمز بريد GitHub قبل تأكيد الربط.';
    return error.message;
  };
  const box=textElement('section','','manage-card github-confirmation');
  box.setAttribute('aria-label',tr('Confirm GitHub identity','تأكيد هوية GitHub'));
  box.append(textElement('h3',tr('Confirm the GitHub account','تأكيد حساب GitHub')),
    textElement('p',tr('You are linking @','أنت تربط @')+item.github_login+tr(' to this Gateway account. Continue only if this is your intended account.',' بحسابك الحالي في Gateway. أكمل فقط إذا كان هذا الحساب الذي تقصده.')));
  const select=document.createElement('select');select.setAttribute('aria-label',tr('Authorized installation','التثبيت المصرح به'));
  select.add(new Option(tr('Select your installation','اختر التثبيت الخاص بك'),''));
  for(const installation of item.installations)select.add(new Option(installation.login+' · '+installation.id,String(installation.id)));
  const accepted=document.createElement('input');accepted.type='checkbox';
  const label=textElement('label');label.append(accepted,document.createTextNode(tr('I confirm @','أؤكد اختيار @')+item.github_login));
  const feedback=textElement('p');feedback.setAttribute('role','status');
  const confirm=textElement('button',tr('Confirm connection','تأكيد الربط'),'button');confirm.type='button';confirm.disabled=true;
  let emailVerified=item.email_verification?.verified===true;
  const update=()=>{confirm.disabled=!accepted.checked||!select.value||!emailVerified;};select.onchange=update;accepted.onchange=update;
  confirm.onclick=async()=>{
    if(confirm.disabled||currentUser?.id!==owner)return;
    confirm.disabled=true;
    try{await api('/api/github/confirm',{method:'POST',body:JSON.stringify({connection_id:item.connection_id,github_user_id:item.github_user_id,installation_id:Number(select.value)})});
      if(currentUser?.id===owner){toast(tr('GitHub connection confirmed.','تم تأكيد ربط GitHub.'));await refresh();}
    }catch(error){if(currentUser?.id===owner){feedback.textContent=errorText(error);update();}}
  };
  const cancel=textElement('button',tr('Cancel / choose another account','إلغاء / اختيار حساب آخر'),'button ghost');cancel.type='button';
  cancel.onclick=async()=>{if(currentUser?.id!==owner)return;cancel.disabled=true;try{await api('/api/github/disconnect',{method:'POST',body:JSON.stringify({connection_id:item.connection_id})});if(currentUser?.id===owner)await refresh();}catch(error){feedback.textContent=errorText(error);cancel.disabled=false;}};
  {
    const proof=textElement('section','','github-email-proof');
    proof.append(textElement('h4',tr('Verify GitHub account ownership','التحقق من ملكية حساب GitHub')),
      textElement('p',tr('Enter the primary email associated with the GitHub account you selected, which may differ from your Gateway email. We will match it with GitHub and send a verification code before connecting.','أدخل البريد الإلكتروني الأساسي لحساب GitHub الذي اخترته، وقد يختلف عن بريد تسجيلك في Gateway. سنتحقق من مطابقته ثم نرسل رمز تحقق قبل إكمال الربط.')));
    const emailLabel=textElement('label',tr('GitHub primary email','البريد الإلكتروني الأساسي المرتبط بحساب GitHub'));
    const email=document.createElement('input');email.type='email';email.autocomplete='off';email.required=true;email.maxLength=254;email.setAttribute('aria-label',tr('GitHub primary email','البريد الإلكتروني الأساسي المرتبط بحساب GitHub'));emailLabel.append(email);
    const send=textElement('button',tr('Verify email and send code','التحقق من البريد وإرسال الرمز'),'button ghost');send.type='button';
    const code=document.createElement('input');code.type='text';code.inputMode='numeric';code.autocomplete='one-time-code';code.maxLength=6;code.pattern='[0-9]{6}';code.setAttribute('aria-label',tr('GitHub email verification code','رمز التحقق من بريد GitHub'));code.hidden=emailVerified;
    const verify=textElement('button',tr('Verify code','تحقق من الرمز'),'button');verify.type='button';verify.hidden=emailVerified;
    const note=textElement('p',emailVerified?tr('GitHub email verified.','تم التحقق من بريد GitHub.'):'');note.setAttribute('role','status');
    const countdown=textElement('p','','github-email-countdown');countdown.setAttribute('role','status');countdown.setAttribute('aria-live','off');
    let expiryTimer=null;
    let expiresAt=Date.parse(item.email_verification?.expires_at||'');
    const stopCountdown=()=>{if(expiryTimer!==null){document.defaultView?.clearInterval(expiryTimer);expiryTimer=null;}};
    const tickCountdown=()=>{
      if(!proof.isConnected||currentUser?.id!==owner){stopCountdown();return;}
      if(emailVerified||!Number.isFinite(expiresAt)){countdown.textContent='';return;}
      const seconds=Math.max(0,Math.ceil((expiresAt-Date.now())/1000));
      countdown.textContent=seconds
        ?tr('Verification code expires in '+seconds+'s.','تنتهي صلاحية رمز GitHub بعد '+seconds+' ثانية.')
        :tr('Code expired. Request a new code.','انتهت صلاحية رمز GitHub؛ اطلب رمزًا جديدًا.');
      verify.disabled=seconds===0;send.disabled=seconds>0;
    };
    const startCountdown=()=>{
      stopCountdown();
      if(!Number.isFinite(expiresAt)||emailVerified)return;
      tickCountdown();
      expiryTimer=document.defaultView?.setInterval(tickCountdown,1000);
    };
    send.onclick=async()=>{
      if(send.disabled||currentUser?.id!==owner)return;if(!email.reportValidity())return;send.disabled=true;emailVerified=false;update();
      try{const result=await api('/api/github/pending/email/send',{method:'POST',body:JSON.stringify({connection_id:item.connection_id,email:email.value.trim()})});if(currentUser?.id!==owner)return;
        if(result.sent!==true||!Number.isFinite(Date.parse(result.expires_at)))throw Error(tr('Verification expiry was not confirmed. Try again.','لم يتم تأكيد وقت انتهاء الرمز؛ أعد المحاولة.'));
        expiresAt=Date.parse(result.expires_at);
        emailVerified=false;update();code.value='';code.hidden=verify.hidden=false;note.textContent=tr('Email matched. Verification code sent.','تمت مطابقة البريد وإرسال رمز التحقق.');startCountdown();code.focus();
      }catch(error){note.textContent=errorText(error);}finally{send.disabled=Number.isFinite(expiresAt)&&!emailVerified&&Date.now()<expiresAt;}
    };
    verify.onclick=async()=>{
      if(verify.disabled||currentUser?.id!==owner)return;
      if(!/^[0-9]{6}$/.test(code.value)){note.textContent=tr('Enter the six-digit code.','أدخل الرمز المكوّن من ستة أرقام.');return;}
      if(!emailVerified&&Number.isFinite(expiresAt)&&expiresAt<=Date.now()){note.textContent=tr('Code expired; request a new one.','انتهت صلاحية الرمز؛ اطلب رمزًا جديدًا.');tickCountdown();return;}
      verify.disabled=true;
      try{const result=await api('/api/github/pending/email/verify',{method:'POST',body:JSON.stringify({connection_id:item.connection_id,code:code.value})});if(currentUser?.id!==owner)return;
        emailVerified=result.verified===true;update();if(emailVerified){stopCountdown();countdown.textContent='';email.value='';code.value='';code.hidden=verify.hidden=true;send.textContent=tr('Send a fresh code','إرسال رمز جديد');note.textContent=tr('GitHub email verified. Confirm the account below.','تم التحقق من بريد GitHub. أكّد الحساب أدناه.');}
      }catch(error){note.textContent=errorText(error);}finally{verify.disabled=false;}
    };
    proof.append(emailLabel,send,code,verify,countdown,note);box.append(proof);

    if(item.installations.length)box.append(select,label,confirm);
  }
  if(!item.installations.length){
    box.append(textElement('p',tr('This account has no authorized installation of this app. Install it on your own repositories first.','لا يوجد تثبيت مصرح لهذا التطبيق على هذا الحساب. ثبّته على مستودعاتك أولًا.')));
    const install=textElement('button',tr('Install on my GitHub account','تثبيت على حسابي في GitHub'),'button');install.type='button';
    install.onclick=async()=>{if(currentUser?.id!==owner||install.disabled)return;install.disabled=true;
      try{const next=await api('/api/github/pending/install',{method:'POST',body:JSON.stringify({connection_id:item.connection_id})});if(currentUser?.id!==owner)return;const url=new URL(next.url);if(url.protocol!=='https:'||url.hostname!=='github.com'||!url.pathname.startsWith('/apps/'))throw Error('Invalid GitHub installation URL');window.location.assign(url.href);}
      catch(error){feedback.textContent=errorText(error);}finally{install.disabled=false;}
    };box.append(install);
  }
  box.append(cancel,feedback);root.append(box);
  // Mount first: initial pending GitHub OTP can be restored after a refresh.
  if(item.email_verification?.sent&&!emailVerified&&Number.isFinite(expiresAt))startCountdown();
};
(function () {
  function applyGithubCard(status) {
    var state = document.getElementById('githubCardState');
    var detail = document.getElementById('githubCardDetail');
    var connect = document.getElementById('connectGithubButton');
    var disconnect = document.getElementById('disconnectGithubButton');
    if (!state) return;
    if (status && status.connected) {
      state.textContent = 'Connected';
      if (detail) detail.textContent = status.account_login || '';
      if (connect) connect.hidden = true;
      if (disconnect) disconnect.hidden = false;
    } else {
      state.textContent = 'Not connected';
      if (detail) detail.textContent = (status && status.available) ? 'GitHub App is ready to connect.' : ((status && status.reason) || 'GitHub App is not configured');
      if (connect) connect.hidden = !(status && status.available);
      if (disconnect) disconnect.hidden = true;
    }
  }

  var connectButton = document.getElementById('connectGithubButton');
  if (connectButton) connectButton.onclick = function () { void window.startFreshGithubConnection(); };
  var disconnectButton = document.getElementById('disconnectGithubButton');
  if (disconnectButton) disconnectButton.onclick = async function () {
    try { if(!await window.disconnectGithubWithReview())return; await loadProjects(); toast('GitHub disconnected'); }
    catch (error) { toast(error.message); }
  };

  loadProjects = async function () {
    var data = await api('/api/dashboard');
    applyGithubCard(data.github);
    var list = document.getElementById('projectList');
    if (!list) return;
    list.replaceChildren();
    if (!data.projects.length) { list.append(textElement('p', t('noProjects'))); return; }
    data.projects.forEach(function (project) {
      var card = textElement('div', '', 'project-card');
      card.append(textElement('strong', project.name + ' · ' + project.source_type));
      if (project.remote_url) card.append(textElement('small', project.remote_url + ' · ' + (project.remote_branch || '')));
      if (!project.workspaces.length) card.append(textElement('small', 'No workspace yet'));
      project.workspaces.forEach(function (workspace) {
        var button = textElement('button', 'Open · ' + workspace.status + ' · ' + workspace.session_count + ' session(s)', 'button ghost');
        button.onclick = function () { openWorkspace(project, workspace); };
        card.append(button);
      });
      list.append(card);
    });
  };

  refreshGit = async function () {
    if (!activeWorkspace) return;
    ensureProviderButton();
    var state = await api('/api/workspaces/' + activeWorkspace.id + '/git/status');
    document.getElementById('commitButton').disabled = state.clean;
    var button = document.getElementById('pushButton');
    button.disabled = !(state.push_available && !state.clean);
    button.title = state.push_available ? ('Push to ' + (state.remote_branch || 'remote')) : 'This project has no connected GitHub remote';
    document.getElementById('gitSummary').textContent = state.changes.length + ' ' + t('changedFiles') + ' · ' +
      (state.head ? state.head.slice(0, 8) : t('noCommits')) + (state.remote_branch ? (' · ' + state.remote_branch) : '');
  };

  var pushButton = document.getElementById('pushButton');
  if (pushButton) pushButton.onclick = async function () {
    if (!activeWorkspace) return;
    pushButton.disabled = true;
    try {
      var result = await api('/api/workspaces/' + activeWorkspace.id + '/git/push', { method: 'POST' });
      toast('Pushed ' + result.branch + ' · verified ' + result.head.slice(0, 8));
      await refreshGit();
    } catch (error) { toast(error.message); pushButton.disabled = false; }
  };

  // --- Admin Console: a separate multi-page section for admin/owner only ---
  var ADMIN_ROLES = ['customer', 'support', 'finance', 'admin', 'owner'];
  var adminView = 'overview';
  var admin = function () { return ['admin', 'owner'].includes(currentUser && currentUser.role); };

  function adminMetric(overview, path) {
    var value = overview;
    path.split('.').forEach(function (key) { value = (value === undefined || value === null) ? undefined : value[key]; });
    return (value === undefined || value === null) ? 'Not available yet' : value;
  }

  function adminCells(row, values) { values.forEach(function (v) { row.append(textElement('td', v === null || v === undefined ? '—' : String(v))); }); }

  async function loadAdminOverview() {
    var o = await api('/api/admin/overview');
    var stats = document.getElementById('adminOverviewStats'); stats.replaceChildren();
    [['Total users', 'users.total'], ['Active users', 'users.active'], ['Suspended users', 'users.suspended'], ['Admin users', 'users.admins'], ['Owner users', 'users.owners'], ['Trial users', 'users.trial_active'], ['Expired trials', 'users.trial_expired'], ['Projects', 'projects.total'], ['Workspaces', 'workspaces.total'], ['Sessions', 'sessions.total'], ['Users with credentials', 'credentials.users'], ['Stored credentials', 'credentials.stored'], ['Plans', 'plans.total'], ['Active plans', 'plans.active']].forEach(function (m) { m[0] = tr(m[0], ({'Total users':'إجمالي المستخدمين','Active users':'المستخدمون النشطون','Suspended users':'المستخدمون الموقوفون','Admin users':'مستخدمون إداريون','Owner users':'الملاك','Trial users':'مستخدمو التجربة','Expired trials':'تجارب منتهية','Projects':'المشاريع','Workspaces':'مساحات العمل','Sessions':'الجلسات','Users with credentials':'مستخدمو بيانات الاعتماد','Stored credentials':'بيانات اعتماد مخزنة','Plans':'الخطط','Active plans':'خطط نشطة'})[m[0]]);
      var card = textElement('article', '');
      card.append(textElement('small', m[0]));
      var b = document.createElement('b'); b.textContent = adminMetric(o, m[1]); card.append(b);
      stats.append(card);
    });
    var body = document.getElementById('adminIntegrationsBody'); body.replaceChildren();
    [['GitHub configured', o.integrations.github.configured ? 'yes' : 'no'], ['GitHub connected users', o.integrations.github.connected_users], ['OpenCode runtime mode', o.runtime.mode], ['OpenCode healthy', o.runtime.healthy ? 'yes' : 'no'], ['Payments', o.payments.status === 'not_available' ? 'Not available yet' : o.payments.status], ['Visitors', o.visitors.status === 'not_available' ? 'Not available yet' : o.visitors.status]].forEach(function (r) {
      var yes = tr('yes', 'نعم'), no = tr('no', 'لا'), nay = tr('Not available yet', 'غير متاح بعد');
      r[0] = tr(r[0], ({'GitHub configured': 'GitHub مكوّن', 'GitHub connected users': 'مستخدمون مرتبطون بـGitHub', 'OpenCode runtime mode': 'وضع تشغيل OpenCode', 'OpenCode healthy': 'OpenCode سليم', 'Payments': 'المدفوعات', 'Visitors': 'الزوار'})[r[0]]);
      if (r[1] === 'yes') r[1] = yes; else if (r[1] === 'no') r[1] = no; else if (r[1] === 'Not available yet') r[1] = nay;
      var tr2 = document.createElement('tr'); tr2.append(textElement('th', r[0])); tr2.append(textElement('td', String(r[1]))); body.append(tr2);
    });
  }

  async function adminPatchUser(id, payload) {
    try { await api('/api/admin/users/' + id, { method: 'PATCH', body: JSON.stringify(payload) }); apiMessage('adminUserMessage', 'Saved'); await gridUsers(); return true; }
    catch (error) { apiMessage('adminUserMessage', error.message, true); return false; }
  }

  async function loadAdminUsersData() {
    var list = await api('/api/admin/users');
    var body = document.getElementById('adminUsersBody'); body.replaceChildren();
    list.forEach(function (u) {
      var row = document.createElement('tr');
      row.append(textElement('td', u.username));
      row.append(textElement('td', u.email));
      var roleTd = document.createElement('td');
      var select = document.createElement('select'); select.className = 'admin-role-select';
      ADMIN_ROLES.forEach(function (r) { var opt = document.createElement('option'); opt.value = r; opt.textContent = r; if (r === u.role) opt.selected = true; select.append(opt); });
      select.disabled=currentUser.role!=='owner'||u.id===currentUser.id||u.role==='owner';select.onchange = function () { adminPatchUser(u.id, { role: select.value }); };
      roleTd.append(select); row.append(roleTd);
      adminCells(row, [statusText(u.status), u.trial_remaining_days + ' ' + tr('days', 'يوم'), fmtDate(u.trial_ends_at), u.plan || tr('Not assigned', 'غير محدد'), u.last_login_at ? new Date(u.last_login_at).toLocaleString(lang === 'ar' ? 'ar' : 'en-GB') : tr('Never', 'أبدًا'), fmtDate(u.created_at), (u.projects_count || 0) + ' / ' + (u.workspaces_count || 0)]);
      var actions = document.createElement('td'); actions.className = 'admin-row-actions';
      var toggle = textElement('button', u.status === 'active' ? tr('Disable', 'تعطيل') : tr('Activate', 'تفعيل'), 'button ghost small');
      toggle.onclick = function () { adminPatchUser(u.id, { status: u.status === 'active' ? 'suspended' : 'active' }); };
      var extend = textElement('button', tr('Extend trial', 'تمديد التجربة'), 'button ghost small');
      extend.onclick = async function () { var d = await window.requestInput('Extend trial by how many days?', '10'); if (d === null) return; var n = Number(d); if (!isFinite(n) || n < 0) { toast('Invalid days'); return; } adminPatchUser(u.id, { trial_days: n }); };
      actions.append(toggle); actions.append(extend); row.append(actions);
      body.append(row);
    });
  }

  async function loadAdminProjects() {
    var list = await api('/api/admin/projects'); var body = document.getElementById('adminProjectsBody'); body.replaceChildren();
    list.forEach(function (p) { var row = document.createElement('tr'); adminCells(row, [p.owner, p.name, p.source_type, p.repository || '—', p.workspaces, p.sessions, p.archived ? 'yes' : 'no', p.created_at ? new Date(p.created_at).toLocaleDateString('en-GB') : '—']); body.append(row); });
  }
  async function loadAdminWorkspaces() {
    var list = await api('/api/admin/workspaces'); var body = document.getElementById('adminWorkspacesBody'); body.replaceChildren();
    list.forEach(function (w) { var row = document.createElement('tr'); adminCells(row, [w.owner, w.project, w.status, w.base_commit_sha ? w.base_commit_sha.slice(0, 8) : '—', w.sessions, w.created_at ? new Date(w.created_at).toLocaleDateString('en-GB') : '—', w.last_activity_at ? new Date(w.last_activity_at).toLocaleString('en-GB') : '—']); body.append(row); });
  }
  async function loadAdminSessions() {
    var list = await api('/api/admin/sessions'); var body = document.getElementById('adminSessionsBody'); body.replaceChildren();
    list.forEach(function (s) { var row = document.createElement('tr'); adminCells(row, [s.owner, s.project || '—', s.title, s.status, s.created_at ? new Date(s.created_at).toLocaleDateString('en-GB') : '—']); body.append(row); });
  }
  let adminGithubLoad=null;
  function loadAdminGithubAdmin() {
    if(!['admin','owner'].includes(currentUser?.role))return Promise.resolve();
    const owner=currentUser.id;
    if(adminGithubLoad?.owner===owner)return adminGithubLoad.promise;
    const section=document.querySelector('[data-admin-panel="github"]');if(!section)return Promise.resolve();
    let panel=document.getElementById('adminGithubPanel');
    // Older loaders replaced the entire section, removing this host and its title.
    if(!panel){panel=textElement('div','','admin-section');panel.id='adminGithubPanel';section.append(panel);}
    panel.replaceChildren();
    const heading=textElement('h2',tr('GitHub integration','تكامل GitHub'));
    const note=textElement('p',tr('OpenCode executes native GitHub tools through MCP. Gateway manages account authorization and repository ownership. GitHub is not used for platform sign-in.','ينفّذ OpenCode أدوات GitHub الأصلية عبر MCP. يدير Gateway تفويض الحسابات وملكية المستودعات. لا يُستخدم GitHub للدخول إلى المنصة.'));
    const nativeCard=textElement('section','','manage-card');nativeCard.setAttribute('aria-label',tr('Official Native GitHub integration','تكامل GitHub الأصلي الرسمي'));
    nativeCard.append(textElement('h3',tr('OpenCode · official GitHub MCP','OpenCode · GitHub MCP الرسمي')));
    const nativeGrid=textElement('div','','field-grid');
    for(const [caption,value] of [['MCP server URL','https://api.githubcopilot.com/mcp/'],['Transport','remote']]){
      const label=textElement('label','','field'),input=document.createElement('input');input.readOnly=true;input.value=value;input.setAttribute('aria-label',caption);label.append(textElement('span',caption),input);nativeGrid.append(label);
    }
    nativeCard.append(nativeGrid,textElement('p',tr('Official service settings only. Native connection and per-account authorization have not been verified by this page. No shared customer token is configured here.','هذه إعدادات الخدمة الرسمية فقط. لا تثبت هذه الصفحة اتصال Native أو تفويض كل حساب. لا يُضبط هنا رمز مشترك للعملاء.')));
    const nativeDocs=textElement('a',tr('Official OpenCode installation guide','دليل الربط الرسمي مع OpenCode'),'button ghost');nativeDocs.href='https://github.com/github/github-mcp-server/blob/main/docs/installation-guides/install-opencode.md';nativeDocs.target='_blank';nativeDocs.rel='noopener noreferrer';nativeCard.append(nativeDocs);
    nativeCard.append(textElement('p',tr('Remote authentication uses an authorized token or host OAuth App. The official local MCP distribution includes its own OAuth registration, but requires a separate runtime. These credentials cannot be substituted into the Gateway App form.','مصادقة الخدمة البعيدة تحتاج رمزًا مفوّضًا أو تطبيق OAuth للمضيف. تتضمن نسخة MCP المحلية الرسمية تسجيل OAuth خاصًا بها، لكنها تحتاج عملية تشغيل إضافية. لا يمكن وضع بياناتها بدل بيانات تطبيق Gateway أدناه.')));
    const gatewaySettings=textElement('details');gatewaySettings.append(textElement('summary',tr('Gateway repository authorization · App settings','تفويض مستودعات Gateway · إعدادات التطبيق')));
    gatewaySettings.append(textElement('p',tr('Existing Gateway repository connection. Saved server settings take priority. For first-time TEST setup, the registered platform App identifiers are suggested; each customer still authorizes their own repositories. Blank secrets preserve saved values.','الربط الحالي لمستودعات Gateway. الأولوية لإعدادات الخادم المحفوظة. في إعداد TEST الأولي تُقترح معرّفات تطبيق المنصة المسجّل؛ يفوّض كل عميل مستودعاته بنفسه. الحقول السرية الفارغة تحتفظ بالقيم المحفوظة.')));
    const status=textElement('p',tr('Checking configuration…','جارٍ فحص الإعدادات…'));status.setAttribute('role','status');
    const grid=textElement('div','','field-grid');
    const inputs=new Map();
    const form=document.createElement('form');form.className='manage-card';form.setAttribute('aria-label',tr('GitHub App configuration','إعدادات تطبيق GitHub'));
    const urls=textElement('details');urls.append(textElement('summary',tr('Callback and service URLs','عناوين العودة والخدمة')));
    const urlGrid=textElement('div','','field-grid');urls.append(urlGrid);
    for(const [caption,key] of [['App ID','app_id'],['App Slug','app_slug'],['OAuth Client ID','client_id'],['Public URL','public_base_url'],['Callback URL','callback_url'],['Webhook URL','webhook_url'],['API URL','api_base'],['GitHub URL','web_base']]){
      const label=textElement('label','','field'),input=document.createElement('input');input.readOnly=!['app_id','app_slug','client_id'].includes(key);input.placeholder='—';input.setAttribute('aria-label',caption);
      if(!input.readOnly){input.required=true;input.name=key;if(key==='app_id'){input.type='number';input.min='1';}else input.maxLength=key==='app_slug'?100:128;}
      label.append(textElement('span',caption),input);(input.readOnly?urlGrid:grid).append(label);inputs.set(key,input);
    }
    const configuration=textElement('div'),connection=textElement('p'),database=textElement('p');database.setAttribute('role','status');
    const authorize=textElement('button',tr('New GitHub connection','ربط GitHub جديد'),'button ghost');authorize.type='button';authorize.disabled=true;authorize.onclick=()=>window.startFreshGithubConnection();
    const refresh=textElement('button',tr('Refresh','تحديث'),'button ghost');refresh.type='button';refresh.onclick=loadAdminGithubAdmin;
    const credentialsPanel=textElement('details');credentialsPanel.append(textElement('summary',tr('Update App credentials','تحديث بيانات اعتماد التطبيق')));
    const secretGrid=textElement('div','','field-grid');credentialsPanel.append(secretGrid);
    function secretField(caption,name,type='password'){const label=textElement('label','','field'),input=document.createElement('input');input.type=type;input.name=name;input.autocomplete='new-password';input.setAttribute('aria-label',caption);label.append(textElement('span',caption),input);secretGrid.append(label);return input;}
    const clientSecret=secretField('OAuth Client Secret','client_secret');clientSecret.maxLength=4096;
    const privateKey=secretField(tr('Private key (.pem file)','المفتاح الخاص (ملف .pem)'),'private_key_file','file');privateKey.accept='.pem';
    const webhookSecret=secretField('Webhook Secret (optional)','webhook_secret');webhookSecret.maxLength=4096;
    const save=textElement('button',tr('Save GitHub App settings','حفظ إعدادات تطبيق GitHub'),'button');save.type='submit';save.disabled=true;
    const setupNote=textElement('p');setupNote.setAttribute('role','status');
    const saveStatus=textElement('p');saveStatus.setAttribute('role','status');
    const connections=textElement('div');connections.id='adminGithubConnections';
    form.append(grid,setupNote,credentialsPanel,save,saveStatus);
    gatewaySettings.append(status,form,urls,configuration,database);
    const identityConfirmation=textElement('div');panel.append(heading,note,nativeCard,gatewaySettings,connection,identityConfirmation,authorize,refresh,connections);
    form.onsubmit=async event=>{
      event.preventDefault();if(save.disabled||!current())return;
      save.disabled=true;saveStatus.textContent=tr('Saving encrypted settings…','جارٍ حفظ الإعدادات مشفّرة…');
      let saved=false;
      try{
        const file=privateKey.files?.[0];if(file&&file.size>32768)throw Error(tr('PEM file exceeds 32 KB','ملف PEM يتجاوز 32 كيلوبايت'));
        const pem=file?await file.text():null;
        if(!current())return;
        const data={app_id:Number(inputs.get('app_id').value),app_slug:inputs.get('app_slug').value.trim(),client_id:inputs.get('client_id').value.trim(),client_secret:clientSecret.value||null,private_key:pem,webhook_secret:webhookSecret.value||null};
        await api('/api/admin/github-configuration',{method:'PUT',body:JSON.stringify(data)});
        saved=true;if(!current())return;
        clientSecret.value='';privateKey.value='';webhookSecret.value='';
        saveStatus.textContent=tr('Saved securely. Configuration is not a completed OAuth connection.','حُفظت الإعدادات بأمان. الحفظ وحده لا يعني نجاح ربط OAuth.');
      }catch(error){if(current())saveStatus.textContent=error.message;}
      finally{if(current())save.disabled=false;}
      if(saved&&current()){
        await loadAdminGithubAdmin();
        const result=document.getElementById('adminGithubPanel');if(result&&currentUser?.id===owner)result.append(textElement('p',tr('GitHub App settings saved securely.','حُفظت إعدادات تطبيق GitHub بأمان.')));
      }
    };
    const current=()=>currentUser?.id===owner&&['admin','owner'].includes(currentUser?.role)&&panel.isConnected;
    const showConfig=async()=>{
      try{
        const config=await api('/api/admin/github-configuration');if(!current())return;
        for(const [key,input] of inputs)input.value=String(config[key]??'');
        // Public metadata, not credentials. Never replace a saved or partially
        // configured App, and never apply TEST suggestions to another server.
        const firstTestSetup=config.source==='protected_server_environment'&&config.public_base_url?.replace(/\/+$/,'')==='https://test.opencode-gateway.codes'&&
          !config.configured&&!config.app_id&&!config.app_slug&&!config.client_id&&
          !config.secrets?.client_secret&&!config.secrets?.private_key&&!config.secrets?.webhook_secret;
        if(firstTestSetup){
          for(const [key,value] of Object.entries({app_id:5470256,app_slug:'opencode-gateway-test-diirzoro',client_id:'Iv23liGSq3yRR7okVSQJ'}))inputs.get(key).value=String(value);
          setupNote.textContent=tr('Registered platform App identifiers suggested · not saved or connected. Add its Client Secret and PEM after setting up Gateway encryption. These are not OpenCode-issued credentials.','اقتُرحت معرّفات تطبيق المنصة المسجّل · لم تُحفظ ولم يتم الربط. أضف Client Secret وملف PEM بعد إعداد تشفير Gateway. هذه ليست بيانات اعتماد صادرة عن OpenCode.');
        }
        gatewaySettings.open=!config.configured;

        save.disabled=config.editable!==true||config.settings_schema_ready!==true||config.credential_storage_ready!==true;
        saveStatus.textContent=config.settings_schema_ready!==true?tr('Apply TEST migration 0024 to enable saving.','طبّق ترحيل TEST رقم 0024 لتمكين الحفظ.'):config.credential_storage_ready!==true?tr('Gateway credential encryption is not configured. Complete server setup before saving secrets; preserve any existing key.','تشفير اعتمادات Gateway غير مُعدّ. أكمل إعداد الخادم قبل حفظ الأسرار، مع الحفاظ على أي مفتاح موجود.'):tr('Secrets are encrypted on the server. Empty fields keep existing secrets.','تُشفّر الأسرار على الخادم. الحقول الفارغة تحتفظ بالأسرار الحالية.');
        status.textContent=config.configured?tr('GitHub App configured.','تطبيق GitHub مهيأ.'):tr('GitHub App is not ready on the server.','تطبيق GitHub غير جاهز على الخادم.');
        configuration.append(textElement('p',[['OAuth Client Secret','client_secret'],['App private key','private_key'],['Webhook Secret','webhook_secret'],['Credential encryption key','encryption_key']].map(([name,key])=>name+': '+(config.secrets?.[key]?tr('Configured','موجود'):tr('Missing','ناقص'))).join(' · ')));
        if(config.missing?.length)configuration.append(textElement('p',tr('Missing server settings: ','إعدادات الخادم الناقصة: ')+config.missing.join(', ')));
        const schema=config.database;
        database.textContent=!schema?tr('Database schema has not been verified. Deploy the matching diagnostics backend.','لم يتم التحقق من مخطط قاعدة البيانات. انشر الخلفية المتوافقة للفحص.'):!schema.checked?tr('Database schema inspection is unavailable.','تعذر التحقق من مخطط قاعدة البيانات.'):
          schema.ready?tr('GitHub database schema is ready.','جداول GitHub وأعمدتها جاهزة.'):
          tr('GitHub database migration required: ','يلزم ترحيل قاعدة بيانات GitHub: ')+(schema.missing||[]).join(', ');
        if(schema?.checked&&schema.ready)database.dataset.ready='true';
        if(schema?.revisions?.length)database.textContent+=' · Alembic: '+schema.revisions.join(', ');
        if(schema&&!schema.ready)authorize.disabled=true;
      }catch(error){if(current())status.textContent=tr('Configuration unavailable: ','تعذر تحميل الإعدادات: ')+error.message;}
    };
    const showConnection=async()=>{
      try{const value=await api('/api/github/status');if(!current())return;
        connection.textContent=value.connected?tr('My connected account: ','حسابي المتصل: ')+(value.github_login||value.account_login||'GitHub'):tr('My account is not connected.','حسابي غير مرتبط.');
        identityConfirmation.replaceChildren();window.renderGithubConfirmation(identityConfirmation,value,loadAdminGithubAdmin);
        const outcome=new URLSearchParams(location.search).get('github');
        if(!value.pending&&['configuration','ownership-review','error'].includes(outcome)){
          const notice=textElement('p',outcome==='ownership-review'?tr('An older GitHub connection needs verified ownership recovery. No new account was connected.','يلزم استرداد موثّق لملكية اتصال GitHub قديم. لم يُربط أي حساب جديد.'):tr('GitHub callback could not complete. Check Gateway diagnostics and the sanitized callback log category.','تعذر استكمال العودة من GitHub. راجع تشخيص Gateway وتصنيف الخطأ الآمن في السجل.'),'api-message show');notice.setAttribute('role','alert');identityConfirmation.append(notice);
        }
        // Enabled only after both configuration and database diagnostics succeed.
        authorize.dataset.available=String(!!value.configured&&!value.connected);
      }catch(error){if(current())connection.textContent=tr('Account status unavailable: ','تعذر فحص اتصال الحساب: ')+error.message;}
    };
    const entry={owner};adminGithubLoad=entry;
    entry.promise=Promise.all([showConfig(),showConnection()]).then(async()=>{
      if(!current())return;
      authorize.disabled=authorize.dataset.available!=='true'||!database.dataset.ready;
      // This child alone is owned by the connections renderer. Never give it the
      // parent admin section: renderManagement starts by clearing its root.
      if(window.renderManagement)await window.renderManagement(connections,'connections',true);
    }).catch(error=>{if(current())connections.append(textElement('p',error.message));}).finally(()=>{if(adminGithubLoad===entry)adminGithubLoad=null;});
    return entry.promise;
  }

  async function loadAdminBilling() {
    var summary = await api('/api/admin/billing/summary');
    var box = document.getElementById('adminBillingSummary'); if (box) {
      box.replaceChildren();
      [['Subscriptions', summary.subscriptions.total], ['Trial', summary.subscriptions.trial], ['Pending payment', summary.subscriptions.pending_payment], ['Active', summary.subscriptions.active], ['Cancelled', summary.subscriptions.cancelled], ['Expired', summary.subscriptions.expired]].forEach(function (m) {
        m[0] = tr(m[0], ({'Subscriptions': 'الاشتراكات', 'Trial': 'تجريبي', 'Pending payment': 'بانتظار الدفع', 'Active': 'نشط', 'Cancelled': 'ملغى', 'Expired': 'منتهي'})[m[0]]);
        var c = textElement('article', ''); c.append(textElement('small', m[0])); var b = document.createElement('b'); b.textContent = m[1]; c.append(b); box.append(c);
      });
    }
    var subs = await api('/api/admin/subscriptions');
    var body = document.getElementById('adminSubscriptionsBody'); if (body) {
      body.replaceChildren();
      subs.forEach(function (s) { var tr3 = document.createElement('tr'); adminCells(tr3, [s.owner, s.owner_email, s.plan || tr('Not assigned', 'غير محدد'), statusText(s.status), s.started_at ? fmtDate(s.started_at) : '—', s.current_period_end ? fmtDate(s.current_period_end) : '—', s.cancelled_at ? fmtDate(s.cancelled_at) : '—']); body.append(tr3); });
    }
    var tx = await api('/api/admin/billing/transactions'); var txBox = document.getElementById('adminTransactions');
    if (txBox) {
      txBox.replaceChildren();
      if (!tx.items || !tx.items.length) txBox.append(textElement('p', tr('No payment orders yet.', 'لا توجد طلبات دفع بعد.')));
      else tx.items.forEach(function (item) {
        var row = textElement('article', '', 'manage-row');
        row.append(textElement('strong', item.plan_name + ' · ' + item.currency + ' ' + (item.amount_cents / 100).toFixed(2)));
        row.append(textElement('span', item.email + ' · ' + item.method_label + ' · ' + statusText(item.status)));
        if (item.payment_reference) row.append(textElement('small', tr('Receipt reference: ', 'مرجع الإيصال: ') + item.payment_reference));
        txBox.append(row);
      });
    }
    var rev = document.getElementById('adminRevenue'); if (rev) {
      rev.replaceChildren();
      var totals = summary.revenue && summary.revenue.items || [];
      if (!totals.length) rev.append(textElement('p', tr('No verified payments yet.', 'لا توجد مدفوعات مؤكدة بعد.')));
      else totals.forEach(function (item) { rev.append(textElement('p', item.currency + ' ' + (item.amount_cents / 100).toFixed(2))); });
    }
  }
  async function loadAdminReports() {
    var data = await api('/api/admin/reports');
    var box = document.getElementById('adminReportsCounts'); if (box) {
      box.replaceChildren();
      [['Users', data.counts.users], ['Projects', data.counts.projects], ['Workspaces', data.counts.workspaces], ['Sessions', data.counts.sessions], ['Subscriptions', data.counts.subscriptions]].forEach(function (m) { m[0] = tr(m[0], ({'Users': 'المستخدمون', 'Projects': 'المشاريع', 'Workspaces': 'مساحات العمل', 'Sessions': 'الجلسات', 'Subscriptions': 'الاشتراكات'})[m[0]]); var c = textElement('article', ''); c.append(textElement('small', m[0])); var b = document.createElement('b'); b.textContent = m[1]; c.append(b); box.append(c); });
    }
    var revenue = document.getElementById('adminReportsRevenue'); if (revenue) {
      revenue.replaceChildren();
      var totals = data.revenue && data.revenue.items || [];
      if (!totals.length) revenue.append(textElement('p', tr('No verified payments yet.', 'لا توجد مدفوعات مؤكدة بعد.')));
      else totals.forEach(function (item) { revenue.append(textElement('p', item.currency + ' ' + (item.amount_cents / 100).toFixed(2))); });
    }
  }
  async function loadAdminHealth() {
    var panel = document.getElementById('adminHealthPanel'); if (!panel) return;
    try { var s = await api('/api/opencode/status'); panel.replaceChildren(textElement('p', 'Runtime mode: ' + s.runtime_mode + ' · healthy: ' + (s.healthy ? 'yes' : 'no')), textElement('p', 'Public multi-user ready: ' + (s.public_multi_user_ready ? 'yes' : 'no'))); }
    catch (error) { panel.replaceChildren(textElement('p', error.message)); }
  }
  async function loadAdminTrial() {
    var panel = document.getElementById('adminTrialPanel'); if (!panel) return;
    try { var o = await api('/api/admin/overview'); panel.replaceChildren(textElement('p', 'Trial users: ' + o.users.trial_active + ' · Expired: ' + o.users.trial_expired + ' · Active users: ' + o.users.active), textElement('p', 'Editing the default trial length is not available yet.')); }
    catch (error) { panel.replaceChildren(textElement('p', error.message)); }
  }

  async function loadAdminAccount() {
    var box = document.getElementById('adminAccountPanel'); if (!box) return;
    var user = await api('/api/profile');
    box.replaceChildren();
    [['#icon-user', tr('Username', 'اسم المستخدم'), user.username], ['#icon-file', tr('Email', 'البريد'), user.email], ['#icon-shield', tr('Role', 'الدور'), user.role], ['#icon-clock', tr('Trial', 'التجربة'), (typeof user.trial_remaining_days === 'number' ? user.trial_remaining_days + ' ' + tr('days remaining', 'يوم متبقٍ') : '—')]].forEach(function (r) { var c = listCard(r[0], r[1], r[2]); box.append(c); });
  }

  var ADMIN_LOADERS = { overview: loadAdminOverview, projects: loadAdminProjects, workspaces: loadAdminWorkspaces, sessions: loadAdminSessions, users: loadAdminUsersData, plans: loadAdminPlans, billing: loadAdminBilling, reports: loadAdminReports, audit: async function () {}, health: loadAdminHealth, policy: loadAdminPolicy, github: loadAdminGithubAdmin, email: async function(){ if(window.gatewayLoadServiceCenter) await window.gatewayLoadServiceCenter(); }, trial: loadAdminTrial, settings: async function () {}, security: async function () {}, account: loadAdminAccount };

  function setAdminView(name) {
    if (!['overview','users','plans','billing','reports','audit','health','policy','github','email','trial','settings','security','account'].includes(name)) name='overview';
    adminView = name;
    document.querySelectorAll('#adminNav [data-admin-view]').forEach(function (b) { b.classList.toggle('active', b.dataset.adminView === name); });
    document.querySelectorAll('#adminPage [data-admin-panel]').forEach(function (p) { p.classList.toggle('active', p.dataset.adminPanel === name); });
    var loader = ADMIN_LOADERS[name];
    if (loader) return loader();
  }

  window.openGithubConnectionPanel=()=>['admin','owner'].includes(currentUser?.role)?setAdminView('github'):window.openConnections?.('github');

  document.querySelectorAll('[data-admin-view]').forEach(function (button) {
    button.onclick = function () { setAdminView(button.dataset.adminView).catch(function (e) { toast(e.message); }); };
  });

  loadAdminUsers = async function () { await setAdminView(adminView || 'overview'); };

  async function connectProviderCredential() {
    if (!activeWorkspace) { toast('Open a workspace first'); return; }
    var providerId = await window.requestInput('Provider id (for example openai or anthropic)');
    if (!providerId) return;
    var apiKey = await window.requestInput('API key. It is sent to the server only and never kept in the browser.','','password');
    if (!apiKey) return;
    try {
      var result = await api('/api/workspaces/' + activeWorkspace.id + '/providers/' + encodeURIComponent(providerId) + '/credentials', { method: 'POST', body: JSON.stringify({ api_key: apiKey }) });
      toast('Connected ' + result.provider_id + ' · key ending ' + result.last4);
    } catch (error) { toast(error.message); }
  }

  function ensureProviderButton() {
    if(window.workspaceFirstEnabled)return;
    var runtimeStatus = document.getElementById('runtimeStatus');
    if (!runtimeStatus || document.getElementById('manageProviders')) return;
    var button = textElement('button', tr('Connect AI provider','ربط مزوّد الذكاء'), 'button ghost small');
    button.id = 'manageProviders';
    button.type = 'button';
    button.onclick = connectProviderCredential;
    runtimeStatus.parentNode.insertBefore(button, runtimeStatus.nextSibling);
  }

  // --- Phase 1: real pricing, trial dates, admin plans/policy, chat controls ---
  function money(cents) { return '$' + (cents / 100).toFixed(cents % 100 ? 2 : 0); }

  function planDurationLabel(days) {
    if (lang === 'ar') {
      if (days === 30) return 'شهريًا';
      if (days === 60) return 'كل شهرين';
      if (days === 90) return 'كل ثلاثة أشهر';
      if (days === 365) return 'سنويًا';
      return 'لـ ' + days + ' يومًا';
    }
    if (days === 30) return 'per month';
    if (days === 60) return 'every 2 months';
    if (days === 90) return 'every 3 months';
    if (days === 365) return 'per year';
    return 'for ' + days + ' days';
  }

  function planDisplayName(plan) {
    return lang === 'ar' ? planDurationLabel(plan.duration_days) : plan.name;
  }
  function planDisplayTerm(plan) {
    return lang === 'ar' ? plan.duration_days + ' ' + tr('days', 'يومًا') : planDurationLabel(plan.duration_days);
  }
  window.planDisplayName = planDisplayName;
  window.planDisplayTerm = planDisplayTerm;
  window.planDisplayPrice = function (plan) { return money(plan.price_cents); };

  async function renderPricing() {
    var cards = document.getElementById('pricingCards');
    if (!cards) return;
    try {
      var plans = await api('/api/plans', { cache: 'no-store' });
      cards.replaceChildren();
      var parts = [];
      plans.forEach(function (plan) {
        var duration = plan.durationLabel || planDurationLabel(plan.duration_days);
        var main = planDisplayName(plan);
        var sub = planDisplayTerm(plan);
        var card = textElement('div', '', 'price-card');
        card.append(textElement('b', money(plan.price_cents)));
        card.append(textElement('span', main));
        card.append(textElement('small', sub));
        var choose=textElement('button',tr('Subscribe','اشترك'),'button small');choose.type='button';choose.dataset.planId=plan.id;choose.onclick=async function(){window.pendingCheckoutPlan=plan.id;if(currentUser){await window.openClientView('billing');await window.beginCheckout(plan.id);}else await page('authPage');};card.append(choose);
        cards.append(card);
        parts.push(money(plan.price_cents) + ' · ' + main);
      });
      var summary = document.getElementById('pricingSummary');
      if (summary && parts.length) summary.textContent = parts.join(' · ');
      if (summary && !parts.length) summary.textContent = tr('No active offers are available right now.', 'لا توجد عروض نشطة حاليًا.');
    } catch (error) {
      cards.replaceChildren();
      var summary = document.getElementById('pricingSummary');
      if (summary) summary.textContent = tr('Offers are temporarily unavailable. Please refresh shortly.', 'العروض غير متاحة مؤقتًا. حدّث الصفحة بعد قليل.');
    }
  }

  renderProfile = function (user) {
    currentUser = user; updateNavigation();
    window.authSession?.start();
    var statusEl = document.getElementById('profileStatus'); if (statusEl) statusEl.textContent = (lang === 'ar' ? ({ active: 'نشط', suspended: 'موقوف' }[user.status] || user.status) : user.status);
    var trialEl = document.getElementById('profileTrial'); if (trialEl) trialEl.textContent = (typeof user.trial_remaining_days === 'number') ? (user.trial_remaining_days + ' trial days remaining') : '—';
    var dates = document.getElementById('profileTrialDates');
    if (dates) dates.textContent = 'Trial ' + new Date(user.trial_started_at).toLocaleDateString('en-GB') + ' → ends ' + new Date(user.trial_ends_at).toLocaleDateString('en-GB');
    for (const [id, text] of Object.entries({ profileUsername: user.username, profileEmail: user.email, profilePhone: user.phone, profileLocation: [user.country, user.region, user.city, user.postal_code].filter(Boolean).join(' · '), profilePreferences: user.preferred_language + ' · ' + user.preferred_theme })) {
      var el = document.getElementById(id);
      if (!el) continue;
      if (el.firstChild) el.firstChild.textContent = text; else el.textContent = text;
    }
    // Browser App Shell preferences survive login, profile reads and session restoration.
    applyPrefs();
  };

  async function loadAdminPlans() {
    var body = document.getElementById('adminPlansBody');
    if (!body) return;
    try {
      var plans = await api('/api/admin/plans', { cache: 'no-store' });
      body.replaceChildren();
      plans.forEach(function (plan) {
        var row = document.createElement('tr');
        [plan.code, plan.name, money(plan.price_cents), planDisplayTerm(plan), plan.active ? 'yes' : 'no'].forEach(function (text) { row.append(textElement('td', text)); });
        var action = document.createElement('td');
        var toggle = textElement('button', plan.active ? 'Deactivate' : 'Activate', 'button ghost small');
        toggle.onclick = async function () { try { await api('/api/admin/plans/' + plan.id, { method: 'PATCH', body: JSON.stringify({ active: !plan.active }) }); await loadAdminPlans(); } catch (error) { toast(error.message); } };
        action.append(toggle); row.append(action); body.append(row);
      });
    } catch (error) { toast(error.message); }
  }

  var planForm = document.getElementById('adminPlanForm');
  if (planForm) planForm.onsubmit = async function (event) {
    event.preventDefault();
    try {
      await api('/api/admin/plans', { method: 'POST', body: JSON.stringify({ code: value('planCode'), name: value('planName'), price_cents: Number(value('planPrice')), currency: 'USD', duration_days: Number(value('planDays')), active: true, sort_order: 90 }) });
      apiMessage('adminPlanMessage', 'Plan created'); planForm.reset(); await loadAdminPlans(); await renderPricing();
    } catch (error) { apiMessage('adminPlanMessage', error.message, true); }
  };

  const policyStyle=document.createElement('style');policyStyle.textContent=`
  .native-policy-console{display:grid;gap:12px}.native-policy-console .manage-actions{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
  .native-policy-console input[type=search]{flex:1;min-width:180px;padding:9px 12px;border:1px solid var(--line);border-radius:10px;background:var(--panel);color:var(--text)}
  .policy-provider-row{display:flex;align-items:center;gap:12px;padding:10px 0;border-block-end:1px solid var(--line);flex-wrap:wrap}
  .policy-provider-identity{flex:1;min-width:150px;display:grid;gap:3px}.policy-provider-identity small{color:var(--muted)}
  .policy-model-editor{border:1px solid var(--line);border-radius:12px;padding:14px}.policy-model-list{display:grid;gap:6px;margin-block:10px}
  .policy-model-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:7px;background:var(--control-fill);border-radius:8px}.policy-model-row small{color:var(--muted);overflow-wrap:anywhere}
  `;document.head.append(policyStyle);
  var policyVisibilityRevision=0;
  async function loadAdminPolicy() {
    const owner=currentUser?.id,revision=++policyVisibilityRevision;
    const t=(en,ar)=>lang==='ar'?ar:en;
    const panel=document.querySelector('[data-admin-panel="policy"]');
    let host=document.getElementById('adminCatalogVisibility');
    if(!host){host=textElement('section','','manage-card native-policy-console');host.id='adminCatalogVisibility';panel.append(host);}
    host.replaceChildren(textElement('p',t('Loading policy…','جارٍ تحميل السياسة…')));
    try {
      let draft=await api('/api/admin/policy');
      const valid=()=>revision===policyVisibilityRevision&&currentUser?.id===owner&&['admin','owner'].includes(currentUser?.role);
      if(!valid())return;
      document.getElementById('policyProviders').value=(draft.allowed_providers||[]).join(', ');
      document.getElementById('policyModels').value=(draft.allowed_models||[]).join(', ');
      document.getElementById('policyTools').value=(draft.allowed_tools||[]).join(', ');
      document.getElementById('policyApproval').checked=!!draft.require_tool_approval;
      const changedProviders=new Map(),changedModels=new Map(),selected=new Set();let rows=[],offset=0,next=null,pageRevision=0;
      host.replaceChildren();
      host.append(textElement('h2',t('Customer catalog visibility','ظهور الكتالوج للعملاء')),textElement('p',t('Hide from default suggestions only. Manual search, connections and use remain available. Access restrictions and customer credentials are separate.','الإخفاء من الاقتراحات الافتراضية فقط. البحث والربط والاستخدام اليدوي متاحة. قيود الوصول ومفاتيح العملاء منفصلة.')));
      const toolbar=textElement('div','','manage-actions'),search=document.createElement('input');search.type='search';search.placeholder=t('Search all Native providers','ابحث في جميع مزوّدي Native');search.setAttribute('aria-label',search.placeholder);
      function action(label,handler){const b=textElement('button',label,'button ghost small');b.type='button';b.onclick=async()=>{try{await handler();}catch(error){if(valid())status.textContent=error.message;}};return b;}
      const status=textElement('p','','muted-small');status.setAttribute('role','status');
      const list=textElement('div','','policy-provider-list'),details=textElement('section','','policy-model-editor');details.hidden=true;
      const save=action(t('Save visibility','حفظ الظهور'),async()=>{
        save.disabled=true;
        try{
          const current=await api('/api/admin/policy');if(!valid())return;
          const hidden=new Set(current.hidden_providers||[]),models={...(current.hidden_models||{})};
          changedProviders.forEach((visible,id)=>visible?hidden.delete(id):hidden.add(id));
          changedModels.forEach((changes,pid)=>{const ids=new Set(models[pid]||[]);changes.forEach((visible,id)=>visible?ids.delete(id):ids.add(id));models[pid]=[...ids];});
          const {updated_at,...body}=current;draft=await api('/api/admin/policy',{method:'PUT',body:JSON.stringify({...body,hidden_providers:[...hidden],hidden_models:models})});
          if(!valid())return;changedProviders.clear();changedModels.clear();window.workspaceRuntime?.clear();status.textContent=t('Visibility saved. Manual access remains available.','حُفظ الظهور. الوصول اليدوي ما زال متاحًا.');await loadPage(offset,false);
        }finally{save.disabled=false;}
      });save.className='button';save.disabled=true;
      const dirty=()=>{save.disabled=!changedProviders.size&&!changedModels.size;status.textContent=t('Unsaved visibility changes','تغييرات ظهور غير محفوظة');};
      const providerVisible=r=>changedProviders.has(r.id)?changedProviders.get(r.id):!(draft.hidden_providers||[]).includes(r.id);
      const bulk=visible=>{rows.filter(r=>selected.has(r.id)).forEach(r=>changedProviders.set(r.id,visible));dirty();renderRows();};
      const pick=action(t('Select page','تحديد الصفحة'),()=>{rows.forEach(r=>selected.add(r.id));renderRows();});
      const show=action(t('Show selected','إظهار المحدد'),()=>bulk(true)),hide=action(t('Hide selected','إخفاء المحدد'),()=>bulk(false));
      toolbar.append(search,action(t('Search','بحث'),()=>{offset=0;return loadPage(0);}),pick,show,hide);
      const previous=action(t('Previous','السابق'),()=>loadPage(Math.max(0,offset-6))),following=action(t('Next','التالي'),()=>loadPage(next)),pageInfo=textElement('span','','muted-small');
      const pager=textElement('div','','manage-actions');pager.append(previous,pageInfo,following);
      const add=action(t('Add from Native catalog','إضافة من كتالوج Native'),async()=>{
        const id=await window.requestInput(t('Native provider ID or name · no API key','اسم أو معرّف مزوّد Native · دون مفتاح API'));
        if(id){search.value=id;await loadPage(0);status.textContent=t('Choose a discovered provider below. Custom engine configuration is protected; connect your own key in Connections.','اختر مزوّدًا مكتشفًا أدناه. إعداد المحرك المخصص محمي؛ اربط مفتاح حسابك من الاتصالات.');}
      });
      host.append(toolbar,list,pager,details,add,save,status);
      async function openModels(provider){
        const result=await api('/api/admin/native/providers?provider_id='+encodeURIComponent(provider.id));if(!valid())return;
        let modelOffset=0;const all=result.models;details.hidden=false;details.replaceChildren(textElement('h3',provider.name));
        const find=document.createElement('input');find.type='search';find.placeholder=t('Search models of this provider','ابحث في نماذج هذا المزوّد');find.setAttribute('aria-label',find.placeholder);
        const body=textElement('div','','policy-model-list'),nav=textElement('div','','manage-actions');
        function visible(m){const changes=changedModels.get(provider.id);return changes?.has(m.id)?changes.get(m.id):!(draft.hidden_models?.[provider.id]||[]).includes(m.id);}
        function set(m,on){if(!changedModels.has(provider.id))changedModels.set(provider.id,new Map());changedModels.get(provider.id).set(m.id,on);dirty();}
        const back=action(t('Previous models','النماذج السابقة'),()=>{modelOffset=Math.max(0,modelOffset-8);render();}),more=action(t('Next models','النماذج التالية'),()=>{modelOffset+=8;render();}),count=textElement('span','','muted-small');nav.append(back,count,more);
        const bulkModels=textElement('div','','manage-actions');
        bulkModels.append(action(t('Show matching models','إظهار النماذج المطابقة'),()=>{matches().forEach(m=>set(m,true));render();}),action(t('Hide matching models','إخفاء النماذج المطابقة'),()=>{matches().forEach(m=>set(m,false));render();}),action(t('Close models','إغلاق النماذج'),()=>details.hidden=true));
        const matches=()=>all.filter(m=>(m.id+' '+m.name).toLowerCase().includes(find.value.toLowerCase()));
        function render(){const matchesNow=matches();body.replaceChildren();for(const m of matchesNow.slice(modelOffset,modelOffset+8)){const row=textElement('label','','policy-model-row'),toggle=document.createElement('input');toggle.type='checkbox';toggle.checked=visible(m);toggle.onchange=()=>set(m,toggle.checked);row.append(toggle,textElement('span',m.name),textElement('small',m.id));body.append(row);}back.disabled=modelOffset===0;more.disabled=modelOffset+8>=matchesNow.length;count.textContent=(matchesNow.length?modelOffset+1:0)+'–'+Math.min(modelOffset+8,matchesNow.length)+' / '+matchesNow.length;}
        find.oninput=()=>{modelOffset=0;render();};details.append(find,bulkModels,body,nav);render();
      }
      function renderRows(){
        list.replaceChildren();for(const r of rows){const row=textElement('div','','policy-provider-row'),check=document.createElement('input');check.type='checkbox';check.checked=selected.has(r.id);check.setAttribute('aria-label',t('Select ','تحديد ')+r.name);check.onchange=()=>{check.checked?selected.add(r.id):selected.delete(r.id);show.disabled=hide.disabled=!selected.size;};
          const identity=textElement('div','','policy-provider-identity');identity.append(textElement('strong',r.name),textElement('small',r.id+' · '+r.model_count+t(' models',' نموذج')));
          const visible=providerVisible(r),state=textElement('small',visible?t('Shown','ظاهر'):t('Hidden · manual access available','مخفي · متاح يدويًا'));if(!r.allowed)state.textContent+=' · '+t('Access restricted separately','الوصول مقيّد بصورة مستقلة');
          const toggle=action(visible?t('Hide','إخفاء'):t('Show','إظهار'),()=>{changedProviders.set(r.id,!providerVisible(r));dirty();renderRows();});
          row.append(check,identity,state,toggle,action(t('Models','النماذج'),()=>openModels(r)));list.append(row);
        }show.disabled=hide.disabled=!rows.some(r=>selected.has(r.id));
      }
      async function loadPage(value,announce=true){
        if(value===null)return;const sequence=++pageRevision;offset=value;
        const result=await api('/api/admin/native/providers?limit=6&offset='+offset+'&query='+encodeURIComponent(search.value));if(!valid()||sequence!==pageRevision)return;
        rows=result.items;next=result.next_offset;selected.clear();renderRows();previous.disabled=offset===0;following.disabled=next===null;pageInfo.textContent=(rows.length?offset+1:0)+'–'+(offset+rows.length)+' / '+result.total;if(announce)status.textContent=t('Native catalog · six providers per page','كتالوج Native · ستة مزوّدين في الصفحة');
      }
      search.onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();loadPage(0).catch(error=>status.textContent=error.message);}};
      await loadPage(0);
    } catch(error){host.replaceChildren(textElement('p',error.message,'api-message'));}
  }

  var policyForm = document.getElementById('adminPolicyForm');
  if (policyForm) policyForm.onsubmit = async function (event) {
    event.preventDefault();
    var split = function (id) { return value(id).split(',').map(function (x) { return x.trim(); }).filter(Boolean); };
    try {
      await api('/api/admin/policy', { method: 'PUT', body: JSON.stringify({ allowed_providers: split('policyProviders'), allowed_models: split('policyModels'), allowed_tools: split('policyTools'), require_tool_approval: document.getElementById('policyApproval').checked }) });
      apiMessage('adminPolicyMessage', 'Policy saved');
    } catch (error) { apiMessage('adminPolicyMessage', error.message, true); }
  };

  function openToolsPanel() {
    var existing = document.getElementById('toolsPanel');
    if (existing) { existing.remove(); return; }
    var panel = textElement('div', '', 'tools-panel'); panel.id = 'toolsPanel';
    panel.append(textElement('strong', 'OpenCode settings and tools'));
    panel.append(textElement('p', 'Provider and model are chosen beside the input. Sensitive commands always ask for approval; nothing runs from this panel.'));
    var runtime = textElement('div', '', '');
    api('/api/opencode/status').then(function (s) { runtime.textContent = 'Runtime mode: ' + s.runtime_mode + ' · healthy: ' + (s.healthy ? 'yes' : 'no'); }).catch(function () { runtime.textContent = 'Runtime status unavailable'; });
    var policyLine = textElement('div', '', '');
    if (activeWorkspace) {
      api('/api/workspaces/' + activeWorkspace.id + '/providers').then(function (list) {
        var names = list.map(function (p) { return p.name; });
        var connected = list.filter(function (p) { return p.connected; }).map(function (p) { return p.name; });
        policyLine.textContent = 'Available providers: ' + (names.join(', ') || 'none') + ' · Connected: ' + (connected.join(', ') || 'none') + ' · Admin policy controls what is available.';
      }).catch(function () { policyLine.textContent = 'Open a workspace to see provider availability.'; });
    } else {
      policyLine.textContent = 'Open a workspace to see provider availability.';
    }
    panel.append(runtime); panel.append(policyLine);
    var anchor = document.getElementById('agentFeed');
    if (anchor) anchor.parentNode.insertBefore(panel, anchor.nextSibling);
  }

  function wireChatControls() {
    var gh = document.getElementById('chatGithub');
    if (gh) gh.onclick = async function () {
      try {
        var status = await api('/api/github/status');
        toast(status.connected ? ('GitHub connected as ' + (status.account_login || '')) : (status.configured ? 'GitHub is not connected yet. Open Account to connect.' : 'GitHub integration is not configured.'));
      } catch (error) { toast(error.message); }
    };
    var tools = document.getElementById('openTools');
    if (tools) tools.onclick = openToolsPanel;
  }

  function renderEventLine(kind) {
    var feed = document.getElementById('agentFeed');
    if (!feed) return;
    var line = textElement('div', '· ' + kind, 'event-line');
    feed.append(line);
    // The shared chat-scroll controller owns follow-tail behavior.
  }

  // The base client owns the sole SSE connection and durable replay cursor.
  window.renderWorkspaceEventLine = renderEventLine;

  Object.assign(copy.en, { clientNavTitle: 'Client', clientDashboard: 'Dashboard', clientProjects: 'Projects', clientSessions: 'Sessions', clientAi: 'OpenCode', clientAccount: 'Account / Profile', clientDashboardLead: 'Your trial, connections, projects and recent activity in one place.', clientRecentLabel: 'RECENT', clientRecentProjects: 'Projects and workspaces', adminNavTitle: 'Administration', adminConsole: 'Admin Console', adminOverview: 'Overview', adminUsers: 'Users', adminProjects: 'Projects', adminWorkspaces: 'Workspaces', adminSessions: 'Sessions', adminPlans: 'Plans & Offers', adminPolicy: 'AI / OpenCode Policy', adminGithub: 'GitHub', adminAudit: 'Audit / Activity', adminSettings: 'Platform Settings', adminPersonal: 'Personal account', adminOverviewLead: 'Real backend metrics only. Metrics without a real query show "Not available yet".', adminPlatformStatus: 'PLATFORM STATUS', adminIntegrations: 'Integrations', adminUsersLead: 'Real account records. Role, status and trial changes call the admin API.', adminActions: 'Actions', adminProjectsLead: 'Metadata only. Customer source code is never shown here.', adminWorkspacesLead: 'Real workspace metadata. The physical path is never exposed.', adminSessionsLead: 'Real OpenCode conversation metadata.', adminPlansLead: 'Published offers are read by the public landing page through the plans API.', adminPolicyLead: 'These settings persist and limit what clients can select. User API keys and OAuth credentials are never shown here.', adminBilling: 'Billing / Subscriptions', adminReports: 'Reports', adminHealth: 'Platform Logs / Health', adminGithubSettings: 'GitHub Integration Settings', adminTrial: 'Trial / Entitlement Settings', adminSecurity: 'Security', clientRecentSessionsTitle: 'Recent sessions', clientProjectsLead: 'Your projects and workspaces.', clientSessionsLead: 'Workspaces and their OpenCode sessions.', clientAiLead: 'Runtime, provider and tool status for your workspaces.', clientGithubLead: 'Connect your GitHub account, then choose a repository and branch.', clientBillingLead: "Your own subscription only. Other customers' billing is never shown here.", clientPlansTitle: 'Plans & offers', clientCancel: 'Cancel subscription', clientReactivate: 'Reactivate', clientRenew: 'Renew subscription', clientInvoicesTitle: 'Invoices & payments', clientAccountLead: 'Personal details and preferences.', clientPersonalInfo: 'Personal information', clientUsername: 'Username', clientEmail: 'Email', clientPhone: 'Phone', clientLocation: 'Location / postal code', clientPreferences: 'Language / theme', clientSecurityNote: 'Use Password & security to change your password, revoke sign-ins, or suspend your account.', clientSecurityLead: 'Session and account security.', clientSecurity: 'Password & Security', clientDashboardBadge: 'CLIENT DASHBOARD', adminConsoleBadge: 'ADMIN CONSOLE', adminBillingLead: 'Business finance view, separate from the client billing page.', adminReportsLead: 'Real platform counts. Revenue appears only when backed by real payment data.', aUsername: 'Username', aEmail: 'Email', aRole: 'Role', aStatus: 'Status', aTrialRemaining: 'Trial remaining', aTrialEnd: 'Trial end', aPlan: 'Plan', aLastLogin: 'Last login', aCreated: 'Created', aProjectsWorkspaces: 'Projects / Workspaces', aCode: 'Code', aName: 'Name', aPrice: 'Price (USD)', aDays: 'Duration', aActive: 'Active', aAddPlan: 'Add plan', aSubscriptionsSmall: 'SUBSCRIPTIONS', aSubsTitle: 'Subscriptions across users', aOwner: 'Owner', aStarted: 'Started', aPeriodEnd: 'Period end', aCancelled: 'Cancelled', aTransactionsSmall: 'TRANSACTIONS', aTransactions: 'Payment transactions', aRevenueSmall: 'REVENUE', aRevenue: 'Revenue', aNay: 'Not available yet.', aAuditLogging: 'Audit logging is not available yet.', aHealthLead: 'Runtime health from the real backend.', aLoading: 'Loading…', aEnabledProviders: 'Enabled providers (comma separated)', aAllowedModels: 'Allowed models (comma separated)', aEnabledTools: 'Enabled tools / capabilities (comma separated)', aRequireApproval: 'Require approval before running tools', aSavePolicy: 'Save policy', aGithubLead: 'GitHub App configuration, database readiness, and account connections.', aLoadingStatus: 'Loading status…', aTrialLead: 'Trial entitlement overview. Editing trial defaults is not available yet.', aPlatformSettings: 'Platform settings are not available yet.', aAdminSecurityNotAvail: 'Admin security settings are not available yet.', aPersonalLead: 'Your own account. Administrative controls are on the other pages.' });
  Object.assign(copy.ar, { clientNavTitle: 'العميل', clientDashboard: 'لوحة المعلومات', clientProjects: 'المشاريع', clientSessions: 'الجلسات', clientAi: 'OpenCode', clientAccount: 'الحساب / الملف', clientDashboardLead: 'تجربتك واتصالاتك ومشاريعك ونشاطك الأخير في مكان واحد.', clientRecentLabel: 'الأحدث', clientRecentProjects: 'المشاريع ومساحات العمل', adminNavTitle: 'الإدارة', adminConsole: 'لوحة الإدارة', adminOverview: 'نظرة عامة', adminUsers: 'المستخدمون', adminProjects: 'المشاريع', adminWorkspaces: 'مساحات العمل', adminSessions: 'الجلسات', adminPlans: 'الخطط والعروض', adminPolicy: 'سياسة الذكاء / OpenCode', adminGithub: 'GitHub', adminAudit: 'التدقيق / النشاط', adminSettings: 'إعدادات المنصة', adminPersonal: 'الحساب الشخصي', adminOverviewLead: 'مؤشرات حقيقية فقط. ما لا يوجد له استعلام حقيقي يظهر "غير متاح بعد".', adminPlatformStatus: 'حالة المنصة', adminIntegrations: 'التكاملات', adminUsersLead: 'سجلات حقيقية. تغيير الدور والحالة والتجربة يستدعي واجهة الإدارة.', adminActions: 'إجراءات', adminProjectsLead: 'بيانات وصفية فقط. لا يظهر كود العميل هنا.', adminWorkspacesLead: 'بيانات مساحة العمل الحقيقية. لا يُكشف المسار الفيزيائي.', adminSessionsLead: 'بيانات محادثات OpenCode الحقيقية.', adminPlansLead: 'تُقرأ العروض المنشورة في صفحة الهبوط عبر واجهة الخطط.', adminPolicyLead: 'تُحفظ هذه الإعدادات وتحدّ من اختيارات العملاء. لا تظهر مفاتيح المستخدمين أو رموز OAuth هنا.', adminBilling: 'الفوترة / الاشتراكات', adminReports: 'التقارير', adminHealth: 'سجلات المنصة / الحالة', adminGithubSettings: 'إعدادات تكامل GitHub', adminTrial: 'إعدادات التجربة / الاستحقاق', adminSecurity: 'الأمان', clientRecentSessionsTitle: 'الجلسات الأخيرة', clientProjectsLead: 'مشاريعك ومساحات العمل.', clientSessionsLead: 'مساحات العمل وجلسات OpenCode الخاصة بها.', clientAiLead: 'حالة وقت التشغيل والمزوّد والأدوات لمساحات عملك.', clientGithubLead: 'حالة الاتصال. التدفق الحقيقي للترخيص مرحلة لاحقة.', clientBillingLead: 'اشتراكك فقط. لا تظهر فوترة العملاء الآخرين هنا.', clientPlansTitle: 'الخطط والعروض', clientCancel: 'إلغاء الاشتراك', clientReactivate: 'إعادة التفعيل', clientRenew: 'تجديد الاشتراك', clientInvoicesTitle: 'الفواتير والمدفوعات', clientAccountLead: 'بياناتك وتفضيلاتك. لوحة المعلومات صفحة منفصلة.', clientPersonalInfo: 'المعلومات الشخصية', clientUsername: 'اسم المستخدم', clientEmail: 'البريد الإلكتروني', clientPhone: 'الهاتف', clientLocation: 'الموقع / الرمز البريدي', clientPreferences: 'اللغة / المظهر', clientSecurityNote: 'تغيير كلمة المرور وإدارة الأجهزة غير متاحين بعد. جلستك تستخدم ملف تعريف ارتباط HttpOnly وSameSite=Strict.', clientSecurityLead: 'أمان الجلسة والحساب.', clientSecurity: 'كلمة المرور والأمان', clientDashboardBadge: 'لوحة العميل', adminConsoleBadge: 'لوحة الإدارة', adminBillingLead: 'عرض مالي للعمل، منفصل عن صفحة فوترة العميل.', adminReportsLead: 'مؤشرات المنصة الحقيقية. تظهر الإيرادات فقط عند توفر بيانات دفع حقيقية.', aUsername: 'اسم المستخدم', aEmail: 'البريد الإلكتروني', aRole: 'الدور', aStatus: 'الحالة', aTrialRemaining: 'المتبقي من التجربة', aTrialEnd: 'نهاية التجربة', aPlan: 'الخطة', aLastLogin: 'آخر دخول', aCreated: 'تاريخ الإنشاء', aProjectsWorkspaces: 'المشاريع / مساحات العمل', aCode: 'الرمز', aName: 'الاسم', aPrice: 'السعر (سنتات)', aDays: 'الأيام', aActive: 'نشط', aAddPlan: 'إضافة خطة', aSubscriptionsSmall: 'الاشتراكات', aSubsTitle: 'الاشتراكات عبر المستخدمين', aOwner: 'المالك', aStarted: 'البدء', aPeriodEnd: 'نهاية الفترة', aCancelled: 'ملغى', aTransactionsSmall: 'المعاملات', aTransactions: 'معاملات الدفع', aRevenueSmall: 'الإيرادات', aRevenue: 'الإيرادات', aNay: 'غير متاح بعد.', aAuditLogging: 'سجل التدقيق غير متاح بعد.', aHealthLead: 'حالة وقت التشغيل من الخلفية الحقيقية.', aLoading: 'جارٍ التحميل…', aEnabledProviders: 'المزوّدون المفعّلون (مفصولة بفواصل)', aAllowedModels: 'النماذج المسموحة (مفصولة بفواصل)', aEnabledTools: 'الأدوات المفعّلة (مفصولة بفواصل)', aRequireApproval: 'تتطلب الموافقة قبل تشغيل الأدوات', aSavePolicy: 'حفظ السياسة', aGithubLead: 'إعداد تطبيق GitHub وجاهزية قاعدة البيانات واتصالات الحسابات.', aLoadingStatus: 'جارٍ تحميل الحالة…', aTrialLead: 'نظرة عامة على استحقاق التجربة. تعديل مدة التجربة الافتراضية غير متاح بعد.', aPlatformSettings: 'إعدادات المنصة غير متاحة بعد.', aAdminSecurityNotAvail: 'إعدادات أمان الإدارة غير متاحة بعد.', aPersonalLead: 'حسابك الخاص. عناصر التحكم الإدارية في الصفحات الأخرى.' });
  applyPrefs();

  // Re-render the active surface after a language switch so dynamic panels match the shell.
  $$('#langBtn,.lang-mirror').forEach(function (el) {
    el.onclick = async function () {
      lang = lang === 'ar' ? 'en' : 'ar';
      applyPrefs();
      try {
        if (currentUser && (currentUser.role === 'admin' || currentUser.role === 'owner')) await setAdminView(adminView || 'overview');
        else if (currentUser && !document.querySelector('#workspacePage.active')) await setClientView(clientView || 'dashboard');
        else renderPricing();
      } catch (error) { toast(error.message); }
      savePrefs();
    };
  });

  var adminLogout = document.getElementById('adminLogoutButton');
  if (adminLogout) adminLogout.onclick = () => window.logoutSession().catch(error=>toast(error.message));

  wireChatControls();
  // Landing pricing is loaded when that page becomes visible, after auth routing.

  // --- Routing: after auth, customer -> workspace; admin/owner -> Admin Console ---
  protectedPages.add('clientPage');
  function homeFor(user) { return (user && (user.role === 'admin' || user.role === 'owner')) ? 'adminPage' : 'workspaceHomePage'; }
  async function routeHome() { clientView='dashboard'; adminView='overview'; if(!['admin','owner'].includes(currentUser?.role)&&window.openClientWorkspace)await window.openClientWorkspace();else await page(homeFor(currentUser));if(!['admin','owner'].includes(currentUser?.role)&&window.pendingCheckoutPlan){const plan=window.pendingCheckoutPlan;window.pendingCheckoutPlan=null;await window.openClientView('billing');await window.beginCheckout(plan);} }
  var _pageImpl = page;
  page = async function (id) {
    if (['admin','owner'].includes(currentUser?.role) && ['workspaceHomePage','connectionsPage','clientPage','accountPage','billingPage','workspacePage','onboarding'].includes(id)) id='adminPage';
    if (id === 'accountPage') { clientView = 'account'; id = 'clientPage'; }
    else if (id === 'billingPage') { clientView = 'billing'; id = 'clientPage'; }
    await _pageImpl(id);
    if (id === 'clientPage' && currentUser && document.querySelector('#clientPage.active')) { try { await setClientView(clientView || 'dashboard'); } catch (error) { toast(error.message); } }
  };

  // --- Client Dashboard (separate from Account/Profile) ---
  var clientView = 'dashboard';
  function clientCard(label, value, hint) {
    var card = textElement('article', '');
    card.append(textElement('small', label));
    card.append(textElement('h3', value));
    if (hint) card.append(textElement('p', hint));
    return card;
  }
  function projectCard(project) {
    var card = textElement('div', '', 'project-card');
    card.append(textElement('strong', project.name + ' · ' + project.source_type));
    if (project.remote_url) card.append(textElement('small', project.remote_url + ' · ' + (project.remote_branch || '')));
    (project.workspaces || []).forEach(function (workspace) {
      var b = textElement('button', 'Open · ' + workspace.status + ' · ' + workspace.session_count + ' session(s)', 'button ghost small');
      b.onclick = function () { openWorkspace(project, workspace); };
      card.append(b);
    });
    if (!(project.workspaces || []).length) card.append(textElement('small', 'No workspace yet'));
    var tools = textElement('div', '', 'admin-row-actions');
    var rename = textElement('button', 'Rename', 'button ghost small');
    rename.onclick = async function () {
      var name = await window.requestInput('Rename project', project.name);
      if (name === null) return; name = name.trim(); if (!name) return;
      try { await api('/api/projects/' + project.id, { method: 'PATCH', body: JSON.stringify({ name: name }) }); toast('Project renamed'); await setClientView(clientView); }
      catch (error) { toast(error.message); }
    };
    var archive = textElement('button', 'Archive', 'button ghost small');
    archive.onclick = async function () {
      if (!await window.confirmAction('Archive "' + project.name + '"? It is hidden from your dashboard but files are preserved.')) return;
      try { await api('/api/projects/' + project.id + '/archive', { method: 'POST' }); toast('Project archived'); await setClientView(clientView); }
      catch (error) { toast(error.message); }
    };
    tools.append(rename); tools.append(archive); card.append(tools);
    return card;
  }
  function renderClientSummary(data) {
    var box = document.getElementById('clientSummary'); if (!box) return;
    box.replaceChildren();
    var p = data.profile || {}, github = data.github || {}, runtime = data.runtime || {}, access = data.access || {};
    box.append(clientCard('Account status', p.status || '—', p.plan ? ('Plan: ' + p.plan) : 'No plan assigned'));
    box.append(clientCard(access.kind === 'subscription' ? 'Subscription' : 'Core trial', typeof access.remaining_days === 'number' ? access.remaining_days + ' days remaining' : '—', 'Ends ' + fmtDate(access.ends_at)));
    box.append(clientCard('GitHub', github.connected ? 'Connected' : 'Not connected', github.connected ? (github.account_login || '') : (github.configured ? 'Ready to connect' : 'GitHub App not configured')));
    box.append(clientCard('AI / OpenCode', 'Runtime: ' + (runtime.mode || 'disabled'), 'Stored credentials: ' + ((data.counts && data.counts.credentials) || 0)));
  }
  function renderClientProjects(data) {
    var recent = document.getElementById('clientRecentProjects');
    if (recent) { recent.replaceChildren(); (data.projects || []).slice(0, 5).forEach(function (p) { recent.append(projectCard(p)); }); if (!(data.projects || []).length) recent.append(textElement('p', t('noProjects'))); }
    var full = document.getElementById('clientProjectsList');
    if (full) { full.replaceChildren(); (data.projects || []).forEach(function (p) { full.append(projectCard(p)); }); if (!(data.projects || []).length) full.append(textElement('p', t('noProjects'))); }
  }
  function renderClientSessions(data) {
    var rows = [];
    (data.projects || []).forEach(function (p) { (p.workspaces || []).forEach(function (w) { rows.push({ project: p.name, workspace: w }); }); });
    [['clientRecentSessions', rows.slice(0, 5)], ['clientSessionsList', rows]].forEach(function (entry) {
      var box = document.getElementById(entry[0]); if (!box) return; box.replaceChildren();
      if (!entry[1].length) { box.append(textElement('p', 'No workspaces yet.')); return; }
      entry[1].forEach(function (r) { var d = textElement('div', '', 'project-card'); d.append(textElement('strong', r.project)); d.append(textElement('small', 'Workspace ' + r.workspace.status + ' · ' + r.workspace.session_count + ' session(s)')); box.append(d); });
    });
  }
  async function loadClientDashboard() {
    var data = await api('/api/dashboard');
    renderClientSummary(data); renderClientProjects(data); renderClientSessions(data);
  }
  async function loadClientGithub() {
    var panel = document.getElementById('clientGithubPanel');
    try { var s = await api('/api/github/status'); panel.replaceChildren(textElement('p', 'Configured: ' + (s.configured ? 'yes' : 'no') + ' · Connected: ' + (s.connected ? 'yes' : 'no') + (s.account_login ? (' · ' + s.account_login) : '')), textElement('p', 'Open Account to connect. The real GitHub authorization flow is a later phase.')); }
    catch (error) { panel.replaceChildren(textElement('p', error.message)); }
  }
  async function loadClientAi() {
    var panel = document.getElementById('clientAiPanel');
    try { var s = await api('/api/opencode/status'); panel.replaceChildren(textElement('p', 'Runtime mode: ' + s.runtime_mode + ' · healthy: ' + (s.healthy ? 'yes' : 'no')), textElement('p', 'Connect a provider inside a workspace so the key stays server-side.')); }
    catch (error) { panel.replaceChildren(textElement('p', error.message)); }
  }
  var CLIENT_LOADERS = { dashboard: loadClientDashboard, projects: loadClientDashboard, sessions: loadClientDashboard, github: loadClientGithub, ai: loadClientAi, security: async function () {} };
  function setClientView(name) {
    clientView = name;try{localStorage.setItem('og-clientview',name);}catch(error){}
    document.querySelectorAll('#clientNav [data-client-view]').forEach(function (b) { b.classList.toggle('active', b.dataset.clientView === name); });
    document.querySelectorAll('#clientPage [data-client-panel]').forEach(function (p) { p.classList.toggle('active', p.dataset.clientPanel === name); });
    var loader = CLIENT_LOADERS[name];
    if (loader) return loader();
  }
  document.querySelectorAll('#clientNav [data-client-view]').forEach(function (button) {
    button.onclick = function () { setClientView(button.dataset.clientView).catch(function (e) { toast(e.message); }); };
  });
  var clientLogout = document.getElementById('clientLogout');
  async function doLogout() {
    try { await window.logoutSession(); } catch (error) { toast(error.message); }
  }
  var logoutBtn = document.getElementById('logoutButton');
  if (logoutBtn) logoutBtn.onclick = doLogout;
  if (clientLogout) clientLogout.onclick = doLogout;

  // --- Client Billing (own subscription only) ---
  function billingCard(label, value, hint) { var c = textElement('article', ''); c.append(textElement('small', label)); c.append(textElement('h3', value)); if (hint) c.append(textElement('p', hint)); return c; }
  async function loadClientBilling() {
    var data = await api('/api/billing/subscription', { cache: 'no-store' });
    var summary = document.getElementById('billingSummary'); if (summary) {
      summary.replaceChildren();
      var planName = data.plan ? data.plan.name : tr('No plan assigned', 'لا توجد خطة');
      const end=data.access.ends_at;
      const days=data.access.remaining_days;
      summary.append(billingCard(tr('Current plan','الخطة الحالية'),data.access.kind==='subscription'?planName:tr('Core trial','تجربة الأساس')));
      summary.append(billingCard(tr('Days remaining','الأيام المتبقية'),days+' '+tr('days','يوم')));
      summary.append(billingCard(tr('Access status','حالة الوصول'),data.access.allowed?tr('Active','نشط'):tr('Expired — renew to continue','انتهت المدة — جدّد للمتابعة')));
      summary.append(billingCard(tr('Expiry','تاريخ الانتهاء'),fmtDate(end)));

    }
    var plans = document.getElementById('billingPlans'); if (plans) {
      plans.replaceChildren();
      (data.plans || []).forEach(function (plan, idx) {
        var card = textElement('div', '', 'price-card');
        var isCurrent = data.plan && data.plan.id === plan.id;
        var isSelected = data.selected_plan && data.selected_plan.id === plan.id;
        if (idx === (data.plans || []).length - 1) { var tag = textElement('span', tr('Best value', 'الأفضل قيمة'), 'plan-tag'); card.append(tag); }
        if (isCurrent || isSelected) { var chk = textElement('span', '✓', 'plan-check'); chk.title = isCurrent ? tr('Current plan', 'الخطة الحالية') : tr('Selected plan', 'الخطة المحددة'); card.append(chk); }
        card.append(textElement('b', money(plan.price_cents)));
        var duration = plan.durationLabel || planDurationLabel(plan.duration_days);
        card.append(textElement('span', planDisplayName(plan)));
        card.append(textElement('small', planDisplayTerm(plan)));
        var select = textElement('button', isCurrent ? tr('Current plan', 'الخطة الحالية') : (isSelected ? tr('Selected', 'محددة') : tr('Select', 'اختيار')), 'button small');
        if (isCurrent || isSelected) select.className = 'button small';
        select.onclick = async function () {
          try { await window.beginCheckout(plan.id); }
          catch (error) { apiMessage('billingMessage', error.message, true); }
        };
        card.append(select); plans.append(card);
      });
    }
    var note = document.getElementById('billingPaymentNote'); if (note) note.textContent = tr('Select a plan to pay using a platform method. Manual transfers activate after receipt verification. Card checkout is not configured yet.', 'اختر خطة للدفع بإحدى وسائل المنصة. يُفعّل التحويل اليدوي بعد التحقق من الاستلام. الدفع بالبطاقة غير مهيأ بعد.');


  }
  // Reuse the existing billing cards/plans without establishing normal login.
  window.loadReactivationBilling=loadClientBilling;
  var billingCancel = document.getElementById('billingCancel');if(billingCancel)billingCancel.hidden=true;
  if (billingCancel) billingCancel.onclick = async function () { try { await api('/api/billing/subscription/cancel', { method: 'POST' }); apiMessage('billingMessage', 'Subscription cancelled'); await loadClientBilling(); } catch (error) { apiMessage('billingMessage', error.message, true); } };
  var billingReactivate = document.getElementById('billingReactivate');if(billingReactivate)billingReactivate.hidden=true;
  if (billingReactivate) billingReactivate.onclick = async function () { try { await api('/api/billing/subscription/reactivate', { method: 'POST' }); apiMessage('billingMessage', 'Reactivated into pending payment'); await loadClientBilling(); } catch (error) { apiMessage('billingMessage', error.message, true); } };
  var billingRenew = document.getElementById('billingRenew');
  if (billingRenew) billingRenew.onclick = async function () { try { const state=await api('/api/billing/subscription');const plan=state.plan||state.selected_plan;if(plan)await window.beginCheckout(plan.id);else document.getElementById('billingPlans').scrollIntoView({block:'center',behavior:'smooth'}); } catch (error) { apiMessage('billingMessage', error.message, true); } };

  // Re-route the auth completion handlers so Account is not the landing page.
  $('#loginForm').onsubmit = async function (event) {
    event.preventDefault();if($('#loginSubmit').disabled||!event.currentTarget.reportValidity())return;
    const identity=value('loginIdentity'),remember=$('#rememberIdentity').checked;
    const button = $('#loginSubmit'); button.disabled = true;
    try {
      renderProfile(await api('/api/auth/login', { method: 'POST', body: JSON.stringify({ identity: value('loginIdentity'), password: $('#loginPassword').value }) }));
      $('#loginPassword').value = '';
      try{if(remember)localStorage.setItem('og-login-identity',identity);else localStorage.removeItem('og-login-identity');}catch(error){}
      await routeHome();
    } catch (error) { apiMessage('loginMessage', error.message, true); }
    finally { button.disabled = false; }
  };
  $('#registerForm').onsubmit = async function (event) {
    event.preventDefault();if($('#registerSubmit').disabled||!event.currentTarget.reportValidity())return;
    if (value('registerUsername') && value('registerUsername').length < 6) { apiMessage('registerMessage', t('usernameHint'), true); return; }
    const password = $('#registerPassword').value;
    if (password.length < 8 || !/[0-9]/.test(password) || ![...password].some(function (c) { return passwordSymbols.includes(c); })) { apiMessage('registerMessage', t('passwordHint'), true); return; }
    const button = $('#registerSubmit'); button.disabled = true;
    try {
      const prefs = { preferred_language: lang, preferred_theme: dark ? 'dark' : 'light' };
      const registered = await api('/api/auth/register', { method: 'POST', body: JSON.stringify(registrationPayload()) });
      if (registered.status === 'pending_email') {
        $('#registerPassword').value = '';
        window.showEmailCodeStep(registered,value('registerEmail'));
        return;
      }
      renderProfile(await api('/api/profile', { method: 'PATCH', body: JSON.stringify(prefs) }));
      $('#registerPassword').value = '';
      if (pendingIdea) { $('#projectName').value = pendingIdea.slice(0, 120); pendingIdea = ''; }
      await routeHome();
    } catch (error) { apiMessage('registerMessage', error.message, true); }
    finally { button.disabled = false; }
  };

  navigationReady.then(async function () {
    if(window.passwordRecoveryActive)return;
    var flag = new URLSearchParams(location.search).get('github');
    if (flag) {
      // Keep the callback outcome until the main bootstrap has opened its panel.
      if (flag === 'connected' && currentUser) toast('Check the GitHub identity and connection status.');
      if (flag === 'error') { toast('GitHub connection was not completed'); }
    }
    if (currentUser) {
      try {
        var status = await window.bootstrapGithubStatus;
        var gh = document.getElementById('chatGithub');
        if (gh && status) gh.title = status.connected ? ('GitHub connected as ' + (status.account_login || '')) : (status.configured ? 'GitHub not connected' : 'GitHub integration not configured');
      } catch (error) { /* leave the truthful default title */ }
    }
  });

  // --- Client UI professionalism pass ---
  function tr(en, ar) { return lang === 'ar' ? ar : en; }
  function fmtDate(iso) { if (!iso) return '—'; try { return new Date(iso).toLocaleDateString(lang === 'ar' ? 'ar-u-nu-latn' : 'en-GB'); } catch (e) { return '—'; } }
  function badge(text, kind) { return textElement('span', text, 'badge ' + (kind || 'muted')); }
  function navIcon(href) { var s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.className = 'nav-icon'; s.setAttribute('aria-hidden', 'true'); var u = document.createElementNS('http://www.w3.org/2000/svg', 'use'); u.setAttribute('href', href); s.appendChild(u); return s; }
  function scIcon(href) { var d = textElement('div', '', 'sc-icon'); d.appendChild(navIcon(href)); return d; }
  function banner(iconHref, text) { var b = textElement('div', text, 'banner'); if (iconHref) b.insertBefore(navIcon(iconHref), b.firstChild); return b; }
  function emptyState(iconHref, title, desc, actionLabel, actionFn) { var box = textElement('div', '', 'empty-state'); var ic = textElement('div', '', 'es-icon'); ic.appendChild(navIcon(iconHref)); box.append(ic); box.append(textElement('h3', title)); if (desc) box.append(textElement('p', desc)); if (actionLabel && actionFn) { var b = textElement('button', actionLabel, 'button'); b.onclick = actionFn; box.append(b); } return box; }
  function listCard(iconHref, title, subtitle) { var card = textElement('div', '', 'list-card'); var ic = textElement('div', '', 'lc-icon'); ic.appendChild(navIcon(iconHref)); card.append(ic); var main = textElement('div', '', 'lc-main'); main.append(textElement('b', title)); if (subtitle) main.append(textElement('small', subtitle)); card.append(main); card.append(textElement('div', '', 'lc-actions')); return card; }
  function statusBadge(status) { var map = { ready: ['good', tr('Ready', 'جاهز')], creating: ['info', tr('Creating', 'جارٍ الإنشاء')], failed: ['danger', tr('Failed', 'فشل')], pushed: ['good', tr('Pushed', 'تم الدفع')], active: ['good', tr('Active', 'نشط')], suspended: ['danger', tr('Suspended', 'موقوف')], cancelled: ['danger', tr('Cancelled', 'ملغى')], pending_payment: ['info', tr('Pending payment', 'بانتظار الدفع')], trial: ['info', tr('Trial', 'تجريبي')], completed: ['good', tr('Completed', 'مكتمل')], idle: ['muted', tr('Idle', 'خامل')], submitted: ['info', tr('Running', 'قيد التشغيل')] }; var m = map[status]; return badge(m ? m[1] : status, m ? m[0] : 'muted'); }
  function statusText(status) { var m = { ready: tr('Ready', 'جاهز'), creating: tr('Creating', 'جارٍ الإنشاء'), failed: tr('Failed', 'فشل'), pushed: tr('Pushed', 'تم الدفع'), active: tr('Active', 'نشط'), suspended: tr('Suspended', 'موقوف'), cancelled: tr('Cancelled', 'ملغى'), pending_payment: tr('Pending payment', 'بانتظار الدفع'), trial: tr('Trial', 'تجريبي'), completed: tr('Completed', 'مكتمل'), idle: tr('Idle', 'خامل'), submitted: tr('Running', 'قيد التشغيل'), expired: tr('Expired', 'منتهي') }; return m[status] || status; }
  function projectSourceIcon(source) { return source === 'github' ? '#icon-github' : (source === 'template' ? '#icon-grid' : '#icon-folder'); }

  function injectNavIcons() {
    var map = { dashboard: '#icon-home', projects: '#icon-folder', sessions: '#icon-chat', opencode: '#icon-opencode', ai: '#icon-opencode', github: '#icon-github', billing: '#icon-file', account: '#icon-user', security: '#icon-shield', overview: '#icon-grid', users: '#icon-user', plans: '#icon-file', reports: '#icon-diff', audit: '#icon-file', health: '#icon-terminal', policy: '#icon-shield', trial: '#icon-clock', settings: '#icon-settings' };
    document.querySelectorAll('#clientNav button, #adminNav button').forEach(function (b) {
      if (b.querySelector('.nav-icon')) return;
      var key = b.dataset.clientView || b.dataset.adminView || (b.dataset.go === 'billingPage' ? 'billing' : (b.dataset.go === 'accountPage' ? 'account' : ''));
      var href = map[key]; if (!href) return;
      var label = document.createElement('span'); label.className = 'nav-label';
      var i18nKey = b.dataset.i18n;
      if (i18nKey) { label.dataset.i18n = i18nKey; b.removeAttribute('data-i18n'); }
      label.textContent = b.textContent;
      b.textContent = '';
      b.appendChild(navIcon(href));
      b.appendChild(label);
    });
  }

  function projectNode(p) {
    var card = listCard(projectSourceIcon(p.source_type), p.name, p.source_type + (p.remote_branch ? ' · ' + p.remote_branch : ''));
    var actions = card.querySelector('.lc-actions');
    (p.workspaces || []).forEach(function (w) {
      card.querySelector('.lc-main').append(textElement('small', tr('Workspace', 'مساحة عمل') + ': ' + w.status + ' · ' + w.session_count + ' ' + tr('sessions', 'جلسات')));
      if (w.cache && (w.cache.warning || w.cache.expired)) card.querySelector('.lc-main').append(textElement('small', window.workspaceRetentionNotice(w.cache), 'project-retention-warning'));
      var open = textElement('button', tr('Open', 'فتح'), 'button ghost small'); open.onclick = function () { openWorkspace(p, w); }; actions.append(open);
    });
    var rename = textElement('button', tr('Rename', 'إعادة تسمية'), 'button ghost small');
    rename.onclick = async function () { var n = await window.requestInput(tr('Rename project', 'إعادة تسمية المشروع'), p.name); if (n === null) return; n = n.trim(); if (!n) return; try { await api('/api/projects/' + p.id, { method: 'PATCH', body: JSON.stringify({ name: n }) }); toast(tr('Project renamed', 'تمت إعادة التسمية')); await setClientView(clientView); } catch (e) { toast(e.message); } };
    var archive = textElement('button', tr('Archive', 'أرشفة'), 'button ghost small');
    archive.onclick = async function () { if (!await window.confirmAction(tr('Archive this project? Files are preserved.', 'أرشفة هذا المشروع؟ تُحفظ الملفات.'))) return; try { await api('/api/projects/' + p.id + '/archive', { method: 'POST' }); toast(tr('Project archived', 'تمت الأرشفة')); await setClientView(clientView); } catch (e) { toast(e.message); } };
    actions.append(rename); actions.append(archive);
    return card;
  }

  loadClientDashboard = async function () {
    var data = await api('/api/dashboard');
    var p = data.profile || {}, gh = data.github || {}, rt = data.runtime || {}, access = data.access || {};
    var box = document.getElementById('clientSummary'); if (box) {
      box.replaceChildren(); box.className = 'card-grid';
      var items = [
        ['#icon-file', tr('Plan / Trial', 'الخطة / التجربة'), access.kind === 'subscription' ? p.plan : tr('Core trial', 'تجربة الأساس'), access.allowed ? tr('Active', 'نشط') : tr('Expired', 'منتهي')],
        ['#icon-clock', tr('Days remaining', 'الأيام المتبقية'), (typeof access.remaining_days === 'number' ? access.remaining_days : '—'), tr('Ends', 'تنتهي') + ' ' + fmtDate(access.ends_at)],
        ['#icon-opencode', tr('OpenCode', 'OpenCode'), rt.mode === 'local' ? tr('Local runtime', 'تشغيل محلي') : tr('Runtime disabled', 'التشغيل معطّل'), tr('Mode', 'الوضع') + ': ' + (rt.mode || 'disabled')],
        ['#icon-github', tr('GitHub', 'GitHub'), gh.connected ? tr('Connected', 'متصل') : tr('Not connected', 'غير متصل'), gh.connected ? (gh.account_login || '') : (gh.configured ? tr('Ready to connect', 'جاهز للربط') : tr('Not configured', 'غير مكوّن'))],
        ['#icon-folder', tr('Projects', 'المشاريع'), (data.counts ? data.counts.projects : 0), tr('Workspaces', 'مساحات العمل') + ': ' + (data.counts ? data.counts.workspaces : 0)],
        ['#icon-chat', tr('Sessions', 'الجلسات'), (data.counts ? data.counts.sessions : 0), tr('Total', 'الإجمالي')]
      ];
      items.forEach(function (it) { var card = textElement('div', '', 'summary-card'); card.append(scIcon(it[0])); var t = textElement('div', ''); t.append(textElement('small', it[1])); t.append(textElement('b', it[2])); var sm = textElement('small', it[3]); t.append(sm); card.append(t); box.append(card); });
    }
    var qa = document.getElementById('clientQuickActions');
    if (!qa) { qa = textElement('div', '', 'quick-actions'); qa.id = 'clientQuickActions';
      [['#icon-plus', tr('New project', 'مشروع جديد'), function () { page('onboarding'); }], ['#icon-folder', tr('Open workspace', 'فتح مساحة عمل'), function () { setClientView('projects'); }], ['#icon-github', tr('New GitHub connection', 'ربط GitHub جديد'), function () { void window.startFreshGithubConnection(); }], ['#icon-opencode', tr('Configure AI provider', 'تهيئة مزوّد الذكاء'), function () { setClientView('ai'); }]].forEach(function (q) { var btn = textElement('button', '', 'button ghost'); btn.appendChild(navIcon(q[0])); btn.appendChild(textElement('span', q[1])); btn.onclick = q[2]; qa.append(btn); });
      var summaryEl = document.getElementById('clientSummary'); if (summaryEl && summaryEl.parentNode) summaryEl.parentNode.insertBefore(qa, summaryEl);
    }
    renderClientProjectsUI(data); renderClientSessionsUI(data);
  };

  function renderClientProjectsUI(data) {
    var box = document.getElementById('clientRecentProjects'); var full = document.getElementById('clientProjectsList');
    if (box) box.replaceChildren(); if (full) full.replaceChildren();
    var projects = data.projects || [];
    if (!projects.length) { var es = emptyState('#icon-folder', tr('No projects yet', 'لا توجد مشاريع بعد'), tr('Create a blank project or start from a template.', 'أنشئ مشروعًا فارغًا أو ابدأ من قالب.'), tr('New project', 'مشروع جديد'), function () { page('onboarding'); }); if (box) box.append(es); if (full) full.append(es); return; }
    projects.forEach(function (p) { if (full) full.append(projectNode(p)); });
    projects.slice(0, 5).forEach(function (p) { if (box) box.append(projectNode(p)); });
  }

  var clientSessionsRevision = 0;
  async function renderClientSessionsUI(data) {
    var revision = ++clientSessionsRevision, owner = currentUser && currentUser.id;
    var box = document.getElementById('clientRecentSessions'); var full = document.getElementById('clientSessionsList');
    if (box) box.replaceChildren(); if (full) full.replaceChildren();
    var ws = []; (data.projects || []).forEach(function (p) { (p.workspaces || []).forEach(function (w) { ws.push({ project: p.name, projectObj: p, workspace: w }); }); });
    var rows;
    try { rows = await api('/api/sessions?include_archived=true'); }
    catch (e) { if (revision === clientSessionsRevision && full) full.append(textElement('p', e.message, 'api-message show error')); return; }
    if (revision !== clientSessionsRevision || !currentUser || currentUser.id !== owner) return;
    var all = rows.map(function (s) { var context = ws.find(function (w) { return w.workspace.id === s.workspace_id; }); return context ? Object.assign({ session: s }, context) : null; }).filter(Boolean);
    var category = full && full.dataset.sessionCategory || 'active';
    var labels = {active:tr('Active','نشطة'), running:tr('Running','قيد التنفيذ'), closed:tr('Closed','مغلقة'), archived:tr('Archived','مؤرشفة'), completed:tr('Completed','مكتملة'), failed:tr('Failed','فشلت')};
    function action(r, kind, label) {
      var button = textElement('button', label, 'button ghost small'); button.type = 'button'; button.dataset.sessionAction = kind;
      button.onclick = async function () {
        if (kind === 'delete' && !await window.confirmAction(tr('Delete from client history? OpenCode history and project files are preserved.', 'حذف من سجل العميل؟ يبقى سجل OpenCode وملفات المشروع محفوظة.'))) return;
        button.disabled = true;
        try {
          if (kind === 'open') { await openWorkspace(r.projectObj, r.workspace); await selectSession(r.session); return; }
          var result = await api('/api/sessions/' + r.session.id + (kind === 'delete' ? '' : '/' + kind), {method:kind === 'delete' ? 'DELETE' : 'POST'});
          window.dispatchEvent(new CustomEvent('workspace-session-lifecycle', {detail:{sessionId:r.session.id, workspaceId:r.workspace.id, action:kind, result:result}}));
          await renderClientSessionsUI(data);
        } catch (e) { toast(e.message); } finally { button.disabled = false; }
      }; return button;
    }
    function render(target, list, managed) {
      if (!target) return; target.replaceChildren();
      if (managed) {
        var filters = textElement('div', '', 'session-filters');
        [['active','Active','نشطة'],['closed','Previous / Closed','سابقة / مغلقة'],['archived','Archived','مؤرشفة']].forEach(function (entry) {
          var button = textElement('button', tr(entry[1],entry[2]), 'button ghost small');button.type='button';button.id='clientSessions-'+entry[0];button.setAttribute('aria-pressed',String(category===entry[0]));
          button.onclick=function(){full.dataset.sessionCategory=entry[0];category=entry[0];render(full,all.filter(function(r){return r.session.lifecycle===category;}),true);};filters.append(button);
        });target.append(filters);
      }
      if (!list.length) { target.append(emptyState('#icon-chat', tr('No sessions in this category', 'لا توجد جلسات في هذا القسم'), tr('Open a workspace or choose another category.', 'افتح مساحة عمل أو اختر قسمًا آخر.'))); return; }
      list.forEach(function (r) {
        var card = listCard('#icon-chat', r.session.title || tr('Session', 'جلسة'), r.project + ' · ' + (labels[r.session.status] || r.session.status)), actions = card.querySelector('.lc-actions');card.dataset.sessionId=r.session.id;
        actions.append(statusBadge(r.session.status));
        if (r.session.lifecycle === 'archived') actions.append(action(r,'restore',tr('Restore','استعادة')));
        else { actions.append(action(r,'open',tr('Open','فتح'))); if (managed) actions.append(action(r,r.session.lifecycle==='active'?'close':'archive',r.session.lifecycle==='active'?tr('Close / Disconnect','إغلاق / فصل'):tr('Archive','أرشفة'))); }
        if (managed && r.session.lifecycle !== 'active') actions.append(action(r,'delete',tr('Delete from history','حذف من السجل')));
        target.append(card);
      });
    }
    render(box,all.filter(function(r){return r.session.lifecycle!=='archived';}).slice(0,5),false);
    render(full,all.filter(function(r){return r.session.lifecycle===category;}),true);
  }

  loadClientGithub = async function () {
    var panel = document.getElementById('clientGithubPanel'); if (!panel) return;
    try { var s = await api('/api/github/status');
      if(s.pending){panel.replaceChildren();window.renderGithubConfirmation(panel,s,loadClientGithub);return;}
      if (s.connected) {
        panel.replaceChildren();
        panel.append(textElement('h3', tr('GitHub connected', 'GitHub متصل')));
        panel.append(textElement('p', (s.account_login || '') + ' · ' + (s.target_type || 'User')));
        var disc = textElement('button', tr('Disconnect', 'فصل'), 'button ghost'); disc.onclick = async function () { try { if(!await window.confirmAction(tr('Disconnect GitHub, revoke its token and remove your verified personal App installation? All project files and unpushed changes remain.','فصل GitHub وإبطال رمزه وإزالة تثبيت التطبيق الشخصي المتحقق؟ تبقى ملفات المشاريع والتعديلات غير المرفوعة.')))return; await api('/api/github/disconnect', { method: 'POST' }); toast(tr('Disconnected', 'تم الفصل')); await loadClientGithub(); } catch (e) { toast(e.message); } }; panel.append(disc);
      } else {
        var cp = textElement('div', '', 'connect-panel');
        var ic = textElement('div', '', 'cp-icon'); ic.appendChild(navIcon('#icon-github')); cp.append(ic);
        cp.append(textElement('h3', tr('New GitHub connection', 'ربط GitHub جديد')));
        cp.append(textElement('p', tr('Link your GitHub account to clone repositories and push changes. Tokens stay on the server and are never stored in your browser.', 'اربط حسابك على GitHub لاستنساخ المستودعات وإرسال التغييرات. تبقى الرموز على الخادم ولا تُخزَّن في متصفحك.')));
        var btn = textElement('button', tr('New GitHub connection', 'ربط GitHub جديد'), 'button');
        btn.onclick = function () { void window.startFreshGithubConnection(); };
        if (!s.configured) { btn.disabled = true; btn.title = tr('GitHub App is not configured', 'تطبيق GitHub غير مكوّن'); }
        cp.append(btn); panel.replaceChildren(cp);
      }
    } catch (e) { panel.replaceChildren(textElement('p', e.message)); }
  };

  loadClientAi = async function () {
    var panel = document.getElementById('clientAiPanel'); if (!panel) return;
    panel.replaceChildren();
    try {
      var s = await api('/api/opencode/status');
      var rtCard = listCard('#icon-opencode', tr('Runtime', 'وقت التشغيل'), tr('Status', 'الحالة') + ': ' + (s.healthy ? tr('healthy', 'سليم') : tr('unavailable', 'غير متاح')) + ' · ' + tr('Mode', 'الوضع') + ': ' + s.runtime_mode);
      rtCard.querySelector('.lc-actions').append(statusBadge(s.healthy ? 'ready' : 'failed')); panel.append(rtCard);
      panel.append(listCard('#icon-settings', tr('Provider', 'المزوّد'), tr('Connect a provider inside a workspace; the key stays server-side.', 'اربط مزوّدًا داخل مساحة عمل؛ يبقى المفتاح على الخادم.')));
      panel.append(listCard('#icon-shield', tr('Tools & permissions', 'الأدوات والأذونات'), tr('Sensitive commands always require approval.', 'الأوامر الحساسة تتطلب موافقة دائمًا.')));
      var qa = textElement('div', '', 'quick-actions'); var cta = textElement('button', tr('Open OpenCode Workspace', 'فتح مساحة عمل OpenCode'), 'button'); cta.onclick = function () { setClientView('projects'); }; qa.append(cta); panel.append(qa);
      if (s.runtime_mode !== 'local') panel.append(banner('#icon-opencode', tr('OpenCode is disabled on this server. The runtime is available only for trusted local development and is not publicly exposed.', 'OpenCode معطّل على هذا الخادم. وقت التشغيل متاح للتطوير المحلي الموثوق فقط وغير معرّض للعامة.')));
    } catch (e) { panel.replaceChildren(textElement('p', e.message)); }
  };

  async function renderSecurityPanel() {
    var panel = document.getElementById('clientSecurityPanel'); if (!panel) return;
    panel.replaceChildren();
    [['#icon-shield', tr('Password', 'كلمة المرور'), tr('Password change is not available yet.', 'تغيير كلمة المرور غير متاح بعد.'), 'muted', tr('Coming later', 'لاحقًا')], ['#icon-user', tr('Active session', 'الجلسة النشطة'), tr('HttpOnly, SameSite=Strict cookie.', 'ملف تعريف ارتباط HttpOnly وSameSite=Strict.'), 'good', tr('Active', 'نشطة')], ['#icon-settings', tr('Two-factor authentication', 'المصادقة الثنائية'), tr('Not configured.', 'غير مكوّنة.'), 'muted', tr('Not configured', 'غير مكوّنة')], ['#icon-terminal', tr('Devices & sessions', 'الأجهزة والجلسات'), tr('Device management is not available yet.', 'إدارة الأجهزة غير متاحة بعد.'), 'muted', tr('Coming later', 'لاحقًا')]].forEach(function (r) { var row = listCard(r[0], r[1], r[2]); row.append(badge(r[4], r[3])); panel.append(row); });
  }

  function accountText(tag,en,ar,cls){const node=textElement(tag,tr(en,ar),cls);node.dataset.accountEn=en;node.dataset.accountAr=ar;return node;}
  async function loadClientAccount() {
    var user=currentUser;if(!user)return;renderProfile(user);
    var box=document.getElementById('accountSummary');if(!box)return;box.replaceChildren();
    var information=textElement('div','', 'summary-card');information.id='accountUsage';information.append(textElement('p',tr('Loading usage and access…','جارٍ تحميل الاستخدام والصلاحيات…')));box.append(information);
    try {
      var data=await api('/api/dashboard');if(currentUser?.id!==user.id)return;renderProfile(data.profile);
      var access=data.access,advanced=access.advanced_trial;
      var heading=textElement('header','','account-card-heading'),icon=textElement('span','','account-card-icon');icon.append(navIcon('#icon-shield'));
      var headingText=textElement('div');headingText.append(accountText('h3','Account status','حالة الحساب'),accountText('p','Your current access.','معلومات الوصول الحالية.'));
      var stateNames={active:['Active','نشط'],suspended:['Suspended','معلّق'],deletion_requested:['Deletion requested','طلب حذف'],archived:['Archived','مؤرشف']};
      var state=accountText('span',...(stateNames[data.profile.status]||['Unavailable','غير متاح']),'account-state');heading.append(icon,headingText,state);information.replaceChildren(heading);
      var plan=access.reason==='subscription'?(data.profile.plan?[data.profile.plan,data.profile.plan]:['Active subscription','اشتراك نشط']):access.allowed?['Core trial','تجربة الأساس']:['Access expired','انتهت مدة الوصول'];
      var planRow=textElement('div','','account-info-row');planRow.append(accountText('small','Current access','الوصول الحالي'),accountText('span',...plan));information.append(planRow);
      var daysRow=textElement('div','','account-info-row');var days=access.remaining_days??access.core_trial.remaining_days;daysRow.append(accountText('small','Time remaining','الوقت المتبقي'),accountText('span',days+' days',days+' يومًا','account-days'));information.append(daysRow);
      var advancedNotice=textElement('div','','account-advanced-notice');advancedNotice.append(navIcon('#icon-clock'),accountText('p',advanced.state==='not_started'?'Advanced trial: 10 days from first actual use, capped by core trial.':'Advanced trial: '+advanced.remaining_days+' days remaining',advanced.state==='not_started'?'التجربة المتقدمة: 10 أيام من أول استخدام فعلي ولا تتجاوز تجربة الأساس.':'التجربة المتقدمة: '+advanced.remaining_days+' يوم متبقٍ'));information.append(advancedNotice);
      var billing=accountText('button','View subscription & invoices','عرض الاشتراك والفواتير','button ghost small account-billing-link');billing.type='button';billing.onclick=()=>window.openClientView('billing');information.append(billing);
      var extras=document.getElementById('accountDetailsBody');extras.replaceChildren();
      var language=document.getElementById('accountLanguage'),appearance=document.getElementById('accountAppearance');language.value=lang;appearance.value=dark?'dark':'light';
      language.onchange=async()=>{lang=language.value;await savePrefs();await window.openClientView('account');};appearance.onchange=async()=>{dark=appearance.value==='dark';await savePrefs();};
      document.querySelector('[data-client-panel=account] [data-edit-profile]').onclick=async()=>{var values=await window.requestForm(tr('Edit phone','تعديل الهاتف'),[{name:'phone',label:tr('Phone with international calling code','الهاتف مع مفتاح الاتصال الدولي'),type:'tel',value:currentUser.phone||'',required:true}]);if(!values)return;try{await api('/api/profile',{method:'PATCH',body:JSON.stringify({phone:values.phone.trim()})});renderProfile(await api('/api/profile'));toast(tr('Profile updated','تم تحديث الملف'));}catch(error){toast(error.message);}};
      document.getElementById('accountReturnWorkspace').onclick=()=>window.openClientWorkspace().catch(error=>toast(error.message));
      document.querySelectorAll('[data-account-section]').forEach(button=>button.onclick=()=>window.openClientView(button.dataset.accountSection));
      var connections=textElement('button',tr('Connected providers · selected workspace','المزوّدات المتصلة · مساحة العمل المختارة'),'button ghost small');connections.onclick=()=>window.openConnections('providers');extras.append(connections);
      if(!access.advanced_integrations||!access.core_access){var upgrade=textElement('button',tr('View plans / upgrade','عرض الخطط / الاشتراك'),'button small');upgrade.onclick=()=>window.openClientView('billing');extras.append(upgrade);}
      var storage=document.createElement('details');storage.append(textElement('summary',tr('Local project storage (50 MB each)','تخزين المشاريع المحلية (50 MB لكل مشروع)')));var usage=textElement('div','');storage.append(usage);extras.append(storage);var loaded=false;
      storage.ontoggle=async()=>{if(!storage.open||loaded)return;loaded=true;usage.replaceChildren(textElement('p',tr('Loading storage usage…','جارٍ تحميل استخدام التخزين…')));try{var rows=await Promise.all(data.projects.filter(p=>p.source_type!=='github').flatMap(p=>p.workspaces.map(async w=>{var s=await api('/api/workspaces/'+w.id+'/storage');return p.name+' · '+s.used_mb+' / '+s.limit_mb+' MB';})));if(currentUser?.id!==user.id)return;usage.replaceChildren(...rows.map(value=>textElement('p',value)));if(!rows.length)usage.append(textElement('p',tr('No local projects yet','لا توجد مشاريع محلية بعد')));}catch(error){loaded=false;usage.replaceChildren(textElement('p',error.message));}};
      var signIns=textElement('div','','account-sign-ins');signIns.append(textElement('h4',tr('Link a sign-in identity','ربط هوية للدخول')));extras.append(signIns);
      api('/api/auth/social/options').then(function(options){if(currentUser?.id!==user.id||!signIns.isConnected)return;for(const provider of ['google']){var link=textElement('button',tr('Link sign-in with ','ربط الدخول عبر ')+provider,'button ghost small');link.disabled=!options[provider];link.title=link.disabled?tr('Not configured on this server','غير مهيأ على هذا الخادم'):'';link.onclick=()=>window.linkSignInProvider(provider);signIns.append(link);}signIns.append(textElement('p',tr('Sign-in identity does not authorize GitHub repositories. Linking requires an active sign-in session.','هوية الدخول لا تمنح صلاحية لمستودعات GitHub. الربط يتطلب جلسة دخول نشطة.')));}).catch(function(error){signIns.append(textElement('p',error.message));});
      extras.append(textElement('h4',tr('How your data is handled','كيف تُدار بياناتك')),textElement('p',tr('Local projects remain on Gateway. GitHub repositories remain in your GitHub account; OpenCode uses a server-side working copy. Credentials are encrypted server-side. Trial expiry does not delete files. Local project files are cleaned after 7 days of meaningful inactivity; temporary GitHub worktrees after 73 hours. Customer records are archived after 90 days of expired access; identity, billing history and explicit marketing-consent state are preserved, while operational secrets are removed. Hardware isolation is not provided.','تبقى المشاريع المحلية في Gateway ومستودعات GitHub في حسابك؛ يستخدم OpenCode نسخة عمل على الخادم. تُشفّر بيانات الاعتماد على الخادم. انتهاء التجربة لا يحذف الملفات. تُنظّف ملفات المشاريع المحلية بعد 7 أيام من الخمول الحقيقي ونسخ GitHub المؤقتة بعد 73 ساعة. يُؤرشف العميل بعد 90 يومًا من انتهاء الوصول مع حفظ الهوية وسجل الفوترة وحالة الموافقة التسويقية الصريحة، وتنظيف بيانات التشغيل الحساسة. لا يُقدّم عزل عتادي.')));
    } catch(error){if(currentUser?.id===user.id)information.replaceChildren(textElement('p',error.message));}
  }

  CLIENT_LOADERS = { dashboard: loadClientDashboard, projects: loadClientDashboard, sessions: loadClientDashboard, github: loadClientGithub, ai: loadClientAi, billing: loadClientBilling, account: loadClientAccount, security: renderSecurityPanel };
  injectNavIcons();

  var editProfile = textElement('button', tr('Edit profile', 'تعديل الملف'), 'button ghost small'); editProfile.type = 'button';
  editProfile.onclick = async function () {
    var values=await window.editProfileForm();if(!values)return;var phone=values.phone,postal=values.postal_code;
    var body = {};
    if (phone.trim()) body.phone = phone.trim(); if (postal.trim()) body.postal_code = postal.trim();
    try { await api('/api/profile', { method: 'PATCH', body: JSON.stringify(body) }); renderProfile(await api('/api/profile')); toast(tr('Profile updated', 'تم تحديث الملف')); } catch (e) { toast(e.message); }
  };
  var personalInfo = document.querySelector('#accountPage .settings-list');
  if (personalInfo) personalInfo.append(editProfile);
  /* ===== fixed headers, header auth, back navigation, advanced data grids ===== */
  'use strict';

  var tr = function (a, b) { return lang === 'ar' ? b : a; };
  function icon(id, cls) {
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', cls || 'ui-icon');
    svg.setAttribute('aria-hidden', 'true');
    var use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    use.setAttribute('href', '#' + id);
    svg.append(use);
    return svg;
  }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = String(text);
    return n;
  }

  /* ============ 1. header actions: back + login on every page ============ */
  var navStack = ['landing'];
  var goingBack = false;

  var HEADERS = [
    { sel: '.welcome-topbar', host: 'landing' },
    { sel: '#authPage .onboard-top', host: 'authPage' },
    { sel: '#onboarding .onboard-top', host: 'onboarding' },
    { sel: '#clientPage .portal-header', host: 'clientPage' },
    { sel: '#adminPage .portal-header', host: 'adminPage' },
    { sel: '#workspacePage .project-bar', host: 'workspacePage' },
  ];

  function syncHeaderState() {
    var authed = !!currentUser;
    document.querySelectorAll('[data-header-login]').forEach(function (b) { b.hidden = authed; });
    document.querySelectorAll('[data-page-back]').forEach(function (b) { b.hidden = navStack.length < 2; });
  }

  HEADERS.forEach(function (cfg) {
    var header = document.querySelector(cfg.sel);
    if (!header || header.querySelector('[data-page-back]')) return;

    var cluster = el('div', 'header-actions');

    var back = el('button', 'icon page-back');
    back.type = 'button';
    back.setAttribute('data-page-back', '');
    back.setAttribute('aria-label', tr('Back', 'رجوع'));
    back.title = tr('Back', 'رجوع');
    back.hidden = true;
    back.append(icon('icon-back'));
    back.onclick = function () {
      if (navStack.length < 2) return;
      navStack.pop();
      goingBack = true;
      page(navStack[navStack.length - 1]);
    };
    header.insertBefore(back, header.firstChild);

    if (cfg.host !== 'clientPage' && cfg.host !== 'adminPage') {
      var login = el('button', 'button ghost small');
      login.type = 'button';
      login.setAttribute('data-header-login', '');
      login.append(icon('icon-login'), el('span', '', tr('Sign in', 'تسجيل الدخول')));
      login.onclick = function () { page('authPage'); };
      cluster.append(login);
    }

    var logout = header.querySelector('#logoutButton, #adminLogoutButton');
    var mirror = header.querySelector('.lang-mirror');
    if (logout) cluster.append(logout);
    if (mirror) cluster.append(mirror);
    header.append(cluster);
  });

  document.addEventListener('click', function (event) {
    var t = event.target.closest('[data-signout]');
    if (!t) return;
    event.preventDefault();
    window.logoutSession().catch(function (error) { toast(error.message); });
  });

  function signOutRow() {
    var row = el('div', 'signout-row');
    row.append(el('p', '', tr('Signed in as', 'مسجّل الدخول باسم') + ' ' + (currentUser ? currentUser.email : '')));
    var b = el('button', 'button ghost small');
    b.type = 'button';
    b.setAttribute('data-signout', '');
    b.append(icon('icon-logout'), el('span', '', tr('Sign out', 'تسجيل الخروج')));
    row.append(b);
    return row;
  }

  /* ============ 2. navigation stack ============ */
  var innerPage = page;
  page = async function (id) {
    if (!goingBack && navStack[navStack.length - 1] !== id) {
      navStack.push(id);
      if (navStack.length > 25) navStack.shift();
    }
    goingBack = false;
    await innerPage(id);
    if (id === 'landing') await renderPricing();
    syncHeaderState();
  };
  syncHeaderState();

  /* ============ 3. advanced data grid ============ */
  function gridBtn(iconId, label, onClick, disabled) {
    var b = el('button', 'grid-btn');
    b.type = 'button';
    b.title = label;
    b.setAttribute('aria-label', label);
    if (disabled) {
      b.setAttribute('aria-disabled', 'true');
      b.disabled = true;
    } else {
      b.onclick = onClick;
    }
    b.append(icon(iconId));
    return b;
  }

  function cellActions(items) {
    var wrap = el('div', 'grid-actions');
    items.forEach(function (it) { wrap.append(gridBtn(it[0], it[1], it[2], it[3])); });
    return wrap;
  }

  /* Wrap a table into a searchable / sortable grid. Re-runnable. */
  function enhanceGrid(tbody, opts) {
    opts = opts || {};
    var table = tbody.closest('table');
    if (!table) return null;
    var wrap = table.closest('.datagrid') || table.parentNode;
    if (!wrap.classList.contains('datagrid')) {
      wrap.classList.add('datagrid');
      var tools = el('div', 'datagrid-tools');
      var search = el('div', 'grid-search');
      var input = document.createElement('input');
      input.type = 'search';
      input.placeholder = tr('Search rows', 'ابحث في الصفوف');
      input.setAttribute('aria-label', tr('Search rows', 'ابحث في الصفوف'));
      search.append(icon('icon-search'), input);
      var count = el('span', 'grid-count');
      tools.append(search, count);
      wrap.insertBefore(tools, wrap.firstChild);
      var scroll = el('div', 'grid-scroll');
      wrap.append(scroll);
      scroll.append(table);
      if (opts.readonly) {
        var note = el('div', 'grid-note');
        note.append(el('span', 'readonly-pill', tr('Read only', 'للقراءة فقط')), el('span', '', opts.readonly));
        wrap.append(note);
      }
    }
    var countEl = wrap.querySelector('.grid-count');
    var searchInput = wrap.querySelector('.grid-search input');
    if (searchInput) searchInput.oninput = function () { filter(searchInput.value); };
    var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));

    rows.forEach(function (row, index) {
      row.dataset.rowId = row.dataset.rowId || String(index);
      if (opts.actions) {
        var last = row.lastElementChild;
        if (last && !last.classList.contains('grid-actions')) {
          var td = document.createElement('td');
          td.append(opts.actions(row, index));
          row.append(td);
        }
      }
    });

    function filter(term) {
      var q = (term || '').trim().toLowerCase();
      var shown = 0;
      rows.forEach(function (row) {
        var hit = !q || row.textContent.toLowerCase().indexOf(q) !== -1;
        row.hidden = !hit;
        if (hit) shown++;
      });
      if (countEl) countEl.textContent = shown + ' / ' + rows.length;
      return shown;
    }

    Array.prototype.forEach.call(table.querySelectorAll('thead th'), function (th, i) {
      if (th.querySelector('.sort-ind')) return;
      th.classList.add('sortable');
      th.append(el('span', 'sort-ind', ''));
      th.addEventListener('click', function () {
        var asc = th.dataset.dir !== 'asc';
        table.querySelectorAll('thead th').forEach(function (o) { o.dataset.dir = ''; o.querySelector('.sort-ind').textContent = ''; });
        th.dataset.dir = asc ? 'asc' : 'desc';
        th.querySelector('.sort-ind').textContent = asc ? '▲' : '▼';
        rows.slice().sort(function (a, b) {
          var av = (a.children[i] ? a.children[i].textContent : '').trim();
          var bv = (b.children[i] ? b.children[i].textContent : '').trim();
          var an = parseFloat(av.replace(/[^0-9.]/g, ''));
          var bn = parseFloat(bv.replace(/[^0-9.]/g, ''));
          var cmp = (!isNaN(an) && !isNaN(bn)) ? an - bn : av.localeCompare(bv);
          return asc ? cmp : -cmp;
        }).forEach(function (r) { tbody.append(r); });
      });
    });

    filter('');
    return { filter: filter, rows: rows };
  }

  /* ============ 4. modal ============ */
  var modal = null;
  function ensureModal() {
    if (modal) return modal;
    modal = el('dialog', 'grid-modal');modal.addEventListener('close',()=>modal.classList.remove('open'));
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    var card = el('div', 'grid-modal-card');
    var head = el('div', 'grid-modal-head');
    var title = el('h3', '', '');
    var close = el('button', 'icon');
    close.type = 'button';
    close.setAttribute('aria-label', tr('Close', 'إغلاق'));
    close.append(icon('icon-close'));
    close.onclick = function () { modal.close(); };
    head.append(title, close);
    var body = el('div', 'grid-modal-body');
    var foot = el('div', 'grid-modal-foot');
    var cancel = el('button', 'button ghost small', tr('Close', 'إغلاق'));
    cancel.type = 'button';
    cancel.onclick = function () { modal.close(); };
    foot.append(cancel);
    card.append(head, body, foot);
    modal.append(card);
    modal.addEventListener('click', function (e) { if (e.target === modal) modal.close(); });
    document.body.append(modal);
    modal.titleEl = title;
    modal.bodyEl = body;
    modal.footEl = foot;
    return modal;
  }

  function kv(pairs) {
    var dl = el('dl', 'kv');
    pairs.forEach(function (p) {
      dl.append(el('dt', '', p[0]));
      var dd = el('dd', '', '');
      if (p[1] instanceof Node) dd.append(p[1]); else dd.textContent = p[2] === undefined ? String(p[1]) : String(p[2]);
      dl.append(dd);
    });
    return dl;
  }

  function openModal(title, bodyNode, actionNodes, alertText) {
    var m = ensureModal();
    m.titleEl.textContent = title;
    m.bodyEl.replaceChildren();
    if (alertText) m.bodyEl.append(el('p', 'modal-alert', alertText));
    m.bodyEl.append(bodyNode);
    m.footEl.replaceChildren();
    var cancel = el('button', 'button ghost small', tr('Close', 'إغلاق'));
    cancel.type = 'button';
    cancel.onclick = function () { m.close(); };
    m.footEl.append(cancel);
    (actionNodes || []).forEach(function (n) { m.footEl.append(n); });
    m.classList.add('open');if(!m.open)m.showModal();
    return m;
  }

  function labeled(labelText, node) {
    var wrap = el('div');
    var l = document.createElement('label');
    l.textContent = labelText;
    wrap.append(l, node);
    return wrap;
  }

  /* ============ 5. grids for admin sections ============ */
  var NOT_AVAILABLE = tr('Not available yet', 'غير متاح بعد');

  async function gridUsers() {
    var list = await api('/api/admin/users');
    var body = document.getElementById('adminUsersBody');
    body.replaceChildren();
    list.forEach(function (u) {
      var row = document.createElement('tr');
      row.append(el('td', '', u.username), el('td', '', u.email));
      var roleTd = el('td');
      var select = document.createElement('select');
      select.className = 'admin-role-select';
      ADMIN_ROLES.forEach(function (r) {
        var o = document.createElement('option');
        o.value = r; o.textContent = r;
        if (r === u.role) o.selected = true;
        select.append(o);
      });
      select.disabled=currentUser.role!=='owner'||u.id===currentUser.id||u.role==='owner';select.onchange = function () { adminPatchUser(u.id, { role: select.value }); };
      roleTd.append(select);
      row.append(roleTd);
      row.append(el('td', '', statusText(u.status)));
      row.append(el('td', '', u.trial_remaining_days + ' ' + tr('days', 'يوم')));
      row.append(el('td', '', fmtDate(u.trial_ends_at)));
      row.append(el('td', '', u.plan || tr('Not assigned', 'غير محدد')));
      row.append(el('td', '', u.last_login_at ? new Date(u.last_login_at).toLocaleString() : tr('Never', 'أبدًا')));
      row.append(el('td', '', fmtDate(u.created_at)));
      row.append(el('td', '', (u.projects_count || 0) + ' / ' + (u.workspaces_count || 0)));
      body.append(row);
    });

    enhanceGrid(body, {
      actions: function (row) {
        var u = list[Number(row.dataset.rowId)];
        return cellActions([
          ['icon-eye', tr('View details', 'عرض التفاصيل'), function () { openUserModal(u, false); }],
          ['icon-edit', tr('Edit user', 'تعديل المستخدم'), function () { openUserModal(u, true); }],
          ['icon-close', u.status==='active'?tr('Suspend','تعليق'):tr('Activate','تفعيل'), function(){return adminPatchUser(u.id,{status:u.status==='active'?'suspended':'active'});},u.id===currentUser.id||u.role==='owner'||(currentUser.role!=='owner'&&u.role==='admin')],
          ['icon-plus',tr('Extend trial','تمديد التجربة'),async function(){var value=await window.requestInput(tr('Trial days','أيام التجربة'),'10');if(value===null)return;var days=Number(value);if(!Number.isInteger(days)||days<0||days>3650){toast(tr('Invalid days','عدد أيام غير صالح'));return;}await adminPatchUser(u.id,{trial_days:days});}],
          ['icon-trash',tr('Remove account access (archive, preserve data)','حذف الوصول للحساب (أرشفة مع حفظ البيانات)'),async function(){if(!await window.confirmAction(tr('Remove this account from use? Sessions will be revoked. Projects, conversations and billing records are preserved.','حذف الحساب من الاستخدام؟ تُلغى جلساته وتُحفظ المشاريع والمحادثات والفواتير.')))return;try{await api('/api/admin/users/'+u.id,{method:'DELETE'});apiMessage('adminUserMessage',tr('Account archived; all data preserved.','أُرشف الحساب مع حفظ جميع البيانات.'));await gridUsers();}catch(error){apiMessage('adminUserMessage',error.message,true);}},u.id===currentUser.id||['admin','owner'].includes(u.role)||u.status==='archived'],
        ]);
      },
    });
  }

  async function openUserModal(u, editable) {
    var pairs = [
      [tr('Username', 'اسم المستخدم'), u.username],
      [tr('Email', 'البريد'), u.email],
      [tr('Role', 'الدور'), u.role],
      [tr('Status', 'الحالة'), statusText(u.status)],
      [tr('Plan', 'الخطة'), u.plan || tr('Not assigned', 'غير محدد')],
      [tr('Trial remaining', 'مدة التجربة المتبقية'), u.trial_remaining_days + ' ' + tr('days', 'يوم')],
      [tr('Trial end', 'نهاية التجربة'), fmtDate(u.trial_ends_at)],
      [tr('Last login', 'آخر دخول'), u.last_login_at ? new Date(u.last_login_at).toLocaleString() : tr('Never', 'أبدًا')],
      [tr('Projects / Workspaces', 'المشاريع / مساحات العمل'), (u.projects_count || 0) + ' / ' + (u.workspaces_count || 0)],
    ];
    if (!editable) {
      openModal(u.username, kv(pairs), [], tr('Editing is available from the edit icon.', 'التعديل متاح من أيقونة التعديل.'));
      return;
    }
    var roleSel = document.createElement('select');
    ADMIN_ROLES.forEach(function (r) {
      var o = document.createElement('option'); o.value = r; o.textContent = r;
      if (r === u.role) o.selected = true;
      roleSel.append(o);
    });
    roleSel.disabled=currentUser.role!=='owner'||u.id===currentUser.id||u.role==='owner';
    var statusSel = document.createElement('select');
    ['active', 'suspended'].forEach(function (r) {
      var o = document.createElement('option'); o.value = r; o.textContent = statusText(r);
      if (r === u.status) o.selected = true;
      statusSel.append(o);
    });
    var trialIn = document.createElement('input');
    trialIn.type = 'number'; trialIn.min = '0'; trialIn.max = '3650'; trialIn.value = '0';
    var body = el('div'),profileFields={};
    for(const [key,en,ar,type] of [['username','Username','اسم المستخدم','text'],['email','Email','البريد الإلكتروني','email'],['phone','Phone (international)','الهاتف الدولي','tel'],['postal_code','Postal / calling code','الرمز البريدي / رمز البلد','text']]){
      const input=document.createElement('input');input.type=type;input.value=u[key]||'';input.required=true;input.name=key;
      input.maxLength=key==='username'?50:key==='email'?254:key==='phone'?30:24;
      profileFields[key]=input;body.append(labeled(tr(en,ar),input));
    }
    for(const [key,en,ar,options] of [['preferred_language','Language','اللغة',['ar','en']],['preferred_theme','Theme','المظهر',['light','dark']]]){
      const input=document.createElement('select');input.name=key;for(const value of options){const option=document.createElement('option');option.value=option.textContent=value;input.append(option);}input.value=u[key]||options[0];profileFields[key]=input;body.append(labeled(tr(en,ar),input));
    }
    body.append(kv([[tr('Location','الموقع'),[u.country,u.region,u.city].filter(Boolean).join(' / ')||'—'],[tr('Created','تاريخ الإنشاء'),fmtDate(u.created_at)],[tr('Last login','آخر دخول'),fmtDate(u.last_login_at)],[tr('Projects / Workspaces','المشاريع / مساحات العمل'),(u.projects_count||0)+' / '+(u.workspaces_count||0)]]));
    const locationInputs={};
    for(const [key,en,ar] of [['country_id','Country','الدولة'],['region_id','Region','المحافظة'],['city_id','City','المدينة']]){const select=document.createElement('select');select.name=key;const option=document.createElement('option');option.value=u[key]||'';option.textContent=u[key.replace('_id','')]||tr('Not assigned','غير محدد');select.append(option);select.disabled=true;locationInputs[key]=select;body.append(labeled(tr(en,ar),select));}
    async function loadLocation(key,path,selected){const select=locationInputs[key];select.disabled=true;const entries=path?await api(path):[];select.replaceChildren();const empty=document.createElement('option');empty.value='';empty.textContent=tr('Not assigned','غير محدد');select.append(empty);for(const entry of entries){const option=document.createElement('option');option.value=entry.id;option.textContent=entry.name;select.append(option);}if(selected&&!entries.some(entry=>String(entry.id)===String(selected))){const current=document.createElement('option');current.value=selected;current.textContent=u[key.replace('_id','')]||String(selected);select.append(current);}select.value=selected||'';select.disabled=false;}
    locationInputs.country_id.onchange=async()=>{try{await loadLocation('region_id',locationInputs.country_id.value?'/api/locations/countries/'+locationInputs.country_id.value+'/regions':null,null);await loadLocation('city_id',null,null);}catch(error){toast(error.message);}};
    locationInputs.region_id.onchange=async()=>{try{await loadLocation('city_id',locationInputs.region_id.value?'/api/locations/regions/'+locationInputs.region_id.value+'/cities':null,null);}catch(error){toast(error.message);}};
    var planSel=document.createElement('select');const currentPlan=document.createElement('option');currentPlan.value=u.plan_id||'';currentPlan.textContent=u.plan||tr('Not assigned','غير محدد');planSel.append(currentPlan);planSel.disabled=true;body.append(labeled(tr('Plan','الخطة'),planSel));
    body.append(
      labeled(tr('Role', 'الدور'), roleSel),
      labeled(tr('Status', 'الحالة'), statusSel),
      labeled(tr('Extend trial by days', 'تمديد التجربة بالأيام'), trialIn)
    );
    var save = el('button', 'button small', tr('Save', 'حفظ'));
    save.type = 'button';
    save.onclick = async function () {
      save.disabled = true;
      var days=Number(trialIn.value);if(!Number.isInteger(days)||days<0||days>3650){save.disabled=false;toast(tr('Invalid days','عدد أيام غير صالح'));return;}
      if(!Array.from(Object.values(profileFields)).every(input=>input.reportValidity())){save.disabled=false;return;}
      var patch={};if(statusSel.value!==u.status)patch.status=statusSel.value;if(days>0)patch.trial_days=days;
      for(const [key,input] of Object.entries(profileFields)){if(input.value!==String(u[key]||''))patch[key]=input.value;}
      for(const [key,input] of Object.entries(locationInputs)){if(!input.disabled&&String(u[key]||'')!==input.value)patch[key]=input.value?Number(input.value):null;}
      if(!planSel.disabled&&String(u.plan_id||'')!==planSel.value)patch.plan_id=planSel.value?Number(planSel.value):null;
      if(currentUser.role==='owner' && roleSel.value!==u.role)patch.role=roleSel.value;
      try{if(await adminPatchUser(u.id,patch))modal.close();}catch(error){toast(error.message);}finally{save.disabled=false;}
    };
    openModal(tr('Edit user', 'تعديل المستخدم') + ' · ' + u.username, body, [save]);
    try{await loadLocation('country_id','/api/locations/countries',u.country_id);await loadLocation('region_id',u.country_id?'/api/locations/countries/'+u.country_id+'/regions':null,u.region_id);await loadLocation('city_id',u.region_id?'/api/locations/regions/'+u.region_id+'/cities':null,u.city_id);}catch(error){body.append(el('p','',tr('Location lookup unavailable; existing values are preserved.','تعذر تحميل المواقع؛ تُحفظ القيم الحالية.')));}
    try{const plans=await api('/api/admin/plans');planSel.replaceChildren();const empty=document.createElement('option');empty.value='';empty.textContent=tr('Not assigned','غير محدد');planSel.append(empty);for(const plan of plans){const option=document.createElement('option');option.value=plan.id;option.textContent=plan.name;planSel.append(option);}planSel.value=u.plan_id||'';planSel.disabled=false;}catch(error){body.append(el('p','',tr('Plan lookup unavailable; existing plan will be preserved.','تعذر تحميل الخطط؛ ستُحفظ الخطة الحالية.')));}

  }

  async function gridPlans() {
    var plans = await api('/api/admin/plans', { cache: 'no-store' });
    var body = document.getElementById('adminPlansBody');
    body.replaceChildren();
    plans.forEach(function (plan) {
      var row = document.createElement('tr');
      row.append(el('td', '', plan.code), el('td', '', plan.name), el('td', '', money(plan.price_cents)),
        el('td', '', plan.duration_days), el('td', '', plan.active ? tr('Yes', 'نعم') : tr('No', 'لا')));
      body.append(row);
    });
    enhanceGrid(body, {
      actions: function (row) {
        var plan = plans[Number(row.dataset.rowId)];
        return cellActions([
          ['icon-eye', tr('View plan', 'عرض الخطة'), function () {
            openModal(plan.name, kv([
              [tr('Code', 'الرمز'), plan.code], [tr('Name', 'الاسم'), plan.name],
              [tr('Price (USD cents)', 'السعر (سنت)'), String(plan.price_cents)],
              [tr('Days', 'الأيام'), String(plan.duration_days)],
              [tr('Active', 'نشط'), plan.active ? tr('Yes', 'نعم') : tr('No', 'لا')],
              [tr('Sort order', 'ترتيب العرض'), String(plan.sort_order)],
            ]), []);
          }],
          ['icon-edit', tr('Edit plan', 'تعديل الخطة'), function () { openPlanModal(plan); }],
          ['icon-close', u.status==='active'?tr('Suspend','تعليق'):tr('Activate','تفعيل'), function(){return adminPatchUser(u.id,{status:u.status==='active'?'suspended':'active'});},u.id===currentUser.id||u.role==='owner'||(currentUser.role!=='owner'&&u.role==='admin')],
          ['icon-plus',tr('Extend trial','تمديد التجربة'),async function(){var value=await window.requestInput(tr('Trial days','أيام التجربة'),'10');if(value===null)return;var days=Number(value);if(!Number.isInteger(days)||days<0||days>3650){toast(tr('Invalid days','عدد أيام غير صالح'));return;}await adminPatchUser(u.id,{trial_days:days});}],
          ['icon-trash',tr('Remove account access (archive, preserve data)','حذف الوصول للحساب (أرشفة مع حفظ البيانات)'),async function(){if(!await window.confirmAction(tr('Remove this account from use? Sessions will be revoked. Projects, conversations and billing records are preserved.','حذف الحساب من الاستخدام؟ تُلغى جلساته وتُحفظ المشاريع والمحادثات والفواتير.')))return;try{await api('/api/admin/users/'+u.id,{method:'DELETE'});apiMessage('adminUserMessage',tr('Account archived; all data preserved.','أُرشف الحساب مع حفظ جميع البيانات.'));await gridUsers();}catch(error){apiMessage('adminUserMessage',error.message,true);}},u.id===currentUser.id||['admin','owner'].includes(u.role)||u.status==='archived'],
        ]);
      },
    });
    var host = body.closest('.datagrid');
    var note = document.getElementById('adminPlansPublishNote');
    if (!note) { note = el('div', 'grid-note'); note.id = 'adminPlansPublishNote'; host.append(note); }
    var activeCount = plans.filter(function (p) { return p.active; }).length;
    note.textContent = tr('Published from this table to the landing page and client billing. Active offers: ', 'نُشر من هذا الجدول إلى صفحة الهبوط وفوترة العميل. العروض النشطة: ') +
      activeCount + ' / ' + plans.length;
  }

  function openPlanModal(plan) {
    var nameIn = document.createElement('input'); nameIn.value = plan.name;
    var priceIn = document.createElement('input'); priceIn.type = 'number'; priceIn.min = '0'; priceIn.value = String(plan.price_cents);
    var daysIn = document.createElement('input'); daysIn.type = 'number'; daysIn.min = '1'; daysIn.max = '3650'; daysIn.value = String(plan.duration_days);
    var activeSel = document.createElement('select');
    [[true, tr('Active', 'نشط')], [false, tr('Inactive', 'غير نشط')]].forEach(function (p) {
      var o = document.createElement('option'); o.value = String(p[0]); o.textContent = p[1];
      if (p[0] === plan.active) o.selected = true;
      activeSel.append(o);
    });
    var body = el('div');
    body.append(labeled(tr('Name', 'الاسم'), nameIn), labeled(tr('Price (USD cents)', 'السعر (سنت)'), priceIn),
      labeled(tr('Duration days', 'المدة بالأيام'), daysIn), labeled(tr('Status', 'الحالة'), activeSel));
    var save = el('button', 'button small', tr('Save', 'حفظ'));
    save.type = 'button';
    save.onclick = async function () {
      save.disabled = true;
      try {
        await api('/api/admin/plans/' + plan.id, {
          method: 'PATCH',
          body: JSON.stringify({
            name: nameIn.value, price_cents: Number(priceIn.value),
            duration_days: Number(daysIn.value), active: activeSel.value === 'true',
          }),
        });
        toast(tr('Plan updated', 'تم تحديث الخطة'));
        modal.close();
        await gridPlans();
        await renderPricing();
      } catch (e) { toast(e.message); }
      save.disabled = false;
    };
    openModal(tr('Edit plan', 'تعديل الخطة') + ' · ' + plan.code, body, [save]);
  }

  async function gridBilling() {
    await loadAdminBilling();
    enhanceGrid(document.getElementById('adminSubscriptionsBody'), {
      readonly: tr('Subscription records are created by the billing service.', ' سجلات الاشتراكات ينشئها خدمة الفوترة.'),
    });
  }

  var prevOverview = ADMIN_LOADERS.overview;
  ADMIN_LOADERS.overview = async function () {
    await prevOverview();
    enhanceGrid(document.getElementById('adminIntegrationsBody'), { readonly: tr('Integration status comes from the server.', 'حالة التكامل من الخادم.') });
  };
  ADMIN_LOADERS.users = gridUsers;
  ADMIN_LOADERS.plans = gridPlans;
  ADMIN_LOADERS.billing = gridBilling;

  var prevAccount = ADMIN_LOADERS.account;
  ADMIN_LOADERS.account = async function () {
    await prevAccount();
    var panel = document.getElementById('adminAccountPanel');
    if (panel) panel.append(signOutRow());
  };

  /* client profile: sign-out row inside the account + security panels */
  function clientAccountHost() {
    return document.querySelector('[data-client-panel="account"] .settings-list:last-of-type') ||
      document.querySelector('[data-client-panel="account"] .settings-list');
  }
  var prevClientAccount = CLIENT_LOADERS.account;
  CLIENT_LOADERS.account = async function () {
    await prevClientAccount();
    var host = clientAccountHost();
    var accountPanel=document.querySelector('[data-client-panel=account]');if(accountPanel&&!accountPanel.querySelector('[data-signout]')){var signout=signOutRow();signout.classList.add('account-signout');accountPanel.append(signout);}
    var info = document.querySelector('[data-client-panel="account"] .settings-list');
    if (info && !info.querySelector('[data-edit-profile]')) {
      var edit = el('button', 'button ghost small');
      edit.type = 'button';
      edit.setAttribute('data-edit-profile', '');
      edit.textContent = tr('Edit profile', 'تعديل الملف');
      edit.onclick = async function () {
        var values=await window.editProfileForm();if(!values)return;var phone=values.phone,postal=values.postal_code;
        var body = {};
        if (phone.trim()) body.phone = phone.trim();
        if (postal.trim()) body.postal_code = postal.trim();
        try {
          await api('/api/profile', { method: 'PATCH', body: JSON.stringify(body) });
          renderProfile(await api('/api/profile'));
          toast(tr('Profile updated', 'تم تحديث الملف'));
        } catch (e) { toast(e.message); }
      };
      var editRow=el('div','signout-row');editRow.append(edit);info.append(editRow);
    }
  };
  var prevClientSecurity = CLIENT_LOADERS.security;
  CLIENT_LOADERS.security = async function () {
    await prevClientSecurity();
    var panel = document.getElementById('clientSecurityPanel');
    if (panel && !panel.querySelector('[data-signout]')) panel.append(signOutRow());
  };

  function managementHost(root,id){var host=document.getElementById(id);if(!host){host=textElement('div');host.id=id;root.append(host)}return host;}
  const billingLoader=CLIENT_LOADERS.billing;
  CLIENT_LOADERS.billing=async function(){await billingLoader();await window.renderManagement(managementHost(document.querySelector('[data-client-panel="billing"]'),'clientBillingMethods'),'billing');};
  function refreshPlanSurfaces() {
    if (document.hidden) return;
    if (document.getElementById('landing')?.classList.contains('active')) renderPricing();
    if (currentUser && !admin() && document.getElementById('clientPage')?.classList.contains('active') && clientView === 'billing') {
      loadClientBilling().catch(function () {});
    }
  }
  document.addEventListener('visibilitychange', refreshPlanSurfaces);
  window.addEventListener('focus', refreshPlanSurfaces);
  window.setInterval(refreshPlanSurfaces, 30000);
  CLIENT_LOADERS.github=function(){return window.renderManagement(document.getElementById('clientGithubPanel'),'connections');};
  const aiLoader=CLIENT_LOADERS.ai;
  CLIENT_LOADERS.ai=async function(){await aiLoader();await window.renderManagement(managementHost(document.getElementById('clientAiPanel'),'clientProviderSettings'),'providers');};
  CLIENT_LOADERS.security=function(){return window.renderManagement(document.getElementById('clientSecurityPanel'),'security');};
  const accountLoader=CLIENT_LOADERS.account;
  CLIENT_LOADERS.account=async function(){await accountLoader();const host=managementHost(document.querySelector('[data-client-panel="account"]'),'clientAccountActivity');await window.renderManagement(host,'logs');const lifecycle=managementHost(document.querySelector('[data-client-panel="account"]'),'clientAccountLifecycle');if(lifecycle.parentElement.tagName!=='DETAILS'){const details=textElement('details','','account-sensitive');details.append(textElement('summary',tr('Suspend or request deletion','تعليق الحساب أو طلب حذفه')));lifecycle.before(details);details.append(lifecycle);}await window.renderManagement(lifecycle,'lifecycle');const signout=document.querySelector('[data-client-panel=account] .account-signout');if(signout)document.querySelector('[data-client-panel=account]').append(signout);};
  const adminBillingLoader=ADMIN_LOADERS.billing;
  ADMIN_LOADERS.billing=async function(){await adminBillingLoader();await window.renderManagement(managementHost(document.querySelector('[data-admin-panel="billing"]'),'adminBillingMethods'),'billing',true);};
  const nativePolicyLoader=ADMIN_LOADERS.policy;
  ADMIN_LOADERS.policy=async function(){await nativePolicyLoader();if(!window.nativeSession||!await window.nativeSession.ready())return;await window.renderManagement(managementHost(document.querySelector('[data-admin-panel="policy"]'),'adminNativeCatalogMaintenance'),'nativeCatalog',true);};
  ADMIN_LOADERS.audit=function(){return window.renderManagement(document.querySelector('[data-admin-panel="audit"]'),'logs',true)};
  ADMIN_LOADERS.github=loadAdminGithubAdmin;
  ADMIN_LOADERS.settings=function(){return window.renderManagement(document.querySelector('[data-admin-panel="settings"]'),'locations',true)};
  ADMIN_LOADERS.security=function(){return window.renderManagement(document.querySelector('[data-admin-panel="security"]'),'security')};
  const adminAccountLoader=ADMIN_LOADERS.account;
  ADMIN_LOADERS.account=async function(){await adminAccountLoader();await window.renderManagement(managementHost(document.querySelector('[data-admin-panel="account"]'),'adminAccountActivity'),'logs');};
  window.openClientView=async function(name){clientView=name;await page('clientPage');};
  window.openAdminView=async function(name){if(['admin','owner'].includes(currentUser?.role))adminView=name;await page('adminPage');};

  /* ===== Homepage Content: Landing carousel + Admin "Homepage Content" ===== */
    Object.assign(copy.en,{adminHomepage:'Homepage Content',adminHomepageLead:'Manage the Landing carousel: offers, announcements, partner promotions and platform messages.'});
    Object.assign(copy.ar,{adminHomepage:'محتوى الصفحة الرئيسية',adminHomepageLead:'أدر شريط الصفحة الرئيسية: العروض والإعلانات وترويج الشركاء ورسائل المنصة.'});
  
    var HOME_TYPE_LABEL = { platform:['Platform Information','معلومات المنصة'], announcement:['Announcement','إعلان'], offer:['Offer','عرض'], update:['Update / News','تحديث / خبر'], partner:['Partner Promotion','ترويج شريك'], advertisement:['Advertisement','إعلان مدفوع'] };
    var HOME_BADGE_LABEL = { new:['New','جديد'], offer:['Offer','عرض'], important:['Important','مهم'], update:['Update','تحديث'] };
    var HOME_ICONS = ['icon-opencode','icon-github','icon-grid','icon-file','icon-folder','icon-clock','icon-diff','icon-home','icon-chat','icon-commit','icon-shield','icon-settings','icon-search','icon-link','icon-user','icon-terminal'];
    var home = { host:null, track:null, viewport:null, dots:null, prev:null, next:null, play:null, items:[], index:0, timer:null, autoEnabled:true, hovered:false, focused:false, built:false, editing:null };
    var homeReduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  
    function homeLabel(map, key) { var row = map[key]; return row ? (lang === 'ar' ? row[1] : row[0]) : ''; }
    function homeSvg(id) { return '<svg class="ui-icon" aria-hidden="true"><use href="#' + id + '"/></svg>'; }
    function homeControlSvg(kind) { return '<svg class="ui-icon" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">' + (kind === 'pause' ? '<path d="M9 5v14M15 5v14"/>' : '<path d="m9 5 9 7-9 7Z"/>') + '</svg>'; }
    function homeLocalized(target, value) {
      target.replaceChildren();
      String(value || '').split(/(OpenCode|GitHub|50 MB)/g).forEach(function (part) {
        if (!part) return;
        if (/^(OpenCode|GitHub|50 MB)$/.test(part)) { var b = document.createElement('bdi'); b.dir = 'ltr'; b.textContent = part; target.append(b); }
        else target.append(document.createTextNode(part));
      });
    }
    function homeVisible() { var v = home.host ? parseInt(getComputedStyle(home.host).getPropertyValue('--cards'), 10) : 3; return v > 0 ? v : 3; }
    function homeMax() { return Math.max(0, home.items.length - homeVisible()); }
    function homeRtl() { return (document.documentElement.dir || 'ltr') === 'rtl'; }
  
    function homeBuildShell() {
      var host = home.host; host.replaceChildren(); home.built = true;
      var viewport = el('div', 'home-viewport'); var track = el('div', 'home-track'); viewport.append(track);
      var nav = el('div', 'home-nav');
      var prev = el('button', 'home-arrow home-prev'); prev.type = 'button'; prev.innerHTML = homeSvg('icon-back');
      var dots = el('div', 'home-dots');
      var next = el('button', 'home-arrow home-next'); next.type = 'button'; next.innerHTML = homeSvg('icon-back');
      var play = el('button', 'home-arrow home-play'); play.type = 'button';
      nav.append(prev, dots, next, play); host.append(viewport, nav);
      home.viewport = viewport; home.track = track; home.dots = dots; home.prev = prev; home.next = next; home.play = play;
      prev.addEventListener('click', function (e) { homeGo(home.index - 1); if (e.detail > 0) prev.blur(); });
      next.addEventListener('click', function (e) { homeGo(home.index + 1); if (e.detail > 0) next.blur(); });
      play.addEventListener('click', function (e) { home.autoEnabled = !home.autoEnabled; homeUpdate(); homeSchedule(); if (e.detail > 0) play.blur(); });
      host.addEventListener('pointerenter', function (e) { if (e.pointerType === 'mouse') { home.hovered = true; homeSchedule(); } });
      host.addEventListener('pointerleave', function () { home.hovered = false; homeSchedule(); });
      host.addEventListener('focusin', function () { home.focused = true; homeSchedule(); });
      host.addEventListener('focusout', function () { home.focused = false; homeSchedule(); });
      host.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { e.preventDefault(); homeGo(home.index + (((e.key === 'ArrowRight') !== homeRtl()) ? 1 : -1)); }
        else if (e.key === 'Home') { e.preventDefault(); homeGo(0); }
        else if (e.key === 'End') { e.preventDefault(); homeGo(homeMax()); }
      });
      var start = null;
      viewport.addEventListener('pointerdown', function (e) { if (e.pointerType !== 'mouse') start = { x: e.clientX, y: e.clientY }; });
      viewport.addEventListener('pointerup', function (e) {
        if (!start) return; var dx = e.clientX - start.x, dy = e.clientY - start.y; start = null;
        if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy) * 1.3) homeGo(home.index + (((dx < 0) !== homeRtl()) ? 1 : -1));
      });
      document.addEventListener('visibilitychange', homeSchedule);
      if (homeReduced.addEventListener) homeReduced.addEventListener('change', function () { home.autoEnabled = !homeReduced.matches; homeUpdate(); homeSchedule(); });
      if (window.ResizeObserver) new ResizeObserver(function () { homeUpdate(); }).observe(viewport);
    }
  
    function homeRenderCards() {
      if (!home.track) return;
      var ar = lang === 'ar'; home.track.replaceChildren();
      home.items.forEach(function (item) {
        var card = el('article', 'home-card');
        card.setAttribute('data-type', item.item_type || '');
        card.setAttribute('data-media', item.media_kind || 'none');
        if (item.media_kind !== 'none') {
          var media = el('div', 'home-media');
          if (item.media_kind === 'image' && item.image_url) {
            var img = document.createElement('img'); img.src = item.image_url; img.alt = '';
            img.onerror = function () { media.innerHTML = homeSvg(item.icon || 'icon-grid'); };
            media.append(img);
          }
          else media.innerHTML = homeSvg(item.icon || 'icon-grid');
          card.append(media);
        }
        if (item.badge && HOME_BADGE_LABEL[item.badge]) { var badge = el('span', 'home-badge', homeLabel(HOME_BADGE_LABEL, item.badge)); badge.setAttribute('data-badge', item.badge); card.append(badge); }
        var title = el('h3', 'home-title'); homeLocalized(title, ar ? item.title_ar : item.title_en); card.append(title);
        var body = el('p', 'home-text'); homeLocalized(body, ar ? item.body_ar : item.body_en); card.append(body);
        var ctaLabel = ar ? item.cta_label_ar : item.cta_label_en;
        if (ctaLabel && item.cta_url) { var link = el('a', 'home-cta'); link.href = item.cta_url; homeLocalized(link, ctaLabel); card.append(link); }
        home.track.append(card);
      });
    }
  
    function homeRenderDots() {
      if (!home.dots) return;
      var total = homeMax() + 1;
      if (home.dots.children.length !== total) {
        home.dots.replaceChildren();
        for (var i = 0; i < total; i++) (function (n) {
          var dot = el('button', 'home-dot'); dot.type = 'button';
          dot.addEventListener('click', function (e) { homeGo(n); if (e.detail > 0) dot.blur(); });
          home.dots.append(dot);
        })(i);
      }
    }
  
    function homeUpdate() {
      if (!home.track || !home.items.length) return;
      if (home.index > homeMax()) home.index = 0;
      homeRenderDots();
      var cards = home.track.children;
      var gap = parseFloat(getComputedStyle(home.track).gap || '0') || 20;
      var cw = cards[0] ? cards[0].getBoundingClientRect().width : 0;
      var offset = home.index * (cw + gap);
      home.track.style.transform = homeRtl() ? ('translateX(' + offset + 'px)') : ('translateX(-' + offset + 'px)');
      var vis = homeVisible();
      for (var i = 0; i < cards.length; i++) { var shown = i >= home.index && i < home.index + vis; cards[i].setAttribute('aria-hidden', String(!shown)); cards[i].inert = !shown; }
      var dots = home.dots.children;
      for (var j = 0; j < dots.length; j++) dots[j].setAttribute('aria-current', String(j === home.index));
      if (home.play) { home.play.innerHTML = homeControlSvg(home.autoEnabled ? 'pause' : 'play'); home.play.setAttribute('aria-label', home.autoEnabled ? tr('Pause automatic rotation', 'إيقاف الدوران التلقائي') : tr('Resume automatic rotation', 'استئناف الدوران التلقائي')); }
    }
  
    function homeSchedule() {
      if (home.timer) { clearTimeout(home.timer); home.timer = null; }
      var playing = home.autoEnabled && !home.hovered && !home.focused && !document.hidden && !homeReduced.matches;
      if (home.host) home.host.setAttribute('data-playing', playing ? 'true' : 'false');
      if (playing) home.timer = setTimeout(function () { homeGo(home.index + 1); }, 6500);
    }
  
    function homeGo(next) { var max = homeMax(); home.index = next > max ? 0 : (next < 0 ? max : next); homeUpdate(); homeSchedule(); }
  
    function homeWithPlatformBenefits(items) {
      // Owner-approved product information, not demo projects or database rows.
      // Preserve every admin item, its dates/media/CTA and existing order.
      var existing=Array.isArray(items)?items:[],icons=['icon-terminal','icon-github','icon-link','icon-clock'];
      var required=icons.map(function(icon,index){
        var key='b'+(index+1);
        return {id:'gateway-benefit-'+(index+1),item_type:'platform',media_kind:'icon',icon:icon,
          title_en:copy.en[key+'t'],title_ar:copy.ar[key+'t'],body_en:copy.en[key+'d'],body_ar:copy.ar[key+'d']};
      });
      return required.filter(function(info){return !existing.some(function(item){return item.title_en===info.title_en&&item.title_ar===info.title_ar&&item.body_en===info.body_en&&item.body_ar===info.body_ar;});}).concat(existing);
    }

    async function renderHomeCarousel() {
      var host = document.getElementById('homeCarousel');
      if (!host) return;
      home.host = host;
      var items;
      try { items = await api('/api/homepage', { cache: 'no-store', allowAnonymous: true }); }
      catch (error) { items=home.remoteItems||[]; }
      home.remoteItems=Array.isArray(items)?items:[];
      home.items = homeWithPlatformBenefits(home.remoteItems);
      if (!home.items.length) { host.replaceChildren(); return; }
      if (!home.built || !home.track) homeBuildShell();
      homeRenderCards(); homeUpdate(); homeSchedule();
    }
    window.renderHomeCarousel = renderHomeCarousel;
  
    function homeField(id, labelText, tag, attrs) { var wrap = el('label'); wrap.append(el('span', '', labelText)); var input = document.createElement(tag); input.id = id; if (attrs) for (var k in attrs) input.setAttribute(k, attrs[k]); wrap.append(input); return wrap; }
    function homeOptions(select, pairs) { select.replaceChildren(); pairs.forEach(function (pair) { var o = document.createElement('option'); o.value = pair[0]; o.textContent = pair[1]; select.append(o); }); }
  
    function adminHomepageRow(item, position, rows) {
      var row = document.createElement('tr');
      row.append(el('td', '', item.title_en + ' / ' + item.title_ar));
      row.append(el('td', '', homeLabel(HOME_TYPE_LABEL, item.item_type)));
      row.append(el('td', '', item.badge ? homeLabel(HOME_BADGE_LABEL, item.badge) : '—'));
      var orderTd = el('td');
      var up = el('button', 'button ghost small', '↑'); up.type = 'button'; up.disabled = position === 0; up.title = tr('Move up','تحريك لأعلى');
      up.onclick = function () { homeMove(item, rows[position - 1]); };
      var down = el('button', 'button ghost small', '↓'); down.type = 'button'; down.disabled = position === rows.length - 1; down.title = tr('Move down','تحريك لأسفل');
      down.onclick = function () { homeMove(item, rows[position + 1]); };
      orderTd.append(up, down, document.createTextNode(' ' + item.sort_order)); row.append(orderTd);
      var pinTd = el('td'); var pinBtn = el('button', 'button ghost small', item.pinned ? '★' : '☆'); pinBtn.type = 'button';
      pinBtn.onclick = function () { homePatch(item.id, { pinned: !item.pinned }); }; pinTd.append(pinBtn); row.append(pinTd);
      var enTd = el('td'); var enBtn = el('button', 'button ghost small', item.enabled ? tr('Disable','تعطيل') : tr('Enable','تفعيل')); enBtn.type = 'button';
      enBtn.onclick = function () { homePatch(item.id, { enabled: !item.enabled }); }; enTd.append(enBtn); row.append(enTd);
      row.append(el('td', '', (item.starts_at ? String(item.starts_at).slice(0,10) : '—') + ' → ' + (item.ends_at ? String(item.ends_at).slice(0,10) : '—')));
      var mediaTd = el('td');
      mediaTd.append(el('span', '', item.media_kind === 'image' ? tr('image','صورة') : (item.icon || '—')));
      var upload = document.createElement('input'); upload.type = 'file'; upload.accept = 'image/png,image/jpeg,image/webp';
      upload.onchange = async function () { if (!upload.files[0]) return; var fd = new FormData(); fd.append('file', upload.files[0]); try { await api('/api/admin/homepage/' + item.id + '/image', { method: 'POST', body: fd }); await loadAdminHomepage(); await renderHomeCarousel(); } catch (e) { apiMessage('adminHomepageMessage', e.message, true); } };
      mediaTd.append(upload);
      if (item.has_image) { var rm = el('button', 'button ghost small', tr('Remove image','إزالة الصورة')); rm.type = 'button'; rm.onclick = async function () { try { await api('/api/admin/homepage/' + item.id + '/image', { method: 'DELETE' }); await loadAdminHomepage(); await renderHomeCarousel(); } catch (e) { apiMessage('adminHomepageMessage', e.message, true); } }; mediaTd.append(rm); }
      row.append(mediaTd);
      var actTd = el('td');
      var edit = el('button', 'button ghost small', tr('Edit','تعديل')); edit.type = 'button'; edit.onclick = function () { homeEditItem(item); };
      var del = el('button', 'button ghost small', tr('Delete','حذف')); del.type = 'button';
      del.onclick = async function () { if (!await window.confirmAction(tr('Delete this homepage item?','حذف هذا العنصر؟'))) return; try { await api('/api/admin/homepage/' + item.id, { method: 'DELETE' }); await loadAdminHomepage(); await renderHomeCarousel(); } catch (e) { apiMessage('adminHomepageMessage', e.message, true); } };
      actTd.append(edit, del); row.append(actTd);
      return row;
    }
  
    async function homePatch(id, payload) { try { await api('/api/admin/homepage/' + id, { method: 'PATCH', body: JSON.stringify(payload) }); await loadAdminHomepage(); await renderHomeCarousel(); } catch (e) { apiMessage('adminHomepageMessage', e.message, true); } }
    async function homeMove(item, neighbour) { if (!neighbour) return; try { await api('/api/admin/homepage/' + item.id, { method: 'PATCH', body: JSON.stringify({ sort_order: neighbour.sort_order }) }); await api('/api/admin/homepage/' + neighbour.id, { method: 'PATCH', body: JSON.stringify({ sort_order: item.sort_order }) }); await loadAdminHomepage(); await renderHomeCarousel(); } catch (e) { apiMessage('adminHomepageMessage', e.message, true); } }
  
    function homeEditItem(item) {
      var set = function (id, v) { var node = document.getElementById(id); if (node) node.value = v == null ? '' : v; };
      set('homeTitleEn', item.title_en); set('homeTitleAr', item.title_ar);
      set('homeBodyEn', item.body_en); set('homeBodyAr', item.body_ar);
      set('homeType', item.item_type); set('homeBadge', item.badge || ''); set('homeIcon', item.icon || HOME_ICONS[0]);
      set('homeCtaEn', item.cta_label_en); set('homeCtaAr', item.cta_label_ar); set('homeCtaUrl', item.cta_url);
      set('homeSort', item.sort_order);
      set('homeStart', item.starts_at ? String(item.starts_at).slice(0,10) : ''); set('homeEnd', item.ends_at ? String(item.ends_at).slice(0,10) : '');
      var pin = document.getElementById('homePinned'); if (pin) pin.checked = !!item.pinned;
      home.editing = item.id;
      var submit = document.getElementById('homeSubmit'); if (submit) submit.textContent = tr('Save changes','حفظ التغييرات');
      var cancel = document.getElementById('homeCancel'); if (cancel) cancel.hidden = false;
      var form = document.getElementById('adminHomepageForm'); if (form) form.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  
    function buildAdminHomepage(panel, rows) {
      panel.replaceChildren();
      var msg = el('div', 'api-message'); msg.id = 'adminHomepageMessage'; panel.append(msg);
      var wrap = el('div', 'table-wrap');
      var table = document.createElement('table'); var thead = document.createElement('thead'); var htr = document.createElement('tr');
      ['Title','Type','Badge','Order','Pinned','Enabled','Starts / Ends','Media','Actions'].forEach(function (t) { htr.append(el('th', '', t)); });
      thead.append(htr); table.append(thead);
      var body = document.createElement('tbody'); body.id = 'adminHomepageBody'; table.append(body);
      rows.forEach(function (item, index) { body.append(adminHomepageRow(item, index, rows)); });
      wrap.append(table); panel.append(wrap);
  
      var form = document.createElement('form'); form.className = 'manage-form'; form.id = 'adminHomepageForm';
      form.append(homeField('homeTitleEn', tr('Title (EN)','العنوان (إنجليزي)'), 'input', { required: 'required', maxlength: '200' }));
      form.append(homeField('homeTitleAr', tr('Title (AR)','العنوان (عربي)'), 'input', { required: 'required', maxlength: '200' }));
      form.append(homeField('homeBodyEn', tr('Description (EN)','الوصف (إنجليزي)'), 'input', { maxlength: '1000' }));
      form.append(homeField('homeBodyAr', tr('Description (AR)','الوصف (عربي)'), 'input', { maxlength: '1000' }));
      var typeField = homeField('homeType', tr('Content type','نوع المحتوى'), 'select'); homeOptions(typeField.querySelector('select'), Object.keys(HOME_TYPE_LABEL).map(function (k) { return [k, homeLabel(HOME_TYPE_LABEL, k)]; })); form.append(typeField);
      var badgeField = homeField('homeBadge', tr('Badge','الشارة'), 'select'); homeOptions(badgeField.querySelector('select'), [['', tr('None','بدون')]].concat(Object.keys(HOME_BADGE_LABEL).map(function (k) { return [k, homeLabel(HOME_BADGE_LABEL, k)]; }))); form.append(badgeField);
      var iconField = homeField('homeIcon', tr('Icon','الأيقونة'), 'select'); homeOptions(iconField.querySelector('select'), HOME_ICONS.map(function (i) { return [i, i.replace('icon-', '')]; })); form.append(iconField);
      form.append(homeField('homeCtaEn', tr('CTA label (EN)','نص الزر (إنجليزي)'), 'input', { maxlength: '80' }));
      form.append(homeField('homeCtaAr', tr('CTA label (AR)','نص الزر (عربي)'), 'input', { maxlength: '80' }));
      form.append(homeField('homeCtaUrl', tr('CTA URL','رابط الزر'), 'input', { maxlength: '500', placeholder: 'https://… or /path' }));
      form.append(homeField('homeSort', tr('Order','الترتيب'), 'input', { type: 'number', min: '0', max: '100000' }));
      form.append(homeField('homeStart', tr('Starts on','يبدأ في'), 'input', { type: 'date' }));
      form.append(homeField('homeEnd', tr('Ends on','ينتهي في'), 'input', { type: 'date' }));
      form.append(homeField('homeImage', tr('Image (optional, ≤3 MB)','صورة (اختياري، ≤3 ميجابايت)'), 'input', { type: 'file', accept: 'image/png,image/jpeg,image/webp' }));
      var pinRow = el('label', 'checkbox-row'); var pin = document.createElement('input'); pin.type = 'checkbox'; pin.id = 'homePinned'; pinRow.append(pin, el('span', '', tr('Pinned / featured','مثبّت / مميّز'))); form.append(pinRow);
      var actions = el('div', 'admin-actions');
      var submit = el('button', 'button', tr('Add item','إضافة عنصر')); submit.type = 'submit'; submit.id = 'homeSubmit';
      var cancel = el('button', 'button ghost', tr('Cancel edit','إلغاء التعديل')); cancel.type = 'button'; cancel.id = 'homeCancel'; cancel.hidden = true;
      actions.append(submit, cancel); form.append(actions);
      panel.append(form);
  
      home.editing = null;
      cancel.onclick = function () { home.editing = null; form.reset(); submit.textContent = tr('Add item', 'إضافة عنصر'); cancel.hidden = true; };
      form.onsubmit = async function (event) {
        event.preventDefault();
        var payload = {
          item_type: value('homeType'), badge: value('homeBadge') || null,
          title_en: value('homeTitleEn'), title_ar: value('homeTitleAr'),
          body_en: value('homeBodyEn'), body_ar: value('homeBodyAr'),
          cta_label_en: value('homeCtaEn') || null, cta_label_ar: value('homeCtaAr') || null,
          cta_url: value('homeCtaUrl') || null, icon: value('homeIcon') || null,
          pinned: pin.checked,
          starts_at: value('homeStart') || null, ends_at: value('homeEnd') || null
        };
        var sort = value('homeSort'); if (sort !== '') payload.sort_order = Number(sort);
        submit.disabled = true;
        try {
          var saved = home.editing ? await api('/api/admin/homepage/' + home.editing, { method: 'PATCH', body: JSON.stringify(payload) }) : await api('/api/admin/homepage', { method: 'POST', body: JSON.stringify(payload) });
          var fileInput = document.getElementById('homeImage');
          if (fileInput && fileInput.files && fileInput.files[0]) { var fd = new FormData(); fd.append('file', fileInput.files[0]); await api('/api/admin/homepage/' + saved.id + '/image', { method: 'POST', body: fd }); }
          apiMessage('adminHomepageMessage', home.editing ? tr('Item updated','تم تحديث العنصر') : tr('Item added','تمت إضافة العنصر'));
          await loadAdminHomepage(); await renderHomeCarousel();
        } catch (error) { apiMessage('adminHomepageMessage', error.message, true); }
        finally { submit.disabled = false; }
      };
    }
  
    async function loadAdminHomepage() {
      var panel = document.getElementById('adminHomepagePanel');
      if (!panel) return;
      try { var rows = await api('/api/admin/homepage', { cache: 'no-store' }); buildAdminHomepage(panel, rows); }
      catch (error) { panel.replaceChildren(textElement('p', error.message)); }
    }
    ADMIN_LOADERS.homepage = loadAdminHomepage;
  
    var prevHomePrefs = applyPrefs;
    applyPrefs = function () { prevHomePrefs(); if (home.items.length) { homeRenderCards(); homeUpdate(); } };
  
    function homeKick() { renderHomeCarousel().catch(function () {}); }
    if (document.readyState === 'complete') homeKick(); else window.addEventListener('load', homeKick, { once: true });
    window.setTimeout(homeKick, 900);
    window.setTimeout(homeKick, 2600);
    document.addEventListener('visibilitychange', function () { if (document.getElementById('landing')?.classList.contains('active')) homeKick(); });
    window.addEventListener('focus', homeKick);
})();
