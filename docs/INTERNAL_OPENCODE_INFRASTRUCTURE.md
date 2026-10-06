# Internal OpenCode infrastructure update — 2026-10-05

## Initial findings

1. Code/config required changes: the old backend variable was OPENCODE_URL with default port 4196. Shared health diagnostics still read OPENCODE_SERVER_PASSWORD. Example environments, helper script and README needed the new variable. An unserved prototype snapshot contained a retired public runtime address.
2. Already matched: customer authentication is Gateway cookie authentication; frontend config uses /api only; workspace operations resolve ownership and entitlement. Shared OpenCode is health-only. Local coding calls use per-workspace runtimes, not the shared service.
3. Isolation still needed: OS/filesystem/network sandbox, resource quotas, durable runtime supervision, task leases/recovery and acceptance with untrusted repositories. Existing separate directories/processes are trusted local development contexts only.

## Current infrastructure authority

The user reports that Ubuntu opencode-web.service is active, responds with HTTP 200, and binds only to 127.0.0.1:4096 using --hostname 127.0.0.1 --port 4096. Its old shared username/password were removed. These are user-reported checks; no VPS inspection was performed for this update. Earlier public URL and shared-login instructions are superseded.

Customer Browser → Gateway authentication/API → Workspace Manager → owned isolated workspace → internal OpenCode runtime/context → customer's GitHub repository.

OPENCODE_BASE_URL=http://127.0.0.1:4096 is backend environment configuration only. A localhost address on the development computer is not the VPS localhost address. Without an operator-run SSH tunnel or a local reference service, local reference health can be unavailable; that must not cause a fallback to the retired public URL.

## Changes made locally

- Canonical environment variable is OPENCODE_BASE_URL; default 127.0.0.1:4096. OPENCODE_URL is no longer read. Existing environment files must be migrated manually when later configuring deployment.
- Reject public hosts, URL credentials, paths, query strings, fragments and invalid ports in this configuration.
- Shared health calls do not use any username/password, even if an obsolete environment password is still present.
- Local and production example environments, live-provider helper and README updated. Retired direct URL removed from the unserved prototype config.
- Frontend endpoints and Gateway login flow remain unchanged. No runtime URL or credential is added to browser responses.
- Random private credentials generated for individual local workspace runtimes remain in memory/server processes. These are not the removed shared service login and are never exposed to the browser.
- The shared reference service remains health-only. No customer chat/session/provider fallback to that shared process is enabled.

No database migration or new API is required. No service, firewall, port exposure, credentials, push or deployment change was performed on the VPS. One authorized SSH tunnel attempt failed authentication; no tunnel was created and no remote command was run.

## Implementation status

| Area | Status | Evidence / remaining work |
| --- | --- | --- |
| Gateway authentication and ten-day trial | REAL | Existing account and entitlement routes/tests |
| Frontend through Gateway APIs only | REAL | Explicit static allowlist; browser config is /api; boundary tests |
| Internal unauthenticated reference configuration | REAL locally | Backend configuration/transport tests; VPS state is user-reported |
| Separate customer workspace paths and ownership | REAL locally | Workspace manager and owned endpoint checks |
| Per-workspace HOME/XDG, sessions, provider auth, process/port | PARTIAL | Implemented in trusted local mode; not a public sandbox |
| Production filesystem/network/process isolation and quotas | MISSING | Needs sandbox manager and adversarial acceptance tests |
| Production supervised lifecycle/restart recovery | MISSING | Process registry/tasks remain in one Gateway process |
| Customer GitHub clone/review/commit/push | PARTIAL | Owned authorization/code paths exist; full live acceptance remains |
| Shared OpenCode used as customer runtime | Not enabled | Deliberately no execution fallback to the shared reference |

The installed local adapter contract remains verified against 1.18.31. Earlier read-only reference health reported 1.18.32; this is not proof of API compatibility for production execution.

See SECURITY_MODEL.md and PRODUCT_MODEL_AUDIT.md for launch gaps. Deployment examples remain preparation only.

## Local verification

78 backend tests passed; one paid-model test skipped because no test provider credential was supplied. Added configuration rejection, credential-free shared health, safe public assets/status and no shared execution fallback tests. These tests do not certify the user-reported VPS service or a real assistant response.
