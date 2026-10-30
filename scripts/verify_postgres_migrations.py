"""Opt-in integration check against an EMPTY disposable loopback PostgreSQL DB.

Run from any directory, with DATABASE_URL and MIGRATION_QA_DISPOSABLE=1:
  python scripts/verify_postgres_migrations.py fresh
  python scripts/verify_postgres_migrations.py existing
  python scripts/verify_postgres_migrations.py duplicates
Each invocation needs its own empty database. Never drops or truncates data.
Not a deployment utility; do not run against TEST/production databases.
"""
import os
from pathlib import Path
import subprocess
import sys
import uuid

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = '0025_email_verification_codes'
HEAD = '0030_staged_registration'


def verify(scenario):
    url = sa.engine.make_url(os.environ['DATABASE_URL'])
    if (os.environ.get('MIGRATION_QA_DISPOSABLE') != '1'
            or url.host not in ('127.0.0.1', 'localhost', '::1')
            or url.get_backend_name() != 'postgresql'):
        raise RuntimeError('Requires explicit disposable loopback PostgreSQL QA database')
    engine = sa.create_engine(url, poolclass=sa.pool.NullPool)
    if sa.inspect(engine).get_table_names():
        raise RuntimeError('QA database must be empty; existing tables were preserved')

    def migrate(revision='head', success=True):
        result = subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', revision],
                                cwd=ROOT / 'backend', capture_output=True, text=True)
        if success and result.returncode:
            raise AssertionError(result.stderr)
        if not success:
            assert result.returncode != 0
        return result.stderr

    def scalar(sql):
        with engine.connect() as conn:
            return conn.execute(sa.text(sql)).scalar_one()

    def width():
        return scalar("SELECT data_type FROM information_schema.columns "
                      "WHERE table_schema=current_schema() AND table_name='alembic_version' "
                      "AND column_name='version_num'")

    if scenario == 'fresh':
        migrate()
    else:
        migrate(PREVIOUS)
        assert scalar("SELECT character_maximum_length FROM information_schema.columns "
                      "WHERE table_schema=current_schema() AND table_name='alembic_version' "
                      "AND column_name='version_num'") == 32
        with engine.begin() as conn:
            for index in range(2 if scenario == 'duplicates' else 1):
                conn.execute(sa.text("""INSERT INTO users
                    (id,username,email,password_hash,phone,postal_code,country_id,trial_started_at,trial_ends_at)
                    VALUES (:id,:username,:email,'synthetic-hash',:phone,'+967',1,now(),now()+interval '7 days')"""),
                    {'id': uuid.uuid4(), 'username': f'qa_user_{index}',
                     'email': f'qa{index}@example.invalid', 'phone': '777123456'})
            conn.execute(sa.text('CREATE TABLE qa_preserve_marker (value text PRIMARY KEY)'))
            conn.execute(sa.text("INSERT INTO qa_preserve_marker VALUES ('untouched')"))
        if scenario == 'duplicates':
            error = migrate(success=False)
            assert 'duplicates require owner reconciliation' in error
            assert scalar('SELECT version_num FROM alembic_version') == PREVIOUS
            assert width() == 'character varying'
            assert scalar('SELECT count(*) FROM users') == 2
            assert 'username_identity' not in {c['name'] for c in sa.inspect(engine).get_columns('users')}
            assert scalar('SELECT value FROM qa_preserve_marker') == 'untouched'
            print('PASS: duplicate identities refused; transaction and account data preserved')
            return
        migrate()
        with engine.connect() as conn:
            row = conn.execute(sa.text('SELECT username,email,password_hash,phone,phone_identity FROM users')).one()
            assert tuple(row) == ('qa_user_0','qa0@example.invalid','synthetic-hash','777123456','+967777123456')
        assert scalar('SELECT value FROM qa_preserve_marker') == 'untouched'
    assert scalar('SELECT version_num FROM alembic_version') == HEAD
    assert width() == 'text'
    assert sa.inspect(engine).get_pk_constraint('alembic_version')['constrained_columns'] == ['version_num']
    migrate()  # Second deployment must not rerun data migrations.
    assert scalar('SELECT version_num FROM alembic_version') == HEAD
    print(f'PASS: {scenario} database reaches {HEAD}; version key preserved; repeat upgrade succeeds')
    engine.dispose()


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('fresh', 'existing', 'duplicates'):
        raise SystemExit('Choose fresh, existing, or duplicates; use a new disposable DB each time')
    verify(sys.argv[1])
