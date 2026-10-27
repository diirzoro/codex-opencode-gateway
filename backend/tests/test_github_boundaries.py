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
    assert args['prompt']==['select_account']
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


def test_disconnect_requires_new_customer_link_and_invalidates_old_callback(boundary,monkeypatch):
    """An installed App is not a Gateway link. No stale OAuth flow may revive it."""
    import uuid
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from backend.app import models
    from backend.tests.test_native_control_plane import authenticated
    client,(owner,other),_,engine,config=boundary
    models.GithubAuthState.__table__.create(engine)
    earlier='stale-oauth-before-disconnect'
    with Session(engine) as db:
        db.add(models.GithubConnection(user_id=owner.id,installation_id=901,
             account_login='fixture-owner',user_token='encrypted-old-user-token',suspended=False))
        db.add(models.GithubAuthState(state=earlier,user_id=owner.id,
             expires_at=datetime.now(timezone.utc)+timedelta(minutes=5)))
        db.add(models.GithubAuthState(state='other-user-authorization',user_id=other.id,
             expires_at=datetime.now(timezone.utc)+timedelta(minutes=5)))
        db.commit()
    monkeypatch.setattr(github,'configured',lambda db=None:True)
    vendor=Mock(side_effect=AssertionError('Disconnected customer must not access GitHub'))
    monkeypatch.setattr(github,'_api',vendor)
    before=authenticated(client,'/api/github/status',owner,config)
    assert before.status_code==200 and before.json()['connected'] is True
    assert 'no-store' in before.headers['cache-control']

    response=authenticated(client,'/api/github/disconnect',owner,config,'POST')
    assert response.status_code==204,response.text
    after=authenticated(client,'/api/github/status',owner,config)
    assert after.status_code==200 and after.json()['connected'] is False
    assert 'no-store' in after.headers['cache-control']
    assert authenticated(client,'/api/github/repositories',owner,config).status_code==503
    assert authenticated(client,'/api/github/branches?repository=fixture-owner/repo',owner,config).status_code==503
    assert vendor.call_count==0
    # Disconnect is idempotent, including when the customer returns/reloads.
    assert authenticated(client,'/api/github/disconnect',owner,config,'POST').status_code==204
    assert authenticated(client,'/api/github/status',owner,config).json()['connected'] is False
    assert authenticated(client,f'/api/projects/{owner.project}',owner,config).status_code==200

    with Session(engine) as db:
        assert db.scalar(select(models.GithubConnection).where(models.GithubConnection.user_id==owner.id)) is None
        assert db.scalar(select(models.GithubAuthState).where(models.GithubAuthState.state==earlier)) is None
        assert db.scalar(select(models.GithubAuthState).where(models.GithubAuthState.user_id==other.id)) is not None
        config_value=SimpleNamespace(github_app_id=5470256)
        monkeypatch.setattr(github.github_app_config,'effective',lambda *a:config_value)
        monkeypatch.setattr(github,'require_configured',lambda *a:None)
        with pytest.raises(HTTPException) as error:
            github.handle_callback(db,earlier,901,'install','old-code')
        assert error.value.status_code==400
        assert vendor.call_count==0


def test_explicit_fresh_oauth_request_does_not_link_before_callback(boundary,monkeypatch):
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from urllib.parse import urlparse,parse_qs
    from backend.app import models
    client,(owner,_),_,engine,config=boundary
    models.GithubAuthState.__table__.create(engine)
    app=SimpleNamespace(github_web_base='https://github.com',
                        github_client_id='IvFreshConnection',github_callback_url=config.public_base_url+'/api/github/callback')
    monkeypatch.setattr(github.github_app_config,'effective',lambda *a:app)
    monkeypatch.setattr(github,'require_configured',lambda *a:None)
    from backend.app.routes import github as github_routes
    monkeypatch.setattr(github_routes,'require_advanced',lambda *a,**kw:None)
    response=client.get('/api/github/authorize',follow_redirects=False,
                        headers={'Cookie':config.session_cookie_name+'=fixture-token-'+owner.name,
                                 'Origin':config.public_base_url})
    assert response.status_code==302
    parsed=urlparse(response.headers['location'])
    assert parsed.netloc=='github.com' and parsed.path=='/login/oauth/authorize'
    state=parse_qs(parsed.query)['state'][0]
    with Session(engine) as db:
        assert db.scalar(select(models.GithubAuthState).where(models.GithubAuthState.state==state,
                         models.GithubAuthState.user_id==owner.id)) is not None
        assert db.scalar(select(models.GithubConnection).where(models.GithubConnection.user_id==owner.id)) is None


def test_install_starts_account_picker_instead_of_installation_settings(monkeypatch):
    from urllib.parse import urlparse,parse_qs
    import uuid
    cfg=SimpleNamespace(github_web_base='https://github.com',github_client_id='fixture-client',github_callback_url='https://test.example/api/github/callback')
    monkeypatch.setattr(github.github_app_config,'effective',lambda *a:cfg)
    monkeypatch.setattr(github,'require_configured',lambda *a:None)
    states=[];db=SimpleNamespace(add=states.append,commit=lambda:None)
    result=github.begin_install(db,SimpleNamespace(id=uuid.uuid4()))
    args=parse_qs(urlparse(result).query)
    assert urlparse(result).path=='/login/oauth/authorize'
    assert args['prompt']==['select_account'] and args['state'][0].startswith('install_')


def test_install_continuation_refuses_foreign_gateway_installation(monkeypatch):
    db,state=_reauthorization_context(monkeypatch,[{'id':42,'app_id':5470256}])
    original=db.scalar
    def scalar(query):
        if db.lookups==0:return original(query)
        return SimpleNamespace(user_id='other-gateway-owner')
    db.scalar=scalar
    with pytest.raises(HTTPException) as error:github.handle_callback(db,'install_fixture',None,None,'code')
    assert error.value.status_code==409
    assert not state.consumed and not db.added


def test_valid_account_selection_mints_new_install_state_without_connecting(monkeypatch):
    db,state=_reauthorization_context(monkeypatch,[{'id':42,'app_id':5470256}])
    continuation=Mock(return_value='https://github.com/apps/fixture/installations/new?state=setup_fixture')
    monkeypatch.setattr(github,'_begin_installation',continuation)
    result=github.handle_callback(db,'install_fixture',None,None,'code')
    assert result['redirect'].startswith('https://github.com/apps/fixture/')
    assert state.consumed and not db.added
    continuation.assert_called_once()


def test_setup_return_without_oauth_code_only_starts_fresh_authorization(monkeypatch):
    db,state=_reauthorization_context(monkeypatch,[])
    start=Mock(return_value='https://github.com/login/oauth/authorize?state=fresh_fixture')
    monkeypatch.setattr(github,'begin_authorization',start)
    exchange=Mock(side_effect=AssertionError('No code must not create a connection'))
    monkeypatch.setattr(github,'exchange_code',exchange)
    result=github.handle_callback(db,'setup_fixture',123,'update',None)
    assert state.consumed and result['redirect'].startswith('https://github.com/login/oauth/authorize')
    assert not db.added
    exchange.assert_not_called()


@pytest.mark.parametrize('role', ['customer', 'admin'])
def test_new_link_post_forgets_only_current_user_connection_and_all_prior_states(boundary, monkeypatch, role):
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from urllib.parse import urlparse, parse_qs
    from backend.app import models
    from backend.app.routes import github as routes
    from backend.tests.test_native_control_plane import authenticated
    client,(owner,other),_,engine,config=boundary
    models.GithubAuthState.__table__.create(engine)
    cfg=SimpleNamespace(github_web_base='https://github.com',github_client_id='fixture',github_callback_url=config.public_base_url+'/api/github/callback')
    monkeypatch.setattr(github.github_app_config,'effective',lambda *a:cfg)
    monkeypatch.setattr(github,'require_configured',lambda *a:None)
    monkeypatch.setattr(routes,'require_advanced',lambda *a,**kw:None)
    monkeypatch.setattr(github,'configured',lambda *a:True)
    with Session(engine) as db:
        db.get(models.User,owner.id).role=role
        for user,installation in [(owner,701),(other,702)]:
            db.add(models.GithubConnection(user_id=user.id,installation_id=installation,account_login='synthetic-'+user.name,user_token='encrypted-fixture',suspended=False))
            db.add(models.GithubAuthState(user_id=user.id,state='old-'+user.name,expires_at=datetime.now(timezone.utc)+timedelta(minutes=5)))
        db.commit()
    assert client.post('/api/github/connect').status_code==401
    first=authenticated(client,'/api/github/connect',owner,config,'POST')
    assert first.status_code==200,first.text
    assert 'no-store' in first.headers['cache-control']
    args=parse_qs(urlparse(first.json()['url']).query)
    assert args['prompt']==['select_account'] and args['state'][0].startswith('install_')
    assert authenticated(client,'/api/github/status',owner,config).json()['connected'] is False
    assert authenticated(client,'/api/github/repositories',owner,config).status_code==503
    with Session(engine) as db:
        assert db.scalar(select(models.GithubConnection).where(models.GithubConnection.user_id==owner.id)) is None
        assert db.scalar(select(models.GithubConnection).where(models.GithubConnection.user_id==other.id)).installation_id==702
        assert db.scalar(select(models.GithubAuthState).where(models.GithubAuthState.state=='old-'+owner.name)) is None
        assert db.scalar(select(models.GithubAuthState).where(models.GithubAuthState.state=='old-'+other.name)) is not None
        assert db.get(models.Project,owner.project) is not None
    second=authenticated(client,'/api/github/connect',owner,config,'POST')
    state2=parse_qs(urlparse(second.json()['url']).query)['state'][0]
    assert state2!=args['state'][0]
    with Session(engine) as db:
        assert db.scalar(select(models.GithubAuthState).where(models.GithubAuthState.state==args['state'][0])) is None
        assert db.scalar(select(models.GithubAuthState).where(models.GithubAuthState.state==state2)) is not None
    assert (owner.root/'marker.txt').read_text()=='synthetic-marker-'+owner.name


def test_unconfigured_new_link_does_not_erase_existing_connection(monkeypatch):
    db=Mock()
    monkeypatch.setattr(github.github_app_config,'effective',lambda *a:SimpleNamespace())
    monkeypatch.setattr(github,'require_configured',Mock(side_effect=HTTPException(503,'Missing configuration')))
    with pytest.raises(HTTPException):github.begin_fresh_link(db,SimpleNamespace(id='fixture'))
    db.execute.assert_not_called()
    db.commit.assert_not_called()


def test_same_github_account_can_reconnect_after_explicit_disconnect(boundary, monkeypatch):
    """Disconnect revokes old state, not the right to link the same installation."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from urllib.parse import urlparse, parse_qs
    from backend.app import models
    from backend.tests.test_native_control_plane import authenticated
    client, (owner, other), _, engine, config = boundary
    models.GithubAuthState.__table__.create(engine)
    cfg = SimpleNamespace(github_web_base='https://github.com', github_app_slug='fixture',
                          github_app_id=5470256, github_client_id='fixture',
                          github_callback_url=config.public_base_url+'/api/github/callback')
    monkeypatch.setattr(github.github_app_config, 'effective', lambda *a: cfg)
    monkeypatch.setattr(github, 'require_configured', lambda *a: None)
    monkeypatch.setattr(github, 'require_advanced', lambda *a, **kw: None)
    from backend.app.routes import github as routes
    monkeypatch.setattr(routes, 'require_advanced', lambda *a, **kw: None)
    monkeypatch.setattr(github, 'configured', lambda *a: True)
    monkeypatch.setattr(github, 'exchange_code', lambda *a, **kw: {'access_token': 'synthetic-new-token'})
    monkeypatch.setattr(github, '_jwt', lambda *a: 'synthetic-jwt')
    monkeypatch.setattr(github.credentials, 'encrypt', lambda t: 'encrypted-new-token')
    def vendor(method, path, **kw):
        if path == '/user/installations':
            return {'installations': [{'id': 901, 'app_id': 5470256}]}
        if path == '/app/installations/901':
            return {'app_id': 5470256, 'account': {'login': 'same-fixture-owner', 'type': 'User'}}
        raise AssertionError(path)
    monkeypatch.setattr(github, '_api', vendor)
    with Session(engine) as db:
        for user, installation in [(owner, 901), (other, 902)]:
            db.add(models.GithubConnection(user_id=user.id, installation_id=installation,
                                          account_login='same-fixture-owner', user_token='encrypted-old'))
        db.commit()
    assert authenticated(client, '/api/github/disconnect', owner, config, 'POST').status_code == 204
    new = authenticated(client, '/api/github/connect', owner, config, 'POST')
    assert new.status_code == 200, new.text
    state = parse_qs(urlparse(new.json()['url']).query)['state'][0]
    with Session(engine) as db:
        continuation = github.handle_callback(db, state, None, None, 'synthetic-code')
        setup = parse_qs(urlparse(continuation['redirect']).query)['state'][0]
        row = github.handle_callback(db, setup, 901, 'install', 'synthetic-new-code')
        assert row.installation_id == 901 and row.user_id == owner.id
        assert row.user_token == 'encrypted-new-token'
        assert db.scalar(select(models.GithubConnection).where(models.GithubConnection.user_id == other.id)).installation_id == 902
    result = authenticated(client, '/api/github/status', owner, config)
    assert result.status_code == 200 and result.json()['connected'] is True
