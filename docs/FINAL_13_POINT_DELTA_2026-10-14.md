# 13-point execution delta — 2026-10-14

Baseline: `c69653a278ad7eaf55a77c77faa401e042e52196`, branch `updates`. This round repairs confirmed defects; it is not another full audit or production acceptance. See handoff section 16 for implementation detail. **The 13 points have been addressed and classified, not all certified complete.**

## Changes and exact source commits

| Commit | Actual change |
|---|---|
| `e1642af9f5865ba931e6275e0e8f949e68cd9d12` | Fail-closed Preview lifecycle, runner interface/fixed launch profiles, bounded descriptor-pinned source snapshot, Stop and async response invalidation |
| `5b99a5e52433c55e34d78c0487f0acc28e16bf91` | Reconcile native process-loss/history against durable dispatch, reject lost waiters without replay, preserve surviving waiters, prevent terminal-state overwrite; real native restart/live-busy tests |
| `0df9b4a6679a6359c258cfb5ec66b155faa2875d` | Compensated archive storage and interrupted-transition recovery; mocked GitHub boundary tests and executable native OAuth CAS gate |

Reviewed/tested source tree: `60e439653341ea689e526c1526322d59ffdd29a0`. The following documentation-only commit records these exact SHAs; its own SHA is returned in the delivery message.

## All 13 requested points

| # | Previous state → actual delta | Status / remaining acceptance |
|---|---|---|
| 1 | Approved architecture/UI/business/security baseline retained; only Preview controls, runtime recovery, archive compensation and tests changed | VERIFIED for this diff review. No redesign, schema/dependency/workflow/production change |
| 2 | Read-only detection/plan → runner Protocol, supported argv profiles, secure source-export helper, owned lifecycle/status and Stop UI | IMPLEMENTED / UNVERIFIED overall. Container adapter, preparation, protected separate-origin proxy, live quotas/logs/expiry/crash cleanup remain OPEN/BLOCKED; no engine/socket, no actual runnable preview |
| 3 | Native restart could leave submitted forever → matching-dispatch reconciliation and no replay; real permission/question process-loss tests; completed history recovered | VERIFIED for actual OpenCode process restart and seeded lost-observer state. Full Gateway SIGKILL/orphan-child supervision and pre-dispatch interruption acceptance remain IMPLEMENTED / UNVERIFIED, not silently complete |
| 4 | SQL rollback could leave runtime erased → staged rename, commit-before-erasure, compensation/recovery including ambiguous commit and erasure failure | VERIFIED internal disposable-DB failure paths plus prior real native runtime shutdown/isolation and recovery/no-trial-reset evidence. Native PostgreSQL concurrency/crash durability and complete operational archive→paid-reactivation journey remain open |
| 5 | Approved Composer/scroll/questions/UI retained → Preview stop/late-response race repaired | IMPLEMENTED / UNVERIFIED visually. VM behavior checks pass; actual Composer/search, scroll/reading position, todos/tool output/cards, reload, RTL/LTR/themes/mobile acceptance BLOCKED by existing crashing Chromium; no replacement browser acceptance claimed |
| 6 | Product GitHub live acceptance missing → 11 first-time mocked authorization/token/repository/path cases | BLOCKED for live App authorization/import/reimport/reconnect and remote failure flows. Requires product GitHub App plus authorized test installation/user/repo. No remote repository operations performed |
| 7 | Existing OAuth checkpoint/CAS preserved → real Agent request survives busy credential-change deferral and idle retry without process disposal | VERIFIED for native waiting-request synchronization with fake key. Vendor refresh/expiration/revocation/failed-refresh recovery and actual token streaming remain BLOCKED by authorized sandbox; native CAS blocked separately; unfinished native OAuth handshake still requires restart of authorization after process loss |
| 8 | Existing disposable native gates retained → new concurrent encrypted OAuth CAS acceptance test | BLOCKED: no native PostgreSQL instance/container; new native case skipped. PGlite migrations and rollback fixtures are preliminary evidence only |
| 9 | Security boundaries retained → preview foreign-owner denial, link/special-file/export bounds, stale native decision rejection, no duplicate replay, archive compensation | VERIFIED targeted cases only, not exhaustive security certification. Runtime/container OS isolation, full vendor/GitHub/native concurrency boundaries remain open |
| 10 | Reused prior evidence; targeted changed/dependent checks and one coordinated available-environment cycle | VERIFIED runs listed below. Not full unavailable browser/native/container acceptance |
| 11 | Existing Chromium/native DB/container/GitHub/vendor blockers retained | VERIFIED execution discipline: no repeated blocked probes/downloads; independent code/tests completed |
| 12 | Payment and outbound confirmation email deferred | DEFERRED — MAIN SERVER, unchanged; no external requests/configuration changes |
| 13 | Living handoff updated with source changes, failures, fixes, exact commands/SHAs and gates | VERIFIED delivery record. Suitable for controlled local acceptance with disposable services, **not merge/deploy/production-ready** |

## Actual test results — separate runs, do not sum duplicate cases

| Run | Passed | Failed | Skipped | Meaning |
|---|---:|---:|---:|---|
| Initial new native restart regression before repair | 0 | 1 | 0 | Reproduced durable `submitted` after killed permission waiter, 8.17 s |
| Initial new archive commit-failure regression before repair | 0 | 1 | 0 | Reproduced missing runtime file after SQL rollback, 1.08 s |
| Coordinated changed/dependent cycle | 56 | 0 | 1 | 62.92 s; real OpenCode/Gateway/PGlite, offline contracts; 3 dependency warnings |
| Additional first-time live waiting-request sync | 1 | 0 | 0 | 5.86 s; actual native pending question, credential change, no interruption, idle retry |
| Final affected-only safety addendum | 8 | 0 | 0 | 22.17 s; five archival failure cases and three native restart/history cases after final terminal/ambiguous-commit guards |
| Preview asynchronous controller VM | 3 | 0 | 0 | Behavioral race checks, **not browser rendering** |

Earlier component runs (22 Preview, 11 mocked GitHub, 2 native pending-restart, 1 initial archive-after-fix) passed before the coordinated cycle; they are superseded rather than added to its count. No unresolved failure remains in the checks run here. One native CAS skip is still an acceptance blocker, not a pass. No complete external/browser/native/container regression was possible.

The coordinated cycle reran the old Gateway HTTP/SSE case, two runtime-sync cases and real retention case **because their dispatch/initialization/archive dependencies changed**. They passed. It did not rerun the full 76-pass offline suite, resolved catalog browser investigation, unchanged signup/billing/trial suites or unchanged checkpoint unit suite. Prior email activation/recovery tests used fixture delivery only and are reused with their original limitations.

### Exact commands

From the repository root; these absolute tool paths identify the already-installed QA environment, not production configuration:

```bash
/workspace/scratch/bd2189746f7a/backend-test/bin/python tests/run_isolated_audit.py --pglite-command /workspace/scratch/bd2189746f7a/audit-tools/node_modules/.bin/pglite-server --opencode-binary /workspace/scratch/bd2189746f7a/audit-tools/node_modules/.bin/opencode --pytest-target backend/tests/test_preview_detection.py --pytest-target backend/tests/test_preview_api_boundaries.py --pytest-target backend/tests/test_github_boundaries.py --pytest-target backend/tests/test_agent_restart_recovery.py --pytest-target backend/tests/test_archive_failure_recovery.py --pytest-target backend/tests/test_native_oauth_concurrency.py --pytest-target backend/tests/test_gateway_agent_http.py --pytest-target backend/tests/test_retention_runtime.py --pytest-target backend/tests/test_batch1_runtime_sync.py --pytest-target backend/tests/test_agent_question_validation.py --pytest-target backend/tests/test_routine_approval_default.py --pytest-target backend/tests/test_agent_event_pool.py

/workspace/scratch/bd2189746f7a/backend-test/bin/python tests/run_isolated_audit.py --pglite-command /workspace/scratch/bd2189746f7a/audit-tools/node_modules/.bin/pglite-server --opencode-binary /workspace/scratch/bd2189746f7a/audit-tools/node_modules/.bin/opencode --pytest-target backend/tests/test_agent_restart_recovery.py::test_live_native_waiter_survives_busy_credential_sync_and_idle_retry

/workspace/scratch/bd2189746f7a/backend-test/bin/python tests/run_isolated_audit.py --pglite-command /workspace/scratch/bd2189746f7a/audit-tools/node_modules/.bin/pglite-server --opencode-binary /workspace/scratch/bd2189746f7a/audit-tools/node_modules/.bin/opencode --pytest-target backend/tests/test_archive_failure_recovery.py --pytest-target backend/tests/test_agent_restart_recovery.py::test_restart_marks_lost_pending_execution_failed_without_replay --pytest-target backend/tests/test_agent_restart_recovery.py::test_completed_native_turn_is_reconciled_after_observer_loss

node tests/browser/preview-controller-unit.cjs
node --check dashboards.js
git diff --check
```

Harness applied migrations only to a fresh temporary in-memory PGlite DB and removed disposable services/files on teardown. No paid model call; the native model is deterministic loopback. Existing browser crash/environment inventory is in `RUNTIME_AGENT_DIAGNOSIS_2026-10-14.md`; it was not probed repeatedly. There is no public preview URL or new screenshot: real visual acceptance remains blocked.

## Remaining release gates and local acceptance

1. Finish and verify the real isolated Preview adapter/preparation/proxy/lifecycle in a disposable engine environment. Never simply enable host execution or label static HTML as universal.
2. Verify browser Composer/search/streaming/cards/RTL/themes/mobile using a functioning browser. Existing `tests/browser/workspace-interactions.cjs` remains the starting fixture, not an executed result for this round.
3. Exercise full Gateway process termination/restart supervision, live orphan child and pre-dispatch interruption; the new native restart tests do not certify that separate journey. Do not auto-replay uncertain tool execution.
4. Run migrations/constraints/races/CAS/rollback/archive and pool acceptance on disposable native PostgreSQL; set `AUDIT_DISPOSABLE_DB=1`, `AUDIT_DB_ENGINE=native` (or `postgresql`) and isolated roots. Never point the tests at customer data.
5. Supply authorized product GitHub App/test repository and vendor OAuth sandbox for their outstanding live flows. Connector source-publishing authorization is not the application's GitHub authorization.
6. Validate actual archive/reactivation operational crash durability and paid entitlement transitions using controlled test records; retain prior no-second-trial evidence.

**Separate server phase, not current failures:** external PayPal/bank processing, gateway/webhooks and real confirmation/activation/resend SMTP delivery. These require later explicit authorization and safe sandbox/mailbox controls. No live payment, SMTP, VPS, production DB, migrations, secrets, deployment or workflow change was made.
