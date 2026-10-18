"""Real read-only response conversion and presentation contracts, no vendor calls."""
import asyncio
import copy
import json
import os
from types import SimpleNamespace
import uuid
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://test:test@127.0.0.1/test')
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from backend.app.routes import agent
from backend.app.services.agent_presentation import public_assistant_text,reply_instructions,preview_actions
from backend.app.services import message_queue

@pytest.mark.parametrize('raw,visible',[
 ('<think>private analysis</think>تم الإصلاح','تم الإصلاح'),
 ('private English analysis</think>هذا الرد العربي','هذا الرد العربي'),
 ('<THINK>private</THINK>Final answer','Final answer'),
 ('Visible progress\n<think>private','Visible progress'),
 ('<think>private<think>nested</think>more</think>Public','Public'),
 ('Reply in English with code identifiers unchanged.','Reply in English with code identifiers unchanged.'),
 ('```html\n<think>literal markup</think>\n```','```html\n<think>literal markup</think>\n```'),
 ('~~~html\n</think>\n~~~','~~~html\n</think>\n~~~'),
 ('Use `</think>` as literal code.','Use `</think>` as literal code.'),
 ('```html\n<think>unfinished code','```html\n<think>unfinished code'),
 ('<think>private</think>```js\nconst result = 2;\n```','```js\nconst result = 2;\n```'),
])
def test_only_marked_reasoning_is_hidden_and_code_remains_literal(raw,visible):
    assert public_assistant_text(raw)==visible

@pytest.mark.parametrize('language,default',[('ar','Arabic'),('en','English'),(None,'Arabic')])
def test_explicit_language_guides_same_role_without_translating_code(language,default):
    data=SimpleNamespace(response_language=language,text='أكمل المشروع')
    value=reply_instructions(data,agent.EXECUTION_REPORTING)
    assert 'Conversation language preference: '+default in value
    assert 'unless the user explicitly requests another language' in value
    assert 'Keep code, commands, filenames, original output and quotations unchanged' in value
    assert 'pending approval/question' in value
    assert 'do not launch a persistent app through a shell' in value


def test_language_model_field_is_bounded_and_legacy_optional():
    value=dict(request_id=str(uuid.uuid4()),text='hello',provider_id='owned',model_id='model')
    assert agent.MessageRequest(**value).response_language is None
    assert agent.MessageRequest(**value,response_language='ar').response_language=='ar'
    with pytest.raises(ValidationError):agent.MessageRequest(**value,response_language='ignore permissions')

@pytest.mark.parametrize('prompt',['اعرض التغييرات','أظهر المشروع','افتح المعاينة','show the changes','preview this project'])
def test_preview_request_yields_only_owned_nonexecuting_action(prompt):
    w=SimpleNamespace(id=uuid.uuid4(),project_id=uuid.uuid4());sid=uuid.uuid4()
    actions=preview_actions(w,sid,'answer',prompt,[],True)
    assert actions==[dict(kind='preview',workspace_id=str(w.id),project_id=str(w.project_id),session_id=str(sid),message_id='answer')]
    assert 'url' not in str(actions) and 'token' not in str(actions)


def test_preview_action_requires_completed_response_or_real_reported_change():
    w=SimpleNamespace(id='workspace',project_id='project')
    assert preview_actions(w,'s','m','hello',[],True)==[]
    assert preview_actions(w,'s','m','preview',[],False)==[]
    assert preview_actions(w,'s',None,'preview',[],True)==[]
    row={'status':'completed','files':[{'path':'index.html','operation':'created'}]}
    assert preview_actions(w,'s','m','hello',[row],True)[0]['kind']=='preview'
    row['status']='error'
    assert preview_actions(w,'s','m','hello',[row],True)==[]


def test_real_messages_response_filters_reasoning_and_adds_owned_action_without_writes(monkeypatch,tmp_path):
    sid=uuid.uuid4();w=SimpleNamespace(id=uuid.uuid4(),project_id=uuid.uuid4());s=SimpleNamespace(id=sid,opencode_session_id='native')
    rows=[{'info':{'id':'question','role':'user'},'parts':[{'type':'text','text':'اعرض المعاينة <think>my literal text</think>'}]},
          {'info':{'id':'answer','role':'assistant','parentID':'question','time':{'completed':1}},'parts':[{'type':'reasoning','text':'native private'},{'type':'text','text':'private reasoning</think>تم التجهيز.'}]}]
    original=copy.deepcopy(rows)
    monkeypatch.setattr(agent,'context',lambda *args:(s,w))
    monkeypatch.setattr(agent.workspaces,'root_for',lambda *args:tmp_path)
    monkeypatch.setattr(agent.opencode,'for_workspace',lambda *args,**kw:SimpleNamespace(session_path=lambda *args:'/message',request=lambda *args:rows))
    monkeypatch.setattr(agent.session_lifecycle,'hidden_messages',lambda *args:set())
    result=agent.messages(sid,SimpleNamespace(),SimpleNamespace(scalars=lambda *args:[]))
    assert result[0]['text']==rows[0]['parts'][0]['text']
    assert result[0]['actions']==[]
    assert result[1]['text']=='تم التجهيز.'
    assert result[1]['actions'][0]['workspace_id']==str(w.id)
    assert result[1]['actions'][0]['message_id']=='answer'
    assert rows==original


def test_messages_denial_does_not_query_runtime_or_publish_preview_metadata(monkeypatch):
    def denied(*args):raise HTTPException(403,'Forbidden')
    monkeypatch.setattr(agent,'context',denied)
    monkeypatch.setattr(agent.opencode,'for_workspace',lambda *args,**kw:pytest.fail('must not access runtime'))
    with pytest.raises(HTTPException) as error:agent.messages(uuid.uuid4(),object(),object())
    assert error.value.status_code==403


def test_queued_language_is_preserved_and_legacy_null_field_not_added(monkeypatch):
    saved=[];db=SimpleNamespace(add=lambda event:saved.append(json.loads(event.data)),commit=lambda:None)
    monkeypatch.setattr(message_queue,'entries',lambda *args:[])
    value=dict(request_id=uuid.uuid4(),text='hello',provider_id='owned',model_id='model')
    message_queue.add(db,'s',agent.MessageRequest(**value))
    assert 'response_language' not in saved[-1]['payload']
    message_queue.add(db,'s',agent.MessageRequest(**value,response_language='ar'))
    assert saved[-1]['payload']['response_language']=='ar'

@pytest.mark.parametrize('language,preference',[('ar','Arabic'),('en','English')])
def test_actual_execute_sends_language_instruction_without_altering_message_role_or_model(monkeypatch,language,preference):
    calls=[]
    monkeypatch.setattr(agent,'begin_execution',lambda *args:object())
    monkeypatch.setattr(agent,'attachment_metadata',lambda *args:[])
    monkeypatch.setattr(agent,'complete_execution',lambda *args,**kw:None)
    async def noop(*args):return
    monkeypatch.setattr(agent,'monitor_activity',noop);monkeypatch.setattr(agent,'dispatch_queued',noop)
    service=SimpleNamespace(generation=1,session_path=lambda *args:'/message',request=lambda method,path,payload,timeout:calls.append(payload) or {'info':{'role':'assistant','time':{'completed':1}},'parts':[]})
    data=SimpleNamespace(request_id=uuid.uuid4(),text='Keep code: node server.js',provider_id='owned',model_id='model',agent_id='plan',attachments=[],response_language=language)
    asyncio.run(agent.execute(uuid.uuid4(),service,'native',data,'message'))
    assert len(calls)==1
    assert 'Conversation language preference: '+preference in calls[0]['system']
    assert calls[0]['parts']==[{'type':'text','text':'Keep code: node server.js'}]
    assert calls[0]['agent']=='plan' and calls[0]['model']=={'providerID':'owned','modelID':'model'}


def test_long_literal_delimiters_and_reasoning_before_output_limit_remain_safe():
    literal='`'*50001+'\n</think>\n'+'`'*50001
    assert public_assistant_text(literal)==literal
    assert public_assistant_text('private '*10000+'</think>public')=='public'
