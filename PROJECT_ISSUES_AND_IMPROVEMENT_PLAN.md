# OpenCode Gateway — Known Issues and Improvement Plan

## Current Native-First TEST issues — 2026-10-29 (updates only)

**Status source, not a second architecture document.** The single architectural policy remains [CANONICAL_NATIVE_FIRST_ARCHITECTURE_AR.md](docs/CANONICAL_NATIVE_FIRST_ARCHITECTURE_AR.md); live VPS evidence belongs only in [CANONICAL_TEST_SERVER_STATUS_AR.md](docs/CANONICAL_TEST_SERVER_STATUS_AR.md). A GitHub commit or passing CI is NOT acceptance on TEST.

### Implemented in source in this repair pass
- **60-second email ownership proof** for registration OTP, legacy verification links, password reset email links, and GitHub email OTP. Enforce on the server, including legacy records whose old expiry was longer. Update signup UI hints, response TTL and resend cooldown to one minute. A successfully verified GitHub proof persists only to finish that same OAuth transaction.
- **Native routes:** `/api/workspaces/{id}/agents` uses Native agent metadata rather than disabled per-workspace runtime; `/api/opencode/status` checks Native health when Native TEST is enabled.
- **Project file safety:** the legacy explicit file upload endpoint no longer overwrites an existing project file; concurrent name collision returns HTTP409.
- **Native session-list visibility:** partial workspace listing now explicitly warns about denied/expired workspaces instead of silently treating 409/410 as empty history.
- **Regression suite:** `.github/workflows/validate-updates.yml` executes email-code/signup/reset, GitHub email-ownership and Native authorization/security tests. GitHub Actions passed at commit `15938b9fb4ca8b5d885489b1ec2855be367435ce`; later changes need their own CI run.

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

**Release gate:** Do not touch LIVE/master, ports/IPs, databases, Native service or Nginx; do not deploy or delete files without explicit approval. Each item requires measured, isolated TEST PASS evidence before closure.

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
