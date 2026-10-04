# Local development delivery report

Completed local phase: 2026-10-04. No VPS connection, upload, deployment, migration or restart performed. GitHub repository publication is a separate explicitly authorized source upload, not platform deployment or implementation of the app's GitHub integration.

## Delivered behavior

- Professional neutral chat/workspace UI inspired by ChatGPT/Kimi; Arabic/English, RTL/LTR, dark/light and mobile drawers.
- Recognizable official OpenCode SVG mark/wordmark, GitHub mark and consistent vector action icons with accessible names/tooltips.
- Actual account/session/profile/locations and owner/admin guards; preserved DB-backed administrative user overview.
- Real Blank/HTML/Python/Node projects, owned filesystem reads, actual Git diffs and commits.
- Opt-in OpenCode 1.18.31 process/session adapter; New Session retains existing workspace files.
- Partial real transport for provider discovery/messages/abort/reviewed approval/SSE; no fake operational response.
- Source-serving allowlist and auth/path regression fixes; six living reference documents plus asset credits.

## Validation

- Backend: **25 passed**, including installed OpenCode two-session/file-preservation test, actual Git operations, ownership/path/static access and auth/admin checks. One third-party Starlette/AnyIO deprecation warning.
- Playwright: **2 passed**: full local account → template → file → diff → commit flow; desktop/mobile review drawers, SVG branding, Arabic/English and dark mode. No uncaught browser JS errors in visual-navigation test. Additional screenshot smoke flow passed.
- Alembic: fresh SQLite upgrade from zero to **0002_workspaces**, current revision confirmed. PostgreSQL offline SQL generated. PostgreSQL 16 and production target Python 3.12 not executed; local Python 3.13 used.
- Agent approval/provider/ownership tests use transport doubles. They do not prove provider-authenticated model edits, sensitive-command execution or complete streaming/recovery.

## Schema and APIs

Added migration `backend/alembic/versions/0002_projects_workspaces.py`: projects, workspaces, workspace_sessions, execution_events. Existing account/location schema preserved.

Added owned projects/workspaces/templates/files/content/changes/diff/logs/git status and commit/session/provider routes; OpenCode health/status and truthful GitHub status; session messages/stop/permissions/events. Push returns 503 with no attempt; delete returns 409 preserving files. Existing auth/profile/admin behavior hardened. Exact routes and body schemas are in API_REFERENCE.md.

## Status outcome

REAL locally: accounts/guards, local files/templates/diffs/commits, real installed-runtime sessions, admin DB counts. PARTIAL: full workspace lifecycle, message/event/approval bridge and provider discovery. SIMULATED product success: removed. MISSING: GitHub App/repo clone/publish/push verification, provider auth/encrypted secret lifecycle, public sandbox/network/quotas, previews/uploads/retention and billing. BLOCKED verification: real provider execution requires a supported credential flow and credentials; production checks await explicit authorization. Full v2.1 is **not complete**; the local development phase is delivered with remaining work recorded.

## Source upload policy

User requested all project files except test files. Tests and Playwright reports remain local; do not upload backend/tests, tests, playwright.config.cjs, .playwright-mcp, snapshots, test DBs, test-results or screenshots. Secrets, runtime/workspace customer data, local environments and dependencies are also excluded. Existing local draft storage was not deleted or converted to server data.

## Future deployment

Exact later manual backup/copy/install/migration/service/health commands are in `deployment/README.md`. They were not executed. Resolve SECURITY_MODEL.md launch blockers first; trusted local runtime mode must not be exposed publicly.

## Changed or added files

- `.env.example`
- `.gitignore`
- `app.js`
- `backend/alembic/versions/0002_projects_workspaces.py`
- `backend/app/config.py`
- `backend/app/main.py`
- `backend/app/models/__init__.py`
- `backend/app/models/workspace.py`
- `backend/app/routes/admin.py`
- `backend/app/routes/agent.py`
- `backend/app/routes/auth.py`
- `backend/app/routes/dependencies.py`
- `backend/app/routes/workspaces.py`
- `backend/app/schemas/account.py`
- `backend/app/services/github.py`
- `backend/app/services/opencode.py`
- `backend/app/services/providers.py`
- `backend/app/services/workspaces.py`
- `backend/requirements.txt`
- `backend/tests/browser_server.py`
- `backend/tests/conftest.py`
- `backend/tests/test_accounts.py`
- `backend/tests/test_agent_boundaries.py`
- `backend/tests/test_security.py`
- `backend/tests/test_workspaces.py`
- `config.js`
- `deployment/.env.production.example`
- `deployment/README.md`
- `docs/API_REFERENCE.md`
- `docs/ARCHITECTURE.md`
- `docs/ASSET_CREDITS.md`
- `docs/DATABASE_REFERENCE.md`
- `docs/DEVELOPMENT_ROADMAP.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/SECURITY_MODEL.md`
- `index.html`
- `node_modules/.bin/playwright`
- `node_modules/.bin/playwright-core`
- `node_modules/.bin/playwright-core.cmd`
- `node_modules/.bin/playwright-core.ps1`
- `node_modules/.bin/playwright.cmd`
- `node_modules/.bin/playwright.ps1`
- `node_modules/.package-lock.json`
- `node_modules/@playwright/test/cli.js`
- `node_modules/@playwright/test/index.d.ts`
- `node_modules/@playwright/test/index.js`
- `node_modules/@playwright/test/index.mjs`
- `node_modules/@playwright/test/LICENSE`
- `node_modules/@playwright/test/NOTICE`
- `node_modules/@playwright/test/package.json`
- `node_modules/@playwright/test/README.md`
- `node_modules/@playwright/test/reporter.d.ts`
- `node_modules/@playwright/test/reporter.js`
- `node_modules/@playwright/test/reporter.mjs`
- `node_modules/playwright/cli.js`
- `node_modules/playwright/index.d.ts`
- `node_modules/playwright/index.js`
- `node_modules/playwright/index.mjs`
- `node_modules/playwright/jsx-runtime.js`
- `node_modules/playwright/jsx-runtime.mjs`
- `node_modules/playwright/lib/agents/agentParser.js`
- `node_modules/playwright/lib/agents/copilot-setup-steps.yml`
- `node_modules/playwright/lib/agents/generateAgents.js`
- `node_modules/playwright/lib/agents/playwright-test-coverage.prompt.md`
- `node_modules/playwright/lib/agents/playwright-test-generate.prompt.md`
- `node_modules/playwright/lib/agents/playwright-test-generator.agent.md`
- `node_modules/playwright/lib/agents/playwright-test-heal.prompt.md`
- `node_modules/playwright/lib/agents/playwright-test-healer.agent.md`
- `node_modules/playwright/lib/agents/playwright-test-plan.prompt.md`
- `node_modules/playwright/lib/agents/playwright-test-planner.agent.md`
- `node_modules/playwright/lib/cli/reportActions.js`
- `node_modules/playwright/lib/cli/testActions.js`
- `node_modules/playwright/lib/common/index.js`
- `node_modules/playwright/lib/common/index.js.txt`
- `node_modules/playwright/lib/errorContext.js`
- `node_modules/playwright/lib/globals.js`
- `node_modules/playwright/lib/index.js`
- `node_modules/playwright/lib/isomorphic.js`
- `node_modules/playwright/lib/isomorphic.js.txt`
- `node_modules/playwright/lib/loader/loaderProcessEntry.js`
- `node_modules/playwright/lib/loader/loaderProcessEntry.js.txt`
- `node_modules/playwright/lib/matchers/expect.js`
- `node_modules/playwright/lib/matchers/expect.js.LICENSE`
- `node_modules/playwright/lib/matchers/expect.js.txt`
- `node_modules/playwright/lib/mcp/test/browserBackend.js`
- `node_modules/playwright/lib/mcp/test/generatorTools.js`
- `node_modules/playwright/lib/mcp/test/plannerTools.js`
- `node_modules/playwright/lib/mcp/test/seed.js`
- `node_modules/playwright/lib/mcp/test/streams.js`
- `node_modules/playwright/lib/mcp/test/testBackend.js`
- `node_modules/playwright/lib/mcp/test/testContext.js`
- `node_modules/playwright/lib/mcp/test/testTool.js`
- `node_modules/playwright/lib/mcp/test/testTools.js`
- `node_modules/playwright/lib/package.js`
- `node_modules/playwright/lib/program.js`
- `node_modules/playwright/lib/runner/index.js`
- `node_modules/playwright/lib/runner/index.js.txt`
- `node_modules/playwright/lib/transform/babelBundle.js`
- `node_modules/playwright/lib/transform/babelBundle.js.LICENSE`
- `node_modules/playwright/lib/transform/babelBundle.js.txt`
- `node_modules/playwright/lib/transform/esmLoader.js`
- `node_modules/playwright/lib/transform/esmLoader.js.LICENSE`
- `node_modules/playwright/lib/transform/esmLoader.js.txt`
- `node_modules/playwright/lib/util.js`
- `node_modules/playwright/lib/worker/workerProcessEntry.js`
- `node_modules/playwright/lib/worker/workerProcessEntry.js.txt`
- `node_modules/playwright/LICENSE`
- `node_modules/playwright/NOTICE`
- `node_modules/playwright/package.json`
- `node_modules/playwright/README.md`
- `node_modules/playwright/test.d.ts`
- `node_modules/playwright/test.js`
- `node_modules/playwright/test.mjs`
- `node_modules/playwright/ThirdPartyNotices.txt`
- `node_modules/playwright/types/test.d.ts`
- `node_modules/playwright/types/testReporter.d.ts`
- `node_modules/playwright-core/bin/install_media_pack.ps1`
- `node_modules/playwright-core/bin/install_webkit_wsl.ps1`
- `node_modules/playwright-core/bin/reinstall_chrome_beta_linux.sh`
- `node_modules/playwright-core/bin/reinstall_chrome_beta_mac.sh`
- `node_modules/playwright-core/bin/reinstall_chrome_beta_win.ps1`
- `node_modules/playwright-core/bin/reinstall_chrome_stable_linux.sh`
- `node_modules/playwright-core/bin/reinstall_chrome_stable_mac.sh`
- `node_modules/playwright-core/bin/reinstall_chrome_stable_win.ps1`
- `node_modules/playwright-core/bin/reinstall_msedge_beta_linux.sh`
- `node_modules/playwright-core/bin/reinstall_msedge_beta_mac.sh`
- `node_modules/playwright-core/bin/reinstall_msedge_beta_win.ps1`
- `node_modules/playwright-core/bin/reinstall_msedge_dev_linux.sh`
- `node_modules/playwright-core/bin/reinstall_msedge_dev_mac.sh`
- `node_modules/playwright-core/bin/reinstall_msedge_dev_win.ps1`
- `node_modules/playwright-core/bin/reinstall_msedge_stable_linux.sh`
- `node_modules/playwright-core/bin/reinstall_msedge_stable_mac.sh`
- `node_modules/playwright-core/bin/reinstall_msedge_stable_win.ps1`
- `node_modules/playwright-core/browsers.json`
- `node_modules/playwright-core/cli.js`
- `node_modules/playwright-core/index.d.ts`
- `node_modules/playwright-core/index.js`
- `node_modules/playwright-core/index.mjs`
- `node_modules/playwright-core/lib/bootstrap.js`
- `node_modules/playwright-core/lib/coreBundle.js`
- `node_modules/playwright-core/lib/entry/cliDaemon.js`
- `node_modules/playwright-core/lib/entry/dashboardApp.js`
- `node_modules/playwright-core/lib/entry/mcp.js`
- `node_modules/playwright-core/lib/entry/oopBrowserDownload.js`
- `node_modules/playwright-core/lib/package.js`
- `node_modules/playwright-core/lib/server/chromium/appIcon.png`
- `node_modules/playwright-core/lib/server/electron/loader.js`
- `node_modules/playwright-core/lib/serverRegistry.js`
- `node_modules/playwright-core/lib/serverRegistry.js.LICENSE`
- `node_modules/playwright-core/lib/tools/cli-client/channelSessions.js`
- `node_modules/playwright-core/lib/tools/cli-client/cli.js`
- `node_modules/playwright-core/lib/tools/cli-client/help.json`
- `node_modules/playwright-core/lib/tools/cli-client/minimist.js`
- `node_modules/playwright-core/lib/tools/cli-client/output.js`
- `node_modules/playwright-core/lib/tools/cli-client/program.js`
- `node_modules/playwright-core/lib/tools/cli-client/registry.js`
- `node_modules/playwright-core/lib/tools/cli-client/session.js`
- `node_modules/playwright-core/lib/tools/dashboard/appIcon.png`
- `node_modules/playwright-core/lib/tools/skills/playwright-cli/references/element-attributes.md`
- `node_modules/playwright-core/lib/tools/skills/playwright-cli/references/playwright-tests.md`
- `node_modules/playwright-core/lib/tools/skills/playwright-cli/references/request-mocking.md`
- `node_modules/playwright-core/lib/tools/skills/playwright-cli/references/running-code.md`
- `node_modules/playwright-core/lib/tools/skills/playwright-cli/references/session-management.md`
- `node_modules/playwright-core/lib/tools/skills/playwright-cli/references/storage-state.md`
- `node_modules/playwright-core/lib/tools/skills/playwright-cli/references/test-generation.md`
- `node_modules/playwright-core/lib/tools/skills/playwright-cli/references/tracing.md`
- `node_modules/playwright-core/lib/tools/skills/playwright-cli/references/video-recording.md`
- `node_modules/playwright-core/lib/tools/skills/playwright-cli/SKILL.md`
- `node_modules/playwright-core/lib/tools/skills/playwright-component-testing/references/gallery-spec.md`
- `node_modules/playwright-core/lib/tools/skills/playwright-component-testing/references/migration.md`
- `node_modules/playwright-core/lib/tools/skills/playwright-component-testing/references/react.md`
- `node_modules/playwright-core/lib/tools/skills/playwright-component-testing/references/typing.md`
- `node_modules/playwright-core/lib/tools/skills/playwright-component-testing/references/vue.md`
- `node_modules/playwright-core/lib/tools/skills/playwright-component-testing/SKILL.md`
- `node_modules/playwright-core/lib/tools/skills/playwright-trace/SKILL.md`
- `node_modules/playwright-core/lib/tools/utils/extension.js`
- `node_modules/playwright-core/lib/tools/utils/socketConnection.js`
- `node_modules/playwright-core/lib/utilsBundle.js`
- `node_modules/playwright-core/lib/utilsBundle.js.LICENSE`
- `node_modules/playwright-core/lib/vite/dashboard/assets/codeMirrorModule--QdMvsKi.css`
- `node_modules/playwright-core/lib/vite/dashboard/assets/codeMirrorModule-CQ8RZGBm.js`
- `node_modules/playwright-core/lib/vite/dashboard/assets/codicon-DCmgc-ay.ttf`
- `node_modules/playwright-core/lib/vite/dashboard/assets/firefox-1bWoP6pv.svg`
- `node_modules/playwright-core/lib/vite/dashboard/assets/firefox-beta-k3eOH_eK.svg`
- `node_modules/playwright-core/lib/vite/dashboard/assets/firefox-nightly-Cp5nfeDT.svg`
- `node_modules/playwright-core/lib/vite/dashboard/assets/index-AwgwcYie.css`
- `node_modules/playwright-core/lib/vite/dashboard/assets/index-hRvO4yU2.js`
- `node_modules/playwright-core/lib/vite/dashboard/assets/safari-na3_-uQk.svg`
- `node_modules/playwright-core/lib/vite/dashboard/index.html`
- `node_modules/playwright-core/lib/vite/dashboard/playwright-logo.svg`
- `node_modules/playwright-core/lib/vite/htmlReport/index.html`
- `node_modules/playwright-core/lib/vite/htmlReport/report.css`
- `node_modules/playwright-core/lib/vite/htmlReport/report.js`
- `node_modules/playwright-core/lib/vite/recorder/assets/codeMirrorModule--QdMvsKi.css`
- `node_modules/playwright-core/lib/vite/recorder/assets/codeMirrorModule-CVQWJZAA.js`
- `node_modules/playwright-core/lib/vite/recorder/assets/codicon-DCmgc-ay.ttf`
- `node_modules/playwright-core/lib/vite/recorder/assets/index-BZpYJZ-P.css`
- `node_modules/playwright-core/lib/vite/recorder/assets/index-hrlLqLtq.js`
- `node_modules/playwright-core/lib/vite/recorder/index.html`
- `node_modules/playwright-core/lib/vite/recorder/playwright-logo.svg`
- `node_modules/playwright-core/lib/vite/traceViewer/assets/codeMirrorModule-BbkfBe3n.js`
- `node_modules/playwright-core/lib/vite/traceViewer/assets/defaultSettingsView-Ds6CBOo0.js`
- `node_modules/playwright-core/lib/vite/traceViewer/assets/urlMatch-L3liM589.js`
- `node_modules/playwright-core/lib/vite/traceViewer/assets/xtermModule-DywYcAf8.js`
- `node_modules/playwright-core/lib/vite/traceViewer/codeMirrorModule.-QdMvsKi.css`
- `node_modules/playwright-core/lib/vite/traceViewer/codicon.DCmgc-ay.ttf`
- `node_modules/playwright-core/lib/vite/traceViewer/defaultSettingsView.Bqk9acqE.css`
- `node_modules/playwright-core/lib/vite/traceViewer/index.B4cLoZK3.js`
- `node_modules/playwright-core/lib/vite/traceViewer/index.B_TqY17P.css`
- `node_modules/playwright-core/lib/vite/traceViewer/index.html`
- `node_modules/playwright-core/lib/vite/traceViewer/manifest.webmanifest`
- `node_modules/playwright-core/lib/vite/traceViewer/playwright-logo.svg`
- `node_modules/playwright-core/lib/vite/traceViewer/snapshot.B_Jk1wbt.js`
- `node_modules/playwright-core/lib/vite/traceViewer/snapshot.html`
- `node_modules/playwright-core/lib/vite/traceViewer/sw.bundle.js`
- `node_modules/playwright-core/lib/vite/traceViewer/uiMode.CU5KtEkS.js`
- `node_modules/playwright-core/lib/vite/traceViewer/uiMode.CyMfwkXJ.css`
- `node_modules/playwright-core/lib/vite/traceViewer/uiMode.html`
- `node_modules/playwright-core/lib/vite/traceViewer/xtermModule.kHJ-D0s7.css`
- `node_modules/playwright-core/lib/webp_codec.LICENSE`
- `node_modules/playwright-core/lib/webp_codec.wasm`
- `node_modules/playwright-core/lib/xdg-open`
- `node_modules/playwright-core/LICENSE`
- `node_modules/playwright-core/NOTICE`
- `node_modules/playwright-core/package.json`
- `node_modules/playwright-core/README.md`
- `node_modules/playwright-core/ThirdPartyNotices.txt`
- `node_modules/playwright-core/types/protocol.d.ts`
- `node_modules/playwright-core/types/structs.d.ts`
- `node_modules/playwright-core/types/types.d.ts`
- `package-lock.json`
- `package.json`
- `playwright.config.cjs`
- `README.md`
- `styles.css`
- `tests/browser/workspace.spec.cjs`

## Final registration simplification

Username minimum 6 characters; password minimum 8 characters including an ASCII number and punctuation symbol, without uppercase/letter requirements. Updated backend and Arabic/English frontend hints/validation. No migration. Existing short-username/old-password logins are unchanged. Two additional backend policy/legacy-login regressions passed; Playwright registered and completed the project flow using an eight-character password. Final local result: 25 backend tests and 2 browser tests passed.
