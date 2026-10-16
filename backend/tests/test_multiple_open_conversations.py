"""Open chat state does not monopolize shared workspace execution."""
import os
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://test:test@127.0.0.1/test')
import uuid
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from backend.app.services import session_lifecycle as lifecycle
from backend.app.routes import workspaces


def test_multiple_idle_open_conversations_do_not_require_closing(monkeypatch):
    rows=[SimpleNamespace(id='first',status='completed'),SimpleNamespace(id='second',status='active')]
    monkeypatch.setattr(lifecycle,'workspace_rows',lambda db,w:rows)
    lifecycle.require_slot(Mock(),SimpleNamespace(id='owned'))
    lifecycle.require_slot(Mock(),SimpleNamespace(id='owned'),'second')


@pytest.mark.parametrize('status',['submitted','waiting_approval'])
def test_actual_other_execution_still_blocks_shared_files(monkeypatch,status):
    monkeypatch.setattr(lifecycle,'workspace_rows',lambda db,w:[SimpleNamespace(id='busy',status=status)])
    with pytest.raises(HTTPException) as error:lifecycle.require_slot(Mock(),SimpleNamespace(),'new')
    assert error.value.status_code==409


def test_current_execution_is_not_rejected_by_other_slot_check(monkeypatch):
    monkeypatch.setattr(lifecycle,'workspace_rows',lambda db,w:[SimpleNamespace(id='selected',status='submitted')])
    lifecycle.require_slot(Mock(),SimpleNamespace(),'selected')


def test_creation_preserves_previous_open_sessions(monkeypatch):
    owner=SimpleNamespace(id=uuid.uuid4());workspace=SimpleNamespace(id=uuid.uuid4(),project=SimpleNamespace(source_type='blank'))
    old=SimpleNamespace(id='old',status='completed')
    monkeypatch.setattr(workspaces.manager,'owned',lambda *a:workspace)
    monkeypatch.setattr(workspaces.manager,'require_quota_headroom',lambda *a:None)
    monkeypatch.setattr(lifecycle,'lock_workspace',lambda *a:None)
    monkeypatch.setattr(lifecycle,'workspace_rows',lambda *a:[old])
    states=[];monkeypatch.setattr(lifecycle,'set_state',lambda db,row,state:states.append((row,state)))
    runtime=Mock();runtime.create_session.return_value='runtime-new';monkeypatch.setattr(workspaces.opencode,'for_workspace',lambda *a,**kw:runtime)
    db=Mock();db.flush.side_effect=lambda:setattr(db.add.call_args.args[0],'id',uuid.uuid4())
    result=workspaces.new_session(workspace.id,workspaces.NewSession(title='Second conversation'),owner,db)
    assert result['title']=='Second conversation' and result['lifecycle']=='active'
    assert old.status=='completed' and len(states)==1 and states[0][0].title=='Second conversation'
    db.commit.assert_called_once()
