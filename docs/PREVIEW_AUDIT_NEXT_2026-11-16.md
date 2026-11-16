# Preview follow-up: React readiness and controlled security checks

## Current validation

40 local tests pass: 13 resource lifecycle cases, 22 encrypted browser-grant/session/project boundary cases and 5 safe inventory/probe cases. The grant tests use real Fernet cryptography with simulated database/session state; they are not a two-account production penetration test. Existing LIVE Python acceptance remains the previously recorded successful test.

## Prepared operator actions

The existing manual Preview operations workflow now includes:

| Operation | Behavior |
| --- | --- |
| react_inspect | Read-only PostgreSQL transaction scoped to the existing testuser account; report only React/Vite/Next detection, standard script names, known framework dependency names, lockfile presence and existing static outputs. No source, paths, customer IDs, script commands, dependency URLs or credentials are printed. |
| audit | Use two generated private worker snapshots and a disposable host canary to check actual read-only mounts, hidden host canary/other snapshot/Docker socket, non-root identity, kernel AppArmor, cgroup memory/CPU/PID limits and refusal of a second concurrent runtime. Stop only audit-owned jobs afterward. |
| audit_full | The same controlled checks, followed by the real five-minute idle and fifteen-minute absolute expiry tests. Allow about 21 minutes; it occupies the single runtime slot during those timer checks. |

All audit modes refuse to start if a managed preview is already running. They do not read real customer projects or change Pi/Gateway configuration. These modes are admin-only one-time scripts; they add no per-message Python work or permanent service.

## Deployment boundary

These newly prepared operator checks have not run on the VPS. The React dependency installation/build/cache pipeline is not implemented by this change. Read the actual project readiness result before choosing the existing framework build path. React project source and dependency files remain unchanged.

At preparation time the previous connected browser became unavailable, and the alternate browser was not signed into GitHub. A signed-in GitHub session is required to dispatch the prepared manual checks; no SSH keys or server passwords are requested from the user.
