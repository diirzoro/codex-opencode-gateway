"""Execution visibility must never publish arbitrary shell arguments or output."""
import asyncio
import os
from types import SimpleNamespace

os.environ.setdefault('DATABASE_URL','postgresql+psycopg://test:test@127.0.0.1/test')
from backend.app.routes import agent


def part(command='npm run build',status='completed',**state):
    return {'type':'tool','id':'tool-one','tool':'bash','state':{'status':status,'input':{'command':command},**state}}


def test_safe_command_shapes():
    for command in ['npm run build','pnpm run lint','pytest -q','python -m pytest','git diff --check','go test ./...']:
        assert agent.command_activity_label(command)==command


def test_shell_payloads_and_secrets_are_not_exposed():
    for command in ['npm run build && curl secret','python -c "print(123)"','git -c http.extraHeader=Authorization:secret status','npm run build --token secret','echo secret','curl https://secret','npm run build\ncat .env']:
        result=agent.command_activity_label(command)
        assert result in {None,'npm','python','git'}
        assert not result or 'secret' not in result


def test_actual_results_and_duration(monkeypatch,tmp_path):
    monkeypatch.setattr(agent.workspaces,'root_for',lambda workspace:tmp_path)
    row=agent.safe_tool_activity([part(metadata={'exit':1,'output':'DO NOT EXPOSE'},time={'start':1000,'end':2500},output='SECRET')],object())[0]
    assert row['command']=='npm run build' and row['command_limited'] is False
    assert row['exit_code']==1 and row['duration_ms']==1500
    assert 'SECRET' not in str(row) and 'DO NOT EXPOSE' not in str(row)


def test_limited_command_is_marked(monkeypatch,tmp_path):
    monkeypatch.setattr(agent.workspaces,'root_for',lambda workspace:tmp_path)
    row=agent.safe_tool_activity([part('python -c "print(secret)"')],object())[0]
    assert row['command']=='python' and row['command_limited'] is True
    assert 'secret' not in str(row)


def test_no_invented_exit_or_duration(monkeypatch,tmp_path):
    monkeypatch.setattr(agent.workspaces,'root_for',lambda workspace:tmp_path)
    for state in [part(status='running',metadata={'exit':0},time={'start':1,'end':2}),part(metadata={'exit':True},time={'start':4,'end':2}),part()]:
        row=agent.safe_tool_activity([state],object())[0]
        assert 'exit_code' not in row and 'duration_ms' not in row


def test_private_and_foreign_paths_stay_protected(monkeypatch,tmp_path):
    monkeypatch.setattr(agent.workspaces,'root_for',lambda workspace:tmp_path)
    rows=agent.safe_tool_activity([{'type':'tool','tool':'read','state':{'status':'completed','input':{'filePath':str(path)}}} for path in [tmp_path/'src'/'app.js',tmp_path/'.env',tmp_path.parent/'foreign.txt']],object())
    assert rows[0]['files'][0]['path']=='src/app.js'
    assert rows[1]['files'][0]['path']=='[private file]'
    assert 'files' not in rows[2]


def test_observer_emits_changed_details_but_not_duplicate(monkeypatch,tmp_path):
    monkeypatch.setattr(agent.workspaces,'root_for',lambda workspace:tmp_path)
    events=[]
    monkeypatch.setattr(agent,'record_activity',lambda *args:events.append(args[-1]) or True)
    async def scenario():
        done=asyncio.create_task(asyncio.sleep(0))
        rows=[{'info':{'role':'assistant','parentID':'message'},'parts':[part('npm',status='running'),part('npm run build',status='running'),part('npm run build',status='running')]}]
        service=SimpleNamespace(request=lambda *a,**kw:rows,session_path=lambda *a:'/message')
        await agent.monitor_activity('session',service,'runtime','message',object(),'request',done)
    asyncio.run(scenario())
    assert [row['command'] for row in events]==['npm','npm run build']


def test_reporting_instructions_keep_user_request_and_existing_controls(monkeypatch):
    calls=[]
    monkeypatch.setattr(agent,'begin_execution',lambda *args:object())
    monkeypatch.setattr(agent,'attachment_metadata',lambda *args:[])
    async def observe(*args):return
    monkeypatch.setattr(agent,'monitor_activity',observe)
    monkeypatch.setattr(agent,'complete_execution',lambda *args,**kwargs:None)
    service=SimpleNamespace(generation=1,session_path=lambda *args:'/message',request=lambda method,path,payload,timeout:calls.append(payload) or {'info':{'role':'assistant','time':{'completed':1}},'parts':[]})
    data=SimpleNamespace(request_id='request',text='Original user request',provider_id='owned',model_id='model',agent_id='plan',attachments=[])
    asyncio.run(agent.execute('session',service,'runtime',data,'message'))
    assert len(calls)==1
    payload=calls[0]
    assert payload['parts']==[{'type':'text','text':'Original user request'}]
    assert payload['agent']=='plan' and payload['model']['providerID']=='owned'
    assert 'pending approval/question' in payload['system'] and 'final report' in payload['system']
    assert 'Never blindly repeat failed operations' in payload['system']
    assert 'tools' not in payload and 'permission' not in payload


def test_reporting_does_not_auto_replay_failed_dispatch(monkeypatch):
    calls=[];results=[]
    monkeypatch.setattr(agent,'begin_execution',lambda *args:object())
    monkeypatch.setattr(agent,'attachment_metadata',lambda *args:[])
    async def observe(*args):return
    monkeypatch.setattr(agent,'monitor_activity',observe)
    monkeypatch.setattr(agent,'complete_execution',lambda *args,**kwargs:results.append(args[1]))
    service=SimpleNamespace(generation=1,session_path=lambda *args:'/message',request=lambda *args:calls.append(args) or {'info':{'role':'assistant','error':{'name':'UnknownError'}},'parts':[]})
    data=SimpleNamespace(request_id='request',text='Fix it',provider_id='owned',model_id='model',agent_id=None,attachments=[])
    asyncio.run(agent.execute('session',service,'runtime',data,'message'))
    assert len(calls)==1 and results==['failed']
