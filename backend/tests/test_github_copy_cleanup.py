"""28October owner policy: disconnect must preserve workspaces and unpushed data.

Supersedes the earlier explicit-erasure tests; retention maintenance is independent.
"""
import uuid
from types import SimpleNamespace
from sqlalchemy import select
from sqlalchemy.orm import Session
import pytest
from backend.app import models
from backend.app.services import github,workspace_cache
from backend.tests.test_github_reconnect_security import flow
from backend.tests.test_native_control_plane import boundary

@pytest.mark.parametrize('source',['github','blank','template'])
@pytest.mark.parametrize('operation',['disconnect','reconnect'])
def test_connection_cleanup_preserves_every_owned_project_type_and_foreign_files(flow,monkeypatch,source,operation):
    f=flow;a,b=f.owners
    with Session(f.engine) as db:db.get(models.Project,a.project).source_type=source;db.commit()
    (a.root/'uncommitted.txt').write_text('synthetic-unpushed-change')
    (a.root/'symlink').symlink_to(b.root,target_is_directory=True)
    monkeypatch.setattr(workspace_cache,'expire_github_copies',lambda *a,**kw:pytest.fail('Disconnect cannot expire project files'))
    monkeypatch.setattr(workspace_cache,'sweep',lambda *a,**kw:pytest.fail('Disconnect cannot erase project files'))
    f.callback(f.start());f.confirm()
    if operation=='disconnect':assert f.request('/api/github/disconnect',method='POST').status_code==200
    else:
        assert f.request('/api/github/connect',method='POST').status_code==409
        assert f.request('/api/github/disconnect',method='POST').status_code==200
        f.start()
    assert (a.root/'uncommitted.txt').read_text()=='synthetic-unpushed-change'
    assert (b.root/'marker.txt').read_text()=='synthetic-marker-b'
    with Session(f.engine) as db:
        assert db.get(models.Workspace,a.workspace).status=='ready'
        assert db.get(models.Project,a.project) is not None
        assert db.get(models.WorkspaceSession,a.session) is not None


def test_invalid_encrypted_credential_is_removed_without_deleting_files(flow):
    f=flow;a=f.owners[0]
    with Session(f.engine) as db:db.add(models.GithubConnection(user_id=a.id,installation_id=999,account_login='synthetic',user_token='broken'));db.commit()
    f.request('/api/github/disconnect',method='POST')
    with Session(f.engine) as db:assert db.scalar(select(models.GithubConnection).where(models.GithubConnection.user_id==a.id)) is None
    assert (a.root/'marker.txt').exists()


@pytest.mark.parametrize('target_type,actor_id,account_id',[('Organization',101,101),('User',102,101),('User',101,102)])
def test_app_jwt_cannot_uninstall_unproved_or_foreign_installation(monkeypatch,target_type,actor_id,account_id):
    calls=[]
    def api(method,path,**kw):
        calls.append(method)
        return {'id':actor_id} if path=='/user' else {'app_id':42,'account':{'id':account_id,'type':target_type}}
    monkeypatch.setattr(github,'_api',api);monkeypatch.setattr(github,'_jwt',lambda *a:'synthetic')
    row=SimpleNamespace(installation_id=901,github_user_id=101)
    assert github.remove_owned_installation(row,'synthetic',SimpleNamespace(github_app_id=42))=='owner-review-required'
    assert 'DELETE' not in calls


def test_verified_personal_installation_delete_is_checked_afterward(monkeypatch):
    from fastapi import HTTPException
    deleted=[]
    def api(method,path,**kw):
        if path=='/user':return {'id':101}
        if method=='DELETE':deleted.append(901);return None
        if deleted:raise HTTPException(404,'Already removed')
        return {'app_id':42,'account':{'id':101,'type':'User'}}
    monkeypatch.setattr(github,'_api',api);monkeypatch.setattr(github,'_jwt',lambda *a:'synthetic')
    assert github.remove_owned_installation(SimpleNamespace(installation_id=901,github_user_id=101),'synthetic',SimpleNamespace(github_app_id=42))=='verified'
    assert deleted==[901]
