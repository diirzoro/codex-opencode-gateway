"""Owned fail-closed Preview lifecycle HTTP contract; no container simulated."""
import os,uuid
from datetime import datetime,timedelta,timezone
import pytest
from backend.tests.test_disposable_database import account
pytestmark=pytest.mark.skipif(os.getenv('AUDIT_DISPOSABLE_DB')!='1',reason='disposable database required')


def test_preview_control_routes_are_owned_and_never_enable_execution(account):
    from backend.app.database import SessionLocal
    from backend.app.models import User,Workspace
    from backend.app.services import workspaces
    client,_,_,_=account
    response=client.post('/api/projects',json={'project_name':'preview-'+uuid.uuid4().hex[:8]});assert response.status_code==201,response.text
    wid=response.json()['workspace']['id'];base=f'/api/workspaces/{wid}/preview'
    with SessionLocal() as db:
        workspace=db.get(Workspace,uuid.UUID(wid));root=workspaces.root_for(workspace)
        (root/'package.json').write_text('{"dependencies":{"vite":"fixture"}}')
    state=client.get(base+'/status');assert state.status_code==200,state.text
    assert state.json()['execution_enabled'] is False and state.json()['url'] is None
    assert state.json()['launch']['profile_available'] is True
    assert str(root) not in state.text
    assert client.post(base+'/start',json={'command':'touch MUST_NOT_EXECUTE','privileged':True}).status_code==503
    assert client.post(base+'/stop').json()['state']=='stopped'
    assert client.post(base+'/stop').json()['state']=='stopped'
    assert not (root/'MUST_NOT_EXECUTE').exists()
    # A valid second account cannot inspect/control the first workspace.
    from backend.app.security.sessions import new_session_token
    from backend.app.models import AuthSession
    from backend.app.config import settings
    now=datetime.now(timezone.utc);raw,hashed=new_session_token()
    with SessionLocal() as db:
        other=User(username='preview_'+uuid.uuid4().hex[:12],email=uuid.uuid4().hex+'@example.org',password_hash='fixture',phone='',postal_code='',trial_started_at=now,trial_ends_at=now+timedelta(days=30));db.add(other);db.flush();db.add(AuthSession(user_id=other.id,token_hash=hashed,expires_at=now+timedelta(hours=1)));db.commit()
    client.cookies.clear();client.cookies.set(settings.session_cookie_name,raw)
    for method,suffix in [('GET','/status'),('GET','/plan'),('POST','/start'),('POST','/stop')]:
        denied=client.request(method,base+suffix);assert denied.status_code==404,(suffix,denied.text)
