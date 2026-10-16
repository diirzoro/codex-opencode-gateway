# Smart Preview — Test-only validation and release gate
Status: READY FOR CONTROLLED TEST-ONLY VALIDATION AFTER BACKUP; NOT READY TO ENABLE DYNAMIC EXECUTION. No deployment performed.
Branch: updates; production master and Live remain untouched.

## Test deployment decision (2026-10-16)
- A controlled **Test-only checkout and validation** is appropriate once a backup and rollback path have been confirmed; do not promote to master and do not enable the isolated preview runner.
- Fixed unit-test contract bugs: capacity release inconsistency test now passes the cleanup acknowledgement; migration column assertions ignore named constraints.
- The test plan is **not evidence of passing tests**; all runtime and PostgreSQL checks must actually be executed in Test.

## Before any Test update
1. Confirm the Test checkout points to `updates`; snapshot/backup **Test only** database/files/config. Never copy or expose production .env.
2. From the Test backend virtual environment, inspect `alembic heads` and `alembic current`. Expected repository migration head: `0020_preview_worker_capacity`; actual DB revision must be checked, not assumed.
3. Use a **disposable PostgreSQL test database** for `alembic upgrade head` and a separate disposable copy for `alembic downgrade -1`; do not downgrade a shared database.
4. Run unit tests from backend working directory (after installing declared dependencies):
   `python -m unittest discover -s tests -p 'test_preview*.py'`
   `python -m unittest discover -s tests -p 'test_email_verification_switch.py'`
5. Run PostgreSQL two-transaction concurrency tests (same worker capacity=1, two different workspaces): exactly one reservation commits; losing request queues. Verify that explicit cleanup acknowledgment, generation and ownership are required for release.
6. Test that GET status/plan never starts execution, browser reconnect never starts, and POST Start remains 503 while unverified worker execution is disabled.
7. Confirm OpenCode coding agent sessions and Live are unaffected.

## Prerequisites to enable dynamic Preview (NOT DONE)
- [ ] Dedicated sandbox/worker host or equivalent strong isolation with untrusted code separated from Gateway/PostgreSQL/OpenCode.
- [ ] Worker authenticated private registration and fresh attestation, realistic heartbeats and separate trust boundary.
- [ ] Trusted atomic durable reservation + resource accounting (CPU/RAM/disk), queueing and concurrency load tests.
- [ ] Constrained build/image preparation, no shared secrets, restricted egress and no Docker socket / sensitive mounts.
- [ ] Verified isolated npm/Python run profiles and separate-origin authenticated preview proxy; no public random ports.
- [ ] Explicit Start/Stop wiring, persisted leases, dynamic 300-second idle reaper and failure/restart cleanup.
- [ ] E2E manual Preview UI, tenant isolation and regression/security tests in Test.
- [ ] Explicit owner approval for promoting to master/Live.

## Current code caveats
The scheduling, worker selection, leasing and capacity store are *dormant control-plane primitives*, not a real isolated runner. Tests added on GitHub have not yet been executed here. Do not advertise dynamic Preview as available. The slot-release function now requires `cleanup_confirmed=True` from a trusted dispatcher after sandbox destruction and route revocation; it must never be passed from browser input.

## Separate launch concern
`EMAIL_VERIFICATION_REQUIRED=false` is an opt-in Test/backend configuration for early acquisition, not a Preview feature. Validate account anti-abuse and recovery restrictions before deciding on Live.
