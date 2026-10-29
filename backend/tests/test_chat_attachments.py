"""Real temporary filesystem/stream tests; Native status is a controlled fixture."""
import asyncio
import json
import uuid
from dataclasses import replace
from types import SimpleNamespace as NS
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
from backend.tests.test_native_control_plane import boundary, authenticated
from backend.app.models import Workspace
from backend.app.services import chat_attachments as uploads, workspaces, workspace_cache

@pytest.fixture
def fixture(boundary,monkeypatch,tmp_path):
    client,owners,calls,engine,config=boundary
    monkeypatch.setattr(uploads,'settings',replace(config,runtime_root=tmp_path/'metadata'))
    monkeypatch.setattr(workspace_cache,'runtime_idle',lambda row:True)
    with Session(engine) as db:
        row=workspaces.owned(db,Workspace,owners[0].workspace,owners[0].id)
        yield NS(client=client,owners=owners,config=config,db=db,row=row)


def slot(f,name='synthetic.txt',size=100):
    return uploads.create(f.db,f.row,f.owners[0].session,name,size,'text/plain')

def test_slot_creation_scans_workspace_quota_only_once(fixture,monkeypatch):
    f=fixture
    original=uploads.workspaces.usage_bytes
    calls=[]
    def measured(*args,**kwargs):
        calls.append((args,kwargs))
        return original(*args,**kwargs)
    monkeypatch.setattr(uploads.workspaces,'usage_bytes',measured)
    item=slot(f,'single-scan.txt',100)
    assert item['state']=='uploading'
    assert len(calls)==1
    assert uploads.cancel(f.row,item['id'])['removed']


def request(chunks,error=False):
    async def stream():
        for chunk in chunks: yield chunk
        if error: raise ConnectionError('synthetic offline')
    return NS(stream=stream)

def transferred(f):
    item=slot(f)
    return asyncio.run(uploads.upload(f.row,item['id'],request([b'x'*100])))

@pytest.mark.parametrize('percentage',[10,50,90])
def test_cancel_mid_transfer_at_each_boundary(fixture,percentage):
    f=fixture;item=slot(f)
    async def stream():
        yield b'x'*percentage
        assert uploads.cancel(f.row,item['id'])['removed']
        yield b'x'*(100-percentage)
    with pytest.raises(HTTPException,match='Upload cancelled'):
        asyncio.run(uploads.upload(f.row,item['id'],NS(stream=stream)))
    assert not (f.owners[0].root/item['path']).exists()
    assert not (f.owners[0].root/item['path']).with_name('upload.part').exists()
    assert (f.owners[0].root/'marker.txt').is_file()


def test_ready_cancel_blocks_native_submission_and_preserves_projects(fixture):
    f=fixture;item=transferred(f)
    assert uploads.cancel(f.row,item['id'])=={'removed':True,'state':'cancelled'}
    session=NS(id=f.owners[0].session)
    with pytest.raises(HTTPException) as exc: uploads.lease(f.row,session,item['path'],'msg_fixture')
    assert exc.value.status_code==410
    assert (f.owners[0].root/'marker.txt').read_text()=='synthetic-marker-a'


def test_offline_cleans_partial_and_allows_a_new_upload(fixture):
    f=fixture;item=slot(f)
    with pytest.raises(ConnectionError):asyncio.run(uploads.upload(f.row,item['id'],request([b'x'*10],True)))
    assert not (f.owners[0].root/item['path']).with_name('upload.part').exists()
    assert transferred(f)['state']=='ready'


def test_native_busy_protects_original_beyond_expiration_then_idle_removes(fixture,monkeypatch):
    f=fixture;item=transferred(f);session=NS(id=f.owners[0].session)
    uploads.lease(f.row,session,item['path'],'msg_fixture')
    with pytest.raises(HTTPException) as exc:uploads.cancel(f.row,item['id'])
    assert exc.value.status_code==409
    monkeypatch.setattr(workspace_cache,'runtime_idle',lambda row:False)
    uploads.reap_workspace(f.row,now=uploads.time.time()+uploads.TTL+1)
    assert (f.owners[0].root/item['path']).exists()
    monkeypatch.setattr(workspace_cache,'runtime_idle',lambda row:True)
    uploads.reap_workspace(f.row,now=uploads.time.time()+uploads.TTL+2)
    assert not (f.owners[0].root/item['path']).exists()
    assert (f.owners[0].root/'marker.txt').is_file()
    assert (f.owners[1].root/'marker.txt').is_file()


def test_finished_native_cleanup_has_forwarding_grace_and_no_recursive_delete(fixture):
    f=fixture;item=transferred(f);uploads.lease(f.row,NS(id=f.owners[0].session),item['path'],'msg_fixture')
    uploads.acknowledge(f.row,f.owners[0].session,'msg_fixture',[item['id']])
    extra=(f.owners[0].root/item['path']).with_name('not-classified.txt');extra.write_text('preserve unknown file')
    uploads.reap_workspace(f.row)
    assert (f.owners[0].root/item['path']).exists()
    uploads.reap_workspace(f.row,now=uploads.time.time()+uploads.FORWARD_GRACE+1)
    assert not (f.owners[0].root/item['path']).exists()
    assert extra.read_text()=='preserve unknown file'


def test_orphan_ready_and_partial_expire_without_reading_native_history(fixture,monkeypatch):
    f=fixture;item=transferred(f);partial=slot(f,'second.txt')
    (f.owners[0].root/partial['path']).with_name('upload.part').write_bytes(b'partial')
    def forbidden(row):raise AssertionError('Unused uploads do not need a Native request')
    monkeypatch.setattr(workspace_cache,'runtime_idle',forbidden)
    uploads.reap_workspace(f.row,now=uploads.time.time()+uploads.TTL+1)
    assert not (f.owners[0].root/item['path']).exists()
    assert not (f.owners[0].root/partial['path']).with_name('upload.part').exists()

@pytest.mark.parametrize('name',['../secret','/etc/passwd','.env','private.key','nested/file','upload.part'])
def test_untrusted_filenames_rejected(fixture,name):
    with pytest.raises(HTTPException):slot(fixture,name)


def test_symlink_cannot_delete_owned_project_marker(fixture):
    f=fixture;item=transferred(f);file=f.owners[0].root/item['path'];file.unlink();file.symlink_to(f.owners[0].root/'marker.txt')
    with pytest.raises(HTTPException):uploads.cancel(f.row,item['id'])
    assert (f.owners[0].root/'marker.txt').is_file()


def test_unmanaged_reserved_directory_is_preserved(fixture):
    f=fixture;directory=f.owners[0].root/uploads.DIRECTORY;directory.mkdir();(directory/'existing.txt').write_text('intentional project data')
    with pytest.raises(HTTPException) as exc:slot(f)
    assert exc.value.status_code==409
    assert (directory/'existing.txt').read_text()=='intentional project data'


def test_foreign_workspace_upload_and_cancel_return_404(fixture):
    f=fixture;a,b=f.owners
    response=authenticated(f.client,f'/api/workspaces/{b.workspace}/attachments',a,f.config,'POST',{'session_id':str(a.session),'name':'synthetic.txt','size':100,'mime':'text/plain'})
    assert response.status_code==404
    response=f.client.delete(f'/api/workspaces/{b.workspace}/attachments/{uuid.uuid4()}',headers={'Cookie':f.config.session_cookie_name+'=fixture-token-a'})
    assert response.status_code==404


def test_wrong_conversation_cannot_use_attachment(fixture):
    f=fixture;item=transferred(f)
    with pytest.raises(HTTPException) as exc:uploads.lease(f.row,NS(id=f.owners[1].session),item['path'],'msg_fixture')
    assert exc.value.status_code==404


def test_same_filename_has_distinct_temporary_paths(fixture):
    f=fixture;one=transferred(f);two=transferred(f)
    assert one['path']!=two['path']
    assert uploads.cancel(f.row,one['id'])['removed']
    assert (f.owners[0].root/two['path']).is_file()


def test_http_upload_roundtrip_and_metadata_restore(fixture):
    f=fixture;a=f.owners[0]
    created=authenticated(f.client,f'/api/workspaces/{a.workspace}/attachments',a,f.config,'POST',{'session_id':str(a.session),'name':'http-qa.txt','size':4,'mime':'text/plain'})
    assert created.status_code==201,created.text
    item=created.json();url=f'/api/workspaces/{a.workspace}/attachments/'+item['id']
    headers={'Cookie':f.config.session_cookie_name+'=fixture-token-a','Origin':f.config.public_base_url,'Content-Type':'application/octet-stream'}
    response=f.client.put(url,content=b'test',headers=headers)
    assert response.status_code==200,response.text
    restored=f.client.get(url,headers=headers)
    assert restored.status_code==200 and restored.json()['state']=='ready'
    assert restored.headers['cache-control']=='private, no-store'
    assert f.client.delete(url,headers=headers).json()['removed']
    assert f.client.get(url,headers=headers).json()['state']=='cancelled'


def test_duplicate_put_cannot_destroy_inflight_transfer(fixture):
    f=fixture;item=slot(f)
    async def stream():
        yield b'x'*50
        with pytest.raises(HTTPException) as exc:
            await uploads.upload(f.row,item['id'],request([b'y'*100]))
        assert exc.value.status_code==409
        yield b'x'*50
    result=asyncio.run(uploads.upload(f.row,item['id'],NS(stream=stream)))
    assert result['state']=='ready'
    assert (f.owners[0].root/result['path']).read_bytes()==b'x'*100


def test_native_status_failure_defers_cleanup_without_claiming_removed(fixture,monkeypatch):
    f=fixture;item=transferred(f);uploads.lease(f.row,NS(id=f.owners[0].session),item['path'],'msg_fixture')
    def failed(row):raise HTTPException(502,'synthetic native unavailable')
    monkeypatch.setattr(workspace_cache,'runtime_idle',failed)
    uploads.reap_workspace(f.row,now=uploads.time.time()+uploads.TTL+1)
    assert (f.owners[0].root/item['path']).is_file()
    with uploads.locked(f.row,item['id']) as (value,_):assert value['cleanup_deferred']=='native-status-unavailable'


def test_temporary_original_is_not_exported_or_committed(fixture):
    import subprocess,zipfile
    from backend.app.services import workspaces
    f=fixture;item=transferred(f);root=f.owners[0].root
    def git(*args):return subprocess.run(['git','-C',str(root),*args],check=True,capture_output=True,text=True).stdout
    git('init');git('config','user.email','synthetic@example.invalid');git('config','user.name','Synthetic QA');git('add','marker.txt');git('commit','-m','baseline')
    (root/'intentional.txt').write_text('project file remains')
    workspaces.commit(f.row,NS(username='Synthetic QA',email='synthetic@example.invalid'),'intentional project change')
    assert 'intentional.txt' in git('ls-files')
    assert uploads.DIRECTORY not in git('ls-files')
    archive=workspaces.export(f.row)
    try:
        with zipfile.ZipFile(archive) as z:
            assert 'intentional.txt' in z.namelist()
            assert not any(name.startswith(uploads.DIRECTORY+'/') for name in z.namelist())
    finally:archive.unlink()


def test_uncertain_native_receipt_preserves_draft_file_until_unused_expiry(fixture):
    f=fixture;item=transferred(f);uploads.lease(f.row,NS(id=f.owners[0].session),item['path'],'msg_uncertain')
    uploads.reap_workspace(f.row,now=uploads.time.time()+uploads.FORWARD_GRACE+2)
    assert (f.owners[0].root/item['path']).is_file()
    uploads.acknowledge(f.row,f.owners[0].session,'msg_uncertain',[item['id']])
    uploads.reap_workspace(f.row,now=uploads.time.time()+uploads.FORWARD_GRACE+3)
    assert not (f.owners[0].root/item['path']).exists()
