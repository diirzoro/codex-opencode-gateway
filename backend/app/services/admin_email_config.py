"""Database-backed admin provider configuration, using the existing Gateway encryption helper."""
import json
from sqlalchemy import text
from fastapi import HTTPException
from . import credentials

def read(db):
    token=db.execute(text("SELECT encrypted_data FROM email_delivery_settings WHERE id=1")).scalar_one_or_none()
    if not token:return None
    try:return json.loads(credentials.decrypt(token))
    except Exception:raise HTTPException(503,"Cannot read encrypted email settings") from None

def save(db, actor_id, data):
    if not credentials.available():
        raise HTTPException(503,"Encryption is not configured")
    token=credentials.encrypt(json.dumps(data))
    db.execute(text("INSERT INTO email_delivery_settings(id,encrypted_data,updated_by) VALUES(1,:data,:actor) ON CONFLICT (id) DO UPDATE SET encrypted_data=excluded.encrypted_data,updated_by=excluded.updated_by,updated_at=CURRENT_TIMESTAMP"),{"data":token,"actor":actor_id})
    db.commit()
