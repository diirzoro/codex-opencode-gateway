"""Verified login identities; repository authorization stays in the GitHub App flow."""
import base64
import hashlib
import json
import secrets
import time
from urllib.parse import urlencode, urlsplit
import httpx
import jwt
from fastapi import HTTPException
from ..config import settings
from . import credentials, github

FLOW_COOKIE = 'gateway_login_flow'
SIGNUP_COOKIE = 'gateway_login_signup'
TTL = 600

def available(provider):
    base=urlsplit(settings.public_base_url)
    if (base.scheme != 'https' and not (base.scheme=='http' and base.hostname in {'127.0.0.1','localhost','::1'})) or base.username or base.password or base.query or base.fragment:
        return False
    if not credentials.available(): return False
    if provider == 'github': return bool(settings.github_client_id and settings.github_client_secret)
    if provider == 'google': return bool(settings.google_client_id and settings.google_client_secret)
    return False

def callback_url(provider):
    return settings.public_base_url + '/api/auth/social/' + provider + '/callback'

def seal(value):
    return credentials.encrypt(json.dumps({**value, 'expires': int(time.time()) + TTL}))

def unseal(raw, purpose):
    try:
        value = json.loads(credentials.decrypt(raw or ''))
        if value.get('purpose') != purpose or value['expires'] <= time.time(): raise ValueError()
        return value
    except Exception:
        raise HTTPException(400, 'Login authorization expired or invalid; start again')

def begin(provider, session=None):
    if not available(provider): raise HTTPException(503, 'This sign-in provider is not configured on this server')
    state, verifier, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(64), secrets.token_urlsafe(32)
    value = {'purpose':'login', 'provider':provider, 'state':state, 'verifier':verifier, 'nonce':nonce,
             'session_id':str(session.id) if session else None, 'user_id':str(session.user_id) if session else None}
    params = {'client_id':settings.github_client_id if provider == 'github' else settings.google_client_id,
              'redirect_uri':callback_url(provider), 'state':state, 'response_type':'code',
              'code_challenge':base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='),
              'code_challenge_method':'S256'}
    if provider == 'github':
        # Login identity only; never install or grant repository access here.
        url = settings.github_web_base + '/login/oauth/authorize'
        params['scope'] = 'read:user user:email'
    else:
        url = 'https://accounts.google.com/o/oauth2/v2/auth'
        params.update(scope='openid email profile', nonce=nonce)
    return url + '?' + urlencode(params), seal(value)

def identity(provider, code, flow):
    if not available(provider): raise HTTPException(503, 'Sign-in is not configured')
    if provider == 'github':
        token = github.exchange_code(code, callback_url(provider), flow['verifier'])
        info = github._api('GET', '/user', token=token['access_token']) or {}
        emails = github._api('GET', '/user/emails', token=token['access_token']) or []
        email = next((row.get('email') for row in emails if row.get('verified') is True and row.get('primary') is True), None)
        subject = str(info.get('id') or '')
    else:
        try:
            with httpx.Client(timeout=20, follow_redirects=False) as client:
                response = client.post('https://oauth2.googleapis.com/token', data={
                    'client_id':settings.google_client_id, 'client_secret':settings.google_client_secret,
                    'code':code, 'code_verifier':flow['verifier'], 'grant_type':'authorization_code',
                    'redirect_uri':callback_url(provider)})
                token = response.json().get('id_token') if response.status_code == 200 else None
            if not token: raise ValueError()
            key = jwt.PyJWKClient('https://www.googleapis.com/oauth2/v3/certs', timeout=20).get_signing_key_from_jwt(token).key
            info = jwt.decode(token, key, algorithms=['RS256'], audience=settings.google_client_id,
                              issuer=['https://accounts.google.com','accounts.google.com'],
                              options={'require':['exp','iat','iss','aud','sub','nonce','email','email_verified']})
            if (not secrets.compare_digest(info['nonce'], flow['nonce']) or info['email_verified'] is not True
                or info.get('azp', settings.google_client_id) != settings.google_client_id): raise ValueError()
            subject, email = info['sub'], info['email']
        except Exception:
            raise HTTPException(403, 'Google identity could not be verified')
    if not subject or len(subject) > (100 if provider == 'github' else 255) or not isinstance(email, str):
        raise HTTPException(403, 'A verified primary email is required for sign-in')
    from pydantic import TypeAdapter, EmailStr
    try: email = str(TypeAdapter(EmailStr).validate_python(email)).lower()
    except ValueError: raise HTTPException(403, 'Verified sign-in email is invalid')
    return {'purpose':'signup', 'provider':provider, 'subject':subject, 'email':email}
