"""New retention regression; fake credentials, real disposable SQL/OpenCode."""
import os, uuid
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select
from backend.tests.test_disposable_database import account
pytestmark=pytest.mark.skipif(os.getenv('AUDIT_DISPOSABLE_DB')!='1' or os.getenv('AUDIT_RUN_OPENCODE')!='1',reason='isolated SQL/OpenCode required')


def test_archive_stops_project_independent_runtime_and_preserves_other_user(account,monkeypatch):
    from backend.app.database import SessionLocal
    from backend.app.models import User, UserProviderCredential, AuthSession, EmailVerification
    from backend.app.services import opencode, customer_lifecycle as lifecycle, credentials
    from backend.app.config import settings
    client,_,user,_=account
    uid=uuid.UUID(user['id']);now=datetime.now(timezone.utc)
    monkeypatch.setattr(lifecycle,'_policy_started',now-timedelta(days=300))
    with SessionLocal() as db:
        target=db.get(User,uid);end=now-timedelta(days=91)
        target.trial_started_at=end-timedelta(days=30);target.trial_ends_at=end
        other=User(username='retention_'+uuid.uuid4().hex[:12],email=uuid.uuid4().hex+'@example.org',password_hash='fixture',phone='',postal_code='',trial_started_at=now,trial_ends_at=now+timedelta(days=30))
        db.add(other);db.flush();otherid=other.id
        db.add_all([UserProviderCredential(user_id=uid,provider_id='fixture',ciphertext=credentials.encrypt('target-fixture'),last4=''),UserProviderCredential(user_id=otherid,provider_id='fixture',ciphertext=credentials.encrypt('other-fixture'),last4='')]);db.commit()
        _,runtime=opencode.for_account(uid,db=db)
        _,other_runtime=opencode.for_account(otherid,db=db)
        trial=target.trial_ends_at
        before=db.scalar(select(UserProviderCredential.ciphertext).where(UserProviderCredential.user_id==otherid))
    otherpath=settings.runtime_root/str(otherid)/str(opencode.account_workspace(otherid).id)/'data/opencode/auth.json';otherfile=otherpath.read_bytes()
    try:
        assert lifecycle.archive_due(now=now)==1
        assert str(opencode.account_workspace(uid).id) not in opencode._runtimes
        assert not (settings.runtime_root/str(uid)).exists()
        assert otherpath.read_bytes()==otherfile
        with SessionLocal() as db:
            target=db.get(User,uid)
            assert target.status=='archived' and target.password_hash=='!archived!' and target.trial_ends_at==trial
            assert db.scalar(select(UserProviderCredential.id).where(UserProviderCredential.user_id==uid)) is None
            assert db.scalar(select(AuthSession.id).where(AuthSession.user_id==uid)) is None
            assert db.scalar(select(EmailVerification.id).where(EmailVerification.user_id==uid)) is None
            assert db.get(User,otherid).status=='active'
            assert db.scalar(select(UserProviderCredential.ciphertext).where(UserProviderCredential.user_id==otherid))==before
    finally:
        opencode.stop_workspace(opencode.account_workspace(uid));opencode.stop_workspace(opencode.account_workspace(otherid))
