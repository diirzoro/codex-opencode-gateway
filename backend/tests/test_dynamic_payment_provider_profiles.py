"""Admin-defined providers: encrypted CRUD only, no real money movements.

All test data is synthetic, on an isolated SQLite memory DB.
"""
import os
from types import SimpleNamespace as NS
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://fixture:fixture@127.0.0.1/fixture")

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.routes.payment_gateways import ProviderField, ProviderProfileDraft, router
from backend.app.routes.dependencies import require_admin
from backend.app.services import payment_provider_profiles as profiles


@pytest.fixture
def db(monkeypatch):
    private = Fernet(Fernet.generate_key())
    monkeypatch.setattr(profiles.credentials, "available", lambda: True)
    monkeypatch.setattr(profiles.credentials, "encrypt",
                        lambda s: private.encrypt(s.encode()).decode())
    monkeypatch.setattr(profiles.credentials, "decrypt",
                        lambda s: private.decrypt(s.encode()).decode())
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as c:
        c.execute(text("""
            CREATE TABLE payment_provider_profiles (
                slug VARCHAR(60) PRIMARY KEY,
                label VARCHAR(100) NOT NULL,
                category VARCHAR(20) NOT NULL,
                connection_mode VARCHAR(20) NOT NULL,
                environment VARCHAR(10) NOT NULL,
                encrypted_fields TEXT NOT NULL,
                updated_by VARCHAR(36),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        c.execute(text("""
            CREATE TABLE payment_gateway_settings (
                provider VARCHAR(24) PRIMARY KEY,
                encrypted_data TEXT NOT NULL
            )
        """))
        c.execute(text("INSERT INTO payment_gateway_settings(provider,encrypted_data)"
                       " VALUES ('stripe','legacy-preserve-this')"))
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def draft(slug="unlisted_company", merchant="merchant-example", secret="synthetic-private",
          *, field_count=2):
    fields = [
        ProviderField(key="merchant_id", label="Merchant ID", kind="text", value=merchant),
        ProviderField(key="security_key", label="Security key", kind="secret",
                      value=secret, required=True),
    ][:field_count]
    return ProviderProfileDraft(slug=slug,label="Unlisted Custom Company",
                                category="processor",connection_mode="api",
                                environment="test",fields=fields)


def test_arbitrary_provider_added_and_secret_never_returned(db):
    value="synthetic-credential-not-a-real-key"
    saved=profiles.save_profile(db,uuid4(),draft(secret=value),create=True)
    assert saved["slug"]=="unlisted_company"  # Not a pre-defined provider name.
    assert saved["status"]=="saved_unverified"
    assert saved["checkout_enabled"] is False
    assert saved["webhook_enabled"] is False
    assert saved["payouts_enabled"] is False
    assert saved["configured"] is True
    assert saved["fields"][0]["value"]=="merchant-example"
    assert saved["fields"][1]["value"]==""
    assert saved["fields"][1]["configured"] is True
    assert value not in str(saved)
    assert value not in str(profiles.list_profiles(db))
    stored=db.execute(text("SELECT encrypted_fields FROM payment_provider_profiles"
                           " WHERE slug='unlisted_company'")).scalar_one()
    assert value not in stored
    assert "merchant-example" not in stored
    assert db.execute(text("SELECT encrypted_data FROM payment_gateway_settings"
                           " WHERE provider='stripe'")).scalar_one()=="legacy-preserve-this"


def test_edit_label_optional_fields_and_keep_or_clear_secret(db):
    actor=uuid4()
    profiles.save_profile(db,actor,draft(secret="first-secret"),create=True)
    new=ProviderProfileDraft(
        slug="unlisted_company",label="Renamed by administrator",category="bank",
        connection_mode="manual",environment="test",fields=[
            ProviderField(key="merchant_id",label="Merchant account",kind="text",
                          value="another-reference",required=False),
            ProviderField(key="security_key",label="Security key",kind="secret",
                          value="",required=False),
            ProviderField(key="iban",label="Optional IBAN",kind="text",
                          value="",required=False),
        ])
    saved=profiles.save_profile(db,actor,new,create=False)
    assert saved["label"]=="Renamed by administrator"
    assert saved["fields"][1]["configured"] is True
    assert saved["fields"][2]["configured"] is False
    cleared=new.model_copy(update={"fields":[new.fields[0],
        new.fields[1].model_copy(update={"clear":True}),new.fields[2]]})
    after=profiles.save_profile(db,actor,cleared,create=False)
    assert after["fields"][1]["configured"] is False
    assert profiles.delete_profile(db,"unlisted_company")["deleted"] is True
    assert profiles.list_profiles(db)==[]
    assert db.execute(text("SELECT encrypted_data FROM payment_gateway_settings"
                           " WHERE provider='stripe'")).scalar_one()=="legacy-preserve-this"


def test_duplicate_ids_forbidden_and_unavailable_credentials_rejected(db,monkeypatch):
    profiles.save_profile(db,uuid4(),draft(),create=True)
    with pytest.raises(HTTPException) as err:
        profiles.save_profile(db,uuid4(),draft(),create=True)
    assert err.value.status_code==409
    duplicate=draft().model_copy(update={"slug":"another","fields":[
        ProviderField(key="merchant_id",label="One"),
        ProviderField(key="merchant_id",label="Two")
    ]})
    with pytest.raises(HTTPException) as err:
        profiles.save_profile(db,uuid4(),duplicate,create=True)
    assert err.value.status_code==422
    monkeypatch.setattr(profiles.credentials,"available",lambda:False)
    with pytest.raises(HTTPException) as err:
        profiles.list_profiles(db)
    assert err.value.status_code==503


@pytest.mark.parametrize("key,kind",[
    ("security_key","text"),("api_key","text"),("client_secret","text"),
    ("otp","secret"),("cvv","secret"),("bank_password","secret"),
])
def test_sensitive_fields_cannot_be_public_or_store_bank_auth_codes(db,key,kind):
    data=ProviderProfileDraft(slug="new_profile",label="Custom Payment",
         fields=[ProviderField(key=key,label="Sensitive",kind=kind,value="not-a-key")])
    with pytest.raises(HTTPException) as err:
        profiles.save_profile(db,uuid4(),data,create=True)
    assert err.value.status_code==422


def test_profile_validation_admin_only_and_no_payment_capture_routes():
    with pytest.raises(ValidationError):
        ProviderField(key="SECRET:API",label="Wrong")
    with pytest.raises(ValidationError):
        ProviderProfileDraft(slug="bad:code",label="Payment",fields=[
            ProviderField(key="merchant_id",label="Merchant")])
    with pytest.raises(HTTPException) as err:
        require_admin(NS(role="customer"))
    assert err.value.status_code==403
    assert require_admin(NS(role="owner")).role=="owner"
    routes={(route.path,method) for route in router.routes for method in route.methods}
    for method,path in [
        ("GET","/api/admin/payment-gateways/profiles"),
        ("POST","/api/admin/payment-gateways/profiles"),
        ("PUT","/api/admin/payment-gateways/profiles/{slug}"),
        ("DELETE","/api/admin/payment-gateways/profiles/{slug}"),
    ]:assert (path,method) in routes
    assert not any("checkout" in path or "webhook" in path or "capture" in path
                   or "payout" in path for path,_ in routes)
