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
owns model execution, messages, conversation history, tools, extensions,
skills, and AI credentials. There is no Python AI engine or second
provider-credential registry.

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
- GitHub's `integration/pi-central.mjs` is a **development bridge**, not a
  proven deployment or a complete implementation of Pi tools/files/sessions.
  It currently creates account-specific Pi directories and disables coding
  tools pending operating-system/project isolation.
- Deployment run `42671819015` failed with no reported jobs; do not infer
  that GitHub source changes were installed on VPS.
- Saving any nonempty provider key is **not** authentication verification.
  The connected-provider list must not claim a provider is verified before a
  successful real Pi model request.
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
Do not enable Pi shell/edit tools for untrusted web users under the same
unconfined VPS account. Pi tools inherit operating-system permissions;
isolate projects at the operating-system boundary before public use.

## Official Pi documentation

- [Pi RPC](https://pi.dev/docs/latest/rpc)
- [Pi RPC commands](https://pi.dev/docs/latest/rpc-commands)
- [Pi CLI](https://pi.dev/docs/latest/cli)
