"""Settings-only tests: no real processor calls, secrets, or payment activation."""
import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.routes.payment_gateways import StripeSettingsDraft, CryptomusSettingsDraft, router
from backend.app.services import payment_gateway_config as config


@pytest.fixture
def db(monkeypatch):
    from cryptography.fernet import Fernet
    private_fernet = Fernet(Fernet.generate_key())
    monkeypatch.setattr(config.credentials, "available", lambda: True)
    monkeypatch.setattr(config.credentials, "encrypt",
                        lambda s: private_fernet.encrypt(s.encode()).decode())
    monkeypatch.setattr(config.credentials, "decrypt",
                        lambda s: private_fernet.decrypt(s.encode()).decode())
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE payment_gateway_settings (
                provider VARCHAR(24) PRIMARY KEY,
                encrypted_data TEXT NOT NULL,
                updated_by CHAR(36),
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def test_stripe_draft_encrypts_and_does_not_expose_secrets(db):
    data = {
        "mode": "test",
        "publishable_key": "pk_test_example_public",
        "secret_key": "sk_test_private_credential",
        "webhook_secret": "whsec_hidden_webhook",
    }
    result = config.save(db, "stripe", uuid.uuid4(), data, origin="https://test.example.invalid")
    assert result["ready_to_integrate"] is True
    assert result["checkout_enabled"] is False
    assert result["webhook_enabled"] is False
    assert result["payouts_enabled"] is False
    serialized = str(result)
    assert data["secret_key"] not in serialized
    assert data["webhook_secret"] not in serialized
    raw = db.execute(text("SELECT encrypted_data FROM payment_gateway_settings")).scalar_one()
    assert data["secret_key"] not in raw
    assert data["webhook_secret"] not in raw
    updated = config.save(db, "stripe", uuid.uuid4(),
                          {"mode": "test", "secret_key": "", "webhook_secret": ""},
                          origin="https://test.example.invalid")
    assert updated["secret_key_configured"]
    assert updated["webhook_secret_configured"]
    assert config._get(db, "stripe")["secret_key"] == data["secret_key"]


def test_cryptomus_is_independent_and_payouts_never_enabled(db):
    config.save(db, "stripe", uuid.uuid4(), {"mode": "test"},
                origin="https://test.example.invalid")
    merchant = str(uuid.uuid4())
    result = config.save(db, "cryptomus", uuid.uuid4(), {
        "merchant_id": merchant, "payment_api_key": "mock_private_payment",
        "payout_api_key": "mock_private_payout",
    }, origin="https://test.example.invalid")
    assert result["ready_to_integrate"] is True
    assert result["payouts_enabled"] is False
    assert result["payment_api_key_configured"] is True
    assert result["payout_api_key_configured"] is True
    assert "mock_private" not in str(result)
    assert config._get(db, "stripe")["mode"] == "test"


def test_no_gateway_activation_routes_exist():
    urls = {(m, route.path) for route in router.routes for m in route.methods}
    assert ("GET", "/api/admin/payment-gateways") in urls
    assert ("PUT", "/api/admin/payment-gateways/stripe") in urls
    assert ("PUT", "/api/admin/payment-gateways/cryptomus") in urls
    assert not any("/checkout" in path or "/webhook" in path or "/payout" in path
                   for _, path in urls)


def test_payload_validation_rejects_extra_fields_and_invalid_merchant():
    with pytest.raises(ValidationError):
        StripeSettingsDraft(mode="production")
    with pytest.raises(ValidationError):
        StripeSettingsDraft(mode="test", enable_checkout=True)
    with pytest.raises(ValidationError):
        CryptomusSettingsDraft(merchant_id="not-an-id")
    with pytest.raises(ValidationError):
        CryptomusSettingsDraft(merchant_id=uuid.uuid4(), enable_payouts=True)


def test_absent_schema_does_not_silently_store_secrets(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with Session(engine) as session:
        with pytest.raises(HTTPException) as exc:
            config.save(session, "stripe", uuid.uuid4(), {"secret_key": "dummy"},
                        origin="https://example.invalid")
        assert exc.value.status_code == 503
    engine.dispose()
