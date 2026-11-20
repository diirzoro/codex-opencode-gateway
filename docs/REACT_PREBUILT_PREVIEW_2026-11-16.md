# React prebuilt preview: deployed and accepted on LIVE

Updated 2026-11-17: PR #51 was merged and the selective react_activate operation succeeded in run 44031305329. Live browser acceptance confirmed React rendering, counter increment/reset and refresh. Subsequent lifecycle checks confirmed Stop, restart, switching to Python and returning to React. PR #52 tightened expiry on each fetch and was deployed successfully in run 44040598727. See PREVIEW_COMPLETION_2026-11-17_AR.md for the current Java status and remaining acceptance work.

Existing LIVE readiness inventory found a Vite/React workspace in the test account with package-lock.json and dist/index.html. This change serves that existing dist output through the current authenticated worker and separate-origin browser-ticket relay. It installs no dependencies, executes no build scripts and starts no Node or Docker application for the static view.

## Resulting behavior

- React/Vite projects with dist/index.html obtain a static worker profile. Source snapshots retain the existing 50 MiB cap and credential exclusions.
- Only dist assets are addressable. Descriptor-pinned NOFOLLOW opens reject symlinks, hard links, traversal, dotfiles and unsupported asset types. Assets are limited to 2 MiB; reference rewriting is bounded to prevent response amplification.
- Existing browser grants remain session, owner, project and lease bound. Explicit Stop revokes the static lease and removes only its worker snapshot. Static snapshots expire after 15 minutes, with retry on cleanup failure. Marked orphan static snapshots are removed after worker restart. Static preparation preserves at least 5 GiB disk headroom.
- Start/Refresh reloads the existing output and issues a new lease. UI explicitly identifies it as an existing React build and explains that source changes require rebuilding the project. Source freshness is not inferred from dist existence.
- No changes to the user's source, package manifests, dependency lockfiles, database, payment settings, model providers or Pi Central are part of this implementation.

## Validation

The current combined local suite passes 71 tests across Java relay, resource lifecycle, encrypted grant/session/project boundaries, read-only inventory and static serving. JavaScript syntax and operator-script syntax checks pass.

The previously started LIVE audit completed successfully in Actions run 43894588550:

- Actual kernel CPU/memory/PID limits, read-only mounts, enforcing AppArmor and isolation from disposable host/other-snapshot canaries passed.
- A second concurrent dynamic preview was refused.
- Idle expiry passed at 15:22:03 UTC after approximately five minutes.
- Absolute expiry passed at 15:37:11 UTC after approximately fifteen minutes despite explicit activity renewal.

These are controlled worker tests, not a full two-account production penetration test. Static React was also accepted in the LIVE browser as described above.

## Deployment and limits

The prepared react_activate operation backs up the affected worker/Gateway modules and dashboards.js, refuses to proceed while a managed dynamic preview is active, verifies a generated static fixture without an application container, and rolls back code if checks fail. Existing Nginx, environment settings and Pi service are preserved. The current worker and Gateway restart to load code.

Remaining: automatic isolated dependency/build preparation for projects without a valid dist output and end-to-end tests with two real test accounts. Java's server acceptance, customer browser health button and rejection of its stopped ticket passed separately. History-router applications may need their existing build/router configuration to support the preview path prefix; this has not been tested. Unsupported/oversized assets fail closed.
