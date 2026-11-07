"""Encrypted, administrator-only payment provider configuration.

This module does not create payments, verify webhooks, issue refunds or payouts.
Each deployment keeps its own settings encrypted with its existing Gateway key.
"""
import json

from fastapi import HTTPException
from sqlalchemy import inspect, text

from . import credentials

PROVIDERS = ("stripe", "cryptomus")
SECRET_FIELDS = {
    "stripe": ("secret_key", "webhook_secret"),
    "cryptomus": ("payment_api_key", "payout_api_key"),
}
PUBLIC_FIELDS = {
    "stripe": ("mode", "publishable_key"),
    "cryptomus": ("merchant_id",),
}


def schema_ready(db):
    return inspect(db.connection()).has_table("payment_gateway_settings")


def _get(db, provider):
    if provider not in PROVIDERS:
        raise HTTPException(404, "Unknown payment provider")
    if not schema_ready(db):
        return None
    token = db.execute(text(
        "SELECT encrypted_data FROM payment_gateway_settings WHERE provider=:provider"
    ), {"provider": provider}).scalar_one_or_none()
    if token is None:
        return None
    try:
        values = json.loads(credentials.decrypt(token))
        if not isinstance(values, dict):
            raise ValueError("Invalid payment settings")
        return values
    except Exception:
        raise HTTPException(503, "Cannot decrypt payment gateway settings; check the original Gateway encryption key") from None


def public(db, provider, *, origin):
    data = _get(db, provider) or {}
    ready = schema_ready(db) and credentials.available()
    visible = {k: data.get(k) or "" for k in PUBLIC_FIELDS[provider]}
    secrets = {field + "_configured": bool(data.get(field))
               for field in SECRET_FIELDS[provider]}
    # Deliberately not published as an active callback route yet.
    return {
        "provider": provider,
        "settings_schema_ready": schema_ready(db),
        "credential_storage_ready": credentials.available(),
        "configured": bool(data),
        "ready_to_integrate": bool(
            ready and (
                data.get("publishable_key") and data.get("secret_key") and data.get("webhook_secret")
                if provider == "stripe" else data.get("merchant_id") and data.get("payment_api_key")
            )
        ),
        "checkout_enabled": False,
        "payouts_enabled": False,
        "webhook_enabled": False,
        "webhook_url_planned": origin.rstrip("/") + "/api/billing/webhooks/" + provider,
        **visible,
        **secrets,
    }


def save(db, provider, actor_id, data, *, origin):
    if provider not in PROVIDERS:
        raise HTTPException(404, "Unknown payment provider")
    if not schema_ready(db):
        raise HTTPException(503, "Apply payment gateway settings migration 0031")
    if not credentials.available():
        raise HTTPException(503, "Gateway encryption key is required before storing payment credentials")
    existing = _get(db, provider) or {}
    values = dict(existing)
    for field in PUBLIC_FIELDS[provider]:
        if field in data and data[field] is not None:
            values[field] = data[field]
    for field in SECRET_FIELDS[provider]:
        candidate = data.get(field)
        if candidate:  # Blank input preserves the previous encrypted credential.
            values[field] = candidate
    db.execute(text("""
        INSERT INTO payment_gateway_settings(provider, encrypted_data, updated_by)
        VALUES (:provider, :encrypted, :actor)
        ON CONFLICT (provider) DO UPDATE SET
            encrypted_data = excluded.encrypted_data,
            updated_by = excluded.updated_by,
            updated_at = CURRENT_TIMESTAMP
    """), {"provider": provider, "encrypted": credentials.encrypt(json.dumps(values)),
           "actor": actor_id})
    db.commit()
    return public(db, provider, origin=origin)
