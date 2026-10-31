"""Verified-receipt payment methods backed by admin-created profiles.

Deliberately uses EXISTING encrypted BillingMethod.details and migration 0033,
not a separate schema/table. Historical checkout methods and orders survive
editing/unpublishing. This does not simulate API processing or grant credits.
"""
import json

from fastapi import HTTPException
from sqlalchemy import select

from ..models import BillingMethod
from ..routes.management import MethodInput, method_values, validate_receiving_method
from . import payment_provider_profiles as profiles, credentials

PROFILE_MARKER = "_gateway_profile_slug"


def _linked_method(db, slug, *, lock=False):
    # Only global methods; never inspect, modify or expose customers' methods.
    query = select(BillingMethod).where(BillingMethod.user_id.is_(None))
    if lock and db.bind.dialect.name == "postgresql":
        query = query.with_for_update()
    for method in db.scalars(query):
        try:
            details = json.loads(credentials.decrypt(method.details))
        except Exception:
            # Existing legacy methods with unusable data are not our profiles.
            continue
        if isinstance(details, dict) and details.get(PROFILE_MARKER) == slug:
            return method
    return None


def publication_status(db, slug):
    method = _linked_method(db, slug)
    mode = None
    if method is not None:
        details = json.loads(credentials.decrypt(method.details))
        mode = details.get("checkout_mode")
    return {
        "published": bool(method is not None and method.user_id is None and method.enabled),
        "method_id": str(method.id) if method is not None else None,
        "checkout_mode": mode,
        "receipt_review_required": True,
        "automatic_capture": False,
    }


def disable_on_edit(db, slug):
    """Unpublish before an admin changes bank details; preserve old orders."""
    method = _linked_method(db, slug, lock=True)
    if method is not None:
        method.enabled = False
        db.flush()


def forget_profile(db, slug):
    """Leave linked method disabled for audit and historical invoice references."""
    disable_on_edit(db, slug)


def _tagged_method_values(data, slug):
    attrs = method_values(data)
    details = json.loads(credentials.decrypt(attrs["details"]))
    details[PROFILE_MARKER] = slug
    attrs["details"] = credentials.encrypt(json.dumps(details))
    return attrs


def publish(db, slug, actor_id, *, currency, instructions, plan_id=None, available_country_codes=None):
    row = profiles._one(db, slug, lock=True)
    if not row:
        raise HTTPException(404, "Unknown provider profile")
    if row["connection_mode"] == "api":
        raise HTTPException(409,
            "Saving merchant API credentials is NOT a payment connection. "
            "Automated capture requires verified provider-specific integration.")
    fields = profiles._decode(row["encrypted_fields"])
    if any(item["required"] and not item["value"] for item in fields):
        raise HTTPException(422, "Complete all required connection fields before publishing")
    values = {item["key"]:item["value"] for item in fields if item["kind"] != "secret"}
    def take(*keys):
        return next((str(values[k]).strip() for k in keys if str(values.get(k, "")).strip()), "")
    mode = "manual" if row["connection_mode"] == "manual" else "link"
    kind = "bank" if row["category"] == "bank" else "wallet" if row["category"] == "wallet" else "other"
    info = {
        "kind": kind,
        "label": row["label"],
        "currency": currency,
        "checkout_mode": mode,
        "bank_name": take("bank_name") if kind == "bank" else "",
        "account_name": take("account_name", "account_holder", "beneficiary_name"),
        "account_reference": take("account_reference", "account_number", "wallet_id", "iban"),
        "iban": take("iban"),
        "branch": take("branch"),
        "network": take("network"),
        "payment_url": take("payment_url") if mode == "link" else "",
        "instructions": instructions.strip(),
        "plan_id": plan_id if mode == "link" else None,
        "available_country_codes": available_country_codes or [],
        "enabled": True,
    }
    if mode == "manual" and not info["account_reference"]:
        raise HTTPException(422, "Enter a real receiving account, wallet ID or IBAN first")
    try:
        data = MethodInput(**info)
    except Exception:
        raise HTTPException(422, "Invalid receiving account or hosted checkout settings") from None
    validate_receiving_method(db, data, True)
    method = _linked_method(db, slug, lock=True)
    attrs = _tagged_method_values(data, slug)
    if method is None:
        method = BillingMethod(user_id=None, **attrs)
        db.add(method)
    else:
        if method.user_id is not None:
            raise HTTPException(409, "Linked payment method is not platform-owned")
        for key,value in attrs.items():
            setattr(method, key, value)
    db.commit()
    return publication_status(db, slug)


def unpublish(db, slug):
    if profiles._one(db, slug) is None:
        raise HTTPException(404, "Unknown provider profile")
    disable_on_edit(db, slug)
    db.commit()
    return publication_status(db, slug)
