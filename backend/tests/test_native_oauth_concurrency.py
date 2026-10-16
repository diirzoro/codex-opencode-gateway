"""Executable acceptance gate: native disposable PostgreSQL ONLY, never PGlite."""
import os,uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from backend.tests.test_disposable_database import account
pytestmark=pytest.mark.skipif(os.getenv('AUDIT_DISPOSABLE_DB')!='1' or os.getenv('AUDIT_DB_ENGINE') not in {'native','postgresql'},reason='explicit disposable native PostgreSQL required')


def test_native_oauth_compare_and_swap_allows_only_one_rotation(account):
    from backend.app.database import SessionLocal
    from backend.app.models import UserProviderCredential
    from backend.app.services import credentials,user_provider_credentials as store
    from sqlalchemy import select
    _,_,owner,_=account;uid=uuid.UUID(owner['id']);old=credentials.encrypt('old-fixture')
    with SessionLocal() as db:
        row=UserProviderCredential(user_id=uid,provider_id='native-cas',ciphertext=old,last4='');db.add(row);db.commit();identifier=row.id
    barrier=Barrier(2)
    def rotate(value):
        with SessionLocal() as db:
            # Bound a failed lock instead of leaving test workers hanging.
            from sqlalchemy import text
            db.execute(text("SET LOCAL lock_timeout = '5s'"))
            barrier.wait(timeout=5)
            accepted=store.replace_encrypted_if_current(db,uid,'native-cas',old,credentials.encrypt(value),expected_id=identifier)
            db.commit();return accepted
    with ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(rotate,['first-fixture','second-fixture']))==[False,True]
    with SessionLocal() as db:
        saved=db.scalar(select(UserProviderCredential).where(UserProviderCredential.id==identifier))
        assert credentials.decrypt(saved.ciphertext) in {'first-fixture','second-fixture'}
        assert not store.replace_encrypted_if_current(db,uid,'native-cas',old,credentials.encrypt('stale-fixture'),expected_id=identifier)
        db.rollback()
