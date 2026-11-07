"""Bounded source export for a future isolated runner; never executes code.

Caller provides a trusted binary spool, not a customer destination path. The
runner must mount the resulting snapshot read-only and validate archive members
again. Nothing here enables preview execution or installs dependencies.
"""
import io
import os
import stat
import tarfile
from fastapi import HTTPException
from . import workspaces

MAX_BYTES = 50 * 1024 * 1024
MAX_FILES = 10000
MAX_ENTRIES = 20000
MAX_DEPTH = 32
EXCLUDED = {'.git', '.ssh', '.aws', '.azure', '.config', 'node_modules', '.venv',
            'venv', '__pycache__', '.next', 'vendor', 'opencode.json', 'opencode.jsonc'}


def private(name):
    lower = name.lower()
    return (lower in EXCLUDED or lower.startswith('.env') or
            lower.endswith(('.pem', '.key', '.p12', '.pfx')))


def export(workspace, output):
    """POSIX descriptor-pinned export, fail closed on links/special files/races.

    Counts actual bytes read (not just stat); rejects changing files. Caller must
    discard the spool on any exception. Credentials are never injected into it.
    """
    if os.name != 'posix' or not hasattr(os, 'O_NOFOLLOW'):
        raise HTTPException(503, 'Secure preview snapshot export is unavailable')
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    count = total = entries = 0
    root = workspaces.root_for(workspace)
    try:
        rootfd = os.open(root, flags | os.O_DIRECTORY)
        try:
            with tarfile.open(fileobj=output, mode='w|', format=tarfile.PAX_FORMAT) as archive:
                def walk(directory, prefix='', depth=0):
                    nonlocal count, total, entries
                    if depth > MAX_DEPTH:
                        raise HTTPException(413, 'Preview source exceeds directory depth limit')
                    for entry in os.scandir(directory):
                        name = entry.name
                        entries += 1
                        if entries > MAX_ENTRIES:
                            raise HTTPException(413, 'Preview source has too many entries')
                        if private(name): continue
                        if name in {'.', '..'} or '/' in name or '\\' in name:
                            raise HTTPException(403, 'Unsafe preview source name')
                        fd = os.open(name, flags | os.O_NONBLOCK, dir_fd=directory)
                        try:
                            before = os.fstat(fd)
                            relative = prefix + name
                            if stat.S_ISDIR(before.st_mode):
                                walk(fd, relative + '/', depth + 1)
                            elif stat.S_ISREG(before.st_mode) and before.st_nlink == 1:
                                count += 1
                                if count > MAX_FILES or before.st_size > MAX_BYTES-total:
                                    raise HTTPException(413, 'Preview source exceeds snapshot quota')
                                # Bounded read detects growth without blocking on special files.
                                with os.fdopen(os.dup(fd), 'rb') as source:
                                    content = source.read(min(before.st_size + 1, MAX_BYTES-total + 1))
                                after = os.fstat(fd)
                                if (len(content) != before.st_size or
                                        (before.st_size, before.st_mtime_ns, before.st_ctime_ns) !=
                                        (after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
                                    raise HTTPException(409, 'Project changed during snapshot; retry when idle')
                                total += len(content)
                                entry = tarfile.TarInfo(relative)
                                entry.size = len(content); entry.mode = 0o444
                                entry.uid = entry.gid = 0; entry.mtime = 0
                                archive.addfile(entry, io.BytesIO(content))
                            else:
                                raise HTTPException(403, 'Links and special files cannot enter a preview snapshot')
                        finally: os.close(fd)
                walk(rootfd)
        finally: os.close(rootfd)
    except OSError:
        raise HTTPException(403, 'Preview source is missing, unsafe or changed during export') from None
    return {'files': count, 'bytes': total}
