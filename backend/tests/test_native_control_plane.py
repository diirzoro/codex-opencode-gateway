"""Local HTTP/ORM boundary regressions with two synthetic owners.

SQLite is used only as an isolated ORM test fixture, never as a Gateway runtime
or Native store. Native metadata is controlled; these are NOT VPS acceptance,
PostgreSQL concurrency, real registration or external credential certification.
"""
import json,os,uuid
from datetime import datetime,timedelta,timezone
from dataclasses import replace
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://fixture:fixture@127.0.0.1/fixture')
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.app import models
from backend.app.database import get_db
from backend.app.routes import native_sessions as native,workspaces as routes,github as github_routes
from backend.app.services import workspaces,policy,native_provider_accounts as providers
from backend.app.security.sessions import hash_session_token

@pytest.fixture
def boundary(monkeypatch,tmp_path):
 engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
 for model in (models.User,models.AuthSession,models.Project,models.Workspace,models.WorkspaceSession,models.AccountAudit,models.GithubConnection,models.UserProviderCredential,models.Subscription,models.PaymentOrder,models.ExecutionEvent):model.__table__.create(engine)
 now=datetime.now(timezone.utc);owners=[]
 with Session(engine) as db:
  for name in ('a','b'):
   uid,pid,wid,sid=[uuid.uuid4() for _ in range(4)]
   user=models.User(id=uid,username='fixture-'+name,email='fixture-'+name+'@example.invalid',password_hash='fixture-hash',phone='synthetic',postal_code='00000',role='customer',status='active',trial_started_at=now,trial_ends_at=now+timedelta(days=1))
   db.add(user);db.add(models.AuthSession(id=uuid.uuid4(),user_id=uid,token_hash=hash_session_token('fixture-token-'+name),expires_at=now+timedelta(hours=1),last_seen_at=now))
   db.add(models.Project(id=pid,user_id=uid,name='Synthetic '+name,source_type='blank'))
   db.add(models.Workspace(id=wid,user_id=uid,project_id=pid,status='ready'))
   db.add(models.WorkspaceSession(id=sid,user_id=uid,workspace_id=wid,opencode_session_id='ses_'+name,title='Synthetic '+name))
   root=tmp_path/str(uid)/str(wid)/'repo';root.mkdir(parents=True);(root/'marker.txt').write_text('synthetic-marker-'+name)
   owners.append(NS(name=name,id=uid,project=pid,workspace=wid,session=sid,root=root))
  db.commit()
 config=replace(native.settings,workspace_root=tmp_path,public_base_url='https://test.opencode-gateway.codes',database_url='postgresql+psycopg://fixture:fixture@127.0.0.1/opencode_gateway_test')
 monkeypatch.setenv('OPENCODE_NATIVE_TEST_ENABLED','true');monkeypatch.setattr(native,'settings',config);monkeypatch.setattr(workspaces,'settings',config)
 monkeypatch.setattr(native,'access_payload',lambda *a:{'allowed':True})
 monkeypatch.setattr(policy,'load',lambda db:NS(allowed_providers='[]',allowed_models='[]',allowed_tools='[]'))
 calls=[]
 def metadata(method,path,root,data=None):
  calls.append((method,path,str(root)))
  if path in ('/permission','/question'):return [{'id':'pending_b','sessionID':'ses_b','permission':'edit','patterns':[str(owners[1].root/'marker.txt')],'questions':[{}]}]
  if path.startswith('/session/'):
   name=path.split('/')[-1].removeprefix('ses_');entry=next(o for o in owners if o.name==name)
   return {'id':'ses_'+name,'directory':str(entry.root),'permission':[]}
  raise AssertionError((method,path))
 monkeypatch.setattr(native,'metadata',metadata)
 app=FastAPI();app.include_router(native.router);app.include_router(routes.router);app.include_router(github_routes.router)
 def database():
  with Session(engine) as db:yield db
 app.dependency_overrides[get_db]=database
 with TestClient(app) as client:yield client,owners,calls,engine,config
 engine.dispose()

def authenticated(client,path,owner,config,method='GET',body=None):
 return client.request(method,path,headers={'Cookie':config.session_cookie_name+'=fixture-token-'+owner.name,'Origin':config.public_base_url},json=body)

@pytest.mark.parametrize('kind',['project','workspace','history','native_messages','native_session','sse','files','content','export','upload','permission','question'])
def test_foreign_resources_return_404_before_transport(boundary,kind):
 client,(a,b),calls,_,config=boundary
 paths={'project':f'/api/projects/{b.project}','workspace':f'/api/workspaces/{b.workspace}', 'history':f'/api/native-test/sessions/{b.session}',
 'native_messages':f'/native-session/{a.workspace}/session/ses_b/message','native_session':f'/native-session/{a.workspace}/session/ses_b',
 'sse':f'/native-session/{b.workspace}/event','files':f'/api/workspaces/{b.workspace}/files','content':f'/api/workspaces/{b.workspace}/files/content?path=marker.txt',
 'export':f'/api/workspaces/{b.workspace}/export','upload':f'/api/workspaces/{b.workspace}/files/upload',
 'permission':f'/native-session/{a.workspace}/permission/pending_b/reply','question':f'/native-session/{a.workspace}/question/pending_b/reply'}
 if kind=='upload':
  response=client.post(paths[kind],headers={'Cookie':config.session_cookie_name+'=fixture-token-a'},files={'file':('marker.txt',b'forbidden','text/plain')})
 else:response=authenticated(client,paths[kind],a,config,'POST' if kind in {'permission','question'} else 'GET',{'reply':'once'} if kind=='permission' else {'answers':[['x']]} if kind=='question' else None)
 assert response.status_code==404,(kind,response.status_code,response.text)
 assert 'synthetic-marker-b' not in response.text
 assert not response.headers.get('x-accel-redirect')
 assert (b.root/'marker.txt').read_text()=='synthetic-marker-b'

@pytest.mark.parametrize('kind',['project','files','content','history','native_messages','sse'])
def test_owner_reads_succeed_and_cookie_switching_cannot_reuse_foreign_ids(boundary,kind):
 client,(a,b),calls,_,config=boundary
 path={'project':f'/api/projects/{a.project}','files':f'/api/workspaces/{a.workspace}/files','content':f'/api/workspaces/{a.workspace}/files/content?path=marker.txt','history':f'/api/native-test/sessions/{a.session}','native_messages':f'/native-session/{a.workspace}/session/ses_a/message','sse':f'/native-session/{a.workspace}/event'}[kind]
 good=authenticated(client,path,a,config);assert good.status_code==200,(kind,good.text)
 assert authenticated(client,path,b,config).status_code==404
 if kind in {'native_messages','sse'}:assert good.headers['x-accel-redirect']=='@native_session_test' and good.content==b''
 if kind=='content':assert good.json()['content']=='synthetic-marker-a'

@pytest.mark.parametrize('path',['../marker.txt','/etc/passwd','child/../../marker.txt','link/marker.txt'])
def test_traversal_and_synthetic_symlink_cannot_read_other_owner(boundary,path):
 client,(a,b),_,_,config=boundary;(a.root/'link').symlink_to(b.root,target_is_directory=True)
 response=client.get(f'/api/workspaces/{a.workspace}/files/content',params={'path':path},headers={'Cookie':config.session_cookie_name+'=fixture-token-a'})
 assert response.status_code in (403,422) and 'synthetic-marker-b' not in response.text

def test_provider_slot_cannot_be_claimed_or_revoked_by_second_owner(boundary,monkeypatch):
 _,(a,b),_,engine,_=boundary;marker=providers.action('fixture-provider')
 with Session(engine) as db:
  db.add(models.AccountAudit(actor_id=a.id,subject_id=a.id,action=marker));db.commit()
  call=Mock(side_effect=AssertionError('must not touch shared credentials'));monkeypatch.setattr(providers,'request',call)
  from fastapi import HTTPException
  with pytest.raises(HTTPException) as error:providers.claim(db,b,'fixture-provider',b.root)
  assert error.value.status_code==409
  with pytest.raises(HTTPException) as error:providers.disconnect(db,b,'fixture-provider')
  assert error.value.status_code==403 and not call.called

def test_native_catalog_manual_lookup_reaches_beyond_50_and_prioritizes_owner(boundary,monkeypatch):
 _,(a,b),_,engine,_=boundary;data={'all':[{'id':f'p{i:03}','name':f'Provider {i}','models':{}} for i in range(120)],'connected':['p119']}
 monkeypatch.setattr(providers,'request',lambda *args:data)
 with Session(engine) as db:
  db.add(models.AccountAudit(actor_id=a.id,subject_id=a.id,action=providers.action('p119')));db.commit()
  own=providers.catalog(db,a,a.root);foreign=providers.catalog(db,b,b.root)
  assert len(own['all'])==50 and own['all'][0]['id']=='p119' and 'p119' in own['connected']
  assert 'p119' not in foreign['connected']
  complete=providers.catalog(db,b,b.root,full=True)
  assert len(complete['all'])==120 and any(row['id']=='p119' for row in complete['all'])

def test_unauthenticated_native_access_is_401(boundary):
 client,(a,b),_,_,_=boundary
 assert client.get(f'/native-session/{a.workspace}/event').status_code==401

def test_provider_disconnect_http_denies_foreign_owner_without_touching_native(boundary,monkeypatch):
 client,(a,b),_,engine,config=boundary
 with Session(engine) as db:db.add(models.AccountAudit(actor_id=a.id,subject_id=a.id,action=providers.action('fixture-provider')));db.commit()
 call=Mock(side_effect=AssertionError('foreign native credential call'));monkeypatch.setattr(providers,'request',call)
 response=authenticated(client,'/api/opencode/connections/fixture-provider',b,config,'DELETE')
 assert response.status_code==403 and not call.called

def test_browser_role_cannot_promote_project_shell_rights(boundary):
 client,(a,b),_,_,config=boundary
 response=client.get(f'/api/native-test/sessions/{a.session}',headers={'Cookie':config.session_cookie_name+'=fixture-token-a','X-Role':'owner','X-User-ID':str(b.id)})
 assert response.status_code==200
 assert response.json()['tool_access']=={'project_manager':False,'shell_authorized':False,'shell_enabled':False,'shell_blocker':'project_manager_required'}

def test_github_connection_status_cannot_be_selected_with_other_user_id(boundary,monkeypatch):
 client,(a,b),_,engine,config=boundary
 with Session(engine) as db:
  db.add(models.GithubConnection(id=uuid.uuid4(),user_id=a.id,installation_id=123,account_login='synthetic-owner-a',account_type='User',target_type='User',suspended=False));db.commit()
 response=client.get('/api/github/status',params={'user_id':str(a.id)},headers={'Cookie':config.session_cookie_name+'=fixture-token-b'})
 assert response.status_code==200 and response.json().get('account_login')!='synthetic-owner-a'

@pytest.fixture
def permissions_boundary(boundary,monkeypatch):
 client,(a,b),calls,engine,config=boundary
 states={o.name:{'id':'ses_'+o.name,'directory':str(o.root),'permission':policy.native_session_permissions(NS(allowed_providers='[]',allowed_models='[]',allowed_tools='[]'),o.root)} for o in (a,b)}
 pending=[{'id':'pending_'+o.name,'sessionID':'ses_'+o.name,'permission':'edit','patterns':[str(o.root/'marker.txt').lstrip('/')],'always':['*']} for o in (a,b)]
 requests=[]
 def metadata(method,path,root,data=None):
  requests.append((method,path,data));owner=next(o for o in (a,b) if o.root==root)
  if path=='/path':return {'directory':str(root),'worktree':'/'}
  if path=='/permission':return pending
  if path.startswith('/session/'):
   name=path.split('/')[-1].removeprefix('ses_')
   if method=='PATCH':states[name].update(data)
   return states[name]
  raise AssertionError((method,path))
 monkeypatch.setattr(native,'metadata',metadata)
 return boundary,states,pending,requests

def test_routine_todo_and_question_use_native_allow_without_blanket_file_or_shell():
 rules=policy.native_session_permissions(NS(allowed_tools='[]',allowed_models='[]',allowed_providers='[]'),None)
 def action(name,pattern='*'):
  import fnmatch
  return next(r['action'] for r in reversed(rules) if fnmatch.fnmatchcase(name,r['permission']) and fnmatch.fnmatchcase(pattern,r['pattern']))
 for name in policy.NATIVE_AUTOMATIC_TOOLS:assert action(name)=='allow'
 for name in ('read','edit','write','glob','grep','list'):assert action(name)=='ask'
 for name in ('bash','task','execute','external_directory','unknown_mcp'):assert action(name)=='deny'
 assert action('read','.env.production')=='deny'
 restricted=policy.native_session_permissions(NS(allowed_tools='["read"]',allowed_models='[]',allowed_providers='[]'),None)
 assert not any(r['permission']=='todowrite' and r['action']=='allow' for r in restricted)

def test_owned_exact_file_grant_lives_only_in_native_session_and_survives_next_prompt(permissions_boundary):
 (client,(a,b),_,engine,config),states,pending,requests=permissions_boundary
 response=authenticated(client,f'/api/native-test/sessions/{a.session}/permissions/pending_a/remember',a,config,'POST')
 assert response.status_code==200,response.text
 assert response.json()['scope']=='next-prompts-in-this-conversation'
 grant={'permission':'edit','pattern':pending[0]['patterns'][0],'action':'allow'}
 assert grant in states['a']['permission'] and grant not in states['b']['permission']
 with Session(engine) as db:
  workspace=db.get(models.Workspace,a.workspace)
  assert grant in native.session_permissions(db,workspace,a.root,states['a'])
 assert not any(path.endswith('/reply') for _,path,_ in requests) # original current reply stays Native/Nginx
 assert not any(data and data.get('reply')=='always' for _,_,data in requests)

@pytest.mark.parametrize('kind',['foreign_session','foreign_pending','wildcard','foreign_path','symlink','secret','config','directory','shell','policy','traversal','no_origin'])
def test_remember_file_permission_rejects_unsafe_scope_without_native_patch(permissions_boundary,kind,monkeypatch):
 (client,(a,b),_,engine,config),states,pending,requests=permissions_boundary
 session=a.session;permission='pending_a';item=pending[0]
 if kind=='foreign_session':session=b.session
 if kind=='foreign_pending':permission='pending_b'
 if kind=='wildcard':item['patterns']=['*']
 if kind=='foreign_path':item['patterns']=[str(b.root/'marker.txt')]
 if kind=='symlink':(a.root/'link').symlink_to(b.root/'marker.txt');item['patterns']=[str(a.root/'link')]
 if kind=='secret':item['patterns']=[str(a.root/'.env.production')]
 if kind=='config':item['patterns']=[str(a.root/'opencode.json')]
 if kind=='directory':item['patterns']=[str(a.root)]
 if kind=='shell':item['permission']='bash'
 if kind=='policy':monkeypatch.setattr(policy,'load',lambda db:NS(allowed_providers='[]',allowed_models='[]',allowed_tools='["read"]'))
 if kind=='traversal':item['patterns']=[str(a.root/'..'/'outside')]
 path=f'/api/native-test/sessions/{session}/permissions/{permission}/remember'
 response=client.post(path,headers={'Cookie':config.session_cookie_name+'=fixture-token-a'}) if kind=='no_origin' else authenticated(client,path,a,config,'POST')
 assert response.status_code==(404 if kind in {'foreign_session','foreign_pending'} else 403),(kind,response.text)
 assert not any(method=='PATCH' for method,_,_ in requests)

def test_stale_or_broad_native_grants_are_removed_and_path_metadata_is_coalesced(permissions_boundary):
 (_, (a,b),_,engine,_),states,pending,requests=permissions_boundary
 good={'permission':'read','pattern':str(a.root/'marker.txt').lstrip('/'),'action':'allow'}
 states['a']['permission'] += [good,{'permission':'edit','pattern':'*','action':'allow'},{'permission':'read','pattern':str(b.root/'marker.txt'),'action':'allow'}]
 with Session(engine) as db:
  workspace=db.get(models.Workspace,a.workspace)
  before=len([r for r in requests if r[1]=='/path']);rules=native.session_permissions(db,workspace,a.root,states['a'])
  assert len([r for r in requests if r[1]=='/path'])-before==1
  assert [r for r in rules if r['action']=='allow' and r['permission'] in policy.NATIVE_FILE_TOOLS]==[good]
  (a.root/'marker.txt').unlink();(a.root/'marker.txt').symlink_to(b.root/'marker.txt')
  assert good not in native.session_permissions(db,workspace,a.root,{'permission':rules})
