"""TEST: dynamic bank profiles publish only manual or hosted receipt-verified checkout.

Synthetic database and Fernet key; no network, real credentials, payments or LIVE.
"""
import os
from uuid import uuid4,UUID

os.environ.setdefault("DATABASE_URL","postgresql+psycopg://test:test@127.0.0.1/test")

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import create_engine,text
from sqlalchemy.orm import Session

from backend.app.models import BillingMethod
from backend.app.routes.payment_gateways import ProviderField,ProviderProfileDraft
from backend.app.services import payment_provider_profiles as profiles
from backend.app.services import payment_profile_publications as publishing


@pytest.fixture
def db(monkeypatch):
    key=Fernet(Fernet.generate_key())
    monkeypatch.setattr(profiles.credentials,"available",lambda:True)
    monkeypatch.setattr(profiles.credentials,"encrypt",lambda s:key.encrypt(s.encode()).decode())
    monkeypatch.setattr(profiles.credentials,"decrypt",lambda s:key.decrypt(s.encode()).decode())
    engine=create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as c:
        c.execute(text("""CREATE TABLE payment_provider_profiles(
          slug VARCHAR(60) PRIMARY KEY,label VARCHAR(100),category VARCHAR(20),
          connection_mode VARCHAR(20),environment VARCHAR(10),
          encrypted_fields TEXT NOT NULL,updated_by VARCHAR(36),
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""))
        c.execute(text("""CREATE TABLE billing_methods(
          id CHAR(32) PRIMARY KEY,user_id CHAR(32),
          kind VARCHAR(20),label VARCHAR(100),details TEXT NOT NULL,
          enabled BOOLEAN NOT NULL)"""))
        c.execute(text("""CREATE TABLE payment_profile_publications(
          profile_slug VARCHAR(60) PRIMARY KEY,method_id CHAR(32) UNIQUE,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""))
    try:
        with Session(engine) as db:yield db
    finally:engine.dispose()


def profile(mode="manual",with_account=True):
    fields=[]
    if with_account:
        fields=[
          ProviderField(key="bank_name",label="Bank",value="Genuine test-bank name"),
          ProviderField(key="account_name",label="Recipient",value="TEST Beneficiary"),
          ProviderField(key="account_number",label="Account",value="TEST-ACCOUNT-123"),
        ]
    if mode=="hosted":
        fields=[ProviderField(key="payment_url",label="Hosted payment",kind="url",
             value="https://payments.exampleprovider.com/secure")]
    if mode=="api":
        fields=[ProviderField(key="client_secret",label="API credential",kind="secret",
             value="synthetic-private-credential")]
    return ProviderProfileDraft(
      slug="custom_bank",label="Example Bank",category="bank",
      connection_mode=mode,environment="test",fields=fields)


def test_real_manual_receipt_checkout_publishes_without_api_or_secrets(db):
    actor=uuid4()
    profiles.save_profile(db,actor,profile(),create=True)
    assert profiles.list_profiles(db)[0]["publication"]["published"] is False
    published=publishing.publish(db,"custom_bank",actor,currency="USD",
        instructions="Send an actual transfer and upload a receipt for review.")
    assert published["published"] is True
    assert published["automatic_capture"] is False
    method=db.get(BillingMethod,UUID(published["method_id"]))
    assert method.kind=="bank" and method.user_id is None and method.enabled is True
    from backend.app.services.billing_methods import method_payload
    body=method_payload(method)["details"]
    assert body["account_reference"]=="TEST-ACCOUNT-123"
    assert body["account_name"]=="TEST Beneficiary"
    assert body["checkout_mode"]=="manual"
    assert body["instructions"]
    assert "client_secret" not in str(body)
    assert profiles.list_profiles(db)[0]["publication"]["published"] is True
    publishing.unpublish(db,"custom_bank")
    assert db.get(BillingMethod,method.id).enabled is False
    assert publishing.publication_status(db,"custom_bank")["published"] is False


def test_draft_changes_disable_public_payment_until_admin_republishes(db):
    actor=uuid4()
    base=profile()
    profiles.save_profile(db,actor,base,create=True)
    first=publishing.publish(db,"custom_bank",actor,currency="USD",
        instructions="Make a transfer and upload the receipt before activation.")
    original=first["method_id"]
    replacement=base.model_copy(update={"label":"Updated bank name"})
    profiles.save_profile(db,actor,replacement,create=False)
    assert db.get(BillingMethod,UUID(original)).enabled is False
    refreshed=publishing.publish(db,"custom_bank",actor,currency="USD",
        instructions="Use updated details, then upload real payment receipt.")
    assert refreshed["method_id"]==original
    assert db.get(BillingMethod,UUID(original)).label=="Updated bank name"
    profiles.delete_profile(db,"custom_bank")
    assert db.get(BillingMethod,UUID(original)) is not None
    assert db.get(BillingMethod,UUID(original)).enabled is False


def test_api_drafts_cannot_impersonate_verified_payment_provider(db):
    actor=uuid4()
    profiles.save_profile(db,actor,profile(mode="api"),create=True)
    with pytest.raises(HTTPException) as exc:
        publishing.publish(db,"custom_bank",actor,currency="USD",
            instructions="API credentials must not grant payment credits.")
    assert exc.value.status_code==409
    assert db.execute(text("SELECT count(*) FROM billing_methods")).scalar_one()==0


def test_incomplete_manual_bank_and_fake_receiving_details_never_publish(db):
    actor=uuid4()
    profiles.save_profile(db,actor,ProviderProfileDraft(slug="custom_bank",label="Example Bank",category="bank",connection_mode="manual",environment="test",fields=[ProviderField(key="bank_name",label="Bank",value="EXAMPLE_REPLACE")]),create=True)
    with pytest.raises(HTTPException) as exc:
        publishing.publish(db,"custom_bank",actor,currency="USD",
            instructions="Send amount to this missing account and submit receipt.")
    assert exc.value.status_code==422
    assert db.execute(text("SELECT count(*) FROM billing_methods")).scalar_one()==0
