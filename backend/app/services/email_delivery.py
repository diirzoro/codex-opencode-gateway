"""Send existing Gateway mail via saved provider settings; no daemon or mail queue."""
import smtplib
import ssl
from email.utils import formataddr
import httpx
from fastapi import HTTPException

BREVO_URL = 'https://api.brevo.com/v3/smtp/email'
DEFAULT_SENDER = 'support@opencode-gateway.codes'
DEFAULT_NAME = 'OpenCode Gateway'
PROVIDERS = ('resend', 'brevo')


def ready(config):
    if config.get('provider') == 'brevo':
        return bool(config.get('api_key') and config.get('smtp_from'))
    return all(config.get(key) for key in ('smtp_host', 'smtp_from', 'smtp_username', 'smtp_password'))


def public_config(config):
    provider = config.get('provider', 'resend')
    return {'provider': provider, 'configured': ready(config),
            'sender': config.get('smtp_from') or DEFAULT_SENDER,
            'sender_name': config.get('sender_name') or DEFAULT_NAME,
            'transport': 'https' if provider == 'brevo' else 'smtp',
            'smtp_host': BREVO_URL if provider == 'brevo' else config.get('smtp_host', 'smtp.resend.com'),
            'smtp_port': None if provider == 'brevo' else config.get('smtp_port', 587),
            'smtp_username': '' if provider == 'brevo' else config.get('smtp_username', 'resend')}


def send(config, message, *, error_status=502, timeout=15):
    if not ready(config):
        raise HTTPException(503, 'Email delivery is not configured')
    if config.get('provider') == 'brevo':
        sender={'email':config['smtp_from'], 'name':config.get('sender_name') or DEFAULT_NAME}
        payload={'sender':sender,'to':[{'email':str(message['To'])}],
                 'subject':str(message['Subject']),'textContent':message.get_content()}
        try:
            with httpx.Client(timeout=timeout, follow_redirects=False) as client:
                response=client.post(BREVO_URL, headers={'api-key':config['api_key'],'accept':'application/json'}, json=payload)
        except httpx.HTTPError:
            raise HTTPException(error_status,'Brevo request failed; delivery is unconfirmed. No automatic retry was made') from None
        if response.status_code not in (200,201):
            reason = 'Brevo rejected the request; verify API key and sender authorization'
            if response.status_code == 429:reason='Brevo rate limit reached; delivery was not confirmed'
            raise HTTPException(error_status,reason)
        try:accepted=bool(response.json().get('messageId'))
        except (ValueError,AttributeError):accepted=False
        if not accepted:raise HTTPException(error_status,'Brevo did not confirm message acceptance')
        return
    if config.get('sender_name'):
        message.replace_header('From',formataddr((config['sender_name'],config['smtp_from'])))
    try:
        with smtplib.SMTP(config['smtp_host'],int(config.get('smtp_port',587)),timeout=timeout) as client:
            client.starttls(context=ssl.create_default_context())
            client.login(config['smtp_username'],config['smtp_password'])
            client.send_message(message)
    except (OSError,smtplib.SMTPException,ValueError):
        raise HTTPException(error_status,'SMTP rejected or could not send the email; delivery is unconfirmed') from None
