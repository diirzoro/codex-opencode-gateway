# Workspace and payment roles update — 2026-10-05

Latest forms correction: see [POPUP_FORMS_REPORT.md](POPUP_FORMS_REPORT.md). Account and administrative create/edit actions now use bounded, centered native dialogs instead of stretched inline editors or browser prompts. Eight headed Chromium cases passed after the final modal changes.

Visual contrast follow-up: light-theme headings, supporting text, prices, placeholders and button labels use dark text. Primary buttons use a pale blue background so dark labels remain readable. Inputs, cards, dialogs and existing separators use visible blue borders; dark-theme borders use a lighter blue. Layout and backend are unchanged. Five headed Chromium payment/navigation cases passed after this update, and the updated checkout screenshot was inspected.

Shell refinement: header and both navigation sidebars now use soft blue/cyan/lavender backgrounds without divider lines or outlined navigation buttons. Active navigation uses a tinted fill. Form/card borders remain blue. All five headed browser cases passed after this refinement; light administrator billing and checkout captures were inspected.

Quiet visual hierarchy refinement: primary actions use a stronger blue fill with readable dark labels, secondary actions use pale surfaces, and inputs have blue focus states and soft fills. Cards have subtle depth, consistent rounded corners and clearer typography. Landing feature cards now have proper internal padding and larger labels; home project/session rows have distinct surfaces. Header/sidebar divider lines remain absent. Five headed browser cases passed for the control/form changes. Final light Landing and Workspace/Home screenshots were captured, and Landing plus administrator billing/checkout were visually inspected. Styling only; no backend changes in this refinement.

Workspace: `D:\opencodde agent\codex project\project`. Local only; no SSH, deployment, commit or push. Existing changes were preserved. This report supersedes older dashboard-first/two-secondary-sidebar requirements where they conflict with the latest user request.

## Delivered behavior

- Customer login/session restore opens Workspace/Home. Admin and owner open Admin Overview. Account remains a separate section.
- Home lists actual owned projects/workspaces and recent sessions, with session search and project actions.
- Composer groups agent, provider, model and GitHub/repository controls. Settings/Connections configures integrations; Workspace uses them. Agents and connected provider/model options are fetched through Gateway APIs, not invented client options.
- One collapsible secondary pane sits opposite main navigation in English and Arabic. Normal account/billing/security pages do not display that workspace pane.
- Header OpenCode wordmark opens Landing without logging out either role.
- Trial lasts ten days. Expired customers cannot use workspace/session APIs or create projects until eligible for subscription access. Billing, account and security remain accessible. UI checks entitlement when entering work and periodically while open.

## Payment roles correction

Administration configures platform receiving accounts: label, type, recipient, bank/account reference, currency, wallet network where appropriate, instructions and enabled status. Bank and wallet fields are conditional. Customer billing does not render the administrative editor or a duplicate personal receiving-account editor.

Customer selects a plan card, sees its server price and duration, chooses an enabled platform method, then receives transfer instructions and submits their own payment reference. They cannot change the recipient, configure the platform method or activate their own subscription. A submitted reference remains pending review. Administrator confirmation records the receipt and activates/extends that customer's subscription atomically. Repeated confirmation does not extend it twice.

**Manual transfer workflow is implemented. Automated card/PayPal processing is not configured.** No card-number/CVV form is displayed without a payment processor, and no raw card data is stored. Local receipt tests are test records, not evidence of money transferred through a bank. Legacy private saved-account API records remain scoped to their owner; they are not selectable platform receiving methods and no longer have an editor in customer checkout.

## Files / migration / APIs

Frontend: `app.js`, `enhancements.js`, `management.js`, `dashboards.js`, `index.html`.

Backend: `routes/dependencies.py`, `routes/workspaces.py`, `routes/agent.py`, `routes/billing.py`, `models/platform.py`, `models/__init__.py` under `backend/app`.

Migration: `backend/alembic/versions/0007_payment_orders.py` creates payment orders with owned customer, plan/price/duration snapshots, method, status and receipt review metadata.

New routes: `GET /api/workspaces/{id}/agents`; `POST /api/billing/checkout`; `GET /api/billing/orders`; `PUT /api/billing/orders/{id}/reference`; administrative order list and confirmation at `/api/billing/admin/orders`. Message submission accepts optional validated `agent_id`; subscription payload includes access entitlement.

## Verification

- Backend phase suite: 65 passed, 1 skipped. Paid model execution was skipped because no real provider credential was supplied. Includes real local OpenCode session/abort testing and isolated agent boundary tests.
- Headed Chromium: five cases passed together: customer home/navigation, English/Arabic opposite sidebar and mobile drawer, admin and owner routing, and payment-role separation. Payment case repeated after compact checkout styling and passed.
- Payment browser case creates a test receiving bank through the administrator form, verifies customers cannot POST/PUT/DELETE platform methods (403), submits a reference through checkout, rejects customer receipt confirmation, confirms via administrator UI and checks the actual customer subscription. Test method removed afterward; history retained in the isolated test database.
- Fresh SQLite Alembic upgrade reaches `0007_payment_orders`. PostgreSQL offline SQL generation passes; no PostgreSQL server migration was executed.
- Captures inspected under `D:\opencodde agent\codex project\.audit\workspace-first-evidence`, including `customer-checkout.png` and `admin-payment-methods.png`.

## Status and limits

| Capability | Status | Limit |
| --- | --- | --- |
| Customer/admin navigation and separated payment forms | REAL | Verified locally |
| Ten-day entitlement and owned manual checkout/orders | REAL | No external bank money transfer performed |
| Admin receipt confirmation linked to subscription | REAL | Human must actually verify receipt |
| Agent selection forwarding | REAL | Runtime choices validated; paid model request not exercised |
| Full paid AI conversation | BLOCKED | Actual provider credential/authorization required |
| Card/CVV or automatic PayPal checkout and webhooks | MISSING | Payment processor integration/configuration required |
| GitHub authorization with a live GitHub App | BLOCKED | Deployment App configuration/authorization required |
| Fake chat/payment success in product | SIMULATED: none | Test fixtures confined to tests |

No production deployment commands were executed. The existing `deployment/README.md` remains the deployment guide; a successful payment-provider deployment cannot be claimed until that provider integration exists.
