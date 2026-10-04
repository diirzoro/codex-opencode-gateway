# Architecture

Updated 2026-10-03. Independent local development project, not affiliated with OpenCode or GitHub. No deployment performed.

## Request path

Browser (`index.html`, `styles.css`, `app.js`) → same-origin FastAPI → require_user → owned metadata lookup → workspace service / OpenCodeService / Git. PostgreSQL stores account and owned workspace metadata. Files stay under WORKSPACE_ROOT; per-workspace OpenCode HOME/XDG/state/logs stay under RUNTIME_ROOT. Session IDs/passwords/physical paths are server-side. Explicit asset routes serve only approved public files; repository root is never mounted.

Auth is initialized through `/api/auth/me`; protected navigation waits for it. Language/theme preferences PATCH the real account. Project creation awaits actual server provisioning. File/diff/log views request owned backend data. Commit invokes Git. New Session retains files and requests a new installed-runtime session. Provider choices come from runtime discovery. A message is sent only for a connected provider/model; empty states never manufacture replies.

## Components

- `routes/auth.py`, `profile.py`, `dependencies.py`: cookie authentication, profile and RBAC.
- `services/workspaces.py`: templates, derived roots, safe reads, Git status/diff/commit; no shell strings.
- `routes/workspaces.py`: owned API orchestration and explicit unavailable GitHub/push/delete responses.
- `services/opencode.py`: verified version adapter and opt-in local process manager. Shared OPENCODE_URL is health-only.
- `services/providers.py`: actual provider/model/auth discovery only. `services/github.py`: truthful disconnected status only.
- `routes/agent.py`: background message transport, text reads, abort, reviewed approvals and durable Gateway event replay. In-process tasks are not distributed/restart-safe.
- `models/workspace.py`: Project/Workspace/WorkspaceSession/ExecutionEvent. Source content is not copied to these tables.

## Local runtime boundary

Default OPENCODE_RUNTIME_MODE=disabled. Local opt-in requires a loopback APP_HOST and installed OpenCode 1.18.31. The launcher uses separate per-workspace HOME/XDG directories, random Basic credentials, loopback port, --pure, no inherited provider secrets, ask-by-default permissions and deny external_directory. It creates the repo first. Tests prove two real sessions retain existing files.

Separate directories/processes are NOT OS or network sandboxes. All processes run under the local account. Use only trusted local development, single worker. Public use needs independent identities/containers, filesystem/network/resource limits, task leases and recovery. No model credentials were copied from production; no provider-backed model execution was claimed.

## Design

Kimi/ChatGPT-inspired neutral conversation layout, existing product identity, sidebar and responsive review drawers. Inline SVG brand marks and original line icons remain crisp without CDN/font dependencies. Arabic/English, RTL/LTR, dark/light, keyboard focus and Escape drawer handling included. Core buttons use icons with accessible names and tooltips. Full admin translation, rich message rendering and complete accessibility audit remain future work.

## Explicit omissions

GitHub App, cloning/private repository/token/webhook flow, push/PR/conflict/remote SHA verification, provider auth/secret encryption, tool/token event bridge, public sandbox/quotas, uploads/private app previews, retention/recovery and billing are not complete. Deletion is blocked to preserve unpushed work. Legacy localStorage draft keys are left intact but are not treated as server workspaces.

Testing and run commands: README.md. Exact endpoint/schema inventory: API_REFERENCE.md and DATABASE_REFERENCE.md. Public launch gates: SECURITY_MODEL.md.
