"""Bounded durable follow-ups in existing owned-session events; no runtime bypass."""
import hashlib
import json
from fastapi import HTTPException
from sqlalchemy import select
from ..models import ExecutionEvent

LIMIT=20
KINDS={'message_queued','queue_dispatched','queue_removed','queue_failed','queue_claimed'}


def entries(db,session_id):
    values={}
    rows=db.scalars(select(ExecutionEvent).where(ExecutionEvent.session_id==session_id,
                    ExecutionEvent.kind.in_(KINDS)).order_by(ExecutionEvent.id))
    for row in rows:
        data=json.loads(row.data);key=data['request_id']
        if row.kind=='message_queued':values[key]={**data,'state':'queued'}
        elif key in values:values[key]['state']={'queue_dispatched':'submitted','queue_removed':'cancelled','queue_failed':'failed','queue_claimed':'claimed'}[row.kind]
    return list(values.values())


def add(db,session_id,payload):
    data=payload.model_dump(mode='json');key=data['request_id']
    fingerprint=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
    rows=entries(db,session_id)
    previous=next((row for row in rows if row['request_id']==key),None)
    if previous:
        if previous['fingerprint']!=fingerprint:raise HTTPException(409,'Queue request ID belongs to a different message')
        return previous
    if sum(row['state'] in {'queued','claimed'} for row in rows)>=LIMIT:raise HTTPException(409,'Conversation queue is full (20 messages)')
    value={'request_id':key,'fingerprint':fingerprint,'payload':data}
    db.add(ExecutionEvent(session_id=session_id,kind='message_queued',data=json.dumps(value)))
    db.commit()
    return {**value,'state':'queued'}


def record(db,session_id,request_id,kind):
    if kind not in KINDS-{'message_queued'}:raise ValueError('Invalid queue event')
    db.add(ExecutionEvent(session_id=session_id,kind=kind,data=json.dumps({'request_id':str(request_id)})))
    db.commit()


def paused(db,session_id):
    row=db.scalar(select(ExecutionEvent).where(ExecutionEvent.session_id==session_id,
                  ExecutionEvent.kind.in_({'queue_paused','queue_resumed'})).order_by(ExecutionEvent.id.desc()).limit(1))
    return bool(row and row.kind=='queue_paused')


def queued_request(db,session_id,request_id):
    # UUID-only, exact serialized field; no raw user text in the predicate.
    needle='"request_id": "'+str(request_id)+'"'
    return db.scalar(select(ExecutionEvent.id).where(ExecutionEvent.session_id==session_id,
                     ExecutionEvent.kind=='message_queued',ExecutionEvent.data.contains(needle)).limit(1)) is not None
