# OpenCode Gateway

Independent browser workspace; not built by or affiliated with OpenCode or GitHub. Arabic/English, light/dark, conversation-focused responsive UI. Local development only; no deployment performed.

Real locally: accounts, profiles, owner/admin listing and user counts, Blank/HTML/Python/Node project files, owned file previews, Git diffs/commits and opt-in OpenCode 1.18.31 sessions that retain project files. Partial: provider discovery, messages/stop/approvals/Gateway event replay. Missing: provider authentication, GitHub clone/push/PR, strong sandbox/quotas, previews/uploads/retention and billing. No simulated operational success is shown.

## Local browser preview and tests (Windows)

Use Python 3.13 (tested) or validate the deployment target Python 3.12 separately. Commands below create a new `.venv-local`; do not overwrite an existing environment. The preview uses its own SQLite test data and loopback port 8765; it never reads production credentials. Accounts are test accounts, and model execution is disabled.

```powershell
Set-Location 'D:\opencodde agent\opencode project'
py -3.13 -m venv .venv-local
.\.venv-local\Scripts\python.exe -m pip install -r backend/requirements.txt
npm ci
npx playwright install chromium
.\.venv-local\Scripts\python.exe backend/tests/browser_server.py
# Open http://127.0.0.1:8765
```

For a new independent E2E server (close the preview above first):

```powershell
$env:E2E_SERVER_COMMAND = '.\.venv-local\Scripts\python.exe backend/tests/browser_server.py'
npm run test:e2e
# Backend and optional installed-runtime integration:
$env:RUN_OPENCODE_TESTS = '1'
Set-Location backend
..\.venv-local\Scripts\python.exe -m pytest -q
```

OpenCode smoke test requires installed version 1.18.31. Without RUN_OPENCODE_TESTS=1, it is skipped. No provider credentials are needed for the session-preservation test. On managed Windows, browser/runtime subprocesses may require approval outside the tool sandbox.

## Local PostgreSQL application

Prepare a separate local PostgreSQL database. Copy `.env.example` and supply local-only values. Export those explicit variables to the shell; this application does not automatically load `.env`. Activate your Python environment, then:

```powershell
Set-Location backend
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Default runtime is disabled. Setting OPENCODE_RUNTIME_MODE=local starts per-workspace OpenCode processes with separate runtime data, but **does not sandbox the host OS/network**. Use trusted local projects and one Gateway worker. Never make local mode publicly reachable. The shared OPENCODE_URL is used only for health diagnostics.

## References

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

At the owner's request, automated test files/configuration and results remain local and are excluded from this repository. The test commands above apply to the complete local development copy, not a fresh source-only clone. Validation results and limitations are recorded in docs/PHASE_REPORT.md. Production secrets, runtime data and dependencies are never included.
