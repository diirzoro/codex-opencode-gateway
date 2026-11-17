"""Fetch public, integrity-locked npm archives; never execute or unpack them.

This runs only on an explicit Preview request, outside the network-disconnected
execution worker. No customer source or credentials are sent to a registry.
"""
import base64
import hashlib
import hmac
import io
import json
import os
import re
import stat
import tarfile
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

MAX_PACKAGE = 8 * 1024 * 1024
MAX_TOTAL = 20 * 1024 * 1024
MAX_PACKAGES = 250
MAX_CACHE = 128 * 1024 * 1024
INTEGRITY = re.compile(r'^sha512-([A-Za-z0-9+/]{86}==)$')

class PackagePreparationError(ValueError):
    pass

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PackagePreparationError('Package redirects are not allowed')

def digest_for(integrity):
    match=INTEGRITY.fullmatch(integrity) if isinstance(integrity,str) else None
    if not match:raise PackagePreparationError('SHA-512 locked packages are required')
    return base64.b64decode(match[1],validate=True)

def validate_url(url):
    if not isinstance(url,str) or len(url)>1024 or any(ord(ch)<33 or ord(ch)==127 for ch in url):raise PackagePreparationError('Unsupported package URL')
    try:parsed=urlsplit(url)
    except ValueError as exc:raise PackagePreparationError('Unsupported package URL') from exc
    if (parsed.scheme!='https' or parsed.netloc!='registry.npmjs.org' or parsed.query
        or parsed.fragment or not re.fullmatch(r'/[@A-Za-z0-9_.%/+-]+/-/[A-Za-z0-9_.+-]+\.tgz',parsed.path)
        or '..' in parsed.path or '//' in parsed.path or '%' in parsed.path):
        raise PackagePreparationError('Only public npm registry tarballs are supported')
    return url

def locked_packages(lock):
    if not isinstance(lock,dict) or lock.get('lockfileVersion') not in {2,3} or not isinstance(lock.get('packages'),dict):
        raise PackagePreparationError('A version 2 or 3 package-lock.json is required')
    result=[];seen=set()
    for name,item in lock['packages'].items():
        if name=='':continue
        if (not isinstance(name,str) or not name.startswith('node_modules/')
            or any(part in {'','.','..'} for part in name.split('/')) or '\\' in name
            or not isinstance(item,dict) or item.get('link')):
            raise PackagePreparationError('Local and workspace package links are not supported')
        # npm will ignore these optional packages on the fixed Linux x64 image.
        supported=True
        for key,target in [('os','linux'),('cpu','x64')]:
            choices=item.get(key)
            if isinstance(choices,list) and (('!'+target) in choices or
                (any(isinstance(v,str) and not v.startswith('!') for v in choices) and target not in choices)):
                supported=False
        if not supported:
            if item.get('optional') is not True:raise PackagePreparationError('Unsupported required package platform')
            continue
        if item.get('inBundle') is True:continue
        url=validate_url(item.get('resolved'));integrity=item.get('integrity');digest_for(integrity)
        if integrity not in seen:
            seen.add(integrity);result.append((url,integrity))
        if len(result)>MAX_PACKAGES:raise PackagePreparationError('Too many preview build packages')
    return result

def lock_from_snapshot(snapshot):
    try:
        with tarfile.open(fileobj=io.BytesIO(snapshot),mode='r:') as archive:
            entry=archive.getmember('package-lock.json')
            if not entry.isfile() or entry.size>2*1024*1024:raise PackagePreparationError('Invalid dependency lockfile')
            with archive.extractfile(entry) as stream:return json.load(stream)
    except (KeyError,ValueError,tarfile.TarError,UnicodeError) as exc:
        raise PackagePreparationError('A valid package-lock.json is required for automatic preview builds') from exc

def _cache_root():
    root=Path(tempfile.gettempdir())/'pi-preview-public-npm-cache'
    root.mkdir(mode=0o700,exist_ok=True)
    if root.is_symlink() or not root.is_dir():raise PackagePreparationError('Public package cache is unavailable')
    return root

def _cached(root,key,expected):
    try:
        fd=os.open(root/key,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd,'rb') as stream:
            info=os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>MAX_PACKAGE:return None
            body=stream.read(MAX_PACKAGE+1)
        if hmac.compare_digest(hashlib.sha512(body).digest(),expected):return body
    except OSError:pass
    return None

def _fetch(item,root,deadline):
    url,integrity=item;expected=digest_for(integrity)
    key=hashlib.sha256(expected).hexdigest()
    cached=_cached(root,key,expected)
    if cached is not None:return integrity,cached
    remaining=deadline-time.monotonic()
    if remaining<=0:raise PackagePreparationError('Package preparation time limit exceeded')
    try:
        with build_opener(NoRedirect()).open(Request(url,headers={'User-Agent':'Pi-Preview-Package-Cache/1'}),timeout=min(8,remaining)) as response:
            if response.status!=200:raise PackagePreparationError('Public package download failed')
            body=response.read(MAX_PACKAGE+1)
    except OSError as exc:raise PackagePreparationError('Public package download is unavailable') from exc
    if len(body)>MAX_PACKAGE or not hmac.compare_digest(hashlib.sha512(body).digest(),expected):
        raise PackagePreparationError('Package size or SHA-512 integrity check failed')
    fd,path=tempfile.mkstemp(prefix='part-',dir=root)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(body)
        os.replace(path,root/key)
    finally:Path(path).unlink(missing_ok=True)
    return integrity,body

def prepare(snapshot,*,cache_root=None):
    packages=locked_packages(lock_from_snapshot(snapshot));root=Path(cache_root) if cache_root is not None else _cache_root()
    # Only immutable public archives are shared. No project output is cached here.
    files=[];size=0
    for file in root.iterdir():
        if re.fullmatch('[0-9a-f]{64}',file.name) and not file.is_symlink():
            info=file.stat();files.append((info.st_mtime,file,info.st_size));size+=info.st_size
    remaining_files=len(files)
    for modified,file,length in sorted(files):
        if size<=MAX_CACHE and remaining_files<=512 and time.time()-modified<86400:break
        file.unlink(missing_ok=True);size-=length;remaining_files-=1
    result=[];total=0;deadline=time.monotonic()+30
    with ThreadPoolExecutor(max_workers=4) as pool:
        for offset in range(0,len(packages),4):
            for integrity,body in pool.map(lambda item:_fetch(item,root,deadline),packages[offset:offset+4]):
                total+=len(body)
                if total>MAX_TOTAL:raise PackagePreparationError('Preview dependency cache exceeds 20 MiB')
                result.append({'integrity':integrity,'body':base64.b64encode(body).decode('ascii')})
    return result

def stage(packages,directory):
    """Worker-side verification before staging opaque tgz files for the sandbox."""
    if not isinstance(packages,list) or len(packages)>MAX_PACKAGES:raise PackagePreparationError('Invalid package cache')
    directory.mkdir(mode=0o755)
    total=0
    for index,item in enumerate(packages):
        if not isinstance(item,dict):raise PackagePreparationError('Invalid package cache entry')
        expected=digest_for(item.get('integrity'))
        try:body=base64.b64decode(item['body'],validate=True)
        except (KeyError,ValueError,TypeError) as exc:raise PackagePreparationError('Invalid package bytes') from exc
        total+=len(body)
        if len(body)>MAX_PACKAGE or total>MAX_TOTAL or not hmac.compare_digest(hashlib.sha512(body).digest(),expected):
            raise PackagePreparationError('Invalid package integrity or quota')
        path=directory/f'{index:04d}.tgz';path.write_bytes(body);path.chmod(0o644)
