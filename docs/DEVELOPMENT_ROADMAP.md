# Verified local phase update — 2026-10-06

See [REAL_AGENT_ACCEPTANCE.md](REAL_AGENT_ACCEPTANCE.md) for real isolated OpenCode/DeepSeek prompt, Stop and secret-boundary evidence, and [PAYMENT_CHECKOUT_REPORT.md](PAYMENT_CHECKOUT_REPORT.md) for admin-owned receiving methods, customer checkout, hosted links, PayPal backend create/capture verification, migration 0008 and remaining merchant-configuration/production gaps. These reports supersede overlapping historical payment/runtime claims below. No push or deployment.

# Internal runtime direction — 2026-10-05

Keep the existing internal reference localhost-only and credential-free; never reopen its public port or restore the shared login. Next runtime work must implement a supervised Workspace Manager with per-workspace sandbox identities/filesystems, HOME/XDG/auth/session/state separation, network/resource restrictions and durable recovery. Verify OpenCode version compatibility and the customer GitHub/provider workflow before release. Do not implement a multi-user fallback to the shared reference process. See [INTERNAL_OPENCODE_INFRASTRUCTURE.md](INTERNAL_OPENCODE_INFRASTRUCTURE.md). No push or deployment authorized.

# Current local update — 2026-10-04

Next: configure and verify real GitHub App OAuth/clone/push, SMTP recovery and local provider execution with user-supplied test credentials; add refresh-token rotation, OAuth credential persistence, public-runtime isolation/quotas, complete billing ledger/checkout, retention/deletion processing and full audited permission management. No server deployment is authorized.

See [PHASE_REPORT.md](PHASE_REPORT.md) and [ACCOUNT_WORKSPACE_REQUIREMENTS.md](ACCOUNT_WORKSPACE_REQUIREMENTS.md).

---

## Earlier audit (historical)

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

Registration update (2026-10-04): username minimum 6, password minimum 8 with number and punctuation symbol; no uppercase requirement, existing logins unchanged. See API_REFERENCE.md. No migration.


## OpenCode synchronization (2026-10-05)

The current Codex workspace now includes the newer OpenCode subscriptions, project archiving, client/admin dashboards, reports, shell and grid UI, together with the merged account-management features. See MERGE_REPORT.md for current verification. The preserved OpenCode document is in reference/opencode/. This workspace uses migration head `0006_subscriptions_archive` after the existing `0005_account_management`. No VPS access or push was performed.


### Current synchronized implementation

Synchronization and role routing precede remaining payment integration, OAuth refresh/backup and production isolation work. No deployment or push is authorized in this task.


## Workspace/payment update — 2026-10-05

Completed: workspace-first navigation/composer, opposite collapsible pane, brand-to-Landing, ten-day entitlement and separate admin/customer manual payment flow. Remaining: real payment processor integration with hosted card checkout and verified webhooks; actual provider-authenticated model verification; live GitHub App acceptance; production PostgreSQL migration execution. No push/deployment authorized in this delivery.

See [WORKSPACE_FIRST_REPORT.md](WORKSPACE_FIRST_REPORT.md) for scope, evidence and limits. This update supersedes conflicting historical statements.
