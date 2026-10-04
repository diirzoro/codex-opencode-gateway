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
    button.disabled = !(state.push_available && state.head);
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

  loadAdminUsers = async function () {
    try {
      var overview = await api('/api/admin/overview');
      $$('[data-overview]').forEach(function (el) { el.textContent = overview.users[el.dataset.overview] ?? '—'; });
      $$('[data-admin]').forEach(function (el) {
        var value = overview;
        el.dataset.admin.split('.').forEach(function (key) { value = value ? value[key] : undefined; });
        el.textContent = (value === undefined || value === null) ? '—' : value;
      });
    } catch (error) { toast(error.message); }
    var body = document.getElementById('adminUsersBody');
    body.replaceChildren();
    try {
      for (const user of await api('/api/admin/users')) {
        var row = document.createElement('tr');
        var planCell = textElement('td', user.plan || 'Not assigned');
        var cells = [user.username + ' · ' + user.email, user.phone, [user.country, user.region, user.city].filter(Boolean).join(' · '), user.trial_remaining_days + ' days'];
        cells.forEach(function (text) { row.append(textElement('td', text)); });
        row.append(planCell);
        ['Not available yet', user.trial_remaining_days + ' days', 'Not available yet', '—', user.last_login_at || 'Never', user.status].forEach(function (text) { row.append(textElement('td', text)); });
        body.append(row);
      }
    } catch (error) {
      var row = document.createElement('tr');
      var cell = textElement('td', error.message);
      cell.colSpan = 11;
      row.append(cell);
      body.append(row);
    }
    loadAdminPlans();
    loadAdminPolicy();
  };

  async function connectProviderCredential() {
    if (!activeWorkspace) { toast('Open a workspace first'); return; }
    var providerId = prompt('Provider id (for example openai or anthropic)');
    if (!providerId) return;
    var apiKey = prompt('API key. It is sent to the server only and never kept in the browser.');
    if (!apiKey) return;
    try {
      var result = await api('/api/workspaces/' + activeWorkspace.id + '/providers/' + encodeURIComponent(providerId) + '/credentials', { method: 'POST', body: JSON.stringify({ api_key: apiKey }) });
      toast('Connected ' + result.provider_id + ' · key ending ' + result.last4);
    } catch (error) { toast(error.message); }
  }

  function ensureProviderButton() {
    var runtimeStatus = document.getElementById('runtimeStatus');
    if (!runtimeStatus || document.getElementById('manageProviders')) return;
    var button = textElement('button', 'Connect AI provider', 'button ghost small');
    button.id = 'manageProviders';
    button.type = 'button';
    button.onclick = connectProviderCredential;
    runtimeStatus.parentNode.insertBefore(button, runtimeStatus.nextSibling);
  }

  // --- Phase 1: real pricing, trial dates, admin plans/policy, chat controls ---
  function money(cents) { return '$' + (cents / 100).toFixed(cents % 100 ? 2 : 0); }

  async function renderPricing() {
    var cards = document.getElementById('pricingCards');
    if (!cards) return;
    try {
      var plans = await api('/api/plans');
      cards.replaceChildren();
      var parts = [];
      plans.forEach(function (plan) {
        var card = textElement('div', '', 'price-card');
        card.append(textElement('b', money(plan.price_cents)));
        card.append(textElement('span', plan.name));
        card.append(textElement('small', plan.duration_days === 30 ? '/ month' : 'for ' + plan.duration_days + ' days'));
        cards.append(card);
        parts.push(money(plan.price_cents) + ' / ' + plan.name);
      });
      var summary = document.getElementById('pricingSummary');
      if (summary && parts.length) summary.textContent = parts.join(' · ');
    } catch (error) { /* Leave the static fallback prices when no catalog is available. */ }
  }

  renderProfile = function (user) {
    currentUser = user; updateNavigation();
    document.getElementById('profileStatus').textContent = (lang === 'ar' ? ({ active: 'نشط', suspended: 'موقوف' }[user.status] || user.status) : user.status);
    document.getElementById('profileTrial').textContent = (typeof user.trial_remaining_days === 'number') ? (user.trial_remaining_days + ' trial days remaining') : '—';
    var dates = document.getElementById('profileTrialDates');
    if (dates) dates.textContent = 'Trial ' + new Date(user.trial_started_at).toLocaleDateString('en-GB') + ' → ends ' + new Date(user.trial_ends_at).toLocaleDateString('en-GB');
    for (const [id, text] of Object.entries({ profileUsername: user.username, profileEmail: user.email, profilePhone: user.phone, profileLocation: [user.country, user.region, user.city, user.postal_code].filter(Boolean).join(' · '), profilePreferences: user.preferred_language + ' · ' + user.preferred_theme })) {
      var el = document.getElementById(id); if (el) el.firstChild.textContent = text;
    }
    lang = user.preferred_language; dark = user.preferred_theme === 'dark'; applyPrefs();
  };

  async function loadAdminPlans() {
    var body = document.getElementById('adminPlansBody');
    if (!body) return;
    try {
      var plans = await api('/api/admin/plans');
      body.replaceChildren();
      plans.forEach(function (plan) {
        var row = document.createElement('tr');
        [plan.code, plan.name, String(plan.price_cents), String(plan.duration_days), plan.active ? 'yes' : 'no'].forEach(function (text) { row.append(textElement('td', text)); });
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
      apiMessage('adminPlanMessage', 'Plan created'); planForm.reset(); await loadAdminPlans();
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

  startEvents = function () {
    if (!activeSession) return;
    eventStream = new EventSource('/api/sessions/' + activeSession.id + '/events');
    var kinds = ['submitted', 'analyzing', 'reading_files', 'editing', 'running_command', 'running_tests', 'waiting_approval', 'approval_decision', 'failed', 'completed', 'cancelled'];
    kinds.forEach(function (kind) {
      eventStream.addEventListener(kind, function () {
        document.getElementById('runtimeStatus').textContent = kind;
        if (['failed', 'completed', 'cancelled'].indexOf(kind) >= 0) {
          document.getElementById('stopAgent').disabled = true;
          refreshMessages();
          refreshGit().catch(function (e) { toast(e.message); });
          document.getElementById('sendMessage').disabled = !value('modelSelect');
        }
        renderEventLine(kind);
      });
    });
    eventStream.onerror = function () { document.getElementById('runtimeStatus').textContent = 'Reconnecting to event stream'; };
  };

  wireChatControls();
  renderPricing();

  authReady.then(async function () {
    var flag = new URLSearchParams(location.search).get('github');
    if (flag) {
      history.replaceState(null, '', location.pathname);
      if (flag === 'connected' && currentUser) { toast('GitHub connected'); await page('accountPage'); }
      else if (flag === 'error') { toast('GitHub connection was not completed'); }
    }
    if (currentUser) {
      try {
        var status = await api('/api/github/status');
        var gh = document.getElementById('chatGithub');
        if (gh) gh.title = status.connected ? ('GitHub connected as ' + (status.account_login || '')) : (status.configured ? 'GitHub not connected' : 'GitHub integration not configured');
      } catch (error) { /* leave the truthful default title */ }
    }
  });
})();
