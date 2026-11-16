"""Exercise real encrypted preview grants against session/tenant boundaries.

No database, browser, Docker, network or customer files are accessed.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import json
import uuid
import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from app.services import preview_access as access

@pytest.fixture
def context(monkeypatch):
    now=datetime(2026,11,16,14,0,tzinfo=timezone.utc)
    owner,session_id,workspace_id,project_id=[uuid.uuid4() for _ in range(4)]
    user=SimpleNamespace(id=owner)
    session=SimpleNamespace(id=session_id,user_id=owner,user=user,revoked_at=None)
    project=SimpleNamespace(user_id=owner,archived_at=None)
    workspace=SimpleNamespace(id=workspace_id,user_id=owner,project_id=project_id,
                              project=project,status='ready')
    cipher=Fernet(Fernet.generate_key())
    monkeypatch.setattr(access,'_cipher',lambda:cipher)
    monkeypatch.setattr(access,'origins',lambda:('https://gateway.example','https://preview.example'))
    monkeypatch.setattr(access,'idle_expires_at',lambda s:now+timedelta(hours=1))
    monkeypatch.setattr(access,'normal_access_ready',lambda u:True)
    lease={'value':'a'*64}
    monkeypatch.setattr(access,'_lease',lambda w:lease['value'])
    def owned(db,model,identifier,user_id):
        if identifier!=workspace.id or user_id!=workspace.user_id:
            raise HTTPException(404,'Not found')
        return workspace
    monkeypatch.setattr(access.workspaces,'owned',owned)
    db=SimpleNamespace(get=lambda model,key:session if key==session.id else None)
    request=SimpleNamespace(url='https://preview.example/preview/placeholder/')
    minted=access.mint(workspace,session,user,now=now)
    token=minted['url'].split('/preview/')[1].rstrip('/')
    return SimpleNamespace(now=now,user=user,session=session,workspace=workspace,
                           db=db,request=request,token=token,cipher=cipher,lease=lease)

def authorize(c,token=None,now=None):
    return access.authorize(token or c.token,c.request,c.db,now=now or c.now)

def altered(c,**changes):
    payload=json.loads(c.cipher.decrypt_at_time(c.token.encode(),ttl=300,current_time=int(c.now.timestamp())))
    payload.update(changes)
    return c.cipher.encrypt_at_time(json.dumps(payload).encode(),int(c.now.timestamp())).decode()

def test_owner_with_current_session_and_lease_is_authorized(context):
    workspace,origin,lease=authorize(context)
    assert workspace is context.workspace
    assert origin=='https://gateway.example' and lease=='a'*64

@pytest.mark.parametrize('seconds',[300,301,901])
def test_expired_grant_is_rejected(context,seconds):
    with pytest.raises(HTTPException) as error:
        authorize(context,now=context.now+timedelta(seconds=seconds))
    assert error.value.status_code==401

def test_tampered_ciphertext_is_rejected(context):
    token=context.token
    replacement='A' if token[30]!='A' else 'B'
    with pytest.raises(HTTPException) as error:
        authorize(context,token[:30]+replacement+token[31:])
    assert error.value.status_code==401

@pytest.mark.parametrize('token',['not-a-token','../secret','x'*2049])
def test_invalid_grant_encoding_is_rejected(context,token):
    with pytest.raises(HTTPException) as error: authorize(context,token)
    assert error.value.status_code==401

def test_revoked_session_immediately_invalidates_grant(context):
    context.session.revoked_at=context.now
    with pytest.raises(HTTPException) as error: authorize(context)
    assert error.value.status_code==401

def test_unknown_session_is_rejected(context):
    with pytest.raises(HTTPException) as error:
        authorize(context,altered(context,sid=str(uuid.uuid4())))
    assert error.value.status_code==401

def test_session_cannot_be_rebound_to_another_user(context):
    with pytest.raises(HTTPException) as error:
        authorize(context,altered(context,uid=str(uuid.uuid4())))
    assert error.value.status_code==401

def test_another_workspace_is_not_authorized(context):
    with pytest.raises(HTTPException) as error:
        authorize(context,altered(context,wid=str(uuid.uuid4())))
    assert error.value.status_code==404

def test_another_project_is_not_authorized(context):
    with pytest.raises(HTTPException) as error:
        authorize(context,altered(context,pid=str(uuid.uuid4())))
    assert error.value.status_code==401

def test_project_owner_is_rechecked_at_read_time(context):
    context.workspace.project.user_id=uuid.uuid4()
    with pytest.raises(HTTPException) as error: authorize(context)
    assert error.value.status_code==404

@pytest.mark.parametrize('status',['archived','deleted','cache_expired'])
def test_inaccessible_workspace_invalidates_existing_grant(context,status):
    context.workspace.status=status
    with pytest.raises(HTTPException) as error: authorize(context)
    assert error.value.status_code==404

def test_archived_project_invalidates_existing_grant(context):
    context.workspace.project.archived_at=context.now
    with pytest.raises(HTTPException) as error: authorize(context)
    assert error.value.status_code==404

def test_runtime_restart_invalidates_previous_grant(context):
    context.lease['value']='b'*64
    with pytest.raises(HTTPException) as error: authorize(context)
    assert error.value.status_code==401

@pytest.mark.parametrize('changes',[{'purpose':'other'},{'origin':'https://attacker.example'}])
def test_grant_purpose_and_origin_cannot_change(context,changes):
    with pytest.raises(HTTPException) as error: authorize(context,altered(context,**changes))
    assert error.value.status_code==401

def test_gateway_origin_cannot_serve_customer_preview(context):
    context.request.url='https://gateway.example/preview/placeholder/'
    with pytest.raises(HTTPException) as error: authorize(context)
    assert error.value.status_code==404
