# Development roadmap

Updated 2026-10-03. Work locally; upload later manually only when explicitly authorized. No SSH or deployment in the current scope.

## Completed local phase

Audited baseline and created permanent references; secured source serving and auth guards; fixed account regressions; added owned Project/Workspace/session/event schema; actual Blank/Template files, Git diff/commit; installed-runtime adapter and real New Session; partial messages/stop/approvals/SSE; responsive conversation UI with official SVG branding; installed Playwright/Chromium; preserved existing real admin overview. See PHASE_REPORT.md for exact proof and limitations.

## Next implementation order

1. Finish auth hardening: verification/reset, rate limits, audited owner setup and subscription gates.
2. GitHub App: installations and selected-repository scope, ephemeral server-side token, repo/branch discovery, private clone, revoke webhook. Keep Blank/Template usable without GitHub.
3. Workspace lifecycle: leases/mutation coordination, state recovery, resource limits, explicit base SHA and source display.
4. OpenCode/provider: encrypted or session-only credentials, supported auth methods, connection test; run an actual prompt that edits a file and executes a harmless test in isolated local test context.
5. Conversation execution: tool events, streaming, pending approvals with reviewed command details, abort E2E, disconnect/reconnect/idempotency/crash recovery. New Session must continue on existing files.
6. Files/diff/logs: remaining status/count UI, binary/large-file handling, file-tree navigation, safe rich messages and sanitization tests.
7. Commit/Push: branch/conflict safeguards, GitHub publish, remote expected-SHA check, clean-tree check, PR where appropriate. No success toast without actual GitHub confirmation.
8. Public sandbox/network/quotas and all security gates, then safe cleanup/grace/export/retention, private previews/uploads. Public deployment is blocked before these gates.
9. Billing/ledger/versioned plans/receipts/webhooks and broader operations only after core flow. Never invent metrics/prices/payment state.

## Decision gates

Production runtime isolation/capacity, retention duration/grace, plan pricing/limits, supported stacks, credential policy and support roles must be chosen before their launch phases. Current local development does not depend on contacting the VPS. Required external credentials should be entered through a secure configuration flow when implemented, never pasted into a chat or committed.

## Phase completion report contract

For each phase report changed files, migrations, APIs, tests (actual engine/version and test-double limits), REAL/PARTIAL/SIMULATED/MISSING/BLOCKED status changes, security implications and exact later deployment commands. Update the six references together. Deployment instructions in deployment/README.md are documentation only and do not claim readiness or authorization.
