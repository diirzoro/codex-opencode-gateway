"""Provider defaults and switching in existing encrypted mail settings; no live vendor calls."""
import json, sqlite3, uuid
from sqlalchemy.orm import Session
from sqlalchemy import text
import httpx
import pytest
from backend.tests.test_admin_mailbox_delivery import mail_acceptance, acceptance, boundary
from backend.tests.test_six_issue_acceptance import request, migrate_email
from backend.app.services import admin_email_config, email_delivery, email_verification, recovery


def initialize(f):
    migrate_email(f[2]);sqlite3.register_adapter(uuid.UUID,lambda value:value.hex)


def save(f,**body):
    return request(f,'/api/admin/service-integrations/email',True,'PUT',body)


def test_key_only_defaults_switch_back_preserves_each_provider_and_resend_read_key(mail_acceptance):
    f=mail_acceptance;initialize(f)
    first=save(f,api_key='SYNTHETIC_RESEND_KEY');assert first.status_code==200,first.text
    assert first.json()['sender']=='no-reply@opencode-gateway.codes'
    assert first.json()['sender_name']=='OpenCode Gateway'
    assert save(f,provider='brevo').status_code==422
    second=save(f,provider='brevo',api_key='SYNTHETIC_BREVO_KEY');assert second.status_code==200,second.text
    assert second.json()['transport']=='https'
    response=request(f,'/api/admin/service-integrations')
    assert 'SYNTHETIC_' not in response.text
    assert response.json()['email']['provider']=='brevo'
    assert all(item['configured'] for item in response.json()['email']['provider_configurations'].values())
    with Session(f[2]) as db:
        cfg=admin_email_config.read(db)
        assert cfg['inbox_api_key']=='SYNTHETIC_RESEND_KEY'
        assert cfg['provider_accounts']['resend']['smtp_password']=='SYNTHETIC_RESEND_KEY'
        assert cfg['api_key']=='SYNTHETIC_BREVO_KEY'
        cipher=db.execute(text('SELECT encrypted_data FROM email_delivery_settings')).scalar_one()
        assert 'SYNTHETIC_' not in cipher
    assert save(f,provider='resend').status_code==200
    with Session(f[2]) as db:
        cfg=admin_email_config.read(db)
        assert cfg['smtp_password']=='SYNTHETIC_RESEND_KEY'
        assert cfg['provider_accounts']['brevo']['api_key']=='SYNTHETIC_BREVO_KEY'


def test_brevo_is_used_for_compose_verification_and_password_recovery(mail_acceptance,monkeypatch):
    f=mail_acceptance;initialize(f);assert save(f,provider='brevo',api_key='SYNTHETIC_BREVO_KEY').status_code==200
    calls=[];original=httpx.Client
    def handler(req):
        assert str(req.url)==email_delivery.BREVO_URL
        assert req.headers['api-key']=='SYNTHETIC_BREVO_KEY'
        body=json.loads(req.content);assert body['sender']=={'email':'no-reply@opencode-gateway.codes','name':'OpenCode Gateway'}
        assert 'textContent' in body and 'htmlContent' not in body
        calls.append(body);return httpx.Response(201,json={'messageId':'synthetic-accepted-id'})
    monkeypatch.setattr(email_delivery.httpx,'Client',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    def forbidden(*args,**kwargs):raise AssertionError('Brevo API must not use SMTP')
    monkeypatch.setattr(email_delivery.smtplib,'SMTP',forbidden)
    result=request(f,'/api/admin/service-integrations/send-email',True,'POST',{'to':'owned@example.com','subject':'Synthetic compose','body':'Harmless test'})
    assert result.status_code==200,result.text
    with Session(f[2]) as db:
        email_verification.send_link('owned@example.com','synthetic-verification-token',db)
        recovery.send_reset('owned@example.com','synthetic-reset-token',db)
    assert len(calls)==3
    assert 'verify-email?token=' in calls[1]['textContent']
    assert '#reset-password=' in calls[2]['textContent']
    assert request(f,'/api/admin/service-integrations').json()['email']['delivery_verified'] is False


@pytest.mark.parametrize('status,payload',[(401,{'message':'SYNTHETIC_BREVO_KEY'}),(429,{}),(201,{})])
def test_brevo_errors_never_leak_key_or_confirm_delivery(mail_acceptance,monkeypatch,status,payload):
    f=mail_acceptance;initialize(f);assert save(f,provider='brevo',api_key='SYNTHETIC_BREVO_KEY').status_code==200
    original=httpx.Client
    monkeypatch.setattr(email_delivery.httpx,'Client',lambda **kwargs:original(transport=httpx.MockTransport(lambda req:httpx.Response(status,json=payload)),**kwargs))
    result=request(f,'/api/admin/service-integrations/send-email',True,'POST',{'to':'owned@example.com','subject':'Synthetic','body':'Test'})
    assert result.status_code==502
    assert 'SYNTHETIC_BREVO_KEY' not in result.text and '"sent":true' not in result.text


def test_customer_cannot_activate_brevo_and_invalid_senders_are_rejected(mail_acceptance):
    f=mail_acceptance;initialize(f)
    assert request(f,'/api/admin/service-integrations/email',False,'PUT',{'provider':'brevo','api_key':'SYNTHETIC_KEY'}).status_code==403
    assert save(f,provider='brevo',api_key='SYNTHETIC_KEY',smtp_from='other@example.com').status_code==422
    assert save(f,provider='brevo',api_key='SYNTHETIC_KEY',sender_name='Name\r\nBcc: other').status_code==422
    assert save(f,provider='unsupported',api_key='SYNTHETIC_KEY').status_code==422
