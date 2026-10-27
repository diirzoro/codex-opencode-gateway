"""Explicit GitHub working-copy erasure; isolated files/ORM, never TEST data."""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from backend.tests.test_native_control_plane import boundary, authenticated
from backend.app import models
from backend.app.services import github, workspace_cache as cache, workspaces, opencode
from backend.app.routes import native_sessions

original_runtime_idle=cache.runtime_idle

@pytest.fixture
def copies(boundary, monkeypatch):
    client,(owner,other),_,engine,config=boundary
    models.GithubAuthState.__table__.create(engine)
    monkeypatch.setattr(cache,'SessionLocal',sessionmaker(bind=engine))
    monkeypatch.setattr(cache,'runtime_idle',lambda row:True)
    monkeypatch.setattr(opencode,'stop_workspace',Mock(side_effect=AssertionError('Never stop shared Native')))
    monkeypatch.setattr(github,'configured',lambda *a:True)
    local_pid,local_wid=uuid.uuid4(),uuid.uuid4()
    with Session(engine) as db:
        db.get(models.Project,owner.project).source_type='github'
        db.get(models.Project,other.project).source_type='github'
        db.add(models.Project(id=local_pid,user_id=owner.id,name='Local published later',source_type='blank',repository='fixture/local',remote_url='https://github.com/fixture/local.git'))
        db.add(models.Workspace(id=local_wid,user_id=owner.id,project_id=local_pid,status='ready'))
        for account,i in [(owner,801),(other,802)]:
            db.add(models.GithubConnection(user_id=account.id,installation_id=i,account_login='synthetic',user_token='encrypted-fixture',suspended=False))
            db.add(models.GithubAuthState(state='old-'+account.name,user_id=account.id,expires_at=datetime.now(timezone.utc)+timedelta(minutes=5)))
        db.commit()
    local=config.workspace_root/str(owner.id)/str(local_wid)/'repo'
    local.mkdir(parents=True);(local/'local.txt').write_text('keep-local')
    return client,owner,other,engine,config,local,local_wid

def test_explicit_disconnect_erases_only_owned_imported_copies_and_preserves_records(copies):
    client,owner,other,engine,config,local,local_wid=copies
    response=authenticated(client,'/api/github/disconnect',owner,config,'POST')
    assert response.status_code==204,response.text
    assert not owner.root.exists()
    assert (local/'local.txt').read_text()=='keep-local'
    assert (other.root/'marker.txt').read_text()=='synthetic-marker-b'
    with Session(engine) as db:
        assert db.get(models.Workspace,owner.workspace).status=='cache_expired'
        assert db.get(models.Workspace,local_wid).status=='ready'
        assert db.get(models.WorkspaceSession,owner.session) is not None
        assert db.get(models.Project,owner.project) is not None
        assert db.scalar(select(models.GithubConnection).where(models.GithubConnection.user_id==other.id)) is not None
        assert db.scalar(select(models.GithubAuthState).where(models.GithubAuthState.state=='old-b')) is not None
    assert authenticated(client,f'/api/workspaces/{owner.workspace}/files',owner,config).status_code==410
    assert authenticated(client,f'/api/native-test/sessions/{owner.session}',owner,config).status_code==410
    assert authenticated(client,'/api/github/disconnect',owner,config,'POST').status_code==204

def test_busy_native_defers_erasure_with_committed_file_barrier_and_existing_retry(copies, monkeypatch):
    client,owner,other,engine,config,local,_=copies
    monkeypatch.setattr(cache,'runtime_idle',lambda row:False)
    assert authenticated(client,'/api/github/disconnect',owner,config,'POST').status_code==204
    assert owner.root.exists()
    with Session(engine) as db:
        assert db.get(models.Workspace,owner.workspace).status=='cache_expiring'
        assert db.scalar(select(models.GithubConnection).where(models.GithubConnection.user_id==owner.id)) is None
    assert authenticated(client,f'/api/workspaces/{owner.workspace}/files',owner,config).status_code==410
    monkeypatch.setattr(cache,'runtime_idle',lambda row:True)
    monkeypatch.setattr(cache,'_policy_started',datetime.now(timezone.utc))
    assert cache.sweep()==1
    assert not owner.root.exists() and local.exists() and other.root.exists()

def test_failed_erase_stays_blocked_and_retries_without_restoring_credentials(copies, monkeypatch):
    client,owner,_,engine,config,local,_=copies
    real=cache.shutil.rmtree
    monkeypatch.setattr(cache.shutil,'rmtree',Mock(side_effect=OSError('controlled failure')))
    assert authenticated(client,'/api/github/disconnect',owner,config,'POST').status_code==204
    with Session(engine) as db:
        assert db.get(models.Workspace,owner.workspace).status=='cache_expiring'
    assert owner.root.exists() and local.exists()
    monkeypatch.setattr(cache.shutil,'rmtree',real)
    assert cache.sweep(workspace_ids=[owner.workspace])==1
    assert not owner.root.exists()

def test_fresh_link_is_not_an_explicit_file_removal(copies,monkeypatch):
    _,owner,_,engine,config,local,_=copies
    cfg=SimpleNamespace(github_web_base='https://github.com',github_client_id='fixture',github_callback_url=config.public_base_url+'/api/github/callback')
    monkeypatch.setattr(github.github_app_config,'effective',lambda *a:cfg)
    monkeypatch.setattr(github,'require_configured',lambda *a:None)
    with Session(engine) as db:
        github.begin_fresh_link(db,db.get(models.User,owner.id))
        assert db.get(models.Workspace,owner.workspace).status=='ready'
    assert owner.root.exists() and local.exists()

def test_commit_failure_never_erases_working_copy(copies,monkeypatch):
    _,owner,_,engine,_,local,_=copies
    with Session(engine) as db:
        monkeypatch.setattr(db,'commit',Mock(side_effect=RuntimeError('controlled SQL failure')))
        with pytest.raises(RuntimeError):github.disconnect(db,db.get(models.User,owner.id))
        db.rollback()
        assert db.get(models.Workspace,owner.workspace).status=='ready'
        assert db.scalar(select(models.GithubConnection).where(models.GithubConnection.user_id==owner.id)) is not None
    assert owner.root.exists() and local.exists()

def test_symlink_copy_cannot_erase_target_or_internal_project(copies):
    client,owner,_,engine,config,local,_=copies
    # Controlled target: move original data aside, then point to owned local data.
    saved=owner.root.with_name('saved-fixture');owner.root.rename(saved);owner.root.symlink_to(local,target_is_directory=True)
    assert authenticated(client,'/api/github/disconnect',owner,config,'POST').status_code==204
    assert owner.root.is_symlink() and (local/'local.txt').read_text()=='keep-local'
    with Session(engine) as db:assert db.get(models.Workspace,owner.workspace).status=='cache_expiring'

@pytest.mark.parametrize('statuses,expected', [({},True),({'s':{'type':'busy'}},False),({'s':{'type':'retry'}},False),([],False)])
def test_native_idle_requires_native_status_not_disabled_legacy_runtime(boundary,monkeypatch,statuses,expected):
    _,(owner,_),_,engine,_=boundary
    monkeypatch.setattr(native_sessions,'metadata',lambda method,path,root:statuses)
    monkeypatch.setattr(opencode,'for_workspace',Mock(side_effect=AssertionError('No legacy runtime')))
    with Session(engine) as db:assert cache.runtime_idle(db.get(models.Workspace,owner.workspace)) is expected


def test_signed_webhook_lifecycle_reuses_same_scoped_cleanup(copies):
    _,owner,other,engine,_,local,_=copies
    with Session(engine) as db:
        github.handle_webhook(db,'installation',{'installation':{'id':801},'action':'deleted'})
        assert db.scalar(select(models.GithubConnection).where(models.GithubConnection.user_id==owner.id)) is None
    assert not owner.root.exists() and other.root.exists() and local.exists()


def test_native_metadata_error_defers_cleanup_instead_of_assuming_idle(copies,monkeypatch):
    client,owner,_,engine,config,local,_=copies
    # Exercise real Native idle checker rather than a legacy process fallback.
    monkeypatch.setattr(cache,'runtime_idle',original_runtime_idle)
    monkeypatch.setattr(native_sessions,'metadata',Mock(side_effect=HTTPException(502,'controlled unavailable metadata')))
    assert authenticated(client,'/api/github/disconnect',owner,config,'POST').status_code==204
    assert owner.root.exists() and local.exists()
    with Session(engine) as db:assert db.get(models.Workspace,owner.workspace).status=='cache_expiring'


def test_admin_disconnect_uses_same_policy_and_customer_cannot_invoke_it(copies):
    client,owner,other,engine,config,local,_=copies
    from backend.app.routes import management
    client.app.include_router(management.router)
    route='/api/admin/connections/'+str(other.id)
    assert authenticated(client,route,owner,config,'DELETE').status_code==403
    assert owner.root.exists() and other.root.exists()
    with Session(engine) as db:
        db.get(models.User,owner.id).role='admin';db.commit()
    assert authenticated(client,route,owner,config,'DELETE').status_code==204
    assert not other.root.exists() and owner.root.exists() and local.exists()


def test_cleanup_status_never_initializes_untrusted_native_configuration(copies,monkeypatch):
    client,owner,_,engine,config,local,_=copies
    (owner.root/'opencode.json').write_text('{"synthetic": true}')
    monkeypatch.setattr(cache,'runtime_idle',original_runtime_idle)
    native_read=Mock(side_effect=AssertionError('Untrusted Native configuration must not initialize'))
    monkeypatch.setattr(native_sessions,'metadata',native_read)
    assert authenticated(client,'/api/github/disconnect',owner,config,'POST').status_code==204
    native_read.assert_not_called()
    assert owner.root.exists() and local.exists()
    with Session(engine) as db:assert db.get(models.Workspace,owner.workspace).status=='cache_expiring'
