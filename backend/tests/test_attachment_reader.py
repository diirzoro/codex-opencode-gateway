"""Bounded real file extraction, without model/API calls or document execution."""
import os
from types import SimpleNamespace
import zipfile
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://test:test@127.0.0.1/test')
import pytest
from fastapi import HTTPException
from backend.app.routes import agent
from backend.app.services import attachment_reader as reader

@pytest.fixture
def root(monkeypatch,tmp_path):
    monkeypatch.setattr(reader.workspaces,'root_for',lambda *args:tmp_path)
    return tmp_path


def attach(root,name,content,mime):
    (root/name).write_bytes(content)
    return {'path':name,'name':name,'mime':mime,'size':len(content)}


def docx(root,xml,name='report.docx'):
    with zipfile.ZipFile(root/name,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('word/document.xml',xml)
        archive.writestr('../outside','never extract this entry')
    return {'path':name,'name':name,'mime':'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}


def test_arabic_docx_paragraphs_tables_and_no_archive_extraction(root):
    item=docx(root,'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>مذكرة عربية</w:t><w:tab/><w:t>الاختبار</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>خلية</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>')
    part=reader.parts(SimpleNamespace(),[item])[0]
    assert part['type']=='text' and 'مذكرة عربية\tالاختبار\nخلية' in part['text']
    assert 'embedded images are not extracted' in part['text']
    assert not (root.parent/'outside').exists()

@pytest.mark.parametrize('encoding',['utf-8','utf-8-sig','utf-16'])
def test_unicode_text_is_inlined_not_a_native_uri(root,encoding):
    item=attach(root,'notes.txt','تعليمات المستخدم'.encode(encoding),'text/plain')
    part=reader.parts(SimpleNamespace(),[item])[0]
    assert part['type']=='text' and 'تعليمات المستخدم' in part['text']
    assert 'file://' not in part['text']

@pytest.mark.parametrize('name,mime',[('app.js','text/javascript'),('README.md','text/markdown'),('data.json','application/json'),('data.csv','text/csv')])
def test_source_and_structured_text_formats(root,name,mime):
    item=attach(root,name,b'content',mime)
    assert 'content' in reader.parts(SimpleNamespace(),[item])[0]['text']

@pytest.mark.parametrize('content',[b'\xff\xff',b'hello\x00binary'])
def test_binary_or_unsupported_encoding_cannot_be_claimed_as_text(root,content):
    with pytest.raises(HTTPException) as error:reader.parts(SimpleNamespace(),[attach(root,'bad.txt',content,'text/plain')])
    assert error.value.status_code==422


def test_text_limits_reject_without_silent_truncation(root):
    with pytest.raises(HTTPException) as error:reader.parts(SimpleNamespace(),[attach(root,'big.txt',b'x'*16001,'text/plain')])
    assert error.value.status_code==413
    items=[attach(root,name,b'x'*11000,'text/plain') for name in ['one.txt','two.txt']]
    with pytest.raises(HTTPException):reader.parts(SimpleNamespace(),items)

@pytest.mark.parametrize('xml',[
    '<!DOCTYPE x [<!ENTITY test "private">]><x>&test;</x>',
    '<!DOCTYPE x SYSTEM "file:///etc/passwd"><x/>',
    '<broken>',
])
def test_docx_entities_external_resources_and_invalid_xml_are_rejected(root,xml):
    with pytest.raises(HTTPException) as error:reader.parts(SimpleNamespace(),[docx(root,xml)])
    assert error.value.status_code==422
    assert 'passwd' not in str(error.value.detail)


def test_docx_large_xml_and_invalid_zip_fail_safely(root):
    with pytest.raises(HTTPException) as error:reader.parts(SimpleNamespace(),[docx(root,'x'*(reader.MAX_XML_BYTES+1))])
    assert error.value.status_code==413
    with pytest.raises(HTTPException) as error:reader.parts(SimpleNamespace(),[attach(root,'broken.docx',b'not a zip','application/zip')])
    assert error.value.status_code==422

@pytest.mark.parametrize('name,mime,head',[
    ('photo.png','image/png',b'\x89PNG\r\n\x1a\n'),('photo.jpg','image/jpeg',b'\xff\xd8\xff'),
    ('photo.gif','image/gif',b'GIF89a'),('photo.webp','image/webp',b'RIFF1234WEBP'),
    ('report.pdf','application/pdf',b'%PDF-1.7'),
])
def test_native_files_keep_uri_for_runtime_and_are_not_claimed_as_extracted(root,name,mime,head):
    part=reader.parts(SimpleNamespace(),[attach(root,name,head,mime)])[0]
    assert part['type']=='file' and part['mime']==mime and part['url']==(root/name).as_uri()


def test_invalid_image_bytes_rejected_before_dispatch(root):
    with pytest.raises(HTTPException) as error:reader.parts(SimpleNamespace(),[attach(root,'fake.png',b'not an image','image/png')])
    assert error.value.status_code==422


def test_unsupported_format_is_honest_tool_only_context(root):
    part=reader.parts(SimpleNamespace(),[attach(root,'old.doc',b'binary','application/msword')])[0]
    assert 'Automatic text extraction is unavailable' in part['text']
    assert 'Never infer contents or claim to have read it' in part['text']


def test_other_project_and_sensitive_attachment_paths_remain_blocked(root):
    for path in ['../other.txt','.env','linked.txt']:
        if path=='linked.txt':(root/path).symlink_to(root.parent/'private')
        with pytest.raises(HTTPException):
            agent.attachment_metadata(SimpleNamespace(),[agent.AttachmentRequest(path=path)])

@pytest.mark.parametrize('category,support', [('image',False),('pdf',False),('image',True),('image',None),('pdf',True)])
def test_native_model_support_is_checked_without_inventing_unknown_capability(category,support):
    model={'capabilities':{'input':{category:support}}}
    rows=[{'mime':'image/png' if category=='image' else 'application/pdf'}]
    if support is False:
        with pytest.raises(HTTPException) as error:reader.ensure_model_inputs(model,rows)
        assert error.value.status_code==422 and ('images' if category=='image' else 'PDF') in error.value.detail
    else:reader.ensure_model_inputs(model,rows)

@pytest.mark.parametrize('role',['build','plan','custom-agent'])
def test_all_agent_roles_receive_extracted_document_text_in_actual_execute(root,monkeypatch,role):
    import asyncio
    import uuid
    workspace=SimpleNamespace();row=attach(root,'notes.txt','محتوى الملف الحقيقي'.encode(),'text/plain')
    monkeypatch.setattr(agent,'begin_execution',lambda *args:workspace)
    monkeypatch.setattr(agent,'attachment_metadata',lambda *args:[row])
    monkeypatch.setattr(agent,'complete_execution',lambda *args,**kwargs:None)
    async def noop(*args):return
    monkeypatch.setattr(agent,'monitor_activity',noop);monkeypatch.setattr(agent,'dispatch_queued',noop)
    calls=[]
    service=SimpleNamespace(generation=1,session_path=lambda *args:'/message',request=lambda method,path,payload,timeout:calls.append(payload) or {'info':{'role':'assistant','time':{'completed':1}},'parts':[]})
    data=SimpleNamespace(request_id=uuid.uuid4(),text='اقرأ المرفق',provider_id='owned',model_id='text-model',agent_id=role,attachments=[])
    asyncio.run(agent.execute(uuid.uuid4(),service,'runtime',data,'message'))
    assert len(calls)==1 and calls[0]['agent']==role
    assert 'محتوى الملف الحقيقي' in calls[0]['parts'][1]['text']
    assert all(part['type']=='text' for part in calls[0]['parts'])


def test_disappeared_docx_is_a_clear_read_error_not_an_internal_exception(root):
    with pytest.raises(HTTPException) as error:reader.docx_text(root/'missing.docx')
    assert error.value.status_code==422 and 'could not be read safely' in error.value.detail
