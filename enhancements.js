// Local Gateway enhancements. Loaded after app.js; it upgrades existing views with
// real backend data (client dashboard, GitHub connection, provider credentials, push)
// without altering the current layout or markup.
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
  if (connectButton) connectButton.onclick = function () { window.location = '/api/github/install'; };
  var disconnectButton = document.getElementById('disconnectGithubButton');
  if (disconnectButton) disconnectButton.onclick = async function () {
    try { await api('/api/github/disconnect', { method: 'POST' }); await loadProjects(); toast('GitHub disconnected'); }
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
    try { await api('/api/admin/users/' + id, { method: 'PATCH', body: JSON.stringify(payload) }); apiMessage('adminUserMessage', 'Saved'); await loadAdminUsersData(); }
    catch (error) { apiMessage('adminUserMessage', error.message, true); }
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
  async function loadAdminGithubAdmin() {
    var panel = document.getElementById('adminGithubPanel');
    try {
      var s = await api('/api/github/status');
      panel.replaceChildren(textElement('p', 'Configured: ' + (s.configured ? 'yes' : 'no') + ' · Connected: ' + (s.connected ? 'yes' : 'no') + (s.account_login ? (' · ' + s.account_login) : '')), textElement('p', 'This is a status placeholder. The real GitHub authorization, clone and push flow is a later phase.'));
    } catch (error) { panel.replaceChildren(textElement('p', error.message)); }
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

  var ADMIN_LOADERS = { overview: loadAdminOverview, projects: loadAdminProjects, workspaces: loadAdminWorkspaces, sessions: loadAdminSessions, users: loadAdminUsersData, plans: loadAdminPlans, billing: loadAdminBilling, reports: loadAdminReports, audit: async function () {}, health: loadAdminHealth, policy: loadAdminPolicy, github: loadAdminGithubAdmin, trial: loadAdminTrial, settings: async function () {}, security: async function () {}, account: loadAdminAccount };

  function setAdminView(name) {
    if (!['overview','users','plans','billing','reports','audit','health','policy','github','trial','settings','security','account'].includes(name)) name='overview';
    adminView = name;
    document.querySelectorAll('#adminNav [data-admin-view]').forEach(function (b) { b.classList.toggle('active', b.dataset.adminView === name); });
    document.querySelectorAll('#adminPage [data-admin-panel]').forEach(function (p) { p.classList.toggle('active', p.dataset.adminPanel === name); });
    var loader = ADMIN_LOADERS[name];
    if (loader) return loader();
  }

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

  async function loadAdminPolicy() {
    try {
      var policy = await api('/api/admin/policy');
      document.getElementById('policyProviders').value = (policy.allowed_providers || []).join(', ');
      document.getElementById('policyModels').value = (policy.allowed_models || []).join(', ');
      document.getElementById('policyTools').value = (policy.allowed_tools || []).join(', ');
      document.getElementById('policyApproval').checked = !!policy.require_tool_approval;
    } catch (error) { toast(error.message); }
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
    feed.scrollTop = feed.scrollHeight;
  }

  // The base client owns the sole SSE connection and durable replay cursor.
  window.renderWorkspaceEventLine = renderEventLine;

  Object.assign(copy.en, { clientNavTitle: 'Client', clientDashboard: 'Dashboard', clientProjects: 'Projects', clientSessions: 'Sessions', clientAi: 'OpenCode', clientAccount: 'Account / Profile', clientDashboardLead: 'Your trial, connections, projects and recent activity in one place.', clientRecentLabel: 'RECENT', clientRecentProjects: 'Projects and workspaces', adminNavTitle: 'Administration', adminConsole: 'Admin Console', adminOverview: 'Overview', adminUsers: 'Users', adminProjects: 'Projects', adminWorkspaces: 'Workspaces', adminSessions: 'Sessions', adminPlans: 'Plans & Offers', adminPolicy: 'AI / OpenCode Policy', adminGithub: 'GitHub', adminAudit: 'Audit / Activity', adminSettings: 'Platform Settings', adminPersonal: 'Personal account', adminOverviewLead: 'Real backend metrics only. Metrics without a real query show "Not available yet".', adminPlatformStatus: 'PLATFORM STATUS', adminIntegrations: 'Integrations', adminUsersLead: 'Real account records. Role, status and trial changes call the admin API.', adminActions: 'Actions', adminProjectsLead: 'Metadata only. Customer source code is never shown here.', adminWorkspacesLead: 'Real workspace metadata. The physical path is never exposed.', adminSessionsLead: 'Real OpenCode conversation metadata.', adminPlansLead: 'Published offers are read by the public landing page through the plans API.', adminPolicyLead: 'These settings persist and limit what clients can select. User API keys and OAuth credentials are never shown here.', adminBilling: 'Billing / Subscriptions', adminReports: 'Reports', adminHealth: 'Platform Logs / Health', adminGithubSettings: 'GitHub Integration Settings', adminTrial: 'Trial / Entitlement Settings', adminSecurity: 'Security', clientRecentSessionsTitle: 'Recent sessions', clientProjectsLead: 'Your projects and workspaces.', clientSessionsLead: 'Workspaces and their OpenCode sessions.', clientAiLead: 'Runtime, provider and tool status for your workspaces.', clientGithubLead: 'Connect your GitHub account, then choose a repository and branch.', clientBillingLead: "Your own subscription only. Other customers' billing is never shown here.", clientPlansTitle: 'Plans & offers', clientCancel: 'Cancel subscription', clientReactivate: 'Reactivate', clientRenew: 'Renew subscription', clientInvoicesTitle: 'Invoices & payments', clientAccountLead: 'Personal details and preferences.', clientPersonalInfo: 'Personal information', clientUsername: 'Username', clientEmail: 'Email', clientPhone: 'Phone', clientLocation: 'Location / postal code', clientPreferences: 'Language / theme', clientSecurityNote: 'Use Password & security to change your password, revoke sign-ins, or suspend your account.', clientSecurityLead: 'Session and account security.', clientSecurity: 'Password & Security', clientDashboardBadge: 'CLIENT DASHBOARD', adminConsoleBadge: 'ADMIN CONSOLE', adminBillingLead: 'Business finance view, separate from the client billing page.', adminReportsLead: 'Real platform counts. Revenue appears only when backed by real payment data.', aUsername: 'Username', aEmail: 'Email', aRole: 'Role', aStatus: 'Status', aTrialRemaining: 'Trial remaining', aTrialEnd: 'Trial end', aPlan: 'Plan', aLastLogin: 'Last login', aCreated: 'Created', aProjectsWorkspaces: 'Projects / Workspaces', aCode: 'Code', aName: 'Name', aPrice: 'Price (USD)', aDays: 'Duration', aActive: 'Active', aAddPlan: 'Add plan', aSubscriptionsSmall: 'SUBSCRIPTIONS', aSubsTitle: 'Subscriptions across users', aOwner: 'Owner', aStarted: 'Started', aPeriodEnd: 'Period end', aCancelled: 'Cancelled', aTransactionsSmall: 'TRANSACTIONS', aTransactions: 'Payment transactions', aRevenueSmall: 'REVENUE', aRevenue: 'Revenue', aNay: 'Not available yet.', aAuditLogging: 'Audit logging is not available yet.', aHealthLead: 'Runtime health from the real backend.', aLoading: 'Loading…', aEnabledProviders: 'Enabled providers (comma separated)', aAllowedModels: 'Allowed models (comma separated)', aEnabledTools: 'Enabled tools / capabilities (comma separated)', aRequireApproval: 'Require approval before running tools', aSavePolicy: 'Save policy', aGithubLead: 'Connection status. The real GitHub integration is a later phase.', aLoadingStatus: 'Loading status…', aTrialLead: 'Trial entitlement overview. Editing trial defaults is not available yet.', aPlatformSettings: 'Platform settings are not available yet.', aAdminSecurityNotAvail: 'Admin security settings are not available yet.', aPersonalLead: 'Your own account. Administrative controls are on the other pages.' });
  Object.assign(copy.ar, { clientNavTitle: 'العميل', clientDashboard: 'لوحة المعلومات', clientProjects: 'المشاريع', clientSessions: 'الجلسات', clientAi: 'OpenCode', clientAccount: 'الحساب / الملف', clientDashboardLead: 'تجربتك واتصالاتك ومشاريعك ونشاطك الأخير في مكان واحد.', clientRecentLabel: 'الأحدث', clientRecentProjects: 'المشاريع ومساحات العمل', adminNavTitle: 'الإدارة', adminConsole: 'لوحة الإدارة', adminOverview: 'نظرة عامة', adminUsers: 'المستخدمون', adminProjects: 'المشاريع', adminWorkspaces: 'مساحات العمل', adminSessions: 'الجلسات', adminPlans: 'الخطط والعروض', adminPolicy: 'سياسة الذكاء / OpenCode', adminGithub: 'GitHub', adminAudit: 'التدقيق / النشاط', adminSettings: 'إعدادات المنصة', adminPersonal: 'الحساب الشخصي', adminOverviewLead: 'مؤشرات حقيقية فقط. ما لا يوجد له استعلام حقيقي يظهر "غير متاح بعد".', adminPlatformStatus: 'حالة المنصة', adminIntegrations: 'التكاملات', adminUsersLead: 'سجلات حقيقية. تغيير الدور والحالة والتجربة يستدعي واجهة الإدارة.', adminActions: 'إجراءات', adminProjectsLead: 'بيانات وصفية فقط. لا يظهر كود العميل هنا.', adminWorkspacesLead: 'بيانات مساحة العمل الحقيقية. لا يُكشف المسار الفيزيائي.', adminSessionsLead: 'بيانات محادثات OpenCode الحقيقية.', adminPlansLead: 'تُقرأ العروض المنشورة في صفحة الهبوط عبر واجهة الخطط.', adminPolicyLead: 'تُحفظ هذه الإعدادات وتحدّ من اختيارات العملاء. لا تظهر مفاتيح المستخدمين أو رموز OAuth هنا.', adminBilling: 'الفوترة / الاشتراكات', adminReports: 'التقارير', adminHealth: 'سجلات المنصة / الحالة', adminGithubSettings: 'إعدادات تكامل GitHub', adminTrial: 'إعدادات التجربة / الاستحقاق', adminSecurity: 'الأمان', clientRecentSessionsTitle: 'الجلسات الأخيرة', clientProjectsLead: 'مشاريعك ومساحات العمل.', clientSessionsLead: 'مساحات العمل وجلسات OpenCode الخاصة بها.', clientAiLead: 'حالة وقت التشغيل والمزوّد والأدوات لمساحات عملك.', clientGithubLead: 'حالة الاتصال. التدفق الحقيقي للترخيص مرحلة لاحقة.', clientBillingLead: 'اشتراكك فقط. لا تظهر فوترة العملاء الآخرين هنا.', clientPlansTitle: 'الخطط والعروض', clientCancel: 'إلغاء الاشتراك', clientReactivate: 'إعادة التفعيل', clientRenew: 'تجديد الاشتراك', clientInvoicesTitle: 'الفواتير والمدفوعات', clientAccountLead: 'بياناتك وتفضيلاتك. لوحة المعلومات صفحة منفصلة.', clientPersonalInfo: 'المعلومات الشخصية', clientUsername: 'اسم المستخدم', clientEmail: 'البريد الإلكتروني', clientPhone: 'الهاتف', clientLocation: 'الموقع / الرمز البريدي', clientPreferences: 'اللغة / المظهر', clientSecurityNote: 'تغيير كلمة المرور وإدارة الأجهزة غير متاحين بعد. جلستك تستخدم ملف تعريف ارتباط HttpOnly وSameSite=Strict.', clientSecurityLead: 'أمان الجلسة والحساب.', clientSecurity: 'كلمة المرور والأمان', clientDashboardBadge: 'لوحة العميل', adminConsoleBadge: 'لوحة الإدارة', adminBillingLead: 'عرض مالي للعمل، منفصل عن صفحة فوترة العميل.', adminReportsLead: 'مؤشرات المنصة الحقيقية. تظهر الإيرادات فقط عند توفر بيانات دفع حقيقية.', aUsername: 'اسم المستخدم', aEmail: 'البريد الإلكتروني', aRole: 'الدور', aStatus: 'الحالة', aTrialRemaining: 'المتبقي من التجربة', aTrialEnd: 'نهاية التجربة', aPlan: 'الخطة', aLastLogin: 'آخر دخول', aCreated: 'تاريخ الإنشاء', aProjectsWorkspaces: 'المشاريع / مساحات العمل', aCode: 'الرمز', aName: 'الاسم', aPrice: 'السعر (سنتات)', aDays: 'الأيام', aActive: 'نشط', aAddPlan: 'إضافة خطة', aSubscriptionsSmall: 'الاشتراكات', aSubsTitle: 'الاشتراكات عبر المستخدمين', aOwner: 'المالك', aStarted: 'البدء', aPeriodEnd: 'نهاية الفترة', aCancelled: 'ملغى', aTransactionsSmall: 'المعاملات', aTransactions: 'معاملات الدفع', aRevenueSmall: 'الإيرادات', aRevenue: 'الإيرادات', aNay: 'غير متاح بعد.', aAuditLogging: 'سجل التدقيق غير متاح بعد.', aHealthLead: 'حالة وقت التشغيل من الخلفية الحقيقية.', aLoading: 'جارٍ التحميل…', aEnabledProviders: 'المزوّدون المفعّلون (مفصولة بفواصل)', aAllowedModels: 'النماذج المسموحة (مفصولة بفواصل)', aEnabledTools: 'الأدوات المفعّلة (مفصولة بفواصل)', aRequireApproval: 'تتطلب الموافقة قبل تشغيل الأدوات', aSavePolicy: 'حفظ السياسة', aGithubLead: 'حالة الاتصال. تكامل GitHub الحقيقي مرحلة لاحقة.', aLoadingStatus: 'جارٍ تحميل الحالة…', aTrialLead: 'نظرة عامة على استحقاق التجربة. تعديل مدة التجربة الافتراضية غير متاح بعد.', aPlatformSettings: 'إعدادات المنصة غير متاحة بعد.', aAdminSecurityNotAvail: 'إعدادات أمان الإدارة غير متاحة بعد.', aPersonalLead: 'حسابك الخاص. عناصر التحكم الإدارية في الصفحات الأخرى.' });
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

  // --- Routing: after auth, customer -> Client Dashboard; admin/owner -> Admin Console ---
  protectedPages.add('clientPage');
  function homeFor(user) { return (user && (user.role === 'admin' || user.role === 'owner')) ? 'adminPage' : 'workspaceHomePage'; }
  async function routeHome() { clientView='dashboard'; adminView='overview'; await page(homeFor(currentUser));if(!['admin','owner'].includes(currentUser?.role)&&window.pendingCheckoutPlan){const plan=window.pendingCheckoutPlan;window.pendingCheckoutPlan=null;await window.openClientView('billing');await window.beginCheckout(plan);} }
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
    var p = data.profile || {}, github = data.github || {}, runtime = data.runtime || {};
    box.append(clientCard('Account status', p.status || '—', p.plan ? ('Plan: ' + p.plan) : 'No plan assigned'));
    box.append(clientCard('Trial', (typeof p.trial_remaining_days === 'number' ? p.trial_remaining_days + ' days remaining' : '—'), 'Trial ' + new Date(p.trial_started_at).toLocaleDateString('en-GB') + ' → ends ' + new Date(p.trial_ends_at).toLocaleDateString('en-GB')));
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
      const end=data.access.reason==='subscription'?data.subscription.current_period_end:data.trial.ends_at;
      const days=end?Math.max(0,Math.ceil((new Date(end)-Date.now())/86400000)):0;
      summary.append(billingCard(tr('Current plan','الخطة الحالية'),data.access.reason==='subscription'?planName:tr('10-day trial','تجربة عشرة أيام')));
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
  var billingCancel = document.getElementById('billingCancel');
  if (billingCancel) billingCancel.onclick = async function () { try { await api('/api/billing/subscription/cancel', { method: 'POST' }); apiMessage('billingMessage', 'Subscription cancelled'); await loadClientBilling(); } catch (error) { apiMessage('billingMessage', error.message, true); } };
  var billingReactivate = document.getElementById('billingReactivate');
  if (billingReactivate) billingReactivate.onclick = async function () { try { await api('/api/billing/subscription/reactivate', { method: 'POST' }); apiMessage('billingMessage', 'Reactivated into pending payment'); await loadClientBilling(); } catch (error) { apiMessage('billingMessage', error.message, true); } };
  var billingRenew = document.getElementById('billingRenew');
  if (billingRenew) billingRenew.onclick = async function () { try { const state=await api('/api/billing/subscription');const plan=state.plan||state.selected_plan;if(plan)await window.beginCheckout(plan.id);else document.getElementById('billingPlans').scrollIntoView({block:'center',behavior:'smooth'}); } catch (error) { apiMessage('billingMessage', error.message, true); } };

  // Re-route the auth completion handlers so Account is not the landing page.
  $('#loginSubmit').onclick = async function () {
    const button = $('#loginSubmit'); button.disabled = true;
    try {
      renderProfile(await api('/api/auth/login', { method: 'POST', body: JSON.stringify({ identity: value('loginIdentity'), password: $('#loginPassword').value }) }));
      $('#loginPassword').value = '';
      await routeHome();
    } catch (error) { apiMessage('loginMessage', error.message, true); }
    finally { button.disabled = false; }
  };
  $('#registerSubmit').onclick = async function () {
    if (value('registerUsername').length < 6) { apiMessage('registerMessage', t('usernameHint'), true); return; }
    const password = $('#registerPassword').value;
    if (password.length < 8 || !/[0-9]/.test(password) || ![...password].some(function (c) { return passwordSymbols.includes(c); })) { apiMessage('registerMessage', t('passwordHint'), true); return; }
    const button = $('#registerSubmit'); button.disabled = true;
    try {
      const prefs = { preferred_language: lang, preferred_theme: dark ? 'dark' : 'light' };
      await api('/api/auth/register', { method: 'POST', body: JSON.stringify({ username: value('registerUsername'), email: value('registerEmail'), password: $('#registerPassword').value, phone: value('registerPhone'), postal_code: value('registerPostal'), country_id: Number(value('registerCountry')), region_id: value('registerRegion') ? Number(value('registerRegion')) : null, city_id: value('registerCity') ? Number(value('registerCity')) : null }) });
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
      history.replaceState(null, '', location.pathname);
      if (flag === 'connected' && currentUser) { toast('GitHub connected'); await page('accountPage'); return; }
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
    var p = data.profile || {}, gh = data.github || {}, rt = data.runtime || {};
    var box = document.getElementById('clientSummary'); if (box) {
      box.replaceChildren(); box.className = 'card-grid';
      var items = [
        ['#icon-file', tr('Plan / Trial', 'الخطة / التجربة'), p.plan || tr('No plan assigned', 'لا توجد خطة'), tr('Trial', 'تجربة') + ' · ' + (typeof p.trial_remaining_days === 'number' ? p.trial_remaining_days + ' ' + tr('days', 'يوم') : '—')],
        ['#icon-clock', tr('Days remaining', 'الأيام المتبقية'), (typeof p.trial_remaining_days === 'number' ? p.trial_remaining_days : '—'), tr('Ends', 'تنتهي') + ' ' + fmtDate(p.trial_ends_at)],
        ['#icon-opencode', tr('OpenCode', 'OpenCode'), rt.mode === 'local' ? tr('Local runtime', 'تشغيل محلي') : tr('Runtime disabled', 'التشغيل معطّل'), tr('Mode', 'الوضع') + ': ' + (rt.mode || 'disabled')],
        ['#icon-github', tr('GitHub', 'GitHub'), gh.connected ? tr('Connected', 'متصل') : tr('Not connected', 'غير متصل'), gh.connected ? (gh.account_login || '') : (gh.configured ? tr('Ready to connect', 'جاهز للربط') : tr('Not configured', 'غير مكوّن'))],
        ['#icon-folder', tr('Projects', 'المشاريع'), (data.counts ? data.counts.projects : 0), tr('Workspaces', 'مساحات العمل') + ': ' + (data.counts ? data.counts.workspaces : 0)],
        ['#icon-chat', tr('Sessions', 'الجلسات'), (data.counts ? data.counts.sessions : 0), tr('Total', 'الإجمالي')]
      ];
      items.forEach(function (it) { var card = textElement('div', '', 'summary-card'); card.append(scIcon(it[0])); var t = textElement('div', ''); t.append(textElement('small', it[1])); t.append(textElement('b', it[2])); var sm = textElement('small', it[3]); t.append(sm); card.append(t); box.append(card); });
    }
    var qa = document.getElementById('clientQuickActions');
    if (!qa) { qa = textElement('div', '', 'quick-actions'); qa.id = 'clientQuickActions';
      [['#icon-plus', tr('New project', 'مشروع جديد'), function () { page('onboarding'); }], ['#icon-folder', tr('Open workspace', 'فتح مساحة عمل'), function () { setClientView('projects'); }], ['#icon-github', tr('Connect GitHub', 'ربط GitHub'), function () { window.location = '/api/github/install'; }], ['#icon-opencode', tr('Configure AI provider', 'تهيئة مزوّد الذكاء'), function () { setClientView('ai'); }]].forEach(function (q) { var btn = textElement('button', '', 'button ghost'); btn.appendChild(navIcon(q[0])); btn.appendChild(textElement('span', q[1])); btn.onclick = q[2]; qa.append(btn); });
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
      if (s.connected) {
        panel.replaceChildren();
        panel.append(textElement('h3', tr('GitHub connected', 'GitHub متصل')));
        panel.append(textElement('p', (s.account_login || '') + ' · ' + (s.target_type || 'User')));
        var disc = textElement('button', tr('Disconnect', 'فصل'), 'button ghost'); disc.onclick = async function () { try { await api('/api/github/disconnect', { method: 'POST' }); toast(tr('Disconnected', 'تم الفصل')); await loadClientGithub(); } catch (e) { toast(e.message); } }; panel.append(disc);
      } else {
        var cp = textElement('div', '', 'connect-panel');
        var ic = textElement('div', '', 'cp-icon'); ic.appendChild(navIcon('#icon-github')); cp.append(ic);
        cp.append(textElement('h3', tr('Connect GitHub', 'ربط GitHub')));
        cp.append(textElement('p', tr('Link your GitHub account to clone repositories and push changes. Tokens stay on the server and are never stored in your browser.', 'اربط حسابك على GitHub لاستنساخ المستودعات وإرسال التغييرات. تبقى الرموز على الخادم ولا تُخزَّن في متصفحك.')));
        var btn = textElement('button', tr('Connect GitHub', 'ربط GitHub'), 'button');
        btn.onclick = function () { window.location = '/api/github/install'; };
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

  async function loadClientAccount() {
    var user = await api('/api/profile');
    renderProfile(user);
    var box = document.getElementById('accountSummary'); if (box) {
      box.replaceChildren();
      [['#icon-user', tr('Account status', 'حالة الحساب'), user.status, user.status === 'active' ? 'good' : 'danger'], ['#icon-shield', tr('Role', 'الدور'), user.role, 'muted']].forEach(function (r) { var c = textElement('div', '', 'summary-card'); c.append(scIcon(r[0])); var t = textElement('div', ''); t.append(textElement('small', r[1])); t.append(textElement('b', r[2])); c.append(t); c.append(badge(r[2], r[3])); box.append(c); });
    }
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
          ['icon-trash', tr('Delete is not available yet', 'الحذف غير متاح بعد'), null, true],
        ]);
      },
    });
  }

  function openUserModal(u, editable) {
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
    trialIn.type = 'number'; trialIn.min = '0'; trialIn.max = '3650'; trialIn.value = String(u.trial_remaining_days);
    var body = el('div');
    body.append(
      labeled(tr('Role', 'الدور'), roleSel),
      labeled(tr('Status', 'الحالة'), statusSel),
      labeled(tr('Extend trial by days', 'تمديد التجربة بالأيام'), trialIn)
    );
    var save = el('button', 'button small', tr('Save', 'حفظ'));
    save.type = 'button';
    save.onclick = async function () {
      save.disabled = true;
      var patch={status:statusSel.value,trial_days:Number(trialIn.value)};
      if(currentUser.role==='owner' && roleSel.value!==u.role)patch.role=roleSel.value;
      await adminPatchUser(u.id,patch);
      save.disabled = false;
      modal.close();
    };
    openModal(tr('Edit user', 'تعديل المستخدم') + ' · ' + u.username, body, [save]);
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
          ['icon-trash', tr('Delete is not available yet', 'الحذف غير متاح بعد'), null, true],
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
    if (host && !host.querySelector('[data-signout]')) host.append(signOutRow());
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
  CLIENT_LOADERS.account=async function(){await accountLoader();const host=managementHost(document.querySelector('[data-client-panel="account"]'),'clientAccountActivity');await window.renderManagement(host,'logs');await window.renderManagement(managementHost(document.querySelector('[data-client-panel="account"]'),'clientAccountLifecycle'),'lifecycle');};
  const adminBillingLoader=ADMIN_LOADERS.billing;
  ADMIN_LOADERS.billing=async function(){await adminBillingLoader();await window.renderManagement(managementHost(document.querySelector('[data-admin-panel="billing"]'),'adminBillingMethods'),'billing',true);};
  ADMIN_LOADERS.audit=function(){return window.renderManagement(document.querySelector('[data-admin-panel="audit"]'),'logs',true)};
  ADMIN_LOADERS.github=function(){return window.renderManagement(document.querySelector('[data-admin-panel="github"]'),'connections',true)};
  ADMIN_LOADERS.settings=function(){return window.renderManagement(document.querySelector('[data-admin-panel="settings"]'),'locations',true)};
  ADMIN_LOADERS.security=function(){return window.renderManagement(document.querySelector('[data-admin-panel="security"]'),'security')};
  const adminAccountLoader=ADMIN_LOADERS.account;
  ADMIN_LOADERS.account=async function(){await adminAccountLoader();await window.renderManagement(managementHost(document.querySelector('[data-admin-panel="account"]'),'adminAccountActivity'),'logs');};
  window.openClientView=async function(name){clientView=name;await page('clientPage');};
  window.openAdminView=async function(name){if(['admin','owner'].includes(currentUser?.role))adminView=name;await page('adminPage');};
})();
