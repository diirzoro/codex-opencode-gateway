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
  settings.innerHTML='<div class="portal-content connections-content"><div class="connections-heading"></div><div id="connectionsProviders"></div><div id="connectionsGithub"></div><div id="connectionsRuntime"></div></div>';
  q('app-main').append(settings);q('connectionsProviders').innerHTML='<section class="manage-card"><label>Workspace / مساحة العمل<select disabled><option>Restoring workspace… / جارٍ استعادة مساحة العمل…</option></select></label><label>Search providers / البحث عن المزوّدات<input type="search" role="combobox" placeholder="Search providers…"></label><p role="status">Loading OpenCode providers… / جارٍ تحميل مزوّدي OpenCode…</p></section>';settings.querySelector('.connections-heading').append(text('h1','Settings · Connections','الإعدادات · الاتصالات'),text('p','Choose a workspace provider and use its OpenCode authentication method.','اختر مزوّد مساحة العمل واستخدم طريقة المصادقة المتاحة في OpenCode.','lead'),btn('connectionsReturn','Return to workspace','العودة لمساحة العمل',()=>activeWorkspace?page('workspacePage'):page('workspaceHomePage')));
  protectedPages.add('workspaceHomePage');protectedPages.add('connectionsPage');
  Object.assign(copy.en,{workspaceHome:'Workspace / Home',connectionsSettings:'Settings / Connections'});
  Object.assign(copy.ar,{workspaceHome:'مساحة العمل / الرئيسية',connectionsSettings:'الإعدادات / الاتصالات'});
  Object.assign(copy.en,{ui51:'Local project · 50 MB',ui53:'GitHub-backed project',githubHintText:'Choose a repository and branch authorized by your GitHub App connection.'});
  Object.assign(copy.ar,{ui51:'مشروع محلي · 50 MB',ui53:'مشروع مرتبط بـGitHub',githubHintText:'اختر مستودعًا وفرعًا مصرحًا بهما عبر اتصال GitHub App الخاص بك.'});
  Object.assign(copy.en,{subscriptionNoRefund:'Subscription payments are non-refundable.',clientAccountLead:'Personal details and preferences.'});
  Object.assign(copy.ar,{subscriptionNoRefund:'الاشتراكات غير قابلة لاسترداد المبلغ.',clientAccountLead:'البيانات الشخصية والتفضيلات.'});
  function navButton(id,key,icon,action){const node=document.createElement('button');node.id=id;node.dataset.go=action;node.innerHTML='<svg class="nav-icon"><use href="'+icon+'"/></svg><span data-i18n="'+key+'">'+t(key)+'</span>';node.onclick=()=>page(action);return node;}
  q('clientNav').insertBefore(navButton('clientWorkspaceHome','workspaceHome','#icon-opencode','workspaceHomePage'),q('clientNav').querySelector('button'));
  q('clientNav').querySelector('[data-client-view=dashboard]')?.remove();
  q('clientNav').querySelector('[data-client-view=ai]')?.remove();q('clientNav').querySelector('[data-client-view=github]')?.remove();
  q('clientNav').append(navButton('clientConnections','connectionsSettings','#icon-settings','connectionsPage'));
  const oldClientView=window.openClientView;
  window.openClientView=name=>['ai','github'].includes(name)?openConnections(name==='ai'?'providers':'github'):oldClientView(name);
  q('clientNav').querySelectorAll('[data-client-view]').forEach(button=>button.onclick=()=>window.openClientView(button.dataset.clientView));
  q('adminNav').querySelectorAll('[data-admin-view]').forEach(button=>button.onclick=()=>window.openAdminView(button.dataset.adminView));
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
  async function loadConnections(){
    const root=q('connectionsProviders'),query=root.querySelector('input[role=combobox]')?.value;
    if(query)root.dataset.providerQuery=query;
    const providersJob=window.renderManagement(root,'providers').catch(error=>{
      const status=root.querySelector('[role=status]');if(status)status.textContent=error.message;
      root.append(btn('retrySettings','Retry','إعادة المحاولة',()=>loadConnections()));
    });
    const githubJob=loadConnectionsGithub();
    const runtime=q('connectionsRuntime');runtime.replaceChildren(title('Selected workspace runtime','وقت تشغيل مساحة العمل المختارة'),text('p','Loading workspace state…','جارٍ تحميل حالة مساحة العمل…'));
    const runtimeJob=(async()=>{
      await (window.workspaceContextReady||Promise.resolve());
      if(!activeWorkspace){runtime.lastElementChild.textContent=tr('Select a workspace to inspect its runtime.','اختر مساحة عمل لفحص وقت تشغيلها.');return;}
      const workspaceId=activeWorkspace.id,state=await window.workspaceRuntime.loadAgents(workspaceId);
      if(activeWorkspace?.id===workspaceId)runtime.lastElementChild.textContent='OpenCode '+(state.health?.version||'')+' · '+(state.health?.healthy?tr('Ready','جاهز'):tr('Unavailable','غير متاح'));
    })();
    const results=await Promise.allSettled([providersJob,githubJob,runtimeJob]);
    for(const result of results)if(result.status==='rejected')toast(result.reason.message);
  }
  async function loadConnectionsGithub(){
    const github=q('connectionsGithub');github.replaceChildren(title('GitHub account / authorization','حساب GitHub / التفويض'));
    const status=await api('/api/github/status');github.append(textElement('p',status.connected?(status.account_login||'GitHub'):tr('Not connected','غير متصل')));
    const authorize=btn('settingsAuthorizeGithub','Authorize GitHub','تفويض GitHub',()=>window.location.assign('/api/github/install'));authorize.disabled=!status.configured;github.append(authorize);
    if(status.connected)github.append(btn('settingsDisconnectGithub','Disconnect','إلغاء الربط',async()=>{await api('/api/github/disconnect',{method:'POST'});await loadConnections();}));
    github.append(text('p','GitHub App authorization controls repository access. Your repository remains in GitHub; the server working copy is preserved until you resolve or export your work. Select a repository when creating a GitHub-backed project.','يحدد تفويض GitHub App صلاحيات المستودعات. يبقى المستودع في GitHub وتُحفظ نسخة العمل بالخادم حتى تحفظ عملك أو تصدّره. اختر المستودع عند إنشاء مشروع مرتبط بـGitHub.'));
  }

  let workAccess=false,entitlement=null,workspaceInitialized=false;
  let updateSend=()=>{},refreshChoices=async()=>{},syncWorkspacePolling=()=>{},loadWorkspaceDetails=()=>{};
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
    homeAccess.append(textElement('span',advanced.state==='not_started'?tr(' · Advanced trial: 30 days from first use',' · المتقدمة: 30 يومًا من أول استخدام'):tr(' · Advanced trial: ',' · التجربة المتقدمة: ')+advanced.remaining_days+tr(' days remaining',' يوم متبقٍ')));
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
  openWorkspace=async function(project,workspace,options={}){
    if(options.navigate===false&&!workspaceInitialized){
      if(activeWorkspace?.id!==workspace.id)clearAttachments();stopEvents();workspaceSelectionRevision++;activeProject=project;activeWorkspace=workspace;activeSession=null;
      try{localStorage.setItem('og-workspace',workspace.id);}catch(error){}return;
    }
    initializeWorkspace();return openWorkspace(project,workspace,options);
  };
  window.openGithubProject=()=>{initializeWorkspace();return window.openGithubProject();};
  function initializeWorkspace(){
    if(workspaceInitialized)return;workspaceInitialized=true;
  const shell=document.querySelector('#workspacePage .workspace-shell'),center=shell.querySelector('.agent-column'),pane=q('sessionSidebar');
  shell.classList.add('workspace-first');
  q('manageProviders')?.remove();

  const projectbar=center.querySelector('.project-bar');projectbar.querySelector('.statuses').hidden=true;
  projectbar.querySelector('.repo-title')?.setAttribute('hidden','');
  const context=textElement('div','','composer-context');projectbar.append(context);context.append(q('workspaceRepo'),q('workspaceBranch'));const gitState=textElement('span',tr('GitHub: checking…','GitHub: جارٍ التحقق…'));gitState.id='workspaceGithubState';context.append(gitState,q('runtimeStatus'),workspaceDays);
  const storageChip=text('span','Storage: …','التخزين: …');storageChip.id='workspaceStorage';context.append(storageChip);
  let storageTimer=null,storagePending=null;
  async function loadStorage(){
    if(!activeWorkspace){storageChip.textContent='';return;}
    const workspaceId=activeWorkspace.id;if(storagePending?.id===workspaceId)return storagePending.promise;
    const promise=(async()=>{try{const s=await api('/api/workspaces/'+workspaceId+'/storage');if(activeWorkspace?.id===workspaceId){storageChip.title=window.workspaceRetentionNotice(s.cache);storageChip.textContent=s.cache?.expired?storageChip.title:(s.scope==='github_working_copy'?tr('Working copy: ','نسخة العمل: '):tr('Local storage: ','التخزين المحلي: '))+s.used_mb+' / '+s.limit_mb+' MB · '+tr('remaining','المتبقي')+' '+(s.remaining_bytes/1048576).toFixed(1)+' MB';}}catch(error){if(activeWorkspace?.id===workspaceId)storageChip.textContent='';}})();
    storagePending={id:workspaceId,promise};try{return await promise;}finally{if(storagePending?.promise===promise)storagePending=null;}
  }
  syncWorkspacePolling=function(){
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
  const capabilityBody=textElement('div');capabilityView.append(capabilityBody);activity.append(activityStage,activitySummary,capabilityView);q('agentFeed').before(activity);
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
  const statuses={pending:['Waiting','بانتظار التنفيذ'],running:['Running','قيد التشغيل'],completed:['Completed','اكتمل'],error:['Failed','فشل']};
  const operations={inspected:['Inspected','تم فحصه'],changed:['Changed','تم تغييره'],created:['Created','تم إنشاؤه'],deleted:['Deleted','تم حذفه'],moved:['Moved','تم نقله']};
  const activityLabel=(map,value)=>tr(...(map[value]||['Reported','مُعلن']));
  window.renderWorkspaceEventLine=(kind,data={})=>{
    if(kind==='activity')activityStage.textContent=activityLabel(stages,data.stage)+' · '+data.tool+' · '+activityLabel(statuses,data.status);
    else if(stages[kind])activityStage.textContent=activityLabel(stages,kind);
  };
  window.renderMessageActivity=(host,rows)=>{
    if(!rows.length)return;
    const details=document.createElement('details');details.className='message-activity';details.append(textElement('summary',tr('Tool activity','نشاط الأدوات')));const list=document.createElement('ul');
    for(const row of rows){const item=textElement('li',row.tool+' · '+activityLabel(statuses,row.status)+(row.command?' · '+row.command:''));
      for(const file of row.files||[])item.append(textElement('div',file.path+' · '+(row.status==='completed'?activityLabel(operations,file.operation):tr('Requested','مطلوب'))));list.append(item);
    }details.append(list);host.append(details);
  };
  window.renderActivitySummary=rows=>{
    const files=new Set(),inspected=new Set(),tools=new Set();
    for(const row of rows)for(const entry of row.activity||[]){tools.add(entry.tool);if(entry.status==='completed')for(const file of entry.files||[])(file.operation==='inspected'?inspected:files).add(file.path);}
    const changed=files.size?tr('Reported file changes: ','تغييرات الملفات المُعلنة: ')+[...files].slice(0,20).join(', '):'';
    const read=inspected.size?tr('Files inspected: ','الملفات التي فُحصت: ')+[...inspected].slice(0,20).join(', '):'';
    const used=tools.size?tr('Tools used: ','الأدوات المستخدمة: ')+[...tools].join(', '):'';
    activitySummary.textContent=[changed,read,used].filter(Boolean).join(' · ');
  };
  const agent=q('agentSelect');agent.title=tr('Agent','الوكيل');controls.insertBefore(agent,q('providerSelect'));
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
  // Option 2 layout: Sessions and project files are sections of the right workspace panel.
  const sessionsSection=document.createElement('details');sessionsSection.className='workspace-side-section workspace-sessions';sessionsSection.open=true;
  sessionsSection.append(text('summary','Sessions','الجلسات'));
  const sessionsBody=textElement('div','','section-body');
  const newSessionButton=pane.querySelector('.new-session');
  const search=document.createElement('input');search.type='search';search.id='workspaceSessionSearch';search.placeholder=tr('Search sessions','ابحث في الجلسات');search.setAttribute('aria-label','Search sessions');
  search.oninput=()=>renderRuntimeSessions(sessionRows);
  const sessionTabs=textElement('div','','session-filters');let sessionFilter='active',sessionRows=[],sessionListPending=null,sessionCreating=null,sending=false,pendingSubmission=null,cancelRequested=false,statusPending=null;
  for(const [value,en,ar] of [['active','Active','نشطة'],['closed','Previous / Closed','سابقة / مغلقة'],['archived','Archived','مؤرشفة']]){const tab=btn('sessions-'+value,en,ar,()=>{sessionFilter=value;for(const b of sessionTabs.children)b.setAttribute('aria-pressed',String(b===tab));renderRuntimeSessions(sessionRows);});tab.setAttribute('aria-pressed',String(value===sessionFilter));sessionTabs.append(tab);}
  const closeSessionButton=btn('closeActiveSession','Close / Disconnect','إغلاق / فصل',()=>sessionAction(activeSession,'close'));
  const submissionStatus=textElement('p','','muted-small');submissionStatus.setAttribute('role','status');q('promptForm').before(submissionStatus);
  const retrySubmission=btn('retrySubmission','Check / retry same submission','تحقق / أعد نفس الطلب',()=>submitPending());retrySubmission.hidden=true;q('promptForm').before(retrySubmission);
  sessionsBody.append(newSessionButton,closeSessionButton,sessionTabs,search,q('sessionList'));sessionsSection.append(sessionsBody);
  const filesSection=document.createElement('details');filesSection.className='workspace-side-section workspace-files';filesSection.open=true;
  const filesSummary=text('summary','Project files','ملفات المشروع');
  const filesRefresh=btn('refreshWorkspaceFiles','Refresh files','حدّث الملفات',()=>loadFiles());filesRefresh.classList.add('icon-btn','files-refresh');
  filesRefresh.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();});
  filesSummary.append(filesRefresh);
  const filesTree=textElement('div','','files-tree');filesTree.id='workspaceFilesTree';
  const filesStatus=text('p','Open a workspace to see its files.','افتح مساحة عمل لعرض ملفاتها.','muted-small');
  const filesBody=textElement('div','','section-body');filesBody.append(filesTree,filesStatus);
  filesSection.append(filesSummary,filesBody);
  const FILE_ICONS={directory:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/></svg>',file:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 2h8l4 4v16H6z"/><path d="M14 2v4h4"/></svg>'};
  function renderFileRows(host,rows){
    host.replaceChildren();
    if(!rows.length){host.append(textElement('p',tr('Empty folder','مجلد فارغ'),'muted-small'));return;}
    for(const row of rows){
      const item=textElement('div','','file-item');
      const rowButton=textElement('button','','file-row'+(row.type==='directory'?' is-directory':''));
      rowButton.type='button';rowButton.title=row.path;rowButton.dataset.path=row.path;
      rowButton.innerHTML=FILE_ICONS[row.type==='directory'?'directory':'file']+'<span></span>';rowButton.querySelector('span').textContent=row.name;
      if(row.type==='directory'){
        const children=textElement('div','','file-children');children.hidden=true;rowButton.setAttribute('aria-expanded','false');
        rowButton.onclick=async()=>{const opening=children.hidden;children.hidden=!opening;rowButton.setAttribute('aria-expanded',String(opening));if(!opening)return;const workspaceId=activeWorkspace?.id;if(!workspaceId||children.dataset.loaded)return;children.dataset.loaded='1';try{const childRows=await api('/api/workspaces/'+workspaceId+'/files?path='+encodeURIComponent(row.path));if(activeWorkspace?.id!==workspaceId)return;renderFileRows(children,childRows);}catch(error){if(activeWorkspace?.id===workspaceId){children.replaceChildren();children.append(textElement('p',error.message,'muted-small'));}}};
        item.append(rowButton,children);
      }else{
        rowButton.onclick=()=>{filesTree.querySelectorAll('.file-row.selected').forEach(node=>node.classList.remove('selected'));rowButton.classList.add('selected');filesStatus.textContent=row.path;};
        item.append(rowButton);
      }
      host.append(item);
    }
  }
  async function loadFiles(){
    if(!activeWorkspace){filesTree.replaceChildren();filesStatus.textContent=tr('Open a workspace to see its files.','افتح مساحة عمل لعرض ملفاتها.');return;}
    const workspaceId=activeWorkspace.id;filesStatus.textContent=tr('Loading files…','جارٍ تحميل الملفات…');
    try{const rows=await api('/api/workspaces/'+workspaceId+'/files');if(activeWorkspace?.id!==workspaceId)return;renderFileRows(filesTree,rows);filesStatus.textContent=rows.length?'':tr('This workspace is empty.','مساحة العمل فارغة.');}
    catch(error){if(activeWorkspace?.id===workspaceId)filesStatus.textContent=error.message;}
  }
  const modes=textElement('nav','','workspace-panel-modes');modes.setAttribute('aria-label',tr('Workspace panel','لوحة مساحة العمل'));
  const changesMode=btn('workspaceChanges','Changes','التغييرات',()=>setPanel('changes'));
  const previewMode=btn('workspacePreview','Preview','المعاينة',()=>setPanel('preview'));
  const approvalsMode=btn('workspaceApprovals','Approvals','الموافقات',()=>setPanel('approvals'));
  modes.append(changesMode,previewMode,approvalsMode);
  const close=q('closeSessions');modes.append(close);
  const changesPanel=textElement('section','','workspace-changes'),previewPanel=textElement('section','','workspace-preview');
  changesPanel.id='workspaceChangesPanel';previewPanel.id='workspacePreviewPanel';
  const approvalsPanel=textElement('section','','workspace-approvals');approvalsPanel.id='workspaceApprovalsPanel';approvalsPanel.hidden=true;
  const approvalsList=textElement('div','','approvals-list');approvalsPanel.append(text('h3','Approvals','الموافقات'),text('p','Sensitive commands require your approval. Approve once or deny each request.','الأوامر الحساسة تتطلب موافقتك. وافق مرة واحدة أو ارفض كل طلب.'),approvalsList);
  function setApprovalsBadge(count){approvalsMode.textContent=tr('Approvals','الموافقات')+(count?' · '+count:'');}
  function renderApprovals(rows,sessionId){
    if(!activeSession||activeSession.id!==sessionId){approvalsList.replaceChildren(text('p','Open a session to see approval requests.','افتح جلسة لعرض طلبات الموافقة.'));setApprovalsBadge(0);return;}
    approvalsList.replaceChildren();setApprovalsBadge(rows.length);
    if(!rows.length){approvalsList.append(text('p','No pending approval requests.','لا توجد طلبات موافقة معلّقة.'));return;}
    for(const request of rows){const card=textElement('div','','approval-card');card.append(textElement('strong',request.permission||'permission'),textElement('pre',(request.patterns||[]).join('\n')));const allow=btn('approve-'+request.id,'Allow once','مرة واحدة',async()=>{await api('/api/sessions/'+sessionId+'/permissions/'+request.id,{method:'POST',body:JSON.stringify({reply:'once'})});await loadApprovals();});allow.disabled=!request.reviewable;const deny=btn('deny-'+request.id,'Deny','رفض',async()=>{await api('/api/sessions/'+sessionId+'/permissions/'+request.id,{method:'POST',body:JSON.stringify({reply:'reject'})});await loadApprovals();});card.append(allow,deny);approvalsList.append(card);}
  }
  window.renderWorkspaceApprovals=renderApprovals;
  async function loadApprovals(){if(!activeSession){renderApprovals([],null);return;}return refreshPermissions();}
  const paneResizer=document.createElement('div');paneResizer.className='pane-resizer';paneResizer.title=tr('Drag to resize','اسحب لتغيير الحجم');paneResizer.setAttribute('role','separator');paneResizer.setAttribute('aria-label',paneResizer.title);paneResizer.setAttribute('aria-orientation','vertical');paneResizer.tabIndex=0;
  let paneDragging=false;let panelWidth=320;
  function panelBounds(){const width=shell.getBoundingClientRect().width||innerWidth,min=drawer()?Math.min(250,Math.max(180,width-120)):250;return {min,max:Math.max(min,Math.min(width*.7,width-(drawer()?120:360)))};}
  function setPanelWidth(value){const {min,max}=panelBounds();panelWidth=Math.round(Math.min(Math.max(min,value),Math.max(min,max)));shell.style.setProperty('--panel-w',panelWidth+'px');paneResizer.setAttribute('aria-valuenow',String(panelWidth));paneResizer.setAttribute('aria-valuemin',String(Math.round(min)));paneResizer.setAttribute('aria-valuemax',String(Math.round(Math.max(min,max))));if(!drawer())shell.style.gridTemplateColumns='minmax(0,1fr) '+panelWidth+'px';}
  paneResizer.addEventListener('pointerdown',event=>{if(event.button!==0)return;paneDragging=true;paneResizer.setPointerCapture(event.pointerId);document.body.style.userSelect='none';event.preventDefault();});
  paneResizer.addEventListener('pointermove',event=>{if(!paneDragging)return;const rect=shell.getBoundingClientRect();setPanelWidth(document.documentElement.dir==='rtl'?event.clientX-rect.left:rect.right-event.clientX);});
  const paneDragEnd=()=>{paneDragging=false;document.body.style.userSelect='';};paneResizer.addEventListener('pointerup',paneDragEnd);paneResizer.addEventListener('pointercancel',paneDragEnd);paneResizer.addEventListener('lostpointercapture',paneDragEnd);
  paneResizer.addEventListener('dblclick',()=>setPanelWidth(320));
  paneResizer.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight'].includes(event.key))return;event.preventDefault();const direction=document.documentElement.dir==='rtl'?1:-1;setPanelWidth(panelWidth+(event.key==='ArrowRight'?20:-20)*direction);});
  function clampPanelWidth(){setPanelWidth(panelWidth);if(drawer()&&!pane.classList.contains('open'))shell.style.gridTemplateColumns='';}
  window.addEventListener('resize',clampPanelWidth);setPanelWidth(panelWidth);

  const gitSummary=q('gitSummary'),gitActions=pane.querySelector('.git-actions'),changedFiles=textElement('div','','changed-file-list'),diffView=textElement('pre','','workspace-diff');
  diffView.id='workspaceFileDiff';changesPanel.append(gitSummary,btn('refreshWorkspaceChanges','Refresh changes','حدّث التغييرات',()=>loadChanges()),changedFiles,diffView,gitActions);
  const previewPath=document.createElement('input');previewPath.value='index.html';previewPath.setAttribute('aria-label',tr('Preview HTML entry','ملف HTML للمعاينة'));
  const previewStatus=text('p','Start a sandboxed HTML preview. Backend/browser automation preview is not configured.','ابدأ معاينة HTML معزولة. معاينة الخادم وأتمتة المتصفح غير مهيأة.');
  const frame=document.createElement('iframe');frame.title=tr('Project preview','معاينة المشروع');frame.setAttribute('sandbox','allow-scripts');frame.setAttribute('referrerpolicy','no-referrer');frame.hidden=true;
  async function startPreview(){if(!activeWorkspace)return;const id=activeWorkspace.id;previewStatus.textContent=tr('Loading preview…','جارٍ تحميل المعاينة…');try{const result=await api('/api/workspaces/'+id+'/preview?path='+encodeURIComponent(previewPath.value));if(activeWorkspace?.id!==id)return;frame.srcdoc=result.html;frame.hidden=false;previewStatus.textContent=tr('Static preview · ','معاينة ثابتة · ')+result.path+' · '+tr('Network, backend servers and browser automation are unavailable here.','الشبكة والخوادم وأتمتة المتصفح غير متاحة هنا.');}catch(error){frame.hidden=true;previewStatus.textContent=error.message;}}
  const previewActions=textElement('div','','preview-actions');
  previewActions.append(btn('startWorkspacePreview','Start preview','ابدأ المعاينة',startPreview),btn('refreshWorkspacePreview','Refresh preview','حدّث المعاينة',startPreview));
  previewPanel.append(text('h3','Static Preview','معاينة ثابتة'),previewPath,previewActions,previewStatus,frame);
  const sideBrand=pane.querySelector('.side-brand'),sideSpacer=pane.querySelector('.side-spacer'),sideLinks=[...pane.querySelectorAll('.side-link')];
  pane.replaceChildren(modes,sessionsSection,filesSection,changesPanel,previewPanel,approvalsPanel);
  if(sideBrand)pane.prepend(sideBrand);
  pane.append(...(sideSpacer?[sideSpacer]:[]),...sideLinks,paneResizer);
  let panelMode='changes',changesStamp=0;
  async function loadChanges(){
    if(!activeWorkspace)return;const id=activeWorkspace.id,stamp=++changesStamp;diffView.textContent=tr('Loading changes…','جارٍ تحميل التغييرات…');
    try{const [state,sessionDiff]=await Promise.all([api('/api/workspaces/'+id+'/git/status'),activeSession?api('/api/sessions/'+activeSession.id+'/diff'):Promise.resolve([])]);if(stamp!==changesStamp||activeWorkspace?.id!==id)return;
      gitSummary.textContent=state.changes.length+' '+tr('working tree changes','تغييرات نسخة العمل')+' · '+(state.branch||'—')+(state.ahead!==undefined?' · '+state.ahead+tr(' unpushed commits',' commits غير مرسلة'):'');gitState.textContent=state.repository?'GitHub · '+state.repository+' → '+state.remote_branch:tr('Local project · stored on Gateway','مشروع محلي · محفوظ في Gateway');syncGit.hidden=reviewPR.hidden=!state.repository;syncGit.disabled=!state.clean||!state.github_access;reviewPR.href=state.repository?'https://github.com/'+state.repository+'/compare/'+encodeURIComponent(state.remote_branch):'#';changedFiles.replaceChildren();
      q('commitButton').disabled=state.clean;q('pushButton').disabled=!state.push_available||!state.clean;q('pushButton').textContent=tr('Push to ','Push إلى ')+(state.remote_branch||'—');q('pushButton').title=state.repository?state.repository+' / '+state.remote_branch:tr('No GitHub remote','لا يوجد مستودع GitHub');
      const runtimeFiles=new Map((sessionDiff||[]).map(row=>[row.file,row]));const names=new Set([...state.changes.map(row=>row.path),...runtimeFiles.keys()]);
      for(const name of names){const b=btn('changed-'+changedFiles.children.length,name,name,async()=>{const patch=runtimeFiles.get(name)?.patch;if(patch){diffView.textContent=patch;return;}const result=await api('/api/workspaces/'+id+'/diff?path='+encodeURIComponent(name));if(stamp===changesStamp&&activeWorkspace?.id===id)diffView.textContent=result.diff||tr('No textual diff','لا يوجد فرق نصّي');});changedFiles.append(b);}
      diffView.textContent=names.size?tr('Select a changed file to review its diff.','اختر ملفًا متغيرًا لمراجعة الفرق.'):tr('No changes in this workspace.','لا توجد تغييرات في مساحة العمل.');
    }catch(error){if(stamp===changesStamp)diffView.textContent=error.message;}
  }
  async function setPanel(mode){panelMode=mode;sessionsSection.hidden=filesSection.hidden=mode!=='changes';changesPanel.hidden=mode!=='changes';previewPanel.hidden=mode!=='preview';approvalsPanel.hidden=mode!=='approvals';changesMode.setAttribute('aria-pressed',String(mode==='changes'));previewMode.setAttribute('aria-pressed',String(mode==='preview'));approvalsMode.setAttribute('aria-pressed',String(mode==='approvals'));if(mode==='changes')await loadChanges();if(mode==='approvals')await loadApprovals();}
  function drawer(){return matchMedia('(max-width:1100px)').matches;}
  function closePane(){paneDragEnd();pane.classList.remove('open');shell.classList.remove('panel-docked');shell.classList.add('sessions-collapsed');shell.style.gridTemplateColumns='';overlay(false);}
  function togglePane(){const opening=shell.classList.contains('sessions-collapsed')||(drawer()&&!pane.classList.contains('open'));shell.classList.toggle('sessions-collapsed',!opening);pane.classList.toggle('open',opening);shell.classList.toggle('panel-docked',drawer()&&opening);shell.style.gridTemplateColumns='';overlay(false);if(opening){setPanelWidth(panelWidth);if(panelMode==='changes')loadChanges();}}

  copy.en.spaceReadyBody='Start a session to work with OpenCode. Review changes or preview your project in the side panel.';
  copy.ar.spaceReadyBody='ابدأ جلسة للعمل مع OpenCode. راجع التغييرات أو عاين مشروعك في اللوحة الجانبية.';
  q('openSessions').onclick=togglePane;close.onclick=closePane;q('backdrop').addEventListener('click',()=>{pane.classList.remove('open');});
  const events=textElement('div');previewPanel.hidden=true;changesMode.setAttribute('aria-pressed','true');previewMode.setAttribute('aria-pressed','false');
  refreshGit=async()=>{await loadChanges();q('manageProviders')?.remove();};
  q('commitButton').onclick=async()=>{if(!activeWorkspace)return;const message=await window.requestInput(tr('Commit message','رسالة الالتزام'));if(!message?.trim())return;try{await api('/api/workspaces/'+activeWorkspace.id+'/git/commit',{method:'POST',body:JSON.stringify({message:message.trim()})});await loadChanges();}catch(error){toast(error.message);}};
  const syncGit=btn('syncWorkspaceGit','Pull / Sync (fast-forward only)','Pull / Sync (تقديم سريع فقط)',async()=>{if(!activeWorkspace)return;if(!await window.confirmAction(tr('Fetch the selected GitHub branch and fast-forward only? Uncommitted/divergent work is preserved.','جلب فرع GitHub المختار والتقديم السريع فقط؟ تُحفظ الأعمال غير المحفوظة أو المتباعدة.')))return;await api('/api/workspaces/'+activeWorkspace.id+'/git/sync',{method:'POST'});await loadChanges();await loadFiles();});syncGit.hidden=true;
  const exportSource=btn('exportWorkspaceSource','Download source','تنزيل ملفات المشروع',()=>{if(activeWorkspace)window.location.assign('/api/workspaces/'+activeWorkspace.id+'/export');});
  const reviewPR=textElement('a',tr('Review PR / Merge in GitHub','مراجعة PR / Merge في GitHub'),'button ghost small');reviewPR.target='_blank';reviewPR.rel='noopener noreferrer';reviewPR.hidden=true;
  gitActions.append(syncGit,exportSource,reviewPR,textElement('small',tr('Commit saves locally. Push updates GitHub. PR and merge are reviewed in GitHub; nothing is sent automatically.','Commit يحفظ محليًا. Push يحدّث GitHub. تُراجع PR وMerge في GitHub؛ لا إرسال تلقائي.')));
  let providers=[],chosenAgent='',chosenProvider='',chosenModel='',discovery=0,modelRequest=0,runtimeReady=false,agentsReady=false,modelsReady=false;
  const retryModels=btn('retryWorkspaceModels','Retry models','أعد تحميل النماذج',()=>models());retryModels.hidden=true;controls.append(retryModels);
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
    attach.disabled=!workAccess||sending||Boolean(pendingSubmission)||busy;attachmentList.querySelectorAll('button').forEach(button=>button.disabled=sending||Boolean(pendingSubmission));
    q('sendMessage').disabled=sending||Boolean(pendingSubmission)||busy||!workAccess||!runtimeReady||!modelsReady||!selected?.connected||selected.allowed===false||!q('modelSelect').value;
    const hasActive=activeSession?.lifecycle==='active'||sessionRows.some(s=>s.lifecycle==='active');
    newSessionButton.disabled=newTask.disabled=!workAccess||hasActive||sending||Boolean(sessionCreating)||Boolean(pendingSubmission);
    closeSessionButton.disabled=!activeSession||sending||Boolean(pendingSubmission);
    q('stopAgent').disabled=(!busy&&!sending&&!pendingSubmission)||Boolean(cancelRequested);
  }
  // Existing entitlement rendering also updates workspace buttons. Reapply the
  // session/submission guards without changing subscription or billing logic.
  const renderAccess=renderEntitlement;renderEntitlement=function(){renderAccess();updateSend();};
  function renderRuntimeSessions(rows){
    if(!rows)return;sessionRows=rows;const list=q('sessionList');list.replaceChildren();
    const shown=rows.filter(row=>(row.lifecycle||'closed')===sessionFilter&&row.title.toLowerCase().includes(search.value.toLowerCase()));
    if(!shown.length)list.append(textElement('p',tr('No sessions in this category.','لا توجد جلسات في هذا القسم.'),'muted-small'));
    const names={active:tr('Active','نشطة'),running:tr('Running','قيد التنفيذ'),closed:tr('Closed','مغلقة'),archived:tr('Archived','مؤرشفة'),completed:tr('Completed','مكتملة'),failed:tr('Failed','فشلت')};
    for(const row of shown){const card=textElement('div','','session'+(row.id===activeSession?.id?' current':'')),label=textElement('div');label.append(textElement('strong',row.title),textElement('small',names[row.status]||row.status));const actions=textElement('div','','session-actions');
      if(row.lifecycle==='active')actions.append(btn('close-session-'+row.id,'Close / Disconnect','إغلاق / فصل',()=>sessionAction(row,'close')));
      else if(row.lifecycle==='archived')actions.append(btn('restore-session-'+row.id,'Restore','استعادة',()=>sessionAction(row,'restore')));
      else actions.append(btn('open-session-'+row.id,'Open','فتح',()=>selectSession(row)),btn('archive-session-'+row.id,'Archive','أرشفة',()=>sessionAction(row,'archive')));
      if(row.lifecycle!=='active')actions.append(btn('delete-session-'+row.id,'Delete from history','حذف من السجل',()=>sessionAction(row,'delete')));
      card.append(label,actions);list.append(card);
    }
    updateSend();
  }
  refreshSessions=async function(){
    if(!activeWorkspace)return;
    const workspaceId=activeWorkspace.id,owner=currentUser?.id;
    if(sessionListPending?.workspaceId===workspaceId)return sessionListPending.promise;
    const promise=(async()=>{const rows=await api('/api/workspaces/'+workspaceId+'/sessions?include_archived=true');if(activeWorkspace?.id!==workspaceId||currentUser?.id!==owner)return;renderRuntimeSessions(rows);
      const current=rows.find(row=>row.id===activeSession?.id);if(current&&current.lifecycle==='active')activeSession={...activeSession,...current};
      if(!activeSession){const open=rows.find(row=>row.lifecycle==='active');if(open)await selectSession(open);}updateSend();return rows;})();
    sessionListPending={workspaceId,promise};try{return await promise;}finally{if(sessionListPending?.promise===promise)sessionListPending=null;}
  };
  async function sessionAction(row,action){
    if(!row||sending||pendingSubmission)return;
    if(action==='delete'&&!await window.confirmAction(tr('Delete from client history? OpenCode history and project files are preserved.','حذف من سجل العميل؟ يبقى سجل OpenCode وملفات المشروع محفوظة.')))return;
    const workspaceId=activeWorkspace?.id;
    const result=await api('/api/sessions/'+row.id+(action==='delete'?'':'/'+action),{method:action==='delete'?'DELETE':'POST'});
    if(activeWorkspace?.id!==workspaceId)return;
    if(row.id===activeSession?.id&&['close','archive','delete'].includes(action)){stopEvents();sessionSelectionRevision++;activeSession=null;renderWorkspaceEmpty();}
    sessionRows=action==='delete'?sessionRows.filter(session=>session.id!==row.id):sessionRows.map(session=>session.id===row.id?{...session,...result}:session);
    renderRuntimeSessions(sessionRows);
    await refreshSessions();updateSend();
  }
  window.addEventListener('workspace-session-lifecycle',event=>{
    const {sessionId,workspaceId,action,result}=event.detail;
    if(activeWorkspace?.id!==workspaceId)return;
    if(activeSession?.id===sessionId&&['close','archive','delete'].includes(action)){stopEvents();sessionSelectionRevision++;activeSession=null;renderWorkspaceEmpty();}
    sessionRows=action==='delete'?sessionRows.filter(row=>row.id!==sessionId):sessionRows.map(row=>row.id===sessionId?{...row,...result}:row);
    renderRuntimeSessions(sessionRows);
  });
  function renderAgents(snapshot){
    agent.title=snapshot.errors?.agents?.detail||tr('Agent','الوكيل');agent.hidden=false;agent.replaceChildren(new Option(tr('OpenCode default','افتراضي OpenCode')+(snapshot.default_agent?' · '+snapshot.default_agent:''),''));
    for(const a of snapshot.agents||[]){const option=new Option(a.name+(a.mode==='subagent'?tr(' · Subagent',' · وكيل فرعي'):''),a.name);option.disabled=Boolean(a.hidden)||!['primary','all'].includes(a.mode);agent.add(option);}
    agentsReady=snapshot.agents!==null;
    agent.value=(snapshot.agents||[]).some(a=>a.name===chosenAgent&&!a.hidden&&['primary','all'].includes(a.mode))?chosenAgent:'';
    chosenAgent=agent.value;agent.onchange=()=>{chosenAgent=agent.value;updateSend();};updateSend();
  }
  function renderProviders(snapshot,preferredProvider=''){
    providers=(snapshot.providers||[]).filter(p=>!p.locally_disconnected&&p.allowed!==false&&(p.connected||p.id==='opencode'));q('providerSelect').replaceChildren(new Option(tr('Provider','المزوّد'),''));
    for(const p of providers.filter(p=>p.connected||p.id==='opencode')){const option=new Option(p.name+' · '+(p.allowed===false?tr('Restricted','مقيّد'):p.connected?tr('Connected','متصل'):tr('Default provider','المزوّد الافتراضي')),p.id);option.disabled=p.allowed===false;q('providerSelect').add(option);}
    if(preferredProvider)chosenProvider=preferredProvider;
    if(!providers.some(p=>p.id===chosenProvider)){chosenProvider='';chosenModel='';}
    if(!chosenProvider){const configured=snapshot.config?.model;const configuredProvider=providers.find(p=>typeof configured==='string'&&configured.startsWith(p.id+'/'));const connected=providers.filter(p=>p.connected&&p.allowed!==false);chosenProvider=configuredProvider?.id||(connected.length===1?connected[0].id:'');if(configuredProvider)chosenModel=configured.slice(configuredProvider.id.length+1);}
    if(providers.some(p=>p.id===chosenProvider))q('providerSelect').value=chosenProvider;
    q('providerSelect').onchange=()=>{chosenProvider=q('providerSelect').value;chosenModel='';models();};q('modelSelect').onchange=()=>{chosenModel=q('modelSelect').value;updateSend();};models();
  }
  refreshChoices=async function(preferredProvider='',force=false){
    if(!activeWorkspace||admin())return;
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
      q('modelSelect').replaceChildren(new Option(tr('Model','النموذج'),''));
      for(const model of rows){const option=new Option(model.name||model.id,model.id);option.disabled=model.allowed===false;q('modelSelect').add(option);}
      const preferred=chosenModel||selected?.default_model||'';
      q('modelSelect').value=rows.some(m=>m.id===preferred&&m.allowed!==false)?preferred:'';
    };
    render(selected&&workspaceId?window.workspaceRuntime.peekModels(workspaceId,selected.id)?.models||[]:[]);updateSend();
    if(!runtimeReady||!selected?.connected||selected.allowed===false)return;
    if(q('modelSelect').options.length===1)q('modelSelect').options[0].textContent=tr('Loading models…','جارٍ تحميل النماذج…');
    try{
      const data=await window.workspaceRuntime.loadModels(workspaceId,selected.id);
      if(!current())return;render(data.models);modelsReady=data.allowed!==false&&data.connected===true;
      chosenModel=q('modelSelect').value;q('modelSelect').title=tr('Model','النموذج');updateSend();
    }catch(error){if(current()){q('modelSelect').title=error.message;q('modelSelect').options[0].textContent=tr('Could not load models','تعذر تحميل النماذج');retryModels.hidden=false;updateSend();toast(error.message);}}
  }
  window.refreshWorkspaceChoices=async(preferredProvider='',force=true)=>{if(activeWorkspace&&force)window.workspaceRuntime.invalidate(activeWorkspace.id);return refreshChoices(preferredProvider,force);};
  openWorkspace=async function(project,workspace,{navigate=true}={}){
    if(admin()){await page('adminPage');return;}
    if(sending||pendingSubmission)throw new Error(tr('Confirm or cancel the pending submission before switching workspaces.','تحقق من الطلب المعلّق أو ألغِه قبل تغيير مساحة العمل.'));
    if(activeWorkspace?.id!==workspace.id)clearAttachments();stopEvents();workspaceSelectionRevision++;activeProject=project;activeWorkspace=workspace;activeSession=null;sessionRows=[];retrySubmission.hidden=true;submissionStatus.textContent='';capabilityView.open=false;capabilityWorkspace='';capabilityBody.replaceChildren();activityStage.textContent=activitySummary.textContent='';try{localStorage.setItem('og-workspace',workspace.id);}catch(error){}
    discovery++;modelRequest++;chosenAgent=chosenProvider=chosenModel='';providers=[];runtimeReady=agentsReady=modelsReady=false;retryModels.hidden=true;q('providerSelect').replaceChildren(new Option(tr('Loading providers…','جارٍ تحميل المزوّدات…'),''));q('modelSelect').replaceChildren(new Option(tr('Model','النموذج'),''));events.replaceChildren();changesStamp++;changedFiles.replaceChildren();diffView.textContent='';frame.srcdoc='';frame.hidden=true;filesTree.replaceChildren();filesStatus.textContent=tr('Loading files…','جارٍ تحميل الملفات…');
    q('stopAgent').disabled=true;q('workspaceRepo').textContent=project.name;q('workspaceBranch').textContent=project.branch||'—';
    renderWorkspaceEmpty();q('promptInput').value=pendingIdea;pendingIdea='';agent.hidden=false;agent.replaceChildren(new Option(tr('OpenCode default','افتراضي OpenCode'),''));updateSend();
    if(!navigate){syncWorkspacePolling();return;}
    await page('workspacePage');
    window.authSession?.workspaceOpened();

  };
  async function refreshSessionStatus(){
    if(!activeSession)return;const sessionId=activeSession.id,workspaceId=activeWorkspace?.id,owner=currentUser?.id;
    if(statusPending?.sessionId===sessionId)return statusPending.promise;
    const promise=(async()=>{const row=await api('/api/sessions/'+sessionId);if(activeSession?.id!==sessionId||activeWorkspace?.id!==workspaceId||currentUser?.id!==owner)return;
      activeSession={...activeSession,...row};q('runtimeStatus').textContent=row.status;
      if(!pendingSubmission&&!['submitted','waiting_approval'].includes(row.execution_status)){
        try{sessionStorage.removeItem('og-submit:'+owner+':'+sessionId);}catch(error){}
      }
      sessionRows=sessionRows.map(s=>s.id===row.id?{...s,...row}:s);renderRuntimeSessions(sessionRows);updateSend();return row;
    })();statusPending={sessionId,promise};try{return await promise;}finally{if(statusPending?.promise===promise)statusPending=null;}
  }
  let eventRefreshTimer=null;
  window.addEventListener('authentication-cleared',()=>{
    clearAttachments();clearTimeout(eventRefreshTimer);clearInterval(storageTimer);storageTimer=null;discovery++;modelRequest++;changesStamp++;
    pendingSubmission=null;sending=cancelRequested=false;sessionRows=[];providers=[];chosenAgent=chosenProvider=chosenModel='';
    runtimeReady=agentsReady=modelsReady=workAccess=false;entitlement=null;workspaceDays.hidden=workspaceAccess.hidden=true;workspaceDays.textContent='';workspaceAccess.replaceChildren();homeAccess.replaceChildren();retrySubmission.hidden=retryModels.hidden=true;
    submissionStatus.textContent=storageChip.textContent=activityStage.textContent=activitySummary.textContent='';
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
    activityStage.textContent=activitySummary.textContent='';await originalSession(session);if(activeSession?.id!==session.id)return;
    sessionRows=sessionRows.map(row=>row.id===session.id?{...row,...activeSession}:row);
    let saved=null;try{saved=JSON.parse(sessionStorage.getItem('og-submit:'+currentUser.id+':'+session.id)||'null');}catch(error){}
    if(saved?.request_id){pendingSubmission={...saved,owner:currentUser.id,workspaceId:activeWorkspace.id,sessionId:session.id,recovered:true};retrySubmission.hidden=false;submissionStatus.textContent=tr('Checking the previous submission; it will not be resent automatically.','جارٍ التحقق من الطلب السابق؛ لن يُعاد إرساله تلقائيًا.');await submitPending();}
    renderRuntimeSessions(sessionRows);updateSend();if(panelMode==='changes'&&!shell.classList.contains('sessions-collapsed'))loadChanges();loadApprovals().catch(()=>{});
  };
  async function createSession({checked=false}={}){
    if(sessionCreating)return sessionCreating;
    if(!activeWorkspace)return;
    if(activeSession?.lifecycle==='active'||sessionRows.some(s=>s.lifecycle==='active'))throw new Error(tr('Close the active session before starting a new one.','أغلق الجلسة النشطة قبل بدء جلسة جديدة.'));
    const workspaceId=activeWorkspace.id,owner=currentUser?.id;
    const promise=(async()=>{if(!checked)await refreshEntitlement();if(!workAccess||activeWorkspace?.id!==workspaceId||currentUser?.id!==owner)return;
      const row=await api('/api/workspaces/'+workspaceId+'/sessions',{method:'POST',body:JSON.stringify({title:tr('New session','جلسة جديدة')})});
      if(activeWorkspace?.id!==workspaceId||currentUser?.id!==owner)return;
      // Creation already opens the session server-side. Select once, without a
      // second creation or an auto-restore/open race during list refresh.
      await originalSession(row);sessionsSection.open=true;await refreshSessions();return activeSession;
    })();sessionCreating=promise;updateSend();try{return await promise;}finally{if(sessionCreating===promise)sessionCreating=null;updateSend();}
  }
  newSessionButton.onclick=()=>createSession().catch(error=>toast(error.message));
  const submissionCurrent=p=>currentUser?.id===p.owner&&activeWorkspace?.id===p.workspaceId&&activeSession?.id===p.sessionId;
  async function submitPending(){
    if(!pendingSubmission||sending)return;
    sending=true;updateSend();const pending=pendingSubmission;
    try{
      let result;
      try{result=await api('/api/sessions/'+pending.sessionId+'/submissions/'+pending.request_id);}catch(error){if(error.status!==404)throw error;if(pending.recovered)throw new Error(tr('Submission is not confirmed yet. Check again; no automatic resend occurred.','لم يتأكد الطلب بعد. تحقق مجددًا؛ لم تحدث إعادة إرسال تلقائية.'));}
      if(!result){if(!submissionCurrent(pending))return;result=await api('/api/sessions/'+pending.sessionId+'/messages',{method:'POST',body:JSON.stringify(pending.payload)});}
      if(!submissionCurrent(pending))return;
      sentAttachments(pending.payload);pendingSubmission=null;retrySubmission.hidden=true;submissionStatus.textContent=tr('Submission confirmed.','تم تأكيد الطلب.');
      if(pending.payload&&q('promptInput').value.trim()===pending.payload.text)q('promptInput').value='';
      await refreshSessionStatus();await refreshMessages();
    }catch(error){if(submissionCurrent(pending)){retrySubmission.hidden=false;submissionStatus.textContent=error.message;toast(error.message);}}
    finally{sending=false;updateSend();}
  }
  window.workspaceSubmissionBlocked=()=>sending||Boolean(pendingSubmission)||['submitted','waiting_approval'].includes(activeSession?.execution_status);
  q('promptForm').onsubmit=async event=>{
    event.preventDefault();if(window.workspaceSubmissionBlocked()||!activeWorkspace)return;if(attachments.some(a=>!a.path||a.error)){submissionStatus.textContent=tr('Wait for uploads or remove failed attachments before sending.','انتظر الرفع أو أزل المرفقات التي فشل رفعها قبل الإرسال.');return;}
    const prompt=q('promptInput').value.trim(),provider=q('providerSelect').value,model=q('modelSelect').value,selectedAgent=agent.value,workspaceId=activeWorkspace.id,owner=currentUser?.id;
    if(!prompt)return;if(!runtimeReady||!modelsReady||!provider||!model){toast(tr('Connect a provider and select a model before sending.','اربط مزوّدًا واختر نموذجًا قبل الإرسال.'));return;}
    // Synchronous lock precedes entitlement, creation, runtime and network waits.
    sending=true;cancelRequested=false;updateSend();submissionStatus.textContent=tr('Submitting…','جارٍ الإرسال…');
    try{
      await refreshEntitlement();if(!workAccess||cancelRequested||activeWorkspace?.id!==workspaceId||currentUser?.id!==owner)return;
      if(!activeSession)await createSession({checked:true});
      if(!activeSession||cancelRequested||activeWorkspace?.id!==workspaceId||currentUser?.id!==owner)return;
      const requestId=crypto.randomUUID(),sessionId=activeSession.id;
      const payload={request_id:requestId,text:prompt,provider_id:provider,model_id:model,attachments:attachments.map(a=>({path:a.path})),...(selectedAgent?{agent_id:selectedAgent}:{})};
      const pending={request_id:requestId,sessionId,workspaceId,owner,payload};pendingSubmission=pending;
      try{sessionStorage.setItem('og-submit:'+owner+':'+sessionId,JSON.stringify({request_id:requestId}));}catch(error){}
      const result=await api('/api/sessions/'+sessionId+'/messages',{method:'POST',body:JSON.stringify(payload)});
      if(!submissionCurrent(pending))return;
      sentAttachments(payload);pendingSubmission=null;retrySubmission.hidden=true;activeSession.execution_status=result.status;updateSend();
      if(q('promptInput').value.trim()===prompt)q('promptInput').value='';submissionStatus.textContent=tr('Submission confirmed.','تم تأكيد الطلب.');
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
    }finally{sending=false;cancelRequested=false;updateSend();}
  };
  q('stopAgent').onclick=async()=>{
    if(cancelRequested)return;cancelRequested=true;updateSend();
    try{
      if(pendingSubmission){await api('/api/sessions/'+pendingSubmission.sessionId+'/submissions/'+pendingSubmission.request_id);}
      if(activeSession){await api('/api/sessions/'+activeSession.id+'/stop',{method:'POST'});pendingSubmission=null;retrySubmission.hidden=true;await refreshSessionStatus();await refreshMessages();submissionStatus.textContent=tr('Execution cancelled. Completed actions and files are preserved.','أُلغي التنفيذ. تبقى الإجراءات المكتملة والملفات محفوظة.');}
    }catch(error){cancelRequested=false;toast(error.message);}finally{if(!sending)cancelRequested=false;updateSend();}
  };
  async function openRepositoryPicker(){
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
      const workingPaths=document.createElement('input');workingPaths.placeholder='src, tests';workingPaths.maxLength=2000;field('Working directories (optional, comma-separated)','مجلدات العمل (اختياري، مفصولة بفواصل)',workingPaths);
      form.append(textElement('p',tr('Leave empty for the complete shallow copy. Selected directories include root files; include dependencies and tests you need. Git history/blobs still count toward the working-copy limit. No files or remote branches are deleted.','اتركه فارغًا لنسخة كاملة بتاريخ مختصر. المجلدات المختارة تشمل ملفات الجذر؛ اختر التبعيات والفحوص اللازمة. بيانات Git تحتسب ضمن حد نسخة العمل. لا تُحذف ملفات أو فروع بعيدة.')));
      name.required=repository.required=branch.required=true;branch.disabled=true;repository.add(new Option(tr('Choose repository','اختر مستودعًا'),''));
      for(const r of repos)repository.add(new Option(r.full_name+(r.private?tr(' · Private',' · خاص'):''),r.full_name));
      const submit=textElement('button',tr('Create GitHub-backed project','إنشاء مشروع مرتبط بـGitHub'),'button');submit.type='submit';submit.disabled=true;form.append(submit);dialog.append(form);feedback.textContent='';let revision=0;
      repository.onchange=async()=>{
        const selected=repository.value,stamp=++revision;branch.replaceChildren();branch.disabled=submit.disabled=true;if(!selected)return;
        feedback.textContent=tr('Loading branches…','جارٍ تحميل الفروع…');
        try{const branches=await api('/api/github/branches?repository='+encodeURIComponent(selected));if(!dialog.open||stamp!==revision)return;for(const b of branches)branch.add(new Option(b.name,b.name));const preferred=repos.find(r=>r.full_name===selected)?.default_branch;if(branches.some(b=>b.name===preferred))branch.value=preferred;name.value=name.value||selected.split('/').pop();branch.disabled=false;submit.disabled=!branches.length;feedback.textContent='';}catch(error){if(stamp===revision)feedback.textContent=error.message;}
      };
      form.onsubmit=async event=>{event.preventDefault();if(!form.reportValidity()||submit.disabled)return;submit.disabled=true;feedback.textContent=tr('Preparing a shallow working copy…','جارٍ تجهيز نسخة عمل بتاريخ مختصر…');try{const result=await api('/api/projects',{method:'POST',body:JSON.stringify({source_type:'github',repository:repository.value,branch:branch.value,project_name:name.value,working_paths:workingPaths.value.split(',').map(path=>path.trim()).filter(Boolean)})});if(!dialog.open)return;dialog.close();await openWorkspace(result.project,result.workspace);}catch(error){if(dialog.open)feedback.textContent=error.message;}finally{submit.disabled=false;}};
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
    refreshSessions().catch(error=>toast(error.message));
    refreshGit().catch(error=>toast(error.message));
  };
  createWorkspaceSession=createSession;
  if(activeProject){q('workspaceRepo').textContent=activeProject.name;q('workspaceBranch').textContent=activeProject.branch||'—';}
  }
  const refundPolicy=text('p','Subscription payments are non-refundable.','الاشتراكات غير قابلة لاسترداد المبلغ.','refund-policy');refundPolicy.id='subscriptionRefundPolicy';document.querySelector('#landing .pricing').append(refundPolicy);
  const prefs=applyPrefs;applyPrefs=()=>{prefs();for(const [node,en,ar] of texts){if(!node.firstChild)node.textContent=tr(en,ar);else if(node.firstChild.nodeType===3)node.firstChild.textContent=tr(en,ar);}q('homeSessionSearch').placeholder=tr('Search recent sessions…','ابحث في الجلسات الأخيرة…');renderEntitlement();};
  // The wordmark is a landing-page navigation control for every role.
  const brand=document.querySelector('#app-header .header-brand');if(brand){brand.setAttribute('role','button');brand.tabIndex=0;brand.setAttribute('aria-label','OpenCode Gateway — Home');brand.style.cursor='pointer';brand.onclick=()=>page('landing');brand.onkeydown=event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();page('landing');}};}
  const paymentOrders=document.createElement('section');paymentOrders.id='clientPaymentOrders';document.querySelector('[data-client-panel=billing]').append(paymentOrders);
  const adminOrders=document.createElement('section');adminOrders.id='adminPaymentOrders';document.querySelector('[data-admin-panel=billing]').append(adminOrders);
  let paymentLoadCounter=0;
  async function loadPaymentOrders(platform=false){
    const host=platform?adminOrders:paymentOrders;const token=String(++paymentLoadCounter);host.dataset.paymentLoad=token;
    host.replaceChildren(title(platform?'Payment review':'Payment orders',platform?'مراجعة المدفوعات':'طلبات الدفع'));
    const list=await api(platform?'/api/billing/admin/orders':'/api/billing/orders');
    if(host.dataset.paymentLoad!==token)return;
    const ACTION_ICONS={view:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2.06 12.35a1 1 0 0 1 0-.7C3.42 8.1 7.22 5 12 5s8.58 3.1 9.94 6.65a1 1 0 0 1 0 .7C20.58 15.9 16.78 19 12 19s-8.58-3.1-9.94-6.65Z"/><circle cx="12" cy="12" r="3"/></svg>',resume:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>',cancel:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>',remove:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/></svg>',confirm:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',reject:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="m15 9-6 6M9 9l6 6"/></svg>'};
    const act=(id,icon,label,action)=>{const b=textElement('button','','icon-btn');b.id=id;b.type='button';b.title=label;b.setAttribute('aria-label',label);b.innerHTML=icon;b.onclick=async()=>{b.disabled=true;try{await action();}catch(error){toast(error.message)}finally{b.disabled=false;}};return b;};
    for(const order of list){
      const row=textElement('div','','manage-row');
      row.append(textElement('strong',order.plan_name+' · '+order.currency+' '+(order.amount_cents/100).toFixed(2)),textElement('span',(order.email||'')+' · '+order.status));
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
      if(!platform&&order.provider_environment&&!['paid','sandbox_paid'].includes(order.status))actions.append(act('capture-'+order.id,ACTION_ICONS.confirm,tr('Confirm PayPal payment','تأكيد دفع PayPal'),async()=>{const verified=await api('/api/billing/orders/'+order.id+'/paypal/capture',{method:'POST'});await refreshCustomerBilling();toast(verified.status==='sandbox_paid'?tr('Sandbox payment verified. Real subscription unchanged.','تم التحقق من الدفع التجريبي دون تفعيل اشتراك حقيقي.'):tr('Payment verified. Subscription active.','تم التحقق من الدفع وتفعيل الاشتراك.'));}));
      if(!platform&&order.status==='awaiting_payment')actions.append(act('resume-'+order.id,ACTION_ICONS.resume,tr('Payment instructions','تعليمات الدفع'),()=>beginCheckout(order.plan_id,order.method_id)));
      if(!platform&&['awaiting_payment','pending_review'].includes(order.status))actions.append(act('cancel-'+order.id,ACTION_ICONS.cancel,tr('Cancel payment','إلغاء الدفع'),async()=>{if(!await window.confirmAction(tr('Cancel this payment request?','إلغاء طلب الدفع هذا؟')))return;await api('/api/billing/orders/'+order.id+'/cancel',{method:'POST'});await loadPaymentOrders();}));
      if(!platform&&!window.reactivationAccount&&['failed','cancelled','rejected'].includes(order.status))actions.append(act('remove-'+order.id,ACTION_ICONS.remove,tr('Remove from history','حذف من السجل'),async()=>{if(!await window.confirmAction(tr('Remove this payment from your history?','حذف هذا الدفع من سجلك؟')))return;await api('/api/billing/orders/'+order.id,{method:'DELETE'});await loadPaymentOrders();}));
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
    const showError=error=>body.replaceChildren(textElement('p',error.message||String(error),'api-message show error'));
    const renderProviderForm=method=>{
      const dl=document.createElement('dl');dl.className='checkout-details';
      for(const [label,value] of [[tr('Plan','الخطة'),plan.name],[tr('Amount','المبلغ'),(plan.price_cents/100).toFixed(2)],[tr('Currency','العملة'),plan.currency]]){dl.append(textElement('dt',label),textElement('dd',String(value)));}
      body.replaceChildren(dl);const phead=textElement('strong',method.label);phead.prepend(payIcon(method.kind));body.prepend(phead);
      const pfield=(labelText,id,type,extra)=>{const wrap=text('label',labelText,labelText);wrap.htmlFor=id;const inp=document.createElement('input');inp.id=id;inp.type=type;inp.required=true;Object.assign(inp,extra||{});wrap.append(inp);body.append(wrap);return inp;};
      const payerName=pfield(tr('Your full name','اسمك الكامل'),'payerName','text',{maxLength:150,autocomplete:'off'});
      const payerEmail=pfield(tr('Your email','بريدك الإلكتروني'),'payerEmail','email',{maxLength:254,autocomplete:'off'});
      const payerCountry=pfield(tr('Your country','دولتك'),'payerCountry','text',{maxLength:80,autocomplete:'off'});
      const go2=textElement('button',method.kind==='googlepay'?tr('Pay with Google Pay','الدفع عبر Google Pay'):tr('Continue to PayPal','المتابعة إلى PayPal'),'button checkout-hosted-link');go2.type='button';
      if(!method.available){const embedNote=method.details.checkout_mode==='paypal'?tr('The official PayPal buttons are already embedded in this form. They appear here automatically once the PayPal merchant credentials are configured on the server; card number, expiry and CVV are then entered on the PayPal hosted page only.','أزرار PayPal الرسمية مدمجة في هذا النموذج، وستظهر هنا تلقائيًا فور تهيئة بيانات تاجر PayPal على الخادم. تُدخل بيانات البطاقة في صفحة PayPal المستضافة فقط.'):tr('The Google Pay payment sheet is opened by the configured payment processor. It appears once a real processor checkout link is configured on the server.','نافذة الدفع Google Pay يفتحها مزوّد الدفع المهيأ، وستظهر فور تهيئة رابط دفع حقيقي على الخادم.');body.append(text('p',(reasonCopy[method.available_reason]||tr('Not connected','غير متصل'))+' — '+tr('the provider connection is checked when you continue.','يتم التحقق من اتصال المزوّد عند المتابعة.'),(reasonCopy[method.available_reason]||tr('Not connected','غير متصل'))+' — '+tr('the provider connection is checked when you continue.','يتم التحقق من اتصال المزوّد عند المتابعة.'),'checkout-lead'),text('p',embedNote,embedNote,'checkout-lead'));}
      body.append(go2);
      go2.onclick=async()=>{go2.disabled=true;try{
        const result=await api('/api/billing/checkout',{method:'POST',body:JSON.stringify({plan_id:planId,method_id:method.id,billing_note:noteInput.value.trim(),payer_name:payerName.value.trim(),payer_email:payerEmail.value.trim(),payer_country:payerCountry.value.trim()})});
        if(result.automatic_processing){
          body.replaceChildren(dl,text('p','Pay through the official PayPal checkout. Access activates only after the completed payment is verified.','ادفع عبر صفحة PayPal الرسمية. يُفعّل الوصول بعد التحقق من اكتمال الدفع فقط.'));
          let ppStatus=null;try{ppStatus=await api('/api/billing/paypal/status')}catch(error){ppStatus=null}
          if(ppStatus&&ppStatus.configured&&ppStatus.client_id&&result.order.provider_order_id){
            const host=textElement('div');host.id='paypalButtonHost';body.append(host);
            const loadPp=()=>new Promise((resolve,reject)=>{if(window.paypal)return resolve(window.paypal);const s=document.createElement('script');s.src='https://www.paypal.com/sdk/js?client-id='+encodeURIComponent(ppStatus.client_id)+'&currency='+encodeURIComponent(result.order.currency)+'&intent=capture&components=buttons';s.onload=()=>resolve(window.paypal);s.onerror=()=>reject(new Error('paypal-sdk'));document.head.append(s);});
            loadPp().then(pp=>{pp.Buttons({style:{layout:'vertical'},createOrder:()=>result.order.provider_order_id,onApprove:async()=>{const verified=await api('/api/billing/orders/'+result.order.id+'/paypal/capture',{method:'POST'});dialog.close();await refreshCustomerBilling();toast(verified.status==='sandbox_paid'?tr('Sandbox payment verified. Real subscription unchanged.','تم التحقق من الدفع التجريبي دون تفعيل اشتراك حقيقي.'):tr('Payment verified. Subscription active.','تم التحقق من الدفع وتفعيل الاشتراك.'));},onCancel:()=>toast(tr('Payment cancelled. No subscription activated.','تم إلغاء الدفع دون تفعيل الاشتراك.')),onError:()=>toast(tr('PayPal could not complete this payment. No subscription activated.','تعذر إتمام الدفع عبر PayPal دون تفعيل الاشتراك.'))}).render('#paypalButtonHost');}).catch(()=>{if(result.approval_url)window.location.assign(result.approval_url);});
          }else if(result.approval_url)window.location.assign(result.approval_url);
          body.append(btn('confirmPayPalPayment','Confirm PayPal payment','تأكيد دفع PayPal',async()=>{const verified=await api('/api/billing/orders/'+result.order.id+'/paypal/capture',{method:'POST'});dialog.close();await refreshCustomerBilling();toast(verified.status==='sandbox_paid'?tr('Sandbox payment verified. Real subscription unchanged.','تم التحقق من الدفع التجريبي دون تفعيل اشتراك حقيقي.'):tr('Payment verified. Subscription active.','تم التحقق من الدفع وتفعيل الاشتراك.'));}));
        }else if(result.payment_url){
          const link=textElement('a',tr('Open the payment provider page','فتح صفحة مزود الدفع'),'button checkout-hosted-link');link.href=result.payment_url;link.target='_blank';link.rel='noopener noreferrer';const pvNote=tr('Complete payment on the provider page, then submit your reference for verification.','أكمل الدفع في صفحة المزود، ثم أرسل مرجعك للتحقق.');body.append(link,text('p',pvNote,pvNote,'checkout-lead'));
        }
      }catch(error){showError(error);}finally{go2.disabled=false;}};
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
    dialog.append(rows,select,noteWrap,go,body,textElement('small',tr('Payment for: ','الدفع لحساب: ')+(currentUser||window.reactivationAccount).email),text('p','Subscription payments are non-refundable.','الاشتراكات غير قابلة لاسترداد المبلغ.','refund-policy'));
    document.body.append(dialog);dialog.onclose=()=>dialog.remove();dialog.showModal();
  }
  window.beginCheckout=beginCheckout;
  authReady.then(async()=>{const params=new URLSearchParams(location.search);const ret=params.get('payment_return'),cancel=params.get('payment_cancel');if(!ret&&!cancel)return;history.replaceState(null,'',location.pathname+location.hash);if(window.reactivationAccount){await window.loadManagement();await window.openReactivation();}else if(!currentUser){page('authPage');return;}else await window.openClientView('billing');try{await loadPaymentOrders()}catch(error){toast(error.message)}if(cancel){toast(tr('Payment cancelled. No subscription was activated.','تم إلغاء الدفع دون تفعيل أي اشتراك.'));return}try{const orders=await api('/api/billing/orders');const order=orders.find(o=>o.id===ret);const status=order&&order.status;if(status==='paid')toast(tr('Payment verified. Subscription active.','تم التحقق من الدفع وتفعيل الاشتراك.'));else if(status==='sandbox_paid')toast(tr('Sandbox payment recorded. Real subscription unchanged.','سُجل الدفع التجريبي دون تفعيل اشتراك حقيقي.'));else if(status)toast(tr('Payment is pending verification. Press Confirm PayPal payment in Payment orders.','الدفع بانتظار التحقق. اضغط تأكيد دفع PayPal في طلبات الدفع.'));else toast(tr('Returned from PayPal. Confirm your payment in Payment orders.','عدت من PayPal. أكد الدفع من طلبات الدفع.'))}catch(error){toast(error.message)}}).catch(error=>toast(error.message));
  setInterval(async()=>{if(!currentUser||admin()||!document.querySelector('#workspacePage.active,#workspaceHomePage.active'))return;try{await refreshEntitlement();}catch(error){toast(error.message);}},30000);
  document.addEventListener('click',event=>{if(event.target.closest('#clientNav [data-client-view=billing]'))loadPaymentOrders().catch(e=>toast(e.message));if(event.target.closest('#adminNav [data-admin-view=billing]'))loadPaymentOrders(true).catch(e=>toast(e.message));});
  matchMedia('(max-width:1100px)').addEventListener('change',()=>{q('sessionSidebar').classList.remove('open');overlay(false);});
  applyPrefs();
  if(document.documentElement.dataset.restorePage==='workspacePage')initializeWorkspace();
  q('promptInput').disabled=true;q('homeNewProject').disabled=true;
  window.showBootstrapFrame?.();
})();
