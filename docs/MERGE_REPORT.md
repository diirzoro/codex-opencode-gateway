# OpenCode → Codex synchronization report

Date: 2026-10-05. Destination: `D:\opencodde agent\codex project\project`. Incoming project: `D:\opencodde agent\opencode project\project`.

The user's final correction makes Codex the destination. Earlier in this turn, the user explicitly selected OpenCode as the destination, so account-management additions were first merged there. After the final correction, OpenCode was read only; its maintained-file hashes have been checked for changes. No Git push, SSH, VPS connection or deployment was performed.

## Found in OpenCode and brought into Codex

- Per-user subscription model and billing routes: read trial/plan status, select a plan, cancel and reactivate. Selection is `pending_payment`, never a simulated successful payment.
- Safe project archiving, archived metadata in admin reports, and dashboard filtering so archived projects disappear without deleting files.
- Separate client Dashboard, Projects, Sessions, GitHub, OpenCode, Plan & Billing, Profile and Security sections; separate admin Overview and management sections.
- Admin subscription overview, billing summary, reports and runtime health; preserved explicit unavailable states for unsupported revenue, invoices and payment processing.
- Unified fixed header/sidebar, navigation history/back button, profile shortcut, professional cards, searchable/sortable grids, modals, editable profile, mobile layout and SVG branding.
- New billing regression tests, owner browser fixture, newer workspace/browser tests, diagnostic scripts and an operator-run live-provider verification script. That live-provider script was inspected and copied, not executed with credentials.
- Reference documentation from OpenCode preserved in `docs/reference/opencode/`, with sync notes in the main references.

## Existing Codex work retained and integrated

Account-management APIs/UI, password change and single-use password recovery, sign-in revocation, suspend/deletion requests with retained files, encrypted personal/platform payment-method configuration, audit, location management, owner-only role grants, user-authorized GitHub tokens, repository/branch chooser and per-workspace provider credential/policy checks remain in the combined project. The newer dashboard/shell was used as the base rather than activating the older incompatible standalone dashboard implementation.

Client login/registration/restoration now explicitly selects Dashboard; admin/owner selects Overview. Profile stays a manual section. Existing profile editing was repaired, and mobile workspace drawers now appear above the fixed header so their close controls remain clickable.

## Database and API changes

The existing Codex `0005_account_management` migration is unchanged. New `0006_subscriptions_archive` follows it and adds subscriptions and `projects.archived_at`. This deliberately preserves Codex migration identity; OpenCode's independently merged migration names are different. Do not interchange database migration histories blindly.

Added/imported APIs:

- `GET /api/billing/subscription`
- `POST /api/billing/subscription/select`, `/cancel`, `/reactivate`, `/renew`
- `GET /api/billing/invoices`, `/payments` (truthfully unavailable)
- `POST /api/projects/{id}/archive`
- `GET /api/admin/subscriptions`, `/billing/summary`, `/billing/transactions`, `/reports`
- `/api/dashboard` retains profile plan data and adds plan/recent sessions/recent workspaces; all exclude archived projects.

Existing management/GitHub/provider routes were merged additively; customer data remains scoped to the authenticated owner, and administrative APIs require administrative roles.

## Validation

- Backend: **59 passed, 1 skipped**. The skipped test requires Windows symlink privileges. Includes the explicit local OpenCode session smoke test and subscription/archive/security tests.
- Fresh isolated SQLite: upgrade through `0006_subscriptions_archive` passed; exactly one migration head.
- PostgreSQL: offline SQL generation passed. No live PostgreSQL database or VPS was contacted.
- Visible Chromium: **15 passed** in the final complete run; covers all three roles, registration, refresh, manual profile, customer admin denial, payment method CRUD, admin locations, files/diff/commit, plans, navigation, Arabic/English and mobile.
- JavaScript syntax checks passed.

## Limits and feature status

REAL locally: authentication and role routing, account/security management, owned projects/files/diff/local commits, safe archiving, persisted subscriptions and payment-method configuration, administrative counts and controls.

PARTIAL/configuration-dependent: provider/GitHub OAuth, encrypted provider storage, SMTP recovery delivery and runtime integration. GitHub authorization expires within 8 hours and automatic token refresh is pending. Provider OAuth token backup to the database is not implemented. Local workspace processes are not a production OS sandbox.

MISSING: automatic charge processing, real invoices/payment transactions/revenue, paid renewal processing and the remaining production isolation/deployment verification. No simulated data was added.

## Preservation

Full pre-sync Codex maintained-file backup: `D:\opencodde agent\codex project\.audit\codex-before-opencode-sync-2026-10-05`.
The earlier OpenCode backup is under `.audit/project-comparison-latest-2026-10-05/destination-before`.
No maintained Codex files were deleted. Existing secrets, databases, dependency directories, runtime state, workspaces and generated test artifacts were excluded from synchronization. Changes remain local and unpushed.

## Changed existing Codex files

- `.env.example`
- `.gitignore`
- `app.js`
- `dashboards.js`
- `enhancements.js`
- `index.html`
- `management.js`
- `styles.css`
- `backend/requirements.txt`
- `backend/app/main.py`
- `backend/app/models/platform.py`
- `backend/app/models/workspace.py`
- `backend/app/models/__init__.py`
- `backend/app/routes/admin.py`
- `backend/app/routes/dashboard.py`
- `backend/app/routes/workspaces.py`
- `backend/app/services/workspaces.py`
- `backend/tests/browser_server.py`
- `backend/tests/test_plans_policy.py`
- `deployment/.env.production.example`
- `deployment/README.md`
- `docs/ACCOUNT_WORKSPACE_REQUIREMENTS.md`
- `docs/API_REFERENCE.md`
- `docs/ARCHITECTURE.md`
- `docs/DATABASE_REFERENCE.md`
- `docs/DEVELOPMENT_ROADMAP.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/PHASE_REPORT.md`
- `docs/SECURITY_MODEL.md`
- `tests/browser/management.spec.cjs`
- `tests/browser/workspace.spec.cjs`

## Imported/adapted new files

- `backend/app/routes/billing.py`
- `backend/scripts/verify_live_provider.py`
- `backend/tests/test_billing.py`
- `docs/reference/opencode/ACCOUNT_WORKSPACE_REQUIREMENTS.md`
- `docs/reference/opencode/API_REFERENCE.md`
- `docs/reference/opencode/ARCHITECTURE.md`
- `docs/reference/opencode/DATABASE_REFERENCE.md`
- `docs/reference/opencode/DEVELOPMENT_ROADMAP.md`
- `docs/reference/opencode/IMPLEMENTATION_STATUS.md`
- `docs/reference/opencode/PHASE_REPORT.md`
- `docs/reference/opencode/SECURITY_MODEL.md`
- `tests/browser/debug-bisect.cjs`
- `tests/browser/debug-bisect2.cjs`
- `tests/browser/debug-btn.cjs`
- `tests/browser/debug-dom.cjs`
- `tests/browser/debug-dom2.cjs`
- `tests/browser/debug-parse.cjs`
- `tests/browser/debug-probe.cjs`
- `tests/browser/merged-routing.spec.cjs`
- `tests/browser/typography-audit.cjs`
- `tests/browser/v2-verify.cjs`
- `backend/alembic/versions/0006_subscriptions_archive.py`
