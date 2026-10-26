"""Send existing Gateway mail via saved provider settings; no daemon or mail queue."""
import smtplib
import ssl
from email.utils import formataddr
import httpx
from fastapi import HTTPException

BREVO_URL = 'https://api.brevo.com/v3/smtp/email'
DEFAULT_SENDER = 'no-reply@opencode-gateway.codes'
DEFAULT_NAME = 'OpenCode Gateway'
DEFAULT_REPLY_TO = 'support@opencode-gateway.codes'
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
            'reply_to': DEFAULT_REPLY_TO,
            'transport': 'https' if provider == 'brevo' else 'smtp',
            'smtp_host': BREVO_URL if provider == 'brevo' else config.get('smtp_host', 'smtp.resend.com'),
            'smtp_port': None if provider == 'brevo' else config.get('smtp_port', 587),
            'smtp_username': '' if provider == 'brevo' else config.get('smtp_username', 'resend')}


def send(config, message, *, error_status=502, timeout=15):
    if not ready(config):
        raise HTTPException(503, 'Email delivery is not configured')
    if 'Reply-To' not in message:message['Reply-To']=DEFAULT_REPLY_TO
    if config.get('provider') == 'brevo':
        sender={'email':config['smtp_from'], 'name':config.get('sender_name') or DEFAULT_NAME}
        payload={'sender':sender,'to':[{'email':str(message['To'])}],
                 'subject':str(message['Subject']),'textContent':message.get_content(),
                 'replyTo':{'email':DEFAULT_REPLY_TO}}
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


def read_resend(path, key):
    """Read fixed Resend endpoints; distinguish credentials from transport errors."""
    import json
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
    import re
    if not re.fullmatch(r'/emails(?:/receiving)?(?:/[0-9a-f-]{36})?(?:\?limit=(?:1|50))?', path):
        raise ValueError('Unsupported Resend read endpoint')
    request=Request('https://api.resend.com'+path,headers={'Authorization':'Bearer '+key,'Accept':'application/json'})
    try:
        with urlopen(request,timeout=10) as response:payload=json.load(response)
    except HTTPError as error:
        if error.code in (401,403):
            raise HTTPException(502,f'Resend refused mailbox access (HTTP {error.code}). Sending access cannot read email. Save a valid Resend Full access key in Connection diagnostics; the sending key remains unchanged.') from None
        if error.code==429:raise HTTPException(503,'Resend mailbox rate limit reached (HTTP 429). Try again later; no automatic retry was made') from None
        if error.code==404:raise HTTPException(404,'Resend email resource was not found (HTTP 404)') from None
        raise HTTPException(502,f'Resend mailbox request failed (HTTP {error.code}); no permission verdict was made') from None
    except (URLError,TimeoutError,OSError):
        raise HTTPException(502,'Cannot connect to Resend mailbox API. Check server connectivity; this does not prove the API key is invalid') from None
    except ValueError:
        raise HTTPException(502,'Resend mailbox API returned an invalid response') from None
    if not isinstance(payload,dict) or ('?limit=' in path and not isinstance(payload.get('data'),list)):raise HTTPException(502,'Resend mailbox API returned an invalid response')
    return payload
