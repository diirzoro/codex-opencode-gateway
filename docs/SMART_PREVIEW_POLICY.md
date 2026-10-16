# Smart Preview Policy & Implementation Roadmap
Status: APPROVED PRODUCT DESIGN — NOT IMPLEMENTED
Agreed: 2026-10-16
Repository: diirzoro/codex-opencode-gateway

## Scope and branch discipline
- This document is shared between `updates` (development/test) and `master` (live) for continuity; adding it to master DOES NOT authorize a live feature deployment.
- All executable Preview changes, migrations, and tests go to `updates` first. Test on the separate Test deployment; promote to `master` only after explicit review/approval.
- Keep Live and Test databases, ports, OpenCode runtimes, filesystem roots, secrets, services, and GitHub Actions workflows separate and unchanged unless separately approved.
- No Playwright. Do not install or use Playwright in Preview.

## Product behavior
1. Preview opens INSIDE the existing Workspace Preview panel. The panel stays open until the user closes it manually.
2. Static output can remain visible without an active runner. For dynamic previews, after **5 minutes of inactivity** STOP the server-side execution lease while keeping the panel open with an explicit inactive/stopped state. Do NOT restart automatically: only a new explicit Preview/Start request by the user can create a fresh lease. On user request, revalidate authorization, workspace revision and available capacity before starting. Closing the panel stops the owned execution session; it must not end the chat or coding session.
3. Local projects: target a 50 MB maximum **source snapshot** per preview. Validate actual uncompressed total, file count, depth, per-file sizes, symlinks and special files. This is NOT a memory/CPU limit and is not a guarantee all 50 MB projects can build.
4. GitHub projects: show changed files and diffs, real preview of the checked-out working tree/branch where supported, and optional external link if one already exists. A thumbnail can be captured by a separately approved method in the future but is not required. Never fabricate a visual result, auto-commit, auto-push or deploy.
5. Preserve existing Workspace layout and account-level provider connections; do not disrupt chats, agents, or filesystem work when preview is started/stopped.
6. Cache a **last successful** static/build artifact per authorized project/revision, with suitable TTL/storage quotas and invalidation on changes. Authentication and ownership checks remain mandatory on every request.

## Smart classification and resource tiers
| Project kind | Approach | Continuous runtime needed? |
| --- | --- | --- |
| Plain HTML/CSS/JS | Serve validated static assets on a separate restricted origin | No |
| React/Vite/Vue or similar static-capable frontends | One isolated build on change, then serve generated static artifact/cache | No after build |
| Next.js with supported static output | Isolated build/export and cache if compatible | No after build |
| Node/npm server, Next.js SSR, Python/FastAPI/Django and other backends | Short-lived per-project isolated runtime when a verified worker is available | Yes during activity |
| Unsupported framework | Honest unsupported/diagnostic state, not a pretend screenshot | No |

- Detect project by real files/manifests and approved profiles, not names or generic guesses.
- JavaScript package manager is selected from manifests/lockfiles; `npm ci`/`npm run build` and ALL install scripts/build hooks run only in isolated build workers, NEVER on the Gateway VPS host.
- Playwright is OUT of scope.

## Pool policy and fair scheduling
- Smart Preview Gateway may group **50 users per logical pool initially**, adjustable up to **100 after measurements**. This is an organizational cap, NOT a promise of 50–100 simultaneous active app runtimes.
- A pool is a logical scheduling/quota unit containing independent build/runtime sandboxes and static-serving paths; do NOT execute code belonging to different tenants in one unisolated process/container.
- Static/cached views should not consume dynamic worker slots. Build tasks use their own queue; dynamic sessions use limited, independent per-project leases. Limits must consider CPU, memory, concurrency, disk, queue wait and actual workload, not merely account count.
- New pool may be created when the logical membership threshold is reached ONLY if verified physical capacity and safe worker isolation are available. Otherwise queue/reject gracefully without disrupting chat/API.
- Pool membership need not be permanently tied to a user; account ownership and project-specific authorization are always checked. No mixing of snapshots, logs or previews between tenants.
- No automatic server capacity is created by creating a logical pool.

## Execution isolation: release gate
- Never run customer commands directly on the main VPS host, in the OpenCode/Gateway process, or as a privileged Docker container.
- Dynamic/build workers must be isolated with enforced CPU/RAM/disk/process/time/log quotas; non-root UID; read-only base filesystem; short-lived writable scratch; no Docker socket, host mounts, secrets or privileged capabilities; controlled network egress during dependency preparation and blocked/internal-protected runtime networking.
- Ensure no access to localhost-only Gateway services, metadata endpoints, PostgreSQL, other tenants' files, or Live/Test credentials. Validate source snapshots and serve previews through a separate origin with authenticated tenant/project/session routing, secure CSP and cookie isolation.
- A dynamic preview inactivity lease expires after 300 seconds without genuine activity; background polling, status checks, or merely keeping the tab open must NOT reset the idle timer. A new explicit user Preview request is required to restart. Static/cached previews do not need a live process and are not automatically hidden after 5 minutes.
- Session leases and TTL reaping must survive Gateway restart. Revoke routes before destroying a lease. Enforce authorization when starting, viewing, resuming and stopping.
- If worker/security verification fails, fail closed; keep existing safe static HTML preview, do not replace 503 with unsafe Popen/docker run.
- A single Docker container is not a sufficient security boundary by itself; hosting arbitrary untrusted user code might require a dedicated worker VPS or stronger isolation before enabling paid/public access.

## Commercial capacity and scaling
- Pilot on existing hardware with conservative measured concurrency; avoid paying for idle fleets.
- Target increasing server to 16 GB RAM and larger disk at about **50 paying subscribers**, or EARLIER if observed saturation warrants it. Evaluate adding a physically separate Preview Worker VPS rather than only increasing the main Gateway's RAM.
- Track measured active previews, queue time, CPU/RAM, disk usage, build success, cache hit rate, expiry/reaper success, errors, and costs. Upgrade from measurements, not raw signups.
- Growth aim: attract the first 50 paying subscribers and expand safely; do not advertise unlimited previews.

## Implementation checklist (updates branch only)
- [ ] P0: inventory current preview backend/frontend and integration points; retain current working read-only HTML renderer until replacement validated.
- [ ] P1: implement robust project detection, validated 50 MB snapshot limits, safe static asset routing, independent origin and tenant tests.
- [ ] P2: implement build-job interface and per-pool scheduler/leases/queues/status/stop/resume, fail-closed without configured worker.
- [ ] P3: add separately isolated build worker for supported npm static frameworks, cache signed/owned build artifacts and invalidate by revision; test without leaking dependencies or secrets.
- [ ] P4: implement Workspace embedded UX, manual close, refresh, graceful idle stop and resume, GitHub diff/working-tree integration.
- [ ] P5: enable dynamic Node/SSR/Python profiles ONLY after dedicated worker security acceptance and resource benchmarks.
- [ ] P6: test tenant isolation, malicious manifests, symlink/path traversal, network/credential boundaries, OOM limits, queues, TTL cleanup, staging rollbacks and load tests; then seek explicit Live approval.

## Current implementation at agreement date
- `backend/app/services/preview.py` provides read-only static HTML rendering with restrictive CSP and asset inlining and framework detection; its 5 MB embedded asset limit is not the proposed 50 MB project snapshot limit.
- `backend/app/services/preview_runner.py` has a fail-closed plan/status interface but `runner_available=false` and `execution_enabled=false`; start returns HTTP 503.
- `backend/app/services/preview_snapshot.py` implements source snapshot constraints, not execution.
- `dashboards.js` includes an embedded Preview iframe and panel with Start/Refresh/Stop.
- Actual dynamic/npm preview is NOT yet available. This document is a product policy, not an assertion that the design has been implemented.

## Maintenance rule for all coding agents
Read this policy before changing Preview. Preserve all approved constraints. Amend this document whenever product decisions or implementation status change, after validating actual code and tests; do not mark a checkbox complete merely because code was proposed.
