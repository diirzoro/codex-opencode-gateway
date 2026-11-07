/* Admin Billing: prepare Stripe and Cryptomus securely; no payment processing. */
(() => {
  const tr = (en, ar) => (typeof lang !== 'undefined' && lang === 'ar') ? ar : en;
  const billingTab = document.querySelector('#adminNav [data-admin-view="billing"]');
  const billingPanel = document.querySelector('[data-admin-panel="billing"]');
  if (!billingTab || !billingPanel) return;

  const host = document.createElement('section');
  host.id = 'adminPaymentGatewaySettings';
  host.className = 'payment-gateway-settings';
  billingPanel.prepend(host);
  let requestSequence = 0;

  const el = (tag, value, className) => {
    const element = document.createElement(tag);
    if (value) element.textContent = value;
    if (className) element.className = className;
    return element;
  };
  const field = (form, label, name, value, secret = false) => {
    const wrap = el('label', label);
    const item = el('input');
    item.name = name;
    item.type = secret ? 'password' : 'text';
    item.autocomplete = 'off';
    item.maxLength = secret ? 1024 : 512;
    item.value = secret ? '' : String(value || '');
    if (secret) item.placeholder = tr('Blank keeps saved secret', 'اتركه فارغًا للاحتفاظ بالمفتاح المحفوظ');
    wrap.append(item);
    form.append(wrap);
    return item;
  };

  async function loadGateways() {
    if (!['admin','owner'].includes(typeof currentUser === 'undefined' ? '' : currentUser?.role)) return;
    const sequence = ++requestSequence;
    host.replaceChildren(el('h2', tr('Stripe and Cryptomus connections', 'إعدادات Stripe وCryptomus')),
      el('p', tr('Configuration only. No checkout, charges, webhook processing, or payouts are enabled.',
               'هذه إعدادات تمهيدية فقط. لم يُفعّل التحصيل أو معالجة Webhook أو السحب.')));
    let data;
    try {
      data = await api('/api/admin/payment-gateways');
    } catch (error) {
      if (sequence === requestSequence) host.append(el('p', error.message));
      return;
    }
    if (sequence !== requestSequence) return;
    for (const provider of ['stripe','cryptomus']) {
      const current = data.providers[provider] || {};
      const stripe = provider === 'stripe';
      const card = el('section', '', 'manage-card');
      card.append(el('h3', stripe ? 'Stripe' : 'Cryptomus'));
      const status = current.configured ?
        tr('Draft saved; payment connection has not been verified.',
           'الإعدادات محفوظة كمسودة؛ لم يتم التحقق من الربط بالدفع.') :
        tr('Not configured yet.', 'لم تتم التهيئة بعد.');
      card.append(el('p', status));
      card.append(el('p', tr('Planned webhook (not active): ', 'عنوان Webhook المستقبلي (غير مفعّل): ') +
        (current.webhook_url_planned || '—')));
      const form = el('form', '', 'manage-form');
      form.autocomplete = 'off';
      if (stripe) {
        const modeLabel = el('label', tr('Stripe mode', 'بيئة Stripe'));
        const mode = el('select');
        mode.name = 'mode';
        for (const value of ['test','live']) {
          const option = el('option', value === 'test' ?
            tr('Test / Sandbox','تجريبي') : tr('Live / Real','حقيقي'));
          option.value = value;
          mode.append(option);
        }
        mode.value = current.mode || 'test';
        modeLabel.append(mode);
        form.append(modeLabel);
        field(form, tr('Publishable key (pk_test_ / pk_live_)', 'المفتاح العام (pk_test_ / pk_live_)'),
          'publishable_key', current.publishable_key);
        field(form, tr('Secret or restricted API key', 'مفتاح API السري أو المحدود الصلاحيات'),
          'secret_key', '', true);
        field(form, tr('Webhook signing secret (whsec_)', 'مفتاح التوقيع Webhook (whsec_)'),
          'webhook_secret', '', true);
        card.append(el('p', tr('API key saved: ', 'مفتاح API محفوظ: ') +
          (current.secret_key_configured ? tr('Yes','نعم') : tr('No','لا')) +
          tr(' · Webhook secret saved: ', ' · مفتاح Webhook محفوظ: ') +
          (current.webhook_secret_configured ? tr('Yes','نعم') : tr('No','لا'))));
      } else {
        field(form, tr('Merchant ID (UUID)', 'معرّف التاجر Merchant ID'),
          'merchant_id', current.merchant_id);
        field(form, tr('Payment API key', 'مفتاح API لاستلام المدفوعات'),
          'payment_api_key', '', true);
        field(form, tr('Payout API key (optional, not active)', 'مفتاح API للسحب (اختياري وغير مفعّل)'),
          'payout_api_key', '', true);
        card.append(el('p', tr('Payment key saved: ', 'مفتاح الاستلام محفوظ: ') +
          (current.payment_api_key_configured ? tr('Yes','نعم') : tr('No','لا')) +
          tr(' · Payout key saved: ', ' · مفتاح السحب محفوظ: ') +
          (current.payout_api_key_configured ? tr('Yes','نعم') : tr('No','لا'))));
      }
      const submit = el('button', tr('Save encrypted settings', 'حفظ الإعدادات المشفّرة'), 'button');
      submit.type = 'submit';
      submit.disabled = !current.settings_schema_ready || !current.credential_storage_ready;
      form.append(submit);
      const note = el('p', submit.disabled ?
        tr('Database migration 0031 and a valid encryption key are required.',
           'يلزم تنفيذ تحديث قاعدة البيانات 0031 وتوفر مفتاح التشفير.') :
        tr('Secrets are stored encrypted and never displayed again.',
           'ستُحفظ المفاتيح مشفّرة ولن تُعرض مرة أخرى.'));
      card.append(form,note);
      form.addEventListener('submit', async (event) => {
        event.preventDefault();
        submit.disabled = true;
        const values = Object.fromEntries(new FormData(form));
        for (const key of (stripe ? ['secret_key','webhook_secret'] : ['payment_api_key','payout_api_key'])) {
          if (!values[key]) delete values[key];
        }
        if (!stripe && !values.merchant_id) values.merchant_id = null;
        try {
          await api('/api/admin/payment-gateways/' + provider, {
            method:'PUT', body:JSON.stringify(values)
          });
          form.querySelectorAll('input[type="password"]').forEach(input => { input.value = ''; });
          await loadGateways();
        } catch (error) {
          note.textContent = error.message;
          submit.disabled = false;
        }
      });
      host.append(card);
    }
  }
  billingTab.addEventListener('click', () => {
    loadGateways().catch(() => {});
  });
  if (billingPanel.classList.contains('active')) loadGateways().catch(() => {});
})();
