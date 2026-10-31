"""Encrypted, data-driven payment provider drafts created by Gateway admins.

No vendor API dispatch, payment creation, webhook, checkout, or automatic
subscription activation is performed by these profiles. Existing payment
methods and processor credentials are intentionally independent.
"""
import json
import re

from fastapi import HTTPException
from sqlalchemy import inspect, text

from . import credentials

MAX_FIELDS = 30
MAX_PROFILES = 50


def schema_ready(db):
    return inspect(db.connection()).has_table("payment_provider_profiles")


def _require_ready(db):
    if not schema_ready(db):
        raise HTTPException(503, "Payment provider profiles migration 0033 is not applied")
    if not credentials.available():
        raise HTTPException(503, "Encrypted credential storage must be configured")


def _decode(token):
    try:
        data = json.loads(credentials.decrypt(token))
        if not isinstance(data, list) or len(data) > MAX_FIELDS:
            raise ValueError("Malformed profile")
        if any(not isinstance(field, dict) or not isinstance(field.get("key"), str)
               or not isinstance(field.get("value"), str) for field in data):
            raise ValueError("Malformed profile fields")
        return data
    except Exception:
        # Never return a token, secret, or decrypted data as an error response.
        raise HTTPException(503, "Cannot decrypt provider profile with current encryption key") from None


def _public(row):
    fields = _decode(row["encrypted_fields"])
    return {
        "slug": row["slug"], "label": row["label"],
        "category": row["category"], "connection_mode": row["connection_mode"],
        "environment": row["environment"],
        "fields": [{
            "key": item["key"], "label": item["label"],
            "kind": item["kind"], "required": bool(item["required"]),
            "configured": bool(item["value"]),
            # Admin may inspect nonsecret bank/display values. Secret credentials
            # never leave the backend, even through this admin-only endpoint.
            "value": "" if item["kind"] == "secret" else item["value"]
        } for item in fields],
        "configured": bool(fields) and all(
            bool(item["value"]) for item in fields if item["required"]
        ),
        "status": "saved_unverified",
        "checkout_enabled": False, "webhook_enabled": False,
        "payouts_enabled": False,
        "message": "Configuration only; no automatic charge or connection test.",
        "updated_at": str(row["updated_at"]) if row.get("updated_at") else None,
    }


def _one(db, slug, *, lock=False):
    suffix = " FOR UPDATE" if lock and db.bind.dialect.name == "postgresql" else ""
    row = db.execute(text(
        "SELECT slug,label,category,connection_mode,environment,"
        "encrypted_fields,updated_at FROM payment_provider_profiles "
        "WHERE slug=:slug" + suffix
    ), {"slug": slug}).mappings().first()
    return dict(row) if row else None


def list_profiles(db):
    _require_ready(db)
    rows = db.execute(text(
        "SELECT slug,label,category,connection_mode,environment,"
        "encrypted_fields,updated_at FROM payment_provider_profiles ORDER BY label,slug"
    )).mappings()
    return [_public(dict(row)) for row in rows]


def _prepare_fields(fields, previous):
    old_by_key = {item["key"]: item for item in previous}
    seen = set()
    result = []
    if not fields or len(fields) > MAX_FIELDS:
        raise HTTPException(422, "Choose between 1 and 30 configuration fields")
    for item in fields:
        key = item.key
        # Never collect online banking authentication or transient MFA data in a
        # merchant configuration form. Generic merchant secrets must stay masked.
        if re.search(r"(?:^|_)(?:otp|2fa|mfa|cvv|cvc|pin|card_number|card_pan|bank_password|bank_login)(?:_|$)",key):
            raise HTTPException(422, "Do not store bank login, cards, PIN or one-time authentication codes")
        if (key.endswith(("_key", "_secret", "_token")) or key in
                {"secret", "security_code", "api_token", "access_token"}) and key not in {
                "publishable_key", "public_key"} and item.kind != "secret":
            raise HTTPException(422, "Mark confidential merchant credentials as Secret")
        if key in seen:
            raise HTTPException(422, "Duplicate field key: " + key)
        seen.add(key)
        old = old_by_key.get(key, {})
        if (old.get("kind") == "secret" and old.get("value")
                and item.kind != "secret"):
            raise HTTPException(409, "Clear the saved secret before changing its field type")
        if item.kind == "secret":
            if item.clear:
                value = ""
            else:
                value = item.value if item.value else (
                    old.get("value", "") if old.get("kind") == "secret" else ""
                )
        else:
            if item.clear:
                raise HTTPException(422, "Clear is only available for secret fields")
            value = item.value or ""
        result.append({
            "key": key, "label": item.label, "kind": item.kind,
            "required": item.required, "value": value,
        })
    return result


def save_profile(db, actor_id, data, *, create):
    _require_ready(db)
    row = _one(db, data.slug, lock=True)
    if create and row is not None:
        raise HTTPException(409, "Provider code already exists")
    if not create and row is None:
        raise HTTPException(404, "Provider profile not found")
    if create:
        count = db.execute(text("SELECT COUNT(*) FROM payment_provider_profiles")).scalar_one()
        if count >= MAX_PROFILES:
            raise HTTPException(409, "Maximum provider profile count reached")
    previous = _decode(row["encrypted_fields"]) if row else []
    fields = _prepare_fields(data.fields, previous)
    token = credentials.encrypt(json.dumps(fields, ensure_ascii=False))
    params = {
        "slug": data.slug, "label": data.label, "category": data.category,
        "connection_mode": data.connection_mode, "environment": data.environment,
        "encrypted_fields": token, "actor": actor_id
    }
    if create:
        db.execute(text(
            "INSERT INTO payment_provider_profiles "
            "(slug,label,category,connection_mode,environment,encrypted_fields,updated_by) "
            "VALUES (:slug,:label,:category,:connection_mode,:environment,:encrypted_fields,:actor)"
        ), params)
    else:
        db.execute(text(
            "UPDATE payment_provider_profiles SET label=:label,category=:category,"
            "connection_mode=:connection_mode,environment=:environment,"
            "encrypted_fields=:encrypted_fields,updated_by=:actor,updated_at=CURRENT_TIMESTAMP "
            "WHERE slug=:slug"
        ), params)
    db.commit()
    return _public(_one(db, data.slug))


def delete_profile(db, slug):
    _require_ready(db)
    if _one(db, slug, lock=True) is None:
        raise HTTPException(404, "Provider profile not found")
    # Only this configuration draft is deleted: never delete orders,
    # subscriptions, existing BillingMethods or remote accounts.
    db.execute(text("DELETE FROM payment_provider_profiles WHERE slug=:slug"),
               {"slug": slug})
    db.commit()
    return {"deleted": True, "slug": slug, "payment_orders_changed": False}
