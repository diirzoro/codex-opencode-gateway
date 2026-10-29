"""24h retention uses OpenCode Native deletion, never Python AI/history storage."""
import asyncio
from datetime import datetime, timedelta, timezone
from dataclasses import replace
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
import pytest
from backend.tests.test_native_control_plane import boundary
from backend.app import database, models
from backend.app.routes import native_sessions as native
from backend.app.services import chat_attachments as uploads, workspace_cache


def prepare(boundary, monkeypatch, tmp_path, *, hours_old=25, native_hours_old=25,
            idle=True, correct_directory=True, deletion_result=True):
    client, owners, _, engine, config=boundary
    a,b=owners
    monkeypatch.setattr(database,'SessionLocal',sessionmaker(bind=engine))
    monkeypatch.setattr(workspace_cache,'runtime_idle',lambda workspace:idle)
    monkeypatch.setattr(uploads,'settings',replace(config,runtime_root=tmp_path/'metadata'))
    monkeypatch.setattr(native,'_native_history_cursor',None)
    now=datetime.now(timezone.utc)
    with Session(engine) as db:
        row=db.get(models.WorkspaceSession,a.session)
        row.created_at=now-timedelta(hours=hours_old)
        db.commit()
    calls=[]
    def metadata(method,path,root,data=None):
        calls.append((method,path,str(root)))
        if method=='GET' and path=='/session/ses_a':
            return {'id':'ses_a',
                    'directory':str(a.root) if correct_directory else str(b.root),
                    'time':{'updated':int((now-timedelta(hours=native_hours_old)).timestamp()*1000)}}
        if method=='DELETE' and path=='/session/ses_a':return deletion_result
        raise AssertionError((method,path))
    monkeypatch.setattr(native,'metadata',metadata)
    return a,b,engine,calls


def test_idle_old_owned_chat_deleted_through_native_and_its_temp_files_only(boundary,monkeypatch,tmp_path):
    a,b,engine,calls=prepare(boundary,monkeypatch,tmp_path)
    with Session(engine) as db:
        workspace=db.get(models.Workspace,a.workspace)
        item=uploads.create(db,workspace,a.session,'owned.txt',4,'text/plain')
        async def stream():
            yield b'test'
        asyncio.run(uploads.upload(workspace,item['id'],type('Req',(),{'stream':lambda self:stream()})()))
        assert (a.root/item['path']).is_file()
    answer=native.sweep_expired_native_history()
    assert answer['deleted']==1
    assert any(method=='DELETE' and path=='/session/ses_a' for method,path,_ in calls)
    with Session(engine) as db:
        assert db.get(models.WorkspaceSession,a.session) is None
        assert db.get(models.WorkspaceSession,b.session) is not None
    assert not (a.root/item['path']).exists()
    assert (a.root/'marker.txt').is_file()
    assert (b.root/'marker.txt').is_file()


@pytest.mark.parametrize('parameter',[
    {'native_hours_old':1},
    {'hours_old':1},
    {'idle':False},
    {'correct_directory':False},
    {'deletion_result':False},
])
def test_retention_preserves_recent_active_foreign_or_unconfirmed_sessions(boundary,monkeypatch,tmp_path,parameter):
    a,b,engine,calls=prepare(boundary,monkeypatch,tmp_path,**parameter)
    result=native.sweep_expired_native_history()
    assert result['deleted']==0
    with Session(engine) as db:
        assert db.get(models.WorkspaceSession,a.session) is not None
        assert db.get(models.WorkspaceSession,b.session) is not None
    assert (a.root/'marker.txt').is_file()
    assert (b.root/'marker.txt').is_file()


def test_malformed_native_time_never_deletes_chat(boundary,monkeypatch,tmp_path):
    a,b,engine,calls=prepare(boundary,monkeypatch,tmp_path)
    monkeypatch.setattr(native,'metadata',lambda method,path,root,data=None: {
        'id':'ses_a','directory':str(a.root),'time':{'updated':'not-a-number'}})
    result=native.sweep_expired_native_history()
    assert result['deleted']==0
    with Session(engine) as db:assert db.get(models.WorkspaceSession,a.session) is not None
