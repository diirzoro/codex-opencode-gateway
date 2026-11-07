# Native storage-first follow-up — 25 October 2026

Reference read before this follow-up: `/OpenCode Gateway/OPENCODE_GATEWAY_NATIVE_ARCHITECTURE_MASTER_HANDOFF_2026-10-23_AR.md`, current Library file version3, 34,110 bytes, modified25 October. The stored heading says3.0; its sections13–14 contain the latest persistent-headless/storage-first decisions identified by the owner as the approved v3.1 execution baseline. The current explicit execution order governs; no extra authorization was requested because of the heading.

## What remains Native

OpenCode alone owns provider/model data and cache, session persistence, agents, message/tool execution, Todo, questions, approvals, abort and SSE. Gateway adds no provider/model database or discovery cache. The account provider helper is authorization/sanitization around native metadata, not a discovery engine. No additional native server, per-user/per-workspace process, systemd unit or AI queue is introduced. LIVE, Preview, original configuration and workflows remain untouched.

## Administrative refresh

The existing Gateway maintenance loop now calls a small administrative adapter; no new task/daemon/service is created. Initial scheduling performs no model download. Default maintenance interval is7 days, selectable as14 days; the schedule and finite timestamps/outcome are operational metadata in one private JSON file under the existing Gateway runtime root, **not a catalog**.

Routes use the existing `require_admin` dependency:

- `GET /api/admin/native/catalog-maintenance`: finite status, current Native service PID/autostart/recovery when readable.
- `PUT /api/admin/native/catalog-maintenance`: `{"interval_days":7}` or14 only.
- `POST /api/admin/native/catalog-maintenance/refresh`: invoke the official CLI command below under the existing native context.

The action is in the existing AI/OpenCode Policy administration panel. Both manual and scheduled operations use the same lock. Existing native service/MainPID, actual executable, headless serve arguments, original HOME/XDG/model-cache settings and host/namespace path identity are inspected privately before selecting the context. If they cannot be read/verified, the operation refuses and reports the actual missing operator context. It does not guess paths, copy auth files, install another executable, start `serve`/`web`, restart a service or run another AI request. Context discovery requires the Gateway OS user to have the existing read/execute permissions; no new sudo/polkit privileges are installed.

The only maintenance command is the installed native executable with:

```
models --refresh --pure --print-logs --log-level WARN
```

`--pure` and project-config disabling keep unrelated project/plugin execution out of this maintenance call. This is a short-lived **Native CLI maintenance operation**, not another persistent OpenCode server. The original server's environment/configuration is not edited. Its built-in refresh logic remains in charge; the7/14-day setting controls administrative CLI invocation, not the internal Native timer.

No native SQLite/cache file is opened or edited by Gateway. Native's own command owns atomic cache replacement and last-good data. Full model output is discarded, and raw stderr/environment/auth values are never returned or logged by Gateway. A native fetch warning counts as failure even if CLI exit code is0. Other zero exits are recorded as `cli_completed_reload_unverified`, never verified immediate reload. Status exposes whether the original Native PID/start identity remained unchanged after the command.

## Verified in-process limitation

One isolated real1.19.4 experiment used a deterministic loopback catalog endpoint and temporary HOME/XDG paths:

1. Official CLI refresh populated catalog model `before`; the persistent Native server reported `before` through `/provider`.
2. The endpoint changed to `after`; a second official CLI refresh and CLI model listing reported `after`.
3. The same running Native server still reported `before`. No restart/dispose was issued.
4. With the catalog endpoint failing, native CLI returned **exit0** and logged the known fetch failure. A subsequent official CLI listing still reported last-good `after`.
5. The persistent Native PID remained unchanged, and its existing SSE stream delivered a session update after the CLI operation.

The installed SDK exposes no supported manual in-process model-refresh API. Its Native runtime contains an internal periodic refresh check; an external CLI's refresh event is not evidence that the persistent server received it. The client invalidates its UI discovery projection only when the running Native service emits its own `models-dev.refreshed`/`catalog.updated` event. No forced instance/global disposal or fabricated “models updated now” claim is made. **Immediate in-process refresh and exact weekly/fortnightly server-snapshot activation remain an upstream/operational limitation.**

## Remaining integration gaps fixed

- Native Workspace capabilities now read original `/experimental/tool/ids` and `/skill` metadata with existing workspace ownership, rather than failing through a disabled legacy runtime. Actual local1.19.4 returned list schemas for both endpoints. Skill paths/content are not returned in this display.
- In Native mode, the old account-provider maintenance task is not even scheduled. Legacy Python execution/queue routes and per-workspace spawning remain disabled by their existing guards; rollback source stays preserved until actual TEST acceptance.
- Existing pilot connections retain credential ownership through the retired pilot-ID value when no newer ownership event supersedes it. That value no longer limits admission to Native. New account bindings and explicit disconnections take precedence, and public free configuration never grants a paid model. No existing native key is overwritten or copied by catalog discovery.
- Native credential UI now accurately says Configure/Connect, without promising that a paid-model validation request ran when it did not.

## Verification and deployment truth

Final distinct focused cases across this work: **40 backend passed /0 failed /0 skipped**, with one upstream Starlette/AnyIO deprecation warning; **60 client/DOM/regression checks passed**. This includes8 maintenance cases (schedule initialization,7/14 validation, exclusive refresh, CLI-only command, zero-exit failure, missing native context, unsafe state-file handling and admin HTTP authorization), plus the previously tested ownership/release/GitHub cases. Compatible-version tests do not claim a new real1.18 runtime test. Python compilation, JS syntax, whitespace, FastAPI import and single Alembic source-head checks pass; no migration was applied. Seven real native conversation/tool scenarios and the native cache-failure/PID/SSE experiment are separate evidence, not extra fabricated pytest cases. Newly created ignored QA files are disposable; existing tracked regressions are retained.

Source is built on published `e398ac85c5d7d7ede7f77e92d34cade38caf0fa5`; published follow-up source SHA: `5ec99c23b2d62ecf374bc794cf8fe7a7aef58871`. The coordinated runtime bundle now has15 files, adding admin route/maintenance adapter/enhancements dependencies to the prior12. Existing TEST native routing/working-file drift must still be reconciled before deployment. The utility refuses unknown current files/configuration rather than silently overwriting them.

**No VPS/SSH access, TEST deployment, real systemd boot/recovery change, actual TEST process-count observation, production database access, paid provider OAuth, or GitHub callback was performed here.** Public TEST already serves different native assets. No partial three-file UI deployment was dispatched. Actual installation of this schedule/button/capabilities fix and multi-account TEST browser acceptance remain blocked on the configured TEST operator connection/config comparison. No final CI success is claimed merely because the GitHub connector returned no workflow runs.

Unchanged functional blocker: the native1.x `/auth/{provider}` store is global. Independent accounts cannot safely install different credentials for the same provider into that one slot through this API. Gateway refuses cross-account reuse/overwrites and keeps originals. A supported native credential-context solution remains required; no duplicate engine was created to hide this limitation. Dedicated OS/filesystem/network hardening and external-user launch remain pending.
