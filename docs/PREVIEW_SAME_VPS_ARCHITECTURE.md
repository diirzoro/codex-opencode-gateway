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

## Test rollout prerequisites (all NOT YET VERIFIED)
- [ ] Verify current VPS OS/kernel, RAM, CPU, free disk, available namespaces/cgroup v2, seccomp/AppArmor, rootless runtime, reverse-proxy isolation and service privileges without altering Live.
- [ ] Decide safe max workers based on measured resources. No default of 50 concurrent users.
- [ ] Implement private worker service, attested heartbeat, constrained provisioning helper and fixed image digests.
- [ ] Implement isolated build/preparation, immutable snapshot validation, backend dispatch, routing, idle reaper, logs and observability.
- [ ] Execute Alembic 0019/0020 migrations and concurrency/security/E2E tests on disposable Test copies.
- [ ] Deploy only to Test with new isolated service; preserve existing staging .env, workflows and Live settings.
- [ ] Require explicit owner approval before any Live promotion.

## Current status
The repository has planning and dormant lease/capacity code and an explicit fail-closed Preview start (503). No worker is running and dynamic Preview is not usable. Same VPS selection does NOT make these checklist items complete.
