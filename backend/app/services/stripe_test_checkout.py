"""Isolated admin Stripe test checkout diagnostic. Never activates subscriptions."""
import re
from urllib.parse import urlsplit
import httpx
from fastapi import HTTPException
from . import payment_gateway_config

def _stripe_call(db, method, path, data=None):
    config = payment_gateway_config._get(db, "stripe") or {}
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

def create_diagnostic_checkout(db, origin):
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(409, "An HTTPS public base URL is required")
    from ..models import Plan
    from sqlalchemy import select
    plan = db.scalar(select(Plan).where(Plan.code == "gateway_100", Plan.active.is_(True)))
    if not plan or plan.price_cents <= 0 or plan.currency.upper() != "USD":
        raise HTTPException(409, "The active gateway_100 USD plan is required for this diagnostic")
    data = {
        "mode": "payment",
        "payment_method_types[0]": "card",
        "line_items[0][price_data][currency]": plan.currency.lower(),
        "line_items[0][price_data][unit_amount]": str(plan.price_cents),
        "line_items[0][price_data][product_data][name]": "OpenCode Gateway test checkout - no entitlement",
        "line_items[0][quantity]": "1",
        "success_url": origin.rstrip("/") + "/?stripe_diagnostic=return&session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": origin.rstrip("/") + "/?stripe_diagnostic=cancel",
        "metadata[diagnostic]": "true",
    }
    payload = _stripe_call(db, "POST", "checkout/sessions", data)
    session_id = payload.get("id", "")
    url = payload.get("url", "")
    u = urlsplit(url)
    if not re.fullmatch(r"cs_test_[A-Za-z0-9_]+", session_id) or u.scheme != "https" or u.hostname not in ("checkout.stripe.com", "checkout.stripe.dev"):
        raise HTTPException(502, "Stripe returned an unexpected Checkout session")
    return {"provider": "stripe", "environment": "test", "session_id": session_id,
            "checkout_url": url, "request_reached_stripe": True,
            "message": "Open the hosted test checkout. This diagnostic never activates a subscription."}

def retrieve_diagnostic_checkout(db, session_id):
    if not re.fullmatch(r"cs_test_[A-Za-z0-9_]{1,150}", session_id):
        raise HTTPException(422, "Invalid test session ID")
    payload = _stripe_call(db, "GET", "checkout/sessions/" + session_id)
    if payload.get("id") != session_id or payload.get("metadata", {}).get("diagnostic") != "true":
        raise HTTPException(404, "Not a diagnostic checkout session")
    return {"provider": "stripe", "environment": "test", "request_reached_stripe": True,
            "session_id": session_id, "status": payload.get("status"),
            "payment_status": payload.get("payment_status"),
            "amount_total": payload.get("amount_total"),
            "currency": payload.get("currency"),
            "subscription_activated": False}
