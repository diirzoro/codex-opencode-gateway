# Product boundaries and development rules

This document records the product direction confirmed by the owner on 2026-10-06. It is the current source of truth when older notes describe a different product split.

## What the customer sees

The customer uses the Gateway's own branded, polished workspace interface. The Gateway must not show or expose the OpenCode interface, its login screen, internal URL, port, server credentials, or runtime configuration. Customers sign in to the Gateway and use Gateway pages and `/api/...` endpoints.

The experience should feel like a complete professional coding product, not a dashboard that embeds or redirects to OpenCode. Workspace, project, provider/model setup, chat, sessions, files, review, and related work controls belong in the Gateway UI.

Provider setup stays deliberately simple: show one provider dropdown and an API-key input for the selected provider. Do not render a long provider/agent inventory or disconnected-provider CRUD table. After the selected provider accepts the credential, show its available models and OpenCode agents as compact choices in the workspace composer; agents are discovered from OpenCode and are not separately created or managed by Gateway.

## Ownership and responsibilities

- **Gateway SaaS and control panel:** owns customer/admin authentication, roles, trial and subscription entitlements, billing and payment configuration, audit/reporting, and platform policy.
- **OpenCode:** is the coding engine and source of operational truth for its projects, workspaces, sessions, LLM providers/models, provider authorization, agents, and coding/runtime behavior.
- **Gateway workspace UI/API:** presents those OpenCode capabilities in the Gateway product, applies Gateway identity/ownership/entitlement checks, and communicates with OpenCode only from the backend. It must not create a parallel provider catalog, custom agent system, or competing coding engine.
- **GitHub:** remains the customer's code source of truth and is accessed with that customer's authorization. Tokens stay server-side.

Gateway may keep the minimum mapping and SaaS ownership metadata needed to associate an OpenCode project/workspace/session with a Gateway account and enforce access. This metadata does not turn Gateway into a competing source of truth for OpenCode operational settings or code.

## Integration and isolation boundary

The browser talks only to Gateway APIs. Gateway authenticates the user, enforces role and current entitlement, verifies ownership, then calls the internal OpenCode API. No direct browser-to-OpenCode calls, iframe, redirect, or exposed runtime URL is allowed.

OpenCode's project directory, provider credential storage, and runtime state must be reachable by the backend runtime that performs work. Do not claim the live server is connected just because a health check succeeds. A shared OpenCode process/configuration must not mix customer credentials, sessions, or filesystem access. If safe account/workspace isolation cannot be provided by the available OpenCode deployment, report that blocker instead of silently routing customers through shared state.

The OpenCode URL is backend-only configuration. The VPS localhost address is distinct from a developer machine's localhost. Do not contact or alter the VPS, establish tunnels, change service settings, or deploy unless the owner explicitly requests it.

`OPENCODE_BASE_URL` is used for health diagnostics only. The production example enables `OPENCODE_RUNTIME_MODE=local`, which uses Gateway-managed per-workspace OpenCode processes rather than the shared 4096 process. Those processes are not a complete multi-customer sandbox. Do not describe customer execution as live-connected until the binary, provider credentials, workspace storage, and the required isolation are configured and accepted on the target host.

## Development environment rule

**Do not create test environments.** Do not create a separate test server, test database, test workspace/runtime, demo deployment, or parallel project copy. Work in the existing canonical local project and use its configured application environment. Do not seed fake customers, fake provider connections, fake payment successes, or simulated OpenCode responses as if they were real.

When a real external credential, account, tunnel, or server-side prerequisite is unavailable, leave a clear configuration step or report the blocker. Never substitute a test environment or fabricated success. Preserve existing local user data and settings.

## Change review checklist

Before changing workspace/provider/project behavior, verify that:

1. The customer-facing control stays in the Gateway's own UI.
2. Operational data/choices are obtained from OpenCode rather than a duplicate Gateway catalog.
3. Every request passes Gateway authentication, entitlement, and ownership checks.
4. Internal URLs and credentials remain backend-only.
5. No shared process or workspace can leak another customer's files, provider credentials, or sessions.
6. No test environment, demo data, or second project copy is created.
