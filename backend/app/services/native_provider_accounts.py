"""Account authorization for the existing native provider store.

The 1.19.4 /auth API is process-global. A provider slot therefore has ONE
account owner; a different account may not overwrite or reuse its credential.
This is a development compatibility limit, not a tenant credential sandbox.
No engines, polling jobs, copied auth files, or alternate AI requests live here.
"""
import hashlib
import os
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import select, text

from ..config import settings
from ..models import AccountAudit
from . import policy, providers, user_provider_credentials


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
    if record is None:return False
    return bool(record.action==action(provider_id) and record.subject_id==user.id)


def lock(db,provider_id):
    # Serialize ownership assignment across Gateway workers, without migration.
    if db.bind.dialect.name=='postgresql':
        number=int.from_bytes(hashlib.sha256(provider_id.encode()).digest()[:8],signed=True)
        db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':number})


def claim(db,user,provider_id,directory,*,catalog=None,proposed_key=None):
    lock(db,provider_id)
    if owned(db,user,provider_id):return
    record=binding(db,provider_id)
    if record and record.action==action(provider_id):
        raise HTTPException(409,'This native provider slot belongs to another TEST account; its credential was preserved')
    live=catalog if catalog is not None else request('GET','/provider',directory)
    entry=next((p for p in live.get('all',[]) if p.get('id')==provider_id),{})
    if provider_id in live.get('connected',[]) and not public_free(entry):
        # A process-global Native credential cannot be reassigned to another
        # account. Never read, copy, compare or silently delete a legacy key.
        # A TEST-only migration must first prove that the Native auth store is
        # separate from LIVE before explicitly revoking unassigned credentials.
        raise HTTPException(409,'Existing unassigned Native credential must be revoked after TEST auth isolation')
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


def catalog(db,user,directory=None,*,full=False):
    data=request('GET','/provider',directory or root(user))
    if not isinstance(data,dict) or not isinstance(data.get('all'),list):raise HTTPException(502,'Invalid native provider catalog')
    connected=[];entries=[];rules=policy.load(db)
    # One ownership query for the catalog, not one query per provider/model.
    owners={}
    for record in db.scalars(select(AccountAudit).where(AccountAudit.action.like('native-provider:%')).order_by(AccountAudit.id)):
        owners[record.action.removesuffix(':off')]=None if record.action.endswith(':off') else record.subject_id
    def account_owned(entry):
        key=action(entry['id'])
        return owners.get(key)==user.id
    def usable(entry):
        return entry['id'] in data.get('connected',[]) and (account_owned(entry) or public_free(entry)) and policy.provider_allowed(rules,entry['id'])
    # Curate presentation only. Manual name/ID lookup needs the complete Native
    # catalog; another account's process-global connection gets no priority.
    ordered=sorted(data['all'],key=lambda entry:(not usable(entry),entry['id'] not in providers.POPULAR_PROVIDER_IDS,str(entry['id'])))
    defaults=[entry for entry in ordered if policy.provider_visible(rules,entry['id'])]
    selected=ordered if full else defaults[:50]
    additional=[] if full else [entry for entry in ordered if entry not in selected and usable(entry)]
    for entry in [*selected,*additional]:
        public=public_entry(entry)
        if public_free(entry) and not account_owned(entry):
            public['models']={k:v for k,v in public['models'].items() if public_free(entry,k)}
        public['models']={k:v for k,v in public['models'].items() if policy.model_allowed(rules,k,entry['id'])}
        if not policy.provider_allowed(rules,entry['id']):public['models']={}
        if usable(entry):connected.append(entry['id'])
        public['visible']=policy.provider_visible(rules,entry['id'])
        for mid,model in public['models'].items():model['visible']=policy.model_visible(rules,entry['id'],mid)
        entries.append(public)
    return {'all':entries[:len(selected)],'connected_entries':entries[len(selected):],
            'connected':connected,'default':data.get('default',{}),'native':True,
            'gateway_auth_status':{pid:{'auth_status':'configured','verified':False} for pid in connected}}


def require_model(db,user,directory,provider_id,model_id):
    if not policy.model_allowed(policy.load(db),model_id,provider_id):raise HTTPException(403,'Model disabled by policy')
    data=request('GET','/provider',directory)
    entry=next((p for p in data.get('all',[]) if p.get('id')==provider_id),None)
    if entry is None or provider_id not in data.get('connected',[]) or model_id not in entry.get('models',{}):raise HTTPException(403,'Native model is not configured')
    if public_free(entry):
        if not public_free(entry,model_id):raise HTTPException(403,'This native model requires an owned provider credential')
    elif not owned(db,user,provider_id):raise HTTPException(403,'This native provider credential does not belong to your account')


def methods(user,provider_id,*,catalog=None):
    directory=root(user)
    # The caller may supply the same original Native catalog it already read.
    # Do not fetch and deserialize the 7 MB Native provider snapshot twice.
    entry=providers.resolve_provider(catalog if catalog is not None else request('GET','/provider',directory),provider_id)
    if entry['id']!=provider_id:raise HTTPException(422,'Use the original Native provider ID')
    data=request('GET','/provider/auth',directory)
    if not isinstance(data,dict):raise HTTPException(502,'Invalid native authentication metadata')
    # /provider/auth enumerates plugin hooks, not generic /auth/{provider} API
    # key storage. The official PUT auth API supports the API-key form for a
    # catalog provider with no plugin method, including manually selected IDs.
    return data.get(provider_id) or [{'type':'api','label':'API key'}]


def connect(db,user,provider_id,data):
    """Do not accept a write-only auth PUT as API-key verification.

    TEST key connections must complete a real OpenCode Native model round-trip
    with rollback on failure. A caller must not bypass that Native-only flow by
    invoking this legacy Gateway service directly.
    """
    raise HTTPException(
        409,
        'Unverified Native credential storage is disabled; connect and verify through OpenCode Native',
    )


def require_isolated_auth():
    """Refuse shared-process TEST auth writes until isolated Native is deployed.

    The operator must set this only after verifying separate TEST service
    HOME/XDG state, runtime endpoint and no shared LIVE auth files. A UI
    directory query parameter does not isolate OpenCode's process-global auth.
    """
    from ..routes.native_sessions import deployment
    if deployment()=='test' and os.getenv('OPENCODE_NATIVE_AUTH_ISOLATED','').lower() not in ('1','true','yes'):
        raise HTTPException(503,'TEST Native authentication store is not verified isolated from LIVE; refusing key mutation')


def oauth_authorize(db,user,provider_id,data):
    require_isolated_auth()
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
    require_isolated_auth()
    lock(db,provider_id)
    if not owned(db,user,provider_id):raise HTTPException(403,'Native OAuth does not belong to this account')
    result=request('POST','/provider/'+quote(provider_id,safe='')+'/oauth/callback',root(user),{'method':data.method,**({'code':data.code} if data.code else {})})
    if result is not True:raise HTTPException(502,'Native OAuth was not confirmed')
    db.commit()
    return {'connected':True,'persisted':True,'provider_id':provider_id,'verified':False}


def disconnect(db,user,provider_id):
    require_isolated_auth()
    lock(db,provider_id)
    if not owned(db,user,provider_id):raise HTTPException(403,'Native provider does not belong to this account')
    if request('DELETE','/auth/'+quote(provider_id,safe=''),root(user)) is not True:raise HTTPException(502,'Native credential revocation was not confirmed')
    # Cleanup legacy Gateway ciphertext only after Native confirms deletion.
    user_provider_credentials.delete_owned(db,user.id,provider_id)
    db.add(AccountAudit(actor_id=user.id,subject_id=user.id,action=action(provider_id)+':off'));db.commit()
