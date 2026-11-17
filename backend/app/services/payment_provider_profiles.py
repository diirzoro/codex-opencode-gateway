"""Encrypted, data-driven payment provider drafts created by Gateway admins.

No vendor API dispatch, payment creation, webhook, checkout, or automatic
subscription activation is performed by these profiles. Existing payment
methods and processor credentials are intentionally independent.
"""
import json
import re
import hashlib

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


def _profile_fingerprint(row):
    # Includes encrypted credentials and connection identity; changes invalidate
    # previous verification even when secrets are not displayed in the UI.
    identity = "\\0".join((row["slug"], row["connection_mode"], row["environment"], row["encrypted_fields"]))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _public(row):
    fields = _decode(row["encrypted_fields"])
    verified = bool(row.get("verification_fingerprint") and
                    row["verification_fingerprint"] == _profile_fingerprint(row) and
                    row["slug"] == "stripe" and row["connection_mode"] == "api")
    return {
        "slug": row["slug"], "label": row["label"],
        "category": row["category"], "connection_mode": row["connection_mode"],
        "environment": row["environment"],
        "admin_suspended": bool(row.get('admin_suspended')),
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
        "status": "api_verified" if verified else "saved_unverified",
        "api_verified": verified,
        "verified_at": str(row["verified_at"]) if verified and row.get("verified_at") else None,
        "verified_account_id": row.get("verified_account_id") if verified else None,
        "checkout_enabled": False, "webhook_enabled": False,
        "payouts_enabled": False,
        "message": "Configuration only; no automatic charge or connection test.",
        "updated_at": str(row["updated_at"]) if row.get("updated_at") else None,
    }


def _one(db, slug, *, lock=False):
    suffix = " FOR UPDATE" if lock and db.bind.dialect.name == "postgresql" else ""
    row = db.execute(text(
        "SELECT slug,label,category,connection_mode,environment,"
        "encrypted_fields,updated_at,admin_suspended,verification_fingerprint,verified_at,verified_account_id FROM payment_provider_profiles "
        "WHERE slug=:slug" + suffix
    ), {"slug": slug}).mappings().first()
    return dict(row) if row else None


def list_profiles(db):
    _require_ready(db)
    rows = db.execute(text(
        "SELECT slug,label,category,connection_mode,environment,"
        "encrypted_fields,updated_at,admin_suspended,verification_fingerprint,verified_at,verified_account_id FROM payment_provider_profiles ORDER BY label,slug"
    )).mappings()
    from . import payment_profile_publications
    result=[]
    for row in rows:
        item=_public(dict(row))
        item["publication"]=payment_profile_publications.publication_status(db,item["slug"])
        result.append(item)
    return result


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


def stripe_fields_for_environment(db, environment):
    """Return environment-scoped merchant fields (never exposed through API)."""
    if environment not in ("test", "live"):
        raise HTTPException(422, "Invalid Stripe environment")
    if inspect(db.connection()).has_table("stripe_environment_credentials"):
        saved = db.execute(text(
            "SELECT encrypted_fields FROM stripe_environment_credentials "
            "WHERE environment=:environment"
        ), {"environment": environment}).scalar_one_or_none()
        if saved is not None:
            return _decode(saved)
    row = _one(db, "stripe")
    if row and row["environment"] == environment:
        return _decode(row["encrypted_fields"])
    return []


def _save_stripe_environment(db, environment, fields):
    db.execute(text(
        "INSERT INTO stripe_environment_credentials (environment, encrypted_fields) "
        "VALUES (:environment,:fields) "
        "ON CONFLICT (environment) DO UPDATE SET encrypted_fields=excluded.encrypted_fields,"
        "updated_at=CURRENT_TIMESTAMP"
    ), {"environment": environment,
        "fields": credentials.encrypt(json.dumps(fields, ensure_ascii=False))})


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
    if data.slug == "stripe":
        if not inspect(db.connection()).has_table("stripe_environment_credentials"):
            raise HTTPException(503, "Stripe environment migration 0041 must be applied")
        if row and row["environment"] != data.environment:
            # Save the old mode before switching. Blank secrets in the new mode
            # retain only that mode's own credentials, never the other mode's.
            if not stripe_fields_for_environment(db, row["environment"]):
                _save_stripe_environment(db, row["environment"], previous)
            previous = stripe_fields_for_environment(db, data.environment)
    fields = _prepare_fields(data.fields, previous)
    if data.slug == "stripe":
        _save_stripe_environment(db, data.environment, fields)
    token = credentials.encrypt(json.dumps(fields, ensure_ascii=False))
    params = {
        "slug": data.slug, "label": data.label, "category": data.category,
        "connection_mode": data.connection_mode, "environment": data.environment,
        "encrypted_fields": token, "actor": actor_id
    }
    if not create:
        # Updating a merchant/bank profile must immediately disable any
        # previously published receiving method until an admin republishes.
        from . import payment_profile_publications
        payment_profile_publications.disable_on_edit(db,data.slug)
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
            "encrypted_fields=:encrypted_fields,updated_by=:actor,updated_at=CURRENT_TIMESTAMP,verification_fingerprint=NULL,verified_at=NULL,verified_account_id=NULL "
            "WHERE slug=:slug"
        ), params)
    db.commit()
    return _public(_one(db, data.slug))


def set_suspended(db, slug, suspended, actor_id):
    _require_ready(db)
    if _one(db, slug, lock=True) is None:
        raise HTTPException(404, 'Provider profile not found')
    from . import payment_profile_publications
    from ..models import AccountAudit
    if suspended:
        payment_profile_publications.disable_on_edit(db, slug)
    db.execute(text('UPDATE payment_provider_profiles SET admin_suspended=:suspended, updated_by=:actor, updated_at=CURRENT_TIMESTAMP WHERE slug=:slug'),
               {'suspended': suspended, 'actor': actor_id, 'slug': slug})
    db.add(AccountAudit(actor_id=actor_id, action='billing.provider_suspended' if suspended else 'billing.provider_resumed'))
    db.commit()
    return _public(_one(db, slug))


def delete_profile(db, slug):
    _require_ready(db)
    if _one(db, slug, lock=True) is None:
        raise HTTPException(404, "Provider profile not found")
    # Disable the linked public method but preserve it for historical orders.
    from . import payment_profile_publications
    payment_profile_publications.forget_profile(db,slug)
    db.execute(text("DELETE FROM payment_provider_profiles WHERE slug=:slug"),
               {"slug": slug})
    db.commit()
    return {"deleted": True, "slug": slug, "payment_orders_changed": False}



def check_provider_connection(db, slug):
    """Read-only admin check; never publishes a method or activates payments."""
    import httpx

    _require_ready(db)
    row = _one(db, slug)
    if row is None:
        raise HTTPException(404, "Payment method not found")
    fields = _decode(row["encrypted_fields"])
    required_missing = [f["label"] for f in fields if f.get("required") and not f.get("value")]
    if required_missing:
        return {"result": "incomplete", "verified": False,
                "message": "Required configuration fields are missing.",
                "missing_fields": required_missing}

    if row["connection_mode"] != "api":
        # A completed form does not prove that a bank account belongs to the
        # merchant or that an actual transfer will reach it.
        return {"result": "manual_review_required", "verified": False,
                "message": "Saved details are complete. Independently confirm the bank or wallet account ownership and receiving details before enabling customer payments."}

    if slug != "stripe":
        return {"result": "unsupported", "verified": False,
                "message": "No safe provider API verification is implemented for this payment service."}

    values = {field["key"]: field["value"] for field in fields}
    secret = values.get("secret_key", "")
    publishable = values.get("publishable_key", "")
    mode = row["environment"]
    expected = "live" if mode == "live" else "test"
    # Stripe supports both standard server secrets (sk_) and least-privilege
    # restricted server keys (rk_). Environment must still match exactly.
    allowed_prefixes = ("sk_" + expected + "_", "rk_" + expected + "_")
    if (not secret.startswith(allowed_prefixes) or
        (publishable and not publishable.startswith("pk_" + expected + "_"))):
        return {"result": "invalid_configuration", "verified": False,
                "message": "Stripe API key or publishable key does not match the selected TEST/LIVE environment."}
    try:
        with httpx.Client(timeout=12, follow_redirects=False, trust_env=False) as client:
            response = client.get("https://api.stripe.com/v1/account",
                                  headers={"Authorization": "Bearer " + secret})
    except httpx.RequestError:
        raise HTTPException(503, "Stripe API is unreachable; no verification performed") from None
    if response.status_code == 401:
        return {"result": "rejected", "verified": False,
                "message": "Stripe rejected the saved API credential. Check its value and environment."}
    if response.status_code == 403:
        return {"result": "insufficient_permissions", "verified": False,
                "message": "Stripe key accepted for its mode but lacks permission for this account-read verification. Grant the minimum necessary read permission in Stripe; no payment has been enabled."}
    if response.status_code != 200:
        raise HTTPException(502, "Stripe verification is unavailable") from None
    try:
        account = response.json()
    except ValueError:
        raise HTTPException(502, "Invalid Stripe verification response") from None
    if account.get("object") != "account" or not str(account.get("id", "")).startswith("acct_"):
        raise HTTPException(502, "Unexpected Stripe account response") from None
    fingerprint = _profile_fingerprint(row)
    # Save only if the same encrypted credentials are still current.
    updated = db.execute(text(
        "UPDATE payment_provider_profiles SET "
        "verification_fingerprint=:fingerprint,verified_at=CURRENT_TIMESTAMP,"
        "verified_account_id=:account_id "
        "WHERE slug=:slug AND encrypted_fields=:encrypted_fields "
        "AND environment=:environment AND connection_mode='api'"
    ), {"fingerprint": fingerprint, "account_id": account["id"],
        "slug": slug, "encrypted_fields": row["encrypted_fields"],
        "environment": mode})
    if updated.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Payment credentials changed during verification; verify the newly saved settings")
    db.commit()
    return {"result": "api_verified", "verified": True, "provider": "stripe",
            "environment": mode, "account_id": account["id"],
            "charges_enabled": bool(account.get("charges_enabled")),
            "checkout_verified": False, "webhook_verified": False,
            "message": "Stripe API credential is valid. Checkout and webhooks are not verified."}
