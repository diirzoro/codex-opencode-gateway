# OpenCode Gateway — Known Issues and Improvement Plan

## Current Native-First TEST issues — 2026-10-29 (updates only)

**Status source, not a second architecture document.** The single architectural policy remains [CANONICAL_NATIVE_FIRST_ARCHITECTURE_AR.md](docs/CANONICAL_NATIVE_FIRST_ARCHITECTURE_AR.md); live VPS evidence belongs only in [CANONICAL_TEST_SERVER_STATUS_AR.md](docs/CANONICAL_TEST_SERVER_STATUS_AR.md). A GitHub commit or passing CI is NOT acceptance on TEST.

### Implemented in source in this repair pass
- **60-second email ownership proof** for registration OTP, legacy verification links, password reset email links, and GitHub email OTP. Enforce on the server, including legacy records whose old expiry was longer. Update signup UI hints, response TTL and resend cooldown to one minute. A successfully verified GitHub proof persists only to finish that same OAuth transaction.
- **Native routes:** `/api/workspaces/{id}/agents` uses Native agent metadata rather than disabled per-workspace runtime; `/api/opencode/status` checks Native health when Native TEST is enabled.
- **Project file safety:** the legacy explicit file upload endpoint no longer overwrites an existing project file; concurrent name collision returns HTTP409.
- **Native session-list visibility:** partial workspace listing now explicitly warns about denied/expired workspaces instead of silently treating 409/410 as empty history.
- **Regression suite:** `.github/workflows/validate-updates.yml` executes email-code/signup/reset, GitHub email-ownership and Native authorization/security tests. GitHub Actions passed at commit `15938b9fb4ca8b5d885489b1ec2855be367435ce`; later changes need their own CI run.

### Owner clarification and attachment/retention fixes — later 29 October 2026
- **Architecture is unchanged:** Python Gateway authorizes/isolates upload ownership and storage transport but does not extract file text, implement a second model reader, accept/deny file extensions, or decide model/provider attachment capabilities. OpenCode Native alone interprets the original FilePart, including unsupported-file errors.
- **Reverted custom upload policy:** removed our 20 MiB-per-file limit and manually maintained MIME/extension allowlist from `chat_attachments.py`, `workspaces.py` and `dashboards.js`. The existing workspace storage quota remains the resource-safety ceiling; the model/Native may have their own real provider limits. Upload processing timeout remains a transport deadline, not a model capability policy.
- **Owner cleanup:** `GET /attachments/pending` and confirmed `POST /attachments/clear-pending` act only on temporary uploads owned by that Workspace, preserve Native-processing bytes, and do not erase project files/Native session history. In-flight cancellation now yields an explicit error rather than dereferencing a removed manifest. No new daemon/service introduced.
- **After Native execution:** the existing maintenance loop removes only temporary bytes after Native confirms idle and successful delivery; unreadable/unsupported format is not a reason to keep temporary bytes after an acknowledged finished run. Ambiguous receipts or unavailable Native status preserve files, not delete them prematurely. Processing cleanup is conservative rather than instantaneous.
- **24h chat retention (new owner authorization):** `native_sessions.sweep_expired_native_history` runs in the existing maintenance loop, requires 24h of inactivity in Native's own time plus Gateway event/creation checks, and calls the **native** `DELETE /session/{id}` endpoint. It refuses active, foreign, unknown, mismapped and non-confirmed deletions. Only after Native returns success do Gateway mapping/event records and exact session-owned temporary attachments get removed. Original project files and GitHub copies remain intact. No Python AI/message-delete engine, no Native fork.
- **Security scanner limitation:** avoiding execution and validating ownership/path are important but do NOT establish that an attachment is virus-free. The presence of an actual trusted malware scanner and TEST deployment enforcement is unverified; do not advertise antivirus scanning as implemented.
- **>5 MiB still blocked on deployed TEST?** The current GitHub source had a 20 MiB Gateway cap before the removal. A live 5 MiB refusal may be from `client_max_body_size` in Nginx or another external request limit. This MUST be checked on the current TEST configuration/413 response; no Nginx setting was changed through GitHub and no live upload succeeded in this review.
- **Acceptance:** CI includes `test_chat_attachments.py` and `test_native_24h_retention.py` with a synthetic 6 MiB transfer, cancel races, ownership isolation, no Python text extraction, and Native 24h/idle guard cases. CI success is source-only and cannot prove actual file/model reading, virus scanning, Nginx upload size, or true session deletion on the TEST VPS.
- **Login/account testing remains separate:** the 60-second registration, password-reset link and GitHub email proof regressions passed in earlier CI. Real SMTP, new-user signup, password reset and GitHub OAuth on TEST remain unverified.

### New-user registration sequencing and verification UI — 29 October 2026 (source only)
- **Critical defect confirmed:** the prior `POST /api/auth/register` inserted a `User(status=pending_email)` and started trial dates before OTP confirmation. The login page rejected the customer later but could not correct the email without an existing account workflow.
- **Corrected password registration:** new email signups persist only a `PendingRegistration` draft in encrypted, separate `pending_registrations` storage. This is NOT a customer account. It contains a password hash, hashed random HttpOnly SameSite registration ticket, HMAC OTP and email fingerprint; no plaintext password/code in database or registration response. Added additive migration `0030_staged_registration`, with no destructive changes to existing users. Existing verified Google signup stays separate.
- **User created only on successful 60-second code:** `POST /api/auth/registration/confirm` validates draft ownership and expiry, limits failed attempts to five, enforces current DB identity uniqueness, atomically creates an active `User` and starts the trial, deletes the draft, then creates the login session. Wrong/expired OTP or login before proof never registers the client.
- **Customer recovery before account creation:** `/api/auth/registration/update`, `/resend` and `/cancel` let customers correct their email/username/phone/password, receive a new OTP upon email change, request another code after the 60-second cooldown, or discard the pending draft. Form values remain editable within the current browser. Browser includes a visible inline incorrect/expired code alert and countdown. Previous `pending_email` legacy accounts and historical email proof endpoints are preserved for migration review, not deleted.
- **Temporary drafts:** drafts expire after one hour and are cleaned using the existing five-minute maintenance loop; they never reserve a User identity or start an account trial. Existing real email/user/phone unique indexes still enforce final ownership and prevent racing draft collisions. The historical verification-required-off switch cannot bypass proof for new password signups.
- **Quality gate:** GitHub Actions tests use isolated in-memory DB/mail fixtures and prove no User before code, wrong-code denial, retry limits, one-minute expiry, correction to new email, no extra message on same-email edit, cancel, cookie ownership, reset-link expiry, normalized identity uniqueness and one-hour draft cleanup. Source CI green is NOT real SMTP/browser/TEST VPS acceptance.
- **Deployment gate:** TEST requires non-destructive Alembic migration `0030` and matching frontend/backend commit with encrypted-credentials configuration, secure HTTPS cookies and email delivery. Do not attempt real registration on a TEST backend without the new migration; it fails closed rather than creating an unverified User. No LIVE/master changes and no automatic deployment.

### Previously implemented source fixes, not yet accepted on TEST
- GitHub legacy identity recovery: `b02a2d8d6517`, verified tests `732d286653dc`.
- Attachment creation duplicate quota scan elimination: `5304d79aa737`, `4922b092aae3`, `a183083ddc97`.
- Native prompt receipt uncertainty/recover: `e1fa147bfe77`.
- Native X-Accel transport and legacy Python engine guard are implemented in source, but require live Nginx+gateway verification.

### Open P0 / P1 blockers (do not mark PASS)
1. **P0 GitHub callback `github=configuration`:** get exact sanitized server-side error category, deployed SHA, migrations `0028/0029` and verified email OTP acceptance with two users.
2. **P0 Native attachments:** confirm upload/cancel/cleanup, native FilePart reading, complete output and SSE without deleting project files.
3. **P0 native session HTTP409:** identify per-workspace `response.detail` (archived project, missing root, executable Native config review); preserve all sessions and files.
4. **P0 shared Native provider credentials:** `native_provider_accounts.py` claims ownership per provider ID in a shared engine; two customers with the same provider ID and separate keys still have an unresolved isolation limitation.
5. **P0 shell/task/file isolation:** `policy.native_session_permissions` intentionally denies Shell/task/execute until tenant OS/filesystem boundaries are demonstrably safe. Never lift this guard merely for usability.
6. **P1 prompt authorization latency:** measure quota filesystem traversal, session metadata, provider metadata and tools metadata per request before optimizing. Preserve checks for ownership, quota, and tools.
7. **P1 Python workspace-file preview:** `workspaces.content` still uses Python `read_text` for UI preview (not AI execution). Migrate if required to authorized Native file-read transport without returning file bodies through Python.
8. **P1 legacy endpoints/fallback:** old routes are guarded in Native TEST; verify frontend/endpoint coverage before deleting old code or allowing fallback.
9. **P0 TEST deployment evidence:** match source SHA, backend asset hashes and live Nginx config. HTTP200 prompt acceptance does not prove generated reply or SSE.
10. **Identity caution:** expiring a code after one minute does NOT release a pending account's email/phone or guarantee uniqueness; existing DB unique constraints, identity checks, resend proof and anti-abuse limits remain required. Password reset currently uses a secure emailed link, not a 6-digit OTP. Confirm the TEST registration-verification configuration before asserting all signups require a code.

**Release gate:** Do not touch LIVE/master or ports/IPs, Native service or Nginx. The owner has explicitly approved 24-hour Native history expiration in TEST source; deployment and first actual deletion still require controlled TEST acceptance and proof of service SHA, status/ownership/idle, and rollback. Never delete project files or customer Git repositories. Each item requires measured, isolated TEST PASS evidence before closure.

---


Updated: 2026-10-09
Purpose: record confirmed technical debt and performance risks without changing product behavior. This file is a planning reference, not permission to refactor automatically.

## Guardrails
Performance/refactor work must not change production ports, internal IP routing, database behavior, provider authentication, GitHub authorization, billing semantics, session security, OpenCode runtime ownership or deployment configuration unless that specific change is separately reviewed and approved.

Keep the current stack unless evidence justifies a change. FastAPI/PostgreSQL/OpenCode/Nginx are not being replaced as part of the performance plan.

## 20 tracked issues

1. **Large first-load frontend payload.** Landing/login currently load major application JavaScript and CSS that are not needed for the first view.
2. **Oversized `index.html`.** Landing, auth, workspace, client, billing and admin markup live in one document, increasing parse/DOM cost.
3. **CSS duplication/layering.** Large external CSS plus multiple inline style blocks and historical override layers increase style parsing/recalculation complexity.
4. **Patch-style frontend layering.** `app.js`, `enhancements.js` and `dashboards.js` wrap/replace shared functions instead of exposing clean module boundaries.
5. **Heavy global state.** Important state/functions are shared through globals/`window`, making dependency order and future refactoring fragile.
6. **Workspace-open request burst.** Opening a workspace can trigger sessions, git, entitlement, runtime, provider/agent, details and storage requests close together.
7. **Polling alongside SSE.** Event streaming exists, but permissions/storage/entitlement checks still create periodic network traffic.
8. **Runtime/provider readiness latency.** Workspace-specific OpenCode startup/discovery can delay usable Provider/Agent/Model controls even after shell render.
9. **Limited code splitting.** Management is lazy-loaded, but large dashboard/workspace code still loads when not immediately required.
10. **No production frontend build optimization.** No real bundling/tree-shaking/minification pipeline currently removes unreachable/unused client code.
11. **Malformed/legacy HTML risk.** Historical markup contains at least one stray form-closing tag and should be validated before further UI expansion.
12. **Dead legacy asset route.** Backend still references the intentionally removed `assets/yemen-hero.svg` path; confirm and remove in a dedicated cleanup change.
13. **Old prototype copy in repository.** `reference/original-prototype/` duplicated obsolete frontend files and should not remain as live project baggage.
14. **Outdated UI copy.** Some preview/later-phase text no longer matches implemented GitHub/provider behavior.
15. **Historical UI layers remain inline.** Theme/control-panel changes were appended over time rather than consolidated.
16. **Static frontend served through FastAPI.** Application Python remains in the static-file request path instead of Nginx serving immutable assets directly.
17. **HTML processing on each main-page request.** The server reads/rewrites/version-hashes the HTML shell per request rather than serving a prebuilt manifest/shell.
18. **Navigation is show/hide DOM rather than routed views.** This makes later navigation fast but increases the initial DOM and first-load work.
19. **Multiple client state stores.** localStorage, sessionStorage, globals, DOM state, entitlement state and runtime cache can create stale/restoration complexity.
20. **The frontend has outgrown a small vanilla-SPA organization.** The issue is maintainability/loading architecture, not the chosen backend language.

## Status classification
- Confirmed: 1-10, 12-20 from current repository inspection.
- Needs targeted validation before change: 11 (HTML validator/browser DOM check) and any individual CSS/function override chosen for removal.
- Issue 13 cleanup may be performed independently because the prototype is not runtime-loaded.

## Improvement plan

### Performance 1 — Audit and safe cleanup
- establish before/after measurements
- remove verified dead reference files and stale copy
- validate HTML
- remove only proven-dead routes/styles/comments
- no API/connection/runtime behavior changes

### Performance 2 — Lazy loading / frontend splitting
- load landing/auth essentials first
- defer dashboard/admin/workspace modules until their view is entered
- keep current APIs and server truth
- avoid a full framework rewrite

### Performance 3 — Request optimization
- measure request waterfall for landing/login/workspace
- deduplicate workspace-open calls
- reduce polling where event-driven or cached state already exists
- preserve explicit meaningful-activity semantics

### Performance 4 — Frontend structure
- replace function wrapping/overrides with explicit module interfaces
- narrow global state
- consolidate CSS layers
- separate auth/workspace/dashboard/billing/admin concerns

### Performance 5 — Static delivery
- evaluate Nginx serving versioned immutable assets directly
- avoid per-request HTML hashing/regex work where practical
- keep FastAPI focused on API/application behavior

### Performance 6 — Measure before considering a framework migration
Compare:
- first content/shell render
- DOMContentLoaded
- transferred JS/CSS
- number of initial API requests
- workspace-open time
- provider/agent/model ready time
- mobile responsiveness

Only if the cleaned/modular vanilla frontend remains difficult to maintain should a React/Vite migration be evaluated. Such a migration would be frontend-only and must preserve existing backend/API/runtime/security contracts.

## Non-goals
- no rewrite of FastAPI/PostgreSQL/OpenCode
- no change to internal IPs/ports
- no replacement of GitHub App integration
- no replacement of provider credential architecture
- no billing/PayPal redesign
- no weakening of session or retention controls
