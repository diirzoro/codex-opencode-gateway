# Historical Codex reference — imported 2026-10-05

This describes the source before merging. Current destination status is in MERGE_REPORT.md; source migration 0005_account_management is now 0006_account_management. Upload claims refer only to the previous Codex release.

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
