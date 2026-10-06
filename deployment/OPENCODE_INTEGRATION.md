# OpenCode runtime included in a Gateway release

The Gateway release includes its OpenCode adapter at `backend/app/services/opencode.py` and the Gateway systemd unit. The OpenCode runtime binary and its existing server unit are separate host software; they are not copied into the project archive. This avoids shipping an unverified executable or overwriting the OpenCode service already reported on the VPS.

## Runtime responsibilities in the current source

- `OPENCODE_BASE_URL` is backend-only and currently supports health diagnostics against the internal OpenCode service.
- Customer workspaces, project files and session ownership are checked by Gateway APIs.
- When explicitly enabled, the adapter starts a distinct OpenCode process for each workspace using `OPENCODE_BINARY`, a workspace directory and per-workspace HOME/XDG state.
- The frontend receives only Gateway `/api/...` endpoints. It never receives the OpenCode URL, port, runtime password, or raw OpenCode UI.
- `OPENCODE_RUNTIME_MODE=local` is enabled in the production example at the owner's request. It starts the per-workspace OpenCode process path; it is not a security sandbox and must not be exposed to untrusted public customer workloads before isolation controls are added.

The current subprocess separation is not an OS or network sandbox. Do not enable it for public customer workloads until a reviewed execution boundary blocks cross-workspace file access, host/metadata/database access, and uncontrolled resource use. A single shared OpenCode process is not a substitute: its provider auth and runtime state can be shared between customers.

## Host prerequisite

Install a reviewed OpenCode 1.18.31 or 1.18.32 Linux CLI separately on the Gateway host, then set `OPENCODE_BINARY` to its absolute executable path in the protected backend environment. The adapter accepts these version strings, but this project has not performed live execution acceptance against the reported VPS binary. Keep the existing `opencode-web.service` on loopback and do not install a duplicate service from this source package.

After upload, an operator can run `sh deployment/check_opencode_runtime.sh` from the release directory to confirm the installed CLI path and version. This is a non-mutating prerequisite check; it does not install software, start a service, connect to OpenCode, or enable customer execution.

The operator-reported `http://127.0.0.1:4096` address is the VPS's loopback, not the developer PC's loopback. Do not copy it into frontend code or expose its port through a public reverse proxy. Installing the source package alone does not connect client messages to that shared service.

## Before enabling real customer execution

1. Before accepting untrusted customer work, deploy a production isolation manager for each workspace (separate filesystem, credentials, HOME/XDG, process identity, limits and recovery).
2. Bind the Gateway privately behind the approved HTTPS reverse proxy and preserve existing environment secrets.
3. Configure the actual OpenCode executable path and confirm the runtime version on the target host.
4. Perform real acceptance in the already approved application environment after deployment is explicitly authorized. Do not create a test server, test DB, or test workspace to work around missing prerequisites.
