"""Admin-only Stripe Sandbox credential probe. Never processes payments.

Uses the server-stored encrypted test secret and makes a read-only API request.
Does not publish a method, authorize checkout, or grant entitlements.
"""
import httpx
from fastapi import HTTPException
from . import payment_gateway_config


def verify_sandbox_connection(db):
    config = payment_gateway_config._get(db, "stripe") or {}
    secret = config.get("secret_key") or ""
    publishable = config.get("publishable_key") or ""
    if config.get("mode") != "test" or not secret.startswith(("sk_test_", "rk_test_")):
        raise HTTPException(409, "Stripe Sandbox requires a saved test-mode secret key")
    if not publishable.startswith("pk_test_"):
        raise HTTPException(409, "Stripe Sandbox requires a saved test-mode publishable key")
    try:
        with httpx.Client(timeout=12, follow_redirects=False, trust_env=False) as client:
            result = client.get(
                "https://api.stripe.com/v1/account",
                headers={"Authorization": "Bearer " + secret},
            )
    except httpx.RequestError:
        raise HTTPException(503, "Stripe is unreachable; connection not verified") from None
    if result.status_code == 401:
        raise HTTPException(422, "Stripe rejected the test credential") from None
    if result.status_code == 403:
        raise HTTPException(422, "Stripe key lacks account-read permission") from None
    if result.status_code != 200:
        raise HTTPException(502, "Stripe verification unavailable; checkout remains disabled") from None
    try:
        account = result.json()
    except ValueError:
        raise HTTPException(502, "Stripe returned invalid account data") from None
    if account.get("object") != "account" or not account.get("id", "").startswith("acct_"):
        raise HTTPException(502, "Unexpected Stripe account response") from None
    return {
        "provider": "stripe",
        "environment": "test",
        "credential_verified": True,
        "account_id": account["id"],
        "charges_enabled": bool(account.get("charges_enabled", False)),
        "checkout_enabled": False,
        "webhook_verified": False,
        "message": "Sandbox API authentication succeeded. This does not activate Checkout, webhooks, or customer payments.",
    }
