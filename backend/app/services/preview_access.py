"""Short-lived browser read grants for a separately configured Preview origin.

No account cookies/keys are sent to customer code. Grants never authorize
Gateway APIs or launch/stop/write operations, and are checked against the live
login session, ownership and the current worker lease on EVERY asset request.
"""
import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import re
import uuid
from urllib.parse import urlsplit
from fastapi import HTTPException
from ..config import settings
from ..models import AuthSession, Workspace
from ..security.sessions import idle_expires_at, normal_access_ready
from . import workspaces

TTL = 300
PURPOSE = 'preview-browser-read-v1'


def _origin(value):
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment or parsed.port not in (None, 443)):
            raise ValueError()
        return 'https://' + parsed.hostname.lower()
    except (ValueError, TypeError):
        raise HTTPException(503, 'Preview requires a configured separate HTTPS origin') from None


def origins():
    gateway = _origin(settings.public_base_url)
    preview = _origin(os.environ.get('PREVIEW_PUBLIC_ORIGIN', ''))
    if urlsplit(preview).hostname == urlsplit(gateway).hostname:
        raise HTTPException(503, 'Preview origin must use a different hostname from Gateway')
    return gateway, preview


def is_preview_host(request):
    # Guard the configured hostname even on a misconfigured HTTP proxy; never
    # serve account/login/API HTML or cookies from the customer-code origin.
    value = os.environ.get('PREVIEW_PUBLIC_ORIGIN', '')
    try:
        host = urlsplit(value).hostname
        return bool(host and host != urlsplit(settings.public_base_url).hostname and request.url.hostname == host)
    except ValueError:
        return False


def _cipher():
    from cryptography.fernet import Fernet
    master = settings.credentials_encryption_key
    if not master:
        raise HTTPException(503, 'Preview browser grant encryption is not configured')
    # Separate cryptographic domain from persisted provider credentials. No
    # new production key or env secret is installed by this implementation.
    key = hmac.new(master.encode(), PURPOSE.encode(), hashlib.sha256).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def _lease(workspace):
    from .preview_runner import _worker
    from .preview_worker_client import PreviewWorkerUnavailable
    try:
        state = _worker().request('status', {'job_id': str(workspace.id)})
    except PreviewWorkerUnavailable as error:
        raise HTTPException(503, 'Preview worker status is unavailable') from error
    if state.get('state') != 'running':
        raise HTTPException(409, 'Preview is stopped; use Start Preview explicitly')
    lease = state.get('browser_lease')
    if not isinstance(lease, str) or re.fullmatch('[0-9a-f]{64}', lease) is None:
        raise HTTPException(503, 'TEST Preview Worker needs the browser-lease code update')
    return lease


def _accessible(workspace, owner):
    if (str(workspace.user_id) != str(owner) or str(workspace.project.user_id) != str(owner)
        or workspace.status in {'deleted', 'archived', 'cache_expiring', 'cache_expired'}
        or workspace.project.archived_at is not None):
        raise HTTPException(404, 'Preview is not available')


def mint(workspace, session, user, *, now=None):
    now = now or datetime.now(timezone.utc)
    gateway, preview = origins()
    if (not session or session.revoked_at is not None or idle_expires_at(session) <= now
        or str(session.user_id) != str(user.id) or not normal_access_ready(user)):
        raise HTTPException(401, 'Login again to open Preview')
    _accessible(workspace, user.id)
    expires = min(int(now.timestamp()) + TTL, int(idle_expires_at(session).timestamp()))
    data = {'purpose': PURPOSE, 'origin': preview, 'uid': str(user.id),
            'sid': str(session.id), 'wid': str(workspace.id), 'pid': str(workspace.project_id),
            'lease': _lease(workspace), 'expires': expires}
    token = _cipher().encrypt_at_time(json.dumps(data, separators=(',', ':')).encode(), int(now.timestamp())).decode()
    return {'url': preview + '/preview/' + token + '/', 'expires_at': expires,
            'gateway_origin': gateway, 'read_only': True}


def authorize(token, request, db, *, now=None):
    from cryptography.fernet import InvalidToken
    now = now or datetime.now(timezone.utc)
    gateway, preview = origins()
    if _origin(str(request.url).split('/preview/', 1)[0]) != preview:
        raise HTTPException(404, 'Not found')
    if len(token) > 2048 or not re.fullmatch('[A-Za-z0-9_=-]+', token):
        raise HTTPException(401, 'Preview access expired; refresh Preview from Workspace')
    try:
        data = json.loads(_cipher().decrypt_at_time(token.encode(), ttl=TTL, current_time=int(now.timestamp())))
        if (data['purpose'] != PURPOSE or data['origin'] != preview
            or type(data['expires']) is not int or data['expires'] <= int(now.timestamp())):
            raise ValueError()
        identifiers = {key: uuid.UUID(data[key]) for key in ('sid', 'uid', 'wid', 'pid')}
    except (InvalidToken, ValueError, TypeError, KeyError, UnicodeError):
        raise HTTPException(401, 'Preview access expired; refresh Preview from Workspace') from None
    session = db.get(AuthSession, identifiers['sid'])
    if (not session or session.revoked_at is not None or idle_expires_at(session) <= now
        or session.user_id != identifiers['uid'] or not normal_access_ready(session.user)):
        raise HTTPException(401, 'Preview login session ended; login again')
    workspace = workspaces.owned(db, Workspace, identifiers['wid'], identifiers['uid'])
    _accessible(workspace, identifiers['uid'])
    if workspace.project_id != identifiers['pid'] or not hmac.compare_digest(str(data.get('lease', '')), _lease(workspace)):
        raise HTTPException(401, 'Preview was restarted; refresh Preview from Workspace')
    return workspace, gateway, data['lease']


def install_access_log_redaction():
    """Do not emit bearer URL paths in the ASGI server's normal access log.

    The dedicated reverse proxy must independently disable/redact its access log.
    """
    import logging
    class PreviewURLFilter(logging.Filter):
        def filter(self, record):
            def redact(value):
                return re.sub(r'/preview/[^\s]+', '/preview/[redacted]', value) if isinstance(value,str) else value
            # Uvicorn's AccessFormatter unpacks the original five-tuple. Keep
            # its shape instead of rendering the message and discarding args.
            record.msg = redact(record.msg)
            if isinstance(record.args,tuple):
                record.args = tuple(redact(value) for value in record.args)
            elif isinstance(record.args,dict):
                record.args = {key:redact(value) for key,value in record.args.items()}
            return True
    logger = logging.getLogger('uvicorn.access')
    if not any(getattr(item, 'preview_redactor', False) for item in logger.filters):
        item = PreviewURLFilter();item.preview_redactor = True;logger.addFilter(item)
