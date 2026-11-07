# Preview configuration transfer and source of truth

Updated2026-10-18. Owner authorizes transferring source and reusable Preview configuration to master, excluding Live operational settings, ports and secrets. This document is a mapping, not an installer.

| Component | Repository source | Environment boundary |
| --- | --- | --- |
| Browser grants | backend/app/services/preview_access.py; backend/app/routes/preview_public.py; backend/app/main.py | Separate verified HTTPS origin; Strict login cookie and grant/session/ownership checks preserved. |
| Project routing | backend/app/services/preview_runner.py; backend/app/routes/workspaces.py | Owned project/workspace roots stay environment-local. |
| Isolated execution | backend/app/services/preview_worker_server.py; preview_worker_client.py; preview_docker_provisioner.py; preview_container_spec.py | Verified rootless engine, user, socket, limits and job isolation required. |
| Browser controls | dashboards.js; index.html | Explicit Start, read-access renewal, sandboxed New Tab and owned Stop. |
| Proxy examples | docs/examples/preview-test-http.conf; preview-test-https.conf | TEST-specific examples; never install on Live unchanged. |
| Evidence | docs/PROJECT_HANDOFF_AND_REMAINING_WORK.md, sections53–58 | TEST acceptance is distinct from Live/framework/security acceptance. |

## Settings that must remain environment-local

| Setting/resource | Required treatment |
| --- | --- |
| PREVIEW_PUBLIC_ORIGIN | Verified origin of that environment; never use TEST's hostname for Live. TLS and restricted routing first. |
| PREVIEW_WORKER_ENABLED | Current code accepts only test. Source merge does not activate Live; do not disguise Live as TEST to bypass this gate. |
| PREVIEW_WORKER_URL / PREVIEW_WORKER_TOKEN | Private loopback endpoint and secret. Do not commit, print or assume credentials can be shared. |
| CREDENTIALS_ENCRYPTION_KEY | Keep each Gateway's existing key. No rotation or replacement is part of source transfer. |
| PREVIEW_IMAGE_NODE / PREVIEW_IMAGE_PYTHON / PREVIEW_IMAGE_PHP | Worker-only pinned references; available images do not certify framework support. |
| DOCKER_HOST / service environment | Actual verified rootless socket and unprivileged identity; no rootful/privileged fallback or global upgrade. |
| Ports, database, roots, TLS files | Keep environment-specific values. Worker currently binds127.0.0.1:8791; another worker cannot bind the same address/port. |
| .github/workflows | Preserve master blobs exactly, including its TEST safety stub; keep the real TEST deployment definition on updates. Never synchronize these files blindly. |

## Historical assets and cleanup

deploy/install-preview-worker-test.sh, deploy/refresh-preview-worker-test.sh and deploy/opencode-preview-worker-test.service are historical TEST provisioning assets, not the current rootless VPS installation recipe and never Live installers. Current TEST Worker code resides under /opt/opencode-preview-test. Old paths/dependencies must not overwrite its verified overrides. Do not execute these assets for the current deployment or delete them without proving repository/operator consumers no longer need them.

No tracked node_modules, virtual environment, runtime/workspace directory, database dump or ordinary generated log was found in Git source. Tests/audit screenshots/handoff are retained evidence, not running services. Removing them would not stop a process or free VPS Docker layers. VPS cleanup and new backup are deferred until GitHub work is complete, per owner instruction.

Keep working static Preview and non-opt-in behavior; these remain required paths. Do not remove code merely to shrink the repository. Application development remains on updates; reviewed master promotion preserves its deployment files.

## Remaining gates

Built-ins Node QA is owner-verified on TEST. React/Vite/Next dependency builds, Python, POST/WebSocket/HMR, durable cleanup, global resource admission, reboot recovery and adversarial two-account/grant lifecycle checks remain open. Five-minute idle shutdown is a requirement, not a certified worker reaper. Live activation and server cleanup have not occurred. Login/page and OpenCode/Agent startup latency still need measurement and targeted repair; documentation cleanup does not claim a performance fix.
