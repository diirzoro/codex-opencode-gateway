"""Disposable SQLite event storage + controlled dispatch; not native PG certification."""
import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import Mock
import uuid
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://test:test@127.0.0.1/test')
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from backend.app.models import ExecutionEvent,WorkspaceSession,User
from backend.app.routes import agent
from backend.app.services import message_queue,entitlements
from backend.app.security import sessions

@pytest.fixture
def db():
    engine=create_engine('sqlite://')
    ExecutionEvent.__table__.create(engine)
    with Session(engine) as session:yield session
    engine.dispose()

def payload(text='Follow-up',request_id=None):
    return agent.MessageRequest(request_id=request_id or uuid.uuid4(),text=text,provider_id='opencode',model_id='model')


def test_order_receipts_and_rollback(db):
    sid=uuid.uuid4();one=payload('first');two=payload('second')
    message_queue.add(db,sid,one);message_queue.add(db,sid,two);message_queue.add(db,sid,one)
    assert [row['payload']['text'] for row in message_queue.entries(db,sid)]==['first','second']
    with pytest.raises(HTTPException) as error:message_queue.add(db,sid,payload('different',one.request_id))
    assert error.value.status_code==409
    db.add(ExecutionEvent(session_id=sid,kind='message_queued',data='{}'));db.rollback()
    assert len(message_queue.entries(db,sid))==2


def test_state_persistence_and_session_isolation(db):
    one,two=uuid.uuid4(),uuid.uuid4();a,b=payload(),payload()
    message_queue.add(db,one,a);message_queue.add(db,two,b)
    message_queue.record(db,one,a.request_id,'queue_claimed')
    assert message_queue.entries(db,one)[0]['state']=='claimed'
    message_queue.record(db,one,a.request_id,'queue_dispatched')
    db.expire_all()
    assert message_queue.entries(db,one)[0]['state']=='submitted'
    assert message_queue.entries(db,two)[0]['state']=='queued'
    message_queue.record(db,two,b.request_id,'queue_removed')
    assert message_queue.entries(db,two)[0]['state']=='cancelled'


def test_queue_bound_and_failed_status(db):
    sid=uuid.uuid4()
    for index in range(20):message_queue.add(db,sid,payload(str(index)))
    with pytest.raises(HTTPException):message_queue.add(db,sid,payload('overflow'))
    first=message_queue.entries(db,sid)[0]
    message_queue.record(db,sid,first['request_id'],'queue_failed')
    message_queue.add(db,sid,payload('replacement'))
    assert sum(row['state']=='queued' for row in message_queue.entries(db,sid))==20


def environment(monkeypatch,status='completed',allowed=True,active=True):
    sid=uuid.uuid4();user=SimpleNamespace(id=uuid.uuid4())
    session=SimpleNamespace(id=sid,user_id=user.id,status=status)
    workspace=SimpleNamespace(id=uuid.uuid4())
    db=Mock();db.__enter__=Mock(return_value=db);db.__exit__=Mock(return_value=False)
    db.get.side_effect=lambda model,key:session if model is WorkspaceSession else user
    monkeypatch.setattr(agent,'SessionLocal',lambda:db)
    monkeypatch.setattr(message_queue,'paused',lambda *args:False)
    monkeypatch.setattr(agent,'context',lambda *args:(session,workspace))
    monkeypatch.setattr(agent.session_lifecycle,'state',lambda *args:'active' if active else 'archived')
    monkeypatch.setattr(agent.session_lifecycle,'lock_workspace',lambda *args:None)
    monkeypatch.setattr(sessions,'normal_access_ready',lambda *args:True)
    monkeypatch.setattr(entitlements,'access_payload',lambda *args:{'allowed':allowed})
    return sid,session,db

@pytest.mark.parametrize('status',['submitted','waiting_approval','failed','cancelled'])
def test_auto_dispatch_never_crosses_busy_or_paused_state(monkeypatch,status):
    sid,session,db=environment(monkeypatch,status)
    send=Mock();monkeypatch.setattr(agent,'send',send)
    assert asyncio.run(agent.dispatch_queued(sid))['status']=='waiting'
    send.assert_not_called()

@pytest.mark.parametrize('allowed,active',[(False,True),(True,False)])
def test_dispatch_rechecks_entitlement_and_visibility(monkeypatch,allowed,active):
    sid,session,db=environment(monkeypatch,allowed=allowed,active=active)
    assert asyncio.run(agent.dispatch_queued(sid))['status']=='paused'


def test_dispatch_fifo_uses_existing_send_and_exact_request_id(monkeypatch):
    sid,session,db=environment(monkeypatch);one,two=payload('first'),payload('second')
    monkeypatch.setattr(message_queue,'entries',lambda *args:[{'state':'queued','payload':p.model_dump(mode='json')} for p in [one,two]])
    records=[];monkeypatch.setattr(message_queue,'record',lambda *args:records.append((str(args[2]),args[3])))
    sent=[]
    async def send(identifier,data,user,database):sent.append(data);return {'status':'submitted'}
    monkeypatch.setattr(agent,'send',send)
    assert asyncio.run(agent.dispatch_queued(sid))['status']=='submitted'
    assert len(sent)==1 and sent[0].request_id==one.request_id
    assert records==[(str(one.request_id),'queue_claimed'),(str(one.request_id),'queue_dispatched')]


def test_explicit_resume_and_preflight_failure_does_not_retry(monkeypatch):
    sid,session,db=environment(monkeypatch,status='failed');one=payload()
    monkeypatch.setattr(message_queue,'entries',lambda *args:[{'state':'queued','payload':one.model_dump(mode='json')}])
    records=[];monkeypatch.setattr(message_queue,'record',lambda *args:records.append(args[3]))
    async def fail(*args):raise HTTPException(403,'private')
    monkeypatch.setattr(agent,'send',fail)
    assert asyncio.run(agent.dispatch_queued(sid,resume=True))=={'status':'paused'}
    assert records==['queue_claimed','queue_failed']


def test_queue_routes_reject_other_user_before_accessing_payload(monkeypatch):
    def deny(*args):raise HTTPException(404,'Not found')
    monkeypatch.setattr(agent,'context',deny)
    for function,args in [(agent.queued_messages,()),(agent.enqueue_message,(payload(),)),
                          (agent.remove_queued_message,(uuid.uuid4(),))]:
        with pytest.raises(HTTPException) as error:function(uuid.uuid4(),*args,user=SimpleNamespace(id=uuid.uuid4()),db=Mock())
        assert error.value.status_code==404


def test_pause_and_request_membership_are_durable_and_session_scoped(db):
    sid,other=uuid.uuid4(),uuid.uuid4();item=payload()
    message_queue.add(db,sid,item)
    assert message_queue.queued_request(db,sid,item.request_id)
    assert not message_queue.queued_request(db,other,item.request_id)
    db.add(ExecutionEvent(session_id=sid,kind='queue_paused',data='{}'));db.commit()
    assert message_queue.paused(db,sid) and not message_queue.paused(db,other)
    db.add(ExecutionEvent(session_id=sid,kind='queue_resumed',data='{}'));db.commit()
    assert not message_queue.paused(db,sid)


def test_auto_dispatch_obeys_explicit_stop_pause_even_after_completion(monkeypatch):
    sid,session,db=environment(monkeypatch)
    monkeypatch.setattr(message_queue,'paused',lambda *args:True)
    monkeypatch.setattr(message_queue,'entries',lambda *args:[{'state':'queued','payload':payload().model_dump(mode='json')}])
    send=Mock();monkeypatch.setattr(agent,'send',send)
    assert asyncio.run(agent.dispatch_queued(sid))=={'status':'paused'}
    send.assert_not_called()


def test_concurrent_dispatchers_share_one_admission(monkeypatch):
    sid,session,db=environment(monkeypatch);item=payload()
    monkeypatch.setattr(message_queue,'entries',lambda *args:[{'state':'queued','payload':item.model_dump(mode='json')}])
    monkeypatch.setattr(message_queue,'record',lambda *args:None)
    called=[]
    async def scenario():
        released=asyncio.Event()
        async def send(*args):called.append(args);await released.wait();return {'status':'submitted'}
        monkeypatch.setattr(agent,'send',send)
        first=asyncio.create_task(agent.dispatch_queued(sid));await asyncio.sleep(0)
        assert await agent.dispatch_queued(sid)=={'status':'waiting'}
        released.set();await first
    asyncio.run(scenario());assert len(called)==1


def test_execute_finishes_before_advancing_queue(monkeypatch):
    monkeypatch.setattr(agent,'begin_execution',lambda *args:object())
    monkeypatch.setattr(agent,'attachment_metadata',lambda *args:[])
    async def observe(*args):return
    monkeypatch.setattr(agent,'monitor_activity',observe)
    order=[]
    monkeypatch.setattr(agent,'complete_execution',lambda *args,**kw:order.append(args[1]))
    async def advance(*args):order.append('queue_check')
    monkeypatch.setattr(agent,'dispatch_queued',advance)
    service=SimpleNamespace(generation=1,session_path=lambda *args:'/message',request=lambda *args:{'info':{'role':'assistant','time':{'completed':1}},'parts':[]})
    asyncio.run(agent.execute(uuid.uuid4(),service,'runtime',payload(),'message'))
    assert order==['completed','queue_check']


def test_queue_admission_is_idempotent_after_runtime_admission(monkeypatch,db):
    sid=uuid.uuid4();session=SimpleNamespace(id=sid);workspace=SimpleNamespace()
    item=payload();message_queue.add(db,sid,item);message_queue.record(db,sid,item.request_id,'queue_dispatched')
    monkeypatch.setattr(agent,'context',lambda *args:(session,workspace))
    monkeypatch.setattr(agent.session_lifecycle,'lock_workspace',lambda *args:None)
    monkeypatch.setattr(agent.session_lifecycle,'state',lambda *args:'active')
    monkeypatch.setattr(db,'refresh',lambda *args:None)
    # Previously accepted receipt does not revalidate missing files or dispatch.
    monkeypatch.setattr(agent,'attachment_metadata',Mock(side_effect=AssertionError('replay must not inspect files')))
    assert agent.enqueue_message(sid,item,SimpleNamespace(),db)=={'status':'submitted','request_id':str(item.request_id)}
    assert len(message_queue.entries(db,sid))==1


def test_failed_queue_card_can_be_removed_after_preflight_receipt(monkeypatch,db):
    sid=uuid.uuid4();session=SimpleNamespace(id=sid);workspace=SimpleNamespace();item=payload()
    message_queue.add(db,sid,item);message_queue.record(db,sid,item.request_id,'queue_failed')
    monkeypatch.setattr(agent,'context',lambda *args:(session,workspace))
    monkeypatch.setattr(agent.session_lifecycle,'lock_workspace',lambda *args:None)
    monkeypatch.setattr(agent.session_lifecycle,'receipt',lambda *args:{'receipt':{'status':'failed'}})
    monkeypatch.setattr(db,'refresh',lambda *args:None)
    assert agent.remove_queued_message(sid,item.request_id,SimpleNamespace(),db)=={'status':'cancelled'}
    assert message_queue.entries(db,sid)[0]['state']=='cancelled'
