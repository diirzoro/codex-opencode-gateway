# GitHub App setup for Gateway customers

The project already includes the Gateway GitHub service and routes in `backend/app/services/github.py` and `backend/app/routes/github.py`. Customer-facing buttons use Gateway APIs; customers authorize their own GitHub account and choose repositories they are allowed to use. The app uses a server-side GitHub App and user authorization flow, not a shared customer PAT. Tokens are kept server-side and encrypted with `CREDENTIALS_ENCRYPTION_KEY`.

## Configure the GitHub App

Create or update a GitHub App in GitHub Developer settings:

1. Set the app homepage to the Gateway's public HTTPS origin.
2. Enable **Request user authorization (OAuth) during installation**.
3. Set the exact callback URL to `https://YOUR_DOMAIN/api/github/callback`. Do not use a wildcard callback.
4. Grant repository permissions needed by the current workflow: **Metadata: read-only** and **Contents: read and write** (private repository discovery, clone, commit and push).
5. Subscribe to the `installation` and `installation_repositories` webhook events if revocation/suspension updates should arrive immediately. Set the webhook URL to `https://YOUR_DOMAIN/api/github/webhook` and generate a webhook secret.
6. Install the app only on accounts/repositories the customer wants to authorize.

GitHub distinguishes the user authorization callback from the post-installation setup URL. This integration expects the user authorization callback and checks that the authenticated user belongs to the selected installation before linking it. The code validates the one-time Gateway `state`; it does not trust `installation_id` by itself.

## Configure the Gateway backend

Set these values in the protected server environment, never in frontend files or the uploaded source archive:

```text
PUBLIC_BASE_URL=https://YOUR_DOMAIN
GITHUB_APP_ID=YOUR_APP_ID
GITHUB_APP_SLUG=YOUR_APP_SLUG
GITHUB_CLIENT_ID=YOUR_CLIENT_ID
GITHUB_CLIENT_SECRET=YOUR_CLIENT_SECRET
GITHUB_APP_PRIVATE_KEY_PATH=/secure/path/github-app.private-key.pem
GITHUB_CALLBACK_URL=https://YOUR_DOMAIN/api/github/callback
GITHUB_WEBHOOK_SECRET=YOUR_WEBHOOK_SECRET
CREDENTIALS_ENCRYPTION_KEY=YOUR_PERSISTENT_ENCRYPTION_KEY
```

Keep the private key outside the project directory; restrict it to the Gateway service account. Back up the encryption key separately and preserve it across releases. If it is lost, encrypted GitHub/provider credentials cannot be recovered. Do not paste secrets in chat or commit them.

After deployment and migration, sign into a Gateway customer account, choose **Connect GitHub**, authorize the app, select a repository, and choose a branch. The browser should receive repository metadata only; Git credentials remain server-side. The app's GitHub API implementation is included in the release bundle, but a live OAuth/clone/push flow cannot work until a real GitHub App and HTTPS callback are configured.

## Current integration limits

This document does not configure GitHub on the VPS or certify the current server deployment. The present source contains connection, repository, branch, clone, commit and push paths, but user tokens expire and require reconnection. The Gateway's OpenCode workspace execution still requires the separate isolation gates in [OPENCODE_INTEGRATION.md](OPENCODE_INTEGRATION.md).

Official GitHub guidance: [user authorization callback URL](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/about-the-user-authorization-callback-url), [OAuth during installation](https://docs.github.com/en/apps/maintaining-github-apps/modifying-a-github-app-registration), and [GitHub App best practices](https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/best-practices-for-creating-a-github-app).
