"""Private registry/manual email/admin toggle regressions. No live credentials."""
import os,json,io,importlib.util
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://fixture:fixture@127.0.0.1/fixture')
from datetime import datetime,timedelta,timezone
import pytest
from sqlalchemy import select,create_engine,text,inspect
from sqlalchemy.orm import Session,sessionmaker
from alembic.migration import MigrationContext
from alembic.operations import Operations
from backend.app import models,database
from backend.app.services import github,email_service_policies
from backend.app.routes import admin
from backend.tests.test_github_reconnect_security import flow
from backend.tests.test_native_control_plane import boundary
from backend.tests.test_github_email_ownership import send,verify,raw_confirm,age_rate


def test_manual_email_mismatch_does_not_send_or_hint_and_is_rate_limited(flow):
    f=flow;a=f.owners[0];f.callback(f.start())
    reply=send(f,a,'wrong@example.com');assert reply.status_code==400
    assert 'github101@example.com' not in reply.text and '***' not in reply.text and not f.sent
    assert send(f,a,'another@example.com').status_code==429
    assert raw_confirm(f,a).status_code==403
    age_rate(f)
    good=send(f,a,'github101@example.com');assert good.status_code==200
    assert 'email' not in good.json() and 'masked_email' not in good.json()
    assert 'masked_email' not in f.pending()['email_verification']
    assert verify(f,a,f.sent[-1]['code']).status_code==200
    assert raw_confirm(f,a).status_code==200


def test_registry_created_only_after_complete_email_and_otp_proof(flow):
    f=flow;a=f.owners[0];f.callback(f.start())
    with Session(f.engine) as db:assert db.get(models.GithubIdentityRegistry,101) is None
    assert raw_confirm(f,a).status_code==403
    assert send(f,a,'github101@example.com').status_code==200
    assert raw_confirm(f,a).status_code==403
    assert verify(f,a,f.sent[-1]['code']).status_code==200
    assert raw_confirm(f,a).status_code==200
    with Session(f.engine) as db:
        row=db.get(models.GithubIdentityRegistry,101)
        assert row.primary_email_hmac==github._primary_email_hmac(101,'github101@example.com')
        assert row.verification_status=='verified'
        assert len(row.primary_email_hmac)==64 and row.primary_email_hmac!=github._primary_email_hmac(102,'github101@example.com')
        assert not {'email','token','code','active_gateway_user_id'}.intersection(row.__table__.columns.keys())
        assert 'github101@example.com' not in f.request('/api/github/status').text


def test_disconnect_keeps_only_private_registry_and_reconnect_updates_changed_email(flow,monkeypatch):
    f=flow;a=f.owners[0];f.callback(f.start());first=f.confirm().json()['connection_id']
    with Session(f.engine) as db:
        row=db.get(models.GithubIdentityRegistry,101);original_first=row.first_verified_at;old_hmac=row.primary_email_hmac
    assert f.request('/api/github/disconnect',method='POST').status_code==200
    with Session(f.engine) as db:
        assert db.get(models.GithubIdentityRegistry,101) is not None
        assert not list(db.scalars(select(models.GithubConnection)))
        assert not list(db.scalars(select(models.GithubAuthState)))
    f.callback(f.start());age_rate(f)
    original=github._api
    monkeypatch.setattr(github,'_api',lambda method,path,**kw:[{'email':'new-primary@example.com','verified':True,'primary':True}] if path=='/user/emails' else original(method,path,**kw))
    assert send(f,a,'new-primary@example.com').status_code==200
    assert verify(f,a,f.sent[-1]['code']).status_code==200
    result=raw_confirm(f,a);assert result.status_code==200,result.text
    assert result.json()['connection_id']!=first
    with Session(f.engine) as db:
        row=db.get(models.GithubIdentityRegistry,101)
        assert row.first_verified_at==original_first and row.primary_email_hmac!=old_hmac
        assert row.primary_email_hmac==github._primary_email_hmac(101,'new-primary@example.com')
        assert db.scalar(select(models.AccountAudit).where(models.AccountAudit.action=='github.auth.email_changed:101'))


def test_registry_never_bypasses_otp_or_active_owner_and_conflict_does_not_revoke_owner(flow):
    f=flow;a,b=f.owners;f.callback(f.start(a),a);assert f.confirm(a).status_code==200
    old_revoked=list(f.revoked)
    callback=f.callback(f.start(b),b,'A')
    assert callback.headers['location'].endswith('account-conflict') and f.pending(b) is None
    assert f.revoked==old_revoked
    assert send(f,b,'github101@example.com').status_code==409
    assert f.request('/api/github/status',a).json()['connected']
    assert f.request('/api/github/disconnect',a,'POST').status_code==200
    f.callback(f.start(b),b,'A')
    assert raw_confirm(f,b).status_code==403  # Registry existence is not authority.


def test_missing_registry_blocks_new_links_without_migration_or_data_changes(flow):
    f=flow
    models.GithubIdentityRegistry.__table__.drop(f.engine)
    response=f.request('/api/github/connect',method='POST')
    assert response.status_code==503 and '0029' in response.text
    assert not f.vendor
    with Session(f.engine) as db:assert db.get(models.User,f.owners[0].id) is not None


def test_private_registry_retention_keeps_active_and_recent_records_only(flow,monkeypatch):
    f=flow;a=f.owners[0];f.callback(f.start());f.confirm()
    old=datetime.now(timezone.utc)-timedelta(days=91)
    with Session(f.engine) as db:
        live=db.get(models.GithubIdentityRegistry,101);live.retain_until=old
        db.add(models.GithubIdentityRegistry(github_user_id=999,primary_email_hmac='a'*64,first_verified_at=old,last_verified_at=old,retain_until=old))
        db.add(models.GithubIdentityRegistry(github_user_id=998,primary_email_hmac='b'*64))
        db.add(models.AccountAudit(subject_id=a.id,action='github.auth.connected:999',created_at=old))
        db.add(models.AccountAudit(subject_id=a.id,action='synthetic.other',created_at=old));db.commit()
    monkeypatch.setattr(database,'SessionLocal',sessionmaker(bind=f.engine));github.expire_pending_authorizations()
    with Session(f.engine) as db:
        assert db.get(models.GithubIdentityRegistry,101) and db.get(models.GithubIdentityRegistry,998)
        assert db.get(models.GithubIdentityRegistry,999) is None
        assert not db.scalar(select(models.AccountAudit).where(models.AccountAudit.action=='github.auth.connected:999'))
        assert db.scalar(select(models.AccountAudit).where(models.AccountAudit.action=='synthetic.other'))


def test_admin_service_default_persistence_permissions_and_fail_closed(flow,monkeypatch):
    from backend.tests.test_email_notifications import prepare
    from backend.app.services import admin_email_config
    f=flow;a,b=f.owners;prepare(f.engine,monkeypatch)
    monkeypatch.setattr(admin_email_config,'read',lambda db:None)
    monkeypatch.setattr(admin_email_config,'schema_ready',lambda db:True)
    f.client.app.include_router(admin.router)
    with Session(f.engine) as db:db.get(models.User,a.id).role='admin';db.commit()
    result=f.request('/api/admin/service-integrations').json()
    service=next(row for row in result['services'] if row['id']=='github_connection_verification')
    assert service['enabled'] and service['available'] and service['editable']
    assert len(result['services'])==21  # Existing20 rows remain; this is supported service18.
    path='/api/admin/service-integrations/services/github_connection_verification'
    assert f.request(path,b,'PUT',{'enabled':False}).status_code==403
    f.callback(f.start());assert send(f,a).status_code==200
    assert verify(f,a,f.sent[-1]['code']).status_code==200
    assert f.request(path,a,'PUT',{'enabled':False}).status_code==200
    assert f.request('/api/github/connect',a,'POST').status_code==503
    assert raw_confirm(f,a).status_code==503
    assert not next(row for row in f.request('/api/admin/service-integrations').json()['services'] if row['id']=='github_connection_verification')['enabled']
    assert f.request(path,a,'PUT',{'enabled':True}).status_code==200
    assert raw_confirm(f,a).status_code==200


def test_additive_migration_creates_only_registry_and_refuses_destructive_downgrade():
    spec=importlib.util.spec_from_file_location('registry_migration','backend/alembic/versions/0029_github_identity_registry.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE preserve_me(id INTEGER PRIMARY KEY)'))
        connection.execute(text('INSERT INTO preserve_me VALUES(1)'))
        with Operations.context(MigrationContext.configure(connection)):migration.upgrade()
        assert connection.execute(text('SELECT id FROM preserve_me')).scalar_one()==1
        assert 'primary_email_hmac' in {c['name'] for c in inspect(connection).get_columns('github_identity_registry')}
    output=io.StringIO()
    with Operations.context(MigrationContext.configure(dialect_name='postgresql',opts={'as_sql':True,'output_buffer':output})):migration.upgrade()
    assert 'CREATE TABLE github_identity_registry' in output.getvalue() and 'BIGSERIAL' not in output.getvalue()
    with pytest.raises(RuntimeError):migration.downgrade()


def test_legacy_active_identity_is_resolved_before_new_installation_can_bypass_ownership(flow):
    f=flow;a,b=f.owners;f.callback(f.start(a),a);f.confirm(a)
    with Session(f.engine) as db:
        row=db.scalar(select(models.GithubConnection).where(models.GithubConnection.user_id==a.id));row.github_user_id=None;db.commit()
    callback=f.callback(f.start(b),b,'A')
    assert callback.headers['location'].endswith('account-conflict') and f.pending(b) is None
    with Session(f.engine) as db:
        assert db.scalar(select(models.GithubConnection).where(models.GithubConnection.user_id==a.id)).github_user_id==101
    assert f.request('/api/github/status',a).json()['connected']
