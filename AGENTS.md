# Instructions for coding agents — OpenCode Gateway

**MANDATORY FIRST STEP:** Read [docs/OPENCODE_GATEWAY_MASTER_SINGLE_MEMO_V3_9_2026-10-27_AR.md](docs/OPENCODE_GATEWAY_MASTER_SINGLE_MEMO_V3_9_2026-10-27_AR.md) in full before inspecting/modifying the project. It is the living source of truth for implementation status, unverified code, outstanding work, business rules, security requirements, and handoff.

**MANDATORY LAST STEP:** Update that same unified document with completed tasks, what was actually tested, remaining issues, exact commit SHA, and the next action. Do not mark code as VERIFIED without reproducible evidence. Keep updates aligned with actual code; do not delete open tasks just because a feature was attempted.

### Branch / production restrictions

- Work on `updates` only. **Never merge into `master`** or change rollback branches until the owner explicitly authorizes it, including after online preview/testing.
- Do not edit deployment workflows, production PostgreSQL, production VPS services, payment credentials, or live `.env` without explicit authorization.
- Apply Alembic migrations 0017/0018 only to an isolated test database until approved.
- Keep customer workspaces, OAuth and API keys, identities, authorization and preview runners separated.
- Preserve the single verified-email-triggered 30-day trial; first verified payment supersedes the trial, subsequent early renewals extend remaining paid time.
- Maintain the unified ChatGPT-like Workspace & Agent behavior: correct follow-scroll, true wait-for-approval, clear choices/recommendation/custom answer, resume after response.
- No "HTML only" preview: detect project framework and implement actual executable previews using secured isolated runners, never host execution.
- Run tests and explain blockers; do not claim CI or production success without proof.

For every change: **read → implement → test → document → commit on updates**.

### Current owner order — 25 October 2026 (supersedes older batch restrictions)

Use existing **OpenCode Native 1.19.4** and existing services/transports only. Read docs/NATIVE_DEVELOPMENT_1194.md and the current handoff override. No new AI engine, queue, SSE service, per-workspace process, visual redesign or copied user credentials. All authenticated TEST accounts may enter their owned workspaces; the former owner-ID gate is retired. This is pre-launch development, not public multi-tenant certification. Preserve authentication, ownership, credential confidentiality and file restrictions; complete functionality before the dedicated pre-launch hardening phase. Do not claim isolated global native credentials: the legacy /auth API has one slot per provider, so enforce account ownership and refuse cross-account overwrites. Never treat provider configuration as successful external model authentication.

AI JSON/SSE travels through Nginx after Gateway authorization. Provider/agent/auth metadata may be handled by Gateway to remove native Provider.key/options and enforce account ownership; never process generated AI bodies in Python. Use native tools, questions, approvals, Todo and abort. Keep old independent Gateway/rollback code inactive in Native mode. Preserve historical test/version records.

Use `updates`/TEST only. Never change `master`, LIVE (stopped), workflows, Preview, databases, existing environment keys, projects or conversation data. The three-file TEST workflow is UI-only; reconcile and deploy the complete native bundle through the coordinated procedure first. SSH is authorized only if an actual configured connection exists. No server access or deployment may be claimed from source/fixture tests. Keep permanent regressions; remove disposable local QA environments after use.

Current storage-first follow-up: read docs/NATIVE_CATALOG_MAINTENANCE.md. Reuse native cache/API and the original `models --refresh` CLI through the existing maintenance loop; never build a Python catalog/cache or another daemon. CLI completion is not in-process reload success (verified1.19.4 limitation). Keep7/14-day operational scheduling separate from Native's own internal timer. Do not dispose/restart active conversations to refresh models. Preserve existing pilot credential attribution without reinstating an owner-only product gate. Current coordinated bundle has15 runtime dependencies; actual TEST config/working files must be reconciled before deployment.

Latest v3.3 source follow-up: read docs/NATIVE_CONNECTIONS_SHELL_ACCEPTANCE.md and the top handoff. Gateway's stored role plus specific project ownership is the project-admin decision; no browser role/permission input. Native denies Shell/alternative commands/task-subagents and unknown tools. Admin Shell is blocked until verified project-limited OS enforcement. Native file approvals are worktree-relative (non-Git worktree may be `/`), so use private native `/path` before checking owned paths/symlinks. Never initialize imported `.opencode`/opencode.json/jsonc in the shared process; preserve them for review. The18-file bundle requires backend/frontend/private metadata routing together. The50-item main Connections list has manual full-catalog lookup and separate connected entries; Native global auth conflict protection stays. Actual TEST deployment/registration/OAuth/process acceptance is blocked on configured server access, not another routine permission.

### Current Native UX acceptance follow-up — 25 October 2026 (v3.7 baseline)

Read docs/NATIVE_UX_SECURITY_ACCEPTANCE.md and the latest top handoff before historical notes above. The prior TEST deployment succeeded: owner/direct-update and Actions run40193999369 are recorded in architecture v3.7. Do not repeat first-install infrastructure investigation. The manual deploy-updates-test.yml workflow now supports audit-test/deploy-test and the reviewed18-file manifest; older three-file/15-file and “deployment NONE” statements are historical. This UX follow-up changes five manifest files and needs its own reviewed TEST rollout. Do not edit workflows, restore old release-tool patches, change routes/config/ports/IPs or restart Native. Preserve all native Todo behavior. New permanent tests are explicitly requested by the owner for this task. Public signup requires independently controlled verified identities; do not invent mailboxes or bypass registration/verification. Local HTTP/ORM and DOM fixtures must never be reported as live TEST acceptance.

Latest approval/attachment follow-up: read docs/NATIVE_APPROVALS_AND_ATTACHMENT_UX.md. New owner authorization permits exact-file remembered Native session policy for subsequent prompts, no raw always. Pinned1.19.4 always cache can override deny; session policy is captured at run start. Never claim immediate current-run reload or automatic large-diff classification. Question/Todo capability permission is automatic subject to enabled tools; original Todo engine/UI stays. Synthetic user text is presentation-only attachment scaffolding; do not remove ordinary prompts by string matching.

### Sole executive reference — owner V3.9, 27 October 2026

The unified V3.9 memo linked above is the only executive reference. Other handoffs, acceptance records and deployment guides are dated technical/historical evidence, not competing instructions. Preserve old Work history in docs/archive/WORK_HANDOFF_THROUGH_20261027.md. Current owner decisions override historical approvals (including old master promotions). No workflows, LIVE, master, shared OpenCode, ports, configuration or database changes. Smart Preview TEST review is permitted by section14; do not alter production Preview or provision/restart workers. Future Silver800MB/Gold2GB per project and capacity review at50actual customers are planning only.

GitHub disconnect is not a ban on the same GitHub account. Explicit New connection must open a separate window and mint fresh ownership-bound OAuth state; never restore revoked local tokens or bypass another Gateway account’s installation ownership. Browser GitHub cookies cannot be cleared by Gateway; a normal new window does not guarantee a clean login profile. Do not claim otherwise or force logout of a different site.
