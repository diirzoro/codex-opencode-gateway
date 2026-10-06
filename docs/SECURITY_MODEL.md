# Verified local phase update — 2026-10-06

See [REAL_AGENT_ACCEPTANCE.md](REAL_AGENT_ACCEPTANCE.md) for real isolated OpenCode/DeepSeek prompt, Stop and secret-boundary evidence, and [PAYMENT_CHECKOUT_REPORT.md](PAYMENT_CHECKOUT_REPORT.md) for admin-owned receiving methods, customer checkout, hosted links, PayPal backend create/capture verification, migration 0008 and remaining merchant-configuration/production gaps. These reports supersede overlapping historical payment/runtime claims below. No push or deployment.

# Internal runtime boundary — 2026-10-05

The reference OpenCode service is now user-reported localhost-only without the previous shared login. Gateway never returns its URL or credentials to the customer. `OPENCODE_BASE_URL` is backend-only, restricted to a loopback HTTP origin without credentials; shared health ignores obsolete passwords. Generated credentials for separate local workspace processes remain private. No shared process is used as a multi-user execution fallback. OS/network sandboxing, quotas and supervised recovery are still required for public production. See [INTERNAL_OPENCODE_INFRASTRUCTURE.md](INTERNAL_OPENCODE_INFRASTRUCTURE.md).

# Current local update — 2026-10-04

Change/reset revokes all account sessions and reset tokens. Suspension stops owned local runtimes before revoking access. Payment records are owner-scoped; platform method mutation requires owner/admin/finance. Role mutation requires owner and cannot demote the existing owner. GitHub callback requires a user authorization code and membership proof, not installation_id alone. User tokens expire and reconnect is required. SMTP delivery uses STARTTLS and HTTPS reset URLs; tokens occur in fragments and are removed immediately. Public runtime sandboxing, global recovery throttling, full retention/purge, OAuth token DB backup and production acceptance remain launch gaps.

See [PHASE_REPORT.md](PHASE_REPORT.md) and [ACCOUNT_WORKSPACE_REQUIREMENTS.md](ACCOUNT_WORKSPACE_REQUIREMENTS.md).

---

## Earlier audit (historical)

# Security model

Updated 2026-10-03. Local testing only. **Not approved for public multi-tenant agent execution.** No VPS access or secrets were used.

## Implemented controls

Scrypt passwords; random cookie tokens stored as SHA-256 hashes; HttpOnly/SameSite=Strict; configurable Secure default true; expiry/revocation and active-user checks. Username normalization and case-insensitive lookup prevent case mismatch. Explicit-null required profile fields return 422. Admin and owner are checked server-side; frontend guard alone is never authorization.

Every workspace/session/file/Git operation resolves ownership before filesystem/runtime access. Server-generated UUID paths are derived under one configured root. File API rejects absolute/drive/backslash/NUL/traversal, protected metadata paths, symbolic links and Windows junctions; content limits 1 MB and UTF-8 only. Static serving uses a short allowlist; backend source, .env files, docs, database and runtime folders return 404.

Cross-site mutations are blocked using Origin and Fetch Metadata. API responses are no-store, nosniff and frame-denied. These controls do not replace production host/proxy/TLS configuration or login rate limits.

Git commands use argument arrays, owned cwd, disabled hooks/fsmonitor/credential helpers/system-global Git configuration and file protocol, no interactive prompts, timeout and sanitized error text. Commit is real; push unavailable. Deletion returns 409 until verified remote backup/retention exists.

OpenCode opt-in local contexts get separate HOME/XDG, random in-memory Basic password, loopback bind, --pure and ask/deny permissions. Approvals filter by owned runtime session and include full bounded patterns. Missing/overlong details cannot be approved; only once/reject allowed. Stop requires runtime acknowledgement. Test doubles validate permission/ownership boundaries, not real model execution.

## Remaining launch blockers

No OS/network sandbox: runtime can execute with host-user privileges. Directory isolation and OpenCode permissions are defense-in-depth only. Add isolated identities/containers, no sensitive mounts/Docker socket, non-root execution, network denial to platform DB/metadata/admin, CPU/RAM/disk/process/time limits and workspace count limits. Validate repository-controlled config/MCP/dependencies and all Git configuration/filter behavior under untrusted-code tests.

Provider auth, encrypted credential storage/key rotation, token scope/revocation and complete redaction are missing. Current regex redaction is limited and is not proof all secrets are protected. Runtime log access is not exposed through Gateway, but files need appropriate OS permissions and retention. No production provider credential was copied or used.

Single-worker tasks do not have cross-worker locks/leases, idempotency or robust restart recovery. Git mutations must be coordinated with agent edits before concurrent public use. SSE stores lifecycle metadata; rich tool events and reconnect-after-crash E2E remain unverified. Deletion/cleanup is deliberately unavailable.

HTTPS/reverse proxy/Host validation/rate limits, password reset/verification, subscription limits, production PostgreSQL and target Python validation, dependency security review and full browser accessibility/security review remain launch work. Origin comparison must be tested behind the selected trusted proxy configuration.

## Evidence

Backend tests cover auth expiry/revocation, admin/owner/other-user access, static-source denial, traversal/symlinks, real filesystem/Git and unconfigured-provider rejection. Actual OpenCode two-session test covers file preservation. Playwright covers registration/project/files/diff/commit, truthful disabled runtime/push, responsive drawers, language/theme and no JavaScript errors. See PHASE_REPORT.md for exact results.

Registration update (2026-10-04): username minimum 6, password minimum 8 with number and punctuation symbol; no uppercase requirement, existing logins unchanged. See API_REFERENCE.md. No migration.


## OpenCode synchronization (2026-10-05)

The current Codex workspace now includes the newer OpenCode subscriptions, project archiving, client/admin dashboards, reports, shell and grid UI, together with the merged account-management features. See MERGE_REPORT.md for current verification. The preserved OpenCode document is in reference/opencode/. This workspace uses migration head `0006_subscriptions_archive` after the existing `0005_account_management`. No VPS access or push was performed.


### Current synchronized implementation

Source and destination secrets/runtime data were excluded. User GitHub tokens remain encrypted and membership-checked; roles may only be granted by owners. All billing queries are per authenticated user; platform aggregates require admin/owner. External credentials were not used for synchronization.


## Workspace/payment update — 2026-10-05

Expired trials/subscriptions are rejected server-side on work APIs before runtime access. Checkout rejects private, disabled or currency-incompatible receiving methods. Customer cannot administer platform methods or confirm receipts; other-customer payment references are inaccessible. Admin review is idempotent and transactional. Card collection is not implemented; processor-hosted secure fields and verified webhooks are required before enabling automated checkout.

See [WORKSPACE_FIRST_REPORT.md](WORKSPACE_FIRST_REPORT.md) for scope, evidence and limits. This update supersedes conflicting historical statements.
