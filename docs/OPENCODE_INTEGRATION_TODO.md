# OpenCode integration TODO — updates

Date: 2026-10-07. Base: `55d11739a3fa757b01a77d0a8450a38f1807a4b3`.

Checked means implementation and available independent verification are complete. It does **not** mean the pending real-provider acceptance checks passed. See [the report](OPENCODE_INTEGRATION_REPORT.md) for evidence and limitations.

- [x] 1. Expose every provider in the selected runtime catalog, with connection/policy annotations.
- [x] 2. Render runtime API/OAuth methods, conditional prompts and server-side auth forwarding.
- [x] 3. Expose real runtime health/version/providers/models/agents/sessions/permissions/tools and additional supported metadata.
- [x] 4. Consolidate selected-workspace discovery in `/api/workspaces/{id}/runtime`.
- [x] 5. Lock startup per workspace, coalesce discovery, reuse generations and restore once.
- [x] 6. Keep agents independent of provider connections; omit the agent override by default.
- [x] 7. Keep models and default models tied to the runtime provider catalog.
- [x] 8. Use the selected runtime in Settings/Connections rather than the reference service.
- [x] 9. Pool runtime HTTP; enforce a total startup deadline and explicit health/error handling.
- [x] 10. Restore credentials once per generation; confirm runtime deletion before deleting stored credentials.
- [x] 11. Implement a real, tool-denied model validation request before API-key persistence; roll back failures.
- [x] 12. Show the workspace immediately and reuse one bootstrap cache across workspace/settings navigation.
- [x] 13. Retain restricted catalog entries visibly while enforcing provider/model/tool policy server-side.
- [ ] 14. Complete authenticated real-provider end-to-end acceptance. Process startup/catalog/auth schema/session/isolation checks pass; Gemini/DeepSeek request, OAuth login and stored-key restart checks remain pending.
- [x] 15. Instrument startup/discovery/bootstrap/frontend visibility; collect scoped before/after timings and request counts.
- [x] 16. Preserve main client sidebar, workflows, billing/payment and unrelated pages.
- [x] 17. Supply this TODO, a detailed report, changed-file inventory, verification and commit SHA in the final response.

## UI follow-up

- [x] Implement after independent runtime/bootstrap/default-agent/session integration checks pass.
- [x] Remove duplicated internal workspace navigation toolbar.
- [x] Keep conversation in the center and move session history into a compact picker.
- [x] Use two side-panel modes: Changes and Preview.
- [x] Show Git status, changed-file selection and current OpenCode session diffs.
- [x] Add start/refresh for a read-only sandboxed HTML preview.
- [x] Show unsupported browser/backend preview honestly; do not invent a runner.
- [x] Verify desktop/mobile layout with labeled UI fixtures and capture screenshots.
- [ ] Final acceptance in an authenticated real customer workspace after provider checks pass. Do not deploy/merge before this acceptance.

## Remaining acceptance, in order

1. Review/save the saved cloud environment requirements and publish the environment settings when appropriate; verify network access. Supply Gemini credentials securely to the application/server environment. Use the live provider ID `google`; use `deepseek` only if Gemini is unavailable. Never paste credentials into chat or reports.
2. Use an existing real authenticated account/workspace. The current canonical DB has no customers/workspaces; no test customers were inserted.
3. Connect through the actual Gateway endpoint, require a successful OpenCode model response, verify encrypted persistence and default-agent omission.
4. Send a real conversation prompt with `agent_id` omitted; check messages/session identity and policy behavior.
5. Disconnect; confirm runtime and stored key removal. Reconnect, restart Gateway, verify exactly one restoration pass and one PUT per saved key per generation.
6. Authenticate one OAuth-only provider through its real authorization/callback flow.
7. Repeat cold/warm workspace and Workspace ↔ Connections browser acceptance with the real account, check two-workspace provider isolation, then approve the implementation for deployment separately.
