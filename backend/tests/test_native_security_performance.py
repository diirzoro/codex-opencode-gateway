"""Small Native control-plane regressions; synthetic HTTP/ORM/files only."""
import os
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://fixture:fixture@127.0.0.1/fixture')
import asyncio, fnmatch, json, uuid, zipfile
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock
import httpx, pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy.orm import Session
from backend.tests.test_native_control_plane import boundary, permissions_boundary, authenticated
from backend.app import models
from backend.app.routes import native_sessions as native
from backend.app.services import workspaces,policy,native_catalog_maintenance as maintenance

@pytest.mark.parametrize('name',['.env.production','auth.json','credentials.json','private.key','PRIVATE.PEM','.aws/token','.config/private'])
def test_protected_files_are_denied_and_not_listed(boundary,name):
 client,(owner,_),_,engine,config=boundary
 target=owner.root/name;target.parent.mkdir(exist_ok=True);target.write_text('synthetic-protected')
 response=authenticated(client,f'/api/workspaces/{owner.workspace}/files/content?path={name}',owner,config)
 assert response.status_code==403 and 'synthetic-protected' not in response.text
 listing=authenticated(client,f'/api/workspaces/{owner.workspace}/files',owner,config)
 assert name.split('/')[0] not in [entry['name'] for entry in listing.json()]
 with Session(engine) as db:
  archive=workspaces.export(db.get(models.Workspace,owner.workspace))
 try:
  with zipfile.ZipFile(archive) as z:assert name not in z.namelist() and 'marker.txt' in z.namelist()
 finally:archive.unlink()

@pytest.mark.parametrize('name',['private.key','auth.json','.aws/token'])
def test_native_permission_cannot_approve_a_protected_file(permissions_boundary,name):
 (client,(owner,_),_,_,config),_,pending,requests=permissions_boundary
 pending[0]['patterns']=[str(owner.root/name).lstrip('/')]
 response=authenticated(client,f'/native-session/{owner.workspace}/permission/pending_a/reply',owner,config,'POST',{'reply':'once'})
 assert response.status_code==403
 assert not any(method=='PATCH' for method,_,_ in requests)

@pytest.mark.parametrize('kind',['project','session','auth'])
def test_revocation_is_immediate_between_requests(boundary,kind):
 client,(owner,other),_,engine,config=boundary
 path=f'/native-session/{owner.workspace}/session/ses_a/message'
 assert authenticated(client,path,owner,config).status_code==200
 with Session(engine) as db:
  if kind=='project':db.get(models.Project,owner.project).user_id=other.id
  elif kind=='session':db.get(models.WorkspaceSession,owner.session).user_id=other.id
  else:
   from datetime import datetime,timezone
   from sqlalchemy import select
   db.scalar(select(models.AuthSession).where(models.AuthSession.user_id==owner.id)).revoked_at=datetime.now(timezone.utc)
  db.commit()
 assert authenticated(client,path,owner,config).status_code==(401 if kind=='auth' else 404)


def test_quota_is_fresh_counts_regular_files_and_ignores_external_symlinks(boundary):
 _,(owner,other),_,engine,_=boundary
 (other.root/'huge').write_bytes(b'x')
 (owner.root/'outside').symlink_to(other.root,target_is_directory=True)
 (owner.root/'outside-file').symlink_to(other.root/'huge')
 with Session(engine) as db:
  row=db.get(models.Workspace,owner.workspace)
  assert workspaces.usage_bytes(row)==len('synthetic-marker-a')
  workspaces.require_quota_headroom(row)
  with (owner.root/'huge.bin').open('wb') as handle:handle.truncate(workspaces.quota_bytes(row)+1)
  with pytest.raises(HTTPException) as error:workspaces.require_quota_headroom(row)
  assert error.value.status_code==413


def test_fifty_megabytes_is_per_client_total_of_local_projects(boundary):
    _,(a,b),_,engine,_=boundary
    from sqlalchemy.orm import Session
    import uuid
    with Session(engine) as db:
        second=models.Project(id=uuid.uuid4(),user_id=a.id,name='Second local',source_type='blank')
        ws=models.Workspace(id=uuid.uuid4(),user_id=a.id,project=second,status='ready')
        db.add_all([second,ws]);db.commit()
        second_root=workspaces.root_for(ws)
        second_root.mkdir(parents=True,exist_ok=True)
        with (a.root/'one.data').open('wb') as f:f.truncate(30*1048576)
        with (second_root/'two.data').open('wb') as f:f.truncate(19*1048576)
        own=workspaces.account_local_storage_payload(db,a.id)
        foreign=workspaces.account_local_storage_payload(db,b.id)
        assert own['limit_bytes']==50*1048576
        assert own['used_bytes']>=49*1048576
        assert foreign['used_bytes']<1048576
        assert foreign['limit_bytes']==own['limit_bytes']
        # The second project still counts against owner A, not owner B.
        with pytest.raises(HTTPException) as error:
            workspaces.require_account_local_headroom(db,a.id,2*1048576)
        assert error.value.status_code==413
        workspaces.require_account_local_headroom(db,b.id,2*1048576)
        other=models.Project(id=uuid.uuid4(),user_id=a.id,name='Imported source',source_type='github')
        source=models.Workspace(id=uuid.uuid4(),user_id=a.id,project=other,status='ready')
        db.add_all([other,source]);db.flush()
        foreign_copy=workspaces.root_for(source);foreign_copy.mkdir(parents=True,exist_ok=True)
        with (foreign_copy/'source.data').open('wb') as f:f.truncate(60*1048576)
        assert workspaces.account_local_storage_payload(db,a.id)['used_bytes']==own['used_bytes']
        with (second_root/'two.data').open('wb') as f:f.truncate(1*1048576)
        workspaces.require_account_local_headroom(db,a.id,2*1048576)


def test_local_storage_endpoint_displays_account_total_not_just_current_workspace(boundary):
    client,(a,b),_,engine,config=boundary
    from sqlalchemy.orm import Session
    with (a.root/'size.data').open('wb') as f:f.truncate(2*1048576)
    own=authenticated(client,f'/api/workspaces/{a.workspace}/storage',a,config)
    assert own.status_code==200,own.text
    assert own.json()['scope']=='account_local_projects'
    assert own.json()['limit_mb']==50
    assert own.json()['used_bytes']>=2*1048576
    other=authenticated(client,f'/api/workspaces/{b.workspace}/storage',b,config)
    assert other.status_code==200
    assert other.json()['used_bytes']<1048576
    assert authenticated(client,f'/api/workspaces/{b.workspace}/storage',a,config).status_code==404


def test_storage_scan_failure_cannot_admit_execution(boundary,monkeypatch):
 _,(owner,_),_,engine,_=boundary
 monkeypatch.setattr(workspaces.os,'fwalk',Mock(side_effect=PermissionError('synthetic denied')))
 with Session(engine) as db:
  with pytest.raises(HTTPException) as error:workspaces.require_quota_headroom(db.get(models.Workspace,owner.workspace))
 assert error.value.status_code==503


def test_unknown_tools_shell_and_secrets_stay_denied():
 rules=policy.native_session_permissions(NS(allowed_tools='[]',allowed_models='[]',allowed_providers='[]'),Path('/synthetic'))
 for tool,path in [('bash','*'),('task','*'),('unknown_mcp','*'),('read','dir/auth.json'),('edit','private.key'),('read','.aws/token')]:
  last=next(r for r in reversed(rules) if fnmatch.fnmatchcase(tool,r['permission']) and fnmatch.fnmatchcase(path,r['pattern']))
  assert last['action']=='deny'


def test_native_merged_session_permission_suffix_is_authoritative():
    from pathlib import Path
    root=Path('/synthetic-owned-workspace')
    expected=policy.native_session_permissions(NS(allowed_tools='[]',allowed_models='[]',allowed_providers='[]'),root)
    assert native.native_restrictions_persisted({'permission':expected},expected)
    assert native.native_restrictions_persisted({'permission':[
        {'permission':'bash','pattern':'*','action':'allow'},*expected]},expected)
    assert not native.native_restrictions_persisted({'permission':[
        *expected,{'permission':'bash','pattern':'*','action':'allow'}]},expected)
    assert not native.native_restrictions_persisted({'permission':expected[:-1]},expected)
    assert not native.native_restrictions_persisted({'permission':None},expected)


def test_native_patch_merge_survives_authoritative_read(monkeypatch):
    from pathlib import Path
    root=Path('/synthetic-owned-workspace')
    rules=[{'permission':'*','pattern':'*','action':'deny'},
           {'permission':'read','pattern':'*','action':'ask'},
           {'permission':'bash','pattern':'*','action':'deny'}]
    old=[{'permission':'bash','pattern':'*','action':'allow'}]
    stored=list(old)
    methods=[]
    def metadata(method,path,directory,data=None):
        methods.append(method)
        if method=='PATCH':
            stored.extend(data['permission'])
            return {'id':'ses_owned','directory':str(root),'permission':old}
        return {'id':'ses_owned','directory':str(root),'permission':list(stored)}
    monkeypatch.setattr(native,'metadata',metadata)
    result=native.confirm_native_session_restrictions('ses_owned',root,rules)
    assert native.native_restrictions_persisted(result,rules)
    assert methods==['PATCH','GET']
    assert len(result['permission'])==len(old)+len(rules)


def test_native_policy_patch_uses_confirmed_read_not_stale_patch_response(monkeypatch):
    from pathlib import Path
    root=Path('/synthetic-owned-workspace')
    required=[{'permission':'*','pattern':'*','action':'deny'},
              {'permission':'read','pattern':'*','action':'ask'}]
    actual={'id':'ses_owned','directory':str(root),'permission':[]}
    calls=[]
    def metadata(method,path,directory,data=None):
        calls.append((method,path))
        if method=='PATCH':
            actual.update(data)
            return {'id':'ses_owned','directory':str(root),'permission':[]}  # stale ACK
        return dict(actual)
    monkeypatch.setattr(native,'metadata',metadata)
    confirmed=native.confirm_native_session_restrictions('ses_owned',root,required)
    assert confirmed['permission']==required
    assert [kind for kind,_ in calls]==['PATCH','GET']


@pytest.mark.parametrize('kind',['ignored','foreign','missing'])
def test_native_policy_rejection_is_fail_closed_even_after_http200_ack(monkeypatch,kind):
    from pathlib import Path
    root=Path('/synthetic-owned-workspace')
    required=[{'permission':'bash','pattern':'*','action':'deny'}]
    actual={'id':'ses_owned','directory':str(root),'permission':[]}
    calls=[]
    def metadata(method,path,directory,data=None):
        calls.append((method,path))
        if method=='PATCH':
            if kind=='foreign':actual['directory']='/other-customer'
            if kind=='missing':actual['id']='ses_other'
            # This successful PATCH response is NOT proof of actual persistence.
            return {'id':'ses_owned','directory':str(root),'permission':required}
        return dict(actual)
    monkeypatch.setattr(native,'metadata',metadata)
    with pytest.raises(HTTPException) as error:
        native.confirm_native_session_restrictions('ses_owned',root,required)
    assert error.value.status_code==503
    assert 'not forwarded' in error.value.detail
    assert [kind for kind,_ in calls]==['PATCH','GET']


def test_metadata_connection_is_reused_only_within_one_authorization(monkeypatch):
 real=httpx.Client;created=[];requests=[]
 def handler(request):
  requests.append(request)
  return httpx.Response(200,json={'id':'synthetic'})
 def factory(**kwargs):
  assert kwargs['trust_env'] is False
  client=real(**kwargs,transport=httpx.MockTransport(handler));created.append(client);return client
 monkeypatch.setattr(native.httpx,'Client',factory)
 def authorize(*args):
  native.metadata('GET','/session/ses_fixture',Path('/synthetic'))
  native.metadata('GET','/experimental/tool/ids',Path('/synthetic'))
  return Response(headers={'X-Accel-Redirect':'@native_session_test'})
 monkeypatch.setattr(native,'_authorize_native',authorize)
 for _ in range(2):native.authorize_native(None,'session/ses_fixture/message',None,None,None,b'')
 assert len(created)==2 and all(c.is_closed for c in created)
 assert len(requests)==4 and all(r.url.host=='127.0.0.1' for r in requests)
 assert native._metadata_request.get() is None


def test_expired_authorization_never_forwards_to_native(monkeypatch):
 clock=[0.0];monkeypatch.setattr(native.time,'monotonic',lambda:clock[0])
 def authorize(*args):
  clock[0]=21
  return Response(headers={'X-Accel-Redirect':'@native_session_test'})
 monkeypatch.setattr(native,'_authorize_native',authorize)
 with pytest.raises(HTTPException) as error:native.authorize_native(None,'session/ses_fixture/prompt_async',None,None,None,b'')
 assert error.value.status_code==504 and native._metadata_request.get() is None


def test_cancelled_browser_cannot_forward_an_authorized_write(monkeypatch):
 monkeypatch.setattr(native,'admit',lambda user:None)
 events=[{'type':'http.request','body':b'{}','more_body':False},{'type':'http.disconnect'}]
 async def receive():return events.pop(0) if events else {'type':'http.disconnect'}
 request=Request({'type':'http','method':'POST','headers':[]},receive)
 async def authorize(*args):return Response(headers={'X-Accel-Redirect':'@native_session_test'})
 monkeypatch.setattr(native,'run_in_threadpool',authorize)
 with pytest.raises(HTTPException) as error:asyncio.run(native.transport(uuid.uuid4(),'session/ses_fixture/abort',request,NS(id='synthetic'),None))
 assert error.value.status_code==408
 assert error.value.headers['X-Native-Request-Outcome']=='not-forwarded'


@pytest.mark.parametrize('status',[403,408,413,502,503,504])
def test_transport_refusal_is_explicitly_not_forwarded(boundary,monkeypatch,status):
 client,(owner,_),_,_,config=boundary
 def refuse(*args):raise HTTPException(status,'Synthetic authorization failure',headers={'Retry-After':'2'})
 monkeypatch.setattr(native,'authorize_native',refuse)
 response=authenticated(client,f'/native-session/{owner.workspace}/session/ses_a/prompt_async',owner,config,'POST',{'parts':[{'type':'text','text':'synthetic'}]})
 assert response.status_code==status
 assert response.headers['x-native-request-outcome']=='not-forwarded'
 assert response.headers['retry-after']=='2'
 assert response.json()['detail']=='Synthetic authorization failure'
 assert 'x-accel-redirect' not in response.headers


def test_successful_native_forward_has_no_rejection_marker(boundary):
 client,(owner,_),_,_,config=boundary
 response=authenticated(client,f'/native-session/{owner.workspace}/session/ses_a/message',owner,config)
 assert response.status_code==200 and response.headers['x-accel-redirect']=='@native_session_test'
 assert 'x-native-request-outcome' not in response.headers


def test_catalog_initialization_and_7_14_schedule_do_not_download(monkeypatch,tmp_path):
 monkeypatch.setattr(maintenance,'settings',NS(runtime_root=tmp_path))
 monkeypatch.setattr(maintenance,'test_scope',lambda:None)
 monkeypatch.setattr(maintenance,'public',lambda value,*args:value)
 clock=1000.0;monkeypatch.setattr(maintenance.time,'time',lambda:clock)
 refresh=Mock(side_effect=AssertionError('No download on initialization/read'))
 monkeypatch.setattr(maintenance,'refresh',refresh)
 assert maintenance.load()['interval_days']==7
 maintenance.sweep();value=maintenance.load();assert value['next_attempt_at']==clock+7*86400
 maintenance.configure(14);assert maintenance.load()['next_attempt_at']==clock+14*86400
 maintenance.sweep();refresh.assert_not_called()
 with pytest.raises(HTTPException):maintenance.configure(8)
