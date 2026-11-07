# TEST database migrations during deploy-test

**Current source behavior (26 October 2026).** The old mandatory
`sudo -n /usr/local/sbin/opencode-gateway-test-migrate upgrade` dependency
has been removed. There is **no need to install or invoke** a separate
root-owned migration script, modify sudoers, or manually advance Alembic
for every release. The former `deployment/test-only-migrate.sh` instructions
were stale and the file is not tracked in this branch.

`scripts/full_test_git_release.py` now performs the following in the existing
TEST release procedure:

1. Confirm the running `opencode-gateway-test.service` is owned by the
   deployment account and its working directory is the TEST backend.
2. Obtain `DATABASE_URL` and related configuration from that **running
   TEST service process**, not from the workflow shell or an assumed
   `.env` file. The effective systemd environment may have overrides.
   No credentials or connection URLs are printed.
3. Connect with the existing TEST Python environment and confirm that
   `SELECT current_database()` returns **`opencode_gateway_test`**.
   Mismatched or unreadable environments stop the operation rather than
   risking an unintended database.
4. Create a private custom-format `pg_dump` backup under
   `/home/tahir/.opencode-gateway-test-db-backups/`, owned by the
   deployment user and protected with directory mode `0700`.
   Validate its format with `pg_restore --list`; retain the backup
   for operator recovery. This uses standard existing PostgreSQL
   utilities, not an additional service or worker.
5. Sync the approved GitHub `updates` source to the TEST working tree.
6. Execute `python -m alembic -c alembic.ini upgrade head` as the
   existing TEST user in its existing virtualenv. This upgrades all
   pending revisions in the checked-out linear chain.
7. Verify `current_database()` **again** and assert the
   `alembic_version` revision equals the current Alembic head.
   Only after success restart **the TEST Gateway service** and mark
   the approved release SHA. OpenCode Native is not restarted.

`audit-test` remains read-only and does not connect to or migrate the
database. `rollback-test` restores source code only; it **does not**
automatically reverse database schema revisions. Existing repository
and project file preservation policies remain in force.

## If a deploy fails

The release is **not** successful when an actual migration fails. Failure
may be caused by missing `pg_dump`/`pg_restore`, inaccessible effective
service environment, unavailable TEST virtualenv, database identity
mismatch, database permissions, or a real Alembic/data conflict.
The uniqueness migration `0026_unique_registration_identities`,
for example, deliberately refuses existing normalized duplicate
accounts instead of deleting or modifying them silently.

Review the failed TEST job and inspect only sanitized database
diagnostics. Do not weaken the TEST database-identity check, skip a
failing Alembic revision, or run the release against LIVE to work around
an error. The existing source rollback attempts to restore prior Git
source if source replacement/restart fails; it **cannot** undo an already
committed database migration.

## Scope

Changes apply to the `updates` branch and the explicit TEST
`deploy-test` workflow only. This does not mutate LIVE, `master`,
systemd configuration, environment/secret files, Nginx, OpenCode Native,
or the separately protected Preview infrastructure.

The source implementation and CI checks are not by themselves proof
that an actual TEST database backup/migration succeeded. Only a
successful pinned `deploy-test` run and TEST acceptance can establish
that.
