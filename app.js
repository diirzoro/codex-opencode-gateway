const $=(q,root=document)=>root.querySelector(q), $$=(q,root=document)=>[...root.querySelectorAll(q)];
let lang=localStorage.getItem('og-lang')||'ar', dark=localStorage.getItem('og-theme')==='dark';
const copy={
 ar:{how:'كيف يعمل',workspace:'مساحة العمل',connect:'اربط GitHub',heroTitle:'من فرع GitHub إلى تغيير جاهز للمراجعة.',heroBody:'افتح مشروعك في مساحة OpenCode مؤقتة، اطلب التغيير من Agent، راجع كل ملف، ثم أعده إلى GitHub.',seeDemo:'شاهد مساحة العمل',sourceTruth:'GitHub يبقى مصدر الحقيقة',ownAi:'استخدم مزود AI الخاص بك',miniTask:'سأحسّن تجربة مساحة العمل على الهاتف.',fromYemen:'من اليمن',forDev:'للمطورين في كل مكان',pipe1:'اربط حسابك',repo:'المستودع',tempSpace:'مساحة مؤقتة',askChange:'اطلب التغيير',review:'المراجعة',backGithub:'إلى GitHub',onePlace:'مكان واحد من الطلب إلى الـPush.',onePlaceBody:'المحادثة في المنتصف، سياق المشروع دائمًا واضح، والمراجعة بجانبك عندما تحتاجها.',shotQuestion:'حسّن تجربة الهاتف بدون تغيير سطح المكتب',prompt:'اطلب تغييرًا جديدًا…',temporary:'مساحات مؤقتة',temporaryBody:'اعمل على نسخة معزولة، بينما يبقى الكود الدائم في GitHub.',yourModel:'ذكاؤك الاصطناعي',yourModelBody:'اربط المزود الذي تختاره عبر OpenCode.',reviewFirst:'راجع قبل الإرسال',reviewFirstBody:'شاهد الملفات والفرق والسجلات قبل Commit وPush.',ready:'مشروعك التالي جاهز لـOpenCode.',previewOnly:'هذه معاينة تفاعلية؛ لا يوجد اتصال فعلي بعد.',startFlow:'ابدأ المسار',setup:'إعداد مساحة جديدة',fewSteps:'من GitHub إلى OpenCode في خطوات قليلة.',setupBody:'نحفظ اختيار المشروع فقط. ملفات العمل تبقى مؤقتة وGitHub هو المصدر الدائم.',account:'الحساب',project:'المشروع',back:'رجوع',connectTitle:'اربط GitHub للبدء',connectBody:'سنطلب الوصول للمستودعات التي تختارها فقط. هذه الخطوة تجريبية الآن.',continueGithub:'المتابعة باستخدام GitHub',noRealData:'معاينة فقط — لا تُدخل أي بيانات حقيقية.',chooseProject:'اختر المشروع والفرع',chooseBody:'هذا يحدد سياق مساحة العمل المؤقتة.',continue:'متابعة',readyTitle:'كل شيء جاهز.',mockConnected:'متصل تجريبيًا',readyState:'جاهز',openSpace:'افتح مساحة العمل',newSession:'جلسة جديدة',sessions:'الجلسات',home:'الرئيسية',settings:'الإعدادات',tempWorkspace:'مساحة مؤقتة',today:'اليوم',agentHello:'ما الذي تريد تغييره في مشروعك؟',agentHelp:'أصف المهمة وسأعرض خطوات التنفيذ، الملفات المعدّلة، ونتائج الفحص هنا.',suggest1:'حسّن تجربة الهاتف',suggest2:'راجع بنية المشروع',suggest3:'أصلح مشكلة في الواجهة',workspaceReady:'مساحة العمل جاهزة',readyHint:'تم تجهيز المشروع والفرع للمعاينة.',changes:'التغييرات',viewChanges:'عرض التغييرات',simulation:'محاكاة واجهة فقط — لن يتم إرسال أي تغيير.'},
 en:{how:'How it works',workspace:'Workspace',connect:'Connect GitHub',heroTitle:'Connect GitHub. Open your project in OpenCode. Code with your AI.',heroBody:'Open your project in a temporary OpenCode workspace, ask the Agent for a change, review every file, then return it to GitHub.',seeDemo:'View workspace',sourceTruth:'GitHub stays the source of truth',ownAi:'Bring your own AI provider',miniTask:'I’ll improve the mobile workspace experience.',fromYemen:'From Yemen',forDev:'For developers everywhere',pipe1:'Connect account',repo:'Repository',tempSpace:'Temporary space',askChange:'Ask for a change',review:'Review',backGithub:'Back to GitHub',onePlace:'One place from prompt to push.',onePlaceBody:'The conversation stays central, project context is always clear, and review is ready when you need it.',shotQuestion:'Improve mobile without changing desktop',prompt:'Ask for a new change…',temporary:'Temporary workspaces',temporaryBody:'Work in an isolated checkout while permanent code stays on GitHub.',yourModel:'Your AI',yourModelBody:'Connect the provider you choose through OpenCode.',reviewFirst:'Review before push',reviewFirstBody:'See files, diffs, and logs before commit and push.',ready:'Your next project is ready for OpenCode.',previewOnly:'Interactive preview only; no services are connected yet.',startFlow:'Start the flow',setup:'NEW WORKSPACE SETUP',fewSteps:'From GitHub to OpenCode in a few steps.',setupBody:'We retain only project choices. Workspace files are temporary and GitHub stays permanent.',account:'Account',project:'Project',back:'Back',connectTitle:'Connect GitHub to begin',connectBody:'We will request access only to repositories you select. This step is simulated now.',continueGithub:'Continue with GitHub',noRealData:'Preview only — do not enter real information.',chooseProject:'Choose project and branch',chooseBody:'This defines the temporary workspace context.',continue:'Continue',readyTitle:'Everything is ready.',mockConnected:'Preview connected',readyState:'Ready',openSpace:'Open workspace',newSession:'New session',sessions:'Sessions',home:'Home',settings:'Settings',tempWorkspace:'Temporary workspace',today:'Today',agentHello:'What would you like to change?',agentHelp:'Describe the task and I’ll show execution steps, changed files, and check results here.',suggest1:'Improve the mobile experience',suggest2:'Review project structure',suggest3:'Fix a UI issue',workspaceReady:'Workspace ready',readyHint:'The project and branch are prepared for preview.',changes:'Changes',viewChanges:'View changes',simulation:'UI simulation only — no changes will be sent.'}
};
function applyPrefs(){document.documentElement.lang=lang;document.documentElement.dir=lang==='ar'?'rtl':'ltr';document.documentElement.classList.toggle('dark',dark);$$('[data-i18n]').forEach(el=>{if(copy[lang][el.dataset.i18n])el.textContent=copy[lang][el.dataset.i18n]});$$('[data-i18n-placeholder]').forEach(el=>el.placeholder=copy[lang][el.dataset.i18nPlaceholder]||'');$$('#langBtn,.lang-mirror').forEach(el=>el.textContent=lang==='ar'?'EN':'AR');localStorage.setItem('og-lang',lang);localStorage.setItem('og-theme',dark?'dark':'light')}
let currentUser=null, activeWorkspace=null, activeSession=null, activeProject=null, eventStream=null, permissionTimer=null;
let navigationRevision=0,workspaceSelectionRevision=0,permissionPending=null,permissionProgressPending=false,sessionSelectionRevision=0,messageRenderRevision=0;
const eventCursors=new Map();
let authenticationRevision=0;
const authenticatedRequests=new Set();
function authenticatedHome(user=currentUser){return ['admin','owner'].includes(user?.role)?'adminPage':'workspaceHomePage'}
const interfaceReady=document.readyState==='loading'?new Promise(resolve=>document.addEventListener('DOMContentLoaded',resolve,{once:true})):Promise.resolve();
let managementLoad=null;
window.loadManagement=function(){
 if(!managementLoad)managementLoad=interfaceReady.then(()=>new Promise((resolve,reject)=>{
  const script=document.createElement('script');script.src=document.getElementById('managementAsset').dataset.src;
  script.onload=resolve;script.onerror=()=>{script.remove();managementLoad=null;reject(new Error('Settings could not load. Retry to continue.'));};document.head.append(script);
 }));return managementLoad;
};
window.renderManagement=async(...args)=>{await window.loadManagement();return window.renderManagement(...args);};
window.openManagement=async(...args)=>{await window.loadManagement();return window.openManagement(...args);};
if(new URLSearchParams(location.hash.slice(1)).has('reset-password')){
 window.passwordRecoveryActive=true;window.loadManagement().catch(error=>{document.documentElement.classList.remove('bootstrapping');toast(error.message);});
}
const protectedPages=new Set(['clientPage','accountPage','onboarding','workspacePage','billingPage','adminPage']);
function invalidateProviderMutation(path,method='GET'){
 const mutation=path.match(/^\/api\/workspaces\/([^/]+)\/providers\/([^/?]+)(?:\/(?:credentials|oauth\/callback))?(?:\?|$)/);
 if(mutation&&!['GET','HEAD'].includes(method.toUpperCase())){
  const workspaceId=decodeURIComponent(mutation[1]);window.workspaceRuntime?.invalidate(workspaceId);
  if(method.toUpperCase()==='DELETE')window.dispatchEvent(new CustomEvent('workspace-provider-disconnected',{detail:{workspaceId,providerId:decodeURIComponent(mutation[2])}}));
 }
}
const api=async(path,options={})=>{
 const revision=authenticationRevision,controller=new AbortController();authenticatedRequests.add(controller);
 const onAbort=()=>controller.abort();options.signal?.addEventListener('abort',onAbort,{once:true});if(options.signal?.aborted)controller.abort();
 let response;
 try{response=await fetch(path,{...options,signal:controller.signal,credentials:'same-origin',headers:{...(options.body instanceof FormData?{}:{'Content-Type':'application/json'}),...(options.headers||{})}});}
 finally{authenticatedRequests.delete(controller);options.signal?.removeEventListener('abort',onAbort);}
 if(revision!==authenticationRevision)throw new Error('Authenticated session changed');
 if(response.ok)window.authSession?.observe(response.headers.get('X-Session-Idle-Expires-At'));
 if(response.status===204){invalidateProviderMutation(path,options.method);return null;}
 const body=await response.json().catch(()=>({detail:'Unexpected server response'}));
 if(revision!==authenticationRevision)throw new Error('Authenticated session changed');
 if(!response.ok){
  if(response.status===401&&!options.allowAnonymous&&currentUser)clearAuthenticatedState();
  const error=new Error(Array.isArray(body.detail)?body.detail.map(x=>x.msg).join(', '):(body.detail||'Request failed'));error.status=response.status;throw error;
 }
 invalidateProviderMutation(path,options.method);return body;
};
function toast(text){$('#toast').textContent=text;$('#toast').classList.add('show');setTimeout(()=>$('#toast').classList.remove('show'),3500)}
function clearAuthenticatedState(){
 authenticationRevision++;for(const controller of authenticatedRequests)controller.abort();authenticatedRequests.clear();
 window.authSession?.stop();window.workspaceRuntime?.clear();stopEvents();eventCursors.clear();
 currentUser=null;activeWorkspace=activeProject=activeSession=null;workspaceSelectionRevision++;sessionSelectionRevision++;messageRenderRevision++;
 try{for(let i=sessionStorage.length-1;i>=0;i--){const key=sessionStorage.key(i);if(key?.startsWith('og-'))sessionStorage.removeItem(key);}for(const key of ['og-workspace','og-page','og-clientview'])localStorage.removeItem(key);}catch(error){}
 for(const dialog of $$('dialog[open]'))if(dialog.id!=='authDialog')dialog.close();
 for(const root of $$('[data-management-section]')){root.providerController?.abort();root.providerView=null;}
 for(const id of ['agentFeed','approvalBox','sessionList','projectList','homeProjects','homeSessions','connectionsProviders','connectionsRuntime','connectionsGithub','workspaceFilesTree','workspaceFileDiff','adminUsersBody','toolsPanel'])$('#'+id)?.replaceChildren();
 for(const input of $$('input[type=password],#promptInput,#welcomeInput'))input.value='';
 for(const id of ['profileStatus','profileTrial','profileUsername','profileEmail','profilePhone','profileLocation','profileTrialDates']){const field=$('#'+id);if(field?.firstChild?.nodeType===3)field.firstChild.textContent='';else if(field)field.textContent='';}
 for(const row of $$('.signout-row'))row.remove();
 for(const select of $$('#agentSelect,#providerSelect,#modelSelect')){select.replaceChildren(new Option(select.id==='agentSelect'?(lang==='ar'?'افتراضي OpenCode':'OpenCode default'):'',''));select.disabled=true;}
 pendingIdea='';window.dispatchEvent(new Event('authentication-cleared'));updateNavigation();showPage('authPage');
}
window.logoutSession=async()=>{try{await api('/api/auth/logout',{method:'POST',signal:AbortSignal.timeout(5000)});}finally{clearAuthenticatedState();}};
window.workspaceRetentionNotice=cache=>{
 if(!cache)return '';
 const ar=lang==='ar',github=cache.scope==='github_working_copy';
 if(cache.expired)return github?(ar?'نُظّفت نسخة العمل المؤقتة؛ يبقى مستودع GitHub وبيانات الحساب محفوظين.':'Temporary worktree cleaned; the GitHub repository and account data remain preserved.'):(ar?'نُظّفت ملفات المشروع المحلي بعد الخمول؛ تبقى بيانات الحساب محفوظة.':'Inactive local project files were cleaned; account data remains preserved.');
 const expiry=new Date(cache.expires_at).toLocaleString(lang);
 if(cache.warning)return (ar?'تنبيه: المشروع المحلي خامل منذ نحو 5 أيام. افتحه أو صدّره قبل التنظيف في ':'Warning: local project inactive for about 5 days. Open or export it before cleanup at ')+expiry;
 return (github?(ar?'كاش نسخة العمل: 73 ساعة من آخر نشاط حقيقي. ':'Worktree cache: 73 hours from last meaningful activity. '):(ar?'ملفات المشروع المحلي: 7 أيام من آخر نشاط حقيقي. ':'Local project files: 7 days from last meaningful activity. '))+(ar?'موعد التنظيف: ':'Cleanup at: ')+expiry;
};
window.authSession=(()=>{
 let deadline=0,timer=null,flushTimer=null,pending=false,dirty=false,stopped=true,warning=null,lastAcknowledged=0,expiring=false;
 const label=(en,ar)=>lang==='ar'?ar:en;
 function dismiss(){warning?.remove();warning=null;}
 function stop(){stopped=true;clearInterval(timer);clearTimeout(flushTimer);timer=flushTimer=null;deadline=0;lastAcknowledged=0;dirty=false;dismiss();}
 async function flush(){
  flushTimer=null;if(stopped||pending||!dirty||!currentUser||document.hidden)return;
  pending=true;dirty=false;const revision=authenticationRevision;
  const workspaceId=activeWorkspace&&$('#workspacePage.active')?activeWorkspace.id:null;
  try{const result=await api('/api/auth/activity',{method:'POST',body:JSON.stringify({workspace_id:workspaceId})});if(revision===authenticationRevision){lastAcknowledged=Date.now();observe(result.idle_expires_at);}}
  catch(error){if(currentUser&&revision===authenticationRevision)dirty=true;}
  finally{pending=false;}
 }
 function scheduleActivity(event){
  if(!event.isTrusted||stopped||!currentUser||document.hidden)return;
  dirty=true;if(!flushTimer)flushTimer=setTimeout(flush,deadline-Date.now()<=60000?1000:Math.max(1000,30000-(Date.now()-lastAcknowledged)));
 }
 function observe(value){const parsed=Date.parse(value);if(Number.isFinite(parsed)){deadline=parsed;dismiss();}}
 async function confirmExpiry(){
  if(expiring)return;expiring=true;const revision=authenticationRevision;
  try{
   // Another tab may have extended this same server session. The server wins.
   await api('/api/auth/me',{signal:AbortSignal.timeout(5000)});
   if(revision===authenticationRevision&&deadline<=Date.now())await window.logoutSession();
  }catch(error){if(revision===authenticationRevision)clearAuthenticatedState();}
  finally{expiring=false;}
 }
 function tick(){
  if(stopped||!currentUser||!deadline)return;
  const remaining=deadline-Date.now();
  if(remaining<=0){confirmExpiry();return;}
  if(remaining>60000){dismiss();return;}
  if(!warning){
   warning=document.createElement('div');warning.className='session-idle-warning';warning.setAttribute('role','alert');
   const message=document.createElement('span'),stay=document.createElement('button');stay.type='button';stay.className='button ghost small';
   stay.onclick=()=>{dirty=true;flush();};warning.append(message,stay);document.body.append(warning);
  }
  warning.firstChild.textContent=label('Your session will expire in ','ستنتهي جلسة الدخول خلال ')+Math.ceil(remaining/1000)+label(' seconds. Unsaved text will be cleared.',' ثانية. سيُمسح النص غير المحفوظ.');
  warning.lastChild.textContent=label('Stay signed in','البقاء مسجّلًا');
  // Native dialogs are in the top layer; keep the security warning readable there.
  const host=$('dialog[open]')||document.body;if(warning.parentElement!==host)host.append(warning);
 }
 for(const kind of ['pointerdown','keydown','wheel','touchstart'])document.addEventListener(kind,scheduleActivity,{capture:true,passive:true});
 document.addEventListener('visibilitychange',()=>{tick();if(!document.hidden&&dirty)flush();});
 return {observe,stop,workspaceOpened(){if(dirty){clearTimeout(flushTimer);flush();}},start(){stopped=false;if(!timer)timer=setInterval(tick,1000);tick();}};
})();
function showPage(id){navigationRevision++;document.documentElement.classList.remove('bootstrapping');if(['admin','owner'].includes(currentUser?.role)&&['workspaceHomePage','connectionsPage','workspacePage','onboarding','clientPage','accountPage','billingPage'].includes(id))id='adminPage';$('#welcomeSidebar').classList.remove('visible');$('#sessionSidebar').classList.remove('open');overlay(false);$$('.page').forEach(p=>p.classList.toggle('active',p.id===id||(id==='authPage'&&p.id==='landing')));$('#siteHeader').style.display=id==='landing'?'flex':'none';window.scrollTo(0,0);syncPermissionPolling()}
async function page(id){await authReady;await interfaceReady;if(protectedPages.has(id)&&!currentUser){showPage('authPage');window.loadManagement().catch(error=>toast(error.message));return}if(id==='adminPage'&&!['admin','owner'].includes(currentUser?.role)){toast('Administrator access required');return}showPage(id);if(['authPage','landing'].includes(id))window.loadManagement().catch(error=>toast(error.message));try{if(id==='accountPage'){renderProfile(await api('/api/profile'));await loadProjects()}if(id==='adminPage')await loadAdminUsers();if(id==='workspacePage'&&!activeWorkspace&&!window.workspaceRestoring){showPage('onboarding')}}catch(error){if(currentUser)toast(error.message)}}
function updateNavigation(){$$('[data-go="adminPage"]').forEach(el=>el.hidden=!['admin','owner'].includes(currentUser?.role))}
function stopEvents(){eventStream?.close();eventStream=null;if(permissionTimer)clearInterval(permissionTimer);permissionTimer=null}
function syncPermissionPolling(){
 const needed=Boolean(currentUser&&activeSession&&!document.hidden&&$('#workspacePage')?.classList.contains('active'));
 if(!needed){if(permissionTimer)clearInterval(permissionTimer);permissionTimer=null;return;}
 if(!permissionTimer)permissionTimer=setInterval(async()=>{
  if(permissionProgressPending)return;permissionProgressPending=true;const id=activeSession?.id;
  try{await refreshPermissions();if(activeSession?.id===id&&['submitted','waiting_approval'].includes(activeSession?.execution_status)){await window.refreshWorkspaceSessionStatus?.();if(activeSession?.id===id)await refreshMessages();}}
  catch(error){}finally{permissionProgressPending=false;}
 },4000);
}
document.addEventListener('visibilitychange',syncPermissionPolling);
function apiMessage(id,text,error=false){const el=$('#'+id);el.textContent=text;el.className='api-message show'+(error?' error':'')}
const value=id=>$('#'+id).value.trim();
function textElement(tag,text,className){const el=document.createElement(tag);el.textContent=text;if(className)el.className=className;return el}
async function fillSelect(id,path,placeholder){const el=$('#'+id);el.replaceChildren(new Option(placeholder,''));if(path)for(const row of await api(path))el.add(new Option(row.name,row.id))}
function renderProfile(user){
 currentUser=user;updateNavigation();
 window.authSession?.start();
 const fields={profileStatus:user.status,profileTrial:user.trial_remaining_days,profileUsername:user.username,profileEmail:user.email,profilePhone:user.phone,profileLocation:[user.country,user.region,user.city,user.postal_code].filter(Boolean).join(' · '),profilePreferences:lang+' · '+(dark?'dark':'light')};
 for(const [id,text] of Object.entries(fields)){const field=document.getElementById(id);if(field)field.textContent=text??'—';}
 applyPrefs();
}
async function savePrefs(){applyPrefs();if(currentUser)try{await api('/api/profile',{method:'PATCH',body:JSON.stringify({preferred_language:lang,preferred_theme:dark?'dark':'light'})})}catch(error){toast(error.message)}}
$$('#langBtn,.lang-mirror').forEach(el=>el.onclick=()=>{lang=lang==='ar'?'en':'ar';savePrefs()});$$('#themeBtn,.theme-mirror,.workspace-theme').forEach(el=>el.onclick=()=>{dark=!dark;savePrefs()});
$$('[data-go]').forEach(el=>el.onclick=()=>page(el.dataset.go));$$('[data-start]').forEach(el=>el.onclick=()=>page(currentUser?'onboarding':'authPage'));$$('[data-demo]').forEach(el=>el.onclick=()=>page('onboarding'));$$('[data-scroll]').forEach(el=>el.onclick=()=>$('#'+el.dataset.scroll).scrollIntoView({behavior:'smooth'}));
$$('[data-auth-tab]').forEach(el=>el.onclick=()=>{$$('[data-auth-tab]').forEach(b=>b.classList.toggle('active',b===el));$$('[data-auth-form]').forEach(f=>f.classList.toggle('active',f.dataset.authForm===el.dataset.authTab))});
$('#registerCountry').onchange=async()=>{try{await fillSelect('registerRegion',value('registerCountry')?`/api/locations/countries/${value('registerCountry')}/regions`:null,'Optional');await fillSelect('registerCity',null,'Optional')}catch(error){toast(error.message)}};
$('#registerRegion').onchange=async()=>{try{await fillSelect('registerCity',value('registerRegion')?`/api/locations/regions/${value('registerRegion')}/cities`:null,'Optional')}catch(error){toast(error.message)}};
$('#registerForm').onsubmit=async event=>{event.preventDefault();if($('#registerSubmit').disabled||!event.currentTarget.reportValidity())return;if(value('registerUsername')&&value('registerUsername').length<6){apiMessage('registerMessage',t('usernameHint'),true);return}const password=$('#registerPassword').value;if(password.length<8||!/[0-9]/.test(password)||![...password].some(c=>passwordSymbols.includes(c))){apiMessage('registerMessage',t('passwordHint'),true);return}const button=$('#registerSubmit');button.disabled=true;try{const prefs={preferred_language:lang,preferred_theme:dark?'dark':'light'};const registered=await api('/api/auth/register',{method:'POST',body:JSON.stringify(registrationPayload())});if(registered.status==='pending_email'){ $('#registerPassword').value='';apiMessage('registerMessage',lang==='ar'?'تم إرسال رابط التفعيل إلى بريدك. افتح الرسالة للتحقق ثم سجل الدخول.':'Check your email for the verification link, then sign in.');return;}renderProfile(await api('/api/profile',{method:'PATCH',body:JSON.stringify(prefs)}));$('#registerPassword').value='';await page(pendingIdea?'onboarding':'accountPage');if(pendingIdea)$('#projectName').value=pendingIdea.slice(0,120)}catch(error){apiMessage('registerMessage',error.message,true)}finally{button.disabled=false}};
$('#loginForm').onsubmit=async event=>{event.preventDefault();if($('#loginSubmit').disabled||!event.currentTarget.reportValidity())return;const button=$('#loginSubmit');button.disabled=true;try{renderProfile(await api('/api/auth/login',{method:'POST',body:JSON.stringify({identity:value('loginIdentity'),password:$('#loginPassword').value})}));$('#loginPassword').value='';try{if($('#rememberIdentity').checked)localStorage.setItem('og-login-identity',value('loginIdentity'));else localStorage.removeItem('og-login-identity');}catch(error){}await page(pendingIdea?'onboarding':'accountPage');if(pendingIdea)$('#projectName').value=pendingIdea.slice(0,120)}catch(error){apiMessage('loginMessage',error.message,true)}finally{button.disabled=false}};
$('#resendEmailVerification').onclick=async()=>{const identity=value('loginIdentity').trim();const password=$('#loginPassword').value;if(!identity||!password){apiMessage('loginMessage',lang==='ar'?'أدخل البريد أو اسم المستخدم وكلمة المرور لإعادة إرسال التفعيل.':'Enter your email or username and password to resend verification.',true);return}const button=$('#resendEmailVerification');button.disabled=true;try{await api('/api/auth/resend-verification',{method:'POST',body:JSON.stringify({identity,password})});apiMessage('loginMessage',lang==='ar'?'أُرسلت رسالة تفعيل جديدة. افتح بريدك للتحقق.':'A new verification email was sent. Please check your inbox.')}catch(error){apiMessage('loginMessage',error.message,true)}finally{button.disabled=false}};
$('#logoutButton').onclick=()=>window.logoutSession().catch(error=>toast(error.message));

$$('[data-preview-action]').forEach(el=>{el.disabled=true;el.title='Not available yet'});
$$('[data-payment]').forEach(el=>el.onclick=()=>{$$('[data-payment]').forEach(b=>b.classList.toggle('active',b===el));$$('[data-payment-panel]').forEach(p=>p.classList.toggle('active',p.dataset.paymentPanel===el.dataset.payment))});
async function loadProjects(){const projects=await api('/api/projects'),workspaces=await api('/api/workspaces');const list=$('#projectList');list.replaceChildren();if(!projects.length)list.append(textElement('p',t('noProjects')));for(const project of projects){const button=textElement('button',`${project.name} · ${project.source_type}`,'button ghost');button.onclick=()=>{const workspace=workspaces.find(w=>w.project_id===project.id);if(workspace)openWorkspace(project,workspace);else toast('Workspace unavailable')};list.append(button)}}
$('#sourceType').onchange=()=>{const hint=$('#githubHint');if(hint)hint.hidden=value('sourceType')!=='github';};$('#githubHintOpen').onclick=()=>window.openConnections&&window.openConnections('github');
$('#createProjectForm').onsubmit=async event=>{event.preventDefault();const button=$('#createProjectButton');button.disabled=true;try{if(value('sourceType')==='github'){document.querySelector('#createProjectForm').closest('dialog')?.close();await window.openGithubProject();return;}const result=await api('/api/projects',{method:'POST',body:JSON.stringify({project_name:value('projectName'),source_type:value('sourceType')})});await openWorkspace(result.project,result.workspace)}catch(error){apiMessage('createProjectMessage',error.message,true)}finally{button.disabled=false}};
async function openWorkspace(project,workspace){if(['admin','owner'].includes(currentUser?.role)){await page('adminPage');return;}stopEvents();activeProject=project;activeWorkspace=workspace;activeSession=null;$('#workspaceRepo').textContent=project.name;$('#workspaceBranch').textContent=project.branch||'No branch';renderWorkspaceEmpty();$('#promptInput').value=pendingIdea;pendingIdea='';$('#runtimeStatus').textContent=t('sessionDisconnected');await page('workspacePage');await Promise.all([refreshSessions(),refreshGit()]);$('#sendMessage').disabled=true;$('#providerSelect').replaceChildren(new Option(t('selectProvider'),''));$('#modelSelect').replaceChildren(new Option(t('selectModel'),''))}
async function refreshGit(){if(!activeWorkspace)return;const state=await api(`/api/workspaces/${activeWorkspace.id}/git/status`);$('#commitButton').disabled=state.clean;$('#pushButton').disabled=true;$('#gitSummary').textContent=`${state.changes.length} ${t('changedFiles')} · ${state.head?state.head.slice(0,8):t('noCommits')}`}
async function refreshSessions(){if(!activeWorkspace)return;const rows=await api(`/api/workspaces/${activeWorkspace.id}/sessions`);const list=$('#sessionList');list.replaceChildren();for(const row of rows){const button=textElement('button',row.title,'session');button.onclick=()=>selectSession(row);list.append(button)}}
$('.new-session').onclick=async()=>{if(!activeWorkspace)return;const button=$('.new-session');button.disabled=true;try{const row=await api(`/api/workspaces/${activeWorkspace.id}/sessions`,{method:'POST',body:JSON.stringify({title:'New session'})});await refreshSessions();await selectSession(row)}catch(error){toast(error.message);$('#runtimeStatus').textContent='OpenCode unavailable'}finally{button.disabled=false}};
async function selectSession(session){const revision=++sessionSelectionRevision,workspaceId=activeWorkspace?.id;const opened=await api(`/api/sessions/${session.id}/open`,{method:'POST'});if(revision!==sessionSelectionRevision||activeWorkspace?.id!==workspaceId)return;stopEvents();activeSession={...session,...opened};$('#runtimeStatus').textContent=opened.status;$('#agentFeed').replaceChildren(textElement('p',session.title));await refreshMessages();if(revision!==sessionSelectionRevision||activeSession?.id!==session.id)return;startEvents();syncPermissionPolling()}
Object.assign(copy.en,{repeatMsg:'Repeat',copyMsg:'Copy',editMsg:'Edit',regenerateMsg:'Regenerate (new request)',hideMsg:'Hide from your view',copied:'Copied',copyFailed:'Could not copy',resent:'Message resubmitted'});
Object.assign(copy.ar,{repeatMsg:'إعادة',copyMsg:'نسخ',editMsg:'تعديل',regenerateMsg:'إعادة التوليد بطلب جديد',hideMsg:'إخفاء من واجهتك',copied:'تم النسخ',copyFailed:'تعذر النسخ',resent:'أُعيد إرسال الرسالة'});
function feedAction(kind,text,attachments=[]){const icons={"repeat":"<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8\"/><path d=\"M3 3v5h5\"/></svg>","regenerate":"<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8\"/><path d=\"M3 3v5h5\"/></svg>","copy":"<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><rect width=\"14\" height=\"14\" x=\"8\" y=\"8\" rx=\"2\" ry=\"2\"/><path d=\"M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2\"/></svg>","edit":"<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7\"/><path d=\"M18.375 2.625a1 1 0 0 1 3 3l-9.013 9.014a2 2 0 0 1-.853.505l-2.873.84a.5.5 0 0 1-.62-.62l.84-2.873a2 2 0 0 1 .506-.852z\"/></svg>","hide":"<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49\"/><path d=\"M14.084 14.158a3 3 0 0 1-4.242-4.242\"/><path d=\"M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143\"/><path d=\"m2 2 20 20\"/></svg>"};const label=t({repeat:'repeatMsg',regenerate:'regenerateMsg',copy:'copyMsg',edit:'editMsg',hide:'hideMsg'}[kind]);const b=document.createElement('button');b.type='button';b.className='icon-btn';b.innerHTML=icons[kind];b.querySelector('svg')?.setAttribute('aria-hidden','true');b.title=label;b.setAttribute('aria-label',label);b.onclick=async()=>{if(kind==='repeat'||kind==='regenerate'){if(window.workspaceSubmissionBlocked?.())return;window.restoreComposerAttachments?.(attachments);$('#promptInput').value=text;$('#promptForm').requestSubmit();toast(t('resent'));}else if(kind==='edit'){window.restoreComposerAttachments?.(attachments);$('#promptInput').value=text;$('#promptInput').focus();try{$('#promptInput').setSelectionRange(text.length,text.length)}catch(error){}}else{try{await navigator.clipboard.writeText(text);toast(t('copied'))}catch(error){try{const area=document.createElement('textarea');area.value=text;document.body.append(area);area.select();document.execCommand('copy');area.remove();toast(t('copied'))}catch(fallbackError){toast(t('copyFailed'))}}}};return b;}
function workspaceLatestControl(feed){
 let button=document.getElementById('workspaceJumpLatest');
 if(!button){
  button=document.createElement('button');
  button.id='workspaceJumpLatest';button.type='button';
  button.className='workspace-jump-latest';
  button.textContent=lang==='ar'?'↓ أحدث رسالة':'↓ Jump to latest';
  button.setAttribute('aria-label',button.textContent);
  button.onclick=()=>{feed.scrollTo({top:feed.scrollHeight,behavior:'smooth'});};
  feed.parentElement?.append(button);
 }
 if(button.dataset.boundFeed!=='agentFeed'){
  feed.addEventListener('scroll',()=>workspaceLatestVisibility(feed),{passive:true});
  button.dataset.boundFeed='agentFeed';
 }
 workspaceLatestVisibility(feed);
 return button;
}
function workspaceLatestVisibility(feed){
 const button=document.getElementById('workspaceJumpLatest');
 if(!button)return;
 button.textContent=lang==='ar'?'↓ أحدث رسالة':'↓ Jump to latest';
 button.hidden=feed.scrollHeight-feed.clientHeight-feed.scrollTop<110;
}
async function refreshMessages(){
 if(!activeSession)return;
 const sessionId=activeSession.id,owner=currentUser?.id,revision=++messageRenderRevision;
 try{
  const rows=await api(`/api/sessions/${sessionId}/messages`);
  if(revision!==messageRenderRevision||activeSession?.id!==sessionId||currentUser?.id!==owner)return;
  const feed=$('#agentFeed');workspaceLatestControl(feed);const followingLatest=feed.scrollHeight-feed.clientHeight-feed.scrollTop<110;const previousOffset=feed.scrollTop;feed.replaceChildren();const seen=new Set();let previousPrompt='',previousAttachments=[];
  const latestAssistant=rows.filter(row=>row.role==='assistant').at(-1);
  for(const row of rows){
   if(row.id&&seen.has(row.id))continue;if(row.id)seen.add(row.id);
   if(row.role==='user'){previousPrompt=row.text;previousAttachments=row.attachments||[];}
   const node=document.createElement('article');node.className=row.role==='user'?'user-bubble':'agent-response';node.dir='auto';node.tabIndex=0;
   if(row.id)node.dataset.messageId=row.id;
   const hasText=Boolean(row.text?.trim());
   const content=textElement('div',row.text||'','message-content');node.append(content);
   if(row.role==='assistant'&&!hasText){const latest=row===latestAssistant,status=latest?activeSession.execution_status:null;
    const state=status==='waiting_approval'?'waiting_approval':status==='failed'||row.state==='failed'?'failed':status==='cancelled'?'cancelled':status==='submitted'?'working':row.state==='working'&&latest?'working':'completed';
    const labels={waiting_approval:['Waiting for your approval…','بانتظار موافقتك…'],failed:['The agent could not finish this request. Review the activity below before retrying.','تعذر على الوكيل إكمال الطلب. راجع النشاط أدناه قبل إعادة المحاولة.'],cancelled:['Execution stopped.','تم إيقاف التنفيذ.'],working:['The agent is working…','الوكيل يعمل الآن…'],completed:['Tool step completed.','اكتملت خطوة الأدوات.']};
    if(latest&&state==='completed')labels.completed=['The agent finished without a text reply. Review the tool results below.','انتهى الوكيل دون رد نصي. راجع نتائج الأدوات أدناه.'];
    const feedback=textElement('p',labels[state][lang==='ar'?1:0],'agent-progress-note');feedback.setAttribute('role','status');node.append(feedback);
   }if(row.role==='user'&&row.attachments?.length){const attached=textElement('div','','message-attachments');for(const file of row.attachments){const label=textElement('span',file.name+' · '+Math.ceil(file.size/1024)+' KB');label.dir='auto';label.title=file.path;attached.append(label);}node.append(attached);}
   window.renderMessageActivity?.(node,row.activity||[]);
   if(row.role==='assistant'&&!hasText){feed.append(node);continue;}
   const bar=document.createElement('div');bar.className='feed-actions';bar.setAttribute('role','group');bar.setAttribute('aria-label',lang==='ar'?'إجراءات الرسالة':'Message actions');
   if(row.role==='user')bar.append(feedAction('repeat',row.text,row.attachments),feedAction('edit',row.text,row.attachments));
   else if(previousPrompt){const regenerate=feedAction('regenerate',previousPrompt,previousAttachments);regenerate.disabled=window.workspaceSubmissionBlocked?.()||false;bar.append(regenerate);}
   bar.append(feedAction('copy',row.text));
   if(row.id){
    const hide=feedAction('hide',row.text);hide.disabled=['submitted','waiting_approval'].includes(activeSession.execution_status);
    hide.onclick=async()=>{
     if(!await window.confirmAction(lang==='ar'?'إخفاء من واجهتك فقط؟ يبقى سياق OpenCode والإجراءات والملفات كما هي.':'Hide from your view only? OpenCode context, completed actions and files are preserved.'))return;
     try{await api(`/api/sessions/${sessionId}/messages/${encodeURIComponent(row.id)}`,{method:'DELETE'});if(activeSession?.id===sessionId)await refreshMessages();}catch(error){if(currentUser?.id===owner)toast(error.message);}
    };bar.append(hide);
   }
   node.append(bar);feed.append(node);
  }
  window.renderActivitySummary?.(rows);
  // Follow live output only while the user was already near the bottom.
  // Preserve intentional history reading during polling and avoid forced jumps.
  if(followingLatest)feed.scrollTop=feed.scrollHeight;
  else feed.scrollTop=previousOffset;
  workspaceLatestVisibility(feed);
 }catch(error){if(activeSession?.id===sessionId&&currentUser?.id===owner)toast(error.message);}
}

function startEvents(){if(!activeSession)return;stopEvents();const sessionId=activeSession.id,owner=currentUser?.id,key=String(owner)+':'+sessionId;let cursor=eventCursors.get(key)||0;try{cursor=Math.max(cursor,Number(sessionStorage.getItem('og-events:'+key))||0)}catch(error){}const stream=new EventSource(`/api/sessions/${sessionId}/events?after=${cursor}`);eventStream=stream;stream.addEventListener('authentication_expired',()=>{if(eventStream===stream&&currentUser?.id===owner)clearAuthenticatedState();});for(const kind of ['activity','submitted','analyzing','reading_files','editing','running_command','running_tests','waiting_approval','approval_decision','failed','completed','cancelled'])stream.addEventListener(kind,event=>{if(eventStream!==stream||activeSession?.id!==sessionId||currentUser?.id!==owner)return;const id=Number(event.lastEventId);if(id&&id<=(eventCursors.get(key)||cursor))return;if(id){cursor=id;eventCursors.set(key,id);try{sessionStorage.setItem('og-events:'+key,String(id))}catch(error){}}let data={};if(kind==='activity'){try{data=JSON.parse(event.data);}catch(error){return;}}window.renderWorkspaceEventLine?.(kind,data);window.dispatchEvent(new CustomEvent('workspace-execution-event',{detail:{sessionId,kind}}));});stream.onopen=()=>{if(eventStream===stream)window.dispatchEvent(new CustomEvent('workspace-execution-event',{detail:{sessionId,kind:'connected'}}))};stream.onerror=()=>{if(eventStream===stream&&activeSession?.id===sessionId)$('#runtimeStatus').textContent='Reconnecting to event stream'};syncPermissionPolling()}
async function refreshPermissions(){
 if(!activeSession)return [];
 const sessionId=activeSession.id;
 if(permissionPending?.id===sessionId)return permissionPending.promise;
 const promise=(async()=>{try{
  const requests=await api(`/api/sessions/${sessionId}/permissions`);
  if(activeSession?.id!==sessionId)return [];
  if(window.renderWorkspaceApprovals){await window.renderWorkspaceApprovals(requests,sessionId);await window.refreshWorkspaceQuestions?.();return requests;}
  const box=$('#approvalBox');box.replaceChildren();
  for(const request of requests){const row=textElement('div',`${t('approval')}: ${request.permission} `);row.append(textElement('pre',(request.patterns||[]).join('\n')));for(const [label,reply] of [[t('allowOnce'),'once'],[t('deny'),'reject']]){const button=textElement('button',label);button.disabled=reply==='once'&&!request.reviewable;button.onclick=async()=>{try{await api(`/api/sessions/${sessionId}/permissions/${request.id}`,{method:'POST',body:JSON.stringify({reply})});await refreshPermissions()}catch(error){toast(error.message)}};row.append(button)}box.append(row)}return requests;
 }catch(error){if(activeSession?.id===sessionId){stopEvents();toast(error.message);}throw error;}})();
 permissionPending={id:sessionId,promise};
 try{return await promise;}finally{if(permissionPending?.promise===promise)permissionPending=null;}
}
$('#promptForm').onsubmit=event=>event.preventDefault();
$('#stopAgent').onclick=async()=>{if(activeSession)try{await api(`/api/sessions/${activeSession.id}/stop`,{method:'POST'})}catch(error){toast(error.message)}};
const promptInput=$('#promptInput');if(promptInput){const growPrompt=()=>{promptInput.style.height='auto';promptInput.style.height=Math.min(promptInput.scrollHeight,260)+'px'};promptInput.addEventListener('input',growPrompt);promptInput.addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();if(!event.repeat&&!window.workspaceSubmissionBlocked?.())promptInput.closest('form')?.requestSubmit();}});growPrompt();}
function overlay(open){$('#backdrop').classList.toggle('open',open)}$('#openSessions').onclick=()=>{$('#sessionSidebar').classList.add('open');overlay(true)};$('#closeSessions').onclick=()=>{$('#sessionSidebar').classList.remove('open');overlay(false)};$('#backdrop').onclick=()=>{overlay(false);$('#sessionSidebar').classList.remove('open')};
async function loadAdminUsers(){try{const overview=await api('/api/admin/overview');$$('[data-overview]').forEach(el=>el.textContent=overview.users[el.dataset.overview]??'—')}catch(error){toast(error.message)}const body=$('#adminUsersBody');body.replaceChildren();try{for(const user of await api('/api/admin/users')){const row=document.createElement('tr');for(const text of [user.username+' · '+user.email,user.phone,[user.country,user.region,user.city].filter(Boolean).join(' · '),user.trial_remaining_days+' days','Not available yet','Not available yet',user.trial_remaining_days+' days','Not available yet','—',user.last_login_at||'Never',user.status])row.append(textElement('td',text));body.append(row)}}catch(error){const row=document.createElement('tr');const cell=textElement('td',error.message);cell.colSpan=11;row.append(cell);body.append(row)}}
applyPrefs();updateNavigation();
const authReady=(async()=>{
 try{renderProfile(await api('/api/auth/me',{allowAnonymous:true}));}
 catch(error){
  if(error.status===401){
   let hadWorkspace=false;try{hadWorkspace=Boolean(localStorage.getItem('og-workspace'));}catch(ignored){}
   window.authRestoreExpired=hadWorkspace||error.message!=='Authentication required';clearAuthenticatedState();
   if(error.message==='Account reactivation required'){
    try{
     window.reactivationAccount=await api('/api/auth/reactivation',{allowAnonymous:true});window.passwordRecoveryActive=true;
     window.loadManagement().then(()=>window.openReactivation()).catch(error=>toast(error.message));
    }catch(ignored){/* An expired limited session needs a new email proof. */}
   }
  }else if(currentUser)toast(error.message);
 }
})();
let registrationCountries=null;
function ensureRegistrationCountries(){if(!$('#registerCountry').required)return Promise.resolve();if(!registrationCountries)registrationCountries=fillSelect('registerCountry','/api/locations/countries','Select country').catch(error=>{registrationCountries=null;apiMessage('registerMessage',error.message,true)});return registrationCountries;}
document.addEventListener('click',event=>{if(event.target.closest('[data-auth-tab="register"]'))ensureRegistrationCountries();});
$('#registerCountry').addEventListener('focus',ensureRegistrationCountries);
async function restoreWorkspaceContext(){
 let workspaceId='';try{workspaceId=localStorage.getItem('og-workspace')||'';}catch(error){}
 if(!workspaceId)return null;
 const selection=workspaceSelectionRevision,owner=currentUser?.id;
 try{
  // The owned API validates the persisted ID before it becomes active context.
  const workspace=await api('/api/workspaces/'+encodeURIComponent(workspaceId));
  if(workspace.files_available===false){
   if(owner===currentUser?.id&&selection===workspaceSelectionRevision){
    activeWorkspace=activeProject=activeSession=null;
    try{localStorage.removeItem('og-workspace');}catch(ignored){}
   }
   return null;
  }
  const project=await api('/api/projects/'+encodeURIComponent(workspace.project_id));
  if(owner!==currentUser?.id||selection!==workspaceSelectionRevision)return null;
  activeWorkspace=workspace;activeProject=project;return {workspace,project};
 }catch(error){if(selection===workspaceSelectionRevision&&[403,404].includes(error.status)){try{localStorage.removeItem('og-workspace');}catch(ignored){}}return null;}
}
const navigationReady=authReady.then(async()=>{
 await interfaceReady;if(window.passwordRecoveryActive)return;
 if(!currentUser){await page(location.hash.startsWith('#social=')||window.authRestoreExpired?'authPage':'landing');return;}
 window.__navRestored=true;
 if(['admin','owner'].includes(currentUser.role)){await page('adminPage');return;}
 let target='';try{target=localStorage.getItem('og-page')||'';}catch(error){}
 if(window.openClientWorkspace&&(!target||target==='workspaceHomePage'||location.hash==='#social=success')){await window.openClientWorkspace();return;}
 if(!['workspaceHomePage','clientPage','connectionsPage','workspacePage'].includes(target))target='workspaceHomePage';
 window.workspaceRestoring=['workspacePage','connectionsPage'].includes(target);
 showPage(target);const navigation=navigationRevision;
 window.workspaceContextReady=window.workspaceRestoring?restoreWorkspaceContext():Promise.resolve(null);
 if(target==='workspacePage'){
  const context=await window.workspaceContextReady;window.workspaceRestoring=false;
  if(navigation!==navigationRevision){if(context&&document.querySelector('#workspacePage.active'))await openWorkspace(context.project,context.workspace);return;}
  if(context)await openWorkspace(context.project,context.workspace);else await page('workspaceHomePage');return;
 }
 if(target==='clientPage'){let view='';try{view=localStorage.getItem('og-clientview')||'';}catch(error){}if(view&&window.openClientView){await window.openClientView(view);return;}}
 await page(target);window.workspaceRestoring=false;
}).catch(error=>{document.documentElement.classList.remove('bootstrapping');toast(error.message)});
// GitHub authorization/repository metadata loads only when its UI is opened.
window.bootstrapGithubStatus=Promise.resolve(null);
$('#sourceType').querySelector('option[value=github]').disabled=false;


Object.assign(copy.en,{newProject:'New project',yourProjects:'Your projects',workspaceLabel:'YOUR WORKSPACE',projectsHint:'Your next idea starts here.',projectsSubhint:'Create a project to keep your work in one place.',notConnected:'Not connected',yourAccount:'Your account',accountHint:'Profile & preferences',getStarted:'Get started',yourSpace:'YOUR IDEAS. YOUR WORKSPACE.',welcomeTitle:'What will you build today?',welcomeSubtitle:'A little less setup. A lot more possibility.',welcomePlaceholder:'Describe an idea, start a project, or make something better…',buildWithAi:'Build with your AI',startBlank:'Start from scratch',useTemplate:'Use a template',openProject:'Open a project',madeForFlow:'A workspace that stays out of your way',filesTogether:'Your files, together',filesTogetherBody:'Start blank or choose a template. Your project has a space of its own.',keepContext:'Pick up where you left off',keepContextBody:'Start a new conversation while keeping the same project files.',reviewClearly:'See every change',reviewClearlyBody:'Browse files, inspect the diff, and commit when you are ready.',independentNotice:'Independent workspace. OpenCode and GitHub are external services.',pricingTitle:'Simple pricing',pricingSubtitle:'Pay only for the time you use. No hidden fees.',pricingSummary:'Live prices from the plan catalog.',});
Object.assign(copy.ar,{newProject:'مشروع جديد',yourProjects:'مشاريعك',workspaceLabel:'مساحة عملك',projectsHint:'فكرتك القادمة تبدأ هنا.',projectsSubhint:'أنشئ مشروعًا لتجمع ملفاتك وعملك في مكان واحد.',notConnected:'غير متصل',yourAccount:'حسابك',accountHint:'الملف الشخصي والتفضيلات',getStarted:'ابدأ الآن',yourSpace:'أفكارك. مساحة عملك.',welcomeTitle:'ماذا ستبني اليوم؟',welcomeSubtitle:'خطوات أقل للبدء. مساحة أكبر للإبداع.',welcomePlaceholder:'صِف فكرة، ابدأ مشروعًا، أو طوّر شيئًا موجودًا…',buildWithAi:'ابنِ بمزوّدك الذكي',startBlank:'ابدأ من الصفر',useTemplate:'استخدم قالبًا',openProject:'افتح مشروعًا',madeForFlow:'مساحة تترك لك التركيز على ما تصنعه',filesTogether:'ملفاتك في مكان واحد',filesTogetherBody:'ابدأ بمشروع فارغ أو اختر قالبًا. لكل مشروع مساحة تخصّه.',keepContext:'أكمل من حيث توقفت',keepContextBody:'ابدأ محادثة جديدة مع الاحتفاظ بملفات مشروعك نفسها.',reviewClearly:'كل تغيير أمامك',reviewClearlyBody:'تصفح الملفات وراجع الفروق، ثم احفظ التغييرات عندما تكون جاهزًا.',independentNotice:'منصة مستقلة. OpenCode وGitHub خدمتان خارجيتان.',pricingTitle:'أسعار بسيطة',pricingSubtitle:'ادفع فقط مقابل المدة التي تستخدمها. لا رسوم خفية.',pricingSummary:'أسعار مباشرة من كتالوج الخطط.',});
let pendingIdea='';
$('#welcomePrompt').onsubmit=async event=>{event.preventDefault();pendingIdea=$('#welcomeInput').value.trim();await page(currentUser?'onboarding':'authPage');if(currentUser&&pendingIdea)$('#projectName').value=pendingIdea.slice(0,120)};
$$('[data-quick]').forEach(button=>button.onclick=async()=>{await page('onboarding');$('#sourceType').value=button.dataset.quick;$('#sourceType').dispatchEvent(new Event('change'))});
$('#welcomeMenu').onclick=()=>{const open=$('#welcomeSidebar').classList.toggle('visible');$('#welcomeMenu').setAttribute('aria-expanded',String(open));};document.addEventListener('keydown',event=>{if(event.key==='Escape'){$('#welcomeSidebar').classList.remove('visible');$('#welcomeMenu').setAttribute('aria-expanded','false');$('#backdrop').click();}});
applyPrefs();

const uiCopy={"ui3": {"en": "New project", "ar": "مشروع جديد"}, "ui48": {"en": "Your projects", "ar": "مشاريعك"}, "ui58": {"en": "Account", "ar": "الحساب"}, "ui69": {"en": "Not connected", "ar": "غير متصل"}, "ui17": {"en": "WELCOME TO OPENCODE", "ar": "مرحبًا بك في OpenCode"}, "ui18": {"en": "YOUR PERSONAL WORKSPACE", "ar": "مساحة عملك الخاصة"}, "ui19": {"en": "A quiet space. Big ideas. Code your way.", "ar": "مساحة هادئة. أفكار كبيرة. كود تصنعه بطريقتك."}, "ui20": {"en": "Create your project", "ar": "أنشئ مشروعك"}, "ui21": {"en": "Blank or a starter template", "ar": "مشروع فارغ أو قالب للبدء"}, "ui22": {"en": "Keep your files together", "ar": "اجمع ملفاتك في مكان واحد"}, "ui23": {"en": "A workspace of your own", "ar": "مساحة تخصك"}, "ui24": {"en": "OpenCode workspace", "ar": "مساحة OpenCode"}, "ui25": {"en": "Files organized by project", "ar": "ملفات مرتبة حسب المشروع"}, "ui26": {"en": "Review with confidence", "ar": "راجع تغييراتك بثقة"}, "ui27": {"en": "Real files, diffs and commits", "ar": "ملفات وفروق وتغييرات فعلية"}, "ui28": {"en": "Login", "ar": "تسجيل الدخول"}, "ui29": {"en": "Create account", "ar": "إنشاء حساب"}, "ui30": {"en": "Welcome back", "ar": "أهلًا بعودتك"}, "ui31": {"en": "Sign in to continue your projects.", "ar": "سجّل الدخول لمتابعة مشاريعك."}, "ui32": {"en": "Email or username", "ar": "البريد الإلكتروني أو اسم المستخدم"}, "ui33": {"en": "Password", "ar": "كلمة المرور"}, "ui34": {"en": "Password recovery — unavailable", "ar": "استعادة كلمة المرور غير متاحة"}, "ui35": {"en": "Create your account", "ar": "أنشئ حسابك"}, "ui36": {"en": "Create your account to start building.", "ar": "أنشئ حسابًا وابدأ العمل على أفكارك."}, "ui37": {"en": "Username", "ar": "اسم المستخدم"}, "ui38": {"en": "Country *", "ar": "الدولة *"}, "ui39": {"en": "Email", "ar": "البريد الإلكتروني"}, "ui40": {"en": "Region", "ar": "المنطقة"}, "ui44": {"en": "Optional", "ar": "اختياري"}, "ui41": {"en": "City", "ar": "المدينة"}, "ui42": {"en": "Phone *", "ar": "الهاتف *"}, "ui43": {"en": "ZIP / Postal Code *", "ar": "الرمز البريدي *"}, "ui45": {"en": "or", "ar": "أو"}, "ui46": {"en": "Create a project", "ar": "أنشئ مشروعًا"}, "ui47": {"en": "Start without GitHub. Your project files live in a local workspace.", "ar": "ابدأ بمشروع جديد. ستُحفظ ملفاته في مساحة عمل محلية."}, "ui49": {"en": "Project name", "ar": "اسم المشروع"}, "ui50": {"en": "Source", "ar": "مصدر المشروع"}, "ui51": {"en": "Blank project", "ar": "مشروع فارغ"}, "ui52": {"en": "Template", "ar": "قالب جاهز"}, "ui53": {"en": "GitHub — Not connected", "ar": "GitHub غير متصل"}, "ui54": {"en": "Templates contain starter files only. No dependencies are installed or executed.", "ar": "تحتوي القوالب على ملفات البداية. يمكنك تطويرها داخل مشروعك."}, "ui55": {"en": "Create project", "ar": "إنشاء المشروع"}, "ui1": {"en": "+ New Session", "ar": "+ جلسة جديدة"}, "ui2": {"en": "Account / Projects", "ar": "الحساب والمشاريع"}, "ui4": {"en": "Home", "ar": "الرئيسية"}, "ui14": {"en": "GitHub: Not connected", "ar": "GitHub غير متصل"}, "ui15": {"en": "Select provider", "ar": "اختر المزوّد"}, "ui16": {"en": "Select model", "ar": "اختر النموذج"}, "ui9": {"en": "Send", "ar": "إرسال"}, "ui10": {"en": "Stop", "ar": "إيقاف"}, "ui5": {"en": "Review", "ar": "المراجعة"}, "ui6": {"en": "Files", "ar": "الملفات"}, "ui7": {"en": "Diff", "ar": "الفروق"}, "ui8": {"en": "Logs", "ar": "السجلات"}, "ui11": {"en": "Commit", "ar": "حفظ التغييرات"}, "ui12": {"en": "Push — unavailable", "ar": "الإرسال غير متاح"}, "ui56": {"en": "ACCOUNT", "ar": "الحساب"}, "ui57": {"en": "Logout", "ar": "تسجيل الخروج"}, "ui59": {"en": "Profile", "ar": "الملف الشخصي"}, "ui60": {"en": "GitHub connection", "ar": "ربط GitHub"}, "ui61": {"en": "Plan & billing", "ar": "الخطة والفوترة"}, "ui62": {"en": "AI provider", "ar": "مزوّد الذكاء الاصطناعي"}, "ui63": {"en": "Sessions", "ar": "الجلسات"}, "ui64": {"en": "Security", "ar": "الأمان"}, "ui65": {"en": "CUSTOMER ACCOUNT", "ar": "حسابك"}, "ui66": {"en": "Account and connections", "ar": "الحساب والاتصالات"}, "ui67": {"en": "A simple control area separate from your coding workspace.", "ar": "مشاريعك وبياناتك وتفضيلاتك في مكان واحد."}, "ui68": {"en": "Account status", "ar": "حالة الحساب"}, "ui70": {"en": "GitHub App is not configured", "ar": "ربط GitHub غير متاح بعد"}, "ui72": {"en": "Provider authentication is not available yet.", "ar": "ربط حساب المزوّد غير متاح بعد."}, "ui73": {"en": "Projects", "ar": "المشاريع"}, "ui74": {"en": "Phone", "ar": "الهاتف"}, "ui75": {"en": "Location / postal code", "ar": "الموقع والرمز البريدي"}, "ui76": {"en": "Language / theme", "ar": "اللغة والمظهر"}, "ui77": {"en": "Billing is not available yet. No payments are collected.", "ar": "الفوترة غير متاحة بعد. لا يتم تحصيل أي مدفوعات."}, "ui0": {"en": "New Session", "ar": "جلسة جديدة"}, "ui71": {"en": "Not configured", "ar": "غير مُعدّ"}, "taskPlaceholder": {"en": "Describe your task…", "ar": "صِف ما تريد إنجازه…"}, "sessionDisconnected": {"en": "No session connected", "ar": "لم تتصل جلسة بعد"}, "selectProvider": {"en": "Select a connected provider", "ar": "اختر مزوّدًا متصلًا"}, "selectModel": {"en": "Select model", "ar": "اختر النموذج"}, "noProjects": {"en": "No projects yet. Create a Blank or Template project.", "ar": "لا توجد مشاريع بعد. ابدأ بمشروع فارغ أو قالب."}, "noEvents": {"en": "No execution events yet", "ar": "لا توجد أحداث تنفيذ بعد"}, "noChanges": {"en": "No changes", "ar": "لا توجد تغييرات"}, "loading": {"en": "Loading…", "ar": "جارٍ التحميل…"}, "approval": {"en": "Approval requested", "ar": "طلب موافقة"}, "allowOnce": {"en": "Allow once", "ar": "السماح مرة واحدة"}, "deny": {"en": "Deny", "ar": "رفض"}, "changedFiles": {"en": "changed files", "ar": "ملفات معدّلة"}, "noCommits": {"en": "No commits yet", "ar": "لا توجد تغييرات محفوظة بعد"}, "spaceReady": {"en": "Your workspace is ready", "ar": "مساحة عملك جاهزة"}, "spaceReadyBody": {"en": "Your files are on the right. Start a session when OpenCode is available, then choose a connected model.", "ar": "تصفح ملفاتك من لوحة المراجعة. عندما يتوفر OpenCode، ابدأ جلسة واختر نموذجًا متصلًا للعمل."}, "spaceReadyHint": {"en": "A new conversation keeps your project files.", "ar": "محادثة جديدة، مع الاحتفاظ بملفات مشروعك."}, "sessionEmpty": {"en": "No conversations yet", "ar": "لا توجد محادثات بعد"}};
for(const [key,values] of Object.entries(uiCopy)){copy.en[key]=values.en;copy.ar[key]=values.ar;}
function t(key){return copy[lang][key]||key;}
function renderWorkspaceEmpty(){const box=textElement("section","","workspace-empty");box.append(brandMark(),textElement("h1",t("spaceReady")),textElement("p",t("spaceReadyBody")),textElement("small",t("spaceReadyHint")));$("#agentFeed").replaceChildren(box);}
applyPrefs();

function brandMark(){const box=document.createElement("div");box.className="workspace-empty-mark";box.innerHTML='<svg aria-hidden="true" viewBox="0 0 16 20"><use href="#icon-opencode"/></svg>';return box;}

const passwordSymbols="!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~";
Object.assign(copy.en,{usernameHint:"At least 6 characters",passwordHint:"8+ characters, including a number and a symbol (such as ! or @)"});
Object.assign(copy.ar,{usernameHint:"6 أحرف على الأقل",passwordHint:"8 أحرف على الأقل، تتضمن رقمًا ورمزًا مثل ! أو @"});
Object.assign(copy.en,{showPassword:"Show password",hidePassword:"Hide password"});
Object.assign(copy.ar,{showPassword:"إظهار كلمة المرور",hidePassword:"إخفاء كلمة المرور"});
function refreshPasswordToggles(){
  $$('.pw-toggle').forEach(btn=>{const input=document.getElementById(btn.dataset.pw);if(!input)return;const hidden=input.type==='password';btn.textContent=hidden?t('showPassword'):t('hidePassword');btn.setAttribute('aria-label',btn.textContent);btn.setAttribute('aria-pressed',String(!hidden))});
  $$('[data-reveal]').forEach(btn=>{const input=document.getElementById(btn.dataset.reveal);if(!input)return;const hidden=input.type==='password';btn.setAttribute('aria-label',hidden?t('showPassword'):t('hidePassword'));btn.setAttribute('aria-pressed',String(!hidden))});
}
for(const id of ['loginPassword','registerPassword']){const input=document.getElementById(id);if(!input||input.parentElement.querySelector('.pw-toggle')||input.parentElement.querySelector('[data-reveal]'))continue;const btn=document.createElement('button');btn.type='button';btn.className='pw-toggle';btn.dataset.pw=id;btn.onclick=()=>{input.type=input.type==='password'?'text':'password';refreshPasswordToggles();input.focus()};input.after(btn)}
$$('[data-reveal]').forEach(btn=>{const input=document.getElementById(btn.dataset.reveal);if(!input)return;btn.onclick=()=>{input.type=input.type==='password'?'text':'password';refreshPasswordToggles();input.focus()}});
const prevPrefsPw=applyPrefs;applyPrefs=function(){prevPrefsPw();refreshPasswordToggles()};
refreshPasswordToggles();
applyPrefs();


/* Shared native dialogs for account and administration actions. */
(() => {
  let sequence=0;
  const tr=(en,ar)=>lang==='ar'?ar:en;
  const element=(tag,text='',cls='')=>{const n=document.createElement(tag);n.textContent=text;n.className=cls;return n;};
  window.mountFormDialog=(root,form,title,launchText)=>{
    if(form.formDialog)return form.formDialog;
    const dialog=element('dialog','','action-form-dialog');dialog.dataset.formDialog='';
    const head=element('header','','action-dialog-head'),heading=element('h2',title),close=element('button','×','icon');
    heading.id='action-dialog-'+(++sequence);dialog.setAttribute('aria-labelledby',heading.id);
    close.type='button';close.setAttribute('aria-label',tr('Close','إغلاق'));close.onclick=()=>dialog.close();head.append(heading,close);
    const body=element('div','','action-dialog-body');body.append(form);
    const actions=element('div','','action-form-actions'),cancel=element('button',tr('Cancel','إلغاء'),'button ghost');cancel.type='button';cancel.onclick=()=>dialog.close();
    const save=form.querySelector('button[type=submit]');actions.append(cancel);if(save)actions.append(save);form.append(actions);
    dialog.append(head,body);root.append(dialog);
    const trigger=element('button',launchText||title,'button ghost');trigger.type='button';trigger.dataset.openForm='';trigger.setAttribute('aria-haspopup','dialog');
    const open=()=>{if(!dialog.open){dialog.showModal();requestAnimationFrame(()=>form.querySelector('input:not([type=hidden]),select,textarea')?.focus());}};
    trigger.onclick=open;root.insertBefore(trigger,dialog);
    dialog.addEventListener('close',()=>{for(const input of form.querySelectorAll('input[type=password]'))input.value='';if(trigger.isConnected)trigger.focus();});
    form.formDialog=dialog;form.openDialog=open;form.dialogTrigger=trigger;return dialog;
  };
  window.requestForm=(title,fields,submitLabel=tr('Save','حفظ'))=>new Promise(resolve=>{
    const host=element('div'),form=element('form','','manage-form');let result=null;
    for(const field of fields){const label=element('label',field.label),id='action-field-'+(++sequence);let input;
      if(field.options){input=element('select');for(const option of field.options)input.add(new Option(option.label||option,option.value||option));}
      else{input=element('input');input.type=field.type||'text';}
      input.name=field.name;input.id=id;input.value=field.value??'';input.required=field.required??false;input.autocomplete=field.type==='password'?'off':field.autocomplete||'off';
      for(const key of ['min','max','minLength','maxLength','pattern'])if(field[key]!==undefined)input[key]=field[key];label.htmlFor=id;label.append(input);form.append(label);
    }
    const save=element('button',submitLabel,'button');save.type='submit';form.append(save);host.append(form);document.body.append(host);
    const dialog=window.mountFormDialog(host,form,title);form.dialogTrigger.hidden=true;
    form.onsubmit=event=>{event.preventDefault();if(!form.reportValidity())return;result=Object.fromEntries(new FormData(form));dialog.close();};
    dialog.addEventListener('close',()=>{host.remove();resolve(result);},{once:true});form.openDialog();
  });
  window.confirmAction=async(title)=>Boolean(await window.requestForm(title,[],tr('Confirm','تأكيد')));
  window.requestInput=async(title,value='',type='text')=>{const result=await window.requestForm(title,[{name:'value',label:title,value,type}],tr('Continue','متابعة'));return result?.value??null;};
  window.editProfileForm=()=>window.requestForm(tr('Edit profile','تعديل الملف'),[
    {name:'phone',label:tr('Phone','الهاتف'),type:'tel',value:currentUser?.phone||'',required:true},
    {name:'postal_code',label:tr('Postal code','الرمز البريدي'),value:currentUser?.postal_code||'',required:true}
  ]);
  const basePage=page;page=async function(...args){document.querySelectorAll('dialog[data-form-dialog][open]').forEach(dialog=>dialog.close());return basePage(...args);};
  document.addEventListener('DOMContentLoaded',()=>{
    for(const [id,en,ar] of [['adminPlanForm','Add plan','إضافة خطة'],['adminPolicyForm','Edit platform policy','تعديل سياسة المنصة'],['createProjectForm','Create project','إنشاء مشروع']]){
      const form=document.getElementById(id);if(!form)continue;
      // Label placeholder-only fields before relocating the existing bound form.
      for(const input of form.querySelectorAll('input:not([type=checkbox])'))if(!input.closest('label')){
        const labels={planCode:['Plan code','رمز الخطة'],planName:['Plan name','اسم الخطة'],planPrice:['Price in cents','السعر بالسنت'],planDays:['Duration in days','المدة بالأيام']};
        const label=element('label',labels[input.id]?tr(...labels[input.id]):input.placeholder);input.before(label);label.append(input);
      }
      const root=form.parentElement;window.mountFormDialog(root,form,tr(en,ar));
      const message=document.getElementById(id==='adminPlanForm'?'adminPlanMessage':id==='adminPolicyForm'?'adminPolicyMessage':'projectMessage');if(message)form.append(message);
      if(id==='createProjectForm'){
        form.querySelector('h2')?.remove();const pageNode=document.getElementById('onboarding');
        new MutationObserver(()=>{if(pageNode.classList.contains('active'))form.openDialog();else if(form.formDialog.open)form.formDialog.close();}).observe(pageNode,{attributes:true,attributeFilter:['class']});
      }
    }
    const authPage=document.getElementById('authPage'),card=authPage.querySelector('.auth-card');
    const authDialog=element('dialog','','action-form-dialog auth-action-dialog');authDialog.id='authDialog';authDialog.setAttribute('aria-label',tr('Account access','الدخول للحساب'));
    const columns=element('div','','auth-dialog-columns'),workflow=authPage.querySelector('.auth-workflow');if(workflow)columns.append(workflow);columns.append(card);authDialog.append(columns);authPage.append(authDialog);
    const closeBtn=card.querySelector('.close');if(closeBtn){closeBtn.type='button';closeBtn.setAttribute('aria-label',tr('Close','إغلاق'));closeBtn.onclick=()=>authDialog.close();}
    const syncAuth=()=>{if(authPage.classList.contains('active')&&!window.passwordRecoveryActive){if(!authDialog.open)authDialog.showModal();}else if(authDialog.open)authDialog.close();};
    window.openAuthLogin=()=>{showPage('authPage');$('[data-auth-tab=login]').click();syncAuth();};
    authDialog.addEventListener('close',()=>{if(authDialog.open)return;if(authPage.classList.contains('active')&&!currentUser&&!window.passwordRecoveryActive)page('landing');});
    new MutationObserver(syncAuth).observe(authPage,{attributes:true,attributeFilter:['class']});syncAuth();
    const welcomeInput=document.getElementById('welcomeInput');const requireEntry=async()=>{await authReady;if(!currentUser)await page('authPage');};welcomeInput.addEventListener('focus',requireEntry);welcomeInput.addEventListener('beforeinput',event=>{if(!currentUser){event.preventDefault();requireEntry();}});
  });
})();

/* Shared viewport-bounded dragging for existing native dialogs. */
(() => {
 const handles='.action-dialog-head,.grid-modal-head,dialog>h2';
 const clamp=dialog=>{const rect=dialog.getBoundingClientRect(),gap=8;dialog.style.left=Math.max(gap,Math.min(rect.left,innerWidth-rect.width-gap))+'px';dialog.style.top=Math.max(gap,Math.min(rect.top,innerHeight-rect.height-gap))+'px';};
 document.addEventListener('pointerdown',event=>{
  const header=event.target.closest(handles),dialog=header?.closest('dialog[open]');
  if(!dialog||event.button!==0||event.target.closest('button,a,input,select,textarea')||!matchMedia('(min-width: 769px) and (pointer: fine)').matches)return;
  const rect=dialog.getBoundingClientRect(),x=event.clientX,y=event.clientY;
  Object.assign(dialog.style,{position:'fixed',inset:'auto',margin:'0',left:rect.left+'px',top:rect.top+'px'});dialog.dataset.dragged='';
  header.setPointerCapture(event.pointerId);event.preventDefault();
  const move=e=>{dialog.style.left=rect.left+e.clientX-x+'px';dialog.style.top=rect.top+e.clientY-y+'px';clamp(dialog);};
  const stop=()=>{header.removeEventListener('pointermove',move);header.removeEventListener('pointerup',stop);header.removeEventListener('pointercancel',stop);header.removeEventListener('lostpointercapture',stop);};
  header.addEventListener('pointermove',move);header.addEventListener('pointerup',stop);header.addEventListener('pointercancel',stop);header.addEventListener('lostpointercapture',stop);
 });
 document.addEventListener('close',event=>{if(event.target.matches('dialog[data-dragged]')){event.target.removeAttribute('data-dragged');for(const key of ['position','inset','margin','left','top'])event.target.style[key]='';}},true);
 window.addEventListener('resize',()=>document.querySelectorAll('dialog[open][data-dragged]').forEach(dialog=>{if(innerWidth<=768){dialog.removeAttribute('data-dragged');for(const key of ['position','inset','margin','left','top'])dialog.style[key]='';}else clamp(dialog);}));
})();
/* Password managers own passwords; Remember stores identity text only. */
Object.assign(copy.en,{rememberIdentity:'Remember email / username only',socialGithub:'Continue with GitHub',socialGoogle:'Continue with Google'});
Object.assign(copy.ar,{rememberIdentity:'تذكّر البريد / اسم المستخدم فقط',socialGithub:'المتابعة باستخدام GitHub',socialGoogle:'المتابعة باستخدام Google'});
Object.assign(copy.en,{benefitsTitle:'Everything for your project',b1t:'Use OpenCode online',b1d:'Work with your coding workspace directly from the browser.',b2t:'Connect your GitHub project',b2d:'Link your repository and keep working with your existing source.',b3t:'Secure provider connections',b3d:'Connect supported AI providers while credentials stay server-side.',b4t:'30-day Core trial',b4d:'Full core access with 50 MB per local project.',b5t:'One 30-day trial',b5d:'Verify your email to begin your only 30-day trial.',b6t:'One workspace for your project',b6d:'Keep files, sessions and reviews in a single place.',authHeadline:'Start your 30-day Core trial',authSubhead:'Sign in to continue your projects. There is no second trial.',brandName:'OpenCode Gateway'});
Object.assign(copy.ar,{benefitsTitle:'كل ما يحتاجه مشروعك',b1t:'استخدم OpenCode عبر الإنترنت',b1d:'اعمل في مساحة الترميز مباشرة من المتصفح.',b2t:'اربط مشروع GitHub',b2d:'اربط مستودعك وتابع العمل بمصدرك الحالي.',b3t:'اتصالات مزوّدين آمنة',b3d:'اربط مزوّدي الذكاء الاصطناعي المدعومين وتبقى بيانات الاعتماد على الخادم.',b4t:'تجربة الأساس 30 يومًا',b4d:'وصول أساسي كامل مع 50 MB لكل مشروع محلي.',b5t:'تجربة واحدة لمدة 30 يوماً',b5d:'تبدأ التجربة الوحيدة بعد تفعيل البريد الإلكتروني.',b6t:'مساحة عمل واحدة لمشروعك',b6d:'اجمع الملفات والجلسات والمراجعات في مكان واحد.',authHeadline:'ابدأ تجربة الأساس المجانية لمدة 30 يومًا',authSubhead:'سجّل الدخول لمتابعة مشاريعك. لا توجد تجربة إضافية بعد الثلاثين يومًا.',brandName:'OpenCode Gateway'});
try{const remembered=localStorage.getItem('og-login-identity');if(remembered){$('#loginIdentity').value=remembered;$('#rememberIdentity').checked=true;}}catch(error){}
let socialOptions;
async function loadSocialOptions(){
 if(!socialOptions)socialOptions=api('/api/auth/social/options',{allowAnonymous:true}).catch(error=>{socialOptions=null;throw error;});
 try{const options=await socialOptions;for(const button of $$('[data-social-login]')){button.disabled=!options[button.dataset.socialLogin];button.title=button.disabled?(lang==='ar'?'غير مهيأ على هذا الخادم':'Not configured on this server'):'';}}
 catch(error){$('#socialLoginNote').textContent=error.message;}
}
$$('[data-social-login]').forEach(button=>{button.disabled=true;button.onclick=()=>location.assign('/api/auth/social/'+button.dataset.socialLogin+'/start');});
new MutationObserver(()=>{if($('#authPage').classList.contains('active'))loadSocialOptions();}).observe($('#authPage'),{attributes:true,attributeFilter:['class']});
window.linkSignInProvider=provider=>location.assign('/api/auth/social/'+provider+'/start');
navigationReady.then(async()=>{
 const result=new URLSearchParams(location.hash.slice(1)).get('social');if(!result)return;
 history.replaceState(null,'',location.pathname+location.search);
 if(result==='register'){
  try{const pending=await api('/api/auth/social/pending',{allowAnonymous:true});if(pending.pending){await page('authPage');$('[data-auth-tab=register]').click();$('#registerEmail').value=pending.email;$('#registerEmail').readOnly=true;apiMessage('registerMessage',lang==='ar'?'أكمل بيانات الحساب لربط هوية الدخول المتحققة.':'Complete account details to bind your verified sign-in identity.');}}
  catch(error){apiMessage('loginMessage',error.message,true);}
 }else if(result==='success')toast(lang==='ar'?'تم تسجيل الدخول بنجاح.':'Signed in successfully.');
 else apiMessage('loginMessage',result==='existing'?(lang==='ar'?'ادخل بكلمة المرور الحالية ثم اربط مزوّد الدخول من الحساب.':'Sign in with your existing password, then link the sign-in provider from Account.'):(lang==='ar'?'تعذر التحقق من الدخول أو أُلغي. حاول مجددًا.':'Sign-in could not be verified or was cancelled. Try again.'),true);
}).catch(()=>{});

/* International calling codes from libphonenumber-js metadata (245 regions). */
const authCallingCodes={"AC":"247","AD":"376","AE":"971","AF":"93","AG":"1","AI":"1","AL":"355","AM":"374","AO":"244","AR":"54","AS":"1","AT":"43","AU":"61","AW":"297","AX":"358","AZ":"994","BA":"387","BB":"1","BD":"880","BE":"32","BF":"226","BG":"359","BH":"973","BI":"257","BJ":"229","BL":"590","BM":"1","BN":"673","BO":"591","BQ":"599","BR":"55","BS":"1","BT":"975","BW":"267","BY":"375","BZ":"501","CA":"1","CC":"61","CD":"243","CF":"236","CG":"242","CH":"41","CI":"225","CK":"682","CL":"56","CM":"237","CN":"86","CO":"57","CR":"506","CU":"53","CV":"238","CW":"599","CX":"61","CY":"357","CZ":"420","DE":"49","DJ":"253","DK":"45","DM":"1","DO":"1","DZ":"213","EC":"593","EE":"372","EG":"20","EH":"212","ER":"291","ES":"34","ET":"251","FI":"358","FJ":"679","FK":"500","FM":"691","FO":"298","FR":"33","GA":"241","GB":"44","GD":"1","GE":"995","GF":"594","GG":"44","GH":"233","GI":"350","GL":"299","GM":"220","GN":"224","GP":"590","GQ":"240","GR":"30","GT":"502","GU":"1","GW":"245","GY":"592","HK":"852","HN":"504","HR":"385","HT":"509","HU":"36","ID":"62","IE":"353","IL":"972","IM":"44","IN":"91","IO":"246","IQ":"964","IR":"98","IS":"354","IT":"39","JE":"44","JM":"1","JO":"962","JP":"81","KE":"254","KG":"996","KH":"855","KI":"686","KM":"269","KN":"1","KP":"850","KR":"82","KW":"965","KY":"1","KZ":"7","LA":"856","LB":"961","LC":"1","LI":"423","LK":"94","LR":"231","LS":"266","LT":"370","LU":"352","LV":"371","LY":"218","MA":"212","MC":"377","MD":"373","ME":"382","MF":"590","MG":"261","MH":"692","MK":"389","ML":"223","MM":"95","MN":"976","MO":"853","MP":"1","MQ":"596","MR":"222","MS":"1","MT":"356","MU":"230","MV":"960","MW":"265","MX":"52","MY":"60","MZ":"258","NA":"264","NC":"687","NE":"227","NF":"672","NG":"234","NI":"505","NL":"31","NO":"47","NP":"977","NR":"674","NU":"683","NZ":"64","OM":"968","PA":"507","PE":"51","PF":"689","PG":"675","PH":"63","PK":"92","PL":"48","PM":"508","PR":"1","PS":"970","PT":"351","PW":"680","PY":"595","QA":"974","RE":"262","RO":"40","RS":"381","RU":"7","RW":"250","SA":"966","SB":"677","SC":"248","SD":"249","SE":"46","SG":"65","SH":"290","SI":"386","SJ":"47","SK":"421","SL":"232","SM":"378","SN":"221","SO":"252","SR":"597","SS":"211","ST":"239","SV":"503","SX":"1","SY":"963","SZ":"268","TA":"290","TC":"1","TD":"235","TG":"228","TH":"66","TJ":"992","TK":"690","TL":"670","TM":"993","TN":"216","TO":"676","TR":"90","TT":"1","TV":"688","TW":"886","TZ":"255","UA":"380","UG":"256","US":"1","UY":"598","UZ":"998","VA":"39","VC":"1","VE":"58","VG":"1","VI":"1","VN":"84","VU":"678","WF":"681","WS":"685","XK":"383","YE":"967","YT":"262","ZA":"27","ZM":"260","ZW":"263"};
function refreshCallingCodes(){
 const select=$('#registerPostal'),chosen=select.selectedOptions[0]?.dataset.region||'YE';
 const names=new Intl.DisplayNames([lang],{type:'region'});
 const options=Object.entries(authCallingCodes).map(([region,code])=>({region,code,name:names.of(region)})).sort((a,b)=>a.name.localeCompare(b.name,lang));
 select.replaceChildren(...options.map(({region,code,name})=>{const option=new Option('+'+code+' · '+name,'+'+code);option.dataset.region=region;option.selected=region===chosen;return option;}));
}
Object.assign(copy.en,{callingCode:'Calling code'});Object.assign(copy.ar,{callingCode:'مفتاح الاتصال الدولي'});
const previousAuthPhonePrefs=applyPrefs;applyPrefs=function(){previousAuthPhonePrefs();refreshCallingCodes();};
function registrationPayload(){
 const number=value('registerPhone').replace(/[\s()-]/g,'');
 return {email:value('registerEmail'),password:$('#registerPassword').value,phone:number.startsWith('+')?number:value('registerPostal')+number,postal_code:value('registerPostal'),country_id:value('registerCountry')?Number(value('registerCountry')):null,region_id:value('registerRegion')?Number(value('registerRegion')):null,city_id:value('registerCity')?Number(value('registerCity')):null,...(value('registerUsername')?{username:value('registerUsername')}:{})};
}
applyPrefs();
