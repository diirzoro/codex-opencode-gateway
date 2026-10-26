import os, smtplib, ssl
from email.message import EmailMessage
from urllib.parse import urlsplit
from fastapi import HTTPException

def send_reset(email, token, db=None):
    if db is not None:
        from .email_service_policies import enabled
        if not enabled(db,"password_reset",True):raise HTTPException(503,"Password recovery email is disabled by the administrator")
    from .email_verification import smtp_settings
    smtp_config=smtp_settings(db)
    from ..config import settings
    base=settings.public_base_url.rstrip('/')
    host=smtp_config.get('smtp_host'); sender=smtp_config.get('smtp_from')
    url=urlsplit(base)
    from .email_delivery import ready, send
    if not ready(smtp_config) or not sender or url.scheme!='https' or not url.netloc or url.username or url.password or url.query or url.fragment:
        raise HTTPException(503,'Password recovery email is not configured')
    message=EmailMessage(); message['From']=sender; message['To']=email; message['Subject']='Reset your OpenCode Gateway password'
    message.set_content(f'Reset your password within 30 minutes:\n{base}/#reset-password={token}\nIf you did not request this, ignore this email.')
    send(smtp_config,message,error_status=503)
