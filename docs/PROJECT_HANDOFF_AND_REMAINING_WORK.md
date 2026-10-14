# OpenCode Gateway — Living Project Handoff and Completion Register

**Updated:** 2026-10-14  
**Source of truth:** this file on `updates`  
**Last verified working branch:** `updates`; latest reviewed commit before this document: `23974362c233a617fb4bef57000eb4b9496c50dd`  
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
| C-01 | Account-level providers | Table `user_provider_credentials`, account catalog/list/delete routes and account key encryption/recovery logic | **CODED / NOT VERIFIED** — requires migration 0017 on *test DB*, concurrent registration/key tests |
| C-02 | API key connection without a project | Isolated temporary OpenCode validation runtime, account connect/options routes, Dashboard UI wiring | **CODED / NOT VERIFIED** — verify actual provider methods, selected model, auth metadata and clean teardown |
| C-03 | OAuth without a project | User-isolated account runtime and authorize/callback routes, encrypted token persistence/recovery | **PARTIAL** — verify OpenCode auth.json location and structure, token refresh, expiry, restart and provider-specific OAuth flows; do not ship based on source alone |
| C-04 | Connections synchronized across workspaces | Restore account credentials on runtime start; attempted in-place refresh of running runtimes; cache invalidation | **PARTIAL** — ensure *every* active session/Composer updates immediately, failed refresh never falsely reports connected, no process interruptions |
| C-05 | Safe disconnect and revocation | Deletes account and legacy credentials; attempts runtime auth removal and private auth-file cleanup | **CODED / NOT VERIFIED** — test stopped and running runtimes, refresh failure, stale tokens and cross-user isolation |
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
| S-02 | Testing | Added `backend/tests/test_account_provider_routes.py`, `test_email_verification_contracts.py`, `test_signup_entitlement_contracts.py`; frontend JS syntax checked | **NOT VERIFIED** — test files added but not executed with reliable full results; add browser + backend + DB test suite |
| S-03 | Online preview and bug-fixing pass | User approved future Work/Codex online testing | **NOT STARTED** — use isolated staging / browser preview and fix discovered issues **on updates**; do not merge |

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
