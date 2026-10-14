# OpenCode Gateway — pre-merge verification gate (owner handoff)

**Branch:** `updates` only. **Production:** `master`, not authorized for merge.
**Status:** NOT RELEASE-READY. This checklist is an evidence gate, not proof that tests passed.

## What the existing test evidence actually covers
- Real FastAPI + OpenCode 1.18.32 + PGlite staging browser journey: signup, fixture email verification, login, account provider catalog, auth choices, create/fallback project. Last recorded result: 1 passed / 0 failed. External OAuth/model requests were not made.
- Offline Python (31 passed / 13 skipped), PGlite integration (9 passed / 4 skipped), and isolated browser fixtures (6 scenarios passed) are separate historical runs. Do not rerun unchanged suites without a reason.
- New post-staging commits touched OAuth compare-and-swap guard, chat scroll/Jump to Latest, question presentation/validation, and routine auto-approval default. New unit tests exist for CAS and approval opt-in. Post-change executed evidence and limitations are recorded in handoff section 14. Some native browser/Agent gates still failed or remain blocked.

## Mandatory acceptance gates still open
1. **OAuth / Connections** — record real provider sandbox refresh and token rotation, encrypted persistence, restart, revoke, cross-user isolation and live Composer re-selection. Prove an older refresh cannot overwrite a newer token on disposable native PostgreSQL. The compare-and-swap guard is now integrated with OpenCode auth-file checkpoints and tested with fake rotations; real vendor rotation/native concurrency remain open.
2. **Busy Workspace synchronization** — verify a live streaming Agent is not interrupted, deferred updates retry after idle, stopped runtimes restore current credentials, and disconnect removes all copies. Automatic idle-only retry is implemented and tested with DB-busy fixture state; that is not live streaming proof.
3. **Real Agent approvals and questions** — in disposable workspace, invoke a protected tool; prove no execution occurs before user approval, rejection prevents the operation, approval resumes the same session, refresh preserves pending state, single/multi/custom questions resume correctly and permissions cannot cross user boundary. Routine auto-approval now defaults OFF; test with a fresh account.
4. **Chat UX** — test auto-follow, reading older messages, Jump to Latest, long streamed output, scrolling/mobile/RTL, no duplicate or blank bubbles, live todos, refresh and interrupted network.
5. **Universal Preview** — current preview detection/static HTML are not isolated runnable containers. Before offering dynamic execution, create/prove unprivileged runner, CPU/RAM/PIDs/disk/time limits, filesystem/network/port restrictions, authenticated proxy, cleanup and strict tenant separation. Do not run untrusted project commands on host.
6. **Native disposable PostgreSQL** — migrations 0017/0018, uniqueness, rollback, multi-request races, pool exhaustion checks. PGlite/SQLite do not certify these.
7. **Account security and regression** — permissions, session ownership, repo/GitHub isolation, CSRF and secret handling; browser journeys across Dashboard, Workspace, Settings, both languages, dark/light and narrow mobile. Verify reported provider search race and previously observed static asset 404s.
8. **Lifecycle sans external delivery** — email verification expiry, unique trial, paid entitlement calculations, archived/reactivated cases and cross-tenant cleanup in disposable tests. **External PayPal/bank requests and outbound SMTP are explicitly DEFERRED TO OWNER-AUTHORIZED MAIN-SERVER TESTING**, not removed and not passed.

## Resource discipline
Run targeted tests only for changed components and their security dependencies. Reuse fixtures; do not restart resolved provider catalog diagnosis. Distinguish PASSED, FAILED, SKIPPED, BLOCKED, and DEFERRED. Never count a skipped test as a pass.

## Required sign-off before asking the owner to merge
- Every mandatory gate has recorded executable test command, environment, results, commit SHA, and redacted evidence.
- Any environment-dependent gate with no evidence remains BLOCKED; do not use a simulated pass as a substitute.
- Audit `git diff master...updates` for protected workflows, migrations, secrets and accidental unrelated files.
- Owner must separately approve merge; no automated promotion, VPS restart, or production migration.

## Current executed evidence and blockers (2026-10-14)

See handoff section 14 and its 18-stage TODO. Latest upstream `bbca5edc` was fetched and reconciled before publishing the repair round. Python, actual OpenCode and disposable PGlite are available; no production service was used. Native PostgreSQL and container execution remain unavailable, and were not repeatedly reprobed.

- Offline regression and real fake-token storage/restart/revocation/retention evidence is recorded with exact separate counts in the handoff. No external model/OAuth sandbox authentication is claimed.
- The Workspace browser attempt is BLOCKED before page load by the installed Chromium's SIGSEGV. Earlier screenshots and the resolved catalog journey remain historical evidence, not post-change browser certification.
- Native pending approval/question experiment with a deterministic loopback model FAILED with OpenCode HTTP 500 before the pending request. Do not infer approval bypass or completion; diagnose fixture/runtime compatibility before certification.
- Preview `/preview/plan` describes a fail-closed security contract only. No container, dependency install, port, authenticated dynamic proxy or runnable preview was launched.
- External payments and outbound verification delivery stay DEFERRED — MAIN SERVER. No credentials/settings or existing payment/email code changed.

**Acceptance remains blocked. No merge/deploy is authorized.** Required infrastructure: a disposable native PostgreSQL service, working browser, authorized provider OAuth/model sandbox, and a dedicated isolated preview runner with authenticated separate-origin routing. Reuse successful unrelated evidence; rerun affected security cases after subsequent changes.

Executed repair commit: `4ce9d48de00214d4dfb9648f01db7bbfcaac3a7a`. Final offline: **76 passed / 0 failed / 17 skipped**. Current-source OpenCode/PGlite affected integration: **3 passed / 1 failed / 0 skipped**. The failed native Agent fixture and blocked browser/container/native PostgreSQL/vendor OAuth gates prevent release approval.
