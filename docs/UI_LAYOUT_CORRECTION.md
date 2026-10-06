# App Shell and workspace layout correction — 2026-10-05

Local Codex workspace only: `D:\opencodde agent\codex project\project`.
No server access, deployment, commit or push. Existing merged changes were preserved.

## Result

- Administration navigation contains the 13 requested business/operations sections. Projects, workspaces and sessions are no longer administrative destinations. Their metadata API remains unchanged for operational counts/reports.
- Navigation and `openWorkspace` redirect admin/owner to administration before opening a coding workspace. Customer access to administration remains guarded.
- Login, registration, profile reads and `/api/auth/me` restoration preserve browser App Shell language/theme. Deliberate preference changes still save through the existing profile API.
- Normal admin/client pages fill available content width. Titles are 30px, table/body content 15–16px, table headers 14px; rows and search controls have larger padding. Billing plan cards span the body.
- Only an actual client workspace displays additional session/history and integration panels. The center retains chat, actual files, diff, logs and commit/push controls. Review lives inside the center.
- Both panels collapse on desktop to expand the center; RTL mirrors their placement. At widths of 1100px or less they are drawers beneath the global header. Main navigation remains accessible.
- The integration panel reuses the real provider/model controls, reads GitHub/runtime status, and links to existing credential/settings pages. Workflow entries reflect received runtime events; no generated activity is added.
- Security remains isolated from billing, GitHub, OpenCode and general account management.
- Fixed a session-restoration DOM timing error and repeated wrapping of searchable tables when returning to a section.

## Files

`app.js`, `enhancements.js`, `management.js`, `dashboards.js`, `index.html`.
Browser acceptance coverage: `tests/browser/layout-correction.spec.cjs`; updated administration expectations in `tests/browser/merged-routing.spec.cjs`.

Backend/API contracts/database rules: unchanged in this phase. Migrations: none.

## Verification

Headed Chromium covers Arabic dark login for admin/owner/customer, English light login, Arabic dark registration, refresh, correct dashboards, admin workspace rejection, wide readable tables, single normal-page navigation, section separation, real template files/diff/local commit, desktop collapse/expand, RTL panel placement and mobile drawers.

Full validation: **22 passed** in headed Chromium on a fresh isolated local test database (port 8770). JavaScript syntax checks and `git diff --check` passed. No backend changes required a new migration or altered API.

Screenshots are outside the repository at `../.audit/layout-evidence/`:
`admin-overview.png`, `admin-users.png`, `client-dashboard.png`, `client-billing.png`, `security.png`, `client-workspace.png`, `mobile-workspace.png`.
They use isolated loopback test data, not production accounts.

## Availability

Preview execution is not configured and says so. Local test runtime is disabled; chat submission stays disabled without a connected runtime/provider/model. 2FA, device fingerprinting and dedicated login-event collection remain unavailable. Payment processing remains unavailable; methods/subscription configuration is unchanged. No feature is marked live merely because its layout is present.
