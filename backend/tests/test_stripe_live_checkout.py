"""Offline safety tests: no Stripe account, merchant secrets or VPS required."""
import hashlib
import hmac
import json
import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import stripe_live_checkout as stripe


def _signed(secret, event, stamp=None):
    stamp = int(time.time()) if stamp is None else stamp
    raw = json.dumps(event, separators=(",", ":")).encode()
    digest = hmac.new(secret.encode(), str(stamp).encode() + b"." + raw,
                      hashlib.sha256).hexdigest()
    return raw, f"t={stamp},v1={digest}"


def test_signed_stripe_event_is_accepted():
    event = {"id": "evt_dummy_1", "type": "checkout.session.completed",
             "livemode": True}
    raw, header = _signed("whsec_mocktestsecret", event)
    assert stripe._signed_event(raw, header, "whsec_mocktestsecret") == event


@pytest.mark.parametrize("bad", ["missing", "tamper", "old", "large"])
def test_webhook_rejects_untrusted_events(bad):
    event = {"id": "evt_dummy_1", "livemode": True}
    raw, header = _signed("whsec_mocktestsecret", event)
    if bad == "missing":
        header = ""
    elif bad == "tamper":
        raw += b" "
    elif bad == "old":
        raw, header = _signed("whsec_mocktestsecret", event, int(time.time()) - 500)
    elif bad == "large":
        raw = b"x" * (1024 * 1024 + 1)
    with pytest.raises(HTTPException) as exc:
        stripe._signed_event(raw, header, "whsec_mocktestsecret")
    assert exc.value.status_code == 400


def _session():
    order = SimpleNamespace(
        id="order-one", user_id="user-one", plan_id=5,
        provider_order_id="cs_live_abcdefgh123456",
        amount_cents=200, currency="USD")
    data = {
        "object": "checkout.session", "id": order.provider_order_id,
        "livemode": True, "mode": "payment", "payment_status": "paid",
        "amount_total": 200, "currency": "usd", "client_reference_id": "order-one",
        "payment_intent": "pi_123456789abcdef",
        "metadata": {"order_id": "order-one", "user_id": "user-one",
                     "plan_id": "5", "gateway_payment": "stripe_live"},
    }
    return order, data


def test_server_verifies_amount_user_order_currency_and_live_mode():
    row, payload = _session()
    assert stripe._validate_stripe_session(payload, row)
    for field, changed in (("amount_total", 100), ("currency", "eur"),
                           ("livemode", False), ("payment_status", "unpaid"),
                           ("client_reference_id", "other-order")):
        wrong = dict(payload)
        wrong[field] = changed
        assert not stripe._validate_stripe_session(wrong, row)
    for field in ("order_id", "user_id", "plan_id", "gateway_payment"):
        wrong = dict(payload)
        wrong["metadata"] = {**payload["metadata"], field: "someone-else"}
        assert not stripe._validate_stripe_session(wrong, row)


def test_disabled_flag_or_changed_keys_blocks_live_checkout(monkeypatch):
    profile = {"publishable_key": "pk_live_mock", "secret_key": "sk_live_mock",
               "webhook_secret": "whsec_mocktestsecret"}
    state = {"checkout_enabled": True, "live_fingerprint": stripe._fingerprint(profile)}
    monkeypatch.setattr(stripe, "_profile", lambda db: profile)
    monkeypatch.setattr(stripe, "_policy", lambda db: state)
    monkeypatch.setattr(stripe.credentials, "available", lambda: True)
    assert stripe.live_ready(object())
    state["live_fingerprint"] = "old-key-fingerprint"
    assert not stripe.live_ready(object())
    state["live_fingerprint"] = stripe._fingerprint(profile)
    state["checkout_enabled"] = False
    assert not stripe.live_ready(object())


def test_activation_never_calls_stripe_api_when_live_keys_missing(monkeypatch):
    monkeypatch.setattr(stripe, "_profile", lambda db: {})
    with pytest.raises(HTTPException) as error:
        stripe.verify_live_account(object())
    assert error.value.status_code == 409


def test_paypal_hidden_by_encrypted_admin_policy(monkeypatch):
    monkeypatch.setattr(stripe, "_policy", lambda db: {"paypal_customer_visible": False})
    assert stripe.paypal_visible(object()) is False
    monkeypatch.setattr(stripe, "_policy", lambda db: {})
    assert stripe.paypal_visible(object()) is True
