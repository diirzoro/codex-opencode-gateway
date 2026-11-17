"""Serve existing Vite/React dist assets from the bounded worker snapshot.

Reads bytes only: no dependency install, build hook, JavaScript or app process.
Every lookup stays under one dist directory with descriptor-pinned NOFOLLOW
opens. Caller retains existing owner/session/browser-lease authorization.
"""
import base64
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import stat
from urllib.parse import unquote,urlsplit

MAX_ASSET_BYTES=2*1024*1024
EXTENSIONS={'.html','.htm','.js','.mjs','.css','.json','.svg','.png','.jpg','.jpeg',
            '.gif','.webp','.ico','.woff','.woff2','.ttf','.otf','.txt','.webmanifest'}

def artifact_root(source):
    root=Path(source)/'dist'
    entry=root/'index.html'
    if root.is_symlink() or not root.is_dir() or entry.is_symlink() or not entry.is_file():
        raise ValueError('Prepared dist/index.html is required')
    return str(root)

def _read(root,parts):
    flags=os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC
    parent=os.open(root,flags|os.O_DIRECTORY)
    try:
        for component in parts[:-1]:
            child=os.open(component,flags|os.O_DIRECTORY,dir_fd=parent)
            os.close(parent);parent=child
        fd=os.open(parts[-1],flags|os.O_NONBLOCK,dir_fd=parent)
        try:
            info=os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:
                raise ValueError('Regular unlinked asset required')
            if info.st_size>MAX_ASSET_BYTES:raise OverflowError()
            with os.fdopen(os.dup(fd),'rb') as stream:
                data=stream.read(MAX_ASSET_BYTES+1)
            if len(data)>MAX_ASSET_BYTES:raise OverflowError()
            return data
        finally:os.close(fd)
    finally:os.close(parent)

def fetch(root,path):
    status=200;kind='text/plain';body=b'Not found'
    try:
        if not isinstance(path,str) or len(path)>2048 or not path.startswith('/') or path.startswith('//'):
            raise ValueError()
        parsed=urlsplit(path)
        decoded=unquote(parsed.path,errors='strict')
        if parsed.scheme or parsed.netloc or parsed.fragment or '\\' in decoded or '%' in decoded or any(ord(c)<32 or ord(c)==127 for c in decoded):
            raise ValueError()
        relative=decoded.strip('/')
        parts=relative.split('/') if relative else ['index.html']
        if any(not part or part.startswith('.') for part in parts):raise ValueError()
        extension=PurePosixPath(parts[-1]).suffix.lower()
        if extension and extension not in EXTENSIONS:raise ValueError()
        try:body=_read(root,parts)
        except (FileNotFoundError,NotADirectoryError,IsADirectoryError):
            if extension:raise
            parts=['index.html'];body=_read(root,parts)
        kind=mimetypes.guess_type(parts[-1])[0] or 'application/octet-stream'
    except OverflowError:
        status=413;body=b'Preview asset exceeds 2 MiB limit'
    except (ValueError,UnicodeError):
        status=400;body=b'Invalid preview asset path'
    except OSError:
        status=404;body=b'Not found'
    return {'status':status,'type':kind,'body':base64.b64encode(body).decode(),
            'mode':'prebuilt_static'}

def rewrite_references(body,media_type,prefix):
    """Rebase built root asset URLs under the existing short-lived ticket path."""
    if not re.fullmatch(r'/(?:preview/[A-Za-z0-9_=-]+|api/workspaces/[0-9a-f-]{36}/preview/live)/',prefix):
        raise ValueError('Invalid preview relay prefix')
    if media_type not in {'application/javascript','text/javascript','text/css'}:return body
    if len(prefix)>2100:raise ValueError('Invalid preview relay prefix')
    text=body.decode('utf-8')
    replacements=0
    def rebase(match,css=False):
        nonlocal replacements
        replacements+=1
        if replacements>512:raise ValueError('Preview reference limit exceeded')
        return 'url('+prefix+match.group(1)+')' if css else match.group(1)+prefix+match.group(2)+match.group(1)
    asset=r'[A-Za-z0-9_./-]+\.(?:m?js|css|svg|png|jpe?g|gif|webp|ico|woff2?|ttf|otf)(?:[?#][A-Za-z0-9_?=&%#./-]*)?'
    text=re.sub(r'(["\'])/('+asset+r')\1',rebase,text)
    if media_type=='text/css':
        text=re.sub(r'url\(\s*/('+asset+r')\s*\)',lambda m:rebase(m,css=True),text)
    result=text.encode('utf-8')
    if len(result)>MAX_ASSET_BYTES:raise ValueError('Preview response exceeds asset limit')
    return result
