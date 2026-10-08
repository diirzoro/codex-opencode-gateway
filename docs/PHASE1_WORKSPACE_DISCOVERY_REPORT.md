# Phase 1: workspace OpenCode discovery

Initially reviewed against master `32f003acf117e6f7ad80db4ed1dab41d6bb99808`, containing updates `05aa44c54c8299bd5ffb7aac3a146cb1ac197ba5`. For publication, only the seven intended Phase 1 files are applied directly to that updates commit. Master-only workflow changes are excluded.

## Scope and preserved work

Only workspace-specific OpenCode, provider and agent discovery changes are included. Existing application features remain on the updates base. Workflows, billing, PayPal, GitHub integration/configuration, database migrations, deployment files, production/server configuration, requirements and lockfiles are unchanged. Phase 2 fixes are deferred.

Temporary Phase 1 verification files and additions were removed after passing validation at the user's request. The existing verification suite remains unchanged. No customer records, fake provider connections or model/payment successes were created. No production server was contacted or configured.

## Exact application files and functions

| File | Functions / changes | Purpose |
|---|---|---|
| `backend/app/services/opencode.py` | `OpenCodeService.__init__`, `_discover`, `snapshot`, `capabilities`, `diagnostics` | Separate four core discovery endpoints from ten optional endpoints; separate locks; reuse recent successful health; preserve timing/count diagnostics. |
| `backend/app/services/runtime_snapshot.py` | `public_snapshot`, `public_capabilities` | Core response contains live providers/auth/models/agents/relevant config; optional response is independent. Session synchronization is outside the core response. |
| `backend/app/routes/workspaces.py` | `sessions`, new `workspace_capabilities` | Session listing uses its own lock; optional discovery uses the selected owned workspace through `_workspace_service`. |
| `dashboards.js` | `loadConnections`, `refreshSessions`, `refreshChoices`, `openWorkspace`, `createSession`, agent initialization | Guard workspace context, fetch sessions separately, avoid discovery solely to refresh sessions, select context without navigating away from Settings, preserve narrow composer and omitted default-agent override. |
| `management.js` | `providers`, workspace picker handler, `renderOptions` | Require an explicit workspace; no first-workspace fallback; preserve full catalog; show connected/disconnected/restricted state; separate provider selection from search text. |
| `index.html` | Agent selector markup and script versions | Show the empty OpenCode-default choice immediately and load changed scripts. |
| `docs/PHASE1_WORKSPACE_DISCOVERY_REPORT.md` | This report | Scope, request flow, validation evidence and timing limitations. |

## Before / after request flow

Before:

```text
Browser -> GET /api/workspaces/<selected-id>/runtime
  -> owned workspace -> for_workspace -> spawn/reuse, health, credential restoration
  -> health + 15 runtime discovery endpoints in one completion barrier
  -> provider/auth/agent/config PLUS sessions, permissions, tools, paths,
     VCS, MCP, LSP, formatters, project, session status and questions
  -> session DB synchronization -> render provider and agent controls
Settings without selection -> silently used workspaces[0]
```

After:

```text
Settings without selection -> asks for explicit selection; no runtime request
Settings picker -> selected workspace context, without opening another page
Browser -> GET /api/workspaces/<selected-id>/runtime
  -> owned workspace -> same for_workspace startup/reuse lifecycle
  -> health (recent successful health reused)
  -> concurrent /provider, /provider/auth, /agent, /config ONLY
  -> core response -> render provider and agent controls

Workspace sessions -> separate GET /api/workspaces/<selected-id>/sessions
  -> /session and session mapping, protected by an independent session lock

Optional inspection -> separate GET /api/workspaces/<selected-id>/runtime/capabilities
  -> optional runtime endpoints, protected by an independent capability lock
  -> never automatically requested by workspace opening or Settings
```

Storage, files, Git status and GitHub status retain their existing independent requests. Their implementations and configuration were not changed. Core calls still share a coherent completion barrier with each other; they no longer include or acquire the optional/session discovery lock.

## Source-of-truth and UI proofs

- Settings requests `workspaceRuntime.load(explicitlySelectedWorkspaceId)`, which calls `/api/workspaces/<id>/runtime`. It does not call `/api/opencode/status` or the shared/reference health service.
- The backend uses `manager.owned(..., user.id)` followed by `opencode.for_workspace(row)`. Its HTTP client carries that workspace directory and targets its ephemeral loopback runtime port.
- An HTTP regression exercised two owned workspace IDs with distinct runtime ports, agent names and configured defaults. It verified the directory parameter, full provider membership and OAuth schemas. Any shared-health call would have failed the check.
- Provider membership comes from `/provider.all`; auth schemas come from `/provider/auth`; models come from provider model maps; agents come from `/agent`; configured default comes from `/config.default_agent`.
- Settings has no API-key-only or connected-only catalog filter. Search is by runtime name/ID. Restricted entries remain visible and are labeled Restricted even when connected.
- A 226-entry fixture including disconnected OAuth and restricted providers rendered all 226 entries. The captured real 1.18.32 catalog rendered all 223 actual entries. No fixed catalog size is encoded in the application.
- Composer membership remains `connected || id == opencode`. Disconnected ordinary providers remain excluded; restricted included entries remain disabled; send/model gating continues to enforce connectivity and policy.
- The measured real runtime reported connected `opencode` only; composer membership was exactly `opencode`.
- The agent choice has an empty OpenCode-default value. No agent is inferred from list order or the name build. A request without an explicit agent choice omits `agent_id`; the backend likewise omits the OpenCode `agent` field. An explicit runtime agent choice is forwarded.
- The measured runtime reported seven agents but no `/config.default_agent`. Gateway displays OpenCode default and leaves resolution to OpenCode; it does not manufacture an effective agent name.
- A stalled optional formatter request and a stalled session-list request did not block core discovery in independent-lock regressions.

## Validation

Before removing temporary tests:

- 26 Python checks passed, zero failures/skips. One dependency deprecation warning from Starlette/AnyIO.
- 8 JavaScript checks passed, zero failures/skips, including the captured real-runtime catalog render.
- Python parsing and JavaScript syntax checks passed.
- Application `/api/health`, served frontend/default selector and unauthenticated runtime protection passed using in-process application requests.
- Protected-path diffs and whitespace checks passed.

The HTTP/UI regression fixtures verify request routing and presentation, not real customer/provider authentication. Native runtime discovery below is real, rather than a simulated OpenCode response.

Publication checks after cleanup: the unchanged existing suites passed again (21 Python checks and 2 JavaScript checks), together with Python/JavaScript syntax checks. The ignored native measurement installation and repository bytecode were removed. Python setup dependencies were moved outside the repository. The final test run disabled bytecode/cache output and removed its temporary fixtures automatically. No new test files or test output are included.

## Real OpenCode timing

Official `opencode-linux-x64@1.18.32` was installed locally through npm with normal registry-integrity/TLS verification. A password-protected loopback process ran in the existing source checkout, with private local runtime state and no inherited provider secrets. The measurement processes were stopped afterward. No production configuration was edited.

Single sample, with initially empty local runtime state:

| Operation | Cold | Warm live refresh |
|---|---:|---:|
| `/provider` | 1429.01 ms | 598.81 ms |
| `/provider/auth` | 267.15 ms | 599.56 ms |
| `/agent` | 763.10 ms | 598.06 ms |
| Core snapshot, four concurrent endpoints | 1429.91 ms | 600.65 ms |

Process spawn: 0.29 ms. Spawn to health-ready: 1934.17 ms. Health readiness plus cold core snapshot: approximately 3364.08 ms.

An immediate warm cached snapshot reused the same object, took less than 0.01 ms and made zero additional endpoint calls. Warm live means the adapter cache was invalidated while keeping the process alive. Concurrent scheduling means not every individual warm endpoint is faster than its cold counterpart. These are endpoint/adapter measurements, not authenticated Gateway HTTP or total browser-load timings, and are not a controlled comparison against the historical report.

The real runtime returned 223 providers, 7 agents and 10 provider-specific auth-schema entries, with no core discovery errors. Its initial catalog count differs from the user's 226-provider installation; Gateway preserves the complete catalog returned by the selected runtime rather than forcing a count.

## Deferred work / limits

Phase 1 does not change long credential-validation locking, cache freshness policy, manual-provider auth handling, duplicate permission polling, runtime compatibility pins or credential restoration. Restoration remains once per runtime generation. These require a later scoped phase if requested.

No external API-key login, OAuth login or successful model prompt was performed. An authenticated existing Gateway workspace/database is still required to measure full customer browser loading. Separate workspace state, installed runtime version, plugins and configuration can legitimately differ from another OpenCode installation. No shared/reference runtime is substituted to hide those differences.
