# GitHub App setup — existing updates branch

The existing repository is sufficient. Reuse a suitable existing GitHub App before registering another. Known network values are already populated in the deployment templates; the public HTTPS application URL remains **PENDING_PUBLIC_HTTPS_URL**. See [the committed network configuration](../deployment/NETWORK_CONFIGURATION.md).

Updated 2026-10-07 (Asia/Aden), aligned with deployment configuration commit `037723f410992f21ddc82f48c41c94404fc1fe96` on `updates`. This is setup preparation, not a deployed or accepted live connection. No App, secret or key was created here. Commands below are instructions for later operator execution; this documentation update does not connect to the VPS, restart services or run live GitHub tests.

## Repository decision

Use **diirzoro/codex-opencode-gateway**. A GitHub App is an account-level registration, not a separate repository. Its installation can select the existing repository. No separate test repository is necessary. Read-only repository discovery/branch checks can use the existing repo; a later write acceptance must use an explicitly chosen non-master branch, exclude `.github/workflows/`, and require separately authorized repository changes. No write test is included here.

## Access and remaining manual step

Repository push access does not establish GitHub App-management access. Earlier API diagnostics could not establish access to App registrations; no new live GitHub tests are part of this preparation.

GitHub registration, client-secret creation and PEM generation/download must therefore happen in your GitHub UI. Do not paste any secret into chat. The supplied VPS IP is 162.35.127.135; its actual public HTTPS origin/domain is still unverified. No domain has been guessed.

## Exact GitHub fields and buttons

Use `<PUBLIC_ORIGIN>` to mean your real public Gateway HTTPS origin, without a trailing slash. Replace this marker before saving; it is not an actual URL.

1. Sign into the intended GitHub account. Open **profile picture → Settings → Developer settings → GitHub Apps** (`https://github.com/settings/apps`). If an appropriate App already exists, open it instead of creating a duplicate. For an organization-owned App, use that organization's **Settings → Developer settings → GitHub Apps** with an authorized owner/admin account.
2. If no suitable App exists, click **New GitHub App** (`https://github.com/settings/apps/new` for a personal account).
3. Fill the following fields:

| Field | Required setting |
|---|---|
| GitHub App name | Suggested **Codex OpenCode Gateway diirzoro**. Availability is not verified. Choose another unique name only if GitHub rejects it. |
| Homepage URL | `<PUBLIC_ORIGIN>` |
| Callback URL under user authorization | `<PUBLIC_ORIGIN>/api/github/callback` |
| Expire user authorization tokens | Keep expiration enabled. Current code requires reconnecting after at most eight hours; refresh is not implemented. Disabling expiration does not remove that Gateway limit. |
| Request user authorization (OAuth) during installation | **Check / enable.** |
| Enable Device Flow | Not used; leave disabled. |
| Setup URL (optional) | Leave blank for this OAuth-during-installation flow. Do not substitute it for the user authorization callback. |
| Webhook → Active | **Enable** for the recommended lifecycle-aware setup. |
| Webhook URL | `<PUBLIC_ORIGIN>/api/github/webhook` |
| Webhook secret | Create/store a unique secret in your password manager; enter the same value in GitHub and VPS `GITHUB_WEBHOOK_SECRET`, never chat. |
| SSL verification | Keep enabled. |
| Where can this GitHub App be installed? | **Only on this account** is sufficient for the existing personal repository setup. Choose **Any account** only if real customers must install on other accounts/organizations. |

4. Under **Permissions → Repository permissions**, set **Contents: Read and write**. **Metadata: Read-only** is GitHub's baseline/automatic permission. Leave unrelated repository permissions at No access. No Workflows permission is needed for this setup; workflow changes are excluded.
5. Under **Account permissions**, leave all at **No access**; no Email addresses permission is required. No organization Members permission is required by this code.
6. No additional push, pull-request, Issues, Actions or Checks event subscriptions are needed. With App webhooks active, **installation** and **installation_repositories** lifecycle events are delivered automatically. Those are the only events this backend handles; if not offered as checkboxes, do not look for invented subscriptions.
7. Click **Create GitHub App** (or **Save changes** for an existing App).
8. On the App's settings page, copy **App ID** and **Client ID** into the VPS environment. Use the same App's values; no separate OAuth App is required. Copy its actual URL slug into `GITHUB_APP_SLUG` from the App's public `/apps/<slug>` URL. Do not assume the name suggestion's derived slug is the actual slug.
9. In **Client secrets**, click **Generate a new client secret**. Store it securely in a password manager and VPS `GITHUB_CLIENT_SECRET`. Do not put it in frontend files or this repository.
10. Scroll to **Private keys → Generate a private key**. GitHub downloads a `.pem` file. Keep it outside any Git repository, and transfer it using the commands below. If a working protected key already exists for this App, reuse it rather than rotating unnecessarily.
11. Open **Install App**, select **diirzoro**, then **Only select repositories → codex-opencode-gateway**. To actually link the installation to a Gateway customer, start from the signed-in Gateway **Settings / Connections → Authorize GitHub** after configuring the VPS. A dashboard-only installation has no Gateway-generated state and cannot by itself link a customer.

Current backend callback requires `state`, `installation_id`, OAuth `code`, active Gateway user and successful installation-membership/App-identity checks. `setup_action` alone is not authorization. A setup-only redirect cannot satisfy this callback.

## Ready-to-fill environment

Use [github-vps.env.fragment.example](../deployment/github-vps.env.fragment.example). It already contains these known values:

```ini
APP_HOST=127.0.0.1
APP_PORT=8000
OPENCODE_BASE_URL=http://127.0.0.1:4096
GITHUB_APP_PRIVATE_KEY_PATH=/home/tahir/secrets/github-app.private-key.pem
```

The public VPS IP is `162.35.127.135`. Nginx proxies Gateway at `http://127.0.0.1:8000`; workspace OpenCode runtimes remain private at `127.0.0.1:<dynamic runtime port>`. The shared 4096 service is reference/health only. Frontend requests use same-origin `/api/...`; neither project nor OpenCode ports should be exposed directly to the browser.

Only unknown App identity/secrets and public HTTPS settings remain blank: `PUBLIC_BASE_URL`, `GITHUB_APP_ID`, `GITHUB_APP_SLUG`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_CALLBACK_URL`, `CREDENTIALS_ENCRYPTION_KEY`, and the conditional `GITHUB_WEBHOOK_SECRET`. Public origin/callback are **PENDING_PUBLIC_HTTPS_URL**. Fill these before restarting; a blank callback fails backend startup validation. Keep the actual existing database/provider settings and persistent encryption key. The key path is **GITHUB_APP_PRIVATE_KEY_PATH**, not `GITHUB_PRIVATE_KEY_PATH`.

Preferred private-key location: `/home/tahir/secrets/github-app.private-key.pem`. No inline PEM environment value is needed. `GITHUB_API_BASE` and `GITHUB_WEB_BASE` must be omitted for the real GitHub.com defaults, rather than set to blanks. Homepage/callback/webhook must all use the actual public HTTPS origin; the backend listener on localhost is not the public origin.

## Exact VPS and transfer commands

These are prepared operator commands, **not commands executed on your VPS**. They assume the existing deployment unit shown in this repository: user/group `tahir`, checkout `/home/tahir/opencode-gateway`, `.env` at that root, Python in its `.venv`, and service `opencode-gateway`. Confirm the deployed unit first; if its paths differ, use those actual paths.

### On the VPS, create the protected directory

```bash
sudo systemctl show opencode-gateway \
  --property=User --property=Group --property=WorkingDirectory --property=EnvironmentFiles
sudo install -d -o tahir -g tahir -m 700 /home/tahir/secrets
```

Do not request or display `systemctl show --property=Environment`; it can expose secrets.

### On your workstation, transfer the downloaded PEM without displaying it

Run from outside any repository containing the private key. The first two prompts request only a host and local file path, not a secret value:

```bash
read -r -p 'VPS hostname or IP: ' GATEWAY_VPS_HOST
read -r -p 'Downloaded PEM file path (outside Git): ' GATEWAY_PEM_FILE
test -f "$GATEWAY_PEM_FILE" && test -r "$GATEWAY_PEM_FILE"
ssh "tahir@${GATEWAY_VPS_HOST}" \
  'set -eu; umask 077; set -C; cat > /home/tahir/secrets/github-app.private-key.pem; chmod 600 /home/tahir/secrets/github-app.private-key.pem' \
  < "$GATEWAY_PEM_FILE"
```

`set -C` refuses to overwrite an existing PEM; reuse/verify the existing matching key, or plan a separately reviewed rotation. Keep SSH host-key verification enabled. If the transfer fails, stop and resolve it before continuing. No PEM is echoed into terminal output, shell history or Git.

Transfer the non-secret verifier from the existing checkout on this cloud machine/workstation to the VPS (use your normal secure transfer if that machine lacks SSH access):

```bash
scp deployment/verify_github_configuration.py \
  "tahir@${GATEWAY_VPS_HOST}:/home/tahir/secrets/verify_github_configuration.py"
```

### On the VPS, set ownership/mode and edit existing environment

```bash
sudo chown tahir:tahir /home/tahir/secrets/github-app.private-key.pem
sudo chmod 600 /home/tahir/secrets/github-app.private-key.pem
sudo chown tahir:tahir /home/tahir/secrets/verify_github_configuration.py
sudo chmod 600 /home/tahir/secrets/verify_github_configuration.py
sudo stat --format='PEM owner=%U group=%G mode=%a' /home/tahir/secrets/github-app.private-key.pem
sudoedit /home/tahir/opencode-gateway/.env
sudo chmod 600 /home/tahir/opencode-gateway/.env
```

Merge the fragment manually with real values from the same App; preserve all existing values outside this integration, especially `CREDENTIALS_ENCRYPTION_KEY`. If no encryption key exists and no existing encrypted credentials rely on another key, create a persistent random secret in your password manager and enter it through the protected editor. No command here prints or replaces an existing key. Store Client secret and webhook secret through that editor/password manager, not chat or command-line arguments.

### Verify required names without printing values

Use systemd's EnvironmentFile loading (the same parser as the actual service), not a shell `source` of a potentially different `.env` format:

```bash
sudo systemd-run --quiet --wait --pipe --collect \
  --unit=opencode-github-config-check \
  --property=User=tahir --property=Group=tahir \
  --property=WorkingDirectory=/home/tahir/opencode-gateway/backend \
  --property=EnvironmentFile=/home/tahir/opencode-gateway/.env \
  /home/tahir/opencode-gateway/.venv/bin/python \
  /home/tahir/secrets/verify_github_configuration.py --require-webhook
```

For a deliberately webhook-disabled App, omit `--require-webhook`. The verifier prints **names and OK/MISSING/INVALID only**, never values or exception details. It checks required presence, numeric App ID, HTTPS public origin, callback consistency, readable RSA PEM outside the repo and its owner/600 mode. It is read-only and does not contact GitHub. A PASS establishes local configuration consistency, not successful OAuth/installation. On FAIL, correct the indicated configuration before restarting. The prepared helper was reviewed here but not executed against your VPS.

### Restart and view local logs after the verifier passes

```bash
sudo systemctl restart opencode-gateway
sudo systemctl is-active opencode-gateway
sudo journalctl -u opencode-gateway --since '5 minutes ago' --no-pager -n 100
```

Changing only `.env` does not require `daemon-reload`; that is needed only if the unit changes. Inspect logs locally. Do not paste unreviewed logs into chat; avoid requesting raw environment/config dumps. These commands restart only Gateway, not the reference OpenCode service.

## Final authorization and what completion means

After configuration/restart, sign into an **existing real Gateway customer account**, open **Settings / Connections → Authorize GitHub**, authorize the App and select the existing installation/repository. Verify repository and branch selection through the actual UI. No account seeding, extra repository, write test, master merge or workflow update is necessary.

The button is enabled only when App ID, slug, loaded private key, Client ID, Client secret and encryption key are present. Webhook secret does not control that button but is required for this runbook's enabled webhooks. Customer repository access requires both App installation and a valid user OAuth token. Current tokens are not refreshed automatically; users reconnect after expiration. Repository and branch lists currently fetch only the first 100 entries.

## Compact status report

| Item | Current result |
|---|---|
| Repository | Existing `diirzoro/codex-opencode-gateway`; no new repository needed/created |
| GitHub App name | Suggested `Codex OpenCode Gateway diirzoro`; no registered name verified |
| App ID | NOT ASSIGNED / NOT VERIFIED |
| App slug | NOT ASSIGNED / NOT VERIFIED; copy actual GitHub-generated slug |
| Client ID | NOT CREATED / NOT VERIFIED |
| Client Secret | NOT CREATED |
| Private Key | NOT CREATED |
| Homepage URL | `<PUBLIC_ORIGIN>` — actual public HTTPS origin not yet supplied |
| Callback URL | `<PUBLIC_ORIGIN>/api/github/callback` |
| Webhook URL | `<PUBLIC_ORIGIN>/api/github/webhook` (recommended active) |
| Repository permissions | Metadata read-only; Contents read/write |
| Account/organization permissions | No additional permissions required |
| Events | Automatic installation and installation_repositories; no additional subscriptions |
| Installation/user authorization | Required; App not configured/installation not verified here |
| VPS environment | Not inspected. All eight required names must be confirmed there; webhook secret additionally required when active |

The cloud development environment lacks the GitHub App credentials; its encryption key exists. This does not establish which values are present/missing on the VPS. Do not describe the App as created, installed or fully connected until the manual steps and real authorization are complete.
