"""Normalized duplicate rejection via HTTP, unique DB keys and data-preserving migration."""
import importlib.util
from types import SimpleNamespace
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from alembic.operations import Operations
from alembic.migration import MigrationContext
import pytest
from backend.tests.test_email_code_signup import signup
from backend.tests.test_admin_mailbox_delivery import mail_acceptance, acceptance, boundary
from backend.app import models
from backend.app.security.identities import account_keys


def register(f,username,email,phone):
    return f[0].post('/api/auth/register',json={'username':username,'email':email,'phone':phone,'postal_code':'+967','password':'Synthetic8!Password'})


def test_email_username_and_phone_are_unique_even_with_case_or_format_variants(signup):
    f,_=signup
    first=register(f,'unique_user','first-fixture@example.org','+967777123456');assert first.status_code==201,first.text
    for username,email,phone in [('other_user','FIRST-FIXTURE@example.org','+967777123457'),('UNIQUE_USER','second-fixture@example.org','+967777123458'),('third_user','third-fixture@example.org','00967 777-123-456'),('fourth_user','fourth-fixture@example.org','٧٧٧١٢٣٤٥٦')]:
        response=register(f,username,email,phone);assert response.status_code==409,response.text
    with Session(f[2]) as db:
        user=db.get(models.User,__import__('uuid').UUID(first.json()['id']))
        assert user.phone=='+967777123456'
        assert user.phone_identity=='+967777123456'
        db.add(models.User(username='UNIQUE_USER',email='other-db-fixture@example.org',phone='+967777123499',password_hash='synthetic',postal_code='+967',trial_started_at=user.trial_started_at,trial_ends_at=user.trial_ends_at))
        with pytest.raises(IntegrityError):db.commit()
        db.rollback();assert db.scalar(select(models.User).where(models.User.id==user.id)).status=='pending_email'


def migration():
    spec=importlib.util.spec_from_file_location('identity_migration','backend/alembic/versions/0026_unique_registration_identities.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def legacy(connection,rows):
    connection.execute(text('CREATE TABLE users (id TEXT PRIMARY KEY,username TEXT,email TEXT,phone TEXT,postal_code TEXT)'))
    for index,(username,email,phone,postal) in enumerate(rows):connection.execute(text('INSERT INTO users VALUES(:id,:u,:e,:p,:c)'),{'id':str(index),'u':username,'e':email,'p':phone,'c':postal})


def test_migration_stops_on_existing_duplicates_before_schema_or_account_mutation():
    engine=create_engine('sqlite://');module=migration()
    with engine.begin() as conn:
        rows=[('one_user','one@example.org','+967777123456','+967'),('two_user','two@example.org','00967 777123456','+967')];legacy(conn,rows)
        before=list(conn.execute(text('SELECT * FROM users')))
        with Operations.context(MigrationContext.configure(conn)):
            with pytest.raises(RuntimeError,match='phone=1'):module.upgrade()
        assert list(conn.execute(text('SELECT * FROM users')))==before
        assert 'phone_identity' not in {row[1] for row in conn.execute(text('PRAGMA table_info(users)'))}
    engine.dispose()


def test_migration_backfills_keys_without_rewriting_legacy_values():
    engine=create_engine('sqlite://');module=migration()
    with engine.begin() as conn:
        legacy(conn,[('One_User','ONE@example.org','777123456','+967'),('two_user','two@example.org','legacy-placeholder','00000')])
        with Operations.context(MigrationContext.configure(conn)):module.upgrade()
        row=conn.execute(text("SELECT username,email,phone,username_identity,email_identity,phone_identity FROM users WHERE id='0'")).one()
        assert tuple(row)==('One_User','ONE@example.org','777123456','one_user','one@example.org','+967777123456')
        assert conn.execute(text("SELECT phone_identity FROM users WHERE id='1'")).scalar_one() is None
        assert module.keys(SimpleNamespace(username='One_User',email='ONE@example.org',phone='777123456',postal_code='+967'))==account_keys('One_User','ONE@example.org','777123456','+967')
    engine.dispose()
