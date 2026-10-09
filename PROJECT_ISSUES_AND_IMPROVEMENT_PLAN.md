# OpenCode Gateway — Known Issues and Improvement Plan

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
- Confirmed/open: 1-10, 14-20 from current repository inspection.
- Resolved in cleanup: 11 (stray auth form-closing tag removed), 12 (dead legacy asset/config routes removed), 13 (obsolete prototype directory removed).
- Any further CSS/function removal still requires targeted validation before change.

## Improvement plan

### Performance 1 — Audit and safe cleanup
- establish before/after measurements
- verified dead reference/prototype files removed
- initial malformed auth markup corrected
- dead config/asset routes removed
- continue removing only proven-dead styles/comments after validation
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