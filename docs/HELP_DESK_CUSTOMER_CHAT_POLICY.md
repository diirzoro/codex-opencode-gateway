# Help Desk & Customer Support Chat — Agreed Feature and Delivery Plan
Status: APPROVED REQUIREMENT; NOT IMPLEMENTED
Date: 2026-10-16
Repository: diirzoro/codex-opencode-gateway

## Product goal
Help Desk and direct customer chat are mandatory launch features, alongside Smart Preview and reliable payment processing. Support must be reachable from the public site (appropriate pre-login contact), customer account, and Workspace without interrupting coding-agent conversations. Support chat is NOT an OpenCode agent session and must use its own authorization, persistence, and notification flow.

## Customer experience
- Persistent Help / Support entry point from navigation and Workspace, accessible on mobile and desktop.
- Authenticated customers can open a support conversation, send messages, track replies, and view their own history across devices.
- Support form/ticket categories: Account/Login; Connections/Providers; Workspace/Agents; Preview; GitHub; Billing/Payments; Other.
- Customer can create a ticket with subject, description, category, optional safe attachment, status, creation date, and updates. Conversation runs inside the ticket; history is retained when closing/reopening the support panel.
- Customer sees statuses Open, Waiting for Support, Waiting for Customer, Resolved, Closed. Never claim a live human is online unless staffing/presence actually exists.
- Pre-login support: allow safe contact via form/email workflow or authenticated signup support, with spam controls and no exposure of private tickets. Decide whether anonymous real-time chat is necessary later.
- Clearly distinguish support conversation from Coding Agent chat; do not expose agent/API keys, hidden instructions, secrets or private repository files in support.

## Staff experience / permissions
- Role-gated admin/support-agent dashboard with inbox, ticket filters, priority, assignment, messages, status changes and resolution history.
- Enforce server-side ticket/customer ownership and support role; customers cannot read other users' tickets or impersonate staff.
- Support staff may only view what customers explicitly submit, not silently access their private project files or API credentials.
- Notifications: in-app unread count, optional email alerts based on configured email service. No fabricated delivery claims.
- Audit trail for staff actions, assignment and status changes; prohibit customer access to internal notes.

## Architecture & resilience
- Database-backed (PostgreSQL) support tickets, messages, participant/role data, attachments metadata, read receipts/status and audit events; NO demo/static ticket data.
- Separate support APIs and client component from OpenCode session/chat APIs. Keep tenant/user boundary and authentication middleware.
- Start with resilient persisted chat using polling or SSE, with live update if infrastructure supports it; no unnecessary external SaaS/dependency.
- All content untrusted: sanitize rendered text/attachments, enforce type/size limits, validate downloads, malware handling policy, CSRF/origin/cookie protections, rate limit and anti-spam for support forms.
- Maintain independent Test and Live PostgreSQL schemas/configuration and migrations. Never write to Live during development.
- Define ticket retention/deletion/privacy policy before production opening; mask/redact sensitive data in logs.

## Delivery sequence — updates branch only
- [ ] Phase S0: inventory existing auth, roles/admin UI, database migrations, messaging infrastructure and navigation; avoid duplicate systems.
- [ ] Phase S1: schema/migrations and authenticated ticket CRUD, messages and ownership/RBAC tests.
- [ ] Phase S2: embedded customer Support panel, ticket list, threaded messages, unread count; responsive Arabic RTL and English.
- [ ] Phase S3: staff Help Desk inbox and assignment/reply/status workflows with audit and permissions.
- [ ] Phase S4: notifications, secure attachments (if needed), pre-login contact, abuse controls and tests.
- [ ] Phase S5: integration, load/abuse/security tests on Test; explicit review before promotion to master/Live.

## Release constraints
- All feature code changes only on `updates`; Test first. `master` holds this document for shared policy only and must not receive runtime features without explicit approval.
- No edits to GitHub Actions, secrets, production environments, SSH, networking or Live databases as part of writing this policy.
- Do not claim Help Desk or chat is already working until code and end-to-end tests confirm it.
- Update this checklist after each verified implementation milestone. Agents must consult this policy and `docs/SMART_PREVIEW_POLICY.md` before relevant work.
