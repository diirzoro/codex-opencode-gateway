# Native UX and ownership acceptance — 25 October 2026

Baseline: updates `e41afab42975ce3b5e411a10632e6f120cee8222`. Architecture master v3.7 read in full. Existing Native deployment is acknowledged; this document records a new source patch, not a repeat infrastructure rollout or completed live acceptance.

## Implemented changes

- `native-session-client.js`: actual Native tool parts supply operation/path/state/duration and bounded counts; call IDs deduplicate. Raw output, diffs, arguments, arbitrary titles, credentials and protected/foreign paths are omitted. File links are relative presentation, not an authorization boundary. Original SSE reducer/history coalescing remains; confirmed completed changes and native file.edited coalesce explorer refresh at400ms. Account/session changes cancel stale refreshes. Grouped localized once/reject controls prevent duplicate submissions; Shell/unknown allow remains disabled. Native-only compact CSS wraps Arabic/English, paths, tables and mobile content. Todo is unchanged.
- `dashboards.js`: activity progress is visible while running; file buttons use the existing authenticated files/content API and inert text viewer. Explorer loads coalesce and retain expanded directories/selection. Viewer discards responses from a previous owner/workspace. Native question forms preserve choices/custom drafts when another pending question arrives; multiple answers and continuation still use existing ownership-validated routes.
- `app.js`: safe text-only Markdown tables; empty Native message spacing reduced; manually changed tool expansion preserved across streaming rendering. Existing follow-scroll, message folding and keyed user nodes retained.
- `backend/app/services/native_provider_accounts.py` and `backend/app/routes/workspaces.py`: fix manual lookup/options beyond the50-provider presentation cap. Full native metadata is internal for explicit lookup; paged/main responses remain capped. Account-usable connections get priority, extra usable connections remain available. Another account's global Native connection does not gain account-connected status. No credentials are written by this fix.

No changes to index.html, styles.css, Preview, deployment workflows, Nginx/systemd/configuration, ports/IPs or Native process. No new execution engine, provider database/cache, API, service, queue or Todo logic. Existing native session/message/tool/question/permission/file.edited SSE data and `/provider` metadata are reused; Python retains its existing authorization/control-plane role.

## Reproducible local evidence

With jsdom installed, `NODE_PATH=<dependencies>/node_modules node tests/browser/test-native-ux.cjs`:15 cases passed. Existing test-activity-details.cjs18, test-agent-text.cjs6, test-composer-draft.cjs14, test-long-user-messages.cjs7 passed:60 total checks. Actual client fixture:200 text deltas, one initial history download, zero file refreshes from tokens; completed file-event burst yields one file refresh. These are fixture request counts, not deployed latency measurements.

`PYTHONPATH=. python -m pytest -q backend/tests/test_native_control_plane.py backend/tests/test_github_boundaries.py backend/tests/test_account_provider_routes.py --tb=short`:45 passed, one dependency deprecation warning. New control-plane tests use two synthetic owners, real auth cookie hashing, ORM ownership queries and FastAPI routes with controlled Native metadata. SQLite is a disposable ORM test fixture only; no Gateway/Native storage replacement or PostgreSQL concurrency certification. No paid vendor or real OAuth requests.

Additional existing test-composer-project-menu.cjs fails before assertions: `ReferenceError: q is not defined` in its extracted composer fragment. Reproduced on unchanged baseline e41afab. This stale harness was not deleted or disguised as passing. No whole-backend-suite result is asserted. JS syntax, affected Python compilation and git diff --check pass.

Local Chromium screenshots at1120px English and390px Arabic use actual component functions and synthetic data, visibly labelled as local fixtures. No horizontal viewport overflow in those fixtures. They do not show a logged-in TEST account or prove whole-app accessibility/mobile acceptance.

## Security matrix

Every result below is **local fixture evidence**; every corresponding live TEST row remains **BLOCKED / not run** pending independently controlled verified accounts and deployment of this patch. HTTP200 for native transport below is Gateway authorization/X-Accel-Redirect with empty body, not proof of actual Nginx/SSE delivery.

| Boundary / controlled request | Expected | Actual local | Decision |
| --- | --- | --- | --- |
| No cookie, Native SSE |401|401|Denied|
| Other owner's project / workspace |404|404 /404|Denied|
| Other owner's mapped Native session/history |404|404|Denied|
| Own workspace URL with other native session/message ID |404|404|Denied before transport|
| Other workspace SSE |404|404|Denied before transport|
| Other files list / content / export |404|404 each|Denied; synthetic marker absent|
| Other file upload/modification |404|404|Denied; synthetic file unchanged|
| Other permission reply / question reply via own workspace |404|404 each|Denied|
| Owned project/files/content/history/Native messages/SSE, then switch cookie to B |200 then404|200 then404|Owner allowed, switched account denied|
| Controlled traversal, absolute path, symlink to B fixture |403/422|403/422|Denied; marker absent|
| Claim another owner's process-global provider slot |409|409|No Native credential mutation|
| Revoke another owner's provider, service and HTTP route |403|403|No Native credential mutation|
| Browser role/user headers, ordinary owner session |No Shell promotion|200, shell_enabled=false|Role comes from stored account|
| GitHub status with another user's query ID |Own state only|200, no foreign connection|Query cannot select owner|
| GitHub repository/branch authorization |Use connected owner, deny foreign|Existing regressions pass|Controlled vendor fixture only|
| Frontend old owner file-view response / old file link |Discard / no navigation|Discarded / blocked|No stale UI attachment|

No suspected cross-account leak was observed in these controlled fixtures. No private existing TEST resource was accessed. This does not certify live Nginx routing, Native tool OS confinement or global credential isolation. Independent per-account credentials for the same provider remain unsupported by the shared Native auth slot; conflicts are refused. Shell remains disabled for all accounts until safe OS confinement is demonstrated. Existing catalog refresh limitation (CLI refresh does not prove running-server reload) remains unchanged.

## Actual TEST and deployment status

Public landing page and registration form were inspected in the browser. No fields submitted, no new account, no existing password/token/cookie inspected. Trial requires email verification; no test-owned verifiable email or independently created accounts were available. Browser account creation requires manual user handoff; never bypass verification, invent an email identity or use someone else's address. Registration/login/project/workspace/conversation/connected-model/long-prompt/SSE/Todo/read-write/approvals/questions/history/logout acceptance therefore remains not run.

Prior deployment: owner direct-update baseline9055cff, then successful Actions run40193999369 at8e2a5c60af40f86c6888a4806922c0a537dfb6d2. This UX patch is source only until a new rollout is verified. No configured local SSH/authenticated Actions-dispatch session or connector dispatch capability is available. No new VPS preimage backup or rollback location was created. Existing rollout backup root is `/home/tahir/opencode-test-diff-backups`; do not claim a child path without actual rollout output.

The unchanged manual Actions workflow accepts audit-test/deploy-test. All five runtime changes are already in its18-file manifest; no infrastructure change is required by this patch. Operator must inspect installed hashes, approve exact known preimages/merge unknown patches, preserve .env/database/config/Native storage and retain reported private backup manifest. Do not dispatch blindly over unknown server edits. Native engine must remain untouched. Verify downloaded assets and Gateway behavior after rollout, then execute two-account matrix above through real Nginx and owned harmless fixtures. Test actual Native prompt/SSE/reconnect, tools/Todo/questions/once-reject/abort, history/logout/account switching, provider/GitHub ownership and rollback readiness. Stop at a suspected foreign synthetic marker leak; never enumerate real user data.

## Remaining work

Blockers: deploy this reviewed source through the existing authenticated TEST mechanism; manually register/verify two controlled ordinary accounts; run and record the full live functional/security matrix and server-provided rollback path. Live external provider/GitHub OAuth and shared-slot credential isolation remain unverified. Broader filesystem/process/network hardening remains required before launch. Enhancements: broader device/screen-reader acceptance and the pre-existing composer-menu harness repair. master, LIVE, Preview, existing data/credentials and shared Native installation/process were untouched by this source turn.
