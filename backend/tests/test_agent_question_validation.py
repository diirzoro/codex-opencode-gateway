"""Question validation regression; native runtime interactions tested separately."""
import os
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://test:test@127.0.0.1/test')
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from backend.app.routes import agent

@pytest.mark.parametrize('values,multiple,custom,valid',[
    (['Blue','Blue'],True,False,False),(['Blue','Green'],True,False,True),
    (['Blue','Custom'],True,True,True),(['Custom'],False,False,False),
    (['Blue','Green'],False,True,False),([],True,True,False)])
def test_question_answers_are_validated_before_native_reply(monkeypatch,values,multiple,custom,valid):
    workspace=SimpleNamespace(id='w',user_id='u');session=SimpleNamespace(id='s',opencode_session_id='native')
    service=Mock();service.request.side_effect=[[{'id':'q','sessionID':'native','questions':[{'multiple':multiple,'custom':custom,'options':[{'label':'Blue'},{'label':'Green'}]}]}],True]
    monkeypatch.setattr(agent,'context',lambda *a:(session,workspace));monkeypatch.setattr(agent.opencode,'for_workspace',lambda *a,**k:service);monkeypatch.setattr(agent,'event',Mock());monkeypatch.setattr(agent,'_sanitize',lambda value,w:value)
    if valid:
        assert agent.answer_question('s','q',agent.QuestionReply(answers=[values]),SimpleNamespace(id='u'),Mock())=={'accepted':True}
        assert service.request.call_args.args[2]['answers']==[values]
    else:
        with pytest.raises(HTTPException) as error:agent.answer_question('s','q',agent.QuestionReply(answers=[values]),SimpleNamespace(id='u'),Mock())
        assert error.value.status_code==422 and service.request.call_count==1


def test_foreign_session_question_cannot_be_answered(monkeypatch):
    service=Mock();service.request.return_value=[{'id':'q','sessionID':'foreign','questions':[]}]
    monkeypatch.setattr(agent,'context',lambda *a:(SimpleNamespace(opencode_session_id='own'),object()));monkeypatch.setattr(agent.opencode,'for_workspace',lambda *a,**k:service)
    with pytest.raises(HTTPException) as error:agent.answer_question('s','q',agent.QuestionReply(reject=True),SimpleNamespace(id='u'),Mock())
    assert error.value.status_code==404 and service.request.call_count==1
