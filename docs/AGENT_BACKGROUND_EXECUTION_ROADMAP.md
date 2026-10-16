# Agent Background Execution / Smart Pause & Resume — Pending Roadmap
Status: AGREED FOR FUTURE WORK; NOT IMPLEMENTED. Priority: AFTER Smart Preview.
Date: 2026-10-16

## Separate lifecycle from Preview
Agent tasks and OpenCode runtime sessions MUST NOT be stopped by Preview's five-minute idle timer, preview workers, or browser panel closure. Account authentication expiry (currently 15 minutes idle) is distinct from server-side agent execution.

## Agreed user experience (proposed defaults; confirm exact behavior before enabling)
- User may select **Smart Pause & Resume** (resource-saving default) or **Continue in Background** (opt-in).
- If the user loses connectivity, closes the tab or logs out, allow a short reconnection grace period (proposed: 2 minutes, subject to validation) before attempting a *safe* pause. Never kill a tool halfway through modifying files, and never assume raw process suspension/resumption works.
- On return, surface task progress plus **Resume Agent**. Resume requires user action when paused; reconnect alone must not duplicate prompts, tool calls or payments.
- For background mode, allow independent execution only up to per-plan CPU, memory, wall-time and concurrency limits. No unbounded work.
- Pending approvals/questions remain blocked and persisted, never auto-approved. Persist messages, task transitions, dispatch receipts and tool outcomes.
- Never conflate client disconnect with cancellation; explicit Stop/Cancel must be authenticated, audited, and idempotent.
- When a backend or OpenCode process restarts, reconcile persisted state first; only safely checkpointed operations can resume. Never blindly replay side-effecting commands.
- Send a clear UI indicator of Running, Waiting for Approval, Pausing, Paused, Resuming, Completed, Failed, Interrupted, Cancelled, and reconnect state. Notify users about completion/failures when their chosen mechanism is configured.

## Implementation agenda (updates only; NOT started)
- [ ] A0: audit `backend/app/routes/agent.py`, `session_recovery.py`, `session_lifecycle.py`, runtime transport and frontend disconnect/Stop behavior; identify boundaries.
- [ ] A1: store per-user/per-task execution preference and durable independent job/lease lifecycle in PostgreSQL, without coupling to authentication session. Add strict tenant permissions.
- [ ] A2: implement reconnect grace and safe checkpoint/pausing protocol **only if** OpenCode capabilities support it; do not fake pausing or SIGSTOP arbitrary tool processes.
- [ ] A3: explicit Resume UI/API with idempotency, durable submission receipts, approval persistence, and no duplicate side effects; fallback to interrupted state where safe resume is impossible.
- [ ] A4: implement opt-in background continuation, per-plan limits, worker concurrency and fair queues. Avoid lingering idle runtime resources.
- [ ] A5: reconnect status, event replay, activity log and notification hooks.
- [ ] A6: run disconnection, browser close, logout, network loss, approval waiting, concurrent Stop/Resume, reboot, multiple users, and side-effect replay security tests on Test.
- [ ] A7: require explicit authorization and review before promoting any changes to master/Live.

## Existing-code observation (not a claim of robust background operation)
`agent.py` currently launches `asyncio.create_task(execute(...))` with persisted dispatch/receipts; tasks remain tied to the backend process lifecycle. `session_recovery.py` explicitly avoids automatic replay of incomplete tool operations. This is NOT a persistent independent background queue and does NOT guarantee safe pause/restart.

## Scope and deployment
This file may be shared as documentation on both branches. All code changes remain on `updates`; no Live/master runtime changes or workflow edits without explicit approval. Consult this roadmap after Preview is complete, and update each checkbox only after tests.
