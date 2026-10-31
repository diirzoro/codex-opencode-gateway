"""Admin-only draft configuration for future Stripe and Cryptomus integrations.

No payment/capture/refund/payout/webhook endpoints are enabled here.
"""
from typing import Literal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import User
from ..services import payment_gateway_config, payment_provider_profiles, payment_profile_publications
from .dependencies import require_admin

router = APIRouter(prefix="/api/admin/payment-gateways", tags=["admin"])


class StripeSettingsDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    mode: Literal["test", "live"] = "test"
    publishable_key: str | None = Field(default=None, max_length=512)
    secret_key: str | None = Field(default=None, max_length=1024)
    webhook_secret: str | None = Field(default=None, max_length=1024)


class CryptomusSettingsDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    merchant_id: UUID | None = None
    payment_api_key: str | None = Field(default=None, max_length=1024)
    payout_api_key: str | None = Field(default=None, max_length=1024)


def _cache_safe(response: Response):
    response.headers["Cache-Control"] = "no-store"


@router.get("")
def list_payment_gateway_settings(
    response: Response, _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _cache_safe(response)
    return {
        "providers": {
            provider: payment_gateway_config.public(
                db, provider, origin=settings.public_base_url
            )
            for provider in payment_gateway_config.PROVIDERS
        },
        "status": "configuration_only",
        "message": "Payment collection, webhook processing and payouts remain disabled.",
    }


@router.put("/stripe")
def save_stripe_settings(
    data: StripeSettingsDraft, response: Response,
    user: User = Depends(require_admin), db: Session = Depends(get_db),
):
    _cache_safe(response)
    values = data.model_dump(exclude_unset=True)
    mode = data.mode
    values["mode"] = mode
    for name, prefix in (
        ("publishable_key", "pk_" + mode + "_"),
        ("secret_key", ("sk_" + mode + "_", "rk_" + mode + "_")),
        ("webhook_secret", "whsec_"),
    ):
        raw = values.get(name)
        if raw and not raw.startswith(prefix):
            raise HTTPException(422, "Stripe key does not match its declared mode or type")
    # The existing non-blank keys must also match after a mode change.
    current = payment_gateway_config._get(db, "stripe") or {}
    for field, kind in (("publishable_key", "pk_"), ("secret_key", None)):
        key = values.get(field) or current.get(field)
        if key and (not key.startswith(kind + mode + "_") if kind else
                    not key.startswith(("sk_" + mode + "_", "rk_" + mode + "_"))):
            raise HTTPException(422, "Existing Stripe keys belong to another mode; replace them before switching modes")
    return payment_gateway_config.save(
        db, "stripe", user.id, values, origin=settings.public_base_url
    )


@router.put("/cryptomus")
def save_cryptomus_settings(
    data: CryptomusSettingsDraft, response: Response,
    user: User = Depends(require_admin), db: Session = Depends(get_db),
):
    _cache_safe(response)
    values = data.model_dump(exclude_unset=True)
    if data.merchant_id is not None:
        values["merchant_id"] = str(data.merchant_id)
    return payment_gateway_config.save(
        db, "cryptomus", user.id, values, origin=settings.public_base_url
    )


# Configurable provider profiles do not replace legacy Stripe/Cryptomus drafts
# or checkout methods. This is an admin-only encrypted configuration catalog.
class ProviderField(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    key: str = Field(min_length=2, max_length=48,
                     pattern=r"^[a-z][a-z0-9_]{1,47}$")
    label: str = Field(min_length=1, max_length=100)
    kind: Literal["text", "secret", "url"] = "text"
    required: bool = False
    value: str = Field(default="", max_length=2048)
    clear: bool = False


class ProviderProfileDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    slug: str = Field(min_length=2, max_length=60,
                      pattern=r"^[a-z][a-z0-9_-]{1,59}$")
    label: str = Field(min_length=2, max_length=100)
    category: Literal["bank", "wallet", "processor", "crypto", "other"] = "other"
    connection_mode: Literal["manual", "hosted", "api"] = "manual"
    environment: Literal["test", "live"] = "test"
    fields: list[ProviderField] = Field(min_length=1, max_length=30)


@router.get("/profiles")
def list_dynamic_payment_profiles(
    response: Response, _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _cache_safe(response)
    return {
        "profiles": payment_provider_profiles.list_profiles(db),
        "status": "configuration_only",
        "notice": "Only administrators see these profiles. No customer checkout or "
                  "automated payment is enabled by saving a profile.",
    }


@router.post("/profiles", status_code=201)
def create_dynamic_payment_profile(
    data: ProviderProfileDraft, response: Response,
    user: User = Depends(require_admin), db: Session = Depends(get_db),
):
    _cache_safe(response)
    return payment_provider_profiles.save_profile(db, user.id, data, create=True)


@router.put("/profiles/{slug}")
def update_dynamic_payment_profile(
    slug: str, data: ProviderProfileDraft, response: Response,
    user: User = Depends(require_admin), db: Session = Depends(get_db),
):
    _cache_safe(response)
    if slug != data.slug:
        raise HTTPException(422, "Provider code cannot be changed after creation")
    return payment_provider_profiles.save_profile(db, user.id, data, create=False)


@router.delete("/profiles/{slug}")
def delete_dynamic_payment_profile(
    slug: str, response: Response,
    _: User = Depends(require_admin), db: Session = Depends(get_db),
):
    _cache_safe(response)
    return payment_provider_profiles.delete_profile(db, slug)


class PublishProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    instructions: str = Field(min_length=10, max_length=1000)
    plan_id: int | None = Field(default=None, ge=1)
    available_country_codes: list[str] = Field(default_factory=list,max_length=100)
    confirmed_receiving_details: Literal[True]


@router.post("/profiles/{slug}/publish")
def publish_profile_for_verified_receipt_checkout(
    slug: str, data: PublishProfileRequest, response: Response,
    user: User = Depends(require_admin), db: Session = Depends(get_db),
):
    _cache_safe(response)
    # Separate explicit action. Never infer publication from credential storage,
    # and never activate a plan without a separately verified receipt.
    return payment_profile_publications.publish(
        db, slug, user.id,
        currency=data.currency,
        instructions=data.instructions,
        plan_id=data.plan_id,
        available_country_codes=data.available_country_codes,
    )


@router.delete("/profiles/{slug}/publish")
def disable_published_profile_for_new_customers(
    slug: str, response: Response, _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _cache_safe(response)
    return payment_profile_publications.unpublish(db,slug)
