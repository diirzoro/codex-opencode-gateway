# Admin Center — Service Providers and Feature Controls (TEST-first)

## Architecture and scope
Extend the EXISTING admin dashboard and Python control plane; do not create any new background AI services, agents, email execution engines, or billing engines. OpenCode Native remains the only AI executor. Maintain multi-user access with admin-only configuration and account-specific access where needed.

Current implementation evidence (updates branch, 2026-10-25):
- `backend/app/services/email_verification.py` already delivers verification links via STARTTLS SMTP.
- `backend/app/routes/auth.py` implements registration, verification and resend.
- `backend/app/routes/admin.py` already provides role-gated admin routes, plans, subscribers, policies and catalog maintenance.
- `backend/app/models/platform.py` provides Plan/Subscription/PaymentOrder/PlatformPolicy.
- Resend DNS verified for `opencode-gateway.codes` from owner screenshots; credentials and end-to-end delivery not yet verified.
- `/home/tahir/opencode-gateway-test/.env`, database, LIVE, OS configuration and the shared OpenCode installation are protected from routine deployment.

## Admin navigation
Introduce a clearly grouped section **Services & Integrations / الخدمات والتكاملات** with two tabs:

### Tab 1 — Providers / إعدادات المزوّدين
Admin may choose the *role* (transactional email, payment processor, subscription billing, future SMS) and a supported adapter. Forms for email:
- Provider selector: Resend SMTP, Generic SMTP, and additional connectors ONLY after compatible provider API integration exists.
- Display name, sender name/email, SMTP host/port, TLS security, username, secret/password field (write-only), test connection/send button, status, last successful test and errors (sanitized).
- Secrets are NEVER returned to browser after save. Show only `configured: true/false`; allow explicit rotate/delete with confirmation.
- On switching email provider, preserve old encrypted configuration for rollback if policy permits, but only one active configuration at once.
- For Resend reuse existing `email_verification.send_link` SMTP path; no Resend-specific queue/proxy. Defaults: `smtp.resend.com`, port 587, `resend` user; key supplied later; sender must belong to verified domain.
- Disallow arbitrary hostnames/URLs under user-configurable SMTP settings without SSRF protections. Require approved, verified hostname/IP policy, secure TLS, bounded timeouts and server-side validation.
- Provider test sends to admin-controlled verified test inbox; never send a live token in a generic test. Rate limit requests.
- Payment providers: display existing integration status; allow selecting supported implementation only; never treat a checkbox as sufficient to activate a nonexistent payment API. Keep payment credential ownership/secrets protected and require sandbox proof before LIVE.

### Tab 2 — Services / تفعيل الخدمات
Use compact, accessible toggles with labels, description, status and prerequisites. Distinguish three states: `enabled`, `disabled`, `unavailable/unconfigured`. Defaults reflect owner's business preference:
- Email verification on new account creation: default enabled (secure/fail-closed when delivery unavailable).
- Password reset: default enabled as a policy preference, but action remains unavailable until secure reset token delivery and flow are operational and tested; do NOT falsely enable a currently unfinished feature.
- Registration welcome email: optional, off by default.
- Account approaching expiry: optional, off by default until an existing eligible notifier/scheduler is integrated.
- Account/subscription expired: optional, off by default until notifier exists.
- Account suspended / closed notification: optional, off by default until notifier exists; authorization for suspension remains independent of email delivery.
- Low account credit/quota: optional; must not invent billing/quota thresholds, enable only when source-of-truth data and delivery exist.
- Payment receipts and invoices: optional and gated on verified payment provider/event integrity.
- Subscription renewal reminders: optional and gated on actual lifecycle data.
- System/update/admin operational alerts: optional, admin-only; no secret exposure.
- Future channels (SMS/push): visibly unsupported until actual integrations are installed.

A toggle controls an existing implementation, NOT creation of new infrastructure. Unsupported features are disabled with explanatory text and cannot be persisted as 'enabled'.

## Operational/security requirements
- Admin-only GET/PUT on backend with CSRF/Origin checks, role checks, strict Pydantic input allowlists, rate limits and audit log for changes; never trust frontend toggles for enforcement.
- Persist provider configs in an existing encrypted-credential approach or a migration-added protected provider config table; never write arbitrary .env strings from browser. No plaintext secrets in DB or application responses, logs, snapshots, test fixtures, or Git.
- Separate operational config (host/port/from/flags) from write-only secret values. Encryption key stays environment-held and unchanged across deploys.
- Ensure multi-worker consistency (DB transaction, version/revision for concurrent edits) and auditable who/when without key contents.
- Preserve fail-closed registration verification behavior: if enabled but SMTP not operational, show explicit unavailable state rather than bypassing verification.
- Preserve password-reset security (short-lived, single-use, digest-stored tokens and rate limiting); do not claim operational if not implemented.
- Existing active TEST environmental SMTP config has priority until explicit, successful migration with a rollback plan. No silent shadowing or breakage.
- Feature flags cannot disable authentication, ownership gates, cross-account isolation, security approval, or native tool restrictions.
- TEST-only first; migrations and smoke tests, then verify owner and standard-user authorization. No direct LIVE rollout.
- UI supports Arabic RTL / English LTR, mobile layout, accessible checkboxes/keyboard use, status loading and confirmations. Display provider readiness and avoid misleading successes.
- Optional service notification dispatch must use established application domain behavior with bounded retries (if available), not introduce an independent AI service or arbitrary custom worker without explicit architectural review.

## Acceptance cases
1. Admin sees configured provider without reading password/key.
2. Non-admin gets 403 for reads/writes even if request bypasses UI.
3. Admin can choose a *supported* provider, set safe fields, rotate secret and test delivery; failed test does not silently switch active provider.
4. New-account email verification flag defaults on in fresh configuration, but registration fails closed until delivery is ready.
5. Password reset is displayed as a default-preferred service, yet cannot be enabled until actual secure flow exists.
6. Disabled notification toggle results in no notification; enabled supported toggle uses existing delivery.
7. Invalid/unconfigured provider, SSRF hostname, TLS misconfiguration, and malformed inputs fail safely.
8. Existing plans/subscriptions and connected integrations keep working; no cross-user secret leakage.
9. No .env, database, OS config, OpenCode runtime, or LIVE mutation through GitHub source deploy.
10. Each newly implemented feature has automated backend authorization and UI contract tests plus browser TEST acceptance before marking complete.

## Implementation staging
- Phase A: inspect existing admin shell and email/management services; add read-only readiness + admin UI tabs with accurately labeled unavailable controls.
- Phase B: add secure admin persistence and editing for supported SMTP configurations, with encrypted secret handling and explicit activation/test flow; migrate without removing current environment fallback.
- Phase C: wire verified supported toggles to existing registration verification, password reset (only after completed), subscriptions and payment notifications.
- Phase D: cross-account and end-to-end delivery tests, documented TEST release.

Do not remove or break the existing Native provider 50-item display cap: AI provider selection is a separate system from Admin service integrations.
