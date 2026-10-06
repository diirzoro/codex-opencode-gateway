# Local delivery — 2026-10-04

## Current local app and cleanup correction — 2026-10-06

This section supersedes older statements below about the active app and test fixture. The real working copy is `D:/opencodde agent/codex project/project`; the running application is `http://127.0.0.1:8766/`, connected to local PostgreSQL `opencode_gateway`, migration head `0008_paypal_checkout`. Health, landing page, and plans each returned HTTP 200. Login was verified with the sole account, now `admin1` / `dahirobaid@gmail.com`, role `owner`; `/api/auth/me` restored the role and `/api/admin/overview` returned HTTP 200. The existing project and workspace were retained.

The browser/backend test source folders, Playwright config, generated reports, `node_modules`, package manifests, and one-time account-bootstrap helper were deleted after the user asked to move implementation into the real app and never create test files again. Prior backend suite execution before deletion used in-memory SQLite only: 92 passed, 3 skipped, and 2 older billing assertions failed because they expected the prior unavailable response rather than the current verified-record response. Browser tests were not run against the actual PostgreSQL app. No persistent test database or test data exists. The current database has zero billing methods, payment orders, subscriptions, and provider credentials; PayPal merchant credentials are unset. Payment processing and provider responses are therefore not claimed to be active until real configuration is entered.

## Workspace and source reconciliation

Development is isolated in `D:/opencodde agent/codex project/project`. A source-only snapshot of the other agent's `D:/opencodde agent/opencode project/project` was imported with user authorization. The other project is not a write target. Existing local files were backed up outside this deliverable. Dependencies, environment secrets, databases, runtime data and workspaces were not imported. No VPS connection or deployment was performed.

## User-requested additions and acceptance status

| Requirement | Status | Evidence and limits |
|---|---|---|
| Separate client and admin dashboards | REAL | Existing account/admin pages plus management navigation; protected APIs and database-backed metrics. |
| Back buttons and chat workspace/repository controls | REAL | Management navigation and composer controls; desktop/mobile browser tests. |
| Username at least 6; password at least 8 with number and symbol | REAL | Registration validation; no uppercase/letter requirement; existing login remains compatible. |
| Change password | REAL | Current password checked, sessions and outstanding reset links revoked. |
| Recover password | PARTIAL | Expiring hashed single-use link, generic response, three requests per account per hour; mocked email tests pass. SMTP/HTTPS must be configured; no real mail sent. Global abuse throttling remains missing. |
| Suspend own account / request deletion | REAL | Password and exact username confirmation; sessions revoked and local workspace runtimes stopped; files retained. Admin reactivation required. |
| Permanently delete account and files | MISSING | UI explicitly requests deletion; no automatic purge or false deletion claim. |
| PayPal, bank, wallet and custom method CRUD | REAL | Encrypted database records, owner isolation, platform/client scopes. Platform receiving details deliberately visible to signed-in customers. |
| Checkout, payment records and subscription ledger | PARTIAL | Real payment orders, customer history and administrator receipt review; PayPal processing requires configured merchant credentials. Formal tax invoices and refunds are not implemented. No unverified order activates access. |
| Admin plans, user status, policy, roles, locations and audit | PARTIAL | Stored CRUD and protected routes; owner controls roles. Audit covers added management operations, not all historical actions. No full arbitrary permission editor. |
| GitHub icon → authorization → repositories/branches | PARTIAL | GitHub App and user-token verification implemented; foreign installation rejected. Requires real App credentials and OAuth during installation. No live OAuth/clone/push acceptance run. |
| GitHub persistent per-client settings | PARTIAL | User token encrypted in DB, expires within 8 hours, reconnect required; refresh-token rotation missing. Existing legacy connections require reconnect. One installation per account. |
| Workspace-bound provider/model selection and credentials | PARTIAL | Runtime discovery and owned workspace APIs; API keys require configured encryption and persist in database. OAuth/device methods exposed when reported by runtime, but OAuth token backup in DB missing. No real provider credential was used. |
| OpenCode conversations, files, diff, commit | PARTIAL | Owned local workspaces; local session/abort smoke tests. Complete paid-provider edit → push remains unverified. |
| Prices $2/month, $3/2 months, $5/3 months | REAL | Stored catalog 200/30, 300/60, 500/90; no automatic billing. |
| Existing online OpenCode on VPS | BLOCKED | Explicitly not contacted. Public multi-tenant runtime execution remains disabled pending sandboxing and deployment configuration. |
| Simulated product success | SIMULATED: none | Test doubles exist only in excluded tests; connection errors remain errors. |

## Files and migrations

Added `management.js`, `backend/app/routes/management.py`, `backend/app/models/management.py`, `backend/app/services/recovery.py`, and migration `0005_account_management.py`. Updated index/styles/static allowlist, account exports, admin and location routes, GitHub callback/token authorization, provider credential persistence requirements, Git push button state, environment examples and reference documents. Imported the other agent's plans/policy/GitHub/provider scaffolding before integration.

Migration chain: `0001_accounts` → `0002_workspaces` → `0003_github_provider` → `0004_plans_policy` → `0005_account_management`. Latest migration adds billing methods, account audit, password resets, and encrypted GitHub user-token/expiry columns. No production migration was executed.

## Verification

Backend: 52 passed, 1 skipped (real paid-provider prompt needs explicitly supplied local test credentials). Browser: 7 passed, including template/file/diff/commit, prices, administrator plans/policy, mobile/RTL, billing CRUD, security navigation and locations. Fresh SQLite migration through head passed; PostgreSQL offline SQL generation passed. A live PostgreSQL upgrade and real GitHub/SMTP/provider acceptance remain unverified. Python 3.13 was used locally; deployment target must be validated separately.

The old `8766` URL was an isolated browser-test fixture, not the application. That test process has been stopped and must not be used as the product environment. Start the application only with the local PostgreSQL configuration documented in `README.md`; do not seed demo users into the application database.

## Manual deployment

See `deployment/README.md` for exact future commands (backup, source copy without secret replacement, dependency installation, `alembic upgrade head`, service start and health check). None were executed. Keep `OPENCODE_RUNTIME_MODE=disabled` for public access until OS/network isolation, quotas and full end-to-end acceptance are completed.

Configure `CREDENTIALS_ENCRYPTION_KEY` as a high-entropy secret outside Git, preserve it with a separately protected backup, configure HTTPS `PUBLIC_BASE_URL`, SMTP, GitHub App signing key/client ID/client secret/webhook secret and OAuth-during-installation. Users must authorize their own GitHub account. Never use the repository-publishing credential for client operations.

Security basis for verifying installation membership: [GitHub setup URL guidance](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/about-the-setup-url). User access is checked before linking an installation; all customer GitHub calls use that user's token.


## OpenCode synchronization (2026-10-05)

The current Codex workspace now includes the newer OpenCode subscriptions, project archiving, client/admin dashboards, reports, shell and grid UI, together with the merged account-management features. See MERGE_REPORT.md for current verification. The preserved OpenCode document is in reference/opencode/. This workspace uses migration head `0006_subscriptions_archive` after the existing `0005_account_management`. No VPS access or push was performed.

Final synchronized-workspace verification: 59 backend tests passed, one Windows symlink privilege test skipped; 15 headed Chromium browser tests passed. Fresh SQLite migrations and PostgreSQL offline SQL generation passed. Deployment remains pending operator configuration and production verification.
