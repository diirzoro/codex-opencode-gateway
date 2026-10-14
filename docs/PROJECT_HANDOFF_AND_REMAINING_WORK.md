# OpenCode Gateway — Living Project Handoff and Completion Register

**Updated:** 2026-10-14  
**Source of truth:** this file on `updates`  
**Last audited baseline:** `updates` at `2b9f2618eb178e5f94a0b4cea32f9a5148bd2ec8`; see the stabilization entry below for this round's evidence and repair commit.
**Status:** DEVELOPMENT / UNVERIFIED — NOT RELEASE-READY

> **MANDATORY FOR EVERY CODING AGENT (Codex, OpenCode, Work, or another agent):** Read this document **before** changing code. After every coherent change, update this document **in the same branch and commit or an immediately following commit**. Never mark a task complete merely because code was written. State evidence, tests, remaining gaps, commit SHA, and any deployment impacts. Continue using the existing design and architecture; do not remove requirements silently.

## 1. Guardrails

- **Only commit to `updates`.** Do not merge/push to `master`, touch `rollback-updates-2026-10-13`, edit GitHub Actions/workflows, or deploy to production without explicit owner approval.
- Do not change production PostgreSQL data, live VPS services, existing secrets or `.env`, PayPal configuration, billing records, or apply migrations on production as part of development.
- Do not assume a green build because JavaScript parses; use real tests, visual browser inspection, database integration tests, and cross-user security tests.
- **No cross-user mixing:** unique email and username; projects may share names across different users but not authorization scope. Each user has their own workspaces, sessions, secrets, API keys, provider/OAuth connections, agents, repos, preview runtime and storage.
- **Connections belong to users, not projects.** Link them once in Dashboard → Connections; apply to all of that user's workspaces; revoke in all; never expose plaintext credentials in API responses or logs.
- Keep existing Arabic/English RTL support, page styling, subscriptions, and current data.
- Previewing untrusted projects requires isolated, resource-limited execution, never arbitrary host-shell execution.
- Human-controlled approvals must genuinely block sensitive operations in backend until approved or rejected.

## 2. Product and environment

- Repo: `diirzoro/codex-opencode-gateway`. Production domain: `opencode-gateway.codes`.
- Stack: FastAPI, PostgreSQL, OpenCode local runtime, frontend vanilla JS/HTML/CSS, Nginx/systemd on Ubuntu 24.04 VPS.
- Working/deployment branches: `updates` = development; `master` = production. Preserve existing deployment workflow.
- Production DB was previously reported at Alembic revision `0016_checkout_locations`; migrations `0017_user_provider_credentials` and `0018_email_verification` exist in source **but are not approved/applied to production**.
- Preserve isolated roots `/var/lib/opencode-workspaces` and `/var/lib/opencode-runtime`; never rely on `backend/workspaces`.
- Target: web-based, multilingual AI coding Gateway. 50 MB workspace upload quota where configured; real GitHub integration; user-owned storage.

## 3. Status legend

- **CODED / NOT VERIFIED:** changes exist on `updates`, but runtime/security/integration behavior not proven.
- **PARTIAL:** significant functionality is still missing.
- **NOT STARTED:** no completed implementation verified.
- **VERIFIED:** requires reproducible tests, exact commands/results and evidence; do not assign without proof.

## 4. Implementation register (as of 2026-10-14)

| ID | Area | Implemented in source | Current status / missing evidence |
|---|---|---|---|
| C-01 | Account-level providers | Table `user_provider_credentials`, account catalog/list/delete routes and account key encryption/recovery logic | **PARTIAL VERIFICATION** — PGlite migrations and real OpenCode key lifecycle passed; native PostgreSQL concurrency/constraints remain blocked; see sections 12–13 |
| C-02 | API key connection without a project | Isolated temporary OpenCode validation runtime, account connect/options routes, Dashboard UI wiring | **PARTIAL VERIFICATION** — real staging browser cold catalog/options now pass; external paid-model authentication is still mocked in lifecycle tests |
| C-03 | OAuth without a project | User-isolated account runtime and authorize/callback routes, encrypted token persistence/recovery | **PARTIAL** — verify OpenCode auth.json location and structure, token refresh, expiry, restart and provider-specific OAuth flows; do not ship based on source alone |
| C-04 | Connections synchronized across workspaces | Restore account credentials on runtime start; attempted in-place refresh of running runtimes; cache invalidation | **PARTIAL** — ensure *every* active session/Composer updates immediately, failed refresh never falsely reports connected, no process interruptions |
| C-05 | Safe disconnect and revocation | Deletes account and legacy credentials; runtime auth removal and private auth-file cleanup | **PARTIAL VERIFICATION** — running/stopped key revocation, reconnect/restart, two workspaces and unchanged second-account auth passed; OAuth stale tokens/live busy-session tests remain |
| A-01 | Single free trial | One 30-day trial; separate advanced 10-day trial logic disabled; registration starts on email verification | **CODED / NOT VERIFIED** — first payment must permanently end trial and start purchased term from payment time |
| A-02 | Renewal and billing | Verified payment activates purchased plan; active paid renewal extends existing end date; repeat payment protected by order status/locks in source | **CODED / NOT VERIFIED** — test first purchase mid-trial, early renewal, expired purchase, simultaneous captures, PayPal sandbox vs live, bank approval, nonpayment and no second trial |
| A-03 | Feature permissions | Core, integrations/BYOK, GitHub, custom agent gated by trial or paid access; admin override | **CODED / NOT VERIFIED** — audit every execution and API route; expired accounts retain permitted billing/export/recovery access only |
| A-04 | Email ownership | `pending_email` registration, SHA-256 hashed single-use 24h verification link, resend password check and 2-minute cooldown, SMTP fail-closed | **CODED / NOT VERIFIED** — migration 0018, outbound SMTP configuration deferred, actual delivery and UI behavior tests outstanding |
| A-05 | Temporary mail | Known disposable domain denylist in registration | **PARTIAL** — list is not exhaustive; update carefully, don't wrongly block legitimate providers; ownership verification does not prove corporate/official email |
| A-06 | Freeze, retention and restore | 90-day retention policy, idle/expiration checks, archive, removal of sensitive tokens including account provider secrets, account recovery path | **PARTIAL** — test reactivation after paid expiry, identity checks, no trial reset, no premature archive, paid period as retention anchor, all secret cleanup |
| W-01 | ChatGPT-like scrolling | Existing Workspace chat and streams; requested sticky-bottom vs user-scroll behavior | **NOT VERIFIED** — implement/test follow-tail only when already near bottom, smooth rendering and Jump to latest; no forced scroll on reading history |
| W-02 | Real approval blocking | Approval UI and API exist | **NOT VERIFIED** — verify no commands/actions proceed while pending; persist across reload; resume after approve, honor reject; backend authority required |
| W-03 | Structured questions/options | Agent question API/UI, choices, custom answer; `recommended` metadata surfaced where provided | **PARTIAL** — visually styled clear square/question cards, optional multi-choice, recommended rationale, custom typed response, persistent state and agent continuation must be proven |
| W-04 | Activity/progress | Agent status and messages supported in source | **NOT VERIFIED** — verify actual searching/reading/editing/executing/todo progress, no duplicate messages, sessions and refresh |
| P-01 | Static HTML preview | Sandboxed `index.html` source parser currently exists | **CODED** but insufficient for project-wide preview |
| P-02 | Project detection | `preview.detect` detects HTML, Node/React/Vite/Next/Vue/Angular/Svelte, Python/Django, PHP/Laravel, Rust, Go, Flutter, Java and exposes `/preview/capabilities` | **CODED / NOT VERIFIED** — detection is **not** execution |
| P-03 | Universal project preview | Must preview actual running apps, not only raw HTML | **PARTIAL / BLOCKED** — design isolated Docker/runner with strict CPU/RAM/timeout, filesystem, network and port mapping controls; secure per-user origin/proxy; browser preview only for web-capable apps; CLI/mobile need runners/emulators/output |
| S-01 | Multi-tenant isolation | Ownership checks and runtime separation patterns exist | **NOT VERIFIED** — two-user same project name, credentials, OAuth, session state, preview ports, files, cross-user request forgery and traversal tests |
| S-02 | Testing | Offline contracts, disposable SQL/OpenCode integration, browser regressions, startup DB-scope tests and sanitized staging diagnostics | **PARTIAL** — actual counts in sections 12–13; native DB, model/OAuth/SMTP/container execution and full lifecycle/agent proofs still pending |
| S-03 | Online preview and bug-fixing pass | Isolated loopback FastAPI/OpenCode/PGlite browser journey exercised and screenshots saved | **PARTIAL** — local staging journey now passes; no public preview URL, no native PostgreSQL browser certification or production access |

## 5. Exact commercial rules (do not regress)

1. **One free trial ever: 30 days, counted from successful verified account activation.** No additional advanced integration trial and no trial reset on renewal/reactivation.
2. **First successfully verified payment** ends free-trial eligibility permanently, starts a new *paid* period from confirmation time for the plan's configured `duration_days` (usually one month / 30 days if that plan specifies 30; do not silently assume calendar month).
3. **Second or later payment during an active paid period** adds purchased days after the current paid expiry, preserving unused paid time.
4. **Payment after paid expiry** starts a new paid period from confirmation time.
5. Selecting a plan, an unpaid checkout, PayPal sandbox payment, or rejected/pending bank transfer **does not** grant paid access. Capture/approval must be verified server-side; duplicate captures must not extend entitlement twice.
6. Keep trial dates as audit history but never reactivate an old trial after the first payment.
7. After paid/trial expiry, restrict execution appropriately but preserve account billing/recovery/export and permitted disconnection; archive per actual retention/grace policy, never automatically delete invoices or payment evidence.
8. Test plan upgrades, renewal across concurrent requests, frozen/archived recovery, and case-sensitive/canonical unique usernames and email.

## 6. Workspace & Agent Interaction — **ONE unified feature**

Implement/test as a **single requirement**, not unrelated UI changes:

- Streaming response follows bottom automatically while the user is at bottom; when the user scrolls up, preserve their reading position and offer a Jump to latest button.
- Display accurate agent status (search, read, edit, execute, test, todo). Keep one logical message; no repeated blank/duplicate answers.
- Approval appears inline as an obvious card; **agent must stop before protected action** and wait for explicit approval/rejection. Pending survives page refresh/session restoration. Approval resumes the same task; rejection blocks the action.
- Agent questions appear in clear rectangular cards with legible description and choices, support single or multiple choices, an explicit **Recommended** choice **only when genuinely supplied by agent** plus explanation, **Other / write your own choice**, and Submit. Agent must await answer, with the card positioned alongside latest conversation, then continue automatically.
- Preserve chat history and state after reload, navigation, and workspace switching; avoid using a purely visual UI state as backend permission decision.

## 7. Real multi-language/project preview requirements

- Detect actual project type and start a compatible app runner; do not hardcode `index.html`.
- React/Vite/Next/Vue/Angular/Svelte: install/build/start as appropriate **inside isolated runner**.
- Python/FastAPI/Django, Node/Express, PHP/Laravel: support web/API preview with routed ports and secure authenticated reverse proxy.
- Other frameworks (Go, Rust, Java, etc.): web servers may preview if a supported runtime exists; CLI output requires logs/terminal view; mobile/desktop apps require a matching simulator/emulator rather than pretending an iframe runs them.
- Preserve per-user isolation, secrets, branch/filesystem boundaries; do not expose containers/ports publicly. Apply budgets and timeouts; no privileged containers, Docker socket sharing, host network, arbitrary mounts, or unrestricted egress by default.
- Do not report this feature complete after simple framework detection.

## 8. Next work sequence

1. **Critical code audit first:** imports, runtime paths, preview detection, DB/SQL ownership, OAuth token lifecycle, persisted secret deletion. Fix failing unit tests and routes before adding features.
2. Make account Connections API/OAuth work end-to-end without project in disposable test environment; test two users and multiple workspaces.
3. Finish the **unified Workspace & Agent Interaction** (scroll, questions/recommendations/custom answer, approval truly blocks and resumes, persistence).
4. Implement secure container-based **universal project preview** and preview its own test fixtures for several frameworks.
5. Validate one-trial lifecycle, paid days, permissions, freeze/retention/restore; email verification/send/resend, disposable email filtering.
6. Run Alembic migrations **0017 and 0018 ONLY on a separate disposable PostgreSQL test database**, not production. Run full pytest, syntax, browser QA and a staging smoke test.
7. Handoff `updates` to **Codex or ChatGPT Work** for live **staging** browsing/preview and bug fixes. Capture screenshots and issue log. **Do not merge to master** at the end of test; wait for explicit owner authorization.

## 9. Mandatory update procedure for all agents

**Before change:** read this document, check latest `updates` commit and actual test status; inspect relevant source.  
**During change:** edit minimal existing code; keep secrets out of logs/commits; do not touch production.  
**After change:** run tests feasible in that environment, inspect diffs; commit to `updates`.  
**Then update this file**, noting in the changelog: date, exact commit, changed features, reproducible test evidence, unresolved blockers, dependencies, and next recommended task. Move a status to VERIFIED only with demonstrated tests.  
**When delegating:** share the GitHub URL of this file and include: *"Read PROJECT_HANDOFF_AND_REMAINING_WORK.md before coding, and update it in your own change set."*

### 2026-10-14 connection reliability audit

- **Fixed in `018a5023`:** stopped-workspace refresh previously used undefined `user`/`workspace` variables and attempted to delete authentication while *connecting*. Now stopped workspaces defer restore to startup without scrubbing credentials.
- **Regression test added in `4b228636`:** `test_stopped_workspaces_never_scrub_credentials_during_connect`. Test code exists; **NOT EXECUTED** in this GitHub-only session.
- **Fixed in `e0761357`:** temporary account validation Runtime used `Path.mkdir()` repeatedly for shared `HOME`/`USERPROFILE` locations, causing `FileExistsError` before startup. Changed to `exist_ok=True`.
- **Still pending:** run unit tests, isolated OpenCode process startup and real model validation, OAuth refresh, workspace key restore, two-account data isolation and browser Connections flow. No deployment or database migrations authorized.

### 2026-10-14 — Partial synchronization reporting

- Commit `ff5df6ee`: account-level API/OAuth connection responses now include `deferred_workspace_count` for active workspaces whose credential refresh failed. This makes partial synchronization visible rather than silently claiming full success.
- Commit `aeb36c45`: Dashboard Connections warns users when running workspaces require a refresh.
- **Not verified end-to-end:** credentials/authorization must be exercised with live OpenCode services, multiple users and concurrent workspaces. No automatic resync guarantee is claimed.
- **Still required:** inspect and test provider OAuth token rotation and restart, isolated preview runner, ChatGPT-like agent approvals/questions/scrolling, billing and archived-account lifecycle, SMTP activation and migrations on a disposable database.


### 2026-10-14 — Batch 1 owner follow-up: OAuth rotation guard (in progress)

- Commit `95d6e14f`: introduced tenant-scoped `replace_encrypted_if_current` in `backend/app/services/user_provider_credentials.py`. This uses a row lock and exact encrypted-value comparison before staging an update; caller retains commit responsibility. It is a **building block**, not yet wired into automatic OpenCode token refresh events.
- Commit `612a3b97`: added three focused mock-level regression cases for the guard in `backend/tests/test_oauth_rotation_cas.py`. These tests have **NOT BEEN EXECUTED** in this GitHub-only editing environment.
- **Not complete:** rotated OAuth tokens are not yet automatically synchronized from OpenCode runtime auth files to Gateway's encrypted database; native PostgreSQL concurrency, actual provider OAuth refresh/restart, busy workspace retry, and Composer fanout remain OPEN.
- No deployment, migration, payment settings or protected branch changed. The next developer must not claim Batch 1 is verified until refresh propagation and real integration tests pass.

### 2026-10-14 — Batch 2 partial implementation

- `cad9d79a`: agent questions now have visibly bounded rectangular answer cards and option rows including selected option and an explicit agent-provided recommendation badge, in `styles.css`. Visual/browser behavior has **not been tested**.
- `7bf4b527`: `app.js` message refresh retains the current scroll offset when the reader was above the bottom; follows new output only if already within 110 pixels of the end before rerender. **Static JavaScript syntax passed; live browser scroll testing remains OPEN.**
- **Open Batch 2 items:** Jump to Latest control, live approval blocking/persistence, question continuation and recommendation rationale, real agent streaming/progress, prevention of duplicate or blank responses, and safe isolated executable preview for non-HTML frameworks.
- **No claim of universal project preview:** static HTML and manifest detection remain the only available preview modes. No Docker/runner infrastructure was added or deployed.
- Do not mark Batch 2 VERIFIED until targeted real-browser and real-OpenCode tests pass. No production/branch/deployment changes.

## 10. Change log

| Date | Commit | Change | Evidence / pending |
|---|---|---|---|
| 2026-10-14 | `23974362c233a617fb4bef57000eb4b9496c50dd` | Latest reviewed baseline before handoff; Preview detection, question recommendation metadata/UI | GitHub diffs and JS syntax only; no runtime QA |
| 2026-10-14 | *this document creation commit* | Central living handoff, full task register and update protocol | Document creation; does **not** mean implementation verified |

## 11. Known uncertainties / test blockers

- Cannot infer that SMTP server is configured; do not store SMTP credentials in git.
- Current production migration state was reported as 0016; verify independently during staging planning, without applying to production.
- Some OpenCode OAuth paths and auth-file assumptions are unverified, especially refresh/expiry.
- GitHub combined commit status had no CI checks for prior work; **tests in source are not test execution evidence**.
- OpenCode runtime separation alone is not a full OS sandbox.
- Do not silently change customer's requested 50 MB quota, UI/RTL, payment terms, project-independent connections, or active session handling.

**Source of truth is the repository version of this file.** The assistant's conversational context can help but cannot replace this durable record.

## 12. 2026-10-14 — Regression stabilization (not a release approval)

Scope: complete the confirmed repairs before large architectural changes. No broad cleanup, migration-source edits, dependency upgrades, visual redesign, production access or deployment. The earlier implementation register remains open except for the specific evidence below. Repair commit: `c45bf25ce048d86423bbfa0376e0f8c58aa6ed85`. Its Git tree `e1723b3389b3ed312be0098ba2b833e9d4a2829b` exactly matches the reviewed/tested local source tree. This immediately following documentation commit records the exact published repair SHA.

### Confirmed repairs

- **Provider revocation:** stopped workspace runtimes now have their persisted `auth.json` scrubbed, in addition to the account runtime and running workspaces. Previously the stopped-runtime branch skipped the file. Other providers and another user's file are preserved.
- **Account Connections UI:** selection, auth dialog, custom-provider dialog and callbacks support account mode with no active project. Account mode is the default; selecting a workspace explicitly retains the legacy workspace interface. Removed duplicate catalog loading and redundant search expression after examining callers; no routes or working authentication handlers deleted.
- **Selected provider status:** browser screenshot inspection found a stale "Disconnected" label beside a successfully connected provider. Refresh now updates the selected provider's status from the same snapshot as the connected-provider list; browser assertions cover the label after connect and reconnect.
- **Owned catalog:** provider/search/agent catalog routes use the authenticated user's account OpenCode runtime. They no longer query the shared daemon. Cache entries are separated by runtime generation, expire, return copies and contain allowlisted metadata only. The compatibility helper still supports an explicit shared-service caller; no account route uses that fallback.
- **Missing project/files:** workspace payload reports `files_available` without disclosing paths. Restoration/opening validates ownership and file availability, clears only stale selection, and returns to the project-independent Workspace home. Opening Workspace no longer implicitly selects the first/recent project. No project data is recreated or deleted.
- **Pending registration:** the `enhancements.js` registration override respects `pending_email`, clears the password, shows the verification instruction and avoids the unauthenticated profile PATCH. The base handler and verified/social flows remain.
- **Schema inspection:** use the current SQLAlchemy transaction connection for migration-presence checks rather than obtaining an extra pooled connection. This avoided a PGlite bridge wait during testing; it is **not evidence of a PostgreSQL-native application defect**. Native PostgreSQL verification remains required.

### Actual test results

| Run | Passed | Failed | Skipped | Scope / limits |
|---|---:|---:|---:|---|
| `python -m pytest backend/tests -q` | 28 | 0 | 12 | Offline regression/contracts; the disposable integration module is opt-in |
| Isolated PGlite + OpenCode harness | 8 | 0 | 4 | Preliminary SQL compatibility/integration evidence, **not native PostgreSQL**; one dependency deprecation warning |
| `node tests/browser/account-connections.cjs` | 6 scenarios | 0 | 0 | Real frontend, mocked Gateway APIs: no/missing project connection, disconnect/reconnect, deferred warning, Arabic/English RTL/LTR, 390px input fit, deleted/missing/available restoration and pending signup |
| Real loopback staging browser | 0 completed journeys | 1 | 0 | Registration/verification/login reached Workspace home; Connections provider readiness did not complete; see blocker below |
| JS syntax, Python compile, `git diff --check` | Passed | 0 | — | Parser/whitespace checks only, not end-to-end verification |

The PGlite harness applied **all migrations through `0018_email_verification`**, including 0017 and 0018, to a new in-memory disposable database. It did not touch any existing database. It verified 249+ seeded countries, hashed/single-use verification tokens, resend password/cooldown/old-token invalidation, one verified-email 30-day trial, normalized duplicate registration rejection, encrypted account credentials, ownership checks, traversal/private-path denial, cross-origin mutation rejection, first-payment/early-renewal/expired-renewal and repeat-confirmation behavior. Payments were internal test orders; no PayPal or bank request occurred.

Security evidence: two accounts can create same-named projects while foreign workspace/files/session/question/permission/preview-capability requests are denied. A `pending_email` account with a deliberately seeded otherwise-valid session receives 403 on auth/profile/profile PATCH/projects/workspaces/account catalog/connections/session messages/questions/permission reply. This samples protected routes; it is not a formal exhaustive security certification.

**Real OpenCode 1.18.32 evidence:** dedicated account runtime starts without any project; native provider/auth-method metadata is available. Gateway Connect → duplicate Connect 409 → account runtime restart/key restore → two project runtimes → stop one → Disconnect → restart stopped runtime without revoked key → Reconnect → both project auth files updated → Disconnect succeeds. A second account's runtime auth file is byte-for-byte unchanged. Keys are fake; only external model validation is mocked in this integration test. The native permission/question/session APIs were queried with empty state; this does **not** verify a live pending approval/question or actual agent continuation.

Busy-runtime deferral/no termination is covered by an offline contract, not a real streaming session. Provider credential persistence, revocation and idle-runtime fanout are tested; live composer synchronization and OAuth refresh remain open.

### Reproduction and evidence

Install backend test dependencies in a separate virtual environment. Auxiliary QA tools used: `@electric-sql/pglite@0.5.9`, `@electric-sql/pglite-socket@0.2.12`, `opencode-ai@1.18.32`, `playwright@1.56.1`, Chromium. These were not added to production dependencies.

```bash
python -m pytest backend/tests -q
python tests/run_isolated_audit.py \
  --pglite-command /absolute/path/to/pglite-server \
  --opencode-binary /absolute/path/to/opencode
NODE_PATH=/absolute/path/to/qa/node_modules \
CHROMIUM_EXECUTABLE=/absolute/path/to/chromium \
AUDIT_SCREENSHOT_DIR=/absolute/path/to/qa-evidence \
node tests/browser/account-connections.cjs
# Real local browser attempt (SMTP replaced by a disposable fixture mailbox):
NODE_PATH=/absolute/path/to/qa/node_modules \
CHROMIUM_EXECUTABLE=/absolute/path/to/chromium \
AUDIT_SCREENSHOT_DIR=/absolute/path/to/qa-evidence \
python tests/run_isolated_audit.py \
  --pglite-command /absolute/path/to/pglite-server \
  --opencode-binary /absolute/path/to/opencode --run-browser
```

`tests/browser/account-connections.cjs` and `tests/browser/staging.cjs` are reproducible browser evidence. The former saved `connections-no-project.png` and `connections-missing-project.png` locally with fixture data. They are not production screenshots or evidence of successful real-provider authentication. The staging script records API paths/statuses without token query strings and saves a failure screenshot when possible.

For **native** PostgreSQL, a separate empty loopback disposable database is still required. Apply Alembic with that explicit test `DATABASE_URL`, then run `backend/tests/test_disposable_database.py` with `AUDIT_DISPOSABLE_DB=1`, `AUDIT_DB_ENGINE=native` and isolated `WORKSPACE_ROOT`/`RUNTIME_ROOT`; set `AUDIT_RUN_OPENCODE=1` only with the pinned executable. Never point this suite at production. Native-only tests cover exact email/username uniqueness, transaction rollback after constraint failure and concurrent duplicate provider inserts, and duplicate provider uniqueness. These four cases are deliberately skipped on the PGlite bridge, whose error/rollback protocol failed with psycopg. Do not classify that bridge failure as a product bug.

### Blockers and remaining requirements

1. **Native PostgreSQL:** no `postgres`/`initdb`, Docker/Podman or Docker socket; the environment maps only UID 0 and cannot run PostgreSQL as an unprivileged user. No authorized disposable native database supplied. Native migrations 0017/0018, constraints/rollback/concurrency and simultaneous HTTP connection/capture races remain **unverified**.
2. **Real staging browser:** provider loading remained pending with no completed OpenCode API response in the first attempt. The attempt used the PGlite socket bridge, which has known transaction/concurrency limitations. Root cause must be reproduced on native PostgreSQL before changing production runtime behavior. The screenshot attempt initially timed out waiting for unavailable external fonts; failure capture now avoids that wait. No public staging URL was created; no deployment workflow changed. Switching real projects/sessions, refresh persistence, disconnect/reconnect in a real browser and Dashboard/billing/settings journeys remain incomplete.
3. **Project deletion:** permanent project DELETE currently intentionally returns 409 and offers archive. Regression browser fixtures simulate a deleted 404; the integration test moves only a newly created test repo directory and retains/restores its database project. Do not claim a real permanent-delete customer journey passed.
4. **OAuth:** encrypted token refresh/expiry/recovery/provider-specific callback/restart and two-account OAuth separation still require actual sandbox authorization. No production tokens used.
5. **Unified Workspace/Agent:** follow-scroll/Jump to Latest, blank-message regressions, actual progress/todos, pending approvals that block/persist/resume/reject, structured question single/multi/recommended/custom answers and state restoration remain open. Empty native API responses are insufficient proof.
6. **Universal Preview:** framework detection/static sandbox tests pass for seven Node frameworks plus static/traversal cases. Isolated runnable containers, quotas, network/port isolation and cleanup are **not implemented or verified**; no host execution of customer project scripts added.
7. **Email, billing and retention:** SMTP delivery is mocked, not tested externally. Verification expiry boundary, PayPal sandbox capture/rejection/webhooks, unpaid/failed order full integration, concurrent payment idempotence, 90-day archive and reactivation/no-second-trial paths require further tests. The existing PayPal `INVALID_RESOURCE_ID` production report was not diagnosed by this isolated audit; payment settings unchanged.
8. **UI/security coverage:** responsive check asserts the Connections input fits 390px and language direction changes. It does not certify every page, theme, GitHub integration, sidebar/session behavior or full cross-user runtime/preview execution isolation. OpenCode process directories are not an OS sandbox.
9. **Provider search interaction:** one browser attempt using a multi-character search lost its option while asynchronous results rerendered during click. The final regression uses the local single-character catalog filter to test connection handlers deterministically. Remote/debounced search selection under timing changes remains an open interaction issue; no application change was made for this observation.

### Files and protected state

Changed application files: `app.js`, `dashboards.js`, `enhancements.js`, `management.js`; `backend/app/routes/workspaces.py`; services `workspaces.py`, `opencode.py`, `opencode_catalog.py`, `providers.py`, `user_provider_credentials.py`, `customer_lifecycle.py`.

Changed/added evidence: `backend/tests/test_account_provider_routes.py`, `test_provider_revocation.py`, `test_account_catalog_isolation.py`, `test_preview_detection.py`, `test_disposable_database.py`; `tests/browser/fixture.js`, `account-connections.cjs`, `staging.cjs`; `tests/run_isolated_audit.py`, `tests/staging_app.py`; this handoff. Selected regression files are explicitly tracked despite an older blanket test ignore rule, following the owner's current test/publish requirement. No tables/routes/legacy files broadly removed.

Protected refs checked before publication: `master` = `bff094a1e4079e51e1673942160e86a28293cc69`; `rollback-updates-2026-10-13` = `4e8dc91d8e2f007fb19ea3914f606c7d41fca377`. No changes to `.github/workflows/`, deployment files, config defaults, production `.env`, payment credentials, production VPS or production database. No production migrations, restart, merge or deploy.

**Next action:** reproduce the staging provider-loading issue and run the prepared tests on native disposable PostgreSQL; resolve confirmed regressions before proceeding to the open architecture/features. Keep this project **NOT RELEASE-READY** until the missing evidence exists.

## 13. 2026-10-14 — Cold catalog stall diagnosed and repaired

Baseline: `f9a9d553d4ba002f90e71320a1481b232c6ce1dd`. Published repair: `28da0ceaeee2ae5d443d21895088c02f62e023f8`, tree `61ee2e51344d7f65522ab0bc614242a7931452ea`, matching the reviewed and tested source/evidence. This immediately following documentation commit records the exact repair SHA. No merge, production access, workflow/config/credential changes or visual redesign.

**Scope and root cause:** `management.js` sent `/api/opencode/catalog/providers`; authentication opened a DB transaction. Cold `for_account` → `for_workspace` then tried to open a second SQLAlchemy session for platform policy, followed by another for credential restore. Sanitized request/SQL/runtime tracing showed the request stopped before any OpenCode request. An independent two-connection PGlite test confirmed that an unrelated SELECT on connection two stayed blocked while connection one's transaction remained open, then completed as soon as connection one rolled back (503 ms including a deliberate 500 ms wait). Thus the reproduced stall is a **nested-connection dependency interacting with the PGlite bridge's single underlying connection**, not a proven native PostgreSQL row lock or frontend rendering defect. A QueuePool single-connection regression also proves nested startup reads cannot acquire another connection when the pool is occupied; SQLite there is only a pool-ownership unit fixture.

**Repair:** runtime startup accepts an optional caller-owned DB session for policy reads and credential restoration. Account catalog/search/agent/OAuth startup and workspace/session/agent HTTP callers pass their existing session. Runtime code neither commits, rolls back nor closes that session. Standalone callers retain their own session lifecycle. Tenant checks, runtime locks, credential encryption, permission decisions and execution payloads are unchanged. This is a bounded startup fix, not a rewrite of Connections or Agent behavior.

**Measured before/after:** before, catalog had no response by the browser's 45-second timeout. After, catalog returned HTTP 200 in **3773.09 ms** (server; 3777 ms browser), and OpenAI auth options HTTP 200 in **3518.01 ms**. The catalog's SQL reads used the request connection. Two new runtime regression cases fail against baseline functions; all three pass with the repair. A new integration test starts the account catalog fully cold, without a project, then checks provider/search/agent catalogs.

| Final run | Passed | Failed | Skipped | Limits |
|---|---:|---:|---:|---|
| `python -m pytest backend/tests -q` | 31 | 0 | 13 | Integration module opt-in |
| `tests/run_isolated_audit.py` with real OpenCode 1.18.32 | 9 | 0 | 4 | PGlite only; native uniqueness/rollback/concurrency still skipped; one dependency deprecation warning |
| `tests/browser/account-connections.cjs` | 6 scenarios | 0 | 0 | Real frontend, mocked Gateway API |
| `tests/browser/staging.cjs` via `--run-browser` | 1 journey | 0 | 0 | Real FastAPI/OpenCode/PGlite, SMTP fixture mailbox, no paid-model/OAuth/payment calls |

Counts describe separate runs and must not be presented as one independent suite. The pre-fix reproduced failure and negative baseline regressions are diagnostic history; they are not hidden from the evidence or counted as final passes.

**Real browser journey now passed:** new registration → pending-email message → token verification via fixture mailbox → login → project-independent Workspace → Connections → owned provider catalog → OpenAI authentication choices → close dialog → create project → move only that new fixture repo folder → refresh → safe Workspace home → create a replacement project. No actual key was submitted in this browser journey; external model validation remains mocked in the separate key-lifecycle integration test. No permanent project deletion, live Agent execution, OAuth refresh, payment or external SMTP success is implied.

**Evidence and reproduction:** [complete diagnosis and remaining-phase report](STAGING_DIAGNOSIS_AND_REMAINING_PHASES_2026-10-14.md); [before screenshot](audit/2026-10-14/staging-before.png); [after screenshot](audit/2026-10-14/staging-after.png); [sanitized request/runtime/SQL timings](audit/2026-10-14/staging-evidence.json). Use section 12's reproduction commands and set `AUDIT_TRACE_FILE=/absolute/path/to/trace.jsonl` for staging telemetry. Test instrumentation records no SQL values, auth bodies, cookies or URL query strings. Browser uncaught errors were empty; expected anonymous 401 and fixture-missing-files 409 responses were recorded. Two resource 404 console entries outside captured API paths remain unclassified, so this is not a clean-all-pages certification.

**Changed files:** `backend/app/services/opencode.py`, `backend/app/routes/workspaces.py`, `backend/app/routes/agent.py`; `backend/tests/test_runtime_database_scope.py`, `backend/tests/test_disposable_database.py`; `tests/staging_app.py`, `tests/staging_diagnostics.py`, `tests/browser/staging.cjs`; this handoff, the phase report and three evidence artifacts under `docs/audit/2026-10-14/`. No migrations or production dependency files changed.

**Native PostgreSQL remains blocked:** no server binaries, container engine/socket or mapped non-root UID, and no authorized disposable native DB. Migrations 0017/0018 and the four native-only constraint/rollback/concurrency tests are **not certified** by PGlite or SQLite results. No production database was substituted.

**Remaining work, in order:** native PostgreSQL and full external-provider authentication; OAuth expiry/refresh/rotation/restart recovery; live synchronization/busy-workspace retry without interrupting streams; unified Agent scroll/progress/questions/approval blocking and persistence; isolated container preview with resource/network/filesystem/port limits; SMTP/verification expiry/entitlement boundary tests; sandbox payment/cancellation/history/archive/concurrency; 90-day retention/reactivation and cross-user cleanup; full browser/security/load/GitHub regression and separate online review. Section 12's other open requirements remain open. OAuth source currently restores the encrypted payload and delegates refresh to OpenCode; persistence of rotated tokens back to the Gateway account store needs explicit investigation/testing before restart recovery can be approved.

**Status:** the previously failed local browser journey is repaired and passed in the described environment. **The application is still NOT RELEASE-READY.** No public staging URL was created; no master/rollback merge, VPS restart/deploy, production migration, payment setting or workflow edit occurred. Next: provision an authorized native disposable test database and OAuth/SMTP/model sandbox access, then close the remaining gates in the linked phase report without bypassing isolation.
