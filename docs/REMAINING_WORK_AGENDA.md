# Remaining work agenda — Test-first
Last updated: 2026-10-16
All executable changes on updates, no Live/master changes without approval.

## Registration blocker — email verification (high priority)
- [ ] Investigate error: **"Email verification is unavailable; registration cannot proceed"** during password registration.
- [ ] Confirm SMTP_HOST, SMTP_FROM, SMTP_USERNAME and SMTP_PASSWORD are configured for the appropriate environment, without revealing values or secrets. Current backend `email_verification.smtp_ready()` checks their presence and `auth.py` returns HTTP 503 before account creation if absent. This strongly suggests missing SMTP configuration, but does NOT establish the current server's actual state.
- [ ] Verify environment variables are loaded into the backend service, `PUBLIC_BASE_URL` is correct HTTPS for the environment, SMTP reachability/port/TLS/authentication and deliverability. Never log SMTP passwords or verification tokens.
- [ ] Check resend-verification and one-time token expiry, error handling and no duplicate accounts. Do NOT bypass verification as a workaround.
- [ ] Add configuration/SMTP failure regression tests with mocked mail transport, then test registration plus verification end-to-end on TEST only.
- [ ] Resolve before paid customer launch. Owner should receive the Test deployment checklist when integration is ready.

## Smart Preview (primary implementation workstream)
See `docs/SMART_PREVIEW_POLICY.md`. Pending: execute committed tests, isolated Test-only Alembic 0019 validation, trusted worker registry and atomic capacity leases, sandboxed build/runtime, manual Start Preview integration, 300-second idle reaper, authenticated separate-origin routing, full security/E2E validation.

## Agent background tasks (after Preview)
See `docs/AGENT_BACKGROUND_EXECUTION_ROADMAP.md`. Independent safe pause/resume and background execution with durable state; NEVER couple to Preview idle timer.
