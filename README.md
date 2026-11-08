# OpenCode Gateway

Independent browser workspace; not built by or affiliated with OpenCode or GitHub. Arabic/English, light/dark, conversation-focused responsive UI. Local development only; no deployment performed.

Implemented in source: Gateway accounts/roles, admin and client pages, plan and billing management, project/workspace APIs, local Git operations, and an OpenCode adapter. External PayPal/GitHub functions need real server-side configuration. The adapter accepts OpenCode 1.18.31 and 1.18.32, but public isolation and live Gateway-to-OpenCode execution remain unverified; production prompt execution is disabled by default. See [deployment/OPENCODE_INTEGRATION.md](deployment/OPENCODE_INTEGRATION.md) and [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md) before upload. The project does not present simulated provider or payment success as real.

## Run the local application (Windows)

The local runner uses the actual Gateway backend and the configured local PostgreSQL database. It binds to loopback only; it does not start a separate demo server or test database.

```powershell
Set-Location 'D:\opencodde agent\codex project\project'
# Create the ignored .env from .env.example and configure local-only values once.
Set-Location backend
..\.venv\Scripts\alembic.exe upgrade head
Set-Location ..
.\run-local.ps1
# Open http://127.0.0.1:8766
```

Keep `.env`, `runtime/`, and `workspaces/` local. Do not copy production credentials into the project. The app and database currently run locally; no deployment is performed.

## Local PostgreSQL application

Prepare a separate local PostgreSQL database. Copy `.env.example` and supply local-only values. Export those explicit variables to the shell; this application does not automatically load `.env`. Activate your Python environment, then:

```powershell
Set-Location backend
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The production example enables `OPENCODE_RUNTIME_MODE=local`, which starts per-workspace OpenCode processes with separate runtime data but **does not sandbox the host OS/network**; do not expose this mode to untrusted public customer workloads before adding production isolation. Backend-only `OPENCODE_BASE_URL=http://127.0.0.1:4096` refers to the separately running internal reference service and is used only for health diagnostics, without shared login credentials. Client prompts use Gateway-managed workspace processes, not the shared reference process. Frontend requests use `/api/...`; customers never access OpenCode directly. Existing environments must replace the old `OPENCODE_URL` variable with `OPENCODE_BASE_URL` (the old name is no longer read).

## References

- [Product boundaries and development rules](docs/PRODUCT_BOUNDARIES.md) — branded Gateway client UI, OpenCode-owned coding capabilities, SaaS control plane, and no test environments.
- [OpenCode deployment integration](deployment/OPENCODE_INTEGRATION.md) — packaged adapter versus separately installed runtime, and production execution gates.
- [GitHub App deployment integration](deployment/GITHUB_INTEGRATION.md) — client-owned authorization and the server-side GitHub App setup.
- [Implementation status and all 224 source requirements](docs/IMPLEMENTATION_STATUS.md)
- [API reference](docs/API_REFERENCE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Database and migrations](docs/DATABASE_REFERENCE.md)
- [Security model and launch blockers](docs/SECURITY_MODEL.md)
- [Roadmap](docs/DEVELOPMENT_ROADMAP.md)
- [Phase report](docs/PHASE_REPORT.md)
- [SVG asset credits](docs/ASSET_CREDITS.md)
- [Later manual deployment commands](deployment/README.md) — documentation only.

## GitHub source publication

The checked-in application source is the deliverable. Local environment settings, runtime data, workspaces, and dependencies are excluded. No automated test harness or test fixtures are part of this project copy.

## Latest local acceptance

Payment checkout supports admin-owned transfer methods, plan-bound hosted links and server-only PayPal Orders/capture verification. Configure merchant credentials locally before payment processing; see docs/PAYMENT_CHECKOUT_REPORT.md. No successful PayPal transaction is claimed without merchant acceptance. Backend migration head: 0008_paypal_checkout. OpenCode/provider integration and GitHub publishing still have documented configuration and production-isolation limits in the implementation status and phase report.
