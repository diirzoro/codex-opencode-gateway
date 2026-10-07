# GitHub App setup for Gateway customers

The project already includes the Gateway GitHub service and routes in `backend/app/services/github.py` and `backend/app/routes/github.py`. Customer-facing buttons use Gateway APIs; customers authorize their own GitHub account and choose repositories they are allowed to use. The app uses a server-side GitHub App and user authorization flow, not a shared customer PAT. Tokens are kept server-side and encrypted with `CREDENTIALS_ENCRYPTION_KEY`.

The current preparation uses the known VPS IP `162.35.127.135`, Gateway `127.0.0.1:8000`, reference OpenCode `127.0.0.1:4096`, and dynamic per-workspace loopback runtimes. The public HTTPS application URL is **PENDING_PUBLIC_HTTPS_URL**; it has not been invented or configured. See [NETWORK_CONFIGURATION.md](NETWORK_CONFIGURATION.md) and [github-vps.env.fragment.example](github-vps.env.fragment.example). Reuse the existing repository and a suitable existing GitHub App; App registration/setup and live checks remain operator actions.

## Configure the GitHub App

Create or update a GitHub App in GitHub Developer settings:

1. Set the app homepage to the Gateway's public HTTPS origin.
2. Enable **Request user authorization (OAuth) during installation**.
3. After the public HTTPS URL is known, set the callback to that exact origin plus `/api/github/callback`. Until then it is **PENDING_PUBLIC_HTTPS_URL**. Do not use a wildcard callback.
4. Grant repository permissions needed by the current workflow: **Metadata: read-only** and **Contents: read and write** (private repository discovery, clone, commit and push).
5. If webhooks are enabled, use the final HTTPS origin plus `/api/github/webhook` and a protected webhook secret. GitHub App installation lifecycle events `installation` and `installation_repositories` are delivered automatically; no push/PR subscriptions are needed. The URL remains **PENDING_PUBLIC_HTTPS_URL** until supplied.
6. Install the app only on accounts/repositories the customer wants to authorize.

GitHub distinguishes the user authorization callback from the post-installation setup URL. This integration expects the user authorization callback and checks that the authenticated user belongs to the selected installation before linking it. The code validates the one-time Gateway `state`; it does not trust `installation_id` by itself.

## Configure the Gateway backend

Set these values in the protected server environment, never in frontend files or the uploaded source archive:

```text
# PENDING_PUBLIC_HTTPS_URL
PUBLIC_BASE_URL=
GITHUB_APP_ID=
GITHUB_APP_SLUG=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GITHUB_APP_PRIVATE_KEY_PATH=/home/tahir/secrets/github-app.private-key.pem
# PENDING_PUBLIC_HTTPS_URL: final origin + /api/github/callback
GITHUB_CALLBACK_URL=
GITHUB_WEBHOOK_SECRET=
# Preserve the existing value on the live server.
CREDENTIALS_ENCRYPTION_KEY=
```

Keep the private key outside the project directory; restrict it to the Gateway service account. Back up the encryption key separately and preserve it across releases. If it is lost, encrypted GitHub/provider credentials cannot be recovered. Do not paste secrets in chat or commit them.

After deployment and migration, sign into a Gateway customer account, choose **Connect GitHub**, authorize the app, select a repository, and choose a branch. The browser should receive repository metadata only; Git credentials remain server-side. The app's GitHub API implementation is included in the release bundle, but a live OAuth/clone/push flow cannot work until a real GitHub App and HTTPS callback are configured.

## Current integration limits

This document does not configure GitHub on the VPS or certify the current server deployment. The present source contains connection, repository, branch, clone, commit and push paths, but user tokens expire and require reconnection. The Gateway's OpenCode workspace execution still requires the separate isolation gates in [OPENCODE_INTEGRATION.md](OPENCODE_INTEGRATION.md).

Official GitHub guidance: [user authorization callback URL](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/about-the-user-authorization-callback-url), [OAuth during installation](https://docs.github.com/en/apps/maintaining-github-apps/modifying-a-github-app-registration), and [GitHub App best practices](https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/best-practices-for-creating-a-github-app).
