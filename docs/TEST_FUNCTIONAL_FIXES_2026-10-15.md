# Corrected TEST functional fixes — 2026-10-15

Working branch `updates`, baseline `d7ddb59311a65a3416e4402fb4b4c2707a3c99cd`. Six owner-approved requirements only. No workspace deletion/retention restriction or workflow protection change is part of this diff. Production impact from this work: **none**.

| Requirement | Actual repair / evidence | Status before authenticated TEST acceptance |
|---|---|---|
| 1. Real Preview | Existing static preview and fail-closed dynamic security gate preserved. No verified isolated execution engine/preparation/proxy is accessible here; cannot inspect TEST runner without server authorization | **Blocked** — no working dynamic preview URL claimed |
| 2. Collapsible Todo above composer | Removed duplicate chat renderer; native tasks in one default-collapsed panel; progress/states/session/request guards; no history changes | **Partially completed** — actual native updates and VM layout/lifecycle pass; TEST visual check pending |
| 3. Provider speed / 50 displayed | 50 initial runtime-reported providers plus pages of 50 and searchable 223-provider catalog; short per-user cache lock, generation/revision invalidation | **Partially completed** — local real catalog/capacity/performance passed; TEST frontend/network measurement pending |
| 4. API-key method discovery speed | Reuse account-owned runtime for read-only schemas; cached `/provider`/`provider/auth`/integration methods; actual key validation remains isolated and unchanged | **Partially completed** — four real native provider method schemas/performance verified locally; TEST pending |
| 5. Agent choices | Existing single/multi/custom cards; explicit genuine recommendation labels/description; Choose and Continue; duplicate/expiry/stale guards | **Partially completed** — actual native question/continuation and VM interactions pass; TEST visual checks pending |
| 6. Last Workspace after login | Owned backend context, missing/archived/foreign fallback, persisted conversation, shared single-flight password/social/session route; admins unchanged | **Partially completed** — SQL isolation and actual username/email/native-history restore pass; Google/GitHub external login and TEST acceptance pending |

## Changed files

- Frontend: `app.js`, `dashboards.js`, `management.js`. Existing CSS/cards/sidebar/composer identity retained; no CSS-only substitute.
- Backend: `backend/app/routes/workspaces.py`, `backend/app/routes/agent.py`, `backend/app/services/workspace_context.py`, `backend/app/services/opencode.py`, `backend/app/services/opencode_catalog.py`, `backend/app/services/providers.py`.
- Tests: `backend/tests/test_account_catalog_isolation.py`, `backend/tests/test_agent_runtime_interactions.py` (optional fixture args only), `backend/tests/test_test_environment_repairs.py`, `backend/tests/test_test_runtime_acceptance.py`, `tests/browser/test-workspace-ui-unit.cjs`.
- Evidence/handoff: `docs/audit/2026-10-15-provider-performance.json`, this report, `docs/PROJECT_HANDOFF_AND_REMAINING_WORK.md` section 17.

Exact published commit is recorded in the immediately following publication entry in the living handoff. No changes under `.github/workflows/`, deletion/retention services, production configuration, database schema or dependencies.

## Actual results (distinct runs, no inflated aggregate)

| Test command/scope | Passed | Failed | Skipped |
|---|---:|---:|---:|
| `python -m pytest backend/tests/test_account_catalog_isolation.py backend/tests/test_agent_question_validation.py backend/tests/test_account_provider_routes.py -q` | 17 | 0 | 0 |
| Isolated harness: `test_test_environment_repairs.py` + `test_real_provider_catalog_capacity_methods_and_warm_latency` | 3 | 0 | 0 |
| Isolated harness: `test_real_todo_updates_and_explicit_recommendation_continuation` after adding username/email restoration | 1 | 0 | 0 |
| `node tests/browser/test-workspace-ui-unit.cjs` | 11 | 0 | 0 |

Python `compileall backend/app`, changed JS `node --check` and `git diff --check` passed. VM tests do not prove browser layout, responsive behavior or external OAuth. PGlite is disposable compatibility evidence, not native PostgreSQL concurrency acceptance. All fixture emails are intercepted; native model is deterministic loopback. The initial metadata attempt was auto-review-blocked on external catalog refresh; the supported fixture-only disable-fetch flag was verified in installed source and accepted reruns used bundled actual native metadata. No global runtime change or unauthorized external model request was added.

Reproduce with existing tools (no installs):

```bash
python tests/run_isolated_audit.py --pglite-command /path/to/pglite-server --opencode-binary /path/to/opencode --pytest-target backend/tests/test_test_environment_repairs.py --pytest-target backend/tests/test_test_runtime_acceptance.py
node tests/browser/test-workspace-ui-unit.cjs
```

The native acceptance module supplies `OPENCODE_DISABLE_MODELS_FETCH=true` only to test processes. `AUDIT_PROVIDER_PERF=/absolute/test/report.json` optionally saves sanitized metrics. Existing unrelated successful suites were reused, not rerun.

## Measured performance (local isolated test, not TEST VPS)

Actual OpenCode 1.18.32 reports **223 providers**; initial account response **50**; each additional page up to **50**, without duplicate provider IDs. DeepSeek, Google, OpenAI and Together AI were found by actual native IDs.

| Measurement | Actual |
|---|---:|
| Cold account catalog, including process initialization | 3547.21 ms |
| Warm account catalog | 15.61 / 26.09 / 16.69 ms |
| Native health-ready | 2020.29 ms |
| Native `/provider` | 1478.83 ms |
| Native `/provider/auth` | 6.07 ms |
| Warm DeepSeek / Google method dialog API | 14.32 / 16.66 ms |
| Warm OpenAI / Together AI method dialog API | 15.79 / 13.90 ms |

Both warm local targets were met; cold cost and TEST network/frontend latency are separate. The read-only `window.gatewayProviderTimings` browser object exposes last request and synchronous option-DOM-render costs for TEST inspection without credentials or telemetry. Actual frontend time remains unmeasured until authenticated TEST deployment/acceptance. The native `/provider` response inherently includes model metadata; frontend index pages omit those model schemas, and there is no eager per-provider model request loop.

## TEST deployment and infrastructure blockers

- Approved existing workflow: `.github/workflows/deploy-updates-test.yml`, branch `updates`, confirmation `promote-test`, staging environment gate. The current file backs up code and TEST PostgreSQL (and validates dump) before additive update, migrations and TEST-only restart. It remains unchanged.
- Workflow-asserted configuration: DB `opencode_gateway_test`; Gateway `127.0.0.1:8001`; OpenCode `127.0.0.1:4097`; roots `/var/lib/opencode-workspaces-test` and `/var/lib/opencode-runtime-test`. Historical successful run `38725480375` does not certify their current state or this repair. Its older workflow version must not be rerun because it predates the no-delete fix.
- New dispatch cannot be initiated by the available GitHub connector; cloud GitHub is signed out and no CLI SSH/GitHub authentication is available. A new authorized dispatch is required; do not substitute an old rerun or modify workflows.
- Public TEST page rendered in the cloud browser over HTTPS. Shell health request timed out at proxy; direct cloud health-URL navigation was blocked by client policy. Neither proves site failure. Authenticated TEST APIs and existing customer flows remain unverified.
- Dynamic Preview needs an accepted isolated runner/engine and controlled dependency preparation, resource quotas, authenticated separate-origin proxy, runtime logs/lease/cleanup and tenant acceptance. No host execution fallback; installing Docker alone is not completion. TEST runner availability has not been inspected.
- No new TEST backup/deploy or server change is claimed in this report. After authorized deployment, verify actual browser login/restoration, Todo, choices, providers/method timing, RTL/LTR/theme/mobile and account isolation. External payment/email and production remain excluded.

**The owner defines completion by demonstration on TEST. This round is not complete until those gates pass.**


**Published repair source:** `38e3fcf2d03ab52a2a1626cdbe11dc39d69817f1` (parent `d7ddb59311a65a3416e4402fb4b4c2707a3c99cd`). This documentation follow-up records the immutable source SHA; TEST dispatch/acceptance remains pending as described above.
