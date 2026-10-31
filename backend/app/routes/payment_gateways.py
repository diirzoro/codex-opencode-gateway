"""Admin-only draft configuration for future Stripe and Cryptomus integrations.

No payment/capture/refund/payout/webhook endpoints are enabled here.
"""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import User
from ..services import payment_gateway_config
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
