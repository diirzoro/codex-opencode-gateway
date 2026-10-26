"""Fixed vendor reads, write preflight and enforced service preferences; isolated fixtures."""
import json, uuid
from io import BytesIO
from urllib.error import HTTPError, URLError
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from backend.tests.test_admin_mailbox_delivery import mail_acceptance, acceptance, boundary, configured
from backend.tests.test_six_issue_acceptance import request
from backend.app import models
from backend.app.services import email_delivery, admin_email_config, recovery


@pytest.mark.parametrize('code,fragment',[(401,'Full access'),(403,'Full access'),(429,'rate limit'),(404,'not found'),(500,'no permission verdict')])
def test_vendor_errors_are_precise_without_exposing_keys(monkeypatch,code,fragment):
    def fail(req,**kwargs):raise HTTPError(req.full_url,code,'SECRET_KEY_DO_NOT_LOG',{},BytesIO(b'SECRET_KEY_DO_NOT_LOG'))
    monkeypatch.setattr('urllib.request.urlopen',fail)
    with pytest.raises(HTTPException) as error:email_delivery.read_resend('/emails/receiving?limit=50','SECRET_KEY_DO_NOT_LOG')
    assert fragment in error.value.detail
    assert 'SECRET_KEY_DO_NOT_LOG' not in error.value.detail


def test_network_failure_does_not_misdiagnose_permissions(monkeypatch):
    def fail(*args,**kwargs):raise URLError('SECRET_NETWORK_DETAIL')
    monkeypatch.setattr('urllib.request.urlopen',fail)
    with pytest.raises(HTTPException) as error:email_delivery.read_resend('/emails?limit=50','synthetic')
    assert 'connect' in error.value.detail and 'does not prove' in error.value.detail
    assert 'SECRET_NETWORK_DETAIL' not in error.value.detail


def test_read_key_preflight_rejects_sending_only_key_without_overwriting_saved_key(mail_acceptance,monkeypatch):
    f=mail_acceptance;configured(f)
    def fail(req,**kwargs):raise HTTPError(req.full_url,401,'restricted_api_key',{},BytesIO(b''))
    monkeypatch.setattr('urllib.request.urlopen',fail)
    response=request(f,'/api/admin/service-integrations/inbox-credential',True,'PUT',{'api_key':'SYNTHETIC_SENDING_ONLY_KEY'})
    assert response.status_code==502 and 'Full access' in response.json()['detail']
    with Session(f[2]) as db:
        cfg=admin_email_config.read(db)
        assert cfg['inbox_api_key']=='SYNTHETIC_MAIL_KEY' and cfg['smtp_password']=='SYNTHETIC_MAIL_KEY'
    monkeypatch.setattr('urllib.request.urlopen',lambda req,**kwargs:BytesIO(json.dumps({'data':[]}).encode()))
    assert request(f,'/api/admin/service-integrations/inbox-credential',True,'PUT',{'api_key':'SYNTHETIC_READ_KEY'}).status_code==200
    with Session(f[2]) as db:
        cfg=admin_email_config.read(db)
        assert cfg['inbox_api_key']=='SYNTHETIC_READ_KEY' and cfg['smtp_password']=='SYNTHETIC_MAIL_KEY'


def test_recovery_toggle_persists_and_blocks_real_delivery_and_token_creation(mail_acceptance,monkeypatch):
    f=mail_acceptance;configured(f)
    endpoint='/api/admin/service-integrations/services/password_reset'
    assert request(f,endpoint,False,'PUT',{'enabled':False}).status_code==403
    assert request(f,endpoint,True,'PUT',{'enabled':False}).status_code==200
    status=request(f,'/api/admin/service-integrations').json()
    row=next(item for item in status['services'] if item['id']=='password_reset')
    assert row['enabled'] is False and row['editable'] is True
    def forbidden(*args,**kwargs):raise AssertionError('Disabled recovery must not send')
    monkeypatch.setattr(email_delivery,'send',forbidden)
    with Session(f[2]) as db:
        user=db.get(models.User,f[1][1].id);user.email='controlled-fixture@example.org';db.commit();email=user.email
        before=db.scalar(select(func.count()).select_from(models.PasswordReset))
        with pytest.raises(HTTPException) as error:recovery.send_reset(email,'synthetic',db)
        assert error.value.status_code==503
    result=request(f,'/api/auth/forgot-password',False,'POST',{'email':email})
    assert result.status_code==202,result.text
    with Session(f[2]) as db:assert db.scalar(select(func.count()).select_from(models.PasswordReset))==before
    assert request(f,endpoint,True,'PUT',{'enabled':True}).status_code==200
    assert next(item for item in request(f,'/api/admin/service-integrations').json()['services'] if item['id']=='password_reset')['enabled'] is True
    assert request(f,'/api/admin/service-integrations/services/low_balance',True,'PUT',{'enabled':True}).status_code==409
