import os, smtplib, ssl
from email.message import EmailMessage
from urllib.parse import urlsplit
from fastapi import HTTPException

def send_reset(email, token):
    base=os.getenv('PUBLIC_BASE_URL','').rstrip('/')
    host=os.getenv('SMTP_HOST'); sender=os.getenv('SMTP_FROM')
    url=urlsplit(base)
    if not host or not sender or url.scheme!='https' or not url.netloc or url.username or url.password or url.query or url.fragment:
        raise HTTPException(503,'Password recovery email is not configured')
    message=EmailMessage(); message['From']=sender; message['To']=email; message['Subject']='Reset your OpenCode Gateway password'
    message.set_content(f'Reset your password within 30 minutes:\n{base}/#reset-password={token}\nIf you did not request this, ignore this email.')
    try:
        with smtplib.SMTP(host,int(os.getenv('SMTP_PORT','587')),timeout=15) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            if os.getenv('SMTP_USERNAME'): smtp.login(os.environ['SMTP_USERNAME'],os.getenv('SMTP_PASSWORD',''))
            smtp.send_message(message)
    except (OSError,smtplib.SMTPException):
        raise HTTPException(503,'Password recovery email could not be delivered')
