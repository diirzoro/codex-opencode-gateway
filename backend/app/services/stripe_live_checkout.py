"""Stripe LIVE Checkout for time-limited Gateway access, using existing tables.

The public browser never receives credentials. Only a verified Stripe API
session or signed Stripe webhook can activate a paid subscription.
One-time payment is deliberate: Gateway does not promise automatic renewals.
"""
import hashlib
import hmac
import json
import re
import time
import uuid
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException
from sqlalchemy import select

from ..models import PaymentOrder, Plan
from . import payment_gateway_config, payment_provider_profiles, credentials

_STRIPE_API = "https://api.stripe.com/v1/"
_SESSION = re.compile(r"^cs_live_[a-zA-Z0-9_]{5,90}$")
_PAID_EVENTS = {"checkout.session.completed", "checkout.session.async_payment_succeeded"}


def _profile(db):
    """Only the admin-maintained dynamic profile may back LIVE charges."""
    if not payment_provider_profiles.schema_ready(db):
        return {}
    row = payment_provider_profiles._one(db, "stripe")
    if not row or row["environment"] != "live" or row["connection_mode"] != "api":
        return {}
    fields = payment_provider_profiles._decode(row["encrypted_fields"])
    return {item["key"]: item["value"] for item in fields}


def _policy(db):
    return payment_gateway_config._get(db, "stripe") or {}


def paypal_visible(db):
    return bool(_policy(db).get("paypal_customer_visible", True))


def _fingerprint(profile):
    values = [profile.get(k, "") for k in ("publishable_key", "secret_key", "webhook_secret")]
    return hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()


def _valid(profile):
    return (
        str(profile.get("publishable_key", "")).startswith("pk_live_")
        and str(profile.get("secret_key", "")).startswith("sk_live_")
        and str(profile.get("webhook_secret", "")).startswith("whsec_")
        and len(str(profile.get("webhook_secret", ""))) >= 12
    )


def live_ready(db):
    profile, policy = _profile(db), _policy(db)
    return bool(
        credentials.available()
        and _valid(profile)
        and policy.get("checkout_enabled") is True
        and hmac.compare_digest(str(policy.get("live_fingerprint") or ""), _fingerprint(profile))
    )


def status(db):
    profile, policy = _profile(db), _policy(db)
    return {
        "environment": "live" if profile else "not_configured",
        "live_keys_configured": _valid(profile),
        "live_checkout_enabled": live_ready(db),
        "paypal_customer_visible": paypal_visible(db),
        "webhook_url": "https://opencode-gateway.codes/api/billing/webhooks/stripe",
        "checkout_requires_verified_payment": True,
        "auto_renew": False,
    }


def _require_config(db, *, enabled=True):
    profile = _profile(db)
    if not _valid(profile):
        raise HTTPException(409, "Configure Stripe LIVE publishable key, secret key and webhook signing secret in Admin")
    if enabled and not live_ready(db):
        raise HTTPException(409, "Stripe LIVE checkout is disabled or credentials changed; activate from Admin")
    return profile


def _call(secret, method, path, data=None, *, idempotency_key=None):
    if not str(secret).startswith("sk_live_"):
        raise HTTPException(503, "Stripe LIVE credential unavailable")
    headers = {"Authorization": "Bearer " + secret}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    try:
        with httpx.Client(timeout=18, follow_redirects=False, trust_env=False) as client:
            response = client.request(method, _STRIPE_API + path, headers=headers, data=data)
    except httpx.RequestError:
        raise HTTPException(503, "Stripe is unreachable; payment not confirmed") from None
    try:
        body = response.json()
    except ValueError:
        raise HTTPException(502, "Unexpected Stripe response") from None
    if response.status_code >= 400:
        # Never echo Stripe's message, request data, credentials or user details.
        raise HTTPException(422 if response.status_code < 500 else 502,
                            "Stripe rejected the request; check LIVE account and permissions")
    if not isinstance(body, dict):
        raise HTTPException(502, "Invalid Stripe response")
    return body


def verify_live_account(db):
    profile = _require_config(db, enabled=False)
    account = _call(profile["secret_key"], "GET", "account")
    if account.get("object") != "account" or not str(account.get("id", "")).startswith("acct_"):
        raise HTTPException(502, "Stripe account verification failed")
    if account.get("charges_enabled") is not True:
        raise HTTPException(409, "Stripe account is not enabled to accept LIVE charges")
    # Do not advertise LIVE charges unless Stripe has an active destination for
    # the exact Gateway production webhook endpoint. The signing secret must
    # still be copied separately from that Stripe endpoint into Admin.
    endpoints = _call(profile["secret_key"], "GET", "webhook_endpoints?limit=100")
    targets = endpoints.get("data", [])
    if not isinstance(targets, list):
        raise HTTPException(502, "Invalid Stripe webhook destination inventory")
    url = "https://opencode-gateway.codes/api/billing/webhooks/stripe"
    def supports_checkout(item):
        events = item.get("enabled_events") or []
        return "*" in events or ("checkout.session.completed" in events and
                                 "checkout.session.async_payment_succeeded" in events)
    if not any(isinstance(item, dict) and item.get("url") == url
               and item.get("status") == "enabled" and supports_checkout(item)
               for item in targets):
        raise HTTPException(409,
            "Register an enabled Stripe LIVE webhook for the published Gateway HTTPS endpoint, "
            "including completed and async-succeeded checkout events, before enabling charges")
    return {"account_verified": True, "charges_enabled": True,
            "webhook_registered": True, "account_id": account["id"]}


def configure(db, actor_id, *, enabled, show_paypal):
    profile = _profile(db)
    previously_enabled = live_ready(db)
    if enabled:
        # Verify the Stripe merchant on first activation. PayPal visibility
        # changes should not unnecessarily revalidate an already-active account.
        if not previously_enabled:
            verify_live_account(db)
        fingerprint = _fingerprint(profile)
    else:
        fingerprint = str(_policy(db).get("live_fingerprint") or "")
    if show_paypal and not paypal_visible(db):
        from . import paypal
        if paypal.admin_config(db)["environment"] != "live":
            raise HTTPException(409, "Only PayPal LIVE merchant credentials may be shown to production customers")
        paypal.verify_connection(db)
    payment_gateway_config.save(
        db, "stripe", actor_id, {
            "checkout_enabled": bool(enabled),
            "paypal_customer_visible": bool(show_paypal),
            "live_fingerprint": fingerprint,
        }, origin="https://opencode-gateway.codes"
    )
    return status(db)


def _validate_stripe_session(payload, row):
    if (payload.get("object") != "checkout.session"
        or payload.get("id") != row.provider_order_id
        or payload.get("livemode") is not True
        or payload.get("mode") != "payment"
        or payload.get("payment_status") != "paid"
        or payload.get("amount_total") != row.amount_cents
        or str(payload.get("currency") or "").upper() != row.currency.upper()
        or payload.get("client_reference_id") != str(row.id)):
        return False
    meta = payload.get("metadata") or {}
    return (
        meta.get("order_id") == str(row.id)
        and meta.get("user_id") == str(row.user_id)
        and meta.get("plan_id") == str(row.plan_id)
        and meta.get("gateway_payment") == "stripe_live"
    )


def reconcile(db, payload):
    """Idempotent, locked receipt reconciliation. No unverified client flags."""
    session_id = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(session_id, str) or not _SESSION.fullmatch(session_id):
        raise HTTPException(422, "Invalid Stripe LIVE session")
    row = db.scalar(select(PaymentOrder).where(
        PaymentOrder.provider_order_id == session_id).with_for_update())
    if not row:
        raise HTTPException(404, "Stripe payment order not found")
    if row.provider_environment != "live" or row.method_label != "Stripe":
        raise HTTPException(409, "Not a Stripe LIVE payment")
    if row.status == "paid":
        return row
    if not _validate_stripe_session(payload, row):
        raise HTTPException(409, "Stripe payment does not match the purchased order")
    payment_intent = payload.get("payment_intent")
    if not isinstance(payment_intent, str) or not re.fullmatch(r"pi_[A-Za-z0-9_]{5,95}", payment_intent):
        raise HTTPException(409, "Stripe paid session lacks a verified payment reference")
    from ..routes.billing import activate_order
    row.provider_capture_id = payment_intent
    activate_order(db, row, None, payment_intent)
    db.commit()
    return row


def start_checkout(db, user, plan_id, *, origin):
    profile = _require_config(db)
    origin_url = urlsplit(origin)
    if origin_url.scheme != "https" or origin_url.hostname != "opencode-gateway.codes":
        raise HTTPException(409, "Stripe LIVE requires the production HTTPS origin")
    plan = db.get(Plan, plan_id)
    if (not plan or not plan.active or plan.code in {"monthly", "two_months", "three_months"}
        or plan.price_cents <= 0 or plan.duration_days <= 0
        or not re.fullmatch(r"[A-Z]{3}", plan.currency)):
        raise HTTPException(422, "Invalid active payment plan")
    row = PaymentOrder(
        user_id=user.id, plan_id=plan.id, method_id=None,
        plan_name=plan.name, method_label="Stripe",
        amount_cents=plan.price_cents, currency=plan.currency,
        duration_days=plan.duration_days, provider_environment="live",
        status="awaiting_payment", payer_name=user.username, payer_email=user.email,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    data = {
        "mode": "payment",
        "payment_method_types[0]": "card",
        "line_items[0][price_data][currency]": plan.currency.lower(),
        "line_items[0][price_data][unit_amount]": str(plan.price_cents),
        "line_items[0][price_data][product_data][name]": "Gateway access - " + plan.name,
        "line_items[0][quantity]": "1",
        "client_reference_id": str(row.id),
        "customer_email": user.email,
        "metadata[order_id]": str(row.id),
        "metadata[user_id]": str(user.id),
        "metadata[plan_id]": str(plan.id),
        "metadata[gateway_payment]": "stripe_live",
        "success_url": origin.rstrip("/") + "/?stripe_live=return&session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": origin.rstrip("/") + "/?stripe_live=cancel",
    }
    checkout = _call(profile["secret_key"], "POST", "checkout/sessions", data,
                     idempotency_key="gateway-live-stripe-" + str(row.id))
    sid, url = checkout.get("id"), checkout.get("url")
    parsed = urlsplit(url) if isinstance(url, str) else None
    if (not isinstance(sid, str) or not _SESSION.fullmatch(sid) or len(sid) > 100
        or not parsed or parsed.scheme != "https"
        or parsed.hostname not in {"checkout.stripe.com", "checkout.stripe.dev"}
        or checkout.get("livemode") is not True):
        raise HTTPException(502, "Unexpected Stripe LIVE Checkout session; payment link not issued")
    row.provider_order_id = sid
    db.commit()
    return {"checkout_url": url, "session_id": sid, "order_id": str(row.id),
            "environment": "live", "subscription_activated": False}


def customer_status(db, user, session_id):
    if not isinstance(session_id, str) or not _SESSION.fullmatch(session_id):
        raise HTTPException(422, "Invalid Stripe LIVE session ID")
    row = db.scalar(select(PaymentOrder).where(
        PaymentOrder.provider_order_id == session_id,
        PaymentOrder.user_id == user.id))
    if not row or row.method_label != "Stripe" or row.provider_environment != "live":
        raise HTTPException(404, "Checkout not found")
    if row.status != "paid":
        profile = _require_config(db, enabled=False)
        checkout = _call(profile["secret_key"], "GET", "checkout/sessions/" + session_id)
        # Reconcile from Stripe's server-to-server verification, never from
        # the customer's redirected URL parameters.
        if checkout.get("payment_status") == "paid":
            row = reconcile(db, checkout)
    return {"order_id": str(row.id), "status": row.status,
            "subscription_activated": row.status == "paid", "environment": "live"}


def _signed_event(raw, signature, secret):
    if len(raw) > 1024 * 1024 or not signature or len(signature) > 4096:
        raise HTTPException(400, "Invalid Stripe webhook")
    params = {}
    for part in signature.split(","):
        key, _, value = part.strip().partition("=")
        params.setdefault(key, []).append(value)
    try:
        stamp = int(params.get("t", [""])[0])
    except ValueError:
        raise HTTPException(400, "Invalid Stripe signature timestamp") from None
    if abs(int(time.time()) - stamp) > 300:
        raise HTTPException(400, "Stale Stripe signature")
    expected = hmac.new(secret.encode(), str(stamp).encode() + b"." + raw,
                        hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in params.get("v1", [])):
        raise HTTPException(400, "Stripe signature verification failed")
    try:
        event = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, "Invalid Stripe event") from None
    if not isinstance(event, dict) or not str(event.get("id", "")).startswith("evt_"):
        raise HTTPException(400, "Invalid Stripe event")
    return event


def process_webhook(db, raw, signature):
    # Continue reconciling pending orders after an admin disables new checkouts.
    profile = _require_config(db, enabled=False)
    event = _signed_event(raw, signature, profile["webhook_secret"])
    if event.get("livemode") is not True:
        raise HTTPException(400, "LIVE webhook received non-live event")
    if event.get("type") not in _PAID_EVENTS:
        return {"received": True}
    payload = (event.get("data") or {}).get("object") or {}
    if payload.get("payment_status") != "paid":
        return {"received": True}
    reconcile(db, payload)
    return {"received": True}
