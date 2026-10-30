"""Explicit GitHub save/delete: real Git/SQLite fixtures, mocked vendor/Native status."""
import os
os.environ.setdefault("DATABASE_URL","postgresql+psycopg://fixture:fixture@127.0.0.1/fixture")
from dataclasses import replace
from sqlalchemy.orm import Session
from sqlalchemy import select
import pytest
from backend.app import models
from backend.app.services import github,workspaces,workspace_cache
from backend.app.routes import workspaces as git_routes
from backend.tests.test_github_reconnect_security import flow
from backend.tests.test_native_control_plane import boundary

@pytest.fixture
def review(flow,monkeypatch):
    f=flow;a,b=f.owners
    monkeypatch.setattr(workspaces,'settings',replace(f.config,runtime_root=a.root.parent/'runtime'))
    monkeypatch.setattr(git_routes,'require_advanced',lambda *a,**k:None)
    monkeypatch.setattr(workspace_cache,'runtime_idle',lambda row:True)
    f.callback(f.start());f.confirm()
    remote={};revocations=[]
    monkeypatch.setattr(github,'revoke_token',lambda token,cfg,**kw:revocations.append((token,kw.get('grant',False))) or 'verified')
    monkeypatch.setattr(workspaces,'push_remote',lambda row,*a:remote.update({str(row.id):workspaces.status(row)['head']}))
    monkeypatch.setattr(github,'verify_remote_commit',lambda conn,repo,branch,sha:sha in remote.values())
    with Session(f.engine) as db:
        p=db.get(models.Project,a.project);p.source_type='github';p.repository='github-101/repo';p.github_repository_id=101;p.github_installation_id=901;p.remote_url='https://github.com/github-101/repo.git';p.remote_branch='main';db.commit()
        row=db.get(models.Workspace,a.workspace)
        workspaces.git(row,'init','--initial-branch=main')
        workspaces.git(row,'add','--all')
        workspaces.git(row,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','Initial fixture')
    def preview():return f.request('/api/github/disconnect/workspaces').json()
    def action(copy,action='save',owner=a,connection=None):
        return f.request('/api/github/disconnect/workspaces/'+copy['id'],owner,'POST',{
            'connection_id':connection or preview()['connection_id'],'snapshot':copy['snapshot'],'action':action})
    f.preview=preview;f.action=action;f.remote=remote;f.revocations=revocations
    return f


def test_save_verify_delete_then_revoke_grant_preserves_records_and_other_owner(review):
    f=review;a,b=f.owners;(a.root/'draft.txt').write_text('synthetic saved content')
    plan=f.preview();copy=plan['workspaces'][0]
    assert copy['repository']=='github-101/repo' and copy['changes']
    saved=f.action(copy);assert saved.status_code==200,saved.text
    assert saved.json()['verified'] and (a.root/'draft.txt').exists()
    copy['snapshot']=saved.json()['snapshot']
    removed=f.action(copy,'delete');assert removed.status_code==200,removed.text
    assert not a.root.exists() and (b.root/'marker.txt').read_text()=='synthetic-marker-b'
    result=f.request('/api/github/disconnect',method='POST',body={'connection_id':plan['connection_id']})
    assert result.status_code==200 and result.json()['grant_revocation']=='verified'
    assert ('token-A',True) in f.revocations
    with Session(f.engine) as db:
        assert db.get(models.Workspace,a.workspace).status=='cache_expired'
        assert db.get(models.Project,a.project) is not None
        assert db.get(models.WorkspaceSession,a.session) is not None
        assert db.scalar(select(models.AuthSession).where(models.AuthSession.user_id==a.id)) is not None


def test_dirty_or_changed_snapshot_cannot_delete(review):
    f=review;a=f.owners[0];(a.root/'draft.txt').write_text('before')
    copy=f.preview()['workspaces'][0]
    assert f.action(copy,'delete').status_code==409
    (a.root/'draft.txt').write_text('after')
    assert f.action(copy,'save').status_code==409
    assert (a.root/'draft.txt').read_text()=='after' and not f.revocations


def test_remote_failure_never_deletes_or_disconnects(review,monkeypatch):
    from fastapi import HTTPException
    f=review;a=f.owners[0];(a.root/'draft.txt').write_text('synthetic')
    monkeypatch.setattr(workspaces,'push_remote',lambda *a:(_ for _ in ()).throw(HTTPException(409,'Push rejected')))
    assert f.action(f.preview()['workspaces'][0]).status_code==409
    assert (a.root/'draft.txt').exists()
    assert f.request('/api/github/status').json()['connected'] and not f.revocations


@pytest.mark.parametrize('kind',['foreign','internal','wrong-connection','busy','ignored'])
def test_copy_cleanup_boundaries(review,monkeypatch,kind):
    f=review;a,b=f.owners;copy=f.preview()['workspaces'][0];owner=a;connection=None
    if kind=='foreign':owner=b
    if kind=='internal':
        with Session(f.engine) as db:db.get(models.Project,a.project).source_type='blank';db.commit()
    if kind=='wrong-connection':connection='00000000-0000-4000-8000-000000000001'
    if kind=='busy':monkeypatch.setattr(workspace_cache,'runtime_idle',lambda row:False)
    if kind=='ignored':
        (a.root/'.git/info/exclude').write_text('private.tmp\n');(a.root/'private.tmp').write_text('synthetic not uploaded')
        copy=f.preview()['workspaces'][0];assert copy['blocked']
    response=f.action(copy,'delete',owner,connection)
    assert response.status_code in (403,404,409)
    assert (a.root/'marker.txt').exists() and (b.root/'marker.txt').exists()


def test_plain_disconnect_keeps_files_and_renews_73_hour_grace(review):
    f=review;a=f.owners[0];(a.root/'draft.txt').write_text('not uploaded')
    result=f.request('/api/github/disconnect',method='POST')
    assert result.json()['grant_revocation']=='verified'
    assert (a.root/'draft.txt').exists()
    with Session(f.engine) as db:
        row=db.get(models.Workspace,a.workspace)
        assert row.status=='ready'
        assert workspace_cache.cache_payload(row)['retention_hours']==73
        assert not workspace_cache.github_copy_is_saved(row)


def test_disconnected_github_project_is_hidden_and_unavailable_but_copy_survives(review):
    f=review;a=f.owners[0]
    assert any(p['id']==str(a.project) for p in f.request('/api/projects').json())
    assert any(w['id']==str(a.workspace) for w in f.request('/api/workspaces').json())
    assert f.request(f'/api/workspaces/{a.workspace}/files').status_code==200
    response=f.request('/api/github/disconnect',method='POST')
    assert response.status_code==200,response.text
    assert not any(p['id']==str(a.project) for p in f.request('/api/projects').json())
    assert not any(w['id']==str(a.workspace) for w in f.request('/api/workspaces').json())
    assert f.request('/api/workspace-context').json()['workspace'] is None
    assert f.request(f'/api/workspaces/{a.workspace}/files').status_code==409
    assert f.request(f'/api/workspaces/{a.workspace}').status_code==409
    assert f.request(f'/api/projects/{a.project}').status_code==409
    assert a.root.joinpath('marker.txt').read_text()=='synthetic-marker-a'
    with Session(f.engine) as db:
        assert db.get(models.Project,a.project) is not None
        assert db.get(models.WorkspaceSession,a.session) is not None
    # Reconnecting the ORIGINAL authorized GitHub identity restores the same
    # working-copy owner UUID; it does not create a parallel customer project.
    f.callback(f.start());assert f.confirm().status_code==200
    assert f.request(f'/api/workspaces/{a.workspace}/files').status_code==200
    assert any(p['id']==str(a.project) for p in f.request('/api/projects').json())


def test_internal_project_stays_visible_when_github_is_disconnected(flow):
    f=flow;a=f.owners[0];f.callback(f.start());assert f.confirm().status_code==200
    assert f.request('/api/github/disconnect',method='POST').status_code==200
    assert any(p['id']==str(a.project) for p in f.request('/api/projects').json())
    assert f.request(f'/api/workspaces/{a.workspace}/files').status_code==200
    assert a.root.joinpath('marker.txt').exists()


def test_pending_identity_cannot_revoke_another_users_grant(flow,monkeypatch):
    f=flow;calls=[]
    monkeypatch.setattr(github,'revoke_token',lambda token,cfg,**kw:calls.append(kw.get('grant',False)) or 'verified')
    f.callback(f.start())
    assert f.request('/api/github/disconnect',method='POST').status_code==200
    assert calls==[False]


def test_retention_guard_requires_clean_fetched_head(review):
    f=review;a=f.owners[0]
    with Session(f.engine) as db:
        row=db.get(models.Workspace,a.workspace)
        assert not workspace_cache.github_copy_is_saved(row)
        head=workspaces.status(row)['head']
        workspaces.git(row,'update-ref','refs/remotes/origin/main',head)
        assert workspace_cache.github_copy_is_saved(row)
        (a.root/'draft.txt').write_text('not uploaded')
        assert not workspace_cache.github_copy_is_saved(row)


def test_grant_endpoint_and_post_revocation_check_use_only_app_basic_auth(monkeypatch):
    from types import SimpleNamespace
    calls=[]
    class Vendor:
        def __init__(self,**kwargs):assert kwargs['auth']==('fixture-client','fixture-secret')
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def request(self,method,path,**kwargs):
            calls.append((method,path,kwargs));return SimpleNamespace(status_code=204)
        def post(self,path,**kwargs):
            calls.append(('POST',path,kwargs));return SimpleNamespace(status_code=404)
    monkeypatch.setattr(github.httpx,'Client',Vendor)
    assert github.revoke_token('synthetic',SimpleNamespace(github_client_id='fixture-client',github_client_secret='fixture-secret'),grant=True)=='verified'
    assert [(m,p) for m,p,_ in calls]==[('DELETE','/applications/fixture-client/grant'),('POST','/applications/fixture-client/token')]
    assert calls[0][2]['json']=={'access_token':'synthetic'}


def test_unverified_identity_never_revokes_whole_grant(review):
    f=review;a=f.owners[0]
    with Session(f.engine) as db:
        db.scalar(select(models.GithubConnection).where(models.GithubConnection.user_id==a.id)).github_user_id=999
        db.commit()
    result=f.request('/api/github/disconnect',method='POST')
    assert result.json()['grant_revocation']=='owner-review-required'
    assert f.revocations==[('token-A',False)]
    assert (a.root/'marker.txt').exists()


def test_old_confirmation_cancel_cannot_disconnect_new_connection(flow):
    f=flow;state=f.start();f.callback(state);old=f.pending()['connection_id'];f.confirm()
    f.request('/api/github/disconnect',method='POST');f.callback(f.start());f.confirm()
    result=f.request('/api/github/disconnect',method='POST',body={'connection_id':old})
    assert result.status_code==409
    assert f.request('/api/github/status').json()['connected']


def test_invalid_token_does_not_prove_whole_grant_revoked(monkeypatch):
    from types import SimpleNamespace
    class Vendor:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def request(self,*args,**kwargs):return SimpleNamespace(status_code=404)
        def post(self,*args,**kwargs):pytest.fail('An absent token cannot verify an absent grant')
    monkeypatch.setattr(github.httpx,'Client',Vendor)
    assert github.revoke_token('synthetic',SimpleNamespace(github_client_id='fixture',github_client_secret='fixture'),grant=True)=='unconfirmed'


def test_changes_during_remote_verification_block_delete(review,monkeypatch):
    f=review;a=f.owners[0];copy=f.preview()['workspaces'][0]
    saved=f.action(copy);assert saved.status_code==200
    copy['snapshot']=saved.json()['snapshot']
    def verified(*args):
        (a.root/'late-draft.txt').write_text('synthetic late change')
        return True
    monkeypatch.setattr(github,'verify_remote_commit',verified)
    assert f.action(copy,'delete').status_code==409
    assert (a.root/'late-draft.txt').exists()
    assert f.request('/api/github/status').json()['connected']


@pytest.mark.parametrize('kind',['stash','other-branch'])
def test_unsaved_git_refs_block_explicit_and_retention_cleanup(review,kind):
    f=review;a=f.owners[0]
    with Session(f.engine) as db:
        row=db.get(models.Workspace,a.workspace)
        head=workspaces.status(row)['head']
        workspaces.git(row,'update-ref','refs/remotes/origin/main',head)
        if kind=='stash':
            (a.root/'draft.txt').write_text('synthetic stashed work')
            workspaces.git(row,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','stash','push','-u','-m','Preserve synthetic draft')
        else:
            workspaces.git(row,'branch','unsaved-work')
            (a.root/'second.txt').write_text('synthetic next commit')
            workspaces.git(row,'add','--all')
            workspaces.git(row,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','Synthetic next commit')
        assert not workspace_cache.github_copy_is_saved(row)
    copy=f.preview()['workspaces'][0];assert copy['blocked']
    assert f.action(copy,'delete').status_code==409
    assert (a.root/'.git').exists()
