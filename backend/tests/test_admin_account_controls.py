"""Real HTTP/ORM with synthetic accounts; never operate on TEST user rows."""
from unittest.mock import Mock
from sqlalchemy.orm import Session
from sqlalchemy import select
from backend.tests.test_native_control_plane import boundary,authenticated
from backend.app import models
from backend.app.routes import admin


def setup(boundary,monkeypatch):
    client,(actor,target),calls,engine,config=boundary
    client.app.include_router(admin.router)
    for model in (models.Plan,models.Country,models.Region,models.City,models.PasswordReset,models.EmailVerification,models.GithubAuthState):model.__table__.create(engine,checkfirst=True)
    with Session(engine) as db:
        user=db.get(models.User,actor.id);user.role='admin';db.commit()
    monkeypatch.setattr(admin.opencode,'stop_workspace',Mock())
    return client,actor,target,engine,config


def test_admin_updates_real_profile_and_preserves_other_users(boundary,monkeypatch):
    client,actor,target,engine,config=setup(boundary,monkeypatch)
    result=authenticated(client,f'/api/admin/users/{target.id}',actor,config,'PATCH',{'username':'qa_updated','email':'qa_updated@example.org','phone':'+967770123456','postal_code':'+967','preferred_language':'en','preferred_theme':'dark'})
    assert result.status_code==200,result.text
    assert result.json()['username']=='qa_updated'
    with Session(engine) as db:
        user=db.get(models.User,target.id)
        assert user.email=='qa_updated@example.org' and user.phone=='+967770123456'
        assert db.get(models.User,actor.id).username=='fixture-a'
    duplicate=authenticated(client,f'/api/admin/users/{target.id}',actor,config,'PATCH',{'username':'fixture-a'})
    assert duplicate.status_code==409,duplicate.text
    invalid=authenticated(client,f'/api/admin/users/{target.id}',actor,config,'PATCH',{'email':None})
    assert invalid.status_code==422


def test_archive_revokes_sessions_and_preserves_projects_and_files(boundary,monkeypatch):
    client,actor,target,engine,config=setup(boundary,monkeypatch)
    assert authenticated(client,f'/api/admin/users/{target.id}',target,config,'DELETE').status_code==403
    assert authenticated(client,f'/api/admin/users/{actor.id}',actor,config,'DELETE').status_code==403
    response=authenticated(client,f'/api/admin/users/{target.id}',actor,config,'DELETE')
    assert response.status_code==200,response.text
    assert response.json()['data_preserved'] is True
    with Session(engine) as db:
        assert db.get(models.User,target.id).status=='archived'
        assert all(row.revoked_at is not None for row in db.scalars(select(models.AuthSession).where(models.AuthSession.user_id==target.id)))
        assert db.get(models.Project,target.project) is not None
        assert db.get(models.WorkspaceSession,target.session) is not None
        assert target.root.joinpath('marker.txt').read_text()=='synthetic-marker-b'
    assert authenticated(client,'/api/profile',target,config).status_code in (401,403,404)
    assert authenticated(client,f'/api/admin/users/{target.id}',actor,config,'DELETE').status_code==200


def test_archived_customer_can_release_identity_without_erasing_projects_or_history(boundary,monkeypatch):
    from backend.app.security.sessions import reactivation_eligible
    from sqlalchemy.exc import IntegrityError
    client,actor,target,engine,config=setup(boundary,monkeypatch)
    with Session(engine) as db:
        original=db.get(models.User,target.id)
        name,email,phone=original.username,original.email,original.phone
    assert authenticated(client,f'/api/admin/users/{target.id}',actor,config,'DELETE').status_code==200
    invalid=authenticated(client,f'/api/admin/users/{target.id}/release-identifiers',actor,config,'POST',{'confirm_username':'wrong_name'})
    assert invalid.status_code==400
    released=authenticated(client,f'/api/admin/users/{target.id}/release-identifiers',actor,config,'POST',{'confirm_username':name})
    assert released.status_code==200,released.text
    assert released.json()['account_reactivation_disabled'] is True
    assert released.json()['permanent_account_deletion'] is False
    with Session(engine) as db:
        old=db.get(models.User,target.id)
        assert old.status=='identity_released'
        assert old.username!=name and old.email!=email and old.phone_identity is None
        assert old.password_hash=='!archived!' and not reactivation_eligible(old)
        assert db.get(models.Project,target.project) is not None
        assert db.get(models.WorkspaceSession,target.session) is not None
        assert target.root.joinpath('marker.txt').read_text()=='synthetic-marker-b'
        assert all(r.revoked_at is not None for r in db.scalars(select(models.AuthSession).where(models.AuthSession.user_id==target.id)))
        # The same name/email/phone now belong to a genuinely NEW owner id.
        from datetime import datetime,timedelta,timezone
        import uuid
        now=datetime.now(timezone.utc)
        new=models.User(id=uuid.uuid4(),username=name,email=email,phone=phone,
            password_hash='new-fixture-hash',postal_code='00000',
            trial_started_at=now,trial_ends_at=now+timedelta(days=30))
        db.add(new);db.commit()
        assert new.id!=target.id and db.get(models.Project,target.project).user_id==target.id
    assert authenticated(client,f'/api/admin/users/{target.id}',actor,config,'PATCH',{'status':'active'}).status_code==409
    assert authenticated(client,f'/api/admin/users/{target.id}/release-identifiers',actor,config,'POST',{'confirm_username':name}).status_code==409


def test_cannot_release_active_or_privileged_customer_identity(boundary,monkeypatch):
    client,actor,target,engine,config=setup(boundary,monkeypatch)
    active=authenticated(client,f'/api/admin/users/{target.id}/release-identifiers',actor,config,'POST',{'confirm_username':'fixture-b'})
    assert active.status_code==409
    admin_identity=authenticated(client,f'/api/admin/users/{actor.id}/release-identifiers',actor,config,'POST',{'confirm_username':'fixture-a'})
    assert admin_identity.status_code==403
    foreign=authenticated(client,f'/api/admin/users/{target.id}/release-identifiers',target,config,'POST',{'confirm_username':'fixture-b'})
    assert foreign.status_code==403


def test_permanent_user_deletion_physically_removes_empty_archived_row_and_dependencies(boundary,monkeypatch):
    import uuid
    from datetime import datetime,timedelta,timezone
    client,actor,target,engine,config=setup(boundary,monkeypatch)
    now=datetime.now(timezone.utc)
    uid=uuid.uuid4()
    with Session(engine) as db:
        user=models.User(id=uid,username='delete_empty',email='delete-empty@example.org',
            phone='+967777543215',postal_code='+967',password_hash='synthetic-only',
            status='archived',role='customer',trial_started_at=now,trial_ends_at=now+timedelta(days=1))
        db.add(user)
        db.add(models.AuthSession(id=uuid.uuid4(),user_id=uid,token_hash=uuid.uuid4().hex,
            expires_at=now+timedelta(hours=1)))
        db.add(models.AccountAudit(subject_id=uid,actor_id=actor.id,action='synthetic.test'))
        db.commit()
    path=f'/api/admin/users/{uid}/delete-permanently'
    assert authenticated(client,path,actor,config,'POST',{'confirm_username':'wrong','confirmation':'DELETE PERMANENTLY'}).status_code==400
    assert authenticated(client,path,actor,config,'POST',{'confirm_username':'delete_empty','confirmation':'incorrect'}).status_code==422
    ok=authenticated(client,path,actor,config,'POST',{'confirm_username':'delete_empty','confirmation':'DELETE PERMANENTLY'})
    assert ok.status_code==200,ok.text
    assert ok.json()['database_row_deleted'] is True
    with Session(engine) as db:
        assert db.get(models.User,uid) is None,'Must really remove users row, never make released tombstone'
        assert not list(db.scalars(select(models.AuthSession).where(models.AuthSession.user_id==uid)))
        assert not list(db.scalars(select(models.AccountAudit).where(models.AccountAudit.subject_id==uid)))
        assert db.get(models.User,actor.id) is not None
        assert db.get(models.Project,target.project) is not None
        assert target.root.joinpath('marker.txt').is_file()


def test_permanent_delete_refuses_projects_without_erasing_files_or_account(boundary,monkeypatch):
    client,actor,target,engine,config=setup(boundary,monkeypatch)
    path=f'/api/admin/users/{target.id}/delete-permanently'
    active=authenticated(client,path,actor,config,'POST',{
        'confirm_username':'fixture-b','confirmation':'DELETE PERMANENTLY'})
    assert active.status_code==409
    assert authenticated(client,f'/api/admin/users/{target.id}',actor,config,'DELETE').status_code==200
    blocked=authenticated(client,path,actor,config,'POST',{
        'confirm_username':'fixture-b','confirmation':'DELETE PERMANENTLY'})
    assert blocked.status_code==409
    assert 'projects' in blocked.text
    with Session(engine) as db:
        assert db.get(models.User,target.id).status=='archived'
        assert db.get(models.Project,target.project) is not None
        assert db.get(models.Workspace,target.workspace) is not None
        assert target.root.joinpath('marker.txt').read_text()=='synthetic-marker-b'
    denied=authenticated(client,f'/api/admin/users/{actor.id}/delete-permanently',actor,config,'POST',{
        'confirm_username':'fixture-a','confirmation':'DELETE PERMANENTLY'})
    assert denied.status_code==403


def test_admin_cannot_archive_another_administrator(boundary,monkeypatch):
    client,actor,target,engine,config=setup(boundary,monkeypatch)
    with Session(engine) as db:
        db.get(models.User,target.id).role='admin';db.commit()
    assert authenticated(client,f'/api/admin/users/{target.id}',actor,config,'DELETE').status_code==403


# Existing TEST CI explicitly invokes this module. Import the isolated payment
# provider suite so its synthetic encrypted CRUD regressions are collected
# without changing either GitHub Actions workflow.
from backend.tests.test_dynamic_payment_provider_profiles import (
    db,
    test_arbitrary_provider_added_and_secret_never_returned,
    test_edit_label_optional_fields_and_keep_or_clear_secret,
    test_duplicate_ids_forbidden_and_unavailable_credentials_rejected,
    test_sensitive_fields_cannot_be_public_or_store_bank_auth_codes,
    test_profile_validation_admin_only_and_no_payment_capture_routes,
)
