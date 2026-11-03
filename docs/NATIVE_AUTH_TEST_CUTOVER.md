# TEST OpenCode Native credential cutover — 2026-11-03

## Source change scope
This change is limited to the `updates` branch. LIVE, its database and its
OpenCode systemd service have not been changed by a repository commit.

OpenCode 1.19.4 has process-global `/auth/{provider}` state. Supplying a
different `directory` query parameter does **not** partition that state.
A single TEST Native server cannot offer the same provider under independent
user API keys. This requires a separate Native instance and auth HOME/XDG
storage for each account, or an upstream-supported tenant isolation boundary.
Until such isolation exists, TEST provider IDs can only have a single owner.

## Immediate corrections
- The account provider credential endpoint no longer returns 410 in TEST.
- In Native mode, API keys are PUT into the OpenCode Native auth API only.
  No new key is written to `user_provider_credentials`.
- Native DELETE is still used for revocation, followed by removal of old
  Gateway ciphertext rows if any belong to the caller. The database table and
  existing records are *not* migrated or globally deleted.
- The old unassigned shared credential is never silently reassigned, exposed,
  overwritten or deleted by an account login.
- A configuration guard rejects TEST key mutations until isolation is
  explicitly verified by the operator. Set
  `OPENCODE_NATIVE_AUTH_ISOLATED=1` only **after** completing the checks below.
- A native auth PUT acknowledgement is not API validation. The UI must not
  call it verified; the provider must answer a real Native model prompt.

## Operator gate BEFORE deleting any legacy key
1. Record the exact `opencode-native-test.service` MainPID and its effective
   HOME, XDG_CONFIG_HOME, XDG_DATA_HOME and XDG_CACHE_HOME.
2. Record the equivalent for LIVE (and any other OpenCode daemon on the host).
3. Resolve the effective auth storage directories and any symlinks. Confirm
   that TEST does not reuse LIVE's HOME/XDG auth files, processes, endpoint,
   or service credentials. Separate ports alone are insufficient.
4. Confirm TEST Nginx upstream routes only to that separate TEST Native
   process on loopback. Preserve native SSE streaming and its cache.
5. Confirm the TEST service credentials are not accessible by the LIVE
   service identity, and vice versa. For multiple TEST users, segregate
   OpenCode processes/storage per user *before* allowing two accounts to
   connect the same provider. The current single process does not meet this.
6. Only then enable `OPENCODE_NATIVE_AUTH_ISOLATED=1` for the TEST
   Gateway and explicitly revoke stale TEST-only unassigned keys through
   OpenCode Native `DELETE /auth/{provider}`. Do not read or print secrets.
   Do not touch any LIVE auth file.
7. Verify GET `/provider` from the correct TEST Native process no longer
   lists the stale credential as connected. Restart the TEST service only
   if Native itself requires it to reload auth state; never restart LIVE.
8. Connect a *new* test API key using Native PUT, then run a real
   `/session/{id}/prompt_async` conversation, observe Native SSE, inspect
   Native message/error state, and verify an actual assistant answer.
   A 200/204, a connected flag, or a saved credential alone is insufficient.
9. Disconnect via Native DELETE and confirm it is no longer usable. Audit old
   Gateway `user_provider_credentials` rows separately; do not rehydrate
   them into OpenCode after this cutover.

## Remaining blockers
- No server access was used for this code change: the service identity,
  process auth separation, stale-key deletion and functional paid-provider
  test **remain unverified**.
- The Native connection route does not yet perform a paid-provider
  round-trip before returning: it accurately reports `verified:false`.
- The existing TEST Native service remains a single process-global auth
  store. Setting the flag by itself does not provide account isolation.
- Other non-Native legacy Gateway endpoints remain in source for deployments
  with Native disabled; they must not be invoked by TEST Native flows.
