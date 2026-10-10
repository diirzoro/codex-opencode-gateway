# OpenCode Gateway

OpenCode Gateway is an independent browser workspace that connects customer projects, GitHub, OpenCode runtimes and customer-selected AI providers behind one FastAPI gateway. It is not built by or affiliated with OpenCode or GitHub.

## Current architecture

```text
Browser
  -> Nginx
  -> FastAPI Gateway
     -> PostgreSQL
     -> workspace-specific OpenCode runtime on loopback
     -> GitHub / configured external providers through server-side integrations
```

The browser talks only to the Gateway. OpenCode runtime addresses and provider credentials remain server-side. GitHub-backed projects keep GitHub as the permanent source; the Gateway working copy is temporary.

## Current product state

Implemented in source:
- accounts, roles, session security and password recovery
- Google/GitHub sign-in identities
- projects, workspaces and OpenCode sessions
- provider/model/agent discovery from OpenCode
- encrypted provider credentials and durable disconnect/reconnect
- GitHub App repository/branch selection, shallow working copy, sync, commit and push
- plans, billing, PayPal/manual-payment flows and paid renewal carry-over
- Core trial 30 days and Advanced trial 10 days from first actual advanced use
- customer retention/reactivation and workspace file-retention policies
- Arabic/English responsive UI

Current migration head: `0013_login_identity.py`. Always run Alembic upgrades in order through `head`.

## Retention summary

- expired access freezes coding/execution
- customer account retention: 90 days, then archived rather than immediately erased
- archived customer return: verified email -> renewal-only session -> verified real payment -> fresh password -> normal login
- local project files: cleanup after 7 days of meaningful inactivity, warning around day 5
- GitHub temporary worktree: cleanup after 73 hours of meaningful inactivity
- original GitHub repository is never deleted by Gateway cleanup
- passive polling does not extend file retention

## Local development

Windows local development uses **Python 3.13** and the root **`.venv`**. Install Python 3.13 with the Windows Python launcher, a native Windows **PostgreSQL** service, Git and OpenCode on `PATH`. `.python-version` records the version for tools that support it; the scripts also check the actual interpreter. Python 3.14 is unsupported by the currently pinned Pydantic/PyO3 dependency chain. Do not set `PYO3_USE_ABI3_FORWARD_COMPATIBILITY` or broadly upgrade dependencies to bypass this.

The local database is a shared native PostgreSQL database on the default port, so the DeepSeek and Codex copies can share users, IDs, subscriptions and test data. Docker/Compose files in the repository are optional and are not used for local development.

From the repository root in PowerShell:

```powershell
py -3.13 --version
psql --version
.\setup-local.ps1
.\run-local.ps1
```

`setup-local.ps1` performs these steps in order and stops on failure:
1. Create `.venv` using `py -3.13 -m venv .venv` if absent, and reject an existing environment using another Python version.
2. Install the unchanged pins with `.venv\Scripts\python.exe -m pip install -r backend\requirements.txt`.
3. Copy `.env.example` to the ignored `.env` only if missing, and generate a local `CREDENTIALS_ENCRYPTION_KEY` if missing/empty.
4. Load `.env` and run `.venv\Scripts\python.exe -m alembic upgrade head` from `backend` through `run-local.ps1 -MigrateOnly`.

If a failed setup left a Python 3.14 `.venv`, close processes using it and move it aside first. For example, `Move-Item -LiteralPath .venv -Destination .venv-local` preserves it in an ignored directory; use this only if `.venv-local` does not already exist. Then rerun setup. Do not reuse an activated old environment or bare `python`/`pip` commands.

An existing `.env` is preserved. Check that it uses these **local-only** values (the database credentials match the shared native PostgreSQL instance). This DeepSeek/OpenCode copy uses its own Gateway port and data roots so it can run alongside the Codex copy:

```dotenv
DATABASE_URL=postgresql+psycopg://gateway_local:gateway_local@127.0.0.1:5432/gateway_local
APP_HOST=127.0.0.1
APP_PORT=7001
PUBLIC_BASE_URL=http://127.0.0.1:7001
GITHUB_CALLBACK_URL=http://127.0.0.1:7001/api/github/callback
COOKIE_SECURE=false
OPENCODE_RUNTIME_MODE=local
OPENCODE_BINARY=opencode
OPENCODE_BASE_URL=http://127.0.0.1:4096
WORKSPACE_ROOT=D:/deepseek-gateway-data/workspaces
RUNTIME_ROOT=D:/deepseek-gateway-data/runtime
```

The local runner restricts both startup and migrations to the shared local database identity/port above and a loopback Gateway bind. It loads `.env` explicitly; invoking Alembic directly does not load that file. After pulling new migrations, use `.\run-local.ps1 -MigrateOnly` before starting the app. No virtual-environment activation is needed.

For saved provider connections, setup generates the encryption key with Python's `secrets.token_urlsafe(48)` and writes it directly into `.env` without printing it. Keep that local key across runs; changing it makes existing encrypted local credentials unreadable. Leave GitHub, Google, SMTP and PayPal credentials empty unless intentionally testing those integrations with separate test accounts. Missing external credentials are expected to show an unavailable/not-configured state, not successful integration.

Open [the local Gateway](http://127.0.0.1:7001). The browser must use the Gateway for all OpenCode requests. The Gateway starts an isolated runtime for each workspace on a dynamic loopback port; `4096` is only the optional reference health URL. A missing standalone service on `4096` does not prove workspace runtimes are unavailable. Local mode is trusted development and must not be publicly exposed.

Baseline before Phase 6: verify `/api/health`, register/login, dashboard, workspace creation/open, workspace runtime startup, provider list/models, agent list/default agent, session creation and refresh persistence, Connections, Billing without external credentials, and Arabic/English navigation. Submit a basic prompt only when a local/test provider is available. Record actual failures or unavailable services; catalog discovery alone does not prove provider authentication or inference works.

Never copy production secrets into the repository. Keep `.env`, `runtime/`, `workspaces/`, receipts, private keys and databases outside source control.

## Authoritative project references

- [Project memory and completed phases](PROJECT_MEMORY.md)
- [Known issues and performance improvement plan](PROJECT_ISSUES_AND_IMPROVEMENT_PLAN.md)
- [Deployment reference](deployment/README.md)
- [Network configuration](deployment/NETWORK_CONFIGURATION.md)
- [OpenCode integration](deployment/OPENCODE_INTEGRATION.md)
- [GitHub integration](deployment/GITHUB_INTEGRATION.md)

## Deployment boundaries

Production deployment must preserve the existing live `.env`, PostgreSQL data, `CREDENTIALS_ENCRYPTION_KEY`, PayPal/GitHub credentials, workspace/runtime storage and operator-managed Nginx configuration. Do not overwrite these from example files.

The separately installed reference OpenCode service remains private on loopback. Customer workspaces use Gateway-managed workspace-specific OpenCode processes.

The checked-in source is the deliverable. Temporary tests, test reports, runtime data and generated release artifacts are not part of the repository.
