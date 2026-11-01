"""Isolated admin Stripe test checkout diagnostic. Never activates subscriptions."""
import re
from urllib.parse import urlsplit
import httpx
from fastapi import HTTPException
from . import payment_gateway_config

def test_credentials(db):
    """Resolve saved dynamic Stripe test profile first; fall back to legacy settings."""
    from . import payment_provider_profiles as profiles
    if profiles.schema_ready(db):
        row = profiles._one(db, "stripe")
        if row is not None and row.get("connection_mode") == "api" and row.get("environment") == "test":
            fields = {item["key"]: item["value"] for item in profiles._decode(row["encrypted_fields"])}
            return {"mode": "test", "secret_key": fields.get("secret_key", ""),
                    "publishable_key": fields.get("publishable_key", "")}
    return payment_gateway_config._get(db, "stripe") or {}


def _stripe_call(db, method, path, data=None):
    config = test_credentials(db)
    secret = config.get("secret_key") or ""
    if config.get("mode") != "test" or not secret.startswith("sk_test_"):
        raise HTTPException(409, "Stripe test checkout requires an sk_test_ secret")
    try:
        with httpx.Client(timeout=18, follow_redirects=False, trust_env=False) as client:
            reply = client.request(
                method, "https://api.stripe.com/v1/" + path,
                headers={"Authorization": "Bearer " + secret},
                data=data,
            )
    except httpx.RequestError:
        raise HTTPException(503, "Could not reach Stripe")
    try:
        payload = reply.json()
    except ValueError:
        raise HTTPException(502, "Stripe returned an unreadable response")
    if reply.status_code >= 400:
        error = payload.get("error") or {}
        # Stripe public diagnostic codes only: no request body, keys or private messages.
        code = str(error.get("code") or error.get("type") or "request_rejected")
        code = code if re.fullmatch(r"[a-z_]{1,100}", code) else "request_rejected"
        raise HTTPException(422 if reply.status_code < 500 else 502,
                            {"provider": "stripe", "http_status": reply.status_code,
                             "provider_code": code, "request_reached_stripe": True})
    return payload

def create_diagnostic_checkout(db, origin, plan_id=None, user_id=None, embedded=False):
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(409, "An HTTPS public base URL is required")
    from ..models import Plan
    from sqlalchemy import select
    plan = db.get(Plan, plan_id) if plan_id is not None else db.scalar(select(Plan).where(Plan.code == "gateway_100", Plan.active.is_(True)))
    if not plan or not plan.active or plan.code in ("monthly", "two_months", "three_months") or plan.price_cents <= 0 or plan.currency.upper() != "USD":
        raise HTTPException(409, "The active gateway_100 USD plan is required for this diagnostic")
    data = {
        "mode": "payment",
        "payment_method_types[0]": "card",
        "line_items[0][price_data][currency]": plan.currency.lower(),
        "line_items[0][price_data][unit_amount]": str(plan.price_cents),
        "line_items[0][price_data][product_data][name]": "OpenCode Gateway test checkout - no entitlement",
        "line_items[0][quantity]": "1",
        **({"ui_mode": "embedded", "return_url": origin.rstrip("/") + "/?stripe_diagnostic=return&session_id={CHECKOUT_SESSION_ID}"} if embedded else {"success_url": origin.rstrip("/") + "/?stripe_diagnostic=return&session_id={CHECKOUT_SESSION_ID}", "cancel_url": origin.rstrip("/") + "/?stripe_diagnostic=cancel"}),
        "metadata[diagnostic]": "true",
        "metadata[user_id]": str(user_id) if user_id else "",
        "metadata[plan_id]": str(plan.id),
    }
    payload = _stripe_call(db, "POST", "checkout/sessions", data)
    session_id = payload.get("id", "")
    url = payload.get("url", "")
    u = urlsplit(url)
    if embedded:
        client_secret = payload.get("client_secret", "")
        publishable_key = test_credentials(db).get("publishable_key", "")
        if (not re.fullmatch(r"cs_test_[A-Za-z0-9_]+", session_id)
                or not isinstance(client_secret, str) or not client_secret.startswith("cs_test_")
                or not publishable_key.startswith("pk_test_")):
            raise HTTPException(502, "Stripe did not return a usable embedded test checkout")
        return {"provider": "stripe", "environment": "test", "session_id": session_id,
                "client_secret": client_secret, "publishable_key": publishable_key,
                "request_reached_stripe": True, "diagnostic": True}
    if not re.fullmatch(r"cs_test_[A-Za-z0-9_]+", session_id) or u.scheme != "https" or u.hostname not in ("checkout.stripe.com", "checkout.stripe.dev"):
        raise HTTPException(502, "Stripe returned an unexpected Checkout session")
    return {"provider": "stripe", "environment": "test", "session_id": session_id,
            "checkout_url": url, "request_reached_stripe": True,
            "message": "Open the hosted test checkout. This diagnostic never activates a subscription."}

def retrieve_diagnostic_checkout(db, session_id, user_id=None):
    if not re.fullmatch(r"cs_test_[A-Za-z0-9_]{1,150}", session_id):
        raise HTTPException(422, "Invalid test session ID")
    payload = _stripe_call(db, "GET", "checkout/sessions/" + session_id)
    if payload.get("id") != session_id or payload.get("metadata", {}).get("diagnostic") != "true":
        raise HTTPException(404, "Not a diagnostic checkout session")
    if user_id is not None and payload.get("metadata", {}).get("user_id") != str(user_id):
        raise HTTPException(404, "Test checkout session not found")
    return {"provider": "stripe", "environment": "test", "request_reached_stripe": True,
            "session_id": session_id, "status": payload.get("status"),
            "payment_status": payload.get("payment_status"),
            "amount_total": payload.get("amount_total"),
            "currency": payload.get("currency"),
            "subscription_activated": False}
