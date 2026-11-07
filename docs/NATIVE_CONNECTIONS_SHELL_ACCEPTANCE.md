# Native Connections, control plane and Shell — 25 October 2026

Baseline: `updates` at `3cff49ca18e3f9e7850e623cef69522823077a93`. Published implementation: `1c7deafe04a8260f7ec9c4e8d171ed5dafc142f6`. This is an implementation follow-up, **not a TEST deployment or completed acceptance**. Read the current handoff entry first. The specified Library memorandum was reread: file version5, document header **v3.3**, including sections2/15/16. The owner’s additional control-plane clarification is applied to source, not treated as a documentation-only policy.

## Implemented source

- Gateway authentication resolves the real stored User; owned Project/Workspace/Native session mappings remain authoritative. Context checks derive the project administrator decision from server-side `User.role in {admin,owner}` **and ownership of this specific project**, before entering Native. The current schema has no separate delegated Project Manager membership; owning a project alone does not grant Shell. New/opened session and capabilities metadata expose a nonsecret `tool_access` decision, never a client-controlled policy.
- Native sessions receive a deny-by-default ruleset. Reviewed built-in file tools, Todo and questions remain available; bash/shell/terminal/code-mode execute, task/subagents, skill, LSP, external directories and unknown tools cannot be approved. Existing sessions must accept the current Native `PATCH /session/{id}` permission policy before the next prompt. A busy session with an older policy must be stopped first. Browser-supplied permission/system/tools/role fields and `always` approvals are not allowed. Unknown or shadowed tool IDs block prompt admission pending operator review.
- **Administrator Shell is intentionally BLOCKED too**: project authorization is calculated, but a verified project-limited OS execution boundary is unavailable in Work/TEST evidence. An admin role cannot sandbox the shared process. No unchecked enable flag or Python Shell executor was added. This is a remaining capability blocker, not a claim that authorized-admin command acceptance passed.
- File approvals validate Native’s own `/path` metadata. Native read/edit permission patterns are worktree-relative; a non-Git project can report worktree `/`. Resolve that actual base before requiring an owned path and rejecting traversal/symlinks/secrets/runtime configuration. Search metadata paths are directory-relative. `/path` is private management metadata on existing18098, never a public transport endpoint.
- Shared-engine project configuration can load executable plugins/custom tools. Native context refuses project/ancestor `.opencode`, `opencode.json`, or `opencode.jsonc` before engine initialization and preserves those files for operator review. Native-mode Gateway file APIs also prohibit creating/modifying those executable configuration paths; Native permission rules protect them and `.git`/`.ssh`/`.env*`. No existing file is removed. This is not an OS sandbox or proof against file-race/instruction/plugin/LSP/network attacks; dedicated hardening remains required before external access.
- Connections main list renders **at most50** entries, with all permitted connected providers also displayed separately even when outside the first50. Infinite page loading was removed. “Add Provider Manually” is enabled without needing a project and resolves exact original Native IDs or unambiguous names across the whole catalog. No provider/model definitions are fabricated.
- Workspace provider lookup, API-key/OAuth connect/callback/disconnect, models and connection-state checks now use the same owned Native account connection instead of legacy workspace runtime creation. Per-account cache invalidation reaches other workspaces/tabs. Provider status distinguishes configured/not tested from tested; saving a key does not claim a real paid-model call occurred.
- Native `/provider/auth` can be empty because it reports plugin hooks. For an existing catalog provider without a reported hook, the supported `/auth/{provider}` API-key form is available. This is also the official Native application’s generic-key fallback, not a new authentication engine. Original OAuth hooks/indexes remain unchanged when present.
- The process-global provider-slot conflict protection is preserved. Another account cannot overwrite, consume or disconnect an owned slot. Independent keys for the **same** provider across accounts in one shared Native process remain unsupported/unresolved; directory separation does not solve this.

## Reused Native interfaces and preserved work

Existing persistent Native service and protected18097/18098 transports only. Native provider catalog/auth/OAuth, sessions/permissions/PATCH, tool IDs, path metadata, prompt_async, native message history/SSE, Todo/questions/abort remain the sources of execution and data. Python does not execute tools or carry generated AI responses/SSE. No extra AI service, server per user, execution queue, provider/model database, installation on TEST, or new long-running task was introduced.

Prior SSE reducers/coalescing/incremental rendering, draft/receipt preservation, model/agent/variant selection, GitHub token-expiry repair, native credential ownership, encrypted storage and catalog maintenance remain in place. The existing maintenance loop still invokes original `models --refresh` with7/14-day operational scheduling and no restart; CLI stored-cache refresh is **not** immediate in-process catalog reload. No new maintenance experiment or VPS result is claimed here.

## Focused verification

Final distinct checks, without adding overlapping retries:

- **59 backend cases PASS**, including current control-plane/permission/configuration/catalog tests and existing GitHub/account-provider regressions. No PostgreSQL service/database, vendor token or real account was used. Controlled route doubles verify rejection before X-Accel transport; these do not certify deployed tenant isolation.
- **50 UI/regression checks PASS**:18 account/Workspace Connections assertions using actual management functions in jsdom,14 existing composer draft cases,18 existing activity-detail cases. Native provider outside the first50 resolved by name and opened its API-key form; no authorized external-provider credential was available, so this is not a successful commercial connection test.
- **Six actual Native1.19.4 tool scenarios PASS**, with a deterministic loopback provider and disposable HOME/XDG/project: Bash blocked; approved owned write completed; foreign-file read blocked; symlink read approval rejected by Gateway403 and rejected in Native; task/subagent delegation blocked; executable project-config write blocked. A privileged agent with `permission.*=allow` did not override the session deny policy. One persistent disposable Native PID served these scenarios, then was terminated. This is not a TEST process inventory.
- Native’s own raw approval accepted a symlink read when bypassing Gateway, and its worktree-relative permission path initially exposed a mismatch in the first Gateway check. The supported `/path` contract was inspected and the implementation corrected; the final real-engine check rejects the symlink. Do not describe Native’s lexical directory guard as OS isolation. Temporary test fixtures were corrected where their UI select wrapper differed from the real helper.
- In the isolated Native context, original `PUT /auth/deepseek` accepted a **non-real fixture key**, appeared in Native connected metadata and was removed with original DELETE. No external model authentication was attempted/claimed.
- Python compilation, FastAPI import212 routes, changed-JavaScript syntax and `git diff --check` PASS. The historical full backend suite was not rerun or relabelled. Temporary task QA/dependencies are removed after use; permanent tracked regressions are retained.

## TEST acceptance and access blockers

| Required result | Actual result |
| --- | --- |
| Public TEST page in browser | PASS: page loaded, unauthenticated |
| Full coordinated TEST deployment / backup / rollback | BLOCKED: no configured SSH identity, agent or server connector in Work; none performed |
| Current release files on TEST | Not deployed by this Work; inspected public assets differ from source |
| New isolated ordinary account registration/verification/login | BLOCKED by verified-deployment prerequisite; not attempted against the older release, no account/password created |
| Real provider outside50 / Workspace model prompt | BLOCKED — CREDENTIALS REQUIRED and coordinated deployment |
| Real provider OAuth / GitHub OAuth/repository journey | BLOCKED — CREDENTIALS REQUIRED and coordinated deployment; existing connections untouched |
| Actual TEST SSE/history/Todo/questions/abort/session/file journey | BLOCKED by deployment/login; earlier local evidence is not substituted |
| Actual TEST ordinary-user Shell denial / account separation | BLOCKED by deployment/login; source/native-local checks are separate |
| Authorized project-manager Shell | BLOCKED until a verified project-limited execution boundary exists |
| VPS service ExecStart/enable/recovery/logout/process count | BLOCKED by server access; no VPS service was inspected/restarted |
| Cache identity / actual7/14-day schedule on VPS | BLOCKED by server access; previous actual local cache limitation remains documented |

No actual TEST file, environment, Nginx configuration, service, original secret, database, Native store/cache, project or connection was changed. No account verification bypass or role elevation was used. `master`, LIVE, Preview sources/services and workflows were untouched.

## Exact safe operator continuation

Run only the read-only inspection command in [NATIVE_TEST_COORDINATED_RELEASE.md](NATIVE_TEST_COORDINATED_RELEASE.md#first-step-actual-test-comparison-no-deployment) on the existing TEST host using its authorized operator access. Fetch `updates`, extract the reviewed revision’s release utility to a temporary file, and run its `inspect`; do not pull/reset the working TEST checkout. Return only the tool’s safe JSON, not `.env`, tokens or raw Nginx/systemd environment. Existing installed routing/working patches must be reconciled before prepare/apply/activate; current first-install guards intentionally refuse unsupported existing layouts.

The complete source bundle now has **18 runtime files**, adding `services/policy.py`, `services/providers.py` and `services/workspaces.py` to the previous15. The private18098 metadata allowlist additionally needs original `/path`. Preserve all exact preimages/permissions and original secrets. The unchanged three-file UI workflow cannot deploy these dependencies and was not dispatched. After compatible full TEST staging/activation, perform the requested newly registered ordinary-user and administrator acceptance journey once, using the supported verification flow and securely provided authorized credentials, then address failures and dedicated pre-launch hardening. Do not open external access while the listed critical boundaries remain unverified.

Pinned read-only operator command for this tested source (no application/config/service writes):

```bash
(
  set -eu
  cd /home/tahir/opencode-gateway-test
  revision=1c7deafe04a8260f7ec9c4e8d171ed5dafc142f6
  git fetch --no-tags origin updates
  git merge-base --is-ancestor "$revision" origin/updates
  tool=$(mktemp /tmp/native-test-release.XXXXXX.py)
  cleanup() { python3 -I -c 'import os,sys; os.unlink(sys.argv[1])' "$tool"; }
  trap cleanup EXIT
  git show "$revision:scripts/native_test_release.py" > "$tool"
  sudo /usr/bin/python3 -I "$tool" inspect --source "$PWD" --revision "$revision"
)
```

Publication changed14 tracked paths: AGENTS.md; app.js; management.js; native-session-client.js; backend/app/routes/native_sessions.py; backend/app/routes/workspaces.py; backend/app/services/native_provider_accounts.py; backend/app/services/policy.py; backend/app/services/providers.py; backend/app/services/workspaces.py; scripts/native_test_release.py; docs/NATIVE_TEST_COORDINATED_RELEASE.md; docs/PROJECT_HANDOFF_AND_REMAINING_WORK.md; docs/NATIVE_CONNECTIONS_SHELL_ACCEPTANCE.md(new). No tracked file deleted. Source tree verified byte-for-byte against GitHub GitData before advancing only `updates` with an expected-parent guard.
