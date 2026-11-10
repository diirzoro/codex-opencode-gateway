# Pi Gateway — TEST

Web workspace and account-management platform powered by **Pi Coding Agent**.

## Architecture

The site uses one Nginx process for the TEST and LIVE virtual hosts. The TEST
virtual host routes normal application traffic to the Gateway backend on
`127.0.0.1:8001` and AI traffic under `/native-direct/api/` to the existing
`/run/pi-central/pi.sock` Unix socket. Pi Central runs as
`pi-central.service` and controls `@earendil-works/pi-coding-agent` using
the Pi SDK for project conversations. The existing RPC command discovery
is retained only for installed Pi commands/skills.

The Gateway owns account authentication, projects, workspace ownership,
GitHub integration, administrative policies, plans, and billing. **Pi alone**
executes model requests, messages, conversation history, tools, extensions,
and skills. The approved design transfers customer AI credentials and their
verification to Gateway-owned encrypted records in PostgreSQL, not to shared
Pi configuration. The source implementation is on `updates` and requires
the reviewed manual TEST SQL and internal-service secret before deploying;
it has NOT yet passed real VPS/browser acceptance tests.

TEST and LIVE have separate database identities. Keep account data, project
files and Pi sessions distinct. An account's Pi `auth.json` must not be
silently shared with other users merely because the operating system uses the
same service user.

The existing domain, Gateway service names and historical database identifiers
contain `opencode` for compatibility with the deployed platform; those names
do not mean the OpenCode engine is installed or supported.

## Status and limitations (2026-11-10)

- VPS operator confirmed Pi CLI version `1.5.0`, `pi-central.service`
  active and Unix-socket health `ready`.
- VPS operator redirected TEST Nginx to
  `/etc/nginx/snippets/pi-central-test.conf`; old TEST OpenCode snippets were
  deleted.
- The operator installed an OpenRouter credential through Pi CLI, whose
  default account directory is `/home/tahir/.pi/agent`.
- GitHub's `integration/pi-central.mjs` retains the existing HTTP/Unix-socket
  bridge but creates project-specific Pi SDK sessions with in-memory credentials.
  The retired global Pi `auth.json` is read only for native metadata discovery,
  not for customer model execution. Account-owned credentials are retrieved
  internally from Gateway before every prompt. SDK tools are disabled by
  default until single-owner TEST tooling is explicitly enabled and real
  multi-tenant filesystem/process isolation has been demonstrated.
  Inline image parts use the SDK, and other uploads are staged in the owned
  project workspace. VPS deployment and execution remain unverified.
- Deployment run `42671819015` failed with no reported jobs; do not infer
  that GitHub source changes were installed on VPS.
- Gateway source now supports provider-specific real API-key checks, encrypted
  per-account storage, delete/replace, distinct provider/model IDs, and a
  PostgreSQL catalog updated by existing maintenance every 7 days, with a
  14-day stale warning. Unsupported key-verification methods fail closed.
  The database tables have NOT been created in TEST yet. The manual SQL and
  environment requirements are in sections 17–18 of the existing Pi memo.
  Shared Pi credentials might remain configured for the operator; they
  are never evidence of a customer's verified connection.
- The gateway workspace currently expects OpenCode-shaped compatibility
  routes; these are existing UI transport paths, **not** permission to run
  or reinstall the retired OpenCode engine.

## Source and deployment

- Active development branch: `updates`
- Pi bridge source: `integration/pi-central.mjs`
- TEST routing snippet source: `ops/native-direct/nginx.conf`
- TEST in-place deployment helper:
  `ops/native-direct/update-existing-test-nginx.sh`
- TEST release workflow: `.github/workflows/deploy-updates-test.yml`
- Implementation memo: `docs/PI_CENTRAL_MIGRATION_AR.md`

Do not run the old OpenCode Native installation or discovery workflows.
Pi tool processes inherit the existing VPS account's permissions.
The current TEST integration has no OS-level isolation for different users,
so do not treat this deployment as a production multi-tenant sandbox.
The website retains the project-ownership boundary while Pi remains the sole
coding and model execution engine.

## Official Pi documentation

- [Pi RPC](https://pi.dev/docs/latest/rpc)
- [Pi RPC commands](https://pi.dev/docs/latest/rpc-commands)
- [Pi CLI](https://pi.dev/docs/latest/cli)
