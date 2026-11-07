"""Persistent, narrowly scoped admin email-service preferences."""
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError, OperationalError

SUPPORTED = frozenset({"registration_verification", "password_reset", "github_connection_verification", "welcome_email", "account_suspension", "payment_receipt", "login_security", "password_changed", "email_changed", "payment_failed", "unusual_activity", "subscription_expiry", "renewal_reminder", "trial_expiring", "system_updates", "service_incident", "backup_status", "support_received"})

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
    except (ProgrammingError, OperationalError) as exc:
        missing_postgres=getattr(getattr(exc, "orig", None), "sqlstate", "") == "42P01"
        missing_fixture=db.bind.dialect.name=="sqlite" and str(getattr(exc,"orig",""))=="no such table: email_service_policies"
        if missing_postgres or missing_fixture:
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
