# Remaining work agenda — Test-first
Last updated: 2026-10-16
All executable changes on updates, no Live/master changes without approval.

## Registration — temporary email verification relaxation (owner decision 2026-10-16)
- [x] Added `EMAIL_VERIFICATION_REQUIRED` environment flag on `updates` (default `true`; explicit `false` enables password registration without SMTP delivery). Password registration creates an active account and login session when disabled; social verified sign-up remains valid.
- [x] Added unit tests for default on, explicit off, re-enable and invalid configuration. **Tests not yet run on Test.**
- [ ] Deploy to Test after controlled validation and configure `EMAIL_VERIFICATION_REQUIRED=false` in the **Test backend service environment**, never by editing the source code or exposing the value as a browser setting. Restart only Test backend after configuration.
- [ ] Validate registration, login, single trial, duplicate registrations, no forged email recovery, disposable-address blocking, and rate limits/anti-bot protection. A password account without ownership verification must be treated as **unverified** for sensitive account recovery/transactions, even while allowed to sign in.
- [ ] Before Live opt-in, obtain explicit approval, enforce abuse controls (IP/user registration throttling and fraud checks), verify rollback and monitor fake registrations.
- [ ] When adoption justifies it, change the flag back to `true` and configure SMTP; existing accounts created while verification was disabled will need a separate email-ownership verification path before sensitive actions. Do not retroactively claim their addresses were verified.
- [ ] Resolve underlying SMTP issue separately; `smtp_ready()` checks SMTP_HOST, SMTP_FROM, SMTP_USERNAME and SMTP_PASSWORD. Current server settings were NOT examined.
- [ ] Do not disable verification silently in Live: this branch has not been promoted.

## Smart Preview (primary implementation workstream)
See `docs/SMART_PREVIEW_POLICY.md`. Pending: execute committed tests, isolated Test-only Alembic 0019 validation, trusted worker registry and atomic capacity leases, sandboxed build/runtime, manual Start Preview integration, 300-second idle reaper, authenticated separate-origin routing, full security/E2E validation.

## Agent background tasks (after Preview)
See `docs/AGENT_BACKGROUND_EXECUTION_ROADMAP.md`. Independent safe pause/resume and background execution with durable state; NEVER couple to Preview idle timer.
