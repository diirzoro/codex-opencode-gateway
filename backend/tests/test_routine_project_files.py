"""Routine opt-in permits native file edits, never scripts or protected paths."""
import os
from types import SimpleNamespace
import pytest
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://test:test@127.0.0.1/test')
from backend.app.routes import agent

@pytest.fixture
def workspace_root(monkeypatch,tmp_path):
    monkeypatch.setattr(agent.workspaces,'root_for',lambda workspace:tmp_path)
    return tmp_path

@pytest.mark.parametrize('name',['index.html','style.css','app.js','README.md'])
def test_routine_project_write(workspace_root,name):
    assert agent.routine_request(SimpleNamespace(),{'tool':'write','state':{'input':{'filePath':name}}})

@pytest.mark.parametrize('name',['../outside.html','.env','.env.local','keys/private.key','.ssh/id_rsa','/etc/passwd','.github/workflows/deploy.yml','opencode.json','.opencode/opencode.json'])
def test_protected_paths_still_require_review(workspace_root,name):
    assert not agent.routine_request(SimpleNamespace(),{'tool':'write','state':{'input':{'filePath':name}}})

@pytest.mark.parametrize('tool',['bash','apply_patch','patch','unknown'])
def test_commands_and_patches_are_not_routine(workspace_root,tool):
    assert not agent.routine_request(SimpleNamespace(),{'tool':tool,'state':{'input':{'filePath':'index.html'}}})

def test_link_to_another_project_is_not_routine(workspace_root,tmp_path):
    outside=tmp_path.parent/'other-project';outside.mkdir(exist_ok=True)
    (workspace_root/'linked').symlink_to(outside,target_is_directory=True)
    assert not agent.routine_request(SimpleNamespace(),{'tool':'edit','state':{'input':{'filePath':'linked/index.html'}}})

def native_patch(text):
    return {'tool':'apply_patch','state':{'input':{'patchText':text}}}

@pytest.mark.parametrize('body',[
    '*** Add File: index.html\n+<h1>Hello</h1>',
    '*** Update File: style.css\n@@\n-body{}\n+body{color:green}',
    '*** Add File: app.js\n+console.log("hello");\n*** Add File: README.md\n+# Project',
])
def test_native_source_file_patches_are_routine(workspace_root,body):
    assert agent.routine_request(SimpleNamespace(),native_patch('*** Begin Patch\n'+body+'\n*** End Patch'))

@pytest.mark.parametrize('body',[
    '*** Add File: .env\n+secret',
    '*** Add File: ../other-project/index.html\n+content',
    '*** Add File: index.html\n+safe\n*** Add File: .env\n+secret',
    '*** Update File: index.html\n*** Move to: ../outside.html\n@@\n-old\n+new',
    '*** Delete File: index.html',
    '*** Add File: app.js\n+safe\n*** Delete File: README.md',
    '*** Add File: .github/workflows/deploy.yml\n+workflow',
    '*** Add File: opencode.json\n+{}',
    '*** Add File: style.css\n+body{}\nnode app.js',
    '*** Unknown File: file.html\n+content',
])
def test_native_patch_boundary_failures_remain_manual(workspace_root,body):
    assert not agent.routine_request(SimpleNamespace(),native_patch('*** Begin Patch\n'+body+'\n*** End Patch'))

@pytest.mark.parametrize('patch',['',None,'node script.js','*** Begin Patch\n*** End Patch','*** Begin Patch\n*** Add File: a.js\n+ok\n*** End Patch\nnode a.js'])
def test_unrecognized_patch_is_never_automatic(workspace_root,patch):
    assert not agent.routine_request(SimpleNamespace(),native_patch(patch))

@pytest.mark.parametrize('enabled,tool,allowed,expected',[
    (True,'apply_patch',set(),True),
    (False,'apply_patch',set(),True),
    (True,'bash',set(),False),
    (True,'apply_patch',{'read'},False),
])
def test_real_permission_route_decides_only_owned_routine_edits(monkeypatch,workspace_root,enabled,tool,allowed,expected):
    import uuid
    from unittest.mock import Mock
    session=SimpleNamespace(id=uuid.uuid4(),opencode_session_id='runtime-owned',status='submitted')
    workspace=SimpleNamespace(id=uuid.uuid4())
    pending={'id':'pending-owned','sessionID':'runtime-owned','permission':'bash' if tool=='bash' else 'edit','patterns':['index.html'],'tool':{'messageID':'message','callID':'call'}}
    part=native_patch('*** Begin Patch\n*** Add File: index.html\n+<h1>Test</h1>\n*** End Patch')
    part.update({'type':'tool','callID':'call','tool':tool})
    calls=[]
    def request(method,path,payload=None):
        calls.append((method,path,payload))
        if path=='/permission': return [pending,{**pending,'id':'another-owner','sessionID':'runtime-other'}]
        if path=='/session/runtime-owned/message': return [{'info':{'id':'message'},'parts':[part]}]
        if method=='POST': return True
        raise AssertionError('Unexpected runtime route')
    service=SimpleNamespace(request=request,session_path=lambda rid,suffix:'/session/'+rid+suffix)
    monkeypatch.setattr(agent,'context',lambda *a:(session,workspace))
    monkeypatch.setattr(agent.opencode,'for_workspace',lambda *a,**kw:service)
    monkeypatch.setattr(agent,'routine_enabled',lambda *a:enabled)
    monkeypatch.setattr(agent,'remembered_approvals',lambda *a:set())
    monkeypatch.setattr(agent.policy,'load',lambda *a:{})
    monkeypatch.setattr(agent.policy,'provider_sets',lambda *a:(None,None,allowed))
    monkeypatch.setattr(agent.session_lifecycle,'lock_workspace',lambda *a:None)
    monkeypatch.setattr(agent,'event',lambda *a,**kw:None)
    result=agent.permissions(session.id,SimpleNamespace(id=uuid.uuid4()),Mock())
    posts=[call for call in calls if call[0]=='POST']
    if expected:
        assert result==[]
        assert posts==[('POST','/permission/pending-owned/reply',{'reply':'once'})]
    else:
        assert [item['id'] for item in result]==['pending-owned']
        assert posts==[]

@pytest.mark.parametrize('enabled', [False, True])
def test_conversation_opt_in_handles_all_pending_files_but_not_commands(monkeypatch, workspace_root, enabled):
    """A single saved opt-in covers distinct safe files, never other sessions."""
    import uuid
    from unittest.mock import Mock
    session=SimpleNamespace(id=uuid.uuid4(),opencode_session_id='owned',status='submitted')
    workspace=SimpleNamespace(id=uuid.uuid4())
    specs=[('read','README.md'),('read','.gitignore'),('write','nested.html'),
           ('edit','style.css'),('write','app.js'),('bash','node server.js'),('read','.env')]
    parts=[{'type':'tool','callID':str(i),'tool':tool,'state':{'input':
            {'command':path} if tool=='bash' else {'filePath':path}}}
           for i,(tool,path) in enumerate(specs)]
    pending=[{'id':str(i),'sessionID':'owned','permission':tool if tool!='write' else 'edit',
              'patterns':[path],'tool':{'messageID':'message','callID':str(i)}}
             for i,(tool,path) in enumerate(specs)]
    posts=[]
    def request(method,path,payload=None):
        if path=='/permission':return pending+[{**pending[0],'id':'foreign','sessionID':'other'}]
        if path=='/session/owned/message':return [{'info':{'id':'message'},'parts':parts}]
        if method=='POST':posts.append((path,payload));return True
        raise AssertionError(path)
    service=SimpleNamespace(request=request,session_path=lambda rid,suffix:'/session/'+rid+suffix)
    monkeypatch.setattr(agent,'context',lambda *a:(session,workspace))
    monkeypatch.setattr(agent.opencode,'for_workspace',lambda *a,**kw:service)
    monkeypatch.setattr(agent,'routine_enabled',lambda *a:enabled)
    monkeypatch.setattr(agent,'remembered_approvals',lambda *a:set())
    monkeypatch.setattr(agent.policy,'load',lambda *a:{})
    monkeypatch.setattr(agent.policy,'provider_sets',lambda *a:(None,None,set()))
    monkeypatch.setattr(agent.session_lifecycle,'lock_workspace',lambda *a:None)
    monkeypatch.setattr(agent,'event',lambda *a,**kw:None)
    db=Mock();db.execute.return_value.rowcount=0
    result=agent.permissions(session.id,SimpleNamespace(id=uuid.uuid4()),db)
    assert [row['id'] for row in result]==(['5','6'] if enabled else ['3','5','6'])
    expected_posts=[('/permission/'+str(i)+'/reply',{'reply':'once'}) for i in (range(5) if enabled else [0,1,2,4])]
    assert posts==expected_posts

@pytest.mark.parametrize('tool,name,exists,expected',[
    ('write','new.html',False,True),('write','existing.html',True,False),
    ('edit','new.html',False,False),('read','README.md',True,True),
    ('read','.env',True,False),('write','.env',False,False),
    ('write','../other.html',False,False),('bash','new.html',False,False),
    ('grep','',False,False),
])
def test_default_only_reads_or_verified_new_files(workspace_root,tool,name,exists,expected):
    if exists:(workspace_root/name).write_text('existing content')
    part={'tool':tool,'state':{'input':{'filePath':name}}}
    assert agent.non_destructive_project_request(SimpleNamespace(),part) is expected


def test_creation_recheck_preserves_existing_and_dangling_links(workspace_root):
    workspace=SimpleNamespace()
    part={'tool':'write','state':{'input':{'filePath':'new.html'}}}
    assert agent.non_destructive_project_request(workspace,part)
    (workspace_root/'new.html').write_text('created between checks')
    assert not agent.non_destructive_project_request(workspace,part)
    (workspace_root/'link.html').symlink_to(workspace_root/'absent.html')
    part['state']['input']['filePath']='link.html'
    assert not agent.non_destructive_project_request(workspace,part)

@pytest.mark.parametrize('body,expected',[
    ('*** Add File: new.html\n+hello',True),
    ('*** Update File: existing.html\n@@\n-old\n+new',False),
    ('*** Add File: existing.html\n+overwrite',False),
    ('*** Add File: new.html\n+safe\n*** Update File: existing.html\n@@\n-old\n+new',False),
    ('*** Add File: same.html\n+one\n*** Add File: same.html\n+two',False),
])
def test_default_patch_requires_every_target_to_be_new(workspace_root,body,expected):
    (workspace_root/'existing.html').write_text('old')
    assert agent.non_destructive_project_request(SimpleNamespace(),native_patch('*** Begin Patch\n'+body+'\n*** End Patch')) is expected
