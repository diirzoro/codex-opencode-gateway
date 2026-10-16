# OpenCode Gateway — Living Project Handoff and Completion Register

**Updated:** 2026-10-14  
**Source of truth:** this file on `updates`  
**Last audited baseline:** `updates` at `2b9f2618eb178e5f94a0b4cea32f9a5148bd2ec8`; see the stabilization entry below for this round's evidence and repair commit.
**Status:** DEVELOPMENT / UNVERIFIED — NOT RELEASE-READY

> **MANDATORY FOR EVERY CODING AGENT (Codex, OpenCode, Work, or another agent):** Read this document **before** changing code. After every coherent change, update this document **in the same branch and commit or an immediately following commit**. Never mark a task complete merely because code was written. State evidence, tests, remaining gaps, commit SHA, and any deployment impacts. Continue using the existing design and architecture; do not remove requirements silently.

## CURRENT DEVELOPMENT SCOPE — owner decision 2026-10-14

**Deferred until owner-authorized main-server validation:** external payment gateway tests (PayPal and bank-transfer processing, webhooks and real payment-provider credentials) and outbound confirmation email delivery (SMTP/TLS, actual verification/resend messages). These are **removed from the current repair batches**, not cancelled, deleted or marked VERIFIED. Do not touch production secrets or configure external services now. Perform these only after explicit authorization and with safe test controls; never create real charges or send unsolicited emails.

**Still in current scope:** OAuth token lifecycle, provider synchronization, Workspace/Agent questions and approvals, isolated project Preview, multi-tenant security, account activation guards, trial and entitlement logic where testable without external payment/email delivery, and non-production database tests. Preserve the existing payment, email-verification, resend, anti-replay and account entitlement code. Record external payment/SMTP tests as **DEFERRED — MAIN SERVER**, separate from failed or completed tests.

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
| W-02 | Real approval blocking | Approval UI and API exist | **IMPLEMENTED / UNVERIFIED** overall — real native/Gateway blocking, approve/reject and fresh-client persistence VERIFIED in section 15; browser and process-restart gates remain open |
| W-03 | Structured questions/options | Agent question API/UI, choices, custom answer; `recommended` metadata surfaced where provided | **IMPLEMENTED / UNVERIFIED** overall — real backend single/multiple/custom answers and continuation VERIFIED in section 15; browser/recommendation rendering still BLOCKED |
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

### 2026-10-14 — Batch 2 continuation: Jump to Latest

- `ca0fbadd` adds a contextual Jump to Latest control in `app.js` for the conversation. It becomes visible when the reader is above the most recent messages and returns the feed to the bottom on user click, while the existing follow-tail logic preserves intentional history reading.
- `5390090f` styles the control for the chat layout and hides it when not applicable.
- Static JavaScript syntax check on `app.js` **PASSED**; **real browser behavior and mobile/RTL positioning NOT YET TESTED**.
- Remaining Batch 2: native permission/question pause/resume persistence, actual OpenCode agent execution, streaming and blank/duplicate message checks, accessible real multi-framework previews using secure isolated runners and cleanup.
- Batch 1 remains open for OAuth refresh persistence and active runtime synchronization. No master/production changes.

### 2026-10-14 — Consolidated partial-feature follow-up

- `5e2d6e76`: the actual provider-authored option description is also exposed as the recommended choice's tooltip, rather than inventing a recommendation rationale.
- `590dc87d`: question cards now display the agent-supplied header and fall back safely if the question prompt is missing.
- JavaScript parser checks for `dashboards.js`, `app.js`, and `management.js` PASSED. No live OpenCode/browser test was executed for these changes.
- This DOES NOT complete the consolidated list. Remaining: live approval execution blocking and persistence; question continuation and streaming; OAuth token refresh propagation; Composer busy-runtime retry; isolated container previews; native PostgreSQL concurrency; SMTP delivery; payment sandbox; retention end-to-end; full browser QA. Keep these OPEN, and do not infer production readiness.
- No production data, `master`, rollback, deployment workflows, or VPS changed.

### 2026-10-14 — Owner-directed remaining work, safety-first progress

- `04a8d084`: changed routine auto-approval default to **OFF** for conversations without an explicit saved preference. Previously absent configuration defaulted to on. This is a deliberate safety behavior change; user-initiated opt-in remains.
- `68041cc5`: added focused contract tests for absent, explicitly enabled, disabled and corrupt routine approval preferences; **NOT EXECUTED** in this tool-only environment.
- **Not verified:** real OpenCode permission blocking, approval/reject/resume, browser persistence and multi-user concurrency. They remain OPEN.
- Remaining active backlog: OAuth refresh propagation and live Composer sync, full Workspace streaming/tests, secure container preview, native disposable PostgreSQL constraints/concurrency, project/tenant security and browser QA.
- Owner decision remains binding: external payments and outbound SMTP are **DEFERRED — MAIN SERVER** and must not be run now.
- No master merge, rollback changes, production service/database changes, deployments or workflow edits.

### 2026-10-14 — Focused question-response validation follow-up

- `55ea52f2`: rejected duplicate selected answer values in an Agent multi-choice reply before forwarding the payload to OpenCode. Preserves single-choice, valid multiple choice, custom answer and reject pathways.
- The edit is repository-only and **has not been executed in an active FastAPI/OpenCode environment**. Browser/real agent continuation remain NOT VERIFIED. Do not count as a passed test.
- Pending active gates: full agent permission/question stream verification, OAuth refresh persistence and live workspace retry, safe container-run previews, native disposable PostgreSQL, and cross-tenant security/browser tests. External PayPal/bank payment and SMTP delivery are **DEFERRED — MAIN SERVER** by owner request.
- No production or protected branch changes.

### 2026-10-14 — Owner-authorized autonomous continuation checkpoint

- Commit `ce7f0277`: added [pre-merge verification gate](PRE_MERGE_VERIFICATION_GATE_2026-10-14.md) with all evidence-dependent remaining requirements, latest reproducible historical test results and exact scope of external services deferred by the owner.
- Read current Agent, Preview, workspace runtime synchronization and credential sources. No new verified live OAuth/Agent/Preview integration could be produced: current connector can read/write GitHub repository files but cannot execute remote processes; local git fetch was blocked by DNS.
- **No speculative security-critical integration edits were made** without a runnable test environment. Earlier post-staging changes remain code-only/unverified.
- Next required execution: permitted isolated FastAPI/OpenCode browser, native disposable PostgreSQL and isolated container runner, then targeted acceptance checks in the linked gate. Do not merge/deploy until proven and owner approved.
- External payments and SMTP are **DEFERRED — MAIN SERVER** as instructed. No changes to master, rollback, workflows or production environment.

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

## 14. 2026-10-14 — Executed repair round and 18-stage preservation checklist

Started from `981fbceb90d9264a2c8b37bb40355c42e7374856`; fetched and reconciled the 20 intervening commits through `bbca5edcf698898a3d6a69342ee3002df8e5209c` before publication. The upstream question cards, header/recommendation explanation, default-OFF routine approvals, duplicate-answer rejection, scroll behavior and styled Jump to Latest are preserved. No second scrolling implementation or duplicate button was retained. Published repair: `4ce9d48de00214d4dfb9648f01db7bbfcaac3a7a`, source tree `29d79b07bc7b7156e9d12c6d946e5ba4a35951b8` (identical to the reviewed local index). This immediately following documentation commit records the exact source SHA.

### Repairs and compatibility

- **OAuth persistence:** live maintenance observes each user's known OpenCode private auth file every five seconds; validates payloads and checkpoints later-expiring rotations into Fernet-encrypted account credentials using the existing `replace_encrypted_if_current` guard. Integrated that previously unused helper, added expected-row identity and `populate_existing` so an ORM identity-map snapshot cannot defeat the locked comparison. Deleted/reconnected/foreign/stale credentials cannot be resurrected. OpenCode still owns vendor-specific token refresh; no parallel vendor OAuth implementation was introduced.
- **Restart and reauthorization:** private 0600 version manifests contain credential IDs and ciphertext hashes, never tokens. They permit recovery of a later-expiring file rotation only for the same DB credential version. Explicit account OAuth reauthorization preserves native method indexes, rejects API-key replacement, binds callbacks to the same account/version and restores the saved credential on callback failure. Expired/known-rejected credentials receive bounded status metadata; known failed OAuth is omitted from Composer/execution catalog until reauthorization.
- **Workspace convergence:** retries mismatched credentials when runtime and Gateway session state are idle; workspace DB row guard serializes with new submissions. No session is stopped merely to synchronize credentials. Stopped runtimes restore on next start. Immediate fanout installs/binds the current DB version, not an earlier function argument. Account mutations invalidate Composer cache; visible idle Composer polls runtime revisions every ten seconds. These are eventual intervals, not hard latency guarantees.
- **Revocation security:** persisted-file deletion now pins each directory using POSIX descriptors, rejects parent/file symlinks and non-regular/oversized files, and atomically replaces in that pinned directory. A missing temporary file during replacement is an error, not success. Other providers/accounts remain unchanged. This hardening targets the supported Linux runtime; native OS sandboxing remains a separate requirement.
- **Existing UI:** preserved approved HTML/CSS/sidebar/composer design. Provider search reuses matching option DOM nodes instead of destroying the clicked element on an asynchronous refresh. Multiple-choice questions preserve selected choices alongside a custom answer. Removed the obsolete event renderer's unconditional scroll assignment; upstream scroll/Jump behavior remains authoritative.
- **Retention:** archival previously stopped project runtimes but left the project-independent account runtime alive while deleting its credential files. It now stops that runtime first and also removes verification-token records, retaining identity, trial dates and billing relationships. The 90-day policy is unchanged.
- **Preview:** added authenticated owned `/api/workspaces/{id}/preview/plan`, a read-only fail-closed plan with immutable API limits, required tenant/project routing and explicit blocked execution. It starts no engine/process, exposes no paths/ports/secrets and does not turn detection into runnable support. A real container runner, dependency-preparation stage, authenticated separate-origin proxy, Start/Stop/logs and cleanup remain OPEN/BLOCKED.

### Mandatory 18-stage TODO (completion requires evidence, not just code)

| # | Requirement retained | Current result / remaining gate |
|---|---|---|
| 1 | Instructions, latest branch, reuse previous evidence | Reviewed; reconciled latest upstream without overwriting changes |
| 2 | Account Connections without project; isolated catalog | Existing real staging evidence retained; affected lifecycle exercised with fake keys; external model authentication OPEN |
| 3 | Encrypted OAuth refresh/rotation/CAS persistence | Mechanisms unit/integration-tested; real vendor refresh and native PostgreSQL concurrency BLOCKED |
| 4 | OAuth expiration, failure, reauthorization, restart | Explicit reauthorization and CAS/replay mechanics tested; vendor sandbox expiry/revoke OPEN |
| 5 | Active/stopped/busy-workspace sync and retry | Real storage/restart and DB-busy deferral tested; uninterrupted live model streaming OPEN |
| 6 | Composer availability and provider search | Two targeted browser scenarios passed before upstream reconciliation; new search interaction needs browser verification |
| 7 | Follow-scroll, reading position, Jump to Latest | Upstream design preserved; control algorithm tested; real layout/streaming browser gate OPEN |
| 8 | Real progress/todos, no duplicate/empty messages, session recovery | Backend activity, four-turn history, idempotency and SSE replay VERIFIED with synthetic model; browser rendering/todos and whole Gateway restart remain UNVERIFIED; native process-loss handling verified in section 16 |
| 9 | Inline approvals genuinely stop/approve/reject/persist | Native/Gateway backend approve/reject/block and fresh-client persistence VERIFIED; browser card acceptance BLOCKED (section 15) |
| 10 | Single/multi/recommended/custom questions and resume | Native/Gateway single/multiple/custom continuation and ownership VERIFIED; genuine recommendation rendering/browser acceptance BLOCKED (section 15) |
| 11 | Multi-framework Preview detection/control plane | Read-only fail-closed plans tested; execution not advertised |
| 12 | Isolated runner, quotas/network/ports/auth/logs/cleanup | BLOCKED: no container engine/socket; runner interface/snapshot/lifecycle control added in section 16; actual adapter/proxy/execution remain OPEN |
| 13 | Activation guards, one 30-day trial, entitlement boundaries | Existing verification/pending-email evidence reused; controlled-time expiry/no-second-trial cases tested; external payment/SMTP DEFERRED |
| 14 | 90-day retention, secure cleanup, reactivation | Prior cleanup evidence reused; internal recovery scope/password/no-trial-reset VERIFIED on seeded paid state; internal archive failure compensation verified in section 16; native concurrency and external delivery/payment journey remain OPEN |
| 15 | Blank/GitHub projects, archive, sessions, files, quotas | Existing ownership/missing-project evidence reused; permanent deletion remains approved 409/archive behavior; live GitHub import OPEN |
| 16 | Native PostgreSQL migrations/uniqueness/rollback/concurrency | BLOCKED; PGlite/SQLite are not substitutes; no repeated native/container probes |
| 17 | Coordinated regression/browser/security evidence | Actual separate run results below; failed/blocked scenarios remain open |
| 18 | Full diff, protection review, handoff, updates-only publication | Reviewed and documented; exact commits in publication entry; no merge/deploy |

### Test evidence and limits

Results below are separate runs, never one combined suite. Earlier diagnostic failures are retained as history, not counted as passes.

- Targeted OAuth/account/security regression: **33 passed / 0 failed / 0 skipped** before upstream reconciliation. After reconciliation and guard integration: **34 passed / 0 failed / 0 skipped** for OAuth, existing rotation helper, routine-default and question validation modules. Final descriptor-revocation security subset: **28 passed / 0 failed / 0 skipped**.
- **Final current-source offline run: 76 passed / 0 failed / 17 skipped** in 0.95 seconds. Syntax/compile/whitespace checks passed. Initial coordinated offline run: **68 passed / 0 failed / 17 skipped**. Reconciled upstream offline run: **74 passed / 0 failed / 17 skipped** (before the final two revocation cases). Opt-in integration skips are not passes.
- Real OpenCode 1.18.32 + disposable PGlite: **3 passed / 0 failed / 0 skipped**, one dependency deprecation warning, 53.89 seconds: two new rotation/reauthorization tests and affected existing connect/disconnect/reconnect lifecycle. Fake OAuth rotation is written through actual OpenCode auth storage; the vendor handshake and external key validation are mocked. Two accounts, two workspaces, stopped restart, stale DB update, replay rejection, DB-submitted busy retry and unchanged process ID are covered. This is not a real vendor refresh or actual streaming Agent proof.
- **Post-upstream/security reconciliation integration: 3 passed / 1 failed / 0 skipped** in 29.80 seconds, one dependency warning: both new OAuth/sync cases and retention pass on current code; the loopback-model native Agent case fails with HTTP 500 `UnknownError`. Migrations through 0018 completed on disposable PGlite. This failed Agent case keeps acceptance open.
- Real OpenCode + PGlite retention regression: **1 passed / 0 failed / 0 skipped**, one dependency warning, 5.31 seconds. Stops project-independent runtime, removes credentials/sessions/verification rows, retains trial history and preserves the other account's runtime file/ciphertext.
- New browser Connections fixtures: **2 scenarios passed / 0 failed** before upstream reconciliation; real HTML/JS, mocked Gateway API. No external OAuth request or paid model. Reuse is limited to unchanged reauthorization/Composer mechanics; final combined browser certification remains OPEN.
- New Workspace browser script is reproducible but **BLOCKED at launch**: the existing Chromium executable exits SIGSEGV (139), including `--version`. No new successful screenshot/layout result is claimed. Existing section 13 screenshots remain historical evidence only.
- Real Agent attempt with a deterministic loopback fake model: **1 failed**, OpenCode HTTP 500 `UnknownError` before a pending permission/question. This is an unresolved fixture/runtime interaction, not proof of approval bypass or confirmed production defect. Earlier collection/request-shape mistakes were corrected. Native approvals/questions/resumption remain unverified.
- Latest-control JS fake-geometry contracts: **3 passed**; they test button visibility/click, not real scrolling layout. Preview tests: **13 passed**, including four new fail-closed plans. Internal lifecycle boundary tests: **5 passed**; question validation: **7 passed**. These subsets overlap the offline suite and must not be added to its count.

Commands (reuse installed QA tools; no production dependencies added):

```bash
python -m pytest backend/tests -q --tb=short
python -m pytest backend/tests/test_provider_revocation.py backend/tests/test_oauth_account_sync.py backend/tests/test_oauth_rotation_cas.py -q --tb=short
python tests/run_isolated_audit.py --pglite-command /path/to/pglite-server --opencode-binary /path/to/opencode --pytest-target backend/tests/test_batch1_runtime_sync.py --pytest-target backend/tests/test_disposable_database.py::test_real_opencode_account_runtime_without_project
python tests/run_isolated_audit.py --pglite-command /path/to/pglite-server --opencode-binary /path/to/opencode --pytest-target backend/tests/test_retention_runtime.py
python tests/run_isolated_audit.py --pglite-command /path/to/pglite-server --opencode-binary /path/to/opencode --pytest-target backend/tests/test_agent_runtime_interactions.py
NODE_PATH=/path/to/qa/node_modules CHROMIUM_EXECUTABLE=/path/to/chromium node tests/browser/batch1-connections.cjs
NODE_PATH=/path/to/qa/node_modules CHROMIUM_EXECUTABLE=/path/to/chromium node tests/browser/workspace-interactions.cjs
node tests/browser/chat-scroll-unit.cjs
```

Reused without restarting: resolved provider-loading investigation, prior full staging signup/fixture verification/login/cold catalog/project fallback journey, earlier same-name project/CSRF/ownership/file traversal/billing arithmetic evidence. No payment processor, bank or SMTP delivery was called. No new public staging URL exists.

**Unverified limits retained:** strictly greater OAuth expiry is required for automatic checkpoint (equal/decreased-expiry rotations require vendor-specific validation); one Gateway worker; no full OS isolation for OpenCode itself; actual vendor refresh and failed-refresh recovery, live Agent permissions/questions/streaming, final responsive/theme/GitHub browser journeys, native PostgreSQL constraints/races and real container preview remain OPEN/BLOCKED. Saved credentials survive restart; an unfinished in-memory OAuth handshake must be restarted after runtime restart.

**Preservation / readiness:** only additive or focused repair code; no broad legacy removal, schema/dependency/config/default-provider redesign, CSS redesign, billing/SMTP processing change, production secret read, customer-data operation, master/rollback/workflow change, VPS restart or deployment. No migrations or new settings required for these repairs. The immutable preview plan is not a deployed runner. **NOT RELEASE-READY**; the 18 requirements remain visible until their actual acceptance gates pass.

**Files in this repair round:** `app.js`, `backend/app/main.py`, `backend/app/routes/workspaces.py`, `backend/app/services/account_provider_sync.py`, `backend/app/services/customer_lifecycle.py`, `backend/app/services/opencode.py`, `backend/app/services/preview_runner.py`, `backend/app/services/providers.py`, `backend/app/services/user_provider_credentials.py`, `backend/tests/test_account_lifecycle_boundaries.py`, `backend/tests/test_agent_question_validation.py`, `backend/tests/test_agent_runtime_interactions.py`, `backend/tests/test_batch1_runtime_sync.py`, `backend/tests/test_oauth_account_sync.py`, `backend/tests/test_preview_detection.py`, `backend/tests/test_provider_revocation.py`, `backend/tests/test_retention_runtime.py`, `dashboards.js`, `docs/PRE_MERGE_VERIFICATION_GATE_2026-10-14.md`, `docs/PROJECT_HANDOFF_AND_REMAINING_WORK.md`, `enhancements.js`, `management.js`, `tests/browser/batch1-connections.cjs`, `tests/browser/chat-scroll-unit.cjs`, `tests/browser/workspace-interactions.cjs`, `tests/run_isolated_audit.py`.

## 15. 2026-10-14 — Delta only: runtime-aware Agent verification

Baseline `fba148b5e16e9055249fdb6958aa87bcba61512c`; the approved `4ce9d48` repairs are preserved. The existing checklist was read once; no audit restart or duplicate 18-stage plan. [Runtime inventory, exact root cause, commands and sanitized evidence](RUNTIME_AGENT_DIAGNOSIS_2026-10-14.md).

- **VERIFIED — original Agent HTTP 500 fixture:** `fixture/fixture` was absent from the native catalog; no request reached the loopback model. Verbose private fixture logs identified `ProviderModelNotFoundError` hidden by `UnknownError`. Fixture startup now configures the custom model and bundled Chat Completions adapter before discovery. Native pending approval → approve/execute, reject/no file and question → answer/continue passed (1 test, 7.12 s). No production provider/network settings changed.
- **VERIFIED — bounded Gateway backend interaction:** real Uvicorn/OpenCode/PGlite and synthetic streaming model exercise four messages in one session, approval blocking/accept/reject, single/multiple/custom questions, pending request restoration through a fresh authenticated HTTP client, duplicate replay/conflicting admission, foreign-user GET/decision denial, real activity, SSE cursor replay and auth revocation on logout. Last affected case: **1 passed / 0 failed / 0 skipped**, 16.28 s. This is backend persistence on client reload, not completed browser layout or OpenCode-process-restart recovery.
- **VERIFIED — connection lifetime correction:** preflight commits before dispatch for free as well as advanced models; background start/activity/finish SQL runs in worker-owned sessions; SSE releases the initial transaction and serializes each poll into detached values before yielding. Single-connection regression failed against the old endpoint and now passes (1 test, 0.79 s). Existing authorization, request-ID/cancellation and default-OFF approval rules preserved. Ten affected question/routine contracts passed; no unrelated full Python run.
- **Coordinated affected cycle:** native + Gateway HTTP + newly written internal recovery case produced **2 passed / 1 failed**, 21.32 s. The failure was the HTTP test checking command activity before the first question's completion. Corrected that cursor assertion and reran only the failed HTTP case (passed above). Prior OAuth/checkpoint/sync/retention and 76-pass Python evidence reused; not rerun. Intermediate diagnostics and PGlite rollback limits are retained in the linked report, never counted as production/native certification.
- **BLOCKED:** browser Composer/scroll/question-card acceptance (installed Chromium SIGSEGV on version probe); live GitHub import (product App/installation/user token absent); native PostgreSQL migration/concurrency acceptance (no server/container/non-root mapping); secure runnable Preview (no isolated engine/socket/proxy); real vendor OAuth/model reasoning (no authorized sandbox). Verified these resource limits once; no downloads or repeated infrastructure retries. Existing preview control-plane remains **IMPLEMENTED / UNVERIFIED** for runnable execution. External payment processing and activation-email delivery remain deferred.

Only the relevant existing checklist cells below are updated; all other requirements and previous evidence remain unchanged. Exact published source commits are recorded in an immediately following documentation commit. No master/rollback/workflow/production/configuration/visual/billing/SMTP changes, migrations, merge or deploy.

**VERIFIED — internal archived-account recovery delta:** new `backend/tests/test_reactivation_scope.py` passed in the coordinated affected cycle above. A manually seeded single-use recovery proof issues a renewal-only session; normal profile/workspace access and password completion stay denied until an already-confirmed paid entitlement is seeded in the disposable DB. Fresh password completion revokes that recovery session, permits normal login, preserves original trial dates and grants no second trial; another account stays active. No payment processing, SMTP/activation delivery or retention-cleanup test was invoked. This certifies internal scope/password/trial behavior, not external payment or email delivery, native concurrency or the complete archive/restore operational journey. Agent repair commit: `92f85280c43417554fa050db29858c2aeff7803b`.

**Published source commits for section 15:** Agent/runtime/HTTP/SSE repair `92f85280c43417554fa050db29858c2aeff7803b`; internal recovery regression `1868d0b0a66244dbd68deaeb9fb3b4a6e832b8dc`. Reviewed source tree `26b374ca26be321ad0f0c329e1de45f2873eed94`. This immediately following documentation commit records the exact SHAs. The three old successful OAuth/sync/retention tests and full Python suite were not rerun.

## 16. 2026-10-14 — Owner's 13-point execution order: Preview control plane

Baseline verified against origin `updates`: `c69653a278ad7eaf55a77c77faa401e042e52196`. Only delta work; resolved catalog investigation and unrelated 76-pass suite were not repeated. No dependency download, infrastructure retry, payment or SMTP call.

**Point 2 — IMPLEMENTED / UNVERIFIED overall; independent components verified.** Added an explicit dedicated-runner Protocol, immutable fixed-argv launch profiles and owned status/start/stop endpoints. Source snapshot export pins POSIX directory descriptors, rejects symlinks/hardlinks/special files and changing files, excludes known credential/config/dependency directories, bounds entries/depth/files/actual bytes and exports regular read-only members. This is a source export, not a secret-content scanner or a running container. Deep-copying nested limit values prevents accidental mutation of the shared API security contract. No client may enable execution, select a host command or loosen quotas. Start returns 503; Stop is idempotent. No engine, dependency install, process or port is started.

Preview frontend preserves the approved layout/CSS and adds Stop; clearing the iframe revokes local preview content and invalidates asynchronous responses, preventing a late result from reopening a stopped/changed preview. Framework status is truthful; an HTML filename field is hidden for dynamic applications. The static sandbox remains available without being advertised as Universal Preview.

**Evidence:** affected coordinated cycle includes 22 detection/profile/snapshot cases plus one real Gateway/disposable-DB Preview ownership case. Another valid account receives 404 on status/plan/start/stop. `node tests/browser/preview-controller-unit.cjs`: **3 passed**, testing late detection, late render after Stop and blocked dynamic status. These are VM behavior checks, not browser visual acceptance. `node --check dashboards.js` passed.

**Still OPEN/BLOCKED:** actual container adapter, controlled dependency-preparation images, quotas enforcement by an engine, isolated network/protected separate-origin routing, live health/bounded log streaming, expiry/crash cleanup and real multi-framework execution acceptance. No suitable engine/socket exists in this environment; no unsafe host fallback was introduced. A Docker installation alone does not make this feature complete. Bare React/Vue/Svelte dependencies without a server and arbitrary Python/Node entrypoints require explicit supported launch configuration; profiles do not prove an app is runnable.

**Files:** `backend/app/services/preview_runner.py`, `backend/app/services/preview_snapshot.py`, Preview endpoints in `backend/app/routes/workspaces.py`, `backend/tests/test_preview_detection.py`, `backend/tests/test_preview_api_boundaries.py`, `dashboards.js`, `tests/browser/preview-controller-unit.cjs`, this handoff. Exact publication SHA follows in the final record.

### Point 3 / point 7 delta — actual OpenCode process loss and live waiting execution

**Confirmed defect, repaired:** killing the native runtime while a permission was pending left its durable Gateway row `submitted` after a healthy restart. The new regression first failed on that exact status (1 failed, 8.17 s). Dispatch events now record runtime generation; reconciliation consults native status, pending permissions/questions and the matching request's message history. It never replays a prompt/tool. Surviving native waiters remain pending; a lost waiter becomes a bounded `failed`/`runtime_interrupted` state with preserved history and an explicit review-before-retry reason. A completed final text turn can be recovered as completed; a tool-only/incomplete step is not fabricated into a completed answer. Late callbacks cannot overwrite an already terminal execution.

**VERIFIED scope:** actual OpenCode 1.18.32 processes were killed/restarted during a bash approval and a question. History/user message IDs persisted, old decisions returned 404, the denied/unapproved file never appeared, exactly one interruption event was recorded. A separately completed native turn survived restart and was reconciled without duplicated messages. A live native question survived a credential change and a maintenance sweep unchanged: no process replacement/dispose while busy; answering continued execution; idle retry applied the new fake key without changing PID (**1 passed**, 5.86 s). These use the real native APIs/SQL and a deterministic loopback model, not a vendor refresh/paid reasoning claim.

**Limits:** native pending promises are process-local; automatic resumption after their process is killed is intentionally not claimed. The restart regressions seed a durable orphan dispatch to represent a lost Gateway observer and actually restart OpenCode; they do not certify SIGKILL/restart of the Gateway process itself. A hard-killed Gateway may leave a living native child holding its OS ownership lock: existing fail-closed multiworker protection must remain, and full supervisor/orphan-process acceptance is still OPEN. Interrupted admission before a durable dispatch also remains an explicit review/Stop case, not automatic replay. Browser card recovery/streaming remains blocked by the browser; actual vendor token streaming/refresh remains blocked by authorization.

**Files:** `backend/app/routes/agent.py`, session read in `backend/app/routes/workspaces.py`, `backend/app/services/opencode.py`, `backend/app/services/session_recovery.py`, `backend/tests/test_agent_restart_recovery.py`, this handoff. Exact source SHA recorded in the final publication entry.

### Point 4 — archival failure compensation; points 6/8 independent evidence

**Confirmed defect, repaired:** injected SQL commit failure reproduced loss of runtime files while the account/credentials/session transaction rolled back (1 failed, 1.08 s). Runtime storage now moves atomically into a private same-filesystem staging directory after shutdown, while project files remain untouched. Successful SQL commit precedes erasure; rollback restores storage. A lost commit acknowledgement is resolved from committed account status, never by blindly restoring archived secrets. Recovery of staged storage runs before the retention grace short-circuit: restore uncommitted transitions, erase committed archives, defer conflicting/active/unsafe/unknown paths. Cleanup failure remains staged for retry; it does not reactivate an archived account. The account runtime lock joins existing workspace/DB guards. No account policy/schema/payment/trial change.

**VERIFIED in disposable SQL:** rollback preserves credentials/auth sessions/runtime file; retry archives; crash simulation before/after commit restores/erases according to status; erasure failure retries; lost commit acknowledgement cannot restore archived secrets. Five new failure cases passed in the final affected addendum; the existing real-OpenCode retention/two-account cleanup case also passed in the coordinated cycle. Original internal reactivation/no-second-trial evidence is reused, not rerun. PGlite is preliminary compatibility evidence, not native transaction/concurrency acceptance.

**GitHub:** `backend/tests/test_github_boundaries.py`: **11 passed**. First-time mocked checks prove expired authorization makes no vendor request, repository/branch calls use the connected customer's token, foreign repo is rejected before branch lookup/clone-token extraction, and private/traversal/option-like import paths are rejected. No production GitHub code change was needed and no remote repository was read/changed by these tests. App installation/authorization/import/reconnect/reimport with a real authorized test repository remains BLOCKED by absent product App/installation/user authorization.

**Native database:** added executable `backend/tests/test_native_oauth_concurrency.py` for two concurrent encrypted CAS rotations (one winner, stale overwrite denied), gated to explicit disposable native PostgreSQL. It is **SKIPPED/BLOCKED here**, not certified. Existing native migration/identity/duplicate-connection tests remain available. No repeated PostgreSQL/container probe/install.

**Files:** `backend/app/services/customer_lifecycle.py`, `backend/app/services/archive_storage.py`, `backend/tests/test_archive_failure_recovery.py`, `backend/tests/test_github_boundaries.py`, `backend/tests/test_native_oauth_concurrency.py`, this handoff. Exact published source SHA follows in the final entry.

### 13-point final evidence and publication

Source commits: Preview `e1642af9f5865ba931e6275e0e8f949e68cd9d12`; native recovery `5b99a5e52433c55e34d78c0487f0acc28e16bf91`; archive/boundary tests `0df9b4a6679a6359c258cfb5ec66b155faa2875d`. Source tree `60e439653341ea689e526c1526322d59ffdd29a0` matches the reviewed local commits exactly. [All 13 points, exact commands/counts, files/commits and remaining gates](FINAL_13_POINT_DELTA_2026-10-14.md).

Coordinated available changed/dependent cycle: **56 PASSED / 0 FAILED / 1 SKIPPED**, 62.92 s (native CAS blocked). New live native waiting-request synchronization: **1 PASSED**, 5.86 s. Final changed-only safety addendum: **8 PASSED**, 22.17 s (five archive failure cases plus three real native restart/history cases). Node preview behavior: **3 PASSED**, not visual acceptance. Syntax/compile/diff checks passed. These overlap; do not sum into a fabricated independent suite. The old successful runtime-sync/retention/Gateway HTTP checks were rerun only because initialization, archive and dispatch changed; other valid historical evidence was reused.

No new unresolved failed test in executed scope. **Not all 13 items or 18 stages are certified complete.** Real Preview execution is still incomplete/blocked; real browser, native DB, vendor OAuth and product GitHub authorization gates remain blocked. Whole Gateway SIGKILL/orphan-child and pre-dispatch recovery are still unverified, distinct from verified OpenCode restart handling. External payment and activation-email delivery are **DEFERRED — MAIN SERVER**, unchanged. Ready for controlled local acceptance with disposable infrastructure; **NOT RELEASE-READY**. Only `updates` is published; no merge or deploy.

## 17. 2026-10-15 — Corrected TEST functional scope (six requirements only)

Baseline `updates` verified/fetched at `d7ddb59311a65a3416e4402fb4b4c2707a3c99cd`, incorporating six upstream commits since `73e97ba` without overwriting them. Owner corrections on 2026-10-15 explicitly remove workspace deletion restrictions, customer permission changes and workflow protection from this round. An attempted file-retention change and its tests were withdrawn; final diff contains **no deletion/retention/policy/workflow changes**. Only the six functional requirements below remain. Models/provider connections already work; preserve validation/OAuth/credential logic and improve discovery latency/display capacity only.

- **Preview — BLOCKED / unchanged execution gate.** Existing static preview, disabled dynamic runner contract and security guards preserved. No verified isolated engine/runner, controlled preparation or protected separate-origin proxy is available to this workspace. Actual TEST runner availability cannot be inspected without authorized server access. Dynamic Node/Python start/stop/logs/browser execution is NOT completed or demonstrated; no host-shell fallback or guessed new startup command was added.
- **Todo — implemented and locally verified; TEST acceptance pending.** Root cause: upstream `app.js` pinned panel and `dashboards.js` chat panel both requested/rendered the same session Todos. Removed only the duplicate chat renderer after checking all callers; one native API-backed `<details>` panel immediately precedes composer, with existing CSS order 9 vs composer order 10. Collapsed on session change, progress/states, single arrow, read-only history, stale/ABA response guards and single-flight requests retained. Session close/workspace change/logout clears the view; it does not alter messages.
- **Provider list — implemented and locally verified; TEST/browser timing pending.** Initial account response now includes **50 actual providers**, connected/popular first, with 50-item UI increments and full-catalog search/pagination (native catalog here reports 223). Browser gets index/counts, not every model schema; the installed native `/provider` itself returns its model metadata and remains the cold-start cost. Composer/default provider selection rules and actual connection logic remain intact. Global catalog lock no longer covers upstream HTTP for other users; TTL 30 seconds, generation+revision isolation, copies and bounded cache preserved.
- **Auth method latency — implemented and locally verified; TEST timing pending.** Opening read-only method metadata previously spawned a new temporary validation runtime and fetched its catalog. It now reuses that account's dedicated runtime/core cache, caches method schema for 60 seconds and invalidates on runtime discovery changes. `/provider/auth` and native integration schema remain authoritative. A fresh isolated validation runtime is **still used by actual API-key validation/connect**; no key-validation/OAuth/ownership/security checks were bypassed. Integration retry HTTP is bounded within its discovery budget; no blanket timeout increase.
- **Agent choices — implemented and locally verified; TEST visual acceptance pending.** Reused existing selectable question cards, single/multi/custom answers and native authenticated continuation API. Explicit native `(Recommended)` / `(موصى به)` labels, in addition to actual boolean metadata, mark a recommendation; only agent-supplied description explains it. No default selection. Action is “Choose and Continue”; pending/duplicate-click, stale response/session and expired question handling improved, existing permissions unchanged.
- **Login — implemented and locally verified; TEST/social acceptance pending.** Root cause: login, restored-session navigation, `openClientWorkspace` override and social-success paths differed; old code did not persist/reopen conversation. They now share a single-flight owned restoration route. Backend selects preferred accessible owned/nonarchived workspace or last-activity fallback, visible owned conversation, no runtime/files/project creation. Owner-keyed browser context persists session selection, native conversation is checked before opening, missing history leaves the Workspace available, new customers see Workspace Home and admin routing stays unchanged. Actual username/email login → same owned native conversation passed; external Google/GitHub sign-in is not certified here.

**Actual selective results:** 17 offline catalog-isolation/revision/concurrency/method-cache/question/route contracts passed (0.75 s); two new disposable context/isolation cases plus updated native provider-performance case **3 passed** (6.19 s); actual native Todo update → explicit recommendation → answer/resume → duplicate rejection → username/email login/context restoration **1 passed** (6.23 s). `node tests/browser/test-workspace-ui-unit.cjs`: **11 passed** (3 Todo lifecycle, 3 answer/duplicate/expiry, 5 login/shared-flow cases), VM behavioral evidence, not browser visual proof. Python compilation, changed JS parser checks and diff whitespace passed. Earlier overlapping runs are not summed. No unchanged full Python/browser suite rerun. Old OAuth/revocation/retention/Preview evidence reused with its original limitations.

**External-request review:** automatic approval review rejected observation of the initial native metadata test after OpenCode attempted `models.opencode.ai` refresh. No workaround to that request was used. Inspected the installed 1.18.32 binary's supported `OPENCODE_DISABLE_MODELS_FETCH` condition (disables fallback and hourly refresh), injected it only into disposable test child environments, and reran the affected tests using the actual bundled runtime catalog. Accepted performance evidence comes from that network-disabled run; no production env/binary/global version was altered. Model execution uses a deterministic loopback fixture; no paid vendor call/payment/SMTP delivery.

**Measured local Gateway/native latency:** 223 providers; 50 initially displayed; cold catalog 3547.21 ms; three warm catalog calls 15.61/26.09/16.69 ms. Warm method calls: DeepSeek 14.32, Google 16.66, OpenAI 15.79, Together AI 13.90 ms. Cold native health-ready 2020.29 ms and `/provider` 1478.83 ms explain initial cost. [Sanitized actual measurements](audit/2026-10-15-provider-performance.json). Browser-only `window.gatewayProviderTimings` records request and synchronous DOM-render duration separately for later TEST verification; it contains no credentials/owner IDs and sends no telemetry. Actual frontend/browser latency remains UNVERIFIED.

**TEST delivery gate:** existing `deploy-updates-test.yml` is unchanged; its current version checks TEST DB `opencode_gateway_test`, API 8001, OpenCode 4097, `/var/lib/opencode-workspaces-test` and `/var/lib/opencode-runtime-test`, creates code/pg_dump backups and validates the dump before additive deployment/migration/restart. Historical run `38725480375` (older source `8c840aca`) succeeded, including isolation/backup/HTTPS steps; it is not proof of this repair's deployment. Do not rerun that old workflow version: it predates the additive/no-delete correction. Connector supports reads/reruns but no new dispatch; CLI SSH/GitHub auth is unavailable and cloud GitHub browser is signed out. New source must be deployed from **updates** with the existing `promote-test` workflow after authorized sign-in; no production fallback.

Cloud browser loaded the public TEST page over HTTPS. Direct shell TEST health was blocked by proxy timeout; direct cloud navigation to `/api/health` was blocked by client policy. These are access limitations, not evidence of a TEST outage. No authenticated TEST login/project/Workspace check, new server backup, deployment, runtime-path/DB inspection or responsive visual acceptance is claimed. Read-only workflow source/history is not live server access. Exact published repair SHA will be recorded in the following documentation entry. No master merge, Live/VPS restart, production DB operation, workflow change, installed OpenCode upgrade, real payment/email or existing customer-data mutation.


**Published repair source:** `38e3fcf2d03ab52a2a1626cdbe11dc39d69817f1` (parent `d7ddb59311a65a3416e4402fb4b4c2707a3c99cd`). This documentation follow-up records the immutable source SHA; TEST dispatch/acceptance remains pending as described above.


## 18. 2026-10-15 — Owner screenshot follow-up: project folders and live follow-scroll

Baseline `updates`: `8c57d0e5754b54b381c591a063a7fd8830634a5f` (includes section 17 repairs). Inspected both owner screenshots successfully. Only the additional approved sidebar/scroll behavior is changed; the six TEST requirements remain open at their previously documented acceptance gates.

**Project folders — implemented / local behavioral verification; TEST visual pending.** Two expandable folder groups: Local projects (yellow folder SVG) and GitHub projects (site-theme folder SVG). Each project is itself an expandable folder instead of a flat navigation link/card. Active project retains its existing file/change controls; other projects lazily load the existing authenticated `/api/workspaces/{id}/files` endpoint on expand, with one in-flight request and retry after errors. Nested trees retain the specific folder's workspace ID even while a different workspace/conversation is active; owner changes and removed nodes discard late results. Expanding a folder does not switch projects, create data, clone repositories or fetch file contents. Existing GitHub policy is preserved: authorized repository/branch, shallow single-branch working copy, optional up-to-ten sparse directories, existing quotas/path restrictions and GitHub credential/branch rules. The user's reference to GitHub snapshots is represented by these actual authorized working-copy files, not fabricated screenshots or full-repository downloads. No GitHub backend, upload, quota, data or permission policy change.

**Live follow-scroll — implemented / local behavioral verification; TEST visual pending.** Confirmed root causes: follow-tail ran only at the end of message rerender, while real activity/questions/approvals can append or resize later; sending-preview reinsertion could also forcibly scroll a reader. A single animation-frame scheduler now observes chat subtree mutations and child/feed resizing, follows growth while following is enabled, and preserves the reader's position after upward scrolling. Jump to latest and an explicit new submission resume following; newly opened conversations reset follow mode. Removed unconditional scrollIntoView on pending-preview reinsertion. The jump button was viewport-fixed over the sidebar in the owner screenshot; it now belongs to the chat column's layout, above the composer/Todo, using logical responsive positioning. No message history, execution/approval, session persistence, Agent/API or model logic changed.

**Actual targeted results:** `node tests/browser/test-project-folders-scroll.cjs`: **11 PASSED / 0 FAILED / 0 SKIPPED** (five follow-tail/reading/resize/queued-cancellation cases; six lazy-folder/single-flight/retry/owner-change/detached-node/correct-workspace cases). `node tests/browser/test-workspace-ui-unit.cjs`: **11 PASSED / 0 FAILED / 0 SKIPPED**, rerun because shared frontend files changed (Todo, choices, login). Both are VM DOM behavioral fixtures, **not real browser visual proof**. `node --check app.js`, `node --check dashboards.js`, `git diff --check` passed. Previous native provider/Todo/question/login, security, GitHub boundary and unrelated Python evidence remains reused; no backend changes justify rerunning it.

**Changed files:** `app.js`, `dashboards.js`, `styles.css`, `tests/browser/test-project-folders-scroll.cjs`, this handoff. Exact source publication SHA is recorded in the following documentation entry. TEST deployment/browser acceptance remains BLOCKED by unavailable authenticated workflow dispatch access, as in section 17; no new deployment or backup is claimed. No master/workflow/production/rollback/database/data mutation. Next: new existing-workflow TEST dispatch at current updates, then demonstrate folders, mobile RTL/LTR, streaming/activity growth, history reading and Jump to latest using authenticated TEST sessions. Dynamic Preview remains separately BLOCKED.


**Published folder/scroll source:** `5c889f5d7122bd5162ee87b49e77e7d4c2360319` (parent `8c57d0e5754b54b381c591a063a7fd8830634a5f`). Local source tree `de68fe45197604f73b69d6491c019a37fb648da6` matched the GitHub tree before publication. TEST deployment and real-browser acceptance remain pending; all preceding limitations stay open.


## 19. 2026-10-15 — Owner reference screenshots: Workspace and formatted Agent replies

Baseline `updates` `0ef58f209b512e3a227c6b3c58a6e073280e9af7`. Read all four new reference screenshots. This is the owner's explicit visual follow-up, not an architecture replacement. Existing sidebars, yellow Local/GitHub folders, safe follow-scroll, inline question/approval cards, default collapsed native Todo and connection/submission/security handlers remain intact.

**Implemented / TEST visual acceptance pending:** wider 1000px maximum conversation/composer, quiet theme-derived canvas, thin composer border without resting shadow, unified compact icons and rounded-square Send, slightly taller text entry while controls remain one row. Empty Workspace heading/composer use centered welcome spacing; this does not create a project or change Workspace Home/no-project behavior. Replaced the viewport-only 700px composer-choice breakpoint with the actual chat column's 680px container breakpoint, preserving the same existing selection popover and keyboard/click handlers when side panels narrow the conversation. Retained English/Arabic fonts and logical properties, dark/light site tokens, genuine runtime progress and all existing integrations; no unavailable connector logos or fake tasks/content added.

**Agent reply formatting:** assistant text now uses a small DOM-only Markdown subset: paragraphs, headings, ordered/unordered lists, bold, inline code and fenced code with language header and Copy. Unclosed streaming fences are rendered as text code until completed. Raw response remains the source for full-message Copy/regeneration and stored history; user text remains plain. No HTML interpretation, remote image/link loading, syntax-highlighter, new dependency or execution. Unsupported Markdown (including tables and links) remains literal text. This is readable formatting, not a claim of a complete Markdown implementation or screenshot-perfect parity.

**Actual selective evidence:** `node tests/browser/test-agent-text.cjs`: **6 PASSED / 0 FAILED / 0 SKIPPED**, including actual DOM-renderer formatting, exact code copy payload, hostile HTML/URL inertness, unfinished fence, bounded language label and incomplete inline tokens. `node tests/browser/test-project-folders-scroll.cjs`: **11 PASSED / 0 FAILED / 0 SKIPPED**, rerun for changed chat layout/render dependencies; VM behavior, not browser geometry/streaming acceptance. JS parser checks and `git diff --check` passed. Optional CSS parser check was **BLOCKED** (`tinycss2` is not installed); no dependency was downloaded and no CSS parser success is claimed. Existing Todo/question/login/backend evidence remains reused; no backend/data/auth code changed.

**Files:** `app.js`, `styles.css`, `tests/browser/test-agent-text.cjs`, this handoff. Source SHA recorded by the following documentation entry. New authenticated TEST deployment and desktop/mobile RTL/LTR/dark/light visual checks remain pending for the same workflow-access blocker in sections 17–18. These source changes are not yet demonstrated on TEST. No production, master, workflow, rollback, PostgreSQL or installed runtime modification; no external payment/email transaction. Dynamic execution Preview remains separately blocked.


**Published reference-style source:** `5141ff29eff2ace1e486dccde4f04f24da4628db` (parent `0ef58f209b512e3a227c6b3c58a6e073280e9af7`). Exact source tree matches the reviewed local implementation. Publication does not certify TEST deployment or visual acceptance.


## 20. 2026-10-15 — Quiet dividers, project/Preview styling and visual samples

Baseline `updates`: `b752a33591740036ff651a878361a8b03940d844`. Owner supplied three additional Arena reference screenshots and explicitly requested quiet division lines/boxes, preserving Gateway colors, plus visual examples. The owner then explicitly extended the request to soften edges/separators throughout the project. Workspace project/files/Preview get the described presentation refinements; shared border/shadow tokens are softened across other pages without changing Auth/account structure, fields, colors, focus/selected/error states or backend behavior.

**Implemented / TEST visual acceptance pending:** Workspace separators derive from existing text/panel colors at 10% and control surfaces at 14%. Other existing light/dark line/control/auth/account border hex tokens are blended at 70% with their corresponding existing panel backgrounds, and the shared resting shadow is lighter. Primary, text, background, dark/light theme identities and focus/status colors remain unchanged. File rows are transparent by default with existing hover/selected states; section headers lose heavy fills/bold weight, panel corners are smaller. Preview controls retain the original five DOM buttons/IDs/onclick handlers, static preview/Start/Stop/refresh/fullscreen/new-tab and fail-closed runner behavior, now in a compact wrapping path/icon toolbar with accessible labels/tooltips. No execution/security policy or backend modification. Actual Node/Python execution remains separately BLOCKED, not solved by these visual changes.

**Visual deliverable:** `docs/audit/workspace-visual-samples-2026-10-15.html` is self-contained with the current repository stylesheet and embedded existing Arabic font. Three view controls show conversation, Local/GitHub folder organization and Preview panel, plus theme and RTL/LTR toggles. It is clearly marked **visual examples only, not TEST**, with illustrative names/content isolated to this documentation file, no API/account/network/real data access, and disabled execution/submission. It is not a screenshot or proof of runtime acceptance, and no demo data was inserted into the application/database.

**Actual targeted evidence:** existing `node tests/browser/preview-controller-unit.cjs`: **3 PASSED / 0 FAILED / 0 SKIPPED** (late detection/render after Stop and truthful disabled dynamic runner) after touching Preview markup. `node tests/browser/test-agent-text.cjs`: **6 PASSED / 0 FAILED / 0 SKIPPED** retained from this refinement round. `node --check dashboards.js`, HTML parsing/unique IDs/offline-script checks, syntax check of the sample's extracted script and `git diff --check` passed. These are behavioral/parser evidence, not a rendered desktop/mobile screenshot or TEST acceptance. CSS parser and real browser gates from section 19 remain open. Unchanged full suites/native service tests were not repeated.

**Files:** `dashboards.js`, `styles.css`, visual HTML above, this handoff. Exact published source SHA is recorded in the following documentation entry. Code is published only to updates. New TEST dispatch still needs an authenticated authorized GitHub browser session; connector cannot dispatch, and the browser shows GitHub sign-in. No new backup, deployment, production/master/workflow/rollback/database/secret change is claimed. After approved existing-workflow TEST deployment, demonstrate actual folder expansion, quiet borders, toolbar keyboard/labels, iframe/fullscreen/Stop, narrow chat selection popup, themes/RTL and follow-scroll with real messages.


**Published quiet-border/Preview source:** `2d18d8e5a1c417db19f949d444ce7f237d0045f6` (parent `b752a33591740036ff651a878361a8b03940d844`). GitHub source tree matches the reviewed local source. The visual HTML is an illustrative offline artifact, not TEST deployment evidence.

**TEST access outcome:** secure GitHub browser authentication was offered for the existing TEST workflow; the result was `declined`. No repeated credential request, workflow dispatch, backup or deployment was performed. The owner's last sidebar image confirms local project folders and linked GitHub project folders; the delivered visual examples show both with their own nested working-copy files. Public TEST remains a previous build until a separately completed authorized TEST deployment.


## 21. 2026-10-15 — Owner clarification: framed file sections

Baseline `updates` `8bc2833c19bd08cf38a0cdcce0ef35a2bbdaeadc`. Both new screenshots confirm that each complete sidebar section should have its own quiet rectangular outline, not that all section outlines should disappear. Local projects and GitHub projects now each have a 1px theme-derived outer border, 8px corners, padded title and a thin divider below the expanded header. Folder/file rows stay unboxed inside each section, yellow Local folders and GitHub folders retain their behavior, and each group remains collapsible. No individual project/file cards, extra panels, data, API or workflow changes.

Updated the existing self-contained visual sample with the actual changed stylesheet. `git diff --check` and sample HTML parsing passed. This CSS-only adjustment needs visual acceptance, not a repeat of unchanged Python/Agent/provider suites; their valid evidence is reused. Actual browser layout on TEST remains UNVERIFIED because the previously declined GitHub sign-in blocks new TEST dispatch. No authentication retry, deployment or production change. Changed files: `styles.css`, `docs/audit/workspace-visual-samples-2026-10-15.html`, this handoff. Exact published source SHA follows in the documentation entry.


**Published framed-section source:** `30a2db5466d93f088bafaf4eb74c56c051fc5822` (parent `8bc2833c19bd08cf38a0cdcce0ef35a2bbdaeadc`); source tree matches the reviewed local CSS/sample update. TEST deployment and visual acceptance remain pending.


## 22. 2026-10-15 — Apply reference presentation in existing Workspace position

Actual origin `updates` was fetched at `3291960` before changes. Ten upstream commits were incorporated by fast-forward, including the owner's three-file rollback of the experimental three-column layout. That HEAD's frontend matches the prior stable source. **Do not restore the rejected layout experiment.** Owner now asks to apply the image's visual presentation carefully and keep conversations as plain text titles; a follow-up explicitly requests calm borders in all sections.

Changed the existing file/project panel in place: Workspace heading, native current-workspace storage in its section header, existing refresh button moved intact to that header, direct expanded project file tree without a redundant nested Project files header, independent GitHub section with a plus button using the existing authorized repository picker, restrained folder indentation/chevrons. The storage node/refresh button remain unique and move to the active project's Local/GitHub section; stale prior-workspace storage is hidden until the existing API returns. No fabricated file totals. Conversation titles retain their existing click/open/current-session logic and text rows, with quiet selected indication. No rail, dashboard navigation, preview position, header, API/session/business or backend change. Actual running Node/Python Preview remains a separate blocked gate.

All existing general/control/Auth/account border tokens now use a consistent low-contrast text-to-panel mix in light/dark themes; primary/focus/status colors remain unchanged. No universal selector that hides borders or removes focus styles. Updated the clearly labelled offline visual HTML using current CSS, reference section headers and selectable illustrative conversation titles in the existing sidebar tab. It is not a TEST screenshot or a working account/Agent demo.

**Actual targeted results:** `node tests/browser/test-reference-panel.cjs`: **4 PASSED / 0 FAILED / 0 SKIPPED** (unique storage/refresh placement, actual storage payload rendering, original GitHub action, two text conversation titles with same-session navigation). Related `test-project-folders-scroll.cjs`: **11 passed**; `test-workspace-ui-unit.cjs`: **11 passed**; `preview-controller-unit.cjs`: **3 passed**. These are VM behavioral regressions, not browser layout verification. `node --check dashboards.js`, sample script/HTML parser checks and `git diff --check` passed. Existing backend/service/native evidence reused; no dependency installation or blocked browser/database retry. TEST visual acceptance remains pending; GitHub browser sign-in was previously declined, so no repeated sign-in/deployment attempt.

**Files:** `dashboards.js`, `styles.css`, `tests/browser/test-reference-panel.cjs`, existing visual sample HTML and this handoff. Source SHA follows in the publication entry. No master/rollback/workflow/production/environment/database operation; updates only. Next: authorized existing-workflow TEST deployment and actual desktop/mobile, RTL/LTR, dark/light acceptance in the unchanged panel position. Pixel-identical parity is not certified by local code changes.


## 23. 2026-10-15 22:35–22:41 Aden — Explicit image reapproval / Workspace-only reference layout

**Owner superseding clarification:** after section 22's initial in-place work, the owner attached the generated OpenCode Gateway reference again and explicitly required the image's full layout, then requested header hiding only inside Workspace, OpenCode branding on the left and GitHub branding above the existing Projects/Preview/Conversations controls. This specifically authorizes the three-zone **Workspace-only** presentation; it does not authorize altering Dashboard navigation or reinstating the rejected unrelated experimental changes. The remote baseline remains `3291960f811e4850e1ebb0dc10270f0b7e23950a`. Section 22's initial in-place-only layout description is superseded by this entry, within one unpublished implementation round.

**Implemented / browser acceptance pending:** a Workspace-local left conversation rail moves the **existing** session section/list/search/filter/new-conversation button intact, with one native list and text-only titles. No duplicate session data, new backend or permission policy. Search/filter remain in a collapsed disclosure; actual lifecycle/menu/archived/current/open behavior remains. The right project/Preview panel retains existing ownership-bound file trees, native current-project storage/refresh, GitHub repository picker, preview controls and resizer. Its Conversations button opens the same left rail; it does not create a duplicate panel. OpenCode brand is left; GitHub brand is above right controls. Only active Workspace hides the global header using a page-scoped CSS condition; leaving Workspace restores the existing Dashboard/other-page header and navigation DOM. Added real-user initial/native OpenCode message avatar presentation, kept raw message text/actions, native approvals/questions/Todo/streaming. No fabricated timestamps or syntax highlighting claims.

Desktop layout follows reference left/conversation/right physically in both text directions; children retain Arabic RTL/English LTR. At <=1100px the project panel uses the existing drawer; at <=700px conversation rail also uses a closable drawer. Resize bounds preserve central chat width. Selecting an authorized conversation closes the narrow-screen rail; auth-clear closes it and retains existing clearing behavior. Settings goes to existing Connections. Actual provider/model/Send/Stop controls, session counts and file data stay native; no illustrative project/chat content enters the application.

**Actual final targeted regression cycle:** `node tests/browser/test-reference-panel.cjs` **5 passed**, including single existing list relocation and original controls/project/Preview remaining intact; `test-workspace-ui-unit.cjs` **11 passed**; `test-project-folders-scroll.cjs` **11 passed**; `test-agent-text.cjs` **6 passed**; `preview-controller-unit.cjs` **3 passed**. Total in these five distinct scripts: **36 PASSED / 0 FAILED / 0 SKIPPED**, VM DOM behavior only, not native/browser layout acceptance. Changed app/dashboard JS syntax, sample HTML/extracted-script parsing and whitespace checks passed. No unchanged Python/native suites rerun. CSS/native browser and authenticated TEST deployment remain unverified as previously documented; no claim of 100% pixel parity.

Offline visual HTML now shows the actual three-zone classes/current CSS, left title list and right project sections; it is marked not TEST and is not execution evidence. Remaining acceptance: actual desktop dimensions vs owner image, narrow/mobile drawers/resizer, keyboard menus, RTL/LTR/themes, auth/navigation restoration and real Agent/Preview flows on authorized TEST. Dynamic runner remains separately BLOCKED. No workflow/master/rollback-branch/production/database/secrets change or deployment. Exact published implementation SHA follows in the documentation entry.


**22:43 owner reminder / final presentation detail:** native Agent output keeps plain replies, the OpenCode avatar and DOM-safe code blocks/Copy; the work-status indicator animates only for actual running/submitted/search/edit/test events, not completed/failed/approval waits, and resets on session change (reduced-motion respected). Composer keeps the original textarea, attachment and Agent/provider/model/Send/Stop controls, with small decorative selection icons and one toolbar. Existing GitHub/tools buttons move intact to the right project header; they are not deleted or rewired. Initial Preview is hidden until its existing tab is selected, avoiding duplicate visible sections. No fabricated timestamps/file totals, paid requests or Agent execution changes. All 36 targeted VM cases above passed on the final code; JS syntax/whitespace passed. The reference HTML embeds the final stylesheet. Actual browser acceptance is still required before asserting screenshot-exact parity.


**Published reference implementation:** `404c6576b3df35f8f651bc9db822ca70123c35f0` (parent `3291960f811e4850e1ebb0dc10270f0b7e23950a`, source tree `f4710e07985d483d8d85b539292ca39f956a93c3`). The owner requested a before/after image; any generated comparison is explicitly conceptual and must not be substituted for screenshots/browser acceptance of TEST. No new deployment or sign-in is claimed.


## 24. 2026-10-15 — Actual Preview failure acknowledged; truthful controls and full panel

Baseline verified/fetched `8e005a9b93cd275706d5d5eea00f1a24aee8906a`; clean updates. Owner's mobile screenshot shows detected Node and unavailable isolated runner. This is **not a working application preview** and not visual acceptance of the sample. Confirmed source: `preview_runner.status()` unconditionally reports `runner_available=False`; `start()` unconditionally raises HTTP503. There is no connected execution implementation to enable merely through CSS or deployment. Gateway only detects frameworks/serves static HTML. Docker/Podman executables and their standard sockets are absent in this disposable environment. TEST runner/server availability was not inspected; no server access is claimed. No unsafe host process fallback was added.

**Small frontend repairs, implemented / VM verified:** preview now occupies available panel space rather than a short floating status card; consistent quiet title/toolbar/canvas. Native iframe sandbox and original controls/handlers retained. Loading/blocked/ready/error states expose accessible status and busy indicators. Fullscreen/new-tab are disabled until actual static content is ready; Start is disabled for known unavailable dynamic execution, while Refresh can recheck availability and Stop can cancel an in-flight request. Workspace switch resets previous status and stale responses cannot restore another project's frame. Existing offline visual sample uses the same canvas styles, remains explicitly illustrative, and is not evidence of TEST deployment.

**Actual selective results:** `node tests/browser/preview-controller-unit.cjs`: **7 PASSED / 0 FAILED / 0 SKIPPED**, including three retained stale/Stop/blocked cases plus static readiness/control state, error recovery, refresh after blocked discovery and workspace-change response rejection. `node tests/browser/test-reference-panel.cjs`: **5 PASSED / 0 FAILED / 0 SKIPPED**, relevant panel relocation regression only. These are VM behavioral tests, not browser screenshots. `node --check dashboards.js` and `git diff --check` passed. Unchanged provider, OAuth, backend, Todo and full suites reused rather than rerun. Browser rendered geometry/mobile/RTL acceptance remains UNVERIFIED.

**Actual runnable Preview remains BLOCKED, not fixed.** Requires separately accepted unprivileged runner/service with bounded prepared snapshots, CPU/memory/disk/process/time enforcement, controlled dependency preparation, no host secrets/socket, restricted networking, tenant/project leases, protected separate-origin authenticated routing and stop/reaping. Existing runner protocol/profile definitions are advisory, not an execution service. Once available, implement and verify Node and Python start/status/logs/stop plus cross-tenant routing using real TEST projects. Enabling a flag alone will not implement it. No new TEST dispatch/backup/deployment, production/master/rollback/workflow/environment/database/customer-data change. Source publication SHA follows.

**Changed files:** `dashboards.js`, `styles.css`, `tests/browser/preview-controller-unit.cjs`, `docs/audit/workspace-visual-samples-2026-10-15.html`, this handoff.


**Published Preview follow-up source:** `9e6f0ef241cd0d8a6fdc8d18f6ed604664a47c17` (parent `8e005a9b93cd275706d5d5eea00f1a24aee8906a`, reviewed source tree `f82294fa8f746ca12791cd0f3358fdf9737f534c`). 12 targeted VM checks passed; runnable Node/Python Preview remains BLOCKED and real TEST visual acceptance UNVERIFIED. No deployment performed.


## 25. 2026-10-15 — Owner TEST screenshot: generic Agent activity lacks detail

Baseline `6818c313cab7925195da97447a76b8adc1146218`, current origin verified. Screenshot shows three versions of generic Run command (tool row, live status, generic summary), no actual command/progress detail. Source confirms Gateway intentionally reduces shell commands to executable only; live UI discards all activity fields except tool/status; observer deduplicates by id/status so later enriched metadata is lost. This is a functional display defect, not evidence that the illustrated mockup's progress was implemented.

**Implemented / targeted unit verification:** expose only a small explicit allowlist of complete command shapes (`npm run build`, package-manager test/lint/check, `pytest -q`, `python -m pytest`, selected git/go/cargo checks). Other previously allowed executable names stay executable-only, explicitly marked arguments hidden; no arbitrary shell arguments, script bodies, command output, descriptions/reasoning, secrets or new host paths are emitted. Existing private-file/owned-root filters remain. Actual native exit code and duration are included only when present with valid types in completed/error state. Live status displays safe command/files/result/time, message tool history uses separate LTR code lines and result metadata. Removed only redundant generic tools summary; actual changed/read file summary remains. Observer deduplicates the complete sanitized snapshot so newly available details can arrive while status stays running, and identical observations are still suppressed. No execution/submission, approval blocking, authorization, model/provider, DB schema, session ownership or message history changes.

**Actual selective evidence:** `/workspace/scratch/bd2189746f7a/backend-test/bin/python -m pytest backend/tests/test_tool_activity_details.py backend/tests/test_agent_event_pool.py -q`: **8 PASSED / 0 FAILED / 0 SKIPPED**, 0.84s (seven new metadata/secret/path/result/observer tests plus retained stream DB-pool regression). Observer is a controlled fixture, not a real OpenCode run. `node tests/browser/test-activity-details.cjs`: **4 PASSED**, live/detail/history/restricted-command/inert-text/no-generic-duplication VM behavior. `node tests/browser/test-reference-panel.cjs`: **5 PASSED**, panel regression. **17 passing tests across these three commands**, no fabricated native/TEST acceptance. Python compile, JS syntax and diff-whitespace passed; no unchanged full suite or paid model call. Default shell Python lacks pytest; reused existing backend-test environment instead of installing anything.

**Files:** `backend/app/routes/agent.py`, `dashboards.js`, `styles.css`, new `backend/tests/test_tool_activity_details.py`, new `tests/browser/test-activity-details.cjs`, this handoff. Source SHA follows publication. **Remaining:** authenticated TEST deployment and real Agent run/browser acceptance, including Arabic mobile code wrapping and actual runtime exit/time fields. Unmatched/compound commands intentionally remain restricted summaries, not full raw command output. No claim of full terminal logs or pixel-perfect screenshot match. Existing Node/Python runnable Preview remains BLOCKED as section24; no new workflow/master/production/database/secret/deployment operation.


**23:14 Aden owner extension — step reports, repair and final report:** added per-request native `system` execution-reporting guidance: concise user-language updates before meaningful steps, observed results, native Todos when available, explain errors and attempt safe authorized corrections, targeted recheck only after a correction, final changes/checks/errors/blockers report. Never override selected Plan/Build role, project rules, pending approvals/questions or rejection, never blindly replay a failed submission. Original user text, attachments, model and agent selection remain unchanged. Installed local OpenCode SDK's prompt body explicitly supports `system` (verified in bundled executable; no binary upgrade). This guides model behavior, not a guarantee of compliance or real model acceptance. Actual progress still comes from native messages/tool metadata, not fabricated Gateway narratives.

Affected extension checks: two new controlled dispatch tests preserve user/model/agent fields and permission settings and prove a failed dispatch is not automatically resubmitted. Final affected Python command now **10 PASSED / 0 FAILED / 0 SKIPPED** (replaces, overlaps the earlier 8); frontend evidence remains 4+5 passing. Real TEST/model narration, autonomous correction and final-report compliance still require authorized runtime/browser acceptance. No external model request was made here.


**Published Agent reporting source:** `4c8725f72a9942864c3ace77cf03cf18f2097751` (parent `6818c313cab7925195da97447a76b8adc1146218`, exact reviewed tree `31ba69e9a51676fe38a9670d9bce20cea4e6b55e`). Final selective evidence: 10 Python + 4 activity VM + 5 panel VM checks passed; no real model/TEST/browser acceptance or deployment claimed.


## 26. 2026-10-16 — Owner-approved compact Login mockup

Baseline verified/fetched clean `updates` at `6a47dd1e2babd9ea95c840fdd22a61baeed24995`. Owner approved the desktop/mobile mockup, then explicitly superseded preserving old benefit icons: use the new laptop/GitHub branch/API key/calendar icons. Four benefits explain browser OpenCode without installation, GitHub work across devices, personal provider keys and one email-verified 30-day platform trial. The owner's free-month wording is scoped to platform subscription fees, not free external provider usage; trial/payment/limits are unchanged. No new pricing/50-project promise or Preview execution claim.

**Implemented / local behavior verified, visual acceptance pending:** narrower form and equal-height fields, desktop form left/info right in both languages with correct text direction, quiet blue site colors/light-dark tokens, four benefits without extra brand/repeated headings, original login/register tabs retained with underline styling. Original OAuth buttons/icons/callbacks are circular with translated accessible names retained in visually hidden text. Recovery link moves below Submit. One native collapsible disclosure places benefits below the mobile form, collapsed by default; desktop opens the same content, breakpoint change adapts without duplicating nodes. Viewport/keyboard overflow scrolls the whole dialog rather than clipping controls. Native inputs/selects, required/length/autocomplete attributes, show/hide, remember startup/save, login/register payloads, session routing and social readiness validation remain unchanged.

**Confirmed compatibility defect fixed:** `management.js` selected the first `.auth-form .text-link`, which is actually `resendEmailVerification`, overwriting its handler/label with password recovery and leaving the real recovery button disabled. Recovery now binds only `#authForgotPassword`; existing `recover()`/cancel/back routes and resend handler remain unchanged. Resend is available after a login error rather than permanently crowding the initial form. No SMTP/send transaction performed. API/network/backend configuration untouched.

**Exact targeted evidence:** `node tests/browser/test-auth-redesign.cjs`: **6 PASSED / 0 FAILED / 0 SKIPPED** VM scenarios (responsive disclosure, distinct recovery/resend handlers, actual login payload/remember/save/Workspace route, existing native OAuth paths, bilingual four benefits, remembered identity restoration). `node tests/browser/test-workspace-ui-unit.cjs`: **11 PASSED / 0 FAILED / 0 SKIPPED**, rerun for shared app/login dependencies. Final total **17 behavioral scenarios passed**, not native/browser acceptance. Python standard-library HTMLParser compared auth input/select maps against `git show HEAD:index.html` baseline: all attributes identical; four benefits, unique auth IDs, two existing OAuth buttons and recovery below Submit passed. `node --check app.js`, `node --check management.js`, `git diff --check` passed. Unchanged backend/provider/security/Agent suites reused. Final diff reviewed; remembered startup identity code retained. No install, real vendor OAuth, payment or email call.

**Files:** `index.html`, `app.js`, `management.js` (one selector), `styles.css` (replaces previous final Auth presentation block, not a global redesign), `tests/browser/test-auth-redesign.cjs`, this handoff. Published source SHA follows. **Remaining:** real desktop/mobile rendered geometry, keyboard/RTL/LTR/dark-light and recovery/social visual acceptance on TEST after an authorized existing-workflow deployment. No new deployment/backup, production/master/rollback/workflow/database/environment change. This is implementation of the approved design, not a claim of screenshot-exact certification or TEST deployment.


**Published compact Auth source:** `7ff4e2f5bf50918455f16dbe7462a4024bdceda9` (parent `6a47dd1e2babd9ea95c840fdd22a61baeed24995`, reviewed tree `9e1c3e799ab7912684e131eda2c0d9bef28715cf`). 17 affected VM scenarios plus HTML field-contract/syntax checks passed. No new TEST deployment or browser visual acceptance claimed.

## 27. 2026-10-16 — TEST follow-up: legacy CSS conflicts, Landing entry and session evidence

Baseline `ab28676036e6f9181422eea45ed81a5592e7c818`, updates only. Owner manually updated TEST during this round; no deployment performed by this agent. Confirmed source defects: late inline theme tokens set normal borders bright blue, overriding quiet external CSS; inline <=1100px legacy shell forced one grid column while reference layout declares conversations/chat columns, potentially placing chat outside the visible shell. Legacy docked sidebar positioning also overrides the new drawer. These are retained competing rules, not evidence that previous implementations were deleted or that cache alone caused the screenshot.

**Small corrections:** remove the blanket all-elements border override and replace resting edge tokens/thickness/shadows in their original blocks with subdued theme-aware values. Keep action colors and keyboard focus indicators. Restrict two legacy responsive/docked rules to non-reference shells, so the approved reference grid/drawer owns its layout; do not delete shared legacy functionality without evidence. Fresh unauthenticated/expired startup enters Landing; deliberate Login, OAuth callbacks and runtime idle-expiry prompt retain their routes. Authenticated customers still restore their authorized Workspace, admins unchanged. Landing carousel merges the approved four bilingual product benefits with existing admin content, preserves all existing item fields/order and avoids exact duplicate benefits; API failure keeps prior content and product copy. No database rows, pricing, trials or credentials changed.

**Actual TEST browser evidence (existing test account, no new signup or paid Agent calls):** login entered Workspace directly and restored owned project `open`/saved conversation; separate Local/GitHub sections and Todo above composer visible. Owner-deployed compact Auth showed four new icons/benefits and circular OAuth buttons. OAuth buttons unavailable because TEST social providers are not configured, not a visual failure. Recovery cancellation was observed returning to Login after the asynchronous native close handler; an immediate snapshot briefly exposed the recovery shell, so no unproven recovery rewrite was made. Dynamic Node preview still reports unavailable isolated runner: BLOCKED, not fixed by this work. Existing screenshots captured before local changes: `/workspace/scratch/test-workspace-login-20261016.jpg`, `/workspace/scratch/test-auth-updated-20261016.jpg`; private test browser evidence is not committed. Preview screenshot was captured during detection, with final unavailable state confirmed separately in UI.

**Targeted final automated evidence:**
- `node tests/browser/test-landing-entry.cjs`: 10 PASSED (entry routes, approved benefit merge/preservation/dedup/fallback, quiet tokens/focus; VM/source).
- `NODE_PATH=/workspace/scratch/bd2189746f7a/auth-test/node_modules node tests/browser/test-workspace-css-cascade.cjs`: 6 PASSED (actual loaded external+inline CSS parsed against DOM at 390/700/900/1100/1366px and open docked drawer). Reused installed css-tree/jsdom; no downloads. This is cascade evidence, not native rendered geometry.
- `/workspace/scratch/bd2189746f7a/backend-test/bin/python -m pytest backend/tests/test_browser_session_cookie.py -q`: 6 PASSED, 0.64s. Real auth functions with controlled DB: session-only HttpOnly cookie, logout revocation, polling does not extend idle expiry, 15-minute expiry rejects/revokes, delayed activity cannot revive expired session, explicit valid activity extends it. No auth backend behavior changed.
- `node tests/browser/test-auth-redesign.cjs`: 6 PASSED; `node tests/browser/test-workspace-ui-unit.cjs`: 11 PASSED; `node tests/browser/test-reference-panel.cjs`: 5 PASSED; `node tests/browser/test-project-folders-scroll.cjs`: 11 PASSED; `node tests/browser/preview-controller-unit.cjs`: 7 PASSED. Rerun because shared app/CSS changed and owner requested regression checks; these are controlled VM tests, not real model acceptance.
- Total final eight commands: **62 PASSED / 0 FAILED / 0 SKIPPED**. Syntax checks for app/enhancements and whitespace review passed. Earlier 2-cookie-only run is superseded by final 6; do not add overlapping runs to the total. Unchanged provider/OAuth/payment/retention suites reused, not rerun.

**Limits / next action:** final local visual/CSS/startup corrections require another authorized TEST update and real phone acceptance; they were not on TEST during the screenshots. Browser-close enforcement is not universally guaranteed by a nonpersistent cookie because mobile/Chrome session restoration may retain cookies; server idle expiry remains authoritative. No forced unload logout was introduced (would break refresh/multiple tabs). Actual suspended-phone 15-minute resume behavior remains unverified. Secure runnable Preview, native PostgreSQL certification, configured vendor OAuth and deferred payments/SMTP remain separate gates. No master/rollback/workflow/production/VPS/production database/settings/customer-data change. Files: app.js, enhancements.js, index.html, styles.css, three new targeted tests, this handoff. Exact publication SHA is recorded below after source publication.
