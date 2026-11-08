"""Loopback-tolerant origin comparison for local development.

Production HTTPS origins compare strictly; only loopback aliases
(localhost / 127.0.0.1 / ::1) are treated as equivalent so a LOCAL
browser can use either spelling without breaking write/origin checks.
"""
from urllib.parse import urlsplit

_LOOPBACK_HOSTS = {'localhost', '127.0.0.1', '::1'}


def same_origin(origin, base):
    """True when `origin` matches `base` (scheme, host and port)."""
    if not origin or not base:
        return False
    o = urlsplit(origin)
    b = urlsplit(base)
    if o.scheme != b.scheme:
        return False
    o_host = o.hostname or ''
    b_host = b.hostname or ''
    same_host = (o_host == b_host) or (o_host in _LOOPBACK_HOSTS and b_host in _LOOPBACK_HOSTS)
    o_port = o.port or (443 if o.scheme == 'https' else 80)
    b_port = b.port or (443 if b.scheme == 'https' else 80)
    return same_host and o_port == b_port
