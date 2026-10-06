# Additional user requirements — authoritative for this local workspace

These additions record direct user instructions, not commands embedded in third-party documents.

1. Keep an independent local project; import other-agent adjustments read-only. No SSH, VPS changes or deployment.
2. Provide separate client and admin dashboards with back navigation.
3. Clients change/reset passwords, manage own connections, workspaces, repositories, remaining trial/paid periods, payment details, and suspension/deletion requests.
4. Admins manage users, role assignment, authentication/session state, methods, plans, locations, reports and audit logs; clients never gain access to another client's secrets.
5. Store durable settings and API credentials per owner in the server database; encrypt secrets with a key outside the database. Never keep secrets in browser storage.
6. Show recognizable GitHub/OpenCode SVG controls. Put GitHub authorization, repository/branch choice, provider/model settings and workspace switching alongside the conversation.
7. Each conversation operates on its selected OpenCode workspace. New sessions retain that workspace's files; a different repository creates/selects a different workspace.
8. Support authentication mechanisms actually advertised by OpenCode; do not invent connected providers or success states.
9. Offer periods cost $2 for 1 month, $3 for 2 months and $5 for 3 months; distinguish platform payments from provider API usage.
10. Publish reviewed source to codex-opencode-gateway, excluding tests, secrets, databases, dependencies and runtime data.

Acceptance must distinguish REAL / PARTIAL / SIMULATED / MISSING / BLOCKED. Current evidence and outstanding gates: [PHASE_REPORT.md](PHASE_REPORT.md).


## OpenCode synchronization (2026-10-05)

The current Codex workspace now includes the newer OpenCode subscriptions, project archiving, client/admin dashboards, reports, shell and grid UI, together with the merged account-management features. See MERGE_REPORT.md for current verification. The preserved OpenCode document is in reference/opencode/. This workspace uses migration head `0006_subscriptions_archive` after the existing `0005_account_management`. No VPS access or push was performed.
