# TEST Preview browser origin — approval and validation gate

Status: owner approved TEST-only infrastructure/configuration on 2026-10-18. Code prepared; NOT configured/deployed/accepted. Do not run this document as a shell script.

## Confirmed cause (2026-10-18)

Owner's existing QA container returned HTTP200 for /, /style.css, /app.js and /nested/page, with correct HTML/CSS/JavaScript types. TEST Gateway then logged401 for cross-site script, style and iframe requests. The current opaque sandbox cannot rely on the normal SameSite=Strict login cookie for these requests. Test workflow39112535467 successfully deployed48f9b41; the cause is no longer an undeployed-logging assumption.

## Prepared application change

Keep the normal host-only HttpOnly/SameSite=Strict account cookie and iframe sandbox allow-scripts (no allow-same-origin). A separately configured HTTPS Preview hostname serves only GET/HEAD /preview/<grant>/<path>. No login, account API, static Gateway shell, docs or writes are served on it. Grants are opaque, encrypted with a domain-separated key derived from the existing credential-encryption master; no new key or production secret is installed. They expire in at most300seconds AND at the original login idle/absolute deadline. Refresh explicitly obtains another grant without starting the container. Viewing assets does not extend the login idle clock.

Grant minting is a normal authenticated/entitled owned-workspace POST. Every public read rechecks the original DB login session (including logout/revocation), user state, project/workspace owner and lifecycle, and the exact running container lease. Worker rechecks lease under its existing lock at fetch time to close a stop/restart race. A stopped/restarted Worker/container invalidates old grants. No migration. An old Worker without browser_lease fails closed until updated.

A grant URL is a PRIVATE short-lived bearer credential: anyone to whom it is copied can read only that authorized Preview until expiry/revocation. It cannot authenticate to Gateway, change files, run commands or select another workspace. Never paste it into logs, support messages or third-party pages. no-referrer/no-store and opaque sandbox retained; app access logging redacts grant paths. The dedicated reverse proxy must not log request URIs (including error logs) or cache responses. Do not enable access until that condition is verified. Do not enable generic credentialed CORS: wildcard CORS exists only on successful bearer-authorized Preview GET results, allowing modules/fetch from the opaque sandbox.

The new transport is opt-in: without PREVIEW_PUBLIC_ORIGIN, existing static/legacy Preview behavior is unchanged (including its known cross-site401 limitation). This allows code-only TEST publication without silently enabling or requiring unconfigured infrastructure. A configured origin activates grant minting; missing key/old Worker then fails closed.

## Owner approval recorded; actual TEST values still required

No .env, DNS, certificates, Nginx, service settings, workflows, Docker daemon or Live changes have been made. Proposed TEST-only hostname: preview-test.opencode-gateway.codes. Owner explicitly approved its use, TEST-only DNS/TLS/new Nginx virtual host, TEST Gateway Environment entry PREVIEW_PUBLIC_ORIGIN=https://preview-test.opencode-gateway.codes and dedicated TEST Worker update/restart. Do not ask for the same approval again. No .env edit is required. This preserves the previously approved separate-origin architecture.

After approval, verify actual TEST upstream host/port/configuration and available TLS certificate locations before producing/installing final Nginx configuration; do not reuse production ports or guess addresses. DNS must resolve to the verified TEST ingress. TLS must cover the new hostname. Do not modify an existing Live server block/certificate. The example below is a review template with unresolved upstream/certificate placeholders, NOT an install-ready file.

```nginx
server {
    listen 443 ssl;
    server_name preview-test.opencode-gateway.codes;
    ssl_certificate     <VERIFIED_TEST_PREVIEW_FULLCHAIN_PATH>;
    ssl_certificate_key <VERIFIED_TEST_PREVIEW_PRIVATE_KEY_PATH>;

    # Grants are bearer URLs. Disable request URI logging/caching only here.
    access_log off;
    error_log /dev/null;
    location /preview/ {
        limit_except GET HEAD { deny all; }
        proxy_pass http://<VERIFIED_TEST_GATEWAY_LOOPBACK_HOST_AND_PORT>;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Cookie "";
        proxy_set_header Authorization "";
        proxy_cache off;
        proxy_no_cache 1;
        proxy_hide_header Set-Cookie;
        # Do not add X-Frame-Options DENY to successful Preview responses.
        # Keep the application's CSP sandbox/frame-ancestors policy intact.
    }
    location / { return 404; }
}
```

Do not add an anonymous proxy route to the old /api/.../preview/live path or expose the private Worker8791/Docker socket. All application auth/ownership/grant checks must run. Do not add allow-same-origin or relax the normal login cookie.

## TEST activation order, after approval and verified backup

1. Verify TEST-only code/DB backups and rollback reference; preserve all projects/history. Do not dump credentials to output.
2. Review final DNS/TLS/new virtual-host configuration against the actual TEST upstream and log/cache requirements. Record exact changes before applying.
3. Publish application code to TEST through the existing workflow (no workflow edits); add only the approved non-secret PREVIEW_PUBLIC_ORIGIN to the TEST service environment. The existing credential-encryption key must already be configured (presence check only; never print it).
4. Back up /opt/opencode-preview-test/app/services/preview_worker_server.py and update it from the exact reviewed updates commit. It alone adds the hashed container lease and under-lock fetch check; existing rootless Docker settings/images/resources are unchanged. Restart ONLY the dedicated TEST Worker after the owner has stopped the disposable QA preview. Worker jobs are memory state: do not assume they survive this restart. Preserve snapshots/customer files.
5. Test Nginx syntax before a reviewed reload; never restart/modify Live services. Old Worker, wrong host, missing TLS/key/origin must fail closed, not downgrade cookie or sandbox protections.
6. Start only the authorized QA Preview through its UI. Inspect /, CSS, JS, counter, /nested/page and return; test Refresh (new read URL, no new container), New Tab and Stop. Verify cookies are absent on Preview host; account APIs there404; forged/expired/wrong-owner/grant-after-logout or stop/restart requests denied. Do not send a real grant URL back in reports.
7. Verify original login, Workspace, Agent, static HTML preview and Live health unchanged. Record actual results; source tests/green workflow are not acceptance.

## Still outside this fix

React/Vite/Next dependency installation/build, Python dependencies, persistent engine setup, admission/concurrency, reaper/storage cleanup and account-wide quota remain separate open work. The existing relay supports bounded GET resources only, not POST/WebSocket/HMR; unknown frameworks/startup commands are not invented. Module/root-path/application-specific routing needs real framework acceptance before claiming support. No customer app runs on Gateway host.


## Read-only preflight after approval

Run backend/scripts/preflight_preview_origin_test.py as root on the VPS before filling the upstream/TLS placeholders. It reads ONLY the TEST Gateway PID/environment metadata and selected TEST/new-host Nginx directives; captures nginx -T in memory without printing its full configuration. It reports the existing TEST loopback proxy origin, database host/port/name without user/password/query, encryption-key presence only, certificate/key paths (private key CONTENTS never read), valid SAN coverage, DNS addresses and pg_dump/certbot availability. It makes no database calls, downloads or service/config/DNS/file changes. No secrets or full command/environment/production server blocks are printed. Results are required to produce the final Test configuration and choose the minimal TLS step; do not guess ports, reuse production settings or repeat the successful Preview asset probe.


## Actual owner VPS inventory — 2026-10-18

The checksum-verified read-only preflight returned:
- TEST Gateway PID327035; cwd /home/tahir/opencode-gateway-test/backend.
- TEST proxy upstream **http://127.0.0.1:8001**; nginx configuration validates.
- TEST DB **opencode_gateway_test**,127.0.0.1:5432. pg_dump and certbot already installed; no installation needed.
- Credential encryption key present (value never printed); PREVIEW_PUBLIC_ORIGIN not set.
- Existing TEST certificate /etc/letsencrypt/live/test.opencode-gateway.codes/fullchain.pem does **not** cover the proposed Preview hostname; do not reuse it or expand/replace Live certificates.
- test.opencode-gateway.codes resolves to **162.35.127.135**; preview-test.opencode-gateway.codes has **no DNS record** at this observation.

Immediate external prerequisite: owner creates only A record preview-test ->162.35.127.135 (TTL300/Auto, DNS-only during issuance). No DNS connector is available; it has NOT been created by the assistant. No further runtime/container test is needed to establish this prerequisite. After record creation, verify actual resolution once, including absence of an unverified AAAA/proxy target, before issuing the new certificate.

Concrete staged configuration files (not installed):
- docs/examples/preview-test-http.conf: new hostname HTTP80 serves ONLY the isolated ACME webroot /var/lib/opencode-preview-acme-test; other URLs404.
- docs/examples/preview-test-https.conf: dedicated certificate under its own exact cert-name preview-test.opencode-gateway.codes; only GET/HEAD Preview routes proxy to the observed TEST upstream127.0.0.1:8001; cookies/Authorization stripped, access/error URI logs off, no cache. Other routes404. Neither configuration edits any existing Test/Live server block or opens Worker/Docker ports.

Use a dedicated late-sorting site filename such as zz-opencode-preview-test and verify that nginx -T actually includes it before any reload. Do not overwrite an unknown existing file/symlink, assume an include directory is active, or mark syntax valid without running the VPS nginx -t. Back up any earlier assistant-managed version privately before replacing it. Rollback removes/restores ONLY that dedicated managed site and approved TEST-only Environment drop-in/Worker file, tests Nginx configuration, then reloads; never restores a production config or database.

Certificate issuance uses **certonly --webroot**, not the Nginx installer or standalone server. It writes only the new challenge/certificate, keeping existing server blocks running. After HTTP-only site inclusion and challenge routing are verified, intended command is:

    sudo certbot certonly --webroot -w /var/lib/opencode-preview-acme-test --cert-name preview-test.opencode-gateway.codes -d preview-test.opencode-gateway.codes

Do not run it before DNS/challenge readiness, repeatedly retry a failed ACME validation, select a different/Live cert-name, or accept certificate expansion. Verify the exact resulting new certificate paths/SAN/expiry before the HTTPS configuration is installed. Plan renewal deploy reload only for this new domain; do not edit existing Live renewal configuration. Official reference: https://eff-certbot.readthedocs.io/en/stable/using.html#webroot.

Reuse the EXISTING Promote updates to test workflow's mandatory backup rather than inventing another DB mechanism: inspected workflow creates a private TEST code archive, asserts database name opencode_gateway_test, pg_dumps it, validates pg_restore -l and emits STAGING_BACKUP_OK before deploying/migrating/restarting TEST. Verify the actual new workflow run reports that backup; source inspection is not proof the next backup already exists. Do not edit the workflow or run a second manual database migration. The future release also needs the section53 dedicated Worker file update/lease contract and the approved non-secret Environment setting; code-only publication with the setting absent retains legacy behavior and cannot by itself fix401.

Owner DNS action and actual VPS nginx/TLS/worker/environment operations are still pending. No certificate was issued, no Nginx file installed/reloaded, no environment set, no service restarted or new TEST deployment initiated by this documentation/config preparation. Prior101 application and9 preflight tests reused; these templates still require actual VPS nginx validation.
