"""Shared payment-method serialization; leave gateway payment flows unchanged."""
import json

from . import credentials


def method_payload(row):
    return {
        "id": str(row.id),
        "kind": row.kind,
        "label": row.label,
        "enabled": row.enabled,
        "details": json.loads(credentials.decrypt(row.details)),
    }
