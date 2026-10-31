"""Publish ONLY real manual/hosted receipt-verified payment methods from admin profiles.

Payment APIs require dedicated verified adapters; selecting 'api' never
automatically grants entitlement. The legacy PayPal flow is not touched.
"""
import json
import uuid
from fastapi import HTTPException
from sqlalchemy import inspect, text

from ..models import BillingMethod
from ..routes.management import MethodInput, method_values, validate_receiving_method
from . import payment_provider_profiles as profiles, credentials


def schema_ready(db):
    return inspect(db.connection()).has_table("payment_profile_publications")


def _linked_id(db, slug, *, lock=False):
    if not schema_ready(db):
        return None
    query="SELECT method_id FROM payment_profile_publications WHERE profile_slug=:slug"
    if lock and db.bind.dialect.name=="postgresql":
        query+=" FOR UPDATE"
    value=db.execute(text(query),{"slug":slug}).scalar_one_or_none()
    return uuid.UUID(str(value)) if value is not None else None


def publication_status(db, slug):
    identifier=_linked_id(db,slug)
    method=db.get(BillingMethod,identifier) if identifier else None
    return {
        "published":bool(method and method.enabled and method.user_id is None),
        "method_id":str(method.id) if method else None,
        "checkout_mode":None if not method else
            json.loads(credentials.decrypt(method.details)).get("checkout_mode"),
        "receipt_review_required":True,
        "automatic_capture":False,
    }


def disable_on_edit(db,slug):
    """An admin changing receiving details must explicitly republish verified data."""
    identifier=_linked_id(db,slug,lock=True)
    if identifier:
        method=db.get(BillingMethod,identifier)
        if method is not None and method.user_id is None:
            method.enabled=False
            db.flush()


def forget_profile(db,slug):
    """Disable receiving method but retain historical orders and its method row."""
    disable_on_edit(db,slug)
    if schema_ready(db):
        db.execute(text("DELETE FROM payment_profile_publications WHERE profile_slug=:slug"),{"slug":slug})


def publish(db,slug,actor_id, *, currency, instructions,plan_id=None,available_country_codes=None):
    if not schema_ready(db):
        raise HTTPException(503,"Payment profile publication migration 0034 required")
    row=profiles._one(db,slug,lock=True)
    if not row:raise HTTPException(404,"Unknown provider profile")
    if row["connection_mode"]=="api":
        raise HTTPException(409,
            "Saving merchant API credentials does NOT connect or verify a provider. "
            "A supported provider-specific capture and webhook adapter is required.")
    fields=profiles._decode(row["encrypted_fields"])
    if any(f["required"] and not f["value"] for f in fields):
        raise HTTPException(422,"Complete all required connection fields before publishing")
    # NEVER return secret fields in public checkout details, even if configured.
    values={f["key"]:f["value"] for f in fields if f["kind"]!="secret"}
    def take(*keys):
        return next((str(values[k]).strip() for k in keys if str(values.get(k,"")).strip()),"")
    mode="manual" if row["connection_mode"]=="manual" else "link"
    kind="bank" if row["category"]=="bank" else "wallet" if row["category"]=="wallet" else "other"
    amount=plan_id if mode=="link" else None
    info={
        "kind":kind,
        "label":row["label"],
        "currency":currency,
        "checkout_mode":mode,
        "bank_name":take("bank_name") if kind=="bank" else "",
        "account_name":take("account_name","account_holder","beneficiary_name"),
        "account_reference":take("account_reference","account_number","wallet_id","iban"),
        "iban":take("iban"),
        "branch":take("branch"),
        "network":take("network"),
        "payment_url":take("payment_url") if mode=="link" else "",
        "instructions":instructions.strip(),
        "plan_id":amount,
        "available_country_codes":available_country_codes or [],
        "enabled":True,
    }
    if mode=="manual" and not info["account_reference"]:
        raise HTTPException(422,
           "Add a real receiving account number, wallet ID or IBAN in the profile")
    try:
        data=MethodInput(**info)
    except Exception:
        # Pydantic's validation errors should become 422; FastAPI handles them,
        # never put merchant keys or user-supplied values in custom errors.
        raise HTTPException(422,"Invalid receiving account or hosted payment settings") from None
    validate_receiving_method(db,data,True)
    identifier=_linked_id(db,slug,lock=True)
    method=db.get(BillingMethod,identifier) if identifier else None
    if method and method.user_id is not None:
        raise HTTPException(409,"Linked checkout method does not belong to the platform")
    if method:
        for key,value in method_values(data).items():
            setattr(method,key,value)
    else:
        method=BillingMethod(user_id=None,**method_values(data))
        db.add(method);db.flush()
        db.execute(text(
            "INSERT INTO payment_profile_publications(profile_slug,method_id) "
            "VALUES (:slug,:method_id)"
        ),{"slug":slug,"method_id":method.id.hex})
    db.commit()
    return publication_status(db,slug)


def unpublish(db,slug):
    if profiles._one(db,slug) is None:
        raise HTTPException(404,"Unknown provider profile")
    disable_on_edit(db,slug)
    db.commit()
    return publication_status(db,slug)
