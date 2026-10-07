# Prepared VPS network configuration

Prepared on `updates`, 2026-10-07 (Asia/Aden), using values supplied by the owner. These are configuration inputs, not a live-server verification. No VPS connection, external connectivity checks, service changes or tests were performed for this configuration task.

| Component | Prepared value |
|---|---|
| Public server IP | `162.35.127.135` |
| Public application URL | **PENDING_PUBLIC_HTTPS_URL**; `PUBLIC_BASE_URL=` remains blank |
| Nginx public listener | Preserve existing HTTP/HTTPS server blocks; actual public hostname/TLS settings remain operator-supplied |
| Nginx → Gateway | `http://127.0.0.1:8000` |
| Gateway internal bind | `APP_HOST=127.0.0.1`, `APP_PORT=8000` |
| Shared/reference OpenCode | `OPENCODE_BASE_URL=http://127.0.0.1:4096` — reference/health only |
| Per-workspace OpenCode | `127.0.0.1:<dynamic runtime port>` — allocated by Gateway at runtime |
| Frontend/API | Same-origin `/api/...`; no public OpenCode URL |
| GitHub App PEM location | `/home/tahir/secrets/github-app.private-key.pem`, outside the repository |

```text
Internet / Browser
       ↓
Existing Nginx public server
       ↓  http://127.0.0.1:8000
Gateway
       ↓  127.0.0.1:<dynamic runtime port>
Selected workspace's OpenCode runtime
```

The existing adapter launches workspace OpenCode with `--hostname 127.0.0.1` and a dynamically allocated port. Do not configure a fixed workspace port or change the bind to `0.0.0.0`. The shared 4096 service remains separate from actual workspace sessions/prompts/auth/discovery. The browser reaches Gateway only; the runtime password and addresses remain server-side.

## Files for later manual deployment

- `.env.production.example`: full template. Known internal values populated; real App identity/secrets and public HTTPS values blank. Unrelated existing settings are retained.
- `github-vps.env.fragment.example`: small fragment for merging the known network/GitHub settings into the server's existing `.env`.
- `nginx-gateway-location.conf.example`: merge/include its `location /` inside the existing public Nginx server block. Do not add a second conflicting `location /`; preserve actual listeners, hostname, certificate and any existing security/access settings. It proxies only Gateway and supports its SSE event stream.
- `GITHUB_INTEGRATION.md`: exact variable names and GitHub App callback/permission setup.

These are ready-to-fill/copy templates, **not ready-to-start completed credentials**. A blank `GITHUB_CALLBACK_URL` is intentionally pending and fails current backend validation until filled. Merge values individually rather than replacing the live `.env`; preserve the current database and encryption credentials. Keep `COOKIE_SECURE=true` for the final HTTPS application.

## Pending values

1. **PENDING_PUBLIC_HTTPS_URL**: final real public application origin for `PUBLIC_BASE_URL`; final origin plus `/api/github/callback` for `GITHUB_CALLBACK_URL`, and plus `/api/github/webhook` in GitHub settings if webhooks are enabled. Do not assume that the public IP already has usable HTTPS or invent a domain.
2. Real `GITHUB_APP_ID`, `GITHUB_APP_SLUG`, `GITHUB_CLIENT_ID` from the existing/reused GitHub App. No verified identity was supplied.
3. `GITHUB_CLIENT_SECRET`, the actual PEM file at the configured path, and `GITHUB_WEBHOOK_SECRET` if enabled. Supply on the VPS only; no secret values are committed.
4. Existing persistent `CREDENTIALS_ENCRYPTION_KEY`: retain on the VPS. The blank template is not an instruction to erase or rotate it.
5. Actual Nginx HTTPS listener/hostname/certificate settings, which the operator will preserve or supply later.

The owner will copy/merge configuration, supply real values, restart services and run live checks. No OpenCode proxy rule, public runtime listener, firewall opening, deployment workflow change or application networking change is included here. `.github/workflows/` and `master` are unchanged.
