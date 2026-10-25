"""Account authorization for the existing native provider store.

The 1.19.4 /auth API is process-global. A provider slot therefore has ONE
account owner; a different account may not overwrite or reuse its credential.
This is a development compatibility limit, not a tenant credential sandbox.
No engines, polling jobs, copied auth files, or alternate AI requests live here.
"""
import hashlib
import json
import hmac
import os
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import select, text

from ..config import settings
from ..models import AccountAudit
from . import credentials, policy, providers, user_provider_credentials


def root(user):
    # Account discovery has no project dependency. Native directory scoping is
    # metadata context only, never a claim of OS isolation.
    result=settings.runtime_root / str(user.id) / 'native-account'
    current=settings.runtime_root
    for part in result.relative_to(current).parts:
        current=current/part
        if current.is_symlink():raise HTTPException(403,'Unsafe account context')
    result.mkdir(parents=True,exist_ok=True,mode=0o700)
    return result


def request(method,path,directory,data=None):
    from ..routes.native_sessions import metadata
    return metadata(method,path,directory,data)


def action(provider_id):
    return 'native-provider:'+hashlib.sha256(provider_id.encode()).hexdigest()[:40]


def binding(db,provider_id):
    return db.scalar(select(AccountAudit).where(AccountAudit.action.in_(
        [action(provider_id),action(provider_id)+':off'])).order_by(AccountAudit.id.desc()).limit(1))


def owned(db,user,provider_id):
    record=binding(db,provider_id)
    # Preserve the prior pilot's existing native connections. This retired flag
    # is legacy ownership attribution only, never an admission restriction.
    if record is None:return str(user.id)==os.getenv('OPENCODE_NATIVE_TEST_OWNER_ID','')
    return bool(record.action==action(provider_id) and record.subject_id==user.id)


def lock(db,provider_id):
    # Serialize ownership assignment across Gateway workers, without migration.
    if db.bind.dialect.name=='postgresql':
        number=int.from_bytes(hashlib.sha256(provider_id.encode()).digest()[:8],signed=True)
        db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':number})


def claim(db,user,provider_id,directory):
    lock(db,provider_id)
    if owned(db,user,provider_id):return
    record=binding(db,provider_id)
    if record and record.action==action(provider_id):
        raise HTTPException(409,'This native provider slot belongs to another TEST account; its credential was preserved')
    live=request('GET','/provider',directory)
    entry=next((p for p in live.get('all',[]) if p.get('id')==provider_id),{})
    if provider_id in live.get('connected',[]) and not public_free(entry):
        # A legacy encrypted account key may establish ownership only when it
        # actually matches the native credential. No copying/decryption fallback.
        saved=user_provider_credentials.find(db,user.id,provider_id)
        try:
            secret=json.loads(credentials.decrypt(saved.ciphertext)) if saved else {}
            matches=secret.get('type')=='api' and isinstance(entry.get('key'),str) and hmac.compare_digest(secret.get('key',''),entry['key'])
        except Exception:matches=False
        if not matches:raise HTTPException(409,'Native provider has a pre-existing unassigned connection; it was preserved')
    db.add(AccountAudit(actor_id=user.id,subject_id=user.id,action=action(provider_id)))
    db.flush()


def public_entry(entry):
    # Only explicit metadata fields. Native Provider.key/options may hold secrets.
    return {'id':entry['id'],'name':entry.get('name',entry['id']),
            'models':{k:providers.public_metadata(v) for k,v in entry.get('models',{}).items()}}


def public_free(entry,model=None):
    # The native built-in free catalog can be shared only while unauthenticated.
    if entry.get('id')!='opencode' or entry.get('source')!='custom' or entry.get('key') or entry.get('options',{}).get('apiKey') not in (None,'public'):
        return False
    models=entry.get('models',{})
    rows=[models.get(model)] if model else list(models.values())
    return bool(rows) and any(isinstance(m,dict) and m.get('cost',{}).get('input')==0 and m.get('cost',{}).get('output')==0 for m in rows)


def catalog(db,user,directory=None):
    data=request('GET','/provider',directory or root(user))
    if not isinstance(data,dict) or not isinstance(data.get('all'),list):raise HTTPException(502,'Invalid native provider catalog')
    connected=[];entries=[];rules=policy.load(db)
    # One ownership query for the catalog, not one query per provider/model.
    owners={}
    for record in db.scalars(select(AccountAudit).where(AccountAudit.action.like('native-provider:%')).order_by(AccountAudit.id)):
        owners[record.action.removesuffix(':off')]=None if record.action.endswith(':off') else record.subject_id
    for entry in data['all']:
        public=public_entry(entry)
        key=action(entry['id'])
        is_owned=owners.get(key)==user.id or (key not in owners and str(user.id)==os.getenv('OPENCODE_NATIVE_TEST_OWNER_ID','') and not public_free(entry))
        if public_free(entry) and not is_owned:
            public['models']={k:v for k,v in public['models'].items() if public_free(entry,k)}
        if entry['id'] in data.get('connected',[]) and (is_owned or public_free(entry)) and policy.provider_allowed(rules,entry['id']):connected.append(entry['id'])
        entries.append(public)
    return {'all':entries,'connected':connected,'default':data.get('default',{}),'native':True,
            'gateway_auth_status':{pid:{'auth_status':'configured','verified':False} for pid in connected}}


def require_model(db,user,directory,provider_id,model_id):
    data=request('GET','/provider',directory)
    entry=next((p for p in data.get('all',[]) if p.get('id')==provider_id),None)
    if entry is None or provider_id not in data.get('connected',[]) or model_id not in entry.get('models',{}):raise HTTPException(403,'Native model is not configured')
    if public_free(entry):
        if not public_free(entry,model_id):raise HTTPException(403,'This native model requires an owned provider credential')
    elif not owned(db,user,provider_id):raise HTTPException(403,'This native provider credential does not belong to your account')


def methods(user,provider_id):
    directory=root(user)
    entry=providers.resolve_provider(request('GET','/provider',directory),provider_id)
    if entry['id']!=provider_id:raise HTTPException(422,'Use the original Native provider ID')
    data=request('GET','/provider/auth',directory)
    if not isinstance(data,dict):raise HTTPException(502,'Invalid native authentication metadata')
    # /provider/auth enumerates plugin hooks, not generic /auth/{provider} API
    # key storage. The official PUT auth API supports the API-key form for a
    # catalog provider with no plugin method, including manually selected IDs.
    return data.get(provider_id) or [{'type':'api','label':'API key'}]


def connect(db,user,provider_id,data):
    directory=root(user);rules=policy.load(db)
    if not policy.provider_allowed(rules,provider_id):raise HTTPException(403,'Provider disabled by policy')
    user_provider_credentials.require_schema(db)
    if not credentials.available():raise HTTPException(503,'Existing credential encryption key is required')
    choices=methods(user,provider_id)
    index=data.method if data.method is not None else next((i for i,m in enumerate(choices) if m.get('type')=='api'),None)
    if index is None or index>=len(choices) or choices[index].get('type')!='api':raise HTTPException(422,'Select a native API-key method')
    claim(db,user,provider_id,directory)
    # Never overwrite an existing saved key, including old encrypted credentials.
    saved=user_provider_credentials.find(db,user.id,provider_id)
    if saved:
        try:secret=json.loads(credentials.decrypt(saved.ciphertext))
        except Exception:raise HTTPException(409,'Saved credentials could not be matched; they were preserved') from None
        if secret.get('type')!='api' or not hmac.compare_digest(secret.get('key',''),data.api_key):raise HTTPException(409,'Saved credentials already exist; they were preserved')
        if request('PUT','/auth/'+quote(provider_id,safe=''),directory,{'type':'api','key':data.api_key,'metadata':data.inputs or {}}) is not True:raise HTTPException(502,'Native credential configuration was not confirmed')
        db.commit();return {'connected':True,'persisted':True,'provider_id':provider_id,'verified':False}
    value={'type':'api','key':data.api_key,'metadata':data.inputs or {}}
    user_provider_credentials.save_encrypted(db,user.id,provider_id,credentials.encrypt(json.dumps(value)),data.api_key[-4:])
    if request('PUT','/auth/'+quote(provider_id,safe=''),directory,value) is not True:raise HTTPException(502,'Native credential configuration was not confirmed')
    db.commit()
    return {'connected':True,'persisted':True,'provider_id':provider_id,'verified':False,'connection_test':'Submit a native prompt to verify provider access'}


def oauth_authorize(db,user,provider_id,data):
    directory=root(user)
    if not policy.provider_allowed(policy.load(db),provider_id):raise HTTPException(403,'Provider disabled by policy')
    choices=methods(user,provider_id)
    if data.method>=len(choices) or choices[data.method].get('type')!='oauth':raise HTTPException(422,'Select a native OAuth method')
    claim(db,user,provider_id,directory)
    result=request('POST','/provider/'+quote(provider_id,safe='')+'/oauth/authorize',directory,{'method':data.method,'inputs':data.inputs or {}})
    # Native holds pending OAuth and refresh tokens; expose only authorization UI.
    db.commit()
    return {k:result[k] for k in ('url','method','instructions') if k in result}


def oauth_callback(db,user,provider_id,data):
    lock(db,provider_id)
    if not owned(db,user,provider_id):raise HTTPException(403,'Native OAuth does not belong to this account')
    result=request('POST','/provider/'+quote(provider_id,safe='')+'/oauth/callback',root(user),{'method':data.method,**({'code':data.code} if data.code else {})})
    if result is not True:raise HTTPException(502,'Native OAuth was not confirmed')
    db.commit()
    return {'connected':True,'persisted':True,'provider_id':provider_id,'verified':False}


def disconnect(db,user,provider_id):
    lock(db,provider_id)
    if not owned(db,user,provider_id):raise HTTPException(403,'Native provider does not belong to this account')
    if request('DELETE','/auth/'+quote(provider_id,safe=''),root(user)) is not True:raise HTTPException(502,'Native credential revocation was not confirmed')
    user_provider_credentials.delete_owned(db,user.id,provider_id)
    db.add(AccountAudit(actor_id=user.id,subject_id=user.id,action=action(provider_id)+':off'));db.commit()
