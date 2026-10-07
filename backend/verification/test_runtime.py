"""Unit regressions; these fixtures do not claim real provider acceptance."""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from fastapi import HTTPException
from app.services import opencode, providers, runtime_snapshot
from app.routes import workspaces


def service(handler):
    result=opencode.OpenCodeService('http://127.0.0.1:1')
    result.client.close()
    result.client=httpx.Client(transport=httpx.MockTransport(handler),base_url='http://127.0.0.1:1')
    return result


def test_complete_catalog_and_auth_fields_are_preserved():
    methods={'oauth-only':[{'type':'oauth','label':'Login','prompts':[{'key':'tenant','type':'text','message':'Tenant','when':{'key':'kind','op':'eq','value':'organization'}}]}]}
    data={'all':[{'id':'oauth-only','name':'OAuth','models':{'m':{'name':'Model','limit':{'context':42}}},'options':{'apiKey':'private','region':'local'}}], 'connected':[], 'default':{'oauth-only':'m'}}
    policy=SimpleNamespace(allowed_providers='["different"]',allowed_models='[]',allowed_tools='[]')
    result=providers.catalog(data,methods,policy)
    assert len(result)==1 and result[0]['allowed'] is False
    assert result[0]['auth_methods']==methods['oauth-only']
    assert result[0]['models'][0]['limit']['context']==42
    assert 'apiKey' not in result[0]['options']


def test_concurrent_bootstrap_has_one_discovery_pass():
    counts={}; lock=threading.Lock()
    def respond(request):
        path=request.url.path
        with lock: counts[path]=counts.get(path,0)+1
        time.sleep(.005)
        payload={'/global/health':{'healthy':True,'version':'1.18.32'},'/provider':{'all':[],'connected':[],'default':{}},'/provider/auth':{},'/config':{'default_agent':'custom'},'/agent':[],'/permission':[],'/session':[],'/experimental/tool/ids':[]}.get(path,{})
        return httpx.Response(200,json=payload)
    instance=service(respond)
    try:
        with ThreadPoolExecutor(max_workers=5) as pool: results=list(pool.map(lambda _:instance.snapshot(),range(5)))
        assert counts['/provider']==counts['/provider/auth']==counts['/agent']==1
        assert all(r['default_agent']=='custom' for r in results)
        instance.invalidate();instance.snapshot();assert counts['/provider']==2
    finally: instance.close()


def test_one_failed_capability_does_not_hide_agents():
    def respond(request):
        if request.url.path=='/provider/auth':return httpx.Response(500,json={})
        if request.url.path=='/global/health':return httpx.Response(200,json={'healthy':True,'version':'1.18.32'})
        return httpx.Response(200,json=[{'name':'custom','mode':'primary'}] if request.url.path=='/agent' else {})
    instance=service(respond)
    try:
        result=instance.snapshot()
        assert result['auth_methods'] is None and 'auth_methods' in result['errors']
        assert result['agents'][0]['name']=='custom'
    finally:instance.close()


def test_unsupported_version_reports_specific_error():
    instance=service(lambda _:httpx.Response(200,json={'healthy':True,'version':'99'}))
    try:
        with pytest.raises(HTTPException,match='Unsupported'):instance.health()
    finally:instance.close()


@pytest.mark.parametrize('connected', [True,False])
def test_removal_requires_confirmation(connected):
    instance=service(lambda r:httpx.Response(200,json=True if r.method=='DELETE' else {'connected':['p'] if connected else []}))
    try:
        if connected:
            with pytest.raises(HTTPException):providers.remove(instance,'p')
        else:assert providers.remove(instance,'p') is True
    finally:instance.close()


@pytest.mark.parametrize('succeeds', [True,False])
def test_validation_requires_real_answer_and_cleans_temporary_session(succeeds):
    calls=[]
    def respond(request):
        calls.append((request.method,request.url.path))
        if request.url.path=='/provider':payload={'all':[{'id':'p','models':{'m':{'modalities':{'output':['text']}}}}],'connected':['p'],'default':{'p':'m'}}
        elif request.url.path=='/session':payload={'id':'ses_validation'}
        elif request.url.path.endswith('/message'):
            payload={'info':{'role':'assistant','providerID':'p','modelID':'m','time':{'completed':1},**({} if succeeds else {'error':{'name':'ProviderAuthError'}})},'parts':[{'type':'text','text':'OK'}]}
        else:payload=True
        return httpx.Response(200,json=payload)
    instance=service(respond)
    try:
        if succeeds:assert providers.validate_model(instance,'p')=='m'
        else:
            with pytest.raises(HTTPException):providers.validate_model(instance,'p')
        assert ('DELETE','/session/ses_validation') in calls
    finally:instance.close()


def test_default_agent_is_not_added_to_prompt():
    # The request contract accepts omission; no Gateway default is synthesized.
    from app.routes.agent import MessageRequest
    request=MessageRequest(text='hello',provider_id='p',model_id='m')
    assert request.agent_id is None


def test_disconnect_keeps_persisted_credential_if_runtime_unconfirmed(monkeypatch):
    instance=Mock();instance.state_lock=threading.RLock()
    db=Mock();workspace=SimpleNamespace(id='workspace')
    monkeypatch.setattr(workspaces,'_workspace_service',lambda *args:(workspace,instance))
    monkeypatch.setattr(providers,'remove',Mock(side_effect=HTTPException(502,'Unconfirmed')))
    with pytest.raises(HTTPException):workspaces.remove_provider_credential('workspace','p',SimpleNamespace(id='user'),db)
    db.delete.assert_not_called();db.commit.assert_not_called()


def test_failed_validation_rolls_back_runtime_without_persisting(monkeypatch):
    instance=Mock();instance.state_lock=threading.RLock()
    db=Mock();db.scalar.return_value=None
    monkeypatch.setattr(workspaces,'_workspace_service',lambda *args:(SimpleNamespace(id='workspace'),instance))
    monkeypatch.setattr(workspaces.credentials,'available',lambda:True)
    monkeypatch.setattr(workspaces.policy,'load',lambda _:SimpleNamespace())
    monkeypatch.setattr(workspaces.policy,'provider_allowed',lambda *args:True)
    monkeypatch.setattr(providers,'auth_methods',lambda _: {})
    monkeypatch.setattr(providers,'is_connected',lambda *args:False)
    monkeypatch.setattr(providers,'set_api_key',Mock())
    monkeypatch.setattr(providers,'validate_model',Mock(side_effect=HTTPException(422,'Model failed')))
    remove=Mock();monkeypatch.setattr(providers,'remove',remove)
    with pytest.raises(HTTPException):workspaces.set_provider_credential('workspace','p',workspaces.ApiKeyCredential(api_key='invalid-fixture'),SimpleNamespace(id='user'),db)
    remove.assert_called_once();db.add.assert_not_called();db.commit.assert_not_called()


def test_per_workspace_locks_and_once_generation_restore(monkeypatch,tmp_path):
    import app.database
    initialized=[]
    monkeypatch.setattr(opencode,'settings',SimpleNamespace(runtime_mode='local',opencode_binary='fake',runtime_root=tmp_path))
    monkeypatch.setattr(opencode,'root_for',lambda _:tmp_path)
    monkeypatch.setattr(opencode.shutil,'which',lambda _: 'fake')
    monkeypatch.setattr(app.database,'SessionLocal',Mock(return_value=Mock(__enter__=Mock(return_value=Mock()),__exit__=Mock(return_value=False))))
    monkeypatch.setattr(__import__('app.services.policy',fromlist=['load']),'load',lambda _:None)
    monkeypatch.setattr(__import__('app.services.policy',fromlist=['permission_config']),'permission_config',lambda _: {})
    class Process:
        def __init__(self,*args,**kwargs):self.done=False
        def poll(self):return 0 if self.done else None
        def terminate(self):self.done=True
        def wait(self,timeout=None):return 0
    monkeypatch.setattr(opencode.subprocess,'Popen',Process)
    monkeypatch.setattr(opencode,'_initialize',lambda s,w:initialized.append(str(w.id)))
    def health(self,timeout=3):
        self.last_health=time.monotonic();return {'healthy':True,'version':'1.18.32'}
    monkeypatch.setattr(opencode.OpenCodeService,'health',health)
    workspace=SimpleNamespace(id='unit-one',user_id='unit-owner')
    other=SimpleNamespace(id='unit-two',user_id='unit-owner')
    assert opencode.workspace_lock(workspace) is not opencode.workspace_lock(other)
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:instances=list(pool.map(lambda _:opencode.for_workspace(workspace),range(4)))
        assert all(item is instances[0] for item in instances)
        assert initialized==['unit-one']
        opencode.stop_workspace(workspace)
        restarted=opencode.for_workspace(workspace)
        assert restarted.generation!=instances[0].generation and initialized==['unit-one','unit-one']
    finally:opencode.stop_workspace(workspace)


def test_initialize_restores_encrypted_metadata_once_per_pass(monkeypatch):
    import app.database
    from app.services import credentials
    rows=[SimpleNamespace(provider_id='fixture-provider',ciphertext='encrypted-unit-fixture')]
    db=Mock();db.scalars.return_value=rows
    manager=Mock();manager.__enter__=Mock(return_value=db);manager.__exit__=Mock(return_value=False)
    monkeypatch.setattr(app.database,'SessionLocal',lambda:manager)
    monkeypatch.setattr(credentials,'decrypt',lambda _:json.dumps({'type':'api','key':'unit-fixture-only','metadata':{'accountId':'account-fixture'}}))
    puts=[]
    def respond(request):
        puts.append(json.loads(request.content))
        return httpx.Response(200,json=True)
    instance=service(respond)
    try:
        opencode._initialize(instance,SimpleNamespace(id='unit-workspace',user_id='unit-owner'))
        assert instance.restore_passes==1 and instance.restore_puts==1
        assert puts==[{'type':'api','key':'unit-fixture-only','metadata':{'accountId':'account-fixture'}}]
    finally:instance.close()


def test_session_permissions_preserve_runtime_admin_tool_policy():
    bodies=[]
    def respond(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200,json={'id':'ses_unit'})
    instance=service(respond)
    try:
        instance.create_session('Unit session')
        assert bodies[0]['permission']==[{'permission':'external_directory','pattern':'*','action':'deny'}]
        # A session-wide ask would override the runtime's restricted-tool deny.
        assert not any(rule['permission']=='*' for rule in bodies[0]['permission'])
    finally:instance.close()


def test_admin_session_tool_rules_keep_external_directory_denied():
    from app.services import policy
    restricted=SimpleNamespace(allowed_providers='[]',allowed_models='[]',allowed_tools='["read","external_directory"]',require_tool_approval=True)
    rules=policy.session_permissions(restricted)
    assert rules[0]=={'permission':'*','pattern':'*','action':'deny'}
    assert {'permission':'read','pattern':'*','action':'ask'} in rules
    assert rules[-1]=={'permission':'external_directory','pattern':'*','action':'deny'}


def test_session_policy_is_confirmed_and_only_updated_when_changed():
    calls=[]
    def respond(request):
        calls.append(request.method)
        rules=json.loads(request.content)['permission']
        return httpx.Response(200,json={'permission':[{'permission':'old','pattern':'*','action':'deny'}]+rules})
    instance=service(respond)
    try:
        rules=[{'permission':'*','pattern':'*','action':'deny'}]
        instance.apply_session_policy('ses_unit',rules)
        instance.apply_session_policy('ses_unit',rules)
        assert calls==['PATCH']
        instance.apply_session_policy('ses_unit',[{'permission':'*','pattern':'*','action':'ask'}])
        assert calls==['PATCH','PATCH']
    finally:instance.close()
