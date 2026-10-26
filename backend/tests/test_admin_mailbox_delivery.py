"""Existing Resend compose/status APIs, synthetic SMTP and isolated DB only."""
import sqlite3, uuid, smtplib, importlib.util
import pytest
from alembic.operations import Operations
from alembic.migration import MigrationContext
from sqlalchemy.orm import Session
from backend.tests.test_six_issue_acceptance import acceptance, migrate_email, request
from backend.tests.test_native_control_plane import boundary
from backend.app.services import admin_email_config


@pytest.fixture
def mail_acceptance(acceptance):
    spec=importlib.util.spec_from_file_location('mail_policy_migration','backend/alembic/versions/0022_email_service_policies.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with acceptance[2].begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):module.upgrade()
    return acceptance


def configured(f):
    migrate_email(f[2]);sqlite3.register_adapter(uuid.UUID,lambda value:value.hex)
    response=request(f,'/api/admin/service-integrations/email',True,'PUT',{
        'smtp_from':'support@opencode-gateway.codes','api_key':'SYNTHETIC_MAIL_KEY'})
    assert response.status_code==200,response.text


def test_mail_status_is_secret_free_and_customers_cannot_send_or_configure(mail_acceptance):
    f=mail_acceptance
    status=request(f,'/api/admin/service-integrations').json()['email']
    assert status['credential_storage_ready'] is True
    assert status['configured'] is False and status['delivery_verified'] is False
    configured(f)
    response=request(f,'/api/admin/service-integrations')
    assert 'SYNTHETIC_MAIL_KEY' not in response.text
    assert response.json()['email']['configured'] is True
    for path,method,data in [('/api/admin/service-integrations','GET',None),
       ('/api/admin/service-integrations/send-email','POST',{'to':'owned@example.com','subject':'Synthetic','body':'Test'}),
       ('/api/admin/service-integrations/email','PUT',{'smtp_from':'support@opencode-gateway.codes','api_key':'OTHER_KEY'})]:
        assert request(f,path,False,method,data).status_code==403
    with Session(f[2]) as db:assert admin_email_config.read(db)['smtp_password']=='SYNTHETIC_MAIL_KEY'


def test_existing_compose_uses_saved_resend_credentials_and_tls(mail_acceptance,monkeypatch):
    f=mail_acceptance;configured(f);sent=[];steps=[]
    class SMTP:
        def __init__(self,host,port,**kwargs):assert (host,port)==('smtp.resend.com',587)
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def starttls(self,context):assert context.check_hostname;steps.append('tls')
        def login(self,user,key):assert (user,key)==('resend','SYNTHETIC_MAIL_KEY');steps.append('login')
        def send_message(self,message):assert steps==['tls','login'];sent.append(message)
    monkeypatch.setattr(smtplib,'SMTP',SMTP)
    response=request(f,'/api/admin/service-integrations/send-email',True,'POST',{'to':'owned@example.com','subject':'Synthetic test','body':'Harmless test body'})
    assert response.status_code==200 and response.json()['sent'] is True
    assert len(sent)==1 and sent[0]['To']=='owned@example.com'
    assert sent[0]['Reply-To']=='support@opencode-gateway.codes'
    assert request(f,'/api/admin/service-integrations').json()['email']['delivery_verified'] is False


def test_smtp_failure_never_reports_success_or_exposes_key(mail_acceptance,monkeypatch):
    f=mail_acceptance;configured(f)
    def fail(*args,**kwargs):raise smtplib.SMTPAuthenticationError(535,b'SYNTHETIC_MAIL_KEY')
    monkeypatch.setattr(smtplib,'SMTP',fail)
    response=request(f,'/api/admin/service-integrations/send-email',True,'POST',{'to':'owned@example.com','subject':'Synthetic test','body':'Test'})
    assert response.status_code==502
    assert 'SYNTHETIC_MAIL_KEY' not in response.text and '"sent":true' not in response.text
