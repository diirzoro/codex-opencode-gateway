"""Archive filesystem/SQL failure compensation on a disposable database only."""
import os,uuid
from datetime import datetime,timedelta,timezone
import pytest
from sqlalchemy import select
from backend.tests.test_disposable_database import account
pytestmark=pytest.mark.skipif(os.getenv('AUDIT_DISPOSABLE_DB')!='1',reason='disposable database required')


def test_commit_failure_preserves_runtime_and_retry_archives(account,monkeypatch):
    from backend.app.database import SessionLocal
    from backend.app.models import User,UserProviderCredential,AuthSession
    from backend.app.config import settings
    from backend.app.services import customer_lifecycle as lifecycle,credentials,opencode
    client,_,owner,_=account;uid=uuid.UUID(owner['id']);now=datetime.now(timezone.utc)
    monkeypatch.setattr(lifecycle,'_policy_started',now-timedelta(days=300))
    runtime=settings.runtime_root/str(uid);runtime.mkdir(parents=True)
    (runtime/'history.fixture').write_text('preserved-runtime')
    with SessionLocal() as db:
        user=db.get(User,uid);user.trial_ends_at=now-timedelta(days=100)
        db.add(UserProviderCredential(user_id=uid,provider_id='archive-fixture',ciphertext=credentials.encrypt('private-fixture'),last4=''));db.commit()
    original=SessionLocal.class_.commit
    def fail_archive_commit(db):
        if any(isinstance(row,User) and row.id==uid and row.status=='archived' for row in db.dirty):
            raise RuntimeError('Injected commit failure')
        return original(db)
    monkeypatch.setattr(SessionLocal.class_,'commit',fail_archive_commit)
    assert lifecycle.archive_due(now=now)==0
    with SessionLocal() as db:
        assert db.get(User,uid).status=='active'
        assert db.scalar(select(UserProviderCredential.id).where(UserProviderCredential.user_id==uid))
        assert db.scalar(select(AuthSession.id).where(AuthSession.user_id==uid))
    assert (runtime/'history.fixture').read_text()=='preserved-runtime'
    monkeypatch.setattr(SessionLocal.class_,'commit',original)
    assert lifecycle.archive_due(now=now)==1
    assert not runtime.exists()
    with SessionLocal() as db:assert db.get(User,uid).status=='archived'


@pytest.mark.parametrize('committed',[False,True])
def test_interrupted_archive_recovers_from_committed_account_status(account,monkeypatch,committed):
    from backend.app.database import SessionLocal
    from backend.app.models import User
    from backend.app.config import settings
    from backend.app.services import customer_lifecycle as lifecycle
    from backend.app.services.archive_storage import StagedRuntime
    _,_,owner,_=account;uid=uuid.UUID(owner['id']);now=datetime.now(timezone.utc)
    # Keep the account in grace; recovery must run even when no archive is due.
    monkeypatch.setattr(lifecycle,'_policy_started',now)
    runtime=settings.runtime_root/str(uid);runtime.mkdir(parents=True)
    (runtime/'history.fixture').write_text('recoverable')
    storage=StagedRuntime(uid);storage.stage();assert not runtime.exists()
    if committed:
        with SessionLocal() as db:
            db.get(User,uid).status='archived';db.commit()
    assert lifecycle.archive_due(now=now)==0
    assert not storage.staged.exists()
    if committed:assert not runtime.exists()
    else:assert (runtime/'history.fixture').read_text()=='recoverable'


def test_archive_erasure_failure_is_retried_without_reactivation(account,monkeypatch):
    from backend.app.database import SessionLocal
    from backend.app.models import User
    from backend.app.config import settings
    from backend.app.services import customer_lifecycle as lifecycle
    from backend.app.services.archive_storage import StagedRuntime
    _,_,owner,_=account;uid=uuid.UUID(owner['id']);now=datetime.now(timezone.utc)
    monkeypatch.setattr(lifecycle,'_policy_started',now-timedelta(days=300))
    runtime=settings.runtime_root/str(uid);runtime.mkdir(parents=True);(runtime/'history.fixture').write_text('fixture')
    with SessionLocal() as db:db.get(User,uid).trial_ends_at=now-timedelta(days=100);db.commit()
    erase=StagedRuntime.erase
    monkeypatch.setattr(StagedRuntime,'erase',lambda self:(_ for _ in ()).throw(OSError('injected erasure failure')))
    assert lifecycle.archive_due(now=now)==1
    storage=StagedRuntime(uid);assert storage.staged.exists() and not runtime.exists()
    with SessionLocal() as db:assert db.get(User,uid).status=='archived'
    monkeypatch.setattr(StagedRuntime,'erase',erase)
    assert lifecycle.archive_due(now=now)==0
    assert not storage.staged.exists() and not runtime.exists()


def test_lost_commit_acknowledgement_never_restores_archived_secrets(account,monkeypatch):
    from backend.app.database import SessionLocal
    from backend.app.models import User
    from backend.app.config import settings
    from backend.app.services import customer_lifecycle as lifecycle
    from backend.app.services.archive_storage import StagedRuntime
    _,_,owner,_=account;uid=uuid.UUID(owner['id']);now=datetime.now(timezone.utc)
    monkeypatch.setattr(lifecycle,'_policy_started',now-timedelta(days=300))
    runtime=settings.runtime_root/str(uid);runtime.mkdir(parents=True);(runtime/'private.fixture').write_text('private fixture')
    with SessionLocal() as db:db.get(User,uid).trial_ends_at=now-timedelta(days=100);db.commit()
    commit=SessionLocal.class_.commit
    def ambiguous(db):
        archive=any(isinstance(row,User) and row.id==uid and row.status=='archived' for row in db.dirty)
        commit(db)
        if archive:raise OSError('Injected lost commit acknowledgement')
    monkeypatch.setattr(SessionLocal.class_,'commit',ambiguous)
    assert lifecycle.archive_due(now=now)==1
    with SessionLocal() as db:assert db.get(User,uid).status=='archived'
    assert not runtime.exists() and not StagedRuntime(uid).staged.exists()
