"""A stream must not reserve a pooled DB connection while the client waits."""
import asyncio,inspect,os,uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://test:test@127.0.0.1/test')
from sqlalchemy import create_engine,text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from backend.app.routes import agent
from backend.app.models import ExecutionEvent


def test_event_stream_releases_request_and_poll_connections(monkeypatch):
    engine=create_engine('sqlite://',poolclass=QueuePool,pool_size=1,max_overflow=0,pool_timeout=.05,connect_args={'check_same_thread':False})
    ExecutionEvent.__table__.create(engine)
    factory=sessionmaker(bind=engine)
    with factory() as seeded:
        seeded.add(ExecutionEvent(id=1,session_id=uuid.UUID(int=1),kind='activity',data='{}'));seeded.commit()
    user=SimpleNamespace(id='user')
    def owned(db,*args):db.execute(text('select 1'));return None,None
    monkeypatch.setattr(agent,'context',lambda db,u,s:owned(db))
    monkeypatch.setattr(agent,'require_user',lambda request,db:user)
    monkeypatch.setattr(agent,'SessionLocal',factory)
    async def scenario():
        with factory() as db:
            response=agent.events(uuid.UUID(int=1),SimpleNamespace(is_disconnected=AsyncMock(return_value=False)),0,None,user,db)
            if inspect.isawaitable(response):response=await response
            assert engine.pool.checkedout()==0,'Request transaction held for SSE lifetime'
            try:
                assert await anext(response.body_iterator)=='id: 1\nevent: activity\ndata: {}\n\n'
                assert engine.pool.checkedout()==0,'Polling session held during client yield'
            finally:await response.body_iterator.aclose()
    try:asyncio.run(scenario())
    finally:engine.dispose()
