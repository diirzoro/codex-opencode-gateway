> **Current v3.7/UX follow-up,25 October:** earlier Native TEST deployment succeeded (Actions run40193999369, backend source8e2a5c60af40f86c6888a4806922c0a537dfb6d2); do not repeat first-install preparation. The current owner-created manual `deploy-updates-test.yml` supports `audit-test`/`deploy-test` and the18-file manifest through `scripts/test_diff_only_rollout.py`. This UX patch changes five existing manifest files only; inspect and review exact installed preimages before dispatch, preserve unknown modifications, and use retained private preimage backups. The older three-file workflow/no-deployment statements below are historical. This source session has not dispatched/deployed the UX patch or created a VPS backup. No config/port/IP change or shared Native restart is authorized/needed. See [NATIVE_UX_SECURITY_ACCEPTANCE.md](NATIVE_UX_SECURITY_ACCEPTANCE.md).

> **Latest v3.3 follow-up,25 October:** read [NATIVE_CONNECTIONS_SHELL_ACCEPTANCE.md](NATIVE_CONNECTIONS_SHELL_ACCEPTANCE.md). Current bundle18 files adds services/policy.py, services/providers.py and services/workspaces.py; existing protected18098 management allowlist must include original `/path` metadata. No deployment occurred. Administrator Shell stays disabled until verified project-limited enforcement. The15/eight-file descriptions below are historical. Obtain real TEST inspect and reconcile existing routing before any mutation.

# Coordinated Native TEST release — 22 October 2026

> **25 October development override:** read [NATIVE_DEVELOPMENT_1194.md](NATIVE_DEVELOPMENT_1194.md) first. The current bundle has 15 runtime files (the original eight plus management.js, routes/workspaces.py, services/native_provider_accounts.py, services/github.py, routes/admin.py, services/native_catalog_maintenance.py and enhancements.js). Activation is `activate --plan "$plan"`, without `--owner-id`. Authenticated TEST admission replaces the owner gate. The existing native service/listeners are reused; private 18098 management routes add native auth/OAuth/auth-method metadata and session rename. Existing environment keys/index/workflows/data stay protected. Preparation privately verifies healthy existing 1.18/1.19-family Native; it never installs/upgrades/restarts the native engine merely because of a version number. The paragraphs below are the historical first-install baseline and their owner-ID/eight-file descriptions are superseded by this override.
>
> See [NATIVE_CATALOG_MAINTENANCE.md](NATIVE_CATALOG_MAINTENANCE.md) for the current storage-first refresh/capabilities follow-up. **Actual state is not reconciled:** public TEST already includes a Native client, and served files differ from the new release. The tool still refuses pre-existing release-owned paths/routing and unknown patches. Obtain actual read-only inspect/config comparison before selecting a compatible coordinated update; do not run first-install prepare blindly. No SSH/server deployment was performed by the 25 October source change. The three-file UI workflow must not deploy newer frontend dependencies against an older native backend/client.

This is a separate **operator-run coordinated release**, not the existing three-file UI workflow. That workflow is unchanged and must not be used to activate this implementation. No `master`/LIVE, database, project/workspace, key, existing environment file, existing systemd unit/drop-in or Preview change is part of this release.

## Exactly what is installed

`scripts/native_test_release.py` is a short-lived deployment utility, not a service, runtime, queue, agent or Preview engine. It uses only Python's standard library. It never runs SQL, Alembic, Docker, an OpenCode binary, or starts/restarts the native OpenCode service.

All eight runtime dependencies are staged together while Gateway TEST is stopped:

- `app.js`
- `dashboards.js`
- `runtime-client.js`
- `native-session-client.js`
- `backend/app/main.py`
- `backend/app/routes/native_sessions.py`
- `backend/app/routes/agent.py`
- `backend/app/services/opencode.py`

`index.html`, management, configuration, requirements and existing service/environment files are preserved and fingerprinted. Existing `main.py` injects the native adapter only when Native is enabled; no independent frontend deployment introduces a missing-script reference.

The coordinated configuration changes are restricted to:

| File | Change |
|---|---|
| `/etc/nginx/sites-available/opencode-gateway-test` | One include inside the existing TEST TLS block; all existing domain, certificate, Gateway and Preview bytes retained |
| `/etc/nginx/conf.d/opencode-native-test-session-local.conf` | Append loopback permission/question read/reply/reject routes, reusing the exact existing private Basic header |
| `/etc/nginx/snippets/opencode-native-coordinated-test.conf` | New internal named redirects to existing 18097/18098; no public raw engine listener |
| `/etc/opencode-gateway-test/native-release.env` | New root-only noncredential feature file; initially false, then true plus explicit existing owner UUID |
| `/etc/systemd/system/opencode-gateway-test.service.d/zzzz-native-release.conf` | New TEST-only drop-in appending that feature file; original unit, limits and other drop-ins stay byte-for-byte unchanged |

No existing `.env` or shared PostgreSQL credential is rewritten. A separately appended EnvironmentFile avoids replacing original keys/configuration. The utility verifies the actual TEST process DB/domain and feature switch; secrets are never printed or saved to the report. The active native service and its credentials/storage are reused, not restarted.

## First step: actual TEST comparison, no deployment

No SSH identity/agent is configured in Work, so **no actual TEST comparison or deployment has occurred yet**. The operator must run this first on TEST and return only its JSON output. The output contains file hashes/modes and safe readiness flags; no environment, password, token or Authorization values.

Choose the exact published coordinated release SHA after reviewing it, fetch `updates`, and extract only its tool into a private temporary file. `-I` prevents importing code from an untrusted current/temp directory. This does not grant new sudo rights or put a sudo password in GitHub Secrets.

```bash
(
  set -eu
  cd /home/tahir/opencode-gateway-test
  git fetch --no-tags origin updates
  revision=$(git rev-parse origin/updates)
  tool=$(mktemp /tmp/native-test-release.XXXXXX.py)
  cleanup() { python3 -I -c 'import os,sys; os.unlink(sys.argv[1])' "$tool"; }
  trap cleanup EXIT
  git show "$revision:scripts/native_test_release.py" > "$tool"
  sudo /usr/bin/python3 -I "$tool" inspect --source "$PWD" --revision "$revision"
)
```

The expected source ref is `updates`; the exact SHA is reported and must match the reviewed release. TEST's HEAD and local changes are **not** reset, merged or pulled. File comparisons accept only exact bytes from approved original baseline `3d4d52d6`, published native implementation `c0d830bc`, or the exact new release. Unknown working patches stop preparation; reconcile/merge them first, never force an overwrite. Configuration shape mismatches, an unexpected service user/directory/port, existing release-owned config paths, symlinks, wrong DB/domain or non-TEST site stop the operation.

The comparison reads the existing running TEST process environment privately only to verify its scope. It does not repeat Docker, mount, provider or PostgreSQL diagnostics. It does not print `nginx -T`, `.env`, systemd Environment or credentials.

## Coordinated staging, activation and rollback

Only after the comparison is reconciled, use the same reviewed temporary tool/revision in an operator SSH session. The following are separate phases; values for `plan`, `review` and `owner` are the **actual** preparation output and existing pilot UUID, never invented placeholders or new accounts.

1. `prepare --source "$PWD" --revision "$revision"`
   - Creates root-private `/var/backups/opencode-native-coordinated-test/<id>/` with exact preimages, modes/owners, candidate bytes and an immutable review digest.
   - Does not change the application, Nginx or services. Authentication-bearing backups/candidates are root-owned mode600 in a mode700 directory.
2. `review --plan "$plan"`
   - Prints source hashes and the generated config diff with Authorization/secret lines removed and no old context lines. This is read-only.
   - Candidates are produced by narrow append-only edits to the actual TEST configs. Unsupported layouts stop rather than guessing.
3. `apply --plan "$plan" --review-sha256 "$review"`
   - Refuses all post-review drift and unknown edits. An exclusive operator lock prevents two deployments overlapping.
   - Stops only Gateway TEST, writes the disable switch first, installs **all eight dependencies and all reviewed Nginx pieces**, validates Nginx and reloads it, then starts the same Gateway TEST service with Native false.
   - Checks runtime health/switch, unchanged protected originals, all deployed file hashes, HTTPS frontend bytes and a real unauthenticated Gateway401 on the public native route.
   - Ends in `staged-disabled`, never “accepted”. No partial frontend release is served while files are copied.
4. `activate --plan "$plan" --owner-id "$owner"`
   - Allowed only after complete staging/health. Enables only the existing pilot via the new private feature file, restarts Gateway TEST, confirms the actual process flag/owner, correct public HTML/client/JS bytes and Gateway login boundary.
   - Ends in `activated-acceptance-pending`; no real chat success is fabricated.
5. `rollback --plan "$plan"`
   - Stops Gateway TEST, restores only exact original files and modes/ownership, removes only files this plan recorded as absent, reloads validated Nginx and restores the original TEST service state.
   - Never resets the DB, Git HEAD, customer files, native history or keys. Native-created session mappings/data remain preserved even when the old UI cannot resume them.

Run these through `sudo /usr/bin/python3 -I "$tool" <phase> ...` using the existing operator's authorized privileges. No blanket sudo rule, new root service, workflow or privileged helper is installed. Keep the private backup until real acceptance and a stable observation window succeed. The only other operational artifact is the root-only `/run/lock/opencode-native-test-release.lock` used by mutation phases; inspect/review do not create it.

Staging/activation failures attempt immediate restoration. Unknown concurrent edits are never overwritten during rollback. Interrupted partial copies are recognizable through before/after hashes and recoverable with the same private plan. If global Nginx validation/reload still fails after restoring originals, Gateway TEST is restored independently and the report requires operator Nginx review; no LIVE config is edited or LIVE app service started. Existing shared Nginx is reloaded only for the reviewed TEST config.

## Focused TEST acceptance after activation (not yet executed)

Use the existing pilot's normal secure login; do not reset an account, manufacture cookies, publish keys or bypass approvals.

1. Open an owned available Workspace. Confirm automatic providers/models/agents from `/native-session/`, and no per-workspace engine spawn or shared browser Basic credential.
2. Create two native conversations; use actual available model choices. Send one short real prompt and observe text before completion over native SSE. Switch away and back, reload, and confirm native history/model selection without mixed events.
3. Disconnect/reconnect the browser stream while work completes. Confirm actual native status is recovered, not a stale “running” state. The reconnect fix is included in this release.
4. In that owned test context, have the native agent create one clearly named disposable acceptance file and Todo. Verify the actual file and native Todo, one real question/resume, allow-once, rejection and Stop. Remove only the explicitly disposable acceptance file afterward; preserve existing files and records.
5. Verify another account and foreign Workspace/session/request IDs cannot enter the pilot/native route, caller directory/routing headers cannot change its target, and no Basic/key appears in browser responses/logs. This remains a single-owner pilot, not OS/customer-isolation certification.

Preview remains untouched/deferred. Do not expand acceptance to another engine, custom Runner, payments, key migration or unrelated cleanup. Real provider execution may incur the owner's existing provider usage; use one authorized short test, not a catalog-wide test.

## Evidence and current deployment status

- **36 local deployment transaction tests passed**: read-only comparison; exact approved baselines; root-private backups/review; secret redaction; site/certificate/Preview preservation; wrong domain/upstream/auth/listener rejection; coordinated disabled staging; activation prerequisites; private-env/config/source drift rejection; candidate/backup allowlist protections; normal rollback; copy/Nginx/health/activation-write failures; interrupted-copy recovery; rollback that preserves external changes and restarts original Gateway even when Nginx needs review. Real temporary files/permissions with controlled systemctl/Nginx/HTTP calls; not actual VPS execution.
- Actual native-client VM reconnect test passed: native status snapshot clears a missed terminal event, and a late response from a closed stream or older snapshot is ignored. A status-read failure after native204 does not fail or retry an already accepted prompt. Native 1.18.32 `/session/status` was already verified in the prior real isolated-engine acceptance; no guessed API added.
- Python compilation, JS syntax and diff checks passed. Existing native-engine/owner/full-backend results remain recorded in NATIVE_SESSION_BATCH1.md; unrelated passing tests were not rerun. Temporary task test files are removed after verification; permanent security tests remain.
- **Changed source:** `native-session-client.js`, this release utility and deployment documentation/handoff.
- **Actually deployed to TEST by Work: none.** No SSH credentials/session are available here. Actual file comparison, generated server plan, live Nginx validation, activation, real authenticated prompt/SSE/file/permission acceptance and post-deployment resource behavior remain unverified.
