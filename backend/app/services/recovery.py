import os, smtplib, ssl
from email.message import EmailMessage
from urllib.parse import urlsplit
from fastapi import HTTPException

def send_reset(email, token, db=None):
    from .email_verification import smtp_settings
    smtp_config=smtp_settings(db)
    from ..config import settings
    base=settings.public_base_url.rstrip('/')
    host=smtp_config.get('smtp_host'); sender=smtp_config.get('smtp_from')
    url=urlsplit(base)
    if not host or not sender or url.scheme!='https' or not url.netloc or url.username or url.password or url.query or url.fragment:
        raise HTTPException(503,'Password recovery email is not configured')
    message=EmailMessage(); message['From']=sender; message['To']=email; message['Subject']='Reset your OpenCode Gateway password'
    message.set_content(f'Reset your password within 30 minutes:\n{base}/#reset-password={token}\nIf you did not request this, ignore this email.')
    try:
        with smtplib.SMTP(host,int(smtp_config.get('smtp_port',587)),timeout=15) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            if smtp_config.get('smtp_username'): smtp.login(smtp_config['smtp_username'],smtp_config.get('smtp_password',''))
            smtp.send_message(message)
    except (OSError,smtplib.SMTPException,ValueError):
        raise HTTPException(503,'Password recovery email could not be delivered')
