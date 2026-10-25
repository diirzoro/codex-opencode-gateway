"""Real Gateway HTTP/ORM behavior with synthetic Native/SMTP vendor boundaries.
Not shared-engine/vendor delivery or live PostgreSQL certification.
"""
import importlib.util,json,sqlite3,uuid
from dataclasses import replace
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from alembic.migration import MigrationContext
from alembic.operations import Operations
from backend.tests.test_native_control_plane import boundary,authenticated
from backend.app import models
from backend.app.routes import admin,auth,management,native_sessions as native
from backend.app.services import policy,credentials,native_provider_accounts as accounts,admin_email_config,email_verification,recovery

@pytest.fixture
def acceptance(boundary,monkeypatch):
 client,(a,b),calls,engine,config=boundary
 for model in (models.PlatformPolicy,models.Country,models.Region,models.City,models.EmailVerification,models.PasswordReset):model.__table__.create(engine)
 with Session(engine) as db:
  db.get(models.User,a.id).role='admin';db.add(models.PlatformPolicy(id=1,allowed_providers='[]',allowed_models='[]',allowed_tools='[]'));db.commit()
 monkeypatch.setattr(policy,'load',lambda db:db.get(models.PlatformPolicy,1))
 monkeypatch.setattr('backend.app.config.settings',config);monkeypatch.setattr(email_verification,'settings',config)
 monkeypatch.setattr(credentials,'settings',replace(credentials.settings,credentials_encryption_key='disposable-acceptance-key'))
 monkeypatch.setattr(accounts,'root',lambda user:(a if user.id==a.id else b).root)
 catalog={'all':[{'id':f'p{i:03}','name':f'Native provider {i}','key':'SYNTHETIC_SECRET_NOT_PUBLIC','options':{'token':'PRIVATE'},'models':{'m1':{'name':'Model one','cost':{'input':0,'output':0}},'m2':{'name':'Model two','cost':{'input':0,'output':0}}}} for i in range(120)],'connected':['p110']}
 live={o.name:{'id':'ses_'+o.name,'directory':str(o.root),'permission':policy.native_session_permissions(NS(allowed_providers='[]',allowed_models='[]',allowed_tools='[]'),o.root)} for o in (a,b)}
 writes=[]
 def metadata(method,path,root,data=None):
  if path=='/provider':return catalog
  if path=='/provider/auth':return {}
  if path=='/path':return {'directory':str(root),'worktree':'/'}
  if path=='/session/status':return {}
  if path=='/experimental/tool/ids':return ['read','write','edit','question','todowrite']
  if path.startswith('/auth/'):
   writes.append((method,path,data));return True
  if path.startswith('/session/'):
   name=path.split('/')[-1].removeprefix('ses_')
   if method=='PATCH':live[name].update(data)
   return live[name]
  raise AssertionError((method,path))
 monkeypatch.setattr(native,'metadata',metadata)
 client.app.include_router(admin.router);client.app.include_router(auth.router);client.app.include_router(management.router)
 return client,(a,b),engine,config,catalog,writes

def request(f,path,admin_user=True,method='GET',body=None):
 client,owners,_,config,_,_=f
 return authenticated(client,path,owners[0 if admin_user else 1],config,method,body)

@pytest.mark.parametrize('path',['/api/admin/policy','/api/admin/native/providers','/api/admin/service-integrations'])
def test_customer_cannot_read_admin_controls(acceptance,path):
 assert request(acceptance,path,False).status_code==403

def test_admin_native_catalog_is_complete_paged_and_secret_free(acceptance):
 first=request(acceptance,'/api/admin/native/providers?limit=6').json()
 assert len(first['items'])==6 and first['total']==120 and first['next_offset']==6
 found=request(acceptance,'/api/admin/native/providers?query=p110').json()
 assert found['items'][0]['id']=='p110' and found['items'][0]['runtime_configured']
 assert 'SYNTHETIC_SECRET' not in json.dumps(found) and 'PRIVATE' not in json.dumps(found)
 assert request(acceptance,'/api/admin/native/providers?provider_id=unsupported').status_code==404

def hide(f):
 body=request(f,'/api/admin/policy').json();body.pop('updated_at',None)
 body.update(hidden_providers=['p110'],hidden_models={'p110':['m2']})
 response=request(f,'/api/admin/policy',True,'PUT',body);assert response.status_code==200,response.text

def test_hidden_is_not_forbidden_default_manual_restore_and_direct_native_prompt(acceptance):
 hide(acceptance)
 f=acceptance;client,(a,b),engine,config,_,_=f
 data=request(f,'/api/admin/policy').json();assert data['hidden_providers']==['p110'] and data['hidden_models']=={'p110':['m2']}
 default=request(f,'/api/opencode/catalog/providers/page?limit=50',False).json()
 assert 'p110' not in [row['id'] for row in default['items']]
 manual=request(f,'/api/opencode/catalog/providers/search?query=p110',False)
 assert manual.status_code==200 and manual.json()[0]['allowed'] is True
 options=request(f,f'/api/workspaces/{b.workspace}/providers/p110/models',False)
 assert options.status_code==200,options.text
 assert next(row for row in options.json()['models'] if row['id']=='m2')['allowed'] is True
 assert next(row for row in options.json()['models'] if row['id']=='m2')['visible'] is False
 with Session(engine) as db:db.add(models.AccountAudit(actor_id=b.id,subject_id=b.id,action=accounts.action('p110')));db.commit()
 prompt={'model':{'providerID':'p110','modelID':'m2'},'parts':[{'type':'text','text':'Synthetic prompt, transport authorization only'}]}
 response=request(f,f'/native-session/{b.workspace}/session/ses_b/prompt_async',False,'POST',prompt)
 assert response.status_code==200 and response.headers.get('x-accel-redirect')=='@native_session_test'
 body={k:v for k,v in data.items() if k!='updated_at'};body.update(hidden_providers=[],hidden_models={})
 assert request(f,'/api/admin/policy',True,'PUT',body).status_code==200
 assert request(f,'/api/admin/native/providers?query=p110').json()['items'][0]['visible'] is True


def test_security_allowlist_still_blocks_direct_native_request_independently_of_visibility(acceptance):
 f=acceptance;_,(a,b),_,_,_,_=f
 body=request(f,'/api/admin/policy').json();body.pop('updated_at');body['allowed_models']=['m1']
 assert request(f,'/api/admin/policy',True,'PUT',body).status_code==200
 denied=request(f,f'/native-session/{b.workspace}/session/ses_b/prompt_async',False,'POST',{'model':{'providerID':'p110','modelID':'m2'},'parts':[{'type':'text','text':'not transported'}]})
 assert denied.status_code==403 and not denied.headers.get('x-accel-redirect')


def test_hidden_provider_credentials_save_encrypted_and_do_not_copy_between_owners(acceptance):
 f=acceptance;hide(f)
 _,(a,b),engine,_,catalog,writes=f
 catalog['connected']=[]
 connected=request(f,'/api/opencode/connections/p110/credentials',False,'POST',{'api_key':'synthetic-test-key','method':0})
 assert connected.status_code==200,connected.text
 assert connected.json()['persisted'] is True and connected.json()['verified'] is False
 assert writes and writes[-1][0]=='PUT'
 with Session(engine) as db:
  saved=db.query(models.UserProviderCredential).filter_by(user_id=b.id,provider_id='p110').one()
  assert 'synthetic-test-key' not in saved.ciphertext
  assert json.loads(credentials.decrypt(saved.ciphertext))['key']=='synthetic-test-key'
  assert db.query(models.UserProviderCredential).filter_by(user_id=a.id,provider_id='p110').count()==0
 # Another account cannot seize the Native slot, even though the provider is hidden.
 conflict=request(f,'/api/opencode/connections/p110/credentials',True,'POST',{'api_key':'other-synthetic-key','method':0})
 assert conflict.status_code==409


def test_missing_original_encryption_key_explains_real_blocker_and_never_mutates_native(acceptance,monkeypatch):
 monkeypatch.setattr(credentials,'settings',replace(credentials.settings,credentials_encryption_key=None))
 options=request(acceptance,'/api/opencode/connections/p110/options',False)
 assert options.status_code==200 and options.json()['credential_storage_ready'] is False
 response=request(acceptance,'/api/opencode/connections/p110/credentials',False,'POST',{'api_key':'synthetic','method':0})
 assert response.status_code==503 and not acceptance[-1]


def migrate_email(engine):
 spec=importlib.util.spec_from_file_location('email_migration','backend/alembic/versions/0021_email_delivery_settings.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 with engine.begin() as connection:
  with Operations.context(MigrationContext.configure(connection)):module.upgrade()


def test_actual_0021_migration_encrypted_settings_and_existing_users_preserved(acceptance):
 f=acceptance;_,(a,b),engine,_,_,_=f
 before=request(f,'/api/admin/service-integrations').json()
 assert before['email']['settings_schema_ready'] is False
 assert request(f,'/api/admin/service-integrations/email',True,'PUT',{'smtp_from':'sender@opencode-gateway.codes','api_key':'synthetic-resend'}).status_code==503
 migrate_email(engine);sqlite3.register_adapter(uuid.UUID,lambda value:value.hex)
 response=request(f,'/api/admin/service-integrations/email',True,'PUT',{'smtp_from':'sender@opencode-gateway.codes','api_key':'synthetic-resend'})
 assert response.status_code==200,response.text
 status=request(f,'/api/admin/service-integrations').json()
 assert status['email']['configured'] is True and status['email']['delivery_verified'] is False
 assert next(row for row in status['services'] if row['id']=='password_reset')['available'] is True
 assert 'synthetic-resend' not in json.dumps(status)
 with Session(engine) as db:
  token=db.execute(text('SELECT encrypted_data FROM email_delivery_settings WHERE id=1')).scalar_one();assert 'synthetic-resend' not in token
  assert admin_email_config.read(db)['smtp_password']=='synthetic-resend'
  assert all(db.get(models.User,o.id).status=='active' for o in (a,b))


def test_password_recovery_reads_saved_resend_configuration(acceptance,monkeypatch):
 f=acceptance;_,(a,b),engine,_,_,_=f;migrate_email(engine);sqlite3.register_adapter(uuid.UUID,lambda value:value.hex)
 assert request(f,'/api/admin/service-integrations/email',True,'PUT',{'smtp_from':'sender@opencode-gateway.codes','api_key':'synthetic-resend'}).status_code==200
 sent=[]
 class SMTP:
  def __init__(self,host,port,**kw):assert host=='smtp.resend.com' and port==587
  def __enter__(self):return self
  def __exit__(self,*a):pass
  def starttls(self,**kw):pass
  def login(self,user,secret):assert user=='resend' and secret=='synthetic-resend'
  def send_message(self,message):sent.append(message)
 monkeypatch.setattr(recovery.smtplib,'SMTP',SMTP)
 # Existing password recovery route uses saved config, never requires existing account re-verification.
 with Session(engine) as db:db.get(models.User,b.id).email='fixture-b@example.org';db.commit()
 response=request(f,'/api/auth/forgot-password',False,'POST',{'email':'fixture-b@example.org'})
 assert response.status_code==202,response.text
 assert len(sent)==1 and sent[0]['To']=='fixture-b@example.org'
 assert 'reset-password=' in sent[0].get_content()


def test_support_inbox_uses_real_handler_and_rejects_other_recipients(acceptance,monkeypatch):
 f=acceptance;_,(a,b),engine,_,_,_=f;migrate_email(engine);sqlite3.register_adapter(uuid.UUID,lambda value:value.hex)
 with Session(engine) as db:admin_email_config.save(db,a.id,{'inbox_api_key':'synthetic-read-key'})
 from io import BytesIO
 mid=str(uuid.uuid4())
 def reply(req,**kw):
  assert req.get_header('Authorization')=='Bearer synthetic-read-key'
  if req.full_url.endswith(mid):return BytesIO(json.dumps({'to':['elsewhere@example.org'],'text':'FOREIGN'}).encode())
  return BytesIO(json.dumps({'data':[{'id':mid,'to':['support@opencode-gateway.codes'],'subject':'Synthetic support','from':'fixture@example.org'}]}).encode())
 monkeypatch.setattr('urllib.request.urlopen',reply)
 listing=request(f,'/api/admin/service-integrations/support-inbox');assert listing.status_code==200 and listing.json()['items'][0]['subject']=='Synthetic support'
 assert request(f,'/api/admin/service-integrations/support-inbox/'+mid).status_code==404
