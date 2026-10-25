"""Database-backed admin provider configuration, using the existing Gateway encryption helper."""
import json
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from fastapi import HTTPException
from . import credentials

def read(db):
    try:
        # Keep existing SMTP functional before optional 0021 schema is installed.
        # Savepoint prevents a missing table from poisoning the caller transaction.
        with db.begin_nested():
            token=db.execute(text("SELECT encrypted_data FROM email_delivery_settings WHERE id=1")).scalar_one_or_none()
    except ProgrammingError as exc:
        if getattr(getattr(exc,"orig",None),"sqlstate",None)=="42P01":
            return None
        raise
    if not token:return None
    try:return json.loads(credentials.decrypt(token))
    except Exception:raise HTTPException(503,"Cannot read encrypted email settings") from None

def save(db, actor_id, data):
    if not credentials.available():
        raise HTTPException(503,"Encryption is not configured")
    token=credentials.encrypt(json.dumps(data))
    db.execute(text("INSERT INTO email_delivery_settings(id,encrypted_data,updated_by) VALUES(1,:data,:actor) ON CONFLICT (id) DO UPDATE SET encrypted_data=excluded.encrypted_data,updated_by=excluded.updated_by,updated_at=CURRENT_TIMESTAMP"),{"data":token,"actor":actor_id})
    db.commit()
