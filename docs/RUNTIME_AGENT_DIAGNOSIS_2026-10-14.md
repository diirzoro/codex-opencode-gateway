# Runtime/Agent delta diagnosis — 2026-10-14

Baseline: `updates` `fba148b5e16e9055249fdb6958aa87bcba61512c` (repair `4ce9d48`). No production access or configuration changes. All addresses below are disposable test addresses, not VPS settings. Services stopped on fixture teardown; ports are not permanent/public previews.

## Detected environment

Host `376d84c57794`; hostname resolution returned internal addresses `172.26.47.197` and `172.31.1.142`. Test services bound **127.0.0.1**, not those interface IPs. Netlink/process-list access was restricted; health requests, actual sockets and controlled startup commands establish readiness. Network-namespace inode comparison was unavailable; successful OpenCode → model POST proves actual reachability.

| Component | Actual corrected diagnostic endpoint | Readiness / source |
|---|---|---|
| FastAPI/Uvicorn | `http://127.0.0.1:40019`, API `/api` | `/api/health` 200; `tests/staging_app.py`, `uvicorn ... --host 127.0.0.1 --port <allocated> --lifespan off` |
| OpenCode 1.18.32 | `http://127.0.0.1:39483` | Authenticated health passed; unauthenticated health 401; private generated HTTP Basic password omitted |
| PGlite | `127.0.0.1:58947` | SQL `select 1` passed; migration `0018_email_verification`; `tests/run_isolated_audit.py` starts `pglite-server --host=127.0.0.1 --port=<allocated> --db=memory://` |
| Synthetic model | `http://127.0.0.1:39683/v1` | `/models` 200, then actual OpenCode POST `/v1/chat/completions` with `stream=true`, tool schemas and SSE chunks; no paid/vendor call |
| Workspace root | `/tmp/gateway-isolated-audit-m8l7fsqk/workspaces` | Fixture environment; account-only probe needs no project directory |
| Runtime root | `/tmp/gateway-isolated-audit-m8l7fsqk/runtime` | Dedicated runtime/workdir existed and were removed on teardown |
| Native PostgreSQL | unavailable | No `postgres`/`initdb`, engine/socket or mapped non-root UID; not substituted with production |
| Containers | unavailable | No Docker/Podman executable or `/var/run/docker.sock` |
| Browser | BLOCKED | Existing Chromium `--version` exits SIGSEGV (-11), no stderr; checked once, no download/session retries |
| Product GitHub App | BLOCKED | App ID/slug/client ID/client secret/private-key/path variables unset; no product installation/user token supplied |

`APP_HOST=127.0.0.1`, `APP_PORT=8180` and OpenCode shared origin `http://127.0.0.1:4096` are **source defaults**, not the running fixture listeners. Earlier `https://testserver` was an in-process TestClient origin with no TCP listener. No assumption or probe of production `opencode-gateway.codes`, VPS IP, Nginx, firewall, DNS or systemd was made.

No root `.env` existed here. The harness supplied disposable `DATABASE_URL`, `WORKSPACE_ROOT`, `RUNTIME_ROOT`, `OPENCODE_RUNTIME_MODE=local`, `OPENCODE_BINARY`, encryption key and public-base fixture values. Runtime launch sets private HOME/XDG directories and generated `OPENCODE_SERVER_PASSWORD`. Parent HTTP/HTTPS proxy and NO_PROXY variables were set; values are omitted. Gateway's HTTP client uses `trust_env=False`; the actual local model request succeeded. No credential values are in this report or evidence.

## Confirmed cause and bounded correction

The original request failed **before reaching the model server**: zero model requests, missing `fixture/fixture` catalog entry. Debug logs resolve generic HTTP 500 `UnknownError` / reference `err_40e04707` to `ProviderModelNotFoundError: Model not found: fixture/fixture` in `SessionPrompt.getModel`.

The fixture had attempted to add a custom model through a post-start `/config` patch. Initialize the custom provider/model in **fixture-only startup `OPENCODE_CONFIG_CONTENT`**, select the already embedded `@ai-sdk/openai-compatible` adapter for the fixture's Chat Completions protocol, and require catalog presence before submission. No production provider/SDK/configuration code was changed. Corrected diagnostic: HTTP 200, one `/v1/chat/completions` stream request, 11 advertised tools, no assistant error. Required tool-call fields (`index`, `id`, `type`, `function.name`, JSON `arguments`) were consumed successfully by native OpenCode tools.

The newly exercised Gateway HTTP journey then exposed independent connection-lifetime defects: free-model preflight retained a transaction before background dispatch; synchronous background SQL could block the event loop; SSE held request/poll connections during streaming. The repair releases preflight before dispatch, runs background SQL in worker-owned sessions, and closes read-only SSE transactions before yielding bytes. Policy/ownership/cancellation/request-ID checks remain intact. A one-connection QueuePool regression failed before the SSE repair and passes after it.

PGlite's known concurrent rollback protocol produced psycopg `IndexError`; that is **not classified as an application/PostgreSQL defect**. The HTTP fixture alone uses a one-connection pool. Production DB defaults are untouched; native PostgreSQL concurrent admission/rollback certification stays BLOCKED. Other diagnostic test corrections: model tool-history detection is scoped to the latest user turn, rejection legitimately ends with a tool-only assistant step, and SSE activity is checked in the corresponding command turn rather than the earlier fast question turn.

## Evidence / selective results

- Native approval/rejection/question test after fixture correction: **1 passed**, 7.12 s, one dependency warning; real OpenCode + disposable PGlite + deterministic model.
- Coordinated affected-area cycle (native tools + new Gateway HTTP + new reactivation): **2 passed / 1 failed**, 21.32 s. Failure was the SSE test expecting command activity before the first question's completed event. Native and reactivation successes reused without rerunning.
- Corrected Gateway HTTP case only: **1 passed / 0 failed / 0 skipped**, 16.28 s, three existing dependency warnings. Four turns; real dispatch, no execution before approval, approve/reject, multi/custom and single answers, pending-state restoration through another HTTP client, duplicate replay and conflicting-submit rejection, two-user denials, durable activity, SSE cursor replay and logout revocation. Rejected command created no file; exactly one final text response per non-rejected turn. Legitimate native tool-only steps retained.
- Internal reactivation scope: **1 case passed** within the coordinated cycle above; proof is seeded, paid entitlement is preconfirmed fixture data. Renewal-only scope, single-use proof, password gate/session revocation, normal login and unchanged trial history verified; no processor or SMTP invoked.
- Single-connection SSE regression: **1 passed**, 0.79 s; verifies no checkout remains while an actual event is yielded. SQLite tests pool ownership only, not PostgreSQL semantics.
- Related question/routine-approval contracts: **10 passed** in the earlier affected subset; unchanged thereafter. Syntax and `git diff --check` passed.
- Original successful OAuth/synchronization/retention and full 76-pass Python evidence reused; **not rerun**. External payments/SMTP never called. Native model reasoning, browser token rendering/layout, native PostgreSQL concurrency, live vendor OAuth and container execution are not certified by a synthetic model or PGlite.

Evidence: [before inventory/error](audit/2026-10-14/runtime-agent-before.json), [corrected inventory/wire metadata](audit/2026-10-14/runtime-agent-after.json), [four-turn HTTP/native-message metadata](audit/2026-10-14/agent-http-message-evidence.json). These contain synthetic IDs, paths, ports and lengths, not user content or secrets.

Reproduce only the affected case when needed:

```bash
python tests/run_isolated_audit.py --pglite-command /path/to/pglite-server --opencode-binary /path/to/opencode --diagnose-agent
python tests/run_isolated_audit.py --pglite-command /path/to/pglite-server --opencode-binary /path/to/opencode --pytest-target backend/tests/test_gateway_agent_http.py
python -m pytest backend/tests/test_agent_event_pool.py -q
```

Remaining infrastructure-dependent gates are BLOCKED as listed above. Existing Preview planning is IMPLEMENTED / UNVERIFIED for real execution. No design, schema, entitlement, payment/email system, workflow, protected branch or production setting was changed. **Not production-ready.**
