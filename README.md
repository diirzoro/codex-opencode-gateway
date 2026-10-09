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

Create an ignored `.env` from `.env.example`, configure a local PostgreSQL database, then:

```powershell
Set-Location backend
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8180
```

Or use `run-local.ps1` after the local environment is configured.

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
