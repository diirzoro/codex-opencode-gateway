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
