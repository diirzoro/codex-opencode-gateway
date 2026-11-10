# Pi Gateway — TEST

Web workspace and account-management platform powered by **Pi Coding Agent**.

## Architecture

The site uses one Nginx process for the TEST and LIVE virtual hosts. The TEST
virtual host routes normal application traffic to the Gateway backend on
`127.0.0.1:8001` and AI traffic under `/native-direct/api/` to the existing
`/run/pi-central/pi.sock` Unix socket. Pi Central runs as
`pi-central.service` and controls `@earendil-works/pi-coding-agent` using
its native RPC protocol.

The Gateway owns account authentication, projects, workspace ownership,
GitHub integration, administrative policies, plans, and billing. **Pi alone**
executes model requests, messages, conversation history, tools, extensions,
and skills. The approved design transfers customer AI credentials and their
verification to Gateway-owned encrypted records in PostgreSQL, not to shared
Pi configuration. This credential migration is NOT IMPLEMENTED yet.

TEST and LIVE have separate database identities. Keep account data, project
files and Pi sessions distinct. An account's Pi `auth.json` must not be
silently shared with other users merely because the operating system uses the
same service user.

The existing domain, Gateway service names and historical database identifiers
contain `opencode` for compatibility with the deployed platform; those names
do not mean the OpenCode engine is installed or supported.

## Status and limitations (2026-11-09)

- VPS operator confirmed Pi CLI version `1.5.0`, `pi-central.service`
  active and Unix-socket health `ready`.
- VPS operator redirected TEST Nginx to
  `/etc/nginx/snippets/pi-central-test.conf`; old TEST OpenCode snippets were
  deleted.
- The operator installed an OpenRouter credential through Pi CLI, whose
  default account directory is `/home/tahir/.pi/agent`.
- GitHub's `integration/pi-central.mjs` is an HTTP-to-Pi RPC transport,
  not a second agent engine. It now points to the installed shared Pi
  configuration in `/home/tahir/.pi/agent` for existing runtime discovery,
  and lets Pi load its native coding tools, skills and extensions. Browser
  login/logout to that shared Pi credential store have now been disabled
  in source to prevent unchecked or cross-customer credential mutation.
  Image parts are passed to Pi RPC; non-image inline uploads are staged inside
  the selected workspace for Pi's tools to inspect. These changes still require
  deployment and an actual server test.
- Deployment run `42671819015` failed with no reported jobs; do not infer
  that GitHub source changes were installed on VPS.
- A nonempty provider key is **not** authentication verification. Shared Pi
  credential add/delete routes are retired; Connections currently presents
  runtime/catalog metadata read-only, NOT customer-owned verified connections.
  The customer-owned PostgreSQL registry, real upstream verification, isolated
  SDK credentials and 7–14 day DB sync are pending the tracked implementation
  and safe schema migration. The current Pi runtime may still have a shared
  credential configured by the VPS operator; it must not be mistaken for a
  customer's saved key.
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
