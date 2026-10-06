# Payment implementation and acceptance — 2026-10-06

The checkout is a compact centered popup: real plan choices, stored plan price/duration, selectable configured methods, next step, account identity and non-refundable subscription notice. No invented taxes, logos for unavailable methods, local card/CVV form, or fake successful payment.

## Active app configuration status — 2026-10-06

The working PostgreSQL database currently has no billing-method rows or payment orders, and the local environment has no PayPal client ID/secret. Checkout backend paths exist, but no customer can make a real payment until the owner configures a real receiving method or eligible PayPal Sandbox/Live credentials. The supplied PayPal email is the owner account email; it is not sufficient to create a merchant API charge flow or invent a PayPal.Me/hosted checkout URL. The UI must keep methods unavailable until valid details are saved. The earlier acceptance results below describe implementation/contract verification and isolated preview state, not an active merchant connection.

## Administration and client separation

Admin can add/edit/delete/disable platform receiving methods. Client only selects and pays; platform mutation endpoints reject client access. Receiver details are encrypted in the database. Bank shortcuts include Al-Qutaibi and Al-Kuraimi without inventing account numbers or banking APIs. The supplied PayPal email was saved only in the isolated local preview database; it is not a merchant API credential.

Modes:
- `manual`: bank/wallet/PayPal transfer instructions → customer receipt reference → admin verifies actual receipt → subscription activation.
- `link`: admin supplies public HTTPS hosted payment URL bound to an active plan/currency → customer opens the provider page → receipt/reference review. Visiting a link or returning from it cannot activate a subscription.
- `paypal`: backend PayPal Orders v2 → customer approval on PayPal-hosted checkout → owned backend capture → verified completed payment → subscription activation. Backend checks provider order ID, completed order/capture, custom order ID, merchant ID, amount and currency. Repeated capture is idempotent; approval alone, declined payment, mismatch and unconfigured merchant cannot unlock access.

PayPal guest card availability is decided by PayPal/account/region; the app cannot promise it for every customer. A linked card/bank used for purchases does not independently prove merchant receiving/withdrawal eligibility. Bank settlements are outside this Gateway's control.

## Endpoints and migration

- Existing CRUD `/api/billing/methods?platform=true`: new `checkout_mode` (manual/link/paypal), `payment_url`, optional `plan_id` in encrypted JSON details.
- POST `/api/billing/checkout`: returns manual instructions, static payment_url, or PayPal approval_url after actual server-side order creation. Price comes from stored plan/order, never client input.
- POST `/api/billing/orders/{id}/paypal/capture`: owned order only; activates after complete server verification. API orders cannot be manually confirmed or submit fake references.
- GET `/api/billing/paypal/status`: safe configured/environment flags only.
- Migration `0008_paypal_checkout`: provider order/capture IDs and environment, unique provider identity indexes. Earlier uncommitted phases include 0006 subscriptions/archive and 0007 payment orders.

## Setup and no-money rejection test

Set backend environment only: PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, PAYPAL_MERCHANT_ID, PAYPAL_ENVIRONMENT=sandbox and correct PUBLIC_BASE_URL. Never paste secrets into chat, frontend or Git. Restart backend after settings change. Admin adds a PayPal method with `checkout_mode=paypal`.

For a PayPal-sandbox-issued decline response, set PAYPAL_SANDBOX_DECLINE=true, approve a sandbox order with a sandbox buyer, then Confirm PayPal payment. The capture sends PayPal's documented PayPal-Mock-Response header requesting INSTRUMENT_DECLINED. This is a forced sandbox rejection, not proof of insufficient funds in a real bank account. The UI must show decline and retain inactive entitlement. Never use real money for this test. Negative testing is rejected in live configuration. Set the flag false for sandbox success testing.

For production, replace sandbox credentials with eligible live merchant credentials, PAYPAL_ENVIRONMENT=live, PAYPAL_SANDBOX_DECLINE=false, correct HTTPS PUBLIC_BASE_URL, run migrations and complete live readiness review. No deployment was performed.

## Honest status

- REAL locally: admin/customer separation, saved receiving settings, order persistence, manual receipt review and entitlement activation, plan-bound secure links, honest unconfigured-provider error.
- PARTIAL: PayPal REST implementation tested using HTTP contract doubles. Actual create/capture calls are implemented; no merchant credentials were provided, so no live or Sandbox financial transaction has been verified.
- BLOCKED: provider acceptance until the user configures merchant credentials. The user explicitly chose to add them later.
- MISSING: signed webhook reconciliation, automatic reconciliation for customers who never return, automated bank receipt verification, refunds/dispute reconciliation, production processor acceptance. Customers can explicitly confirm/reconcile an existing PayPal order on return through the order list.
- SIMULATED product payments: none. HTTP doubles and test receiving data are test evidence only.

Official references: [PayPal Orders v2](https://developer.paypal.com/api/orders/v2), [Sandbox negative testing](https://developer.paypal.com/negative-testing/request-headers), [Hosted payment links](https://developer.paypal.com/payment-links-buttons/overview), [Guest checkout](https://www.paypal.com/c2/cshelp/article/how-do-i-accept-cards-with-checkout-using-the-guest-checkout-option--help307?locale.x=en_C2).

## Google Pay, Binance and editable setup guidance

Admin methods now include Google Pay and Binance. Google Pay requires a real processor-hosted HTTPS payment URL, matched plan/currency; it is disabled in the preview until configured. No direct Google Pay API or processing gateway is claimed. Binance has the supplied receiving email in the isolated preview only and uses manual receipt verification; Binance Pay API credentials/webhooks remain missing.

The admin popup has examples as placeholders and contextual instructions for every checkout mode. Examples are never seeded as enabled fictitious receiver accounts/URLs. Recipient name, reference, currency, network and instructions can be edited by admin. PayPal merchant secrets remain backend environment configuration; the UI explains variable names and restart/testing steps without revealing secret values.

Admin has ready-to-edit disabled presets for PayPal, Google Pay, Binance, Al-Qutaibi and Al-Kuraimi. Example URLs/account values cannot be enabled until replaced; disabled methods are not offered to customers. No real receiver wallet was invented. Sandbox completed captures outside TESTING mode are recorded as sandbox_paid and cannot grant a real subscription.

## Final local verification

Follow-up: user requested enabled methods before supplying provider settings. A platform hosted-link method may be enabled with an empty link so it appears as a selectable payment option. Checkout returns an honest 503 configuration error before creating an order or charging when link/plan are missing. Example receiver values and example URLs still cannot be enabled. Enabled means listed, not a verified processor connection. The local preview Google Pay method is now enabled in hosted-link mode with no fabricated URL.

95 backend tests passed; one paid-provider test was skipped. Four payment browser scenarios passed across sequential runs (receiving-method permissions/manual activation, hosted link checkout, honest missing PayPal configuration, and editable disabled presets). The broader headed Chromium run passed 14 cases with one real-provider automation case skipped; real provider chat/Stop was verified separately as recorded in REAL_AGENT_ACCEPTANCE.md. Fresh local Alembic migration chain through 0008 applied successfully on SQLite; production PostgreSQL upgrade remains unverified. JavaScript syntax and Git whitespace checks passed.

Success/decline/mismatched amount/mismatched merchant/cross-user/idempotence/non-test sandbox entitlement checks use explicit PayPal HTTP contract doubles, not actual financial transactions. No empty or invented card number was charged. Actual merchant Sandbox acceptance remains blocked on the settings the user will supply later.
