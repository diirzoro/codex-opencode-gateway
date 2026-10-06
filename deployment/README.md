# Future manual deployment — NOT executed

This guide prepares a source package only. Packaging is local and never contacts a server. Do not deploy or run the server commands below until the owner explicitly asks. The production example enables the existing per-workspace OpenCode process mode as requested, but that mode is not an OS/network sandbox and is not safe for public customer execution until production isolation is implemented and reviewed.

## Build the manual-upload package

From the project root on Windows, run:

```powershell
python deployment/package_release.py
```

This writes `../project-release.zip` outside the repository and refuses to overwrite an existing archive. The package includes the current tracked and untracked source changes, but excludes `.git`, `.audit`, every real `.env`, keys/certificates, databases, runtime/workspace data, dependencies, and test files. It also includes a manifest for review. Inspect the ZIP contents and compare them with the intended release before manually uploading it. This command does not install dependencies, migrate a database, or contact the VPS.

OpenCode integration details and the exact division between packaged adapter code and separately installed host runtime are documented in [OPENCODE_INTEGRATION.md](OPENCODE_INTEGRATION.md).

GitHub App setup, callback URL, repository permissions, webhook configuration, and backend-only environment values are documented in [GITHUB_INTEGRATION.md](GITHUB_INTEGRATION.md).

## Preconditions

### Internal OpenCode configuration (2026-10-05)

The operator reports that the existing `opencode-web.service` binds only `127.0.0.1:4096`, without the retired shared login. Keep that service and port private. Configure `OPENCODE_BASE_URL=http://127.0.0.1:4096` only in the Gateway backend environment. Replace the obsolete `OPENCODE_URL` name manually in the existing environment when deployment is later authorized; remove retired shared OpenCode credential entries. Do not add OpenCode URLs/credentials to frontend config or reverse-proxy its raw UI/port for customers. The current adapter uses this reference for health only; public customer execution stays disabled pending per-workspace production isolation. See `docs/INTERNAL_OPENCODE_INFRASTRUCTURE.md`. No commands below change the OpenCode service or firewall.

Before deployment, validate the release on the target Python/PostgreSQL versions; configure HTTPS, recovery email, GitHub and payment credentials; and resolve per-customer OpenCode process/filesystem/provider-state isolation, resource limits, supervision, and secret backup/rotation. Existing server state, service file, installed OpenCode version, and DB credentials have not been inspected. Preserve `.env`, runtime/workspaces and backups. Do not replace secrets with example values.

The project contains the Gateway-side OpenCode adapter in `backend/app/services/opencode.py`; it starts one OpenCode process per owned workspace when `OPENCODE_RUNTIME_MODE=local`. The binary itself is not copied into the Gateway source archive: install OpenCode 1.18.31 or 1.18.32 on the host and set `OPENCODE_BINARY` to its executable path. The internal service configured by `OPENCODE_BASE_URL` currently provides health diagnostics only; customer prompts use the Gateway-managed workspace process. The production example enables this mode at the owner's request, but it is not a complete sandbox and must not serve untrusted public customer workloads until filesystem/network/process isolation and quotas are implemented. The source archive includes the existing Gateway systemd unit; it will not replace or install a second OpenCode unit over the service already reported on the VPS.

## Package locally later

Review the source tree and the generated release manifest. Do not create a test environment. The package script includes application source, migrations, deployment configuration, and references; it excludes `.env`, `.git`, `.venv*`, `node_modules`, test files, test reports, `.audit`, workspaces, runtime, logs, databases, receipts, and key files. Manually upload the reviewed ZIP to `/home/tahir/opencode-gateway-release`, then extract it there so the source is at `/home/tahir/opencode-gateway-release/project/`. These instructions do not initiate a network connection.

## Commands on the VPS after approval

Run as tahir in a server terminal only when authorized. Confirm `/home/tahir/opencode-gateway` and the service name match current server state before proceeding. Existing `.env` must use DATABASE_URL compatible with the PostgreSQL service. Database backup uses PostgreSQL administrator locally, avoiding printing credentials.

```bash
cd /home/tahir/opencode-gateway
test -f .env && test -d backend
umask 077
backup_dir="/home/tahir/opencode-backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup_dir"
sudo systemctl stop opencode-gateway
sudo -u postgres pg_dump -Fc opencode_gateway > "$backup_dir/database.dump"
tar --exclude=.git --exclude=.venv --exclude=.venv-local --exclude=node_modules --exclude=workspaces --exclude=runtime -czf "$backup_dir/application.tar.gz" .
# Preserve .env and live workspace/runtime contents. No --delete.
rsync -av --exclude=.env --exclude='.env.*' --exclude=.git --exclude='.venv*' --exclude=node_modules --exclude=workspaces --exclude=runtime --exclude=test-results --exclude=playwright-report /home/tahir/opencode-gateway-release/ /home/tahir/opencode-gateway/
test -x .venv/bin/python || python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
# Review these values in existing .env: COOKIE_SECURE=true, APP_HOST=127.0.0.1,
# OPENCODE_RUNTIME_MODE=disabled and external runtime/workspace roots.
chmod 600 .env
set -a
source .env
set +a
cd backend
../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m alembic current
cd ..
sudo systemctl start opencode-gateway
sudo systemctl status opencode-gateway --no-pager
curl --fail --silent --show-error http://127.0.0.1:8000/api/health
```

Migration failure: keep the service stopped, preserve backup and diagnose; do not rerun destructively or downgrade new workspace tables. Health is process liveness, not proof of account/DB/runtime/GitHub functionality. Run the approved acceptance checks over HTTPS before public release. Rollback requires a reviewed source/database plan; restoring source alone may not match schema.

Existing service template is illustrative and has not been installed or validated against the VPS. Do not run a second public OpenCode UI; internal ports must remain firewalled. Do not use production secrets in local tests.

## Merged account management

Expected migration head: `0008_paypal_checkout`, including `0006_subscriptions_archive` and `0007_payment_orders` after the existing `0005_account_management`. Back up the database before running `python -m alembic upgrade head`. Keep CREDENTIALS_ENCRYPTION_KEY outside Git and preserve it across releases. Configure SMTP and HTTPS PUBLIC_BASE_URL for recovery. Existing GitHub connections must reconnect to grant user authorization; tokens expire within 8 hours. Payment methods support manual receipt review, hosted links and backend PayPal order/capture verification. Actual PayPal acceptance is pending merchant credentials; Google Pay needs a processor-hosted link and Binance transfers remain manual. See `docs/PAYMENT_CHECKOUT_REPORT.md`. Preserve existing live environment values: merge new variable names individually, never replace the live `.env` with an example. Production APP_PORT remains 8000. The local private `backend/.env.paypal.local` is for sandbox testing only and must not be uploaded. No server connection or deployment was performed during this review.
