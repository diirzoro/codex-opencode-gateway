# Instructions for coding agents — OpenCode Gateway

**MANDATORY FIRST STEP:** Read [docs/PROJECT_HANDOFF_AND_REMAINING_WORK.md](docs/PROJECT_HANDOFF_AND_REMAINING_WORK.md) in full before inspecting/modifying the project. It is the living source of truth for implementation status, unverified code, outstanding work, business rules, security requirements, and handoff.

**MANDATORY LAST STEP:** Update that same document with completed tasks, what was actually tested, remaining issues, exact commit SHA, and the next action. Do not mark code as VERIFIED without reproducible evidence. Keep updates aligned with actual code; do not delete open tasks just because a feature was attempted.

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

### Latest owner-authorized native TEST batch (22 October 2026)

Use the existing native **OpenCode 1.18.32**, not the superseded V2/Docker plan. Read docs/NATIVE_SESSION_BATCH1.md and the current override at the top of the handoff. Gateway authorizes identity/owned mappings only; Nginx carries native JSON/SSE; do not build another engine/queue. Native mode remains explicit single-owner TEST opt-in pending actual Nginx/working-file reconciliation and acceptance. No per-workspace process or old credential copying in native mode. Preserve the old source for rollback until native TEST acceptance; no database/project/history deletion. Temporary task tests must be removed after use, while existing security regressions remain. SSH is authorized if a configured connection is actually available; do not claim server access or print secrets. Do not change master/LIVE/workflows or Preview in this batch.
