"""Rename authorization and lifecycle invariants; controlled DB, no runtime calls."""
import os
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://test:test@127.0.0.1/test')
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from backend.app.routes import agent

@pytest.mark.parametrize('value',['','  ','x'*121,None])
def test_invalid_title(value):
    with pytest.raises(ValidationError): agent.RenameSession(title=value)

@pytest.mark.parametrize('state',['active','closed','archived'])
def test_rename_preserves_lifecycle_and_runtime(monkeypatch,state):
    row=SimpleNamespace(id='s',workspace_id='w',title='Old',status='completed',created_at=None,opencode_session_id='runtime')
    workspace=SimpleNamespace(id='w');db=Mock();user=SimpleNamespace(id='owner')
    owned=Mock(side_effect=[row,workspace]);monkeypatch.setattr(agent.workspaces,'owned',owned)
    monkeypatch.setattr(agent.session_lifecycle,'state',lambda *a:state)
    lock=Mock();monkeypatch.setattr(agent.session_lifecycle,'lock_workspace',lock)
    result=agent.rename_session('s',agent.RenameSession(title='  تصميم جديد  '),user,db)
    assert result['title']=='تصميم جديد' and result['lifecycle']==state
    assert row.opencode_session_id=='runtime' and row.status=='completed'
    assert all(call.args[-1]=='owner' for call in owned.call_args_list)
    lock.assert_called_once_with(db,workspace);db.commit.assert_called_once()

@pytest.mark.parametrize('hidden',['foreign','deleted'])
def test_inaccessible_session_cannot_be_renamed(monkeypatch,hidden):
    db=Mock();row=SimpleNamespace(title='Old',workspace_id='w')
    if hidden=='foreign':monkeypatch.setattr(agent.workspaces,'owned',Mock(side_effect=HTTPException(404,'Not found')))
    else:
        monkeypatch.setattr(agent.workspaces,'owned',Mock(side_effect=[row,SimpleNamespace()]))
        monkeypatch.setattr(agent.session_lifecycle,'state',lambda *a:'deleted')
    with pytest.raises(HTTPException) as error:agent.rename_session('s',agent.RenameSession(title='New'),SimpleNamespace(id='other'),db)
    assert error.value.status_code==404
    assert row.title=='Old';db.commit.assert_not_called()

@pytest.mark.parametrize('action,expected',[('archive_session','archived'),('restore_session','closed'),('delete_session','deleted')])
def test_existing_history_actions_preserve_files_and_runtime(monkeypatch,action,expected):
    row=SimpleNamespace(id='s',workspace_id='w',title='Keep',status='completed',created_at=None,opencode_session_id='runtime')
    db=Mock();monkeypatch.setattr(agent.workspaces,'owned',Mock(side_effect=[row,SimpleNamespace()]))
    monkeypatch.setattr(agent.session_lifecycle,'state',lambda *a:'archived' if action=='restore_session' else 'closed')
    monkeypatch.setattr(agent.session_lifecycle,'lock_workspace',Mock())
    change=Mock();monkeypatch.setattr(agent.session_lifecycle,'set_state',change)
    getattr(agent,action)('s',SimpleNamespace(id='owner'),db)
    change.assert_called_once_with(db,row,expected);db.commit.assert_called_once();db.delete.assert_not_called()
    assert row.opencode_session_id=='runtime' and row.title=='Keep'

@pytest.mark.parametrize('action',['archive_session','delete_session'])
def test_history_actions_do_not_interrupt_running_agent(monkeypatch,action):
    row=SimpleNamespace(workspace_id='w',status='submitted');db=Mock()
    monkeypatch.setattr(agent.workspaces,'owned',Mock(side_effect=[row,SimpleNamespace()]))
    monkeypatch.setattr(agent.session_lifecycle,'state',lambda *a:'active')
    monkeypatch.setattr(agent.session_lifecycle,'lock_workspace',Mock())
    with pytest.raises(HTTPException) as error:getattr(agent,action)('s',SimpleNamespace(id='owner'),db)
    assert error.value.status_code==409;db.commit.assert_not_called();db.delete.assert_not_called()
