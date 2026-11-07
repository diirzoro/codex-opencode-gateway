# Native security and performance — 27 October 2026

Scope: incremental source changes on `updates`, not a runtime replacement. Requirements were read from the owner's architecture security/performance addendum and Work brief dated27October. Historical3.5 infrastructure descriptions in the attachment do not override verified running TEST state or later handoff entries. No workflow/config/ports/IP/schema/Preview/shared Native changes or automatic deployment.

## Confirmed changes and request map

`POST /native-session/<workspace>/session/<native>/prompt_async` still authenticates the Gateway session and verifies user→project→workspace→conversation, current lifecycle, Native directory mapping, current policy and credential ownership. Nginx still forwards the original prompt body/AI response/SSE; Python performs authorization only. The already-validated Workspace/root are reused within that same request, removing four redundant SQL SELECTs and repeated filesystem checks. There is no cross-request authorization cache. Native `/session/{id}`, `/experimental/tool/ids` and configured-provider checks stay live because they are security decisions. `/path` remains conditional on remembered file rules/approval paths; no blind TTL security cache was introduced.

Native metadata HTTP connections are reused only for the duration of one authorization and closed afterward. A ContextVar holds operational deadline/client state, not messages/catalog/permission data. The request budget is20seconds (5for abort) and is checked again before X-Accel-Redirect; each metadata wait is bounded by the remaining budget and15seconds. This prevents authorizing a delayed request after the budget elapsed; it is not a hard wall-clock guarantee for every synchronous OS/DB operation. A disconnected POST is checked after authorization before transport. Allowed decisions use a finite DEBUG log and refusals use an INFO status-only log, without raw prompts, paths, headers, IDs or vendor errors; these are operational logs, not a new persistent audit ledger. Existing Gateway audit/ownership data remain authoritative.

No duplicate Native data/API was introduced. Existing Gateway explorer/export APIs remain because their ownership, protected-path and size-limit behavior is established; no Native endpoint replacement with equivalent security was demonstrated. AI reads/writes remain Native tools. Files listing reuses its checked root instead of resolving it for every entry. Storage measurement uses descriptor-relative `fwalk/stat` on Ubuntu, avoids following symlinks, checks fresh usage on each quota decision and stops once quota is reached. Unreadable usage fails503 rather than admitting an unmeasured execution. This is not an OS disk quota or a limit enforced continuously during an AI run. No stale usage cache, new sweeper, database or service was added.

Protected names are now consistent for direct reads, listings, attachments, approval validation and ZIP export: `.env*`, `.git`, `.ssh`, `.aws`, `.config`, `.opencode`, Native executable configs, `auth.json`, `credentials.json` and `.key/.pem` files. Native session deny patterns include those names. The benchmark reproduced HTTP200 for three synthetic protected files before this change and403 after. No real secret was retrieved. Filename rules alone cannot detect arbitrary secrets in ordinary files and do not prove OS confinement or the absence of old Native instance-wide `always` grants.

## Native receipt root cause reproduced

The real client in VM received an accepted message SSE event followed by `session.idle`, then the delayed prompt HTTP acknowledgement overwrote idle with submitted. The regression failed with actual=submitted / expected=idle before the fix. New sends capture the SSE status revision; an acknowledgement cannot overwrite a later idle/error event. Malformed status responses no longer release an uncertain draft through Recover. Existing exact messageID history reconciliation, saved attachments/drafts, bounded abort-before-status and no automatic resend remain.29 client cases pass, including both idle/error orderings, Stop and uncertainty. No conversation, draft, file or Native history was deleted. The actual testuser conversation “New Test File” has not been reproduced with this new source on TEST; do not claim all provider/network stalls are cured.

## Local before/after measurements

Reproducible commands (installed backend requirements and repository root):

```bash
PYTHONPATH=backend:. python tests/performance/native_control_plane.py --baseline-ref eab766226861040045cc3301243a6d5f59de63f7
PYTHONPATH=backend:. python tests/performance/native_control_plane.py
PYTHONPATH=backend:. python -m pytest backend/tests/test_native_security_performance.py backend/tests/test_native_control_plane.py backend/tests/test_github_copy_cleanup.py -q
NODE_PATH=<existing-jsdom-node-modules> node tests/browser/test-native-ux.cjs
```

The baseline option loads only the three committed module preimages in a disposable Python process; it never resets/checks out the working tree. Temporary synthetic SQLite/files are removed.30 measured authorization samples after one warmup;15 quota samples after one warmup. A tiny owned project and a3000-file synthetic tree are used. Native metadata and model entitlement are controlled, and the benchmark never follows X-Accel-Redirect or invokes a model. Thus it excludes real provider/catalog latency and PostgreSQL concurrency.

| Local metric | Before p50 / p95 | After p50 / p95 |
| --- | --- | --- |
| HTTP/ORM authorization, ms | 9.76 / 15.837 | 7.272 / 12.227 |
| Fresh quota scan:3000files, ms | 31.088 / 42.973 | 7.385 / 12.878 |
| Reject over-limit tree, ms | 31.248 / 37.244 | 0.136 / 0.327 |

SQL SELECTs per measured authorization: **11→7**. Native metadata in this fixture remains **one session + one tool-ID read** before/after. Real provider access adds its own live Native `/provider` read and ownership checks; it is not counted as a verified paid-model connection. No Native call was removed merely to improve the numbers. Process CPU median per authorization: 9.503→7.133ms. Benchmark-process peak RSS: 101892→101812KiB; this negligible difference is not a server RAM improvement. No TEST CPU/RAM/TTFT/SSE-byte/parallel-user measurement was available. Measurements vary with hardware and page cache; no numerical live speedup claim.

## Catalog preservation

The existing maintenance schedule defaults to7days and supports14, with its existing admin-only controls and official `models --refresh` CLI under the service identity. Tests confirm initialization/read does not download; a configured future schedule does not refresh on access. No catalog/provider database, new daemon, service restart or cache-file manipulation. Existing limitation remains: CLI success updates Native's stored cache and does not prove in-process snapshot reload. TEST admin UI visibly showed7days and14-day option; no manual refresh or schedule modification was performed.

## Tests and actual TEST evidence

77 distinct affected backend cases passed (20new security/performance +43existing Native boundaries +14GitHub cleanup);29client cases passed. One existing AnyIO deprecation warning. The new disconnect fixture initially raised ClientDisconnect before the intended post-authorization branch; its receive sequence was corrected to send body then disconnect, and all20new cases passed. The late-SSE regression failed before the fix; a new count assertion fixture was corrected to record its intercepted prompt. Benchmark fixture initially lacked policy model/provider fields; corrected without changing product validation. Syntax/compile/diff checks pass. No unchanged full backend suite was rerun or reported green.

After the owner's manual deployment, public TEST downloads of enhancements.js, dashboards.js, management.js and native-session-client.js all matched committed eab7662source bytes (not the new local client edits). No Backend revision, server preimages, backup directory or rollback execution was inspected over SSH; no configured SSH session exists here. Secure TEST login succeeded as admin after the first credential request timed out. Reload showed one “New GitHub connection” button in admin; clicking it and confirming opened the real GitHub account picker with Continue / Use a different account. No repository permission grant, installation edit, customer disconnect, real working-copy deletion or completed callback was performed. The existing customer GitHub link was preserved. Screenshot: github-fresh-picker-test-20261027.jpg is user-facing evidence, not committed private browser state. Do not save OAuth state URLs in reports.

The security/performance source in this report was **not deployed by Work**. It needs the owner's matched four-runtime-file rollout (Native client, native_sessions.py, workspaces.py, policy.py), preimage backups and manual rollback procedure. Git history retains the exact old source. No VPS backup or successful rollback has been claimed.

## Remaining acceptance and security limits

- Login as the owner of “New Test File” and verify Send / Stop / Recover / reconnect without duplicates on the new deployment; current browser account is admin, not permission to impersonate testuser.
- Two independent controlled accounts, Native tool execution outside Workspace, cross-account SSE/attachment/key checks, PostgreSQL concurrency and actual OS filesystem/network confinement still need live acceptance. Gateway denial fixtures do not certify shared-process isolation.
- Shell, commands, task/subagents and unknown tools remain denied. Pre-existing Native instance `always` cache is not proven absent/revoked. Same-provider independent credentials in the shared Native auth slot remain unsupported; cross-account claim/overwrite protection remains.
- Quota checks remain admission checks, not hard mid-run OS quotas. File-descriptor traversal improves scanning; it is not a blanket TOCTOU proof for all existing read/export/native tool operations.
- Complete GitHub OAuth/install/callback with the intended account and synthetic repository. Do not move a customer’s existing installation to admin or claim return-to-project before verification. GitHub’s saved browser login cannot be erased by Gateway’s local disconnect.
- Keep LIVE/master/Preview/workflows/ports/systemd/Nginx/config/secrets/DB and the shared engine untouched. No public launch is certified by these tests.
