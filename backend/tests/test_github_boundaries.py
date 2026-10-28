"""First-time mocked vendor checks; not live GitHub App/import certification."""
import os
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://test:test@127.0.0.1/test')
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from backend.app.services import github,workspaces
from backend.tests.test_native_control_plane import boundary  # Reuse existing isolated HTTP/ORM fixture


def connection(expired=False):
    return SimpleNamespace(user_token='encrypted-fixture',token_expires_at=datetime.now(timezone.utc)+timedelta(minutes=-1 if expired else 10),installation_id=42)


def test_expired_github_authorization_never_calls_vendor(monkeypatch):
    api=Mock();monkeypatch.setattr(github,'_api',api)
    with pytest.raises(HTTPException) as error:github.list_repositories(connection(expired=True))
    assert error.value.status_code==403 and api.call_count==0


def test_github_nonexpiring_token_does_not_gain_a_fabricated_expiry(monkeypatch):
    row=connection();row.token_expires_at=None;row.suspended=False;row.account_login='fixture';row.account_type='User';row.target_type='User'
    monkeypatch.setattr(github.credentials,'decrypt',lambda value:'owner-token')
    monkeypatch.setattr(github,'configured',lambda db=None:True)
    assert github.installation_token(row)=='owner-token'
    row.id='fixture-connection';row.github_user_id=101;row.github_user_login='fixture'
    assert github.connection_status(SimpleNamespace(scalar=lambda query:row,commit=lambda:None),SimpleNamespace(id='owner'))['connected'] is True


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


# The old install-first/automatic-callback assertions are superseded by the
# owner's28October explicit-confirmation policy. Security cases now exercise
# actual HTTP/ORM transactions in test_github_reconnect_security.py.
from backend.tests.test_github_reconnect_security import flow

@pytest.mark.parametrize('role',['customer','admin'])
def test_fresh_transaction_is_session_bound_for_customer_and_admin(flow,role):
    from sqlalchemy.orm import Session
    from sqlalchemy import select
    from backend.app import models
    f=flow;owner=f.owners[0]
    with Session(f.engine) as db:db.get(models.User,owner.id).role=role;db.commit()
    first=f.start();second=f.start();assert first!=second
    with Session(f.engine) as db:
        assert db.get(models.GithubAuthState,first) is None
        record=db.get(models.GithubAuthState,second)
        assert record.auth_session_id==db.scalar(select(models.AuthSession).where(models.AuthSession.user_id==owner.id)).id
        assert record.connection_id is not None
    assert not f.request('/api/github/status').json()['connected']
    assert (owner.root/'marker.txt').exists()


def test_unconfigured_new_link_never_erases_current_connection(monkeypatch):
    db=Mock()
    monkeypatch.setattr(github.github_app_config,'effective',lambda *a:SimpleNamespace())
    monkeypatch.setattr(github,'require_configured',Mock(side_effect=HTTPException(503,'Missing configuration')))
    with pytest.raises(HTTPException):github.begin_fresh_link(db,SimpleNamespace(id='fixture'),'session')
    db.execute.assert_not_called();db.commit.assert_not_called()


def test_legacy_get_entry_cannot_silently_connect_or_revoke(flow):
    f=flow;f.callback(f.start());f.confirm()
    for path in ['/api/github/authorize','/api/github/install']:
        response=f.client.get(path,headers={'Cookie':f.config.session_cookie_name+'=fixture-token-a'},follow_redirects=False);assert response.status_code==303
        assert response.headers['location'].endswith('connect-required')
    assert f.request('/api/github/status').json()['connected']


def test_only_one_github_status_route_is_registered(flow):
    paths=[route for route in flow.client.app.routes if getattr(route,'path',None)=='/api/github/status']
    assert len(paths)==1
