"""Focused OAuth/CAS tests. SQLite is not native PostgreSQL certification."""
import json
import os
import threading
import time
import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, update, select
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL","postgresql+psycopg://test:test@127.0.0.1/test")
from backend.app.models import UserProviderCredential
from backend.app.services import account_provider_sync as sync, credentials, opencode


def token(expiry, label="fixture"):
    return {"type":"oauth","access":label+"-access","refresh":label+"-refresh","expires":expiry}


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(sync,"settings",SimpleNamespace(runtime_root=tmp_path))
    monkeypatch.setattr(credentials,"settings",SimpleNamespace(credentials_encryption_key="fixture-only"))
    engine=create_engine("sqlite://")
    UserProviderCredential.__table__.create(engine)
    factory=sessionmaker(bind=engine,expire_on_commit=False)
    with factory() as db:
        owner=uuid.uuid4()
        workspace=SimpleNamespace(id=uuid.uuid4(),user_id=owner,is_account_runtime=True)
        row=UserProviderCredential(user_id=owner,provider_id="example",ciphertext=credentials.encrypt(json.dumps(token(1000))),last4="")
        db.add(row);db.commit()
        service=SimpleNamespace(credential_bindings={},auth_failures={},workspace_ref=workspace,
                                ensure_auth_idle=Mock(),refresh_auth=Mock(),state_lock=threading.RLock())
        path=tmp_path/str(owner)/str(workspace.id)/"data/opencode/auth.json"
        path.parent.mkdir(parents=True);path.write_text(json.dumps({"example":token(1000)}))
        sync.bind(service,row)
        yield db,workspace,service,row,path
    engine.dispose()


def test_rotation_is_encrypted_and_old_runtime_cannot_overwrite(store):
    db,workspace,service,row,path=store
    old=SimpleNamespace(credential_bindings=dict(service.credential_bindings))
    path.write_text(json.dumps({"example":token(3000,"new")}))
    assert sync.checkpoint(db,workspace,service,[row])==1
    assert "new-access" not in row.ciphertext
    assert sync.decode(row)==token(3000,"new")
    path.write_text(json.dumps({"example":token(2000,"old")}))
    assert sync.checkpoint(db,workspace,old,[row])==0
    assert sync.decode(row)==token(3000,"new")


def test_cas_rejects_competing_update_and_deleted_connection(store):
    db,workspace,service,row,path=store
    old=row.ciphertext
    newer=credentials.encrypt(json.dumps(token(5000,"winner")))
    db.execute(update(UserProviderCredential).where(UserProviderCredential.id==row.id).values(ciphertext=newer)
               .execution_options(synchronize_session=False));db.commit()
    path.write_text(json.dumps({"example":token(4000,"loser")}))
    assert sync.checkpoint(db,workspace,service,[row])==0
    assert db.scalar(select(UserProviderCredential.ciphertext))==newer
    db.delete(row);db.commit()
    assert sync.checkpoint(db,workspace,service,[row])==0
    assert db.scalar(select(UserProviderCredential.id)) is None


def test_second_account_unchanged_and_equal_expiry_rejected(store):
    db,workspace,service,row,path=store
    stranger=UserProviderCredential(user_id=uuid.uuid4(),provider_id="example",ciphertext=credentials.encrypt(json.dumps(token(1000,"other"))),last4="")
    db.add(stranger);db.commit();before=stranger.ciphertext
    path.write_text(json.dumps({"example":token(1000,"equal")}))
    assert sync.checkpoint(db,workspace,service,[row])==0
    path.write_text(json.dumps({"example":token(2000,"updated")}))
    assert sync.checkpoint(db,workspace,service,[row])==1
    db.refresh(stranger);assert stranger.ciphertext==before


def test_failed_commit_does_not_advance_binding(store,monkeypatch):
    db,workspace,service,row,path=store
    before=dict(service.credential_bindings)
    path.write_text(json.dumps({"example":token(2000,"rotation")}))
    monkeypatch.setattr(db,"commit",Mock(side_effect=RuntimeError("fixture failure")))
    with pytest.raises(RuntimeError):sync.checkpoint(db,workspace,service,[row])
    db.rollback()
    assert service.credential_bindings==before
    assert sync.decode(row)==token(1000)


def test_restart_recovers_file_rotation_but_not_after_reconnect(store):
    db,workspace,service,row,path=store
    path.write_text(json.dumps({"example":token(3000,"crash-recovery")}))
    assert json.loads(sync.startup_value(workspace,row))==token(3000,"crash-recovery")
    row.ciphertext=credentials.encrypt(json.dumps(token(4000,"reconnected")));db.commit()
    assert json.loads(sync.startup_value(workspace,row))==token(4000,"reconnected")


def test_parent_symlink_is_rejected(store,tmp_path):
    db,workspace,service,row,path=store
    path.unlink();path.parent.rmdir();path.parent.symlink_to(tmp_path,target_is_directory=True)
    with pytest.raises(ValueError):sync.read_auth(workspace)


@pytest.mark.skipif(not hasattr(os,"O_NOFOLLOW"),reason="POSIX no-follow descriptors required")
def test_symlink_cannot_bypass_a_stale_path_precheck(store,tmp_path,monkeypatch):
    from pathlib import Path
    db,workspace,service,row,path=store
    path.unlink();path.parent.rmdir();path.parent.symlink_to(tmp_path,target_is_directory=True)
    monkeypatch.setattr(Path,"is_symlink",lambda path:False)
    with pytest.raises(ValueError):sync.read_auth(workspace)


def test_busy_sync_retries_without_install_or_stop(store,monkeypatch):
    db,workspace,service,row,path=store
    service.credential_bindings={}
    install=Mock();monkeypatch.setattr(__import__('backend.app.services.providers',fromlist=['restore_credential']),"restore_credential",install)
    service.ensure_auth_idle.side_effect=HTTPException(409,"busy")
    with pytest.raises(HTTPException):sync.reconcile(db,workspace,service,[row])
    install.assert_not_called();service.refresh_auth.assert_not_called()
    service.ensure_auth_idle.side_effect=None
    assert sync.reconcile(db,workspace,service,[row]) is True
    install.assert_called_once();service.refresh_auth.assert_called_once()
    assert sync.reconcile(db,workspace,service,[row]) is False


def test_expiry_failure_and_reauthorization_status(store):
    db,workspace,service,row,path=store
    assert sync.public_status(row,[service])["auth_status"]=="refresh_required"
    service.auth_failures["example"]=row.ciphertext
    assert sync.public_status(row,[service])["auth_status"]=="reauthorization_required"
    row.ciphertext=credentials.encrypt(json.dumps(token(int(time.time()*1000)+60000,"reauthorized")));db.commit()
    sync.bind(service,row)
    assert sync.public_status(row,[service])["auth_status"]=="connected"


def test_upstream_auth_failure_invalidates_composer_state():
    service=opencode.OpenCodeService("http://127.0.0.1")
    service.credential_bindings["example"]=(uuid.uuid4(),"cipher-version","fingerprint")
    service.client.close()
    service.client=httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={"info":{"error":{"name":"APIError","data":{"statusCode":401}}}})),base_url="http://test")
    try:
        revision=service.discovery_revision
        service.request("POST","/session/fixture/message",{"model":{"providerID":"example"}})
        assert service.auth_failures["example"]=="cipher-version"
        assert service.discovery_revision>revision
    finally:service.close()


def test_pending_authorization_is_not_checkpointed_or_overwritten(store):
    db,workspace,service,row,path=store
    service.oauth_pending={"example":0}
    path.write_text(json.dumps({"example":token(2000,"unconfirmed")}))
    assert sync.checkpoint(db,workspace,service,[row])==0
    service.credential_bindings={}
    assert sync.reconcile(db,workspace,service,[row]) is False
    service.ensure_auth_idle.assert_not_called()


def test_forged_foreign_binding_cannot_update_another_account(store):
    db,workspace,service,row,path=store
    workspace.user_id=uuid.uuid4()
    foreign_path=sync.settings.runtime_root/str(workspace.user_id)/str(workspace.id)/"data/opencode/auth.json"
    foreign_path.parent.mkdir(parents=True);foreign_path.write_text(json.dumps({"example":token(2000,"foreign")}))
    before=row.ciphertext
    assert sync.checkpoint(db,workspace,service,[row])==0
    db.refresh(row);assert row.ciphertext==before


def test_revoked_startup_file_is_pruned_without_touching_other_provider(store):
    db,workspace,service,row,path=store
    path.write_text(json.dumps({"example":token(1000),"keep":{"type":"api","key":"fixture"}}))
    assert sync.prune_revoked(workspace,[],set()) is True
    assert json.loads(path.read_text())=={"keep":{"type":"api","key":"fixture"}}


@pytest.mark.parametrize("value",[True,-1,"123"])
def test_invalid_oauth_expiry_is_rejected(value):
    with pytest.raises(ValueError):sync.oauth_payload({**token(1000),"expires":value})


def test_callback_cannot_use_another_users_pending_authorization(monkeypatch):
    from backend.app.routes import workspaces as routes
    user=SimpleNamespace(id=uuid.uuid4());db=Mock();db.scalar.return_value=None;db.scalars.return_value=[]
    monkeypatch.setattr(routes.user_provider_credentials,"require_schema",lambda db:None)
    monkeypatch.setattr(routes.user_provider_credentials,"find",lambda db,uid,pid:None)
    monkeypatch.setattr(routes,"require_advanced",lambda *a,**kw:None)
    monkeypatch.setattr(routes.policy,"load",lambda db:None)
    monkeypatch.setattr(routes.policy,"provider_allowed",lambda *a:True)
    other_pending={"example":(uuid.uuid4(),"other-cipher")}
    own_service=SimpleNamespace(state_lock=threading.RLock(),oauth_versions={})
    start=Mock(return_value=(opencode.account_workspace(user.id),own_service))
    monkeypatch.setattr(opencode,"for_account",start)
    callback=Mock();monkeypatch.setattr(routes.providers,"oauth_callback",callback)
    with pytest.raises(HTTPException) as denied:
        routes.account_oauth_callback("example",routes.OAuthCallback(method=0,code="fake"),user,db)
    assert denied.value.status_code==409
    start.assert_called_once_with(user.id,db=db);callback.assert_not_called()
    assert "example" in other_pending


def test_explicit_oauth_reauthorization_cannot_replace_an_api_key(store,monkeypatch):
    from backend.app.routes import workspaces as routes
    db,workspace,service,row,path=store
    row.ciphertext=credentials.encrypt(json.dumps({"type":"api","key":"fixture-api"}));db.commit()
    monkeypatch.setattr(routes,"require_advanced",lambda *a,**kw:None)
    monkeypatch.setattr(routes.policy,"load",lambda db:None)
    monkeypatch.setattr(routes.policy,"provider_allowed",lambda *a:True)
    start=Mock();monkeypatch.setattr(opencode,"for_account",start)
    with pytest.raises(HTTPException) as denied:
        routes.account_oauth_authorize("example",routes.OAuthAuthorize(method=0,reauthorize=True),SimpleNamespace(id=workspace.user_id),db)
    assert denied.value.status_code==409;start.assert_not_called()


def test_failed_oauth_is_not_usable_by_direct_workspace_requests(store,monkeypatch):
    from backend.app.models import AccountAudit
    from backend.app.services import providers
    db,workspace,service,row,path=store
    AccountAudit.__table__.create(db.bind)
    service.auth_failures["example"]=row.ciphertext
    monkeypatch.setattr(sync,"services_for",lambda uid:[service])
    result=providers.client_catalog(db,workspace,{"all":[{"id":"example","models":{}}],"connected":["example"]})
    assert result["connected"]==[]
    assert result["gateway_auth_status"]["example"]["auth_status"]=="reauthorization_required"
    assert "fake-access" not in json.dumps(result)


@pytest.mark.parametrize("revoked", [False, True])
def test_fanout_installs_only_current_version(store,monkeypatch,revoked):
    from backend.app.routes import workspaces as routes
    db,w,service,row,path=store
    old=row.ciphertext
    row.ciphertext=credentials.encrypt(json.dumps(token(9000,"current")));db.commit()
    fake_db=Mock();fake_db.scalars.return_value=[w]
    monkeypatch.setattr(routes.opencode,"for_workspace",lambda *a,**k:service)
    monkeypatch.setattr(sync,"require_idle",lambda *a:None)
    monkeypatch.setattr(routes.user_provider_credentials,"find",lambda *a:None if revoked else row)
    restore=Mock();monkeypatch.setattr(routes.providers,"restore_credential",restore)
    assert routes._refresh_other_user_runtimes(fake_db,w.user_id,None,"example",old)==[]
    if revoked:restore.assert_not_called()
    else:
        assert json.loads(restore.call_args.args[2])==token(9000,"current")
        assert service.credential_bindings["example"][1]==row.ciphertext
