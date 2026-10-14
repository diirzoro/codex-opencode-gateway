"""Opt-in integration tests. Run ONLY against a disposable loopback PostgreSQL DB.

AUDIT_DISPOSABLE_DB=1 DATABASE_URL=postgresql+psycopg://... pytest ...
The caller must apply Alembic first. SMTP delivery/model validation are mocked;
SQLAlchemy, ownership, encryption, HTTP auth and filesystem checks are real.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.skipif(os.getenv("AUDIT_DISPOSABLE_DB") != "1",
                               reason="requires explicitly disposable PostgreSQL")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1/test")


@pytest.fixture
def account(monkeypatch):
    from urllib.parse import urlsplit
    assert urlsplit(os.environ["DATABASE_URL"]).hostname in {"127.0.0.1", "localhost"}
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.services import email_verification
    sent = []
    monkeypatch.setattr(email_verification, "smtp_ready", lambda: True)
    monkeypatch.setattr(email_verification, "send_link", lambda email, token: sent.append((email, token)))
    client = TestClient(app, base_url="https://testserver")
    suffix = uuid.uuid4().hex[:12]
    data = dict(username="audit_"+suffix, email=suffix+"@example.org",
                password="Fixture!Pass123", phone="777123456", postal_code="967")
    registered = client.post("/api/auth/register", json=data)
    assert registered.status_code == 201, registered.text
    assert registered.json()["status"] == "pending_email"
    assert client.post("/api/auth/login", json={"identity": data["email"], "password": data["password"]}).status_code == 403
    assert len(sent) == 1
    token = sent[0][1]
    assert client.get("/api/auth/verify-email", params={"token": token}, follow_redirects=False).status_code == 303
    assert client.post("/api/auth/login", json={"identity": data["email"], "password": data["password"]}).status_code == 200
    yield client, data, registered.json(), token
    client.close()


def test_migrations_and_email_ownership(account):
    from sqlalchemy import text, select
    from backend.app.database import SessionLocal
    from backend.app.models import EmailVerification
    client, data, user, token = account
    with SessionLocal() as db:
        assert db.execute(text("select version_num from alembic_version")).scalar_one() == "0018_email_verification"
        assert db.execute(text("select count(*) from countries")).scalar_one() >= 249
        row = db.scalar(select(EmailVerification).where(EmailVerification.user_id == uuid.UUID(user["id"])))
        assert row.token_hash != token and row.used_at is not None
    assert client.get("/api/auth/verify-email", params={"token": token}).status_code == 400
    access = client.get("/api/profile/access").json()["access"]
    assert access["remaining_days"] == 30
    assert access["advanced_trial"]["state"] == "disabled"
    duplicate = client.post("/api/auth/register", json={**data, "email": data["email"].upper()})
    assert duplicate.status_code == 409
    disposable = client.post("/api/auth/register", json={**data, "username": "another_"+uuid.uuid4().hex[:10], "email": "fixture@mailinator.com"})
    assert disposable.status_code == 422


def test_resend_requires_password_cooldown_and_invalidates_old_link(account, monkeypatch):
    from sqlalchemy import select
    from backend.app.database import SessionLocal
    from backend.app.models import EmailVerification
    from backend.app.services import email_verification
    client,data,_,_=account
    links=[]
    monkeypatch.setattr(email_verification,"send_link",lambda email,token:links.append(token))
    data={**data,"username":"pending_"+uuid.uuid4().hex[:12],"email":uuid.uuid4().hex+"@example.org"}
    registered=client.post("/api/auth/register",json=data)
    assert registered.status_code == 201
    uid=uuid.UUID(registered.json()["id"])
    old=links[-1]
    payload={"identity":data["email"],"password":data["password"]}
    assert client.post("/api/auth/resend-verification",json={**payload,"password":"wrong"}).status_code == 401
    assert client.post("/api/auth/resend-verification",json=payload).status_code == 429
    with SessionLocal() as db:
        row=db.scalar(select(EmailVerification).where(EmailVerification.user_id==uid))
        row.created_at=datetime.now(timezone.utc)-timedelta(minutes=3);db.commit()
    assert client.post("/api/auth/resend-verification",json=payload).status_code == 200
    assert len(links)==2
    assert client.get("/api/auth/verify-email",params={"token":old}).status_code == 400
    assert client.get("/api/auth/verify-email",params={"token":links[-1]},follow_redirects=False).status_code == 303


def test_pending_email_cannot_use_even_a_valid_session(account):
    from backend.app.config import settings
    from backend.app.database import SessionLocal
    from backend.app.models import AuthSession
    from backend.app.security.sessions import new_session_token
    client, data, _, _ = account
    data = {**data, "email": uuid.uuid4().hex+"@example.org", "username": "pending_"+uuid.uuid4().hex[:12]}
    registered = client.post("/api/auth/register", json=data)
    assert registered.status_code == 201
    raw, hashed = new_session_token()
    with SessionLocal() as db:
        db.add(AuthSession(user_id=uuid.UUID(registered.json()["id"]), token_hash=hashed,
                           expires_at=datetime.now(timezone.utc)+timedelta(hours=1)))
        db.commit()
    client.cookies.clear()
    client.cookies.set(settings.session_cookie_name, raw)
    identifier = str(uuid.uuid4())
    checks = [("GET", "/api/auth/me", None), ("GET", "/api/profile", None),
              ("PATCH", "/api/profile", {}), ("GET", "/api/workspaces", None),
              ("GET", "/api/projects", None), ("GET", "/api/opencode/catalog/providers", None),
              ("GET", "/api/opencode/connections", None),
              ("GET", "/api/sessions/"+identifier+"/messages", None),
              ("GET", "/api/sessions/"+identifier+"/questions", None),
              ("POST", "/api/sessions/"+identifier+"/permissions/fixture", {"reply":"once"})]
    for method, path, payload in checks:
        assert client.request(method, path, json=payload).status_code == 403, (method, path)


@pytest.mark.skipif(os.getenv("AUDIT_DB_ENGINE") == "pglite", reason="requires native PostgreSQL error/rollback protocol")
@pytest.mark.parametrize("field", ["email", "username"])
def test_native_unique_identity_and_transaction_rollback(account, field):
    from sqlalchemy.exc import IntegrityError
    from backend.app.database import SessionLocal
    from backend.app.models import User
    _, data, user, _ = account
    with SessionLocal() as db:
        duplicate = User(username="unique_"+uuid.uuid4().hex[:12], email=uuid.uuid4().hex+"@example.org",
                         password_hash="fixture", phone="777111111", postal_code="967", status="pending_email")
        setattr(duplicate, field, data[field])
        db.add(duplicate)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.get(User, uuid.UUID(user["id"])) is not None


@pytest.mark.skipif(os.getenv("AUDIT_DB_ENGINE") == "pglite", reason="requires native PostgreSQL concurrent transactions")
def test_native_concurrent_provider_connections(account):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy import select, func
    from sqlalchemy.exc import IntegrityError
    from backend.app.database import SessionLocal
    from backend.app.models import UserProviderCredential
    _, _, user, _ = account
    uid = uuid.UUID(user["id"])
    barrier = Barrier(2)
    def attempt(_):
        with SessionLocal() as db:
            db.add(UserProviderCredential(user_id=uid, provider_id="race-fixture", ciphertext="fixture", last4=""))
            barrier.wait(timeout=10)
            try:
                db.commit()
                return "committed"
            except IntegrityError:
                db.rollback()
                return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == ["committed", "conflict"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(UserProviderCredential).where(
            UserProviderCredential.user_id == uid, UserProviderCredential.provider_id == "race-fixture")) == 1


def test_two_accounts_same_project_name_ownership_files_and_preview(account):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client, data, user, token = account
    first = client.post("/api/projects", json={"project_name": "test", "source_type": "blank"})
    assert first.status_code == 201, first.text
    workspace = first.json()["workspace"]
    assert workspace["files_available"] is True
    stranger = TestClient(app, base_url="https://testserver")
    try:
        from backend.app.database import SessionLocal
        from backend.app.models import User
        from backend.app.security.passwords import hash_password
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            other = User(username="other_"+uuid.uuid4().hex[:12], email=uuid.uuid4().hex+"@example.org",
                         password_hash=hash_password("Other!Pass123"), phone="777111111", postal_code="967",
                         trial_started_at=now, trial_ends_at=now+timedelta(days=30), status="active")
            db.add(other); db.commit(); identity=other.email
        assert stranger.post("/api/auth/login", json={"identity": identity, "password": "Other!Pass123"}).status_code == 200
        second = stranger.post("/api/projects", json={"project_name": "test", "source_type": "blank"})
        assert second.status_code == 201
        assert second.json()["workspace"]["id"] != workspace["id"]
        for suffix in ["", "/files", "/preview/capabilities", "/sessions", "/storage"]:
            assert stranger.get("/api/workspaces/"+workspace["id"]+suffix).status_code == 404
        assert stranger.delete("/api/projects/"+first.json()["project"]["id"]).status_code == 404
        from backend.app.models import WorkspaceSession
        with SessionLocal() as db:
            session=WorkspaceSession(user_id=uuid.UUID(user["id"]), workspace_id=uuid.UUID(workspace["id"]),
                                     opencode_session_id="ses_fixture_only",title="Owned conversation")
            db.add(session);db.commit();sid=str(session.id)
        for suffix in ["", "/questions", "/permissions", "/messages"]:
            assert stranger.get("/api/sessions/"+sid+suffix).status_code == 404
        assert stranger.post("/api/sessions/"+sid+"/questions/foreign",json={"answers":[["yes"]]}).status_code == 404
        assert stranger.post("/api/sessions/"+sid+"/permissions/foreign",json={"reply":"once"}).status_code == 404
        for path in ["../.env", "/etc/passwd", ".env", ".git/config"]:
            assert client.get("/api/workspaces/"+workspace["id"]+"/files/content", params={"path":path}).status_code in {403,404,422}
        assert client.post("/api/projects", json={"project_name":"cross-site"}, headers={"Origin":"https://attacker.invalid"}).status_code == 403
        assert client.get("/.env").status_code == 404
    finally:
        stranger.close()


def test_missing_workspace_files_do_not_delete_database_project(account):
    from sqlalchemy import select
    from backend.app.database import SessionLocal
    from backend.app.models import Workspace
    from backend.app.services import workspaces
    client, _, _, _ = account
    result = client.post("/api/projects", json={"project_name":"missing-files"}).json()
    identifier = result["workspace"]["id"]
    with SessionLocal() as db:
        row = db.scalar(select(Workspace).where(Workspace.id == uuid.UUID(identifier)))
        root = workspaces.root_for(row)
        moved = root.with_name("repo.saved-for-test")
        root.rename(moved)
    missing = client.get("/api/workspaces/"+identifier)
    assert missing.status_code == 200
    assert missing.json()["files_available"] is False
    assert client.get("/api/projects/"+result["project"]["id"]).status_code == 200
    moved.rename(root)
    assert client.get("/api/workspaces/"+identifier).json()["files_available"] is True


def test_encrypted_account_provider_uniqueness_and_owner_delete(account):
    from sqlalchemy import select
    from backend.app.database import SessionLocal
    from backend.app.models import UserProviderCredential
    from backend.app.services import credentials, user_provider_credentials
    _, _, user, _ = account
    uid = uuid.UUID(user["id"])
    plain = '{"type":"api","key":"fake-only-unit-key"}'
    with SessionLocal() as db:
        saved = user_provider_credentials.save_encrypted(db, uid, "example", credentials.encrypt(plain), "-key")
        db.commit()
        assert saved.ciphertext != plain and credentials.decrypt(saved.ciphertext) == plain
        assert user_provider_credentials.find(db, uuid.uuid4(), "example") is None
        assert user_provider_credentials.delete_owned(db, uuid.uuid4(), "example") is False
        assert user_provider_credentials.find(db, uid, "example") is not None
        assert user_provider_credentials.delete_owned(db, uid, "example") is True
        db.commit()


@pytest.mark.skipif(os.getenv("AUDIT_DB_ENGINE") == "pglite",
                   reason="PGlite socket error/rollback protocol is incompatible with psycopg; requires native PostgreSQL")
def test_duplicate_provider_database_constraint(account):
    from sqlalchemy.exc import IntegrityError
    from backend.app.database import SessionLocal
    from backend.app.models import UserProviderCredential
    _, _, user, _ = account
    with SessionLocal() as db:
        for value in ["first", "duplicate"]:
            db.add(UserProviderCredential(user_id=uuid.UUID(user["id"]), provider_id="duplicate-fixture",
                                          ciphertext=value, last4=""))
            if value == "first":db.commit()
            else:
                with pytest.raises(IntegrityError):db.commit()
                db.rollback()


def test_first_payment_renewal_and_duplicate_confirmation(account):
    from sqlalchemy import select
    from backend.app.database import SessionLocal
    from backend.app.models import User, Plan, PaymentOrder, Subscription
    from backend.app.routes.billing import activate_order
    from backend.app.services.entitlements import access_payload
    client, _, profile, _ = account
    uid = uuid.UUID(profile["id"])
    with SessionLocal() as db:
        user=db.get(User, uid)
        plan=Plan(code="audit-"+uuid.uuid4().hex[:12], name="Audit 30 days", price_cents=200, currency="USD", duration_days=30)
        db.add(plan);db.commit()
        def order():
            row=PaymentOrder(user_id=uid, plan_id=plan.id, plan_name=plan.name, method_label="fixture bank",
                             amount_cents=200, currency="USD", duration_days=30)
            db.add(row);db.commit();return row
        first=order();before=datetime.now(timezone.utc)
        activate_order(db,first,None,"verified-fixture-1");db.commit()
        sub=db.scalar(select(Subscription).where(Subscription.user_id==uid))
        assert before+timedelta(days=30) <= sub.current_period_end <= datetime.now(timezone.utc)+timedelta(days=30)

        expiry=sub.current_period_end
        activate_order(db,first,None,"verified-fixture-1");db.commit()
        assert sub.current_period_end == expiry
        second=order();activate_order(db,second,None,"verified-fixture-2");db.commit()
        assert sub.current_period_end == expiry+timedelta(days=30)
        sub.current_period_end=datetime.now(timezone.utc)-timedelta(days=1);db.commit()
        assert access_payload(db,user)["allowed"] is False
        third=order();before=datetime.now(timezone.utc)
        activate_order(db,third,None,"verified-fixture-3");db.commit()
        assert before+timedelta(days=30) <= sub.current_period_end <= datetime.now(timezone.utc)+timedelta(days=30)


@pytest.mark.skipif(os.getenv("AUDIT_RUN_OPENCODE") != "1", reason="requires pinned OpenCode binary")
def test_real_opencode_account_runtime_without_project(account, monkeypatch):
    import json
    from sqlalchemy import select
    from backend.app.database import SessionLocal
    from backend.app.models import Workspace
    from backend.app.services import opencode, providers
    client, _, user, _ = account
    uid=uuid.UUID(user["id"]);other=uuid.uuid4()
    owned_workspaces = []
    try:
        synthetic, service=opencode.for_account(uid)
        assert service.health()["version"] == "1.18.32"
        assert service.request("GET", "/permission") == []
        assert service.request("GET", "/question") == []
        metadata=service.request("GET", "/provider")
        assert isinstance(metadata.get("all"), list)
        # Unknown request IDs must not confirm imaginary actions/questions.
        assert service.request("GET", "/session") == []
        isolated_path=opencode.settings.runtime_root / str(uid) / "account-workdir"
        assert isolated_path.is_dir()
        other_account, other_service=opencode.for_account(other)
        assert other_account.id != synthetic.id
        assert other_service.generation != service.generation
        assert service.request("PUT", "/auth/openai", {"type":"api", "key":"fake-audit-only-never-call-model"}) is True
        auth_path=opencode.settings.runtime_root / str(uid) / str(synthetic.id) / "data/opencode/auth.json"
        assert json.loads(auth_path.read_text())["openai"]["key"] == "fake-audit-only-never-call-model"
        other_auth=opencode.settings.runtime_root / str(other) / str(other_account.id) / "data/opencode/auth.json"
        assert not other_auth.exists() or "openai" not in json.loads(other_auth.read_text())
        assert service.request("DELETE", "/auth/openai") is True
        options=client.get("/api/opencode/connections/openai/options")
        assert options.status_code == 200, options.text
        assert options.json()["auth_methods"]
        catalog=client.get("/api/opencode/catalog/providers")
        assert catalog.status_code == 200, catalog.text
        assert any(row["id"] == "openai" for row in catalog.json())
        # Exercise real Gateway connect/disconnect and OpenCode auth persistence.
        # Only the external model validation call is mocked; keys are fake.
        monkeypatch.setattr(providers, "validate_model", lambda *a, **kw: "fixture-model")
        method = next(i for i, row in enumerate(options.json()["auth_methods"]) if row["type"] in {"api", "key"})
        payload = {"api_key":"fake-fixture-first1234", "model_id":"fixture-model", "method":method}
        assert client.post("/api/opencode/connections/openai/credentials", json=payload).status_code == 200
        assert client.post("/api/opencode/connections/openai/credentials", json=payload).status_code == 409
        # Restart restores the encrypted account key without any project.
        opencode.stop_workspace(synthetic)
        _, service = opencode.for_account(uid)
        assert json.loads(auth_path.read_text())["openai"]["key"] == payload["api_key"]
        assert other_service.request("PUT", "/auth/openai", {"type":"api", "key":"other-fixture-unchanged"}) is True
        other_before = other_auth.read_bytes()
        for name in ["First runtime", "Stopped runtime"]:
            created = client.post("/api/projects", json={"project_name":name})
            assert created.status_code == 201, created.text
            with SessionLocal() as db:
                owned_workspaces.append(db.scalar(select(Workspace).where(Workspace.id == uuid.UUID(created.json()["workspace"]["id"]))))
            opencode.for_workspace(owned_workspaces[-1])
        opencode.stop_workspace(owned_workspaces[1])
        assert client.delete("/api/opencode/connections/openai").status_code == 204
        paths = [auth_path] + [opencode.settings.runtime_root / str(uid) / str(w.id) / "data/opencode/auth.json" for w in owned_workspaces]
        assert all("openai" not in json.loads(path.read_text()) for path in paths)
        assert other_auth.read_bytes() == other_before
        # A stopped runtime cannot revive the revoked key on restart.
        opencode.for_workspace(owned_workspaces[1])
        assert "openai" not in json.loads(paths[2].read_text())
        payload["api_key"] = "fake-fixture-reconnect5678"
        result = client.post("/api/opencode/connections/openai/credentials", json=payload)
        assert result.status_code == 200, result.text
        assert result.json()["deferred_workspace_count"] == 0
        assert all(json.loads(path.read_text())["openai"]["key"] == payload["api_key"] for path in paths[1:])
        assert other_auth.read_bytes() == other_before
        assert client.delete("/api/opencode/connections/openai").status_code == 204
        assert client.get("/api/opencode/connections").json() == []
    finally:
        for workspace in owned_workspaces:
            opencode.stop_workspace(workspace)
        opencode.stop_workspace(opencode.account_workspace(uid))
        opencode.stop_workspace(opencode.account_workspace(other))
