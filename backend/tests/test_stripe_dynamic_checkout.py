"""Regression coverage for one Stripe TEST/LIVE billing path, without network."""
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models import AccountAudit, PaymentOrder, Plan, Subscription, User
from app.services import stripe_checkout


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = User(username="stripe-customer", email="stripe@example.test",
                    password_hash="unused", phone="", postal_code="",
                    role="customer", status="active")
        plan = Plan(code="stripe_gateway_test", name="Stripe Gateway",
                    price_cents=1250, currency="USD", duration_days=30)
        session.add_all([user, plan])
        session.commit()
        yield session, user, plan
    engine.dispose()


def _event(order, *, mode="live", amount=None, paid=True):
    session_id = order.provider_order_id
    return {
        "id": "evt_live_one", "type": "checkout.session.completed",
        "livemode": mode == "live",
        "data": {"object": {
            "object": "checkout.session", "id": session_id,
            "livemode": mode == "live",
            "mode": "payment", "payment_status": "paid" if paid else "unpaid",
            "currency": "usd", "amount_total": amount if amount is not None else order.amount_cents,
            "payment_intent": "pi_live_abc123",
            "metadata": {"environment": mode, "user_id": str(order.user_id),
                         "plan_id": str(order.plan_id), "order_id": str(order.id)}
        }}
    }


def _sign(raw, secret, timestamp=None):
    timestamp = timestamp or int(time.time())
    signature = hmac.new(secret.encode(), str(timestamp).encode() + b"." + raw,
                         hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def test_live_checkout_uses_saved_mode_and_server_amount(db, monkeypatch):
    session, user, plan = db
    monkeypatch.setattr(stripe_checkout, "_environment", lambda _: (
        {"environment": "live"}, {"secret_key": "rk_live_example", "webhook_secret": "whsec_live"}))
    monkeypatch.setattr(stripe_checkout, "status", lambda _: {"checkout_available": True})
    called = {}
    def fake_call(key, method, path, *, data=None, idempotency_key=None):
        called.update({"key": key, "data": data, "idempotency_key": idempotency_key})
        return {"id": "cs_live_Abcd1234", "url": "https://checkout.stripe.com/test"}
    monkeypatch.setattr(stripe_checkout, "_call", fake_call)
    result = stripe_checkout.create_checkout(session, user, plan.id, "https://opencode-gateway.codes")
    order = session.scalar(select(PaymentOrder).where(PaymentOrder.user_id == user.id))
    assert called["key"].startswith("rk_live_")
    assert called["data"]["line_items[0][price_data][unit_amount]"] == str(plan.price_cents)
    assert called["data"]["managed_payments[enabled]"] == "false"
    assert called["idempotency_key"] == "gateway-stripe-" + str(order.id)
    assert result["environment"] == "live" and order.status == "awaiting_payment"
    assert not session.scalar(select(Subscription).where(Subscription.user_id == user.id))


def test_valid_webhook_activates_once_and_rejects_tampering(db, monkeypatch):
    session, user, plan = db
    order = PaymentOrder(user_id=user.id, plan_id=plan.id, method_label="Stripe",
                         plan_name=plan.name, amount_cents=plan.price_cents,
                         currency="USD", duration_days=30,
                         status="awaiting_payment", provider_environment="live",
                         provider_order_id="cs_live_Abcd1234")
    session.add(order)
    session.commit()
    monkeypatch.setattr(stripe_checkout.profiles, "stripe_fields_for_environment",
                        lambda db, mode: [{"key": "webhook_secret",
                                           "value": "whsec_live" if mode == "live" else "whsec_test"}])
    raw = json.dumps(_event(order)).encode()
    with pytest.raises(HTTPException) as err:
        stripe_checkout.webhook(session, raw, "t=0,v1=bad")
    assert err.value.status_code == 400
    bad = json.dumps(_event(order, amount=plan.price_cents + 1)).encode()
    with pytest.raises(HTTPException) as err:
        stripe_checkout.webhook(session, bad, _sign(bad, "whsec_live"))
    assert err.value.status_code == 400
    assert order.status == "awaiting_payment"
    signed = _sign(raw, "whsec_live")
    assert stripe_checkout.webhook(session, raw, signed)["received"]
    assert order.status == "paid"
    first_end = session.scalar(select(Subscription).where(Subscription.user_id == user.id)).current_period_end
    assert stripe_checkout.webhook(session, raw, signed)["duplicate"]
    assert session.scalar(select(Subscription).where(Subscription.user_id == user.id)).current_period_end == first_end
    assert sum(1 for row in session.scalars(select(AccountAudit)) if row.action == "billing.payment_confirmed") == 1


def test_test_event_never_creates_entitlement(db, monkeypatch):
    session, user, plan = db
    monkeypatch.setattr(stripe_checkout.profiles, "stripe_fields_for_environment",
                        lambda db, mode: [{"key": "webhook_secret",
                                           "value": "whsec_live" if mode == "live" else "whsec_test"}])
    order = PaymentOrder(user_id=user.id, plan_id=plan.id, method_label="Stripe",
                         plan_name=plan.name, amount_cents=plan.price_cents,
                         currency="USD", duration_days=30,
                         provider_environment="test", provider_order_id="cs_test_Abcd1234")
    raw = json.dumps(_event(order, mode="test")).encode()
    result = stripe_checkout.webhook(session, raw, _sign(raw, "whsec_test"))
    assert result["test_only"] is True
    assert session.scalar(select(Subscription).where(Subscription.user_id == user.id)) is None
