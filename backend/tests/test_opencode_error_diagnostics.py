"""Mock HTTP transport, safe finite diagnostics; no real model/provider request."""
import os
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://test:test@127.0.0.1/test')
import logging
from unittest.mock import Mock
import httpx
import pytest
from fastapi import HTTPException
from backend.app.services.opencode import OpenCodeService,request_operation

@pytest.mark.parametrize('method,path,expected',[
    ('POST','/session/ses_private/message','post_session_message'),
    ('GET','/session/ses_private/message?api_key=secret','get_session_message'),
    ('GET','/session/status','get_session_status'),
    ('GET','/provider','get_providers'),
    ('GET','/session','get_sessions'),
    ('GET','/session/ses_private/todo','get_session_todo'),
    ('PATCH','/session/ses_private','patch_session'),
    ('GET','/unknown/secret','get_other'),
    ('SECRET','/unknown/secret','other_other'),
])
def test_operation_labels_never_contain_private_values(method,path,expected):
    assert request_operation(method,path)==expected


def test_http_400_has_correlated_safe_reference_without_body_credentials_or_directory(caplog):
    service=OpenCodeService('http://runtime.example',password='private-password',directory='/private/owner/workspace')
    service.client.close();service.client=httpx.Client(base_url='http://runtime.example',transport=httpx.MockTransport(lambda request:httpx.Response(400,json={'name':'ValidationError','message':'private-token','data':{'directory':'/private/owner/workspace','password':'private-password'}})))
    try:
        with caplog.at_level(logging.WARNING),pytest.raises(HTTPException) as caught:
            service.request('POST','/session/ses_private/message',{'text':'private-user-prompt','model':{'providerID':'secret-provider','modelID':'model'}},params={'api_key':'private-token'})
        error=caught.value
        assert error.status_code==502 and error.runtime_status==400 and error.runtime_category=='ValidationError'
        assert len(error.runtime_reference)==12
        assert error.runtime_reference in error.detail and error.runtime_reference in caplog.text
        assert 'operation=post_session_message status=400 category=ValidationError' in caplog.text
        for secret in ['private-token','private-password','private-user-prompt','ses_private','/private/owner/workspace','secret-provider']:
            assert secret not in caplog.text and secret not in error.detail
    finally:service.close()


def test_unrecognized_upstream_name_is_not_logged(caplog):
    service=OpenCodeService('http://runtime.example');service.client.close()
    service.client=httpx.Client(base_url='http://runtime.example',transport=httpx.MockTransport(lambda request:httpx.Response(400,json={'name':'private-secret'})))
    try:
        with caplog.at_level(logging.WARNING),pytest.raises(HTTPException):service.request('GET','/provider')
        assert 'category=unclassified' in caplog.text and 'private-secret' not in caplog.text
    finally:service.close()


def test_existing_credential_failure_invalidation_preserved(caplog):
    service=OpenCodeService('http://runtime.example');service.client.close()
    service.client=httpx.Client(base_url='http://runtime.example',transport=httpx.MockTransport(lambda request:httpx.Response(401,json={'name':'ProviderAuthError'})))
    service.credential_bindings['provider']=('binding','version');service.invalidate=Mock()
    try:
        with caplog.at_level(logging.WARNING),pytest.raises(HTTPException):service.request('POST','/session/ses_private/message',{'model':{'providerID':'provider'}})
        assert service.auth_failures['provider']=='version';service.invalidate.assert_called_once()
    finally:service.close()


def test_success_response_unchanged_and_no_error_log(caplog):
    service=OpenCodeService('http://runtime.example');service.client.close()
    service.client=httpx.Client(base_url='http://runtime.example',transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'result':'ok'})))
    try:
        with caplog.at_level(logging.WARNING):assert service.request('GET','/provider')=={'result':'ok'}
        assert not caplog.records
    finally:service.close()
