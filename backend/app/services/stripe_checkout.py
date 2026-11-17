"""Unified server-side Stripe Checkout for TEST diagnostics and LIVE orders.

All payment amounts originate from server plans, never the browser. LIVE
entitlements are granted only by a signed paid Checkout webhook or an
authenticated provider reconciliation, never from return URLs.
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

from ..models import AccountAudit, PaymentOrder, Plan, User
from . import payment_provider_profiles as profiles

_SESSION_RE = re.compile(r"^cs_(test|live)_[A-Za-z0-9_]{4,180}$")
_SECRET_RE = re.compile(r"^(?:sk|rk)_(test|live)_[A-Za-z0-9_]+$")
_HOSTS = {"checkout.stripe.com", "checkout.stripe.dev"}


def _values(fields):
    return {field["key"]: field["value"] for field in fields}


def _environment(db, mode=None):
    row = profiles._one(db, "stripe")
    if not row or row["connection_mode"] != "api" or row.get("admin_suspended"):
        return None, None
    mode = mode or row["environment"]
    if mode not in ("test", "live"):
        return None, None
    fields = profiles.stripe_fields_for_environment(db, mode)
    if not fields:
        return row, None
    return row, _values(fields)


def status(db):
    row, cfg = _environment(db)
    mode = row["environment"] if row else "not_configured"
    key = (cfg or {}).get("secret_key", "")
    hook = (cfg or {}).get("webhook_secret", "")
    valid = bool(_SECRET_RE.fullmatch(key) and key.split("_")[1] == mode)
    # Require signed server confirmation for real payments; TEST is diagnostic.
    ready = bool(valid and (mode == "test" or hook.startswith("whsec_")))
    return {
        "provider": "stripe", "environment": mode,
        "enabled": bool(row and not row.get("admin_suspended")),
        "configured": bool(row),
        "checkout_available": ready,
        "test_checkout_available": ready and mode == "test",
        "live_checkout_available": ready and mode == "live",
        "webhook_configured": bool(hook.startswith("whsec_")),
    }


def _call(key, method, path, *, data=None, idempotency_key=None):
    headers = {"Authorization": "Bearer " + key}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    try:
        with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
            result = client.request(method, "https://api.stripe.com/v1/" + path,
                                    data=data, headers=headers)
    except httpx.RequestError:
        raise HTTPException(503, "Stripe is temporarily unreachable") from None
    try:
        payload = result.json()
    except ValueError:
        raise HTTPException(502, "Stripe returned an invalid response") from None
    if result.status_code >= 400:
        error = payload.get("error", {})
        code = str(error.get("code") or error.get("type") or "")
        if not re.fullmatch(r"[a-z_]{1,80}", code):
            code = "provider_rejected"
        raise HTTPException(422 if result.status_code < 500 else 502,
                            "Stripe could not create checkout (" + code + ")")
    return payload


def create_checkout(db, user, plan_id, origin):
    row, cfg = _environment(db)
    ready = status(db)
    if not ready["checkout_available"] or not cfg:
        raise HTTPException(409, "Stripe Checkout is not enabled for the selected environment")
    mode = row["environment"]
    if user.status != "active":
        raise HTTPException(403, "Account is not active")
    plan = db.get(Plan, plan_id)
    if not plan or not plan.active or plan.price_cents <= 0 or plan.duration_days <= 0:
        raise HTTPException(422, "Unavailable paid subscription plan")
    if plan.currency != "USD":
        raise HTTPException(422, "Stripe checkout currently supports USD plans only")
    origin_url = urlsplit(origin)
    if origin_url.scheme != "https" or not origin_url.hostname or origin_url.username or origin_url.password:
        raise HTTPException(503, "A public HTTPS checkout origin is required")
    order = None
    if mode == "live":
        # A stable order ID is also the Stripe idempotency key. Pending/failed
        # Stripe requests may be retried without a second charge session.
        db.scalar(select(User).where(User.id == user.id).with_for_update())
        previous = db.scalar(select(PaymentOrder).where(
            PaymentOrder.user_id == user.id,
            PaymentOrder.plan_id == plan.id,
            PaymentOrder.provider_environment == "live",
            PaymentOrder.status == "awaiting_payment",
            PaymentOrder.provider_order_id.like("cs_live_%")).order_by(
            PaymentOrder.created_at.desc()).with_for_update())
        if previous:
            # Reuse the same unfinished Stripe session to prevent accidentally
            # opening multiple payable sessions for the same plan.
            existing = _call(cfg["secret_key"], "GET",
                             "checkout/sessions/" + previous.provider_order_id)
            if (existing.get("id") == previous.provider_order_id and
                existing.get("status") == "open" and
                existing.get("amount_total") == previous.amount_cents and
                previous.amount_cents == plan.price_cents):
                url = existing.get("url", "")
                parsed = urlsplit(url)
                if parsed.scheme == "https" and parsed.hostname in _HOSTS:
                    db.commit()
                    return {"provider": "stripe", "environment": mode,
                            "checkout_url": url, "session_id": previous.provider_order_id,
                            "order_id": str(previous.id), "test_only": False}
            if existing.get("status") == "complete" and existing.get("payment_status") == "paid":
                raise HTTPException(409, "Stripe payment is awaiting signed webhook confirmation")
            # An expired/unpaid provider session cannot later capture money.
            if existing.get("status") == "expired":
                previous.status = "failed"
                db.flush()
            else:
                raise HTTPException(409, "Existing Stripe checkout needs reconciliation")
        order = db.scalar(select(PaymentOrder).where(
            PaymentOrder.user_id == user.id,
            PaymentOrder.plan_id == plan.id,
            PaymentOrder.provider_environment == "live",
            PaymentOrder.status == "awaiting_payment",
            PaymentOrder.provider_order_id.is_(None)).order_by(
            PaymentOrder.created_at.desc()).with_for_update())
        if order and (order.amount_cents != plan.price_cents or order.currency != plan.currency):
            order.status = "cancelled"
            db.flush()
            order = None
        if order is None:
            order = PaymentOrder(user_id=user.id, plan_id=plan.id,
                                 method_id=None, plan_name=plan.name,
                                 method_label="Stripe", amount_cents=plan.price_cents,
                                 currency=plan.currency, duration_days=plan.duration_days,
                                 provider_environment="live", status="awaiting_payment",
                                 payer_email=user.email, payer_name=user.username)
            db.add(order)
            db.flush()
        db.commit()
    checkout_data = {
        "mode": "payment",
        "line_items[0][price_data][currency]": plan.currency.lower(),
        "line_items[0][price_data][unit_amount]": str(plan.price_cents),
        "line_items[0][price_data][product_data][name]": plan.name[:120],
        "line_items[0][quantity]": "1",
        "success_url": origin.rstrip("/") + "/?stripe_return=success&session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": origin.rstrip("/") + "/?stripe_return=cancel",
        "metadata[environment]": mode,
        "metadata[user_id]": str(user.id),
        "metadata[plan_id]": str(plan.id),
        "metadata[order_id]": str(order.id) if order else "",
    }
    if mode == "test":
        checkout_data["metadata[diagnostic]"] = "true"
        # Preserve the original Stripe TEST diagnostic configuration.
        checkout_data["managed_payments[enabled]"] = "false"
    try:
        payload = _call(cfg["secret_key"], "POST", "checkout/sessions",
                        data=checkout_data,
                        idempotency_key=("gateway-stripe-" + str(order.id)) if order else None)
    except HTTPException as exc:
        # A definitive Stripe 4xx rejection created no payable session.
        # Keep ambiguous network/5xx outcomes pending for safe reconciliation.
        if order is not None and exc.status_code == 422:
            db.scalar(select(PaymentOrder).where(
                PaymentOrder.id == order.id).with_for_update()).status = "failed"
            db.commit()
        raise
    sid, url = payload.get("id", ""), payload.get("url", "")
    target = urlsplit(url)
    if not _SESSION_RE.fullmatch(sid) or not sid.startswith("cs_" + mode + "_"):
        raise HTTPException(502, "Unexpected Stripe Checkout session identifier")
    if target.scheme != "https" or target.hostname not in _HOSTS or target.username or target.password:
        raise HTTPException(502, "Unexpected Stripe Checkout URL")
    if order:
        locked = db.scalar(select(PaymentOrder).where(
            PaymentOrder.id == order.id).with_for_update())
        if locked.provider_order_id and locked.provider_order_id != sid:
            raise HTTPException(409, "Checkout session changed; retry safely")
        locked.provider_order_id = sid
        db.commit()
    return {"provider": "stripe", "environment": mode, "checkout_url": url,
            "session_id": sid, "order_id": str(order.id) if order else None,
            "test_only": mode == "test"}


def _verify_signature(raw, signature_header, secret):
    parts = {}
    for entry in signature_header.split(","):
        k, _, v = entry.partition("=")
        if k in ("t", "v1"):
            parts.setdefault(k, []).append(v)
    try:
        stamp = int(parts["t"][0])
    except (KeyError, ValueError, IndexError):
        return False
    if abs(time.time() - stamp) > 300:
        return False
    signed = str(stamp).encode() + b"." + raw
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, value) for value in parts.get("v1", []))


def webhook(db, raw, signature):
    if len(raw) > 65536:
        raise HTTPException(413, "Webhook is too large")
    # Retain credentials for earlier transactions when admin switches mode.
    matched_mode = None
    for mode in ("live", "test"):
        fields = profiles.stripe_fields_for_environment(db, mode)
        secret = _values(fields).get("webhook_secret", "") if fields else ""
        if secret.startswith("whsec_") and _verify_signature(raw, signature, secret):
            matched_mode = mode
            break
    if not matched_mode:
        raise HTTPException(400, "Stripe webhook signature invalid")
    try:
        event = json.loads(raw)
    except ValueError:
        raise HTTPException(400, "Invalid Stripe webhook payload") from None
    if not isinstance(event, dict):
        raise HTTPException(400, "Invalid Stripe webhook event")
    if event.get("livemode") is not (matched_mode == "live"):
        raise HTTPException(400, "Stripe event environment mismatch")
    if event.get("type") not in (
        "checkout.session.completed", "checkout.session.async_payment_succeeded"
    ):
        return {"received": True}
    checkout = (event.get("data") or {}).get("object") or {}
    if checkout.get("object") != "checkout.session" or checkout.get("payment_status") != "paid":
        return {"received": True}
    if checkout.get("livemode") is not (matched_mode == "live"):
        raise HTTPException(400, "Stripe session environment mismatch")
    metadata = checkout.get("metadata") or {}
    sid = str(checkout.get("id") or "")
    if not _SESSION_RE.fullmatch(sid) or not sid.startswith("cs_" + matched_mode + "_"):
        raise HTTPException(400, "Invalid Stripe session mode")
    if matched_mode == "test":
        return {"received": True, "test_only": True}
    try:
        order_id = uuid.UUID(metadata.get("order_id") or "")
    except (ValueError, TypeError):
        raise HTTPException(400, "Unknown Stripe payment order") from None
    order = db.scalar(select(PaymentOrder).where(PaymentOrder.id == order_id).with_for_update())
    if not order or order.provider_environment != "live" or order.provider_order_id != sid:
        raise HTTPException(400, "Stripe order not recognized")
    if (metadata.get("environment") != "live" or
        metadata.get("user_id") != str(order.user_id) or
        metadata.get("plan_id") != str(order.plan_id) or
        checkout.get("mode") != "payment" or
        checkout.get("currency") != order.currency.lower() or
        checkout.get("amount_total") != order.amount_cents):
        raise HTTPException(400, "Stripe payment does not match the order")
    if order.status == "paid":
        return {"received": True, "duplicate": True}
    if order.status in ("cancelled", "rejected", "failed"):
        # Paid after local cancellation: preserve payment for reconciliation;
        # do not silently grant previously withdrawn entitlements.
        db.add(AccountAudit(actor_id=None, subject_id=order.user_id,
                            action="billing.stripe_paid_after_cancellation"))
        db.commit()
        return {"received": True, "requires_review": True}
    from ..routes.billing import activate_order
    intent = str(checkout.get("payment_intent") or sid)
    if len(intent) > 100:
        raise HTTPException(400, "Invalid Stripe payment identifier")
    order.provider_capture_id = intent
    order.payment_reference = sid
    activate_order(db, order, None, sid)
    db.commit()
    return {"received": True}
