"""Batch 1 only: real OpenCode auth storage; no real provider OAuth/model calls."""
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from backend.tests.test_disposable_database import account

pytestmark = pytest.mark.skipif(os.getenv("AUDIT_DISPOSABLE_DB")!="1" or os.getenv("AUDIT_RUN_OPENCODE")!="1",
                               reason="requires disposable DB and existing pinned OpenCode")


def payload(label, increment=0):
    return {"type":"oauth","access":label+"-fake-access","refresh":label+"-fake-refresh",
            "expires":int(time.time()*1000)+3600000+increment}


def save(db,uid,value):
    from backend.app.models import UserProviderCredential
    from backend.app.services import credentials
    row=UserProviderCredential(user_id=uid,provider_id="fixture-oauth",ciphertext=credentials.encrypt(json.dumps(value)),last4="")
    db.add(row);db.commit();return row


def test_rotation_busy_retry_restart_revocation_and_second_user(account):
    from backend.app.database import SessionLocal
    from backend.app.models import User,UserProviderCredential,Workspace,WorkspaceSession
    from backend.app.services import opencode,account_provider_sync as sync
    from backend.app.security.passwords import hash_password
    client,_,profile,_=account
    uid=uuid.UUID(profile["id"]); owned=[]; other_id=uuid.uuid4()
    try:
        with SessionLocal() as db:
            now=datetime.now(timezone.utc)
            db.add(User(id=other_id,username="other_"+uuid.uuid4().hex[:10],email=uuid.uuid4().hex+"@example.org",
                        password_hash=hash_password("Fixture!Pass123"),phone="777111111",postal_code="967",status="active",
                        trial_started_at=now,trial_ends_at=now+timedelta(days=30)))
            db.commit(); row=save(db,uid,payload("first"));row_id=row.id
            other=save(db,other_id,payload("other"));other_cipher=other.ciphertext
        account_ref,account_service=opencode.for_account(uid)
        other_ref,other_service=opencode.for_account(other_id)
        other_path=opencode.settings.runtime_root/str(other_id)/str(other_ref.id)/"data/opencode/auth.json"
        other_bytes=other_path.read_bytes()
        for name in ["Batch1 live","Batch1 stopped"]:
            response=client.post("/api/projects",json={"project_name":name})
            assert response.status_code==201,response.text
            with SessionLocal() as db:owned.append(db.get(Workspace,uuid.UUID(response.json()["workspace"]["id"])))
            opencode.for_workspace(owned[-1])
        opencode.stop_workspace(owned[1])
        service=opencode.for_workspace(owned[0]);pid=opencode._runtimes[str(owned[0].id)].process.pid
        rotated=payload("rotation",60000)
        assert service.request("PUT","/auth/fixture-oauth",rotated) is True
        sync.sweep()
        with SessionLocal() as db:assert sync.decode(db.get(UserProviderCredential,row_id))==rotated
        opencode.for_workspace(owned[1])
        second_path=opencode.settings.runtime_root/str(uid)/str(owned[1].id)/"data/opencode/auth.json"
        assert json.loads(second_path.read_text())["fixture-oauth"]==rotated
        with SessionLocal() as db:
            busy=WorkspaceSession(user_id=uid,workspace_id=owned[0].id,opencode_session_id="ses_fixture",title="Busy guard",status="submitted")
            db.add(busy);db.commit();busy_id=busy.id
        newest=payload("newest",120000)
        account_service.request("PUT","/auth/fixture-oauth",newest)
        before=service.call_counts.get("POST /instance/dispose",0)
        sync.sweep()
        assert service.call_counts.get("POST /instance/dispose",0)==before
        assert opencode._runtimes[str(owned[0].id)].process.pid==pid
        with SessionLocal() as db:db.get(WorkspaceSession,busy_id).status="completed";db.commit()
        sync.sweep()
        assert service.call_counts.get("POST /instance/dispose",0)>before
        assert opencode._runtimes[str(owned[0].id)].process.pid==pid
        assert other_path.read_bytes()==other_bytes
        with SessionLocal() as db:
            assert db.scalar(select(UserProviderCredential.ciphertext).where(UserProviderCredential.user_id==other_id))==other_cipher
        assert client.delete("/api/opencode/connections/fixture-oauth").status_code==204
        opencode.stop_workspace(account_ref)
        # Simulate a crash after DB revocation but before old private-file cleanup.
        account_path=opencode.settings.runtime_root/str(uid)/str(account_ref.id)/"data/opencode/auth.json"
        account_path.write_text(json.dumps({"fixture-oauth":newest}))
        opencode.for_account(uid)
        assert "fixture-oauth" not in json.loads(account_path.read_text())
        assert other_path.read_bytes()==other_bytes
    finally:
        for workspace in owned:opencode.stop_workspace(workspace)
        opencode.stop_workspace(opencode.account_workspace(uid));opencode.stop_workspace(opencode.account_workspace(other_id))


def test_expired_account_oauth_explicit_reauthorization_and_stale_callback(account,monkeypatch):
    from backend.app.database import SessionLocal
    from backend.app.models import UserProviderCredential
    from backend.app.services import opencode,providers,credentials,account_provider_sync as sync
    client,_,profile,_=account;uid=uuid.UUID(profile["id"])
    with SessionLocal() as db:
        expired=payload("expired");expired["expires"]=1
        row=save(db,uid,expired);identifier=row.id
    def authorize(service,provider_id,method,inputs):
        service.oauth_pending[provider_id]=method
        return {"url":"https://provider.invalid/fixture","method":"code","instructions":"fixture only"}
    refreshed=payload("authorized",60000)
    def callback(service,provider_id,method,code):
        assert service.oauth_pending[provider_id]==method
        return service.request("PUT","/auth/"+provider_id,refreshed)
    monkeypatch.setattr(providers,"oauth_authorize",authorize)
    accepted=__import__('unittest.mock',fromlist=['Mock']).Mock(side_effect=callback)
    monkeypatch.setattr(providers,"oauth_callback",accepted)
    try:
        base="/api/opencode/connections/fixture-oauth/oauth/"
        assert client.post(base+"authorize",json={"method":0}).status_code==409
        assert client.post(base+"authorize",json={"method":0,"reauthorize":True}).status_code==200
        result=client.post(base+"callback",json={"method":0,"code":"fake-code"})
        assert result.status_code==200,result.text
        with SessionLocal() as db:
            row=db.get(UserProviderCredential,identifier)
            assert sync.decode(row)==refreshed
        assert client.post(base+"callback",json={"method":0,"code":"fake-code"}).status_code==409
        assert client.post(base+"authorize",json={"method":0,"reauthorize":True}).status_code==200
        with SessionLocal() as db:
            row=db.get(UserProviderCredential,identifier);row.ciphertext=credentials.encrypt(json.dumps(payload("competing",120000)));db.commit()
        assert client.post(base+"callback",json={"method":0,"code":"old-code"}).status_code==409
        assert accepted.call_count==1
    finally:opencode.stop_workspace(opencode.account_workspace(uid))
