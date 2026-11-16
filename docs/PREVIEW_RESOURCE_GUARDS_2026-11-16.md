# Existing preview service activation

The existing dedicated rootless Docker daemon and Python control worker are reused. Pi Central, model providers, chats, payments and project source are not part of this service. Customer runtime code is never launched on the Gateway host interpreter.

## Operating contract

- One dynamic preview at a time across this worker.
- Fixed 0.5 CPU, 768 MiB, 128 PIDs per runtime; no swap allowance beyond memory limit.
- Worker control service: 384 MiB / 25% CPU maximum. Dedicated daemon and dedicated user slice have 1 GiB / 60% CPU ceilings each.
- Idle expiry 300 seconds measured from explicit Start/reuse, absolute expiry 900 seconds, checked every five seconds. Ordinary polling, asset requests and app interaction do not extend this timer.
- Missing or insufficient trusted local RAM/disk telemetry denies launch. Current policy reserves at least 1536 MiB available RAM beyond a 768 MiB runtime reservation and 4096 MiB free disk beyond 1024 MiB planning allowance.
- Read-only source snapshot and root filesystem, unprivileged UID/GID 10001, all capabilities dropped, no-new-privileges, default seccomp and a named enforcing AppArmor profile. Runtime network is none and no ports or Docker sockets are exposed.
- Failed cleanup retains the allocation and retries. Restart reconciliation checks Docker ownership labels before stopping orphan preview containers.
- Graceful worker shutdown stops active previews. Existing rootless infrastructure uses its dedicated user D-Bus manager for enforceable systemd cgroups.

## Trusted Python runtime

Only operator-selected FastAPI/Uvicorn wheels are resolved outside the VPS for CPython 3.12 on Linux x86-64. Wheel checksums are verified during provisioning. They are installed offline in a bounded rootless preparation container without any customer source, requirements, host mounts or network. The resulting runtime image is pinned by immutable SHA256 image ID. This setup happens during administration, not on chat messages or every preview request.

## Connection

Explicit PREVIEW_WORKER_ENABLED=live, a loopback endpoint and the existing private worker token are configured on LIVE. The existing TLS hostname preview-test.opencode-gateway.codes is reused and routed to the LIVE Gateway after checking TEST previews are disabled. The historical name does not select the database. The existing encrypted, session/workspace/owner-bound short-lived browser tickets remain required; customer-code origin only serves read-only preview GET/HEAD assets. Ticket access logging is disabled at that Nginx location.

Activation backs up the Gateway environment, relevant modules and preview Nginx configuration under root-only /var/backups/opencode-preview-activation. If Gateway/Nginx checks fail, these changes roll back. Pi Central is never restarted. Only the existing Gateway restarts to load its preview environment.

## Verification and limitations

Thirteen local tests cover timers, concurrency refusal, cleanup retry, restart reconciliation, shutdown, idle polling, host reserve refusal, explicit LIVE opt-in, immutable image IDs, CPU ceiling, retained startup diagnostics and refusal to delete containers with foreign labels. These tests do not execute customer code or Docker.

The preparation action additionally runs a tiny real isolated Python HTTP application, verifies its actual Docker configuration, fetches JSON and stops the container. Browser acceptance of the separate Python audit project remains required before reporting success.

React/Vite dependency preparation and static artifact caching are still separate unfinished work. Java detection has no executable launch profile. Do not report either language working based on this Python setup. Python supports the prepared FastAPI/Uvicorn entrypoint shape; arbitrary project-specific requirements are not installed automatically.

This is not a complete security audit. Dynamic application interaction uses GET-only asset relay; applications must use relative asset/API URLs beneath the preview ticket path. Idle services retain a small fixed memory footprint even without an active application. Snapshots/images also use disk; the 1024 MiB planning allowance is not an enforced source-volume disk quota.
