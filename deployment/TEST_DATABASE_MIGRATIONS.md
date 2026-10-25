# TEST-only database migration deployment prerequisite

The TEST deployment script now fails closed if Alembic is not executed and verified.
Do NOT point this runner at production. It asserts current_database() = opencode_gateway_test.

On the VPS as a sudo-authorized operator, after pulling updates:

```bash
sudo install -o root -g root -m 0750 /home/tahir/opencode-gateway-test/deployment/test-only-migrate.sh /usr/local/sbin/opencode-gateway-test-migrate
sudo visudo -f /etc/sudoers.d/opencode-gateway-test-migrate
```

Add this one line via visudo:

```
tahir ALL=(root) NOPASSWD: /usr/local/sbin/opencode-gateway-test-migrate upgrade
```

Then verify securely (after confirming a TEST DB backup exists):

```bash
sudo -n /usr/local/sbin/opencode-gateway-test-migrate upgrade
```

Expect TEST_DATABASE_CONFIRMED, Alembic current, TEST_DB_MIGRATION_OK.
Use only the same protected TEST systemd environment files loaded by
opencode-gateway-test.service. No credentials are printed or stored in Git.
The root-owned runner uses transient systemd units under User=tahir and
passes the protected EnvironmentFile paths to systemd. It never sources
writable files into a root shell or prints secrets. If the TEST rollback
environment path changes, an authorized operator must update and reinstall
the runner. Transient units do not create persistent workers.

The release script copies migrations before executing this runner and restarts
the TEST gateway only on successful migration. A failed migration aborts and
restores application source; database migration rollbacks are NOT automatic.
Do not run this procedure for the live gateway.
