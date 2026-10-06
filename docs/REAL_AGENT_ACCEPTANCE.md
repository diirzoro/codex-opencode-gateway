# Real agent acceptance — 2026-10-05

## Required path

Client UI → Gateway API → isolated OpenCode runtime → OpenCode-configured DeepSeek provider → real assistant response → Gateway → Client UI.

No separate DeepSeek chat API or permanent provider-specific architecture was added. OpenCode remains the provider/agent layer. Gateway owns authentication, entitlement and workspace authorization.

## Exact interfaces already implemented

- POST /api/workspaces/{workspace_id}/sessions creates a real OpenCode session in the owned runtime.
- GET /api/workspaces/{workspace_id}/providers and /agents discover actual runtime capabilities.
- POST /api/workspaces/{workspace_id}/providers/deepseek/credentials installs the user-entered key in that runtime and saves an encrypted workspace-scoped database credential. The response contains status and last four characters, never the full key.
- POST /api/sessions/{session_id}/messages submits the message to internal POST /session/{runtime_session_id}/message.
- GET /api/sessions/{session_id}/messages reads actual OpenCode messages; the frontend renders their text.
- GET /api/sessions/{session_id}/events provides lifecycle SSE. The current bridge shows lifecycle states and final text; it does not stream token deltas.
- POST /api/sessions/{session_id}/stop requests actual OpenCode abort without starting a new runtime solely to stop it.

## Isolated test setup

The local acceptance Gateway runs on 127.0.0.1:8772 with a separate database, workspace root, runtime root and encryption key under the parent .audit/isolated-agent-acceptance directory. It uses installed local OpenCode 1.18.31, not the shared VPS service. The VPS tunnel failed authentication; using the local isolated runtime was subsequently explicitly requested by the user.

Runtime provider auth may be stored by OpenCode in its private runtime HOME/XDG auth state, outside the project and Files/Git scope. It must not appear in public project files or browser responses. Separate contexts are local test isolation, not a production OS sandbox.

## Verified results — 2026-10-06

- User entered a DeepSeek credential locally in the owned Settings → Connections popup. Actual DeepSeek provider/models appeared in the composer (including deepseek-flash / DeepSeek V4.1 Flash).
- The authenticated client submitted `Reply with: OpenCode connection works` through POST /api/sessions/{session_id}/messages. The local isolated OpenCode runtime called its configured DeepSeek provider and the actual assistant response `OpenCode connection works` appeared in client chat. A separate `hi` also produced a real greeting. No synthetic response or direct DeepSeek integration was used.
- Live Stop exposed a race: a delayed execution failure could overwrite cancelled state. The bridge now commits terminal execution transitions atomically only when status is not cancelled. Two regression cases protect late failure/completion. A new real cancellation test remained cancelled; a subsequent real prompt completed successfully.
- Real unavailable-runtime browser case passed: HTTP 503, honest unavailable state, disabled Send, no manufactured assistant reply.
- Actual-key audit: encrypted database storage; zero matches in repository source/staged diff, workspace files/Git, runtime logs and inspected public API responses. One private OpenCode runtime auth.json legitimately contains the credential, outside repository/Files/Git scope. This is not a claim that the key is absent from all disk files.
- Temporary direct DeepSeek path: NOT USED. The VPS was not used for execution or modified.
- Automated real-provider browser case is skipped in the disabled-runtime suite; live success above was verified separately in the isolated preview. Lifecycle SSE and final message rendering work; token-delta streaming remains missing.

Production OS/network sandboxing, quotas, supervised recovery and multi-user isolation are still pending. Local separate HOME/XDG/process/auth state is not a production security boundary. Evidence images and safe leakage audit results live outside the repository in the parent .audit directory.
