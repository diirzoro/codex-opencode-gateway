# Native 1.19.4 development checkpoint — 25 October 2026

Source baseline: `6a04264d94f7b175cf5e0ba087fc9f407a88e693` on `updates`.
Published implementation SHA is recorded in the top entry of PROJECT_HANDOFF_AND_REMAINING_WORK.md after publication. This is a source/local checkpoint, **not a TEST deployment or a claim that A–G are entirely accepted**.

## Owner scope

The owner is the only real TEST user; the platform is pre-launch. LIVE remains stopped and untouched. Use the existing native installation, existing Nginx and existing Gateway. No second engine/service, Python AI execution path, Gateway message queue, Preview changes, migrations, original secret replacement or workflow changes. A single installation with separate paths does not itself create an OS credential/filesystem boundary. No LIVE change is authorized to implement any eventual shared-installation arrangement.

The original single-owner-ID admission is removed in source. All authenticated TEST accounts use existing user/workspace/project/session ownership checks and entitlements. Native stays feature-controlled and explicitly TEST-domain/database-only. Original owner environment values may remain on the server for rollback but no longer admit or reject users in this source.

## Implemented source

- Native SSE updates a session-scoped message/part cache directly, including native delta/update/remove events. Full native history is loaded on first opening, reconnect or unsupported event recovery, not per token. Concurrent matching reads coalesce; initial discovery/agent requests coalesce and cache briefly. Status and controls are event-driven. Native Todo now supplies `supported:true`, and ordinary message renders do not repeatedly request Todo.
- Existing chat retains unchanged message DOM nodes while updating streamed output. User text/attachments and native tool parts remain separate. Native tools deduplicate by call ID; native timings/statuses remain authoritative. Markdown/code rendering remains the existing inert-text formatter. Unknown receipt failures preserve message text/attachments locally and block blind resends until history confirms the native message ID. There is no alternate execution queue.
- Per-session provider/model/agent/variant selection, native variant options in the existing composer, text/attachment draft persistence, native question custom answers (default supported unless explicitly false), native permission once/reject with double-click protection, abort, and ownership-gated rename/client-history visibility. Native session history/files are not deleted by the client-history action.
- Account Connections now uses native provider/auth methods instead of spawning legacy account runtimes in Native mode. API-key PUT/DELETE and supported OAuth authorize/callback go to the existing native store; API keys are also encrypted with the existing configured key in the existing account table. Missing original encryption key/schema stops persistence, without generating replacements. Account mutation invalidates owned workspace discovery and broadcasts a nonsecret invalidation between same-origin tabs.
- Gateway strips native `Provider.key` and `options` from public metadata and applies provider/model policy and credential ownership before admitting prompts. Public unauthenticated built-in free models are distinguished from paid/configured credentials. Provider configuration returns `verified:false`; it does not pretend a vendor model request succeeded.
- Additional guards reject caller routing headers, arbitrary prompt tool/system overrides, unsupported part types, cross-workspace file URIs, permanent permission `always`, and external-directory approval. Native sessions begin with native ask/deny rules. No permission is auto-answered by a second executor.
- GitHub preserves genuine non-expiring user tokens instead of fabricating an eight-hour expiry. Existing expired-token rejection, OAuth state binding, per-user repository authorization and existing connections remain. No repository writes or real GitHub OAuth callback were performed.
- Coordinated release source now includes all 12 runtime dependencies, reuses existing 18098 for private auth/metadata routes, removes owner-ID activation, verifies actual native health/version before preparation, and preserves original settings/backups/rollback. The existing three-file workflow is unchanged. Existing installation/configuration drift still stops the tool; it is not a blind upgrade utility.

## Important functional limit — shared native /auth

Actual local **1.19.4** testing confirmed that setting `/auth/deepseek` in directory A makes that connection visible in directory B. Separate directories do not give different accounts independent credentials for the same provider through this API.

Consequently the Gateway assigns each authenticated native provider slot to one account using the existing audit table and PostgreSQL transaction advisory locking. Another TEST account cannot overwrite/use that credential or consume its pending OAuth flow. Existing unassigned native credentials remain preserved and unavailable to other users. An existing encrypted account key can be adopted only if it matches the actual native key; no credential migration/copy sweep exists. Unauthenticated built-in free models can be shared when native reports its public configuration.

**Not complete:** two accounts using different credentials for the same provider in one shared native process. The source deliberately returns a conflict instead of swapping global credentials around active sessions or launching another engine. This needs an actual supported native credential-context contract, or an owner-approved architecture decision; do not silently remove the ownership guard. OAuth refresh/revocation during active execution and kernel filesystem/network isolation remain unverified. Do not present this compatibility guard as production tenant isolation.

## Actual verification

Local dependency installation was disposable and outside the repository; no VPS runtime install/upgrade happened.

- Backend focused acceptance: **31 passed / 0 failed / 0 skipped**, including 14 native account/gate/confidentiality cases, 5 release cases (including actual temporary-file stage/activate/rollback and compatible-version checks), and 12 GitHub boundaries/non-expiring-token cases. SQLite tests are disposable fixtures, not native PostgreSQL certification; release service/HTTP calls are controlled.
- Actual native 1.19.4, isolated temporary HOME/XDG/project, no inherited keys and a deterministic loopback model: two concurrent conversations/two model IDs, text SSE, real Todo, question/custom answer/continuation, approved shell file write, rejected write with absent file, and abort while approval is pending with absent file. All seven final scenarios passed. Abort correctly reports native MessageAbortedError; the initial harness incorrectly expected no error on a deliberate abort and was corrected.
- Actual native metadata conformance: directory-A SSE did not receive directory-B session mutation; permission/question/status/Todo/auth-method routes returned their documented structures. API-key PUT becomes visible across directory contexts; DELETE removes it. Native built-in free provider uses the literal public API-key option; no real provider credential was supplied.
- Actual client VM/jsdom: 200 text deltas, one initial history download, bounded UI refresh, read/discovery coalescing, attachment separation, Todo, selections/variant, reconnect/status restoration, uncertain-receipt protection, account cache clearing, and retention of an unchanged user DOM node. These are controlled measurements, not customer-browser latency numbers.
- Existing activity-details test had one stale expectation that running tool details opened by default. The same failure was reproduced using the unmodified `6a04264` dashboard. Its assertion was updated to the already-established compact/collapsed behavior; failure details and security assertions remain.

Final JavaScript pass: **58 checks**: native adapter/DOM/drafts13, existing text formatter6, composer draft14, long-user-message7, tool activity18. Parser/compile/whitespace and FastAPI import checks passed. The full historical backend suite was not rerun; its previously recorded two baseline fixture failures are not relabeled as successes. Newly created QA harnesses are ignored by this repository's owner-requested test-publication rules and removed after execution; existing tracked security/regression tests remain.

No claim of paid-model authentication, real GitHub authorization, actual TEST multi-account login, PostgreSQL concurrency, deployed browser acceptance or penetration-test success.

## Actual TEST observation / deployment

Read-only HTTPS checks on 25 October returned 200 for the TEST page and app.js/dashboards.js/runtime-client.js/native-session-client.js/management.js. HTML already includes a Native client. Every observed JS digest differs from this working release. This does **not** reveal the deployed backend, current runtime credentials, original configuration or complete deployment SHA.

No SSH agent, identity or configured connection is available in this Work environment. **No server file, service, Nginx setting, database, backup or native activation was changed by this turn.** No partial UI deployment was dispatched: newer dashboard/management depend on the matching backend/client. The GitHub connector has no workflow-dispatch operation. The existing UI workflow cannot deploy this native bundle or prove its acceptance.

The release tool currently rejects existing release-owned config paths/already-installed native routing or unknown TEST edits. Since TEST already serves Native, the operator must first obtain a read-only `inspect` and reconcile actual protected configuration; do not assume first-install `prepare` is compatible. This remains a real deployment blocker, not a pending permission request.

After actual reconciliation and complete coordinated deployment, run one authenticated TEST acceptance covering two test accounts, owned projects, configured providers/models/agents, two conversations, stream/reconnect/refresh, draft retention, file/Todo/question/once/reject/abort, foreign-ID/path/header denial, GitHub status/repos, and exact rollback files. Then conduct the dedicated pre-launch hardening phase. Do not launch external access with open critical findings.
