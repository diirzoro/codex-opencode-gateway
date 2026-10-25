"""Persistent, narrowly scoped admin email-service preferences."""
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

SUPPORTED = frozenset({"registration_verification"})

def enabled(db, service_id: str, fallback: bool = True) -> bool:
    if service_id not in SUPPORTED:
        return False
    # On installations waiting for migration 0022, keep secure defaults.
    try:
        with db.begin_nested():
            value = db.execute(
                text("SELECT enabled FROM email_service_policies WHERE service_id=:name"),
                {"name": service_id},
            ).scalar_one_or_none()
            return fallback if value is None else bool(value)
    except ProgrammingError as exc:
        if getattr(getattr(exc, "orig", None), "sqlstate", "") == "42P01":
            return fallback
        raise

def set_enabled(db, service_id: str, value: bool):
    if service_id not in SUPPORTED:
        raise ValueError("Service is not implemented")
    db.execute(text("""
        INSERT INTO email_service_policies (service_id, enabled) VALUES (:name, :enabled)
        ON CONFLICT (service_id) DO UPDATE
        SET enabled=excluded.enabled, updated_at=CURRENT_TIMESTAMP
    """), {"name":service_id,"enabled":value})
    db.commit()
