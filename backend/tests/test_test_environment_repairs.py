"""Targeted disposable data for TEST repair acceptance; never existing staging DB."""
import os,uuid
from datetime import datetime,timedelta,timezone
import pytest
from backend.tests.test_disposable_database import account
pytestmark=pytest.mark.skipif(os.getenv('AUDIT_DISPOSABLE_DB')!='1',reason='explicit disposable database required')


def create(client,name='Repair'):
    response=client.post('/api/projects',json={'project_name':name+uuid.uuid4().hex[:8]})
    assert response.status_code==201,response.text
    return response.json()


def test_workspace_restore_owns_context_and_skips_missing_archived_projects(account):
    from backend.app.database import SessionLocal
    from backend.app.models import Workspace,WorkspaceSession,Project
    from backend.app.services import workspaces
    client,_,owner,_=account
    assert client.get('/api/workspace-context').json()['workspace'] is None
    first=create(client);second=create(client)
    wid=uuid.UUID(first['workspace']['id'])
    with SessionLocal() as db:
        session=WorkspaceSession(workspace_id=wid,user_id=uuid.UUID(owner['id']),opencode_session_id='ses_fixture_owned',title='Previous conversation',status='idle');db.add(session);db.commit();sid=str(session.id)
    restored=client.get('/api/workspace-context',params={'workspace_id':str(wid),'session_id':sid});assert restored.status_code==200,restored.text
    assert restored.json()['workspace']['id']==str(wid) and restored.json()['session']['id']==sid
    # A foreign/missing preference never becomes active context; select owned fallback.
    fallback=client.get('/api/workspace-context',params={'workspace_id':str(uuid.uuid4()),'session_id':str(uuid.uuid4())}).json()
    assert fallback['workspace']['id'] in {first['workspace']['id'],second['workspace']['id']}
    with SessionLocal() as db:
        db.get(Project,uuid.UUID(first['project']['id'])).archived_at=datetime.now(timezone.utc);db.commit()
        other=db.get(Workspace,uuid.UUID(second['workspace']['id']));root=workspaces.root_for(other);root.rename(root.with_name('missing-fixture'))
    assert client.get('/api/workspace-context',params={'workspace_id':str(wid)}).json()['workspace'] is None



def test_restore_never_uses_other_accounts_workspace_or_session(account):
    from backend.app.database import SessionLocal
    from backend.app.models import User,Project,Workspace,WorkspaceSession
    from backend.app.services import workspaces
    client,_,_,_=account;owned=create(client);now=datetime.now(timezone.utc)
    with SessionLocal() as db:
        other=User(username='restore_'+uuid.uuid4().hex[:12],email=uuid.uuid4().hex+'@example.org',password_hash='fixture',phone='',postal_code='',trial_started_at=now,trial_ends_at=now+timedelta(days=30));db.add(other);db.flush()
        project=Project(user_id=other.id,name='Other account',source_type='blank');db.add(project);db.flush()
        workspace=Workspace(user_id=other.id,project_id=project.id,status='ready');db.add(workspace);db.flush();workspaces.root_for(workspace).mkdir(parents=True)
        session=WorkspaceSession(user_id=other.id,workspace_id=workspace.id,opencode_session_id='ses_foreign_restore',title='Private',status='submitted');db.add(session);db.commit();wid=str(workspace.id);sid=str(session.id)
    result=client.get('/api/workspace-context',params={'workspace_id':wid,'session_id':sid});assert result.status_code==200,result.text
    assert result.json()['workspace']['id']==owned['workspace']['id'] and result.json()['session'] is None
    for path in ['/api/workspaces/'+wid,'/api/sessions/'+sid]:assert client.get(path).status_code==404
