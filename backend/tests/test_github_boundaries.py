"""First-time mocked vendor checks; not live GitHub App/import certification."""
import os
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://test:test@127.0.0.1/test')
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from backend.app.services import github,workspaces


def connection(expired=False):
    return SimpleNamespace(user_token='encrypted-fixture',token_expires_at=datetime.now(timezone.utc)+timedelta(minutes=-1 if expired else 10),installation_id=42)


def test_expired_github_authorization_never_calls_vendor(monkeypatch):
    api=Mock();monkeypatch.setattr(github,'_api',api)
    with pytest.raises(HTTPException) as error:github.list_repositories(connection(expired=True))
    assert error.value.status_code==403 and api.call_count==0


def test_repository_and_branch_access_uses_only_connected_user_token(monkeypatch):
    api=Mock(side_effect=[{'repositories':[{'id':1,'full_name':'owned/repo','name':'repo','owner':{'login':'owned'},'default_branch':'updates','clone_url':'https://github.com/owned/repo.git'}]},[{'name':'updates','commit':{'sha':'fixture'}}]])
    monkeypatch.setattr(github,'_api',api);monkeypatch.setattr(github.credentials,'decrypt',lambda value:'owned-token-fixture')
    assert github.list_branches(connection(),'owned/repo')==[{'name':'updates','commit':'fixture'}]
    assert [c.kwargs['token'] for c in api.call_args_list]==['owned-token-fixture']*2
    assert api.call_args_list[0].args[1]=='/user/installations/42/repositories'


def test_foreign_repository_is_rejected_before_branch_lookup(monkeypatch):
    api=Mock(return_value={'repositories':[{'full_name':'owned/repo','owner':{'login':'owned'}}]})
    monkeypatch.setattr(github,'_api',api);monkeypatch.setattr(github.credentials,'decrypt',lambda value:'owned-token-fixture')
    with pytest.raises(HTTPException) as error:github.list_branches(connection(),'foreign/repo')
    assert error.value.status_code==404 and api.call_count==1


@pytest.mark.parametrize('path',['../outside','/etc','-option','.git','a/.env.production','a/../../b','a\\b'])
def test_import_working_paths_cannot_escape_or_address_secrets(path):
    with pytest.raises(HTTPException) as error:workspaces.validate_working_paths([path])
    assert error.value.status_code==422


def test_import_source_rejects_foreign_repository_before_clone(monkeypatch):
    from backend.app.routes import workspaces as routes
    monkeypatch.setattr(routes,'require_advanced',Mock())
    monkeypatch.setattr(github,'connection_for',lambda db,user:connection())
    monkeypatch.setattr(github,'authorized_repository',Mock(side_effect=HTTPException(404,'Not authorized')))
    token=Mock();monkeypatch.setattr(github,'installation_token',token)
    data=routes.CreateProject(project_name='fixture',source_type='github',repository='foreign/repo',branch='updates')
    with pytest.raises(HTTPException):routes._github_source(Mock(),SimpleNamespace(id='owner'),data)
    token.assert_not_called()
