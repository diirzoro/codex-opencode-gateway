#!/usr/bin/env python3
"""Read-only GitHub config preflight. Run as the service user with its environment.

Print names and status only, never values, paths, PEM, tokens or exceptions.
No GitHub requests, database changes, service restart or key generation.
"""
import os
import stat
import sys
from pathlib import Path
from urllib.parse import urlparse


def main():
    failed = False

    def result(name, valid, reason='MISSING OR INVALID'):
        nonlocal failed
        print(name + ': ' + ('OK' if valid else reason))
        failed |= not valid

    value = lambda name: os.environ.get(name, '').strip()
    for name in ('GITHUB_APP_ID', 'GITHUB_APP_SLUG', 'GITHUB_CLIENT_ID',
                 'GITHUB_CLIENT_SECRET', 'CREDENTIALS_ENCRYPTION_KEY'):
        present = bool(value(name))
        if name == 'GITHUB_APP_ID':
            present = present and value(name).isdigit() and int(value(name)) > 0
        result(name, present)

    base = value('PUBLIC_BASE_URL').rstrip('/')
    try:
        origin = urlparse(base)
        valid_origin = (origin.scheme == 'https' and bool(origin.hostname)
                        and origin.username is None and origin.password is None
                        and not origin.path and not origin.query and not origin.fragment)
        _ = origin.port
    except ValueError:
        valid_origin = False
    result('PUBLIC_BASE_URL', valid_origin)
    callback = (value('GITHUB_CALLBACK_URL') if 'GITHUB_CALLBACK_URL' in os.environ
                else base + '/api/github/callback')
    result('GITHUB_CALLBACK_URL', valid_origin and callback == base + '/api/github/callback')

    inline = value('GITHUB_APP_PRIVATE_KEY')
    key_path = value('GITHUB_APP_PRIVATE_KEY_PATH')
    key = None
    if inline:
        key = inline.encode()
        print('GITHUB_APP_PRIVATE_KEY_PATH: NOT USED (INLINE KEY TAKES PRECEDENCE)')
    elif key_path:
        try:
            path = Path(key_path)
            root = Path('/home/tahir/opencode-gateway').resolve()
            safe = (path.is_absolute() and not path.is_symlink()
                    and not path.resolve().is_relative_to(root)
                    and path.is_file() and path.stat().st_uid == os.geteuid()
                    and stat.S_IMODE(path.stat().st_mode) == 0o600)
            result('GITHUB_APP_PRIVATE_KEY_PATH', safe,
                   'MISSING, UNSAFE LOCATION/OWNER/MODE, OR UNREADABLE')
            if safe:
                key = path.read_bytes()
        except (OSError, ValueError):
            result('GITHUB_APP_PRIVATE_KEY_PATH', False, 'UNREADABLE')
    else:
        result('GITHUB_APP_PRIVATE_KEY_PATH', False, 'MISSING (NO INLINE ALTERNATIVE)')

    signing_key_valid = False
    if key:
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            signing_key_valid = isinstance(
                serialization.load_pem_private_key(key, password=None), rsa.RSAPrivateKey)
        except Exception:
            pass
    result('GITHUB_APP_PRIVATE_KEY (EFFECTIVE PEM)', signing_key_valid)

    webhook_required = '--require-webhook' in sys.argv[1:]
    if webhook_required:
        result('GITHUB_WEBHOOK_SECRET', bool(value('GITHUB_WEBHOOK_SECRET')))
    else:
        print('GITHUB_WEBHOOK_SECRET: ' +
              ('PRESENT' if value('GITHUB_WEBHOOK_SECRET') else 'ABSENT (OPTIONAL IF WEBHOOKS DISABLED)'))
    for name in ('GITHUB_API_BASE', 'GITHUB_WEB_BASE'):
        valid = name not in os.environ or bool(value(name))
        result(name, valid, 'EMPTY OVERRIDE; OMIT FOR GITHUB.COM DEFAULT')

    print('LOCAL CONFIG CHECK: ' + ('FAIL' if failed else 'PASS'))
    print('This does not verify GitHub identity, permissions, installation, OAuth, or network access.')
    return 1 if failed else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        print('LOCAL CONFIG CHECK: FAIL (NO VALUES DISPLAYED)')
        raise SystemExit(1) from None
