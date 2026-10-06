# Sidebar content mapping — 2026-10-05

The fixed App Shell remains unchanged. Client management forms now render directly inside their owning main sidebar panel; Security no longer opens the shared management menu.

| Sidebar | Body content |
|---|---|
| Security | Password change, active sign-ins/revocation, 2FA availability, device availability, password/session security activity |
| Plan & Billing | Subscription/plan selection, payment methods CRUD, invoices/payment-history availability |
| GitHub | Connection and authorization, repository/branch access, GitHub workspace creation |
| OpenCode | Runtime status, owned workspace selection, providers and credentials, model selection guidance, tools/permissions |
| Account / Profile | Personal information, preferences, profile editing, general account activity, suspension/deletion requests |

General audit activity is shown under Account/Profile; recorded password/session/auth/security/role actions are shown under Security. Login-event tracking, device identification and 2FA configuration are not implemented and are explicitly labelled unavailable. No fake functionality or records were added.

Admin Billing, GitHub, Security, Audit and Location Settings likewise render their scoped content within existing admin panels. Role management remains in Users. Workspaces continue to use the existing provider/model/session APIs.

Changed frontend: management.js (scoped renderers and routing), enhancements.js (panel loaders), index.html (removed misplaced profile security block). Backend and database migrations were not changed.

Validation: all **16 headed Chromium browser tests passed**, including explicit isolation checks for each client sidebar body, repeated Security navigation, mobile width, payment CRUD, admin settings, role routing, files/diff/commit and subscription/pricing flows. Existing management/routing tests were updated to follow the main sidebar instead of the removed shared menu.
