"""Read-only admin schema diagnosis + real existing migration compatibility.
Local isolated SQLite evidence, not remote TEST PostgreSQL verification.
"""
import importlib.util
from pathlib import Path
from unittest.mock import Mock
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import Session
from alembic.migration import MigrationContext
from alembic.operations import Operations
from backend.tests.test_native_control_plane import boundary, authenticated
from backend.app.routes import admin
from backend.app.services import github

def test_existing_github_migrations_create_required_structure_without_new_migration():
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        operations=Operations(MigrationContext.configure(connection))
        versions=Path(__file__).parents[1]/'alembic/versions'
        for pattern in ('0001_*','0002_*','0003_*','0004_*','0005_*'):
            path=next(versions.glob(pattern+'.py'))
            spec=importlib.util.spec_from_file_location(path.stem,path)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            module.op=operations;module.upgrade()
        with Session(bind=connection) as db:
            result=github.schema_status(db)
            assert result['checked'] and result['ready'],result
        assert 'user_token' in {c['name'] for c in inspect(connection).get_columns('github_connections')}
    engine.dispose()

def test_missing_schema_returns_precise_non_secret_diagnostics():
    engine=create_engine('sqlite://')
    with Session(engine) as db:
        result=github.schema_status(db)
        assert result['checked'] and not result['ready']
        assert set(result['missing'])=={'github_connections','github_auth_states','projects'}
    engine.dispose()

def test_admin_http_diagnostics_enforce_role_and_detect_missing_table(boundary):
    client,(owner,customer),_,engine,config=boundary
    client.app.include_router(admin.router)
    with Session(engine) as db:
        from backend.app.models import User
        db.get(User,owner.id).role='admin';db.commit()
    assert authenticated(client,'/api/admin/github-configuration',customer,config).status_code==403
    response=authenticated(client,'/api/admin/github-configuration',owner,config)
    assert response.status_code==200,response.text
    result=response.json()
    assert result['database']['missing']==['github_auth_states']
    assert result['source']=='protected_server_environment' and result['editable'] is True
    assert all(isinstance(value,bool) for value in result['secrets'].values())
    assert 'user_token' not in result and 'private_key' not in result
