"""Send existing Gateway mail via saved provider settings; no daemon or mail queue."""
import smtplib
import ssl
from email.utils import formataddr
import httpx
from fastapi import HTTPException

BREVO_URL = 'https://api.brevo.com/v3/smtp/email'
RESEND_SEND_URL = 'https://api.resend.com/emails'
DEFAULT_SENDER = 'no-reply@opencode-gateway.codes'
DEFAULT_NAME = 'OpenCode Gateway'
DEFAULT_REPLY_TO = 'support@opencode-gateway.codes'
PROVIDERS = ('resend', 'brevo')


def _transport_provider(config):
    # Old TEST/LIVE .env values stored Resend SMTP credentials without a
    # provider label. Resend's API key works over HTTPS; never accidentally
    # fall back to outbound SMTP just because that label is absent.
    selected = config.get('provider')
    if selected:
        return selected
    if (config.get('smtp_host') or '').strip().lower() == 'smtp.resend.com' and (config.get('smtp_username') or '').strip().lower() == 'resend':
        return 'resend'
    return 'legacy_smtp'


def ready(config):
    provider = _transport_provider(config)
    if provider == 'brevo':
        return bool(config.get('api_key') and config.get('smtp_from'))
    if provider == 'resend':
        return bool(config.get('smtp_from') and config.get('smtp_password'))
    # Historical non-Resend SMTP remains supported without changing the
    # configuration of unrelated deployments.
    return all(config.get(key) for key in ('smtp_host', 'smtp_from', 'smtp_username', 'smtp_password'))


def public_config(config):
    provider = _transport_provider(config)
    return {'provider': provider, 'configured': ready(config),
            'sender': config.get('smtp_from') or DEFAULT_SENDER,
            'sender_name': config.get('sender_name') or DEFAULT_NAME,
            'reply_to': DEFAULT_REPLY_TO,
            'transport': 'https' if provider in ('brevo', 'resend') else 'smtp',
            'smtp_host': BREVO_URL if provider == 'brevo' else config.get('smtp_host', 'smtp.resend.com'),
            'smtp_port': None if provider == 'brevo' else config.get('smtp_port', 587),
            'smtp_username': '' if provider == 'brevo' else config.get('smtp_username', 'resend')}


def send(config, message, *, error_status=502, timeout=15):
    provider = _transport_provider(config)
    if not ready(config):
        hint = ('Resend sending key and sender address must be configured by an administrator'
                if provider == 'resend' else 'Email delivery is not configured')
        raise HTTPException(503, hint)
    if 'Reply-To' not in message:message['Reply-To']=DEFAULT_REPLY_TO
    if provider == 'resend':
        # Resend HTTPS API uses the same provider API key as SMTP, but only
        # requires outbound HTTPS (443), not SMTP 587 which some VPSs block.
        sender = formataddr((config.get('sender_name') or DEFAULT_NAME, config['smtp_from']))
        payload = {'from': sender, 'to': [str(message['To'])],
                   'subject': str(message['Subject']), 'text': message.get_content(),
                   'reply_to': str(message.get('Reply-To') or DEFAULT_REPLY_TO)}
        try:
            with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
                response = client.post(RESEND_SEND_URL, headers={
                    'Authorization': 'Bearer ' + config['smtp_password'],
                    'Content-Type': 'application/json',
                }, json=payload)
        except httpx.HTTPError:
            raise HTTPException(error_status,
                'Resend HTTPS connection failed; delivery is unconfirmed. No automatic retry was made') from None
        if response.status_code not in (200, 201):
            category = {
                401: 'Resend rejected the API key (HTTP 401)',
                403: 'Resend API key lacks permission or sender domain is unauthorized (HTTP 403)',
                422: 'Resend rejected the sender or recipient; verify sending domain and sender address (HTTP 422)',
                429: 'Resend rate limit reached (HTTP 429)',
            }.get(response.status_code, 'Resend rejected delivery request (HTTP ' + str(response.status_code) + ')')
            raise HTTPException(error_status, category)
        try:
            accepted = bool(response.json().get('id'))
        except (ValueError, AttributeError, TypeError):
            accepted = False
        if not accepted:
            raise HTTPException(error_status,
                'Resend did not confirm acceptance; do not resend automatically')
        return
    if provider == 'brevo':
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
