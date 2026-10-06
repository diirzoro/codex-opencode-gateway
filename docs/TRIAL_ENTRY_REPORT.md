# Trial entry and expiry verification

Verified locally on 2026-10-05. No push, deployment, SSH or remote mutations.

## Behavior delivered

- Anonymous prompt focus/input and protected workspace entry open the registration/login popup with `Start your free 10-day trial`. The API rejects anonymous project creation.
- Registration grants exactly ten days without payment; subsequent login preserves the original expiry. Customers enter Workspace/Home, while admin/owner retain Admin Overview.
- Home shows days remaining. Expiry disables new projects/sessions, prompt submission, commit and push and displays Subscribe/Renew.
- Owned workspace metadata, files/content, Git diff/status, logs and session listings remain readable after expiry. Live runtime message/history discovery is still gated; this change does not add a stored conversation archive.
- Stopping a session may abort an existing runtime after expiry, but cannot start a new runtime solely to stop it.

## Files and interfaces

Changed: `app.js`, `dashboards.js`, `index.html`, `backend/app/routes/dependencies.py`, `backend/app/routes/agent.py`, `backend/app/services/opencode.py`, and trial tests.

No migration or new API. Existing workspace GET routes now permit expired authenticated owners to read their data. Execution routes retain entitlement and ownership checks. Browser payment and subscription logic is unchanged.

## Evidence

- JavaScript syntax checks passed for app.js and dashboards.js.
- Backend: 66 passed, 1 skipped. The skipped test requires an actual paid model credential; no successful AI file-edit execution is claimed.
- Visible Chromium: 8 existing popup/navigation/payment cases and 3 new trial-entry cases passed.
- Browser expiry presentation uses a controlled entitlement response; real expiry enforcement and retained owned-data reads are tested separately against the backend.
- Real OpenCode reference: authenticated HTTP health and root returned 200; version 1.18.32. Browser navigation was refused in this tool environment, so authenticated visual inspection was not completed. The existing user screenshot remains the visual reference.

## Remaining scope

The live reference is not connected to customer coding execution. Production runtime sandboxing, full live GitHub/model acceptance and automated payment processing remain incomplete; see PRODUCT_MODEL_AUDIT.md. Local runtime adapter verification still targets 1.18.31, and reading the newer reference does not certify compatibility with 1.18.32.

Deployment commands remain in deployment/README.md. This phase does not make the project ready for deployment or authorize deployment.
