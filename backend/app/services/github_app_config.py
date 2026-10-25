"""Gateway-owned GitHub App configuration; no customer credentials or AI execution."""
import json
from dataclasses import replace
from fastapi import HTTPException
from sqlalchemy import inspect, select, text
from ..database import SessionLocal
from ..models import GithubConnection
from . import credentials

TABLE='github_app_settings'
FIELDS=('github_app_id','github_app_slug','github_client_id','github_client_secret','github_private_key','github_webhook_secret')

def schema_ready(db):
    return inspect(db.connection()).has_table(TABLE)

def read(db):
    if not schema_ready(db):return None
    token=db.execute(text('SELECT encrypted_data FROM github_app_settings WHERE id=1')).scalar_one_or_none()
    if not token:return None
    try:
        result=json.loads(credentials.decrypt(token))
        if not isinstance(result,dict):raise ValueError()
        return result
    except Exception:
        raise HTTPException(503,'Cannot read encrypted GitHub App settings; check the original Gateway encryption key') from None

def effective(base,db=None):
    if db is None:
        with SessionLocal() as session:return effective(base,session)
    values=read(db)
    if values is None:return base
    return replace(base,**{key:values.get(key) for key in FIELDS})

def save(db,actor_id,base,data):
    if not schema_ready(db):raise HTTPException(503,'GitHub settings schema missing; apply migration 0024')
    if not credentials.available():raise HTTPException(503,'Original Gateway credential encryption key is required')
    if db.bind.dialect.name=='postgresql':
        db.execute(text('SELECT id FROM github_app_settings WHERE id=1 FOR UPDATE'))
    current=effective(base,db)
    identity_changed=(current.github_app_id,current.github_client_id)!=(data['app_id'],data['client_id'])
    if identity_changed and db.scalar(select(GithubConnection.id).limit(1)) is not None:
        raise HTTPException(409,'Existing customer connections must be preserved; changing GitHub App identity requires an operator migration')
    values={'github_app_id':data['app_id'],'github_app_slug':data['app_slug'],'github_client_id':data['client_id']}
    for source,target in [('client_secret','github_client_secret'),('private_key','github_private_key'),('webhook_secret','github_webhook_secret')]:
        value=data.get(source)
        if value is not None and len(value)>32768:raise HTTPException(422,'GitHub credential exceeds supported size')
        values[target]=value if value else (None if identity_changed else getattr(current,target))
    if not values['github_client_secret'] or not values['github_private_key']:
        raise HTTPException(422,'Client secret and private key are required for this GitHub App')
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
        key=load_pem_private_key(values['github_private_key'].encode(),password=None)
        if not isinstance(key,RSAPrivateKey) or key.key_size<2048:raise ValueError()
    except Exception:
        raise HTTPException(422,'A valid unencrypted RSA private key of at least 2048 bits is required') from None
    token=credentials.encrypt(json.dumps(values))
    db.execute(text('INSERT INTO github_app_settings(id,encrypted_data,updated_by) VALUES(1,:data,:actor) ON CONFLICT(id) DO UPDATE SET encrypted_data=excluded.encrypted_data,updated_by=excluded.updated_by,updated_at=CURRENT_TIMESTAMP'),{'data':token,'actor':actor_id.hex if db.bind.dialect.name=='sqlite' else actor_id})
    db.commit()
