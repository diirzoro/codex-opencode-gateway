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


def test_github_nonexpiring_token_does_not_gain_a_fabricated_expiry(monkeypatch):
    row=connection();row.token_expires_at=None;row.suspended=False;row.account_login='fixture';row.account_type='User';row.target_type='User'
    monkeypatch.setattr(github.credentials,'decrypt',lambda value:'owner-token')
    monkeypatch.setattr(github,'configured',lambda db=None:True)
    assert github.installation_token(row)=='owner-token'
    assert github.connection_status(SimpleNamespace(scalar=lambda query:row),SimpleNamespace(id='owner'))['connected'] is True


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


def test_reauthorization_starts_user_oauth_without_reinstall(monkeypatch):
    from urllib.parse import urlparse, parse_qs
    import uuid
    cfg=SimpleNamespace(github_web_base='https://github.com',github_client_id='IvTestReauth',
                        github_callback_url='https://test.example/api/github/callback')
    monkeypatch.setattr(github.github_app_config,'effective',lambda *a:cfg)
    monkeypatch.setattr(github,'require_configured',lambda *a:None)
    added=[]
    db=SimpleNamespace(add=added.append,commit=lambda:None)
    owner=SimpleNamespace(id=uuid.uuid4())
    url=github.begin_authorization(db,owner)
    parsed=urlparse(url);args=parse_qs(parsed.query)
    assert parsed.path=='/login/oauth/authorize'
    assert args['client_id']==['IvTestReauth']
    assert args['redirect_uri']==[cfg.github_callback_url]
    assert len(args['state'][0])>=30
    assert len(added)==1 and added[0].user_id==owner.id
    assert added[0].state==args['state'][0]


def _reauthorization_context(monkeypatch,installations):
    import uuid
    cfg=SimpleNamespace(github_app_id=5470256)
    monkeypatch.setattr(github.github_app_config,'effective',lambda *a:cfg)
    monkeypatch.setattr(github,'require_configured',lambda *a:None)
    monkeypatch.setattr(github,'require_advanced',lambda *a,**kw:None)
    monkeypatch.setattr(github,'exchange_code',lambda *a,**kw:{'access_token':'synthetic-user-token'})
    monkeypatch.setattr(github,'_jwt',lambda *a:'synthetic-jwt')
    monkeypatch.setattr(github.credentials,'encrypt',lambda t:'encrypted-synthetic-token')
    def api(method,path,**kwargs):
        if path=='/user/installations':
            return {'installations':installations}
        if path.startswith('/app/installations/'):
            return {'app_id':5470256,'account':{'login':'fixture-owner','type':'User'},'target_type':'User'}
        raise AssertionError('unexpected GitHub API route: '+path)
    monkeypatch.setattr(github,'_api',api)
    uid=uuid.uuid4()
    state=SimpleNamespace(user_id=uid,consumed=False,expires_at=datetime.now(timezone.utc)+timedelta(minutes=5))
    class Database:
        def __init__(self):
            self.lookups=0
            self.added=[]
        def scalar(self,statement):
            self.lookups+=1
            if self.lookups==1:return state
            return None
        def get(self,model,identifier):
            assert identifier==uid
            return SimpleNamespace(id=uid,status='active')
        def add(self,value):
            self.added.append(value)
        def commit(self):pass
    return Database(),state


def test_reconnect_callback_resolves_only_the_one_authorized_app_installation(monkeypatch):
    db,state=_reauthorization_context(monkeypatch,[
        {'id':713,'app_id':12345},
        {'id':842,'app_id':5470256},
    ])
    row=github.handle_callback(db,'one-time-state',None,None,'synthetic-code')
    assert row.installation_id==842
    assert row.account_login=='fixture-owner'
    assert row.user_token=='encrypted-synthetic-token'
    assert row.token_expires_at is None
    assert state.consumed is True


@pytest.mark.parametrize('eligible,reason',[
    ([], 'Install the GitHub App'),
    ([{'id':11,'app_id':5470256},{'id':12,'app_id':5470256}], 'Multiple GitHub installations'),
])
def test_reconnect_never_chooses_unverified_or_ambiguous_installation(monkeypatch,eligible,reason):
    db,state=_reauthorization_context(monkeypatch,eligible)
    with pytest.raises(HTTPException) as error:
        github.handle_callback(db,'one-time-state',None,None,'synthetic-code')
    assert error.value.status_code==409
    assert reason in str(error.value.detail)
    assert not state.consumed and not db.added


def test_reconnect_rejects_requested_foreign_installation(monkeypatch):
    db,state=_reauthorization_context(monkeypatch,[{'id':19,'app_id':5470256}])
    with pytest.raises(HTTPException) as error:
        github.handle_callback(db,'one-time-state',20,None,'synthetic-code')
    assert error.value.status_code==403
    assert not state.consumed and not db.added
