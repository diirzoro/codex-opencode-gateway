# OpenCode Gateway

OpenCode Gateway is a branded Arabic/English multi-user project workspace with account, project, billing and GitHub administration. **The installed OpenCode Native service alone** performs AI model/provider discovery, sessions, messages, streaming, tools, permissions, questions, Todos and model-supported attachments. Gateway is the administrative control plane, not a second AI engine.

## Single authoritative project memo

[docs/OPENCODE_GATEWAY_CURRENT_AGREEMENT_AR.md](docs/OPENCODE_GATEWAY_CURRENT_AGREEMENT_AR.md) — the **only active architecture, product and implementation-status memo**. Historical documents were removed from the working tree to prevent conflicting instructions; Git history retains previous versions.

## Environments

- LOCAL (Windows): existing local OpenCode Native, Windows local Gateway; actual local Native chat integration not yet accepted.
- TEST: `updates`, `https://test.opencode-gateway.codes`; work and E2E acceptance in [GitHub Issue #47](https://github.com/diirzoro/codex-opencode-gateway/issues/47).
- LIVE: `master`, `https://opencode-gateway.codes`; production promotion remains separate and explicit.

Build and deployment references under `deployment/`, source-code tests under `tests/`, and evidence under `docs/audit/` and `docs/evidence/` are **not competing architecture policies**. Do not use stale deployment examples to override the current memo.
