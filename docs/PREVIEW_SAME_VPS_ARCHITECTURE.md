# Smart Preview — same-VPS isolated-worker architecture
Decision: 2026-10-16. Preview worker will run on the SAME VPS as Gateway, but as a separately isolated service. This is a deployment design, **not** proof of safety or a running implementation.
Branch: updates. Never touch master/Live without explicit approval.

## Trust boundaries
1. Public nginx -> Gateway application (Test: port 8001; Live untouched). Gateway authenticates owner and workspace and accepts an explicit Start Preview POST only. GET/status and browser reconnect cannot start anything.
2. Private worker-control process (dedicated unprivileged service account, separate internal Unix socket, strictly checked peer identity). Not publicly reachable; no authentication tokens, SQL credentials, .env, SSH keys or OpenCode credentials inside customer workloads. The Gateway process must NOT gain access to a Docker or container-runtime privileged socket.
3. Privileged provisioning *helper* is separately owned, locked to a fixed set of trusted prebuilt image digests and hardcoded resource/security settings. Require an authenticated private request from the worker-control service; never accept customer-controlled mounts, container flags, image names, commands or network routes. Rootless runtime preferred where supported and verified. Docker socket access must not be granted to the Gateway or containers.
4. Per-preview isolated sandbox: unprivileged UID, user+mount+PID+network namespaces, drop all capabilities, no-new-privileges, read-only root filesystem, separate writable quota-limited tmpfs/volume, 1 CPU, memory ~768 MB, disk ~1024 MB, process and execution limits, seccomp/AppArmor, no host devices, no privileged modes. Source snapshot max 50 MiB, validated twice, mounted read-only.
5. Dependency preparation occurs only INSIDE tightly restricted sandbox/build stages with a controlled package cache/network proxy and no access to private/VPS networks. Runtime network defaults deny; outbound network explicitly allowlisted only where justified. Never install npm/pip on Gateway host.
6. Preview website uses a separate origin controlled by nginx plus Gateway auth/ownership checking, bounded reverse proxy to sandbox-internal port only. Never expose arbitrary customer ports publicly. No cookies/credentials shared with Gateway origin. Enforce CSP, timeouts, no sensitive internal traffic.
7. Durable PostgreSQL leases with generation fencing, verified worker heartbeat and atomic slots. Queue at saturation. Track real RAM/CPU usage; logical groups of 50 registered users are NOT 50 concurrent worker slots. Restrict concurrency to independently measured VPS headroom.
8. User Start only; STOP revokes preview route, destroys sandbox, verifies cleanup and only then releases slot. Crash reaper performs identical cleanup. After 300 seconds of meaningful user inactivity stop only Preview-owned process, not agent execution or ongoing independent builds. Panel stays open.
9. Operating limitation: kernel-sharing containers on one VPS are not equivalent to a separate VM/host. Before admitting untrusted customer code require a threat-model/security review, tested isolation and fail-closed controls. If VPS cannot provide acceptable isolation, deny dynamic Preview rather than using unsandboxed node/python.

## Confirmed capacity input — owner reported VPS size
- VPS capacity reported by owner: **4 GB RAM, 80 GB total storage**. CPU count, usable/free disk and RAM, swap, OS, current Gateway/OpenCode/PostgreSQL use are not yet measured.
- Begin with a strict **single dynamic preview slot maximum** (not 50 concurrent). Even one isolated container must remain **disabled until measured headroom and sandbox security pass**.
- Provisional per-preview cgroup envelope: 1 CPU core, up to 768 MiB memory and 1 GiB ephemeral disk, up to 128 PIDs, 300s Preview idle threshold. Add explicit host-reserved headroom for Gateway, OpenCode, PostgreSQL and OS; if headroom is insufficient, return queued/unavailable instead of causing host OOM. These are limits, not guarantees.
- The 80 GB is **total storage**, not free space. Inspect `df -h`, inode availability, container image/cache size and backups before allocating any sandbox storage.
- Packages/builds can exceed 768 MiB or 1 GiB; refuse or queue projects that do not fit, rather than raising host limits blindly. Never run package install or project code on the host.
- Upgrade RAM or use a separate worker host when telemetry shows sustained pressure; 4 GB is unsuitable for promising many simultaneous dynamic previews.

## Test rollout prerequisites (all NOT YET VERIFIED)
- [ ] Verify current VPS OS/kernel, RAM, CPU, free disk, available namespaces/cgroup v2, seccomp/AppArmor, rootless runtime, reverse-proxy isolation and service privileges without altering Live.
- [ ] Decide safe max workers based on measured resources. No default of 50 concurrent users.
- [ ] Implement private worker service, attested heartbeat, constrained provisioning helper and fixed image digests.
- [ ] Implement isolated build/preparation, immutable snapshot validation, backend dispatch, routing, idle reaper, logs and observability.
- [ ] Execute Alembic 0019/0020 migrations and concurrency/security/E2E tests on disposable Test copies.
- [ ] Deploy only to Test with new isolated service; preserve existing staging .env, workflows and Live settings.
- [ ] Require explicit owner approval before any Live promotion.

## Progress — host headroom gate (2026-10-16)
- Added `backend/app/services/preview_host_gate.py` as a pure, fail-closed admission check: one concurrent preview maximum; requires trusted host telemetry and reserves 1536 MiB available RAM and 4096 MiB free disk after prospective 768 MiB RAM / 1024 MiB sandbox allocation.
- Added `backend/tests/test_preview_host_gate.py` regression tests for low RAM, low disk, forged/invalid telemetry, unknown state and slot saturation.
- **Advisory only**: no host collector, authenticated ingestion or real isolated runner has been deployed. This gate is not yet wired to actual reservation and does not prove that capacity is available. Tests committed but not run on Test.
- Implementation must use system-level enforcement and fresh trusted measurements, not a browser-provided `collector_verified` field. Actual production safeguards require independently measured overhead and security review.

## Progress — enforce headroom in reservation (2026-10-16)
- Wired the fail-closed host admission rule into `preview_capacity_store.reserve()`: without trusted `HostTelemetry`, no worker slot can be reserved. Preserves worker row locking and owner/generation validation.
- Extended `test_preview_capacity_store.py` to supply verified 4 GB VPS test telemetry and reject missing host telemetry before any DB query.
- This is **not a live host telemetry collector**, and the private dispatcher is not yet implemented. A `collector_verified=True` value supplied by clients must never count as attestation. Actual code execution remains disabled and tests not yet run on Test.
- Outstanding: authenticated telemetry service, sandbox provisioner, proxy and cleanup, PostgreSQL concurrency and E2E tests. Security isolation on the same VPS requires review before enabling dynamic Preview.

## Progress — Linux resource probe (2026-10-16)
- Added `backend/app/services/preview_host_probe.py` to read Linux `/proc/meminfo` MemTotal/MemAvailable and `shutil.disk_usage` for the intended worker storage path. No shell subprocess, package install, worker provisioning, or host mutation.
- Added `backend/tests/test_preview_host_probe.py` for accurate units, missing-value refusal and `collector_verified=False` by default.
- **Important:** probe is not wired to a verified private collector; telemetry from normal Gateway/client requests cannot be trusted as attestation. Tests are committed but NOT executed here. No isolated worker has been deployed and Start Preview remains fail-closed.
- Immediate next work on Test: measure VPS actual spare RAM/disk, verify cgroup v2 and sandbox security support, implement and test dedicated unprivileged worker-control service with authenticated local transport and isolated provisioning. Do not use Docker on the Gateway service.

## Current status
The repository has planning and dormant lease/capacity code and an explicit fail-closed Preview start (503). No worker is running and dynamic Preview is not usable. Same VPS selection does NOT make these checklist items complete.
