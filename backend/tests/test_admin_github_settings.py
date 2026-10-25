"""Encrypted admin configuration with actual HTTP/ORM and existing account flows.
No external GitHub, server migration or real credential claims.
"""
import importlib.util,uuid
from dataclasses import replace
from pathlib import Path
import pytest
from sqlalchemy import text,select
from sqlalchemy.orm import Session,sessionmaker
from alembic.operations import Operations
from alembic.migration import MigrationContext
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from backend.tests.test_native_control_plane import boundary,authenticated
from backend.app import models
from backend.app.routes import admin,auth
from backend.app.services import github,github_app_config as config,credentials,social_login

@pytest.fixture
def setup(boundary,monkeypatch):
 client,(owner,customer),_,engine,base=boundary
 with engine.begin() as connection:
  path=Path(__file__).parents[1]/'alembic/versions/0024_github_app_settings.py'
  spec=importlib.util.spec_from_file_location('github_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  module.op=Operations(MigrationContext.configure(connection));module.upgrade()
 with Session(engine) as db:db.get(models.User,owner.id).role='admin';db.commit()
 runtime=replace(base,github_app_id=None,github_app_slug=None,github_client_id=None,github_client_secret=None,github_private_key=None,credentials_encryption_key='test-only-master-key')
 for module in (github,admin,social_login,credentials):monkeypatch.setattr(module,'settings',runtime)
 monkeypatch.setattr(config,'SessionLocal',sessionmaker(bind=engine))
 client.app.include_router(admin.router);client.app.include_router(auth.router)
 key=rsa.generate_private_key(public_exponent=65537,key_size=2048).private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()).decode()
 payload={'app_id':5470256,'app_slug':'synthetic-gateway-test','client_id':'IvTestClient','client_secret':'SYNTHETIC_CLIENT_SECRET','private_key':key}
 return client,owner,customer,engine,runtime,payload

def send(f,method='GET',data=None,customer=False):
 client,owner,other,_,runtime,_=f
 return authenticated(client,'/api/admin/github-configuration',other if customer else owner,runtime,method,data)

def test_encrypted_save_activates_native_github_flows_without_exposing_secrets(setup):
 client,owner,customer,engine,runtime,payload=setup
 response=send(setup,'PUT',payload)
 assert response.status_code==200,response.text
 data=response.json();assert data['configured'] and data['source']=='encrypted_database'
 assert data['secrets']['client_secret'] and data['secrets']['private_key']
 assert payload['client_secret'] not in response.text and 'BEGIN PRIVATE' not in response.text
 with Session(engine) as db:
  stored=db.execute(text('SELECT encrypted_data FROM github_app_settings')).scalar_one()
  assert payload['client_secret'] not in stored and 'BEGIN PRIVATE' not in stored
  assert github.configured(db)
  assert github.connection_status(db,db.get(models.User,customer.id))['configured']
  assert not github.connection_status(db,db.get(models.User,customer.id))['connected']
  assert list(db.scalars(select(models.GithubConnection)))==[]
 assert social_login.available('github')
 url,_=social_login.begin('github');assert 'IvTestClient' in url and 'social%2Fgithub%2Fcallback' in url
 assert authenticated(client,'/api/auth/social/options',customer,runtime).json()['github']
 assert 'synthetic-gateway-test' in github.install_url('test-state')
 import jwt
 public=serialization.load_pem_private_key(payload['private_key'].encode(),password=None).public_key()
 assert jwt.decode(github._jwt(),public,algorithms=['RS256'])['iss']=='5470256'
 assert send(setup,'GET').json()['client_id']=='IvTestClient'

def test_customer_write_denied_and_blank_secrets_preserved(setup):
 payload=setup[-1];assert send(setup,'PUT',payload,customer=True).status_code==403
 assert send(setup,'PUT',payload).status_code==200
 update={key:value for key,value in payload.items() if key not in ('private_key','client_secret')}
 assert send(setup,'PUT',update).status_code==200
 assert send(setup).json()['secrets']['private_key']

def test_missing_master_key_and_missing_migration_do_not_mutate(setup,monkeypatch):
 monkeypatch.setattr(credentials,'settings',replace(setup[-2],credentials_encryption_key=None))
 assert send(setup,'PUT',setup[-1]).status_code==503
 with Session(setup[3]) as db:assert db.execute(text('SELECT COUNT(*) FROM github_app_settings')).scalar_one()==0
 with setup[3].begin() as c:c.execute(text('DROP TABLE github_app_settings'))
 assert send(setup).json()['settings_schema_ready'] is False
 assert send(setup,'PUT',setup[-1]).status_code==503

def test_existing_customer_connections_block_app_identity_replacement(setup):
 assert send(setup,'PUT',setup[-1]).status_code==200
 with Session(setup[3]) as db:
  db.add(models.GithubConnection(id=uuid.uuid4(),user_id=setup[2].id,installation_id=12345,account_login='synthetic-owner',app_id=5470256,user_token='synthetic-existing-encrypted-token',suspended=False));db.commit()
 updated={**setup[-1],'app_id':5470257,'client_id':'DifferentApp'}
 assert send(setup,'PUT',updated).status_code==409
 with Session(setup[3]) as db:assert db.scalar(select(models.GithubConnection)).user_token=='synthetic-existing-encrypted-token'
 assert send(setup).json()['app_id']==5470256

def test_invalid_pem_returns_safe_error(setup):
 result=send(setup,'PUT',{**setup[-1],'private_key':'INVALID_SYNTHETIC_PEM_DO_NOT_ECHO'})
 assert result.status_code==422
 assert 'INVALID_SYNTHETIC_PEM_DO_NOT_ECHO' not in result.text

@pytest.mark.parametrize('opaque',['ghs_'+'x'*36,'ghs_'+'a'*200+'.'+'b'*200+'.'+'c'*120])
def test_opaque_long_tokens_roundtrip_and_transport_without_truncation(setup,monkeypatch,opaque):
 import httpx
 encrypted=credentials.encrypt(opaque)
 with Session(setup[3]) as db:
  db.add(models.GithubConnection(id=uuid.uuid4(),user_id=setup[2].id,installation_id=12345,account_login='synthetic-owner',app_id=5470256,user_token=encrypted,suspended=False));db.commit()
  connection=db.scalar(select(models.GithubConnection))
  assert github.installation_token(connection)==opaque
 seen=[]
 def handler(request):
  seen.append(request.headers['Authorization']);return httpx.Response(200,json={'ok':True})
 original=httpx.Client
 monkeypatch.setattr(github.httpx,'Client',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
 assert github._api('GET','/user',token=opaque)=={'ok':True}
 assert seen==['Bearer '+opaque]
