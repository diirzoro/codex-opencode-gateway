"""Validate untrusted Preview source archives before sandbox extraction.

This module is intended for a dedicated worker, NOT for extraction on the
Gateway host. Its successful result is necessary but not sufficient for safety.
"""
import os
import stat
import tarfile
from pathlib import Path, PurePosixPath

MAX_FILES = 10000
MAX_UNPACKED_BYTES = 50 * 1024 * 1024
MAX_DEPTH = 32


class UnsafePreviewArchive(ValueError):
    pass


def validate_archive(archive: tarfile.TarFile) -> tuple[int, int]:
    """Reject traversal, links, duplicate paths, special files and over-quota input.

    Seekable trusted-size-bounded spool required; caller must also enforce the
    *compressed/archive byte count* when receiving a snapshot.
    """
    seen = set()
    total = 0
    count = 0
    for member in archive:
        name = member.name
        path = PurePosixPath(name)
        if (not name or name.startswith("/") or "\\" in name or
                any(part in ("", ".", "..") for part in name.split("/")) or
                len(path.parts) > MAX_DEPTH or path.is_absolute()):
            raise UnsafePreviewArchive("Unsafe archive member path")
        if path.parts[0].startswith(".") or any(
                part.startswith(".env") or part in (".git", ".ssh", ".aws", "node_modules", ".venv")
                for part in path.parts):
            raise UnsafePreviewArchive("Private or generated files cannot enter Preview")
        canonical = str(path)
        if canonical in seen:
            raise UnsafePreviewArchive("Duplicate archive member")
        seen.add(canonical)
        if not member.isfile() or member.issym() or member.islnk():
            raise UnsafePreviewArchive("Only regular files may enter Preview")
        if member.size < 0 or member.size > MAX_UNPACKED_BYTES - total:
            raise UnsafePreviewArchive("Archive exceeds size limit")
        count += 1
        if count > MAX_FILES:
            raise UnsafePreviewArchive("Archive exceeds file limit")
        total += member.size
    return count, total


def extract_into_sandbox(archive: tarfile.TarFile, destination: Path) -> tuple[int, int]:
    """Extract only regular validated files into an empty, worker-owned directory.

    Only call inside an already isolated worker with an exclusively owned,
    freshly created directory. Never pass a Gateway/host workspace directory.
    Use directory-fd relative opens with NOFOLLOW to reject symlink races.
    """
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        raise UnsafePreviewArchive("Secure sandbox extraction requires POSIX")
    count, total = validate_archive(archive)
    destination = Path(destination)
    root_fd = os.open(destination, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if os.listdir(root_fd):
            raise UnsafePreviewArchive("Sandbox destination must be empty")
        for member in archive.getmembers():
            components = member.name.split("/")
            parent_fd = os.dup(root_fd)
            try:
                for component in components[:-1]:
                    try:
                        os.mkdir(component, 0o700, dir_fd=parent_fd)
                    except FileExistsError:
                        pass
                    next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY |
                                      os.O_NOFOLLOW, dir_fd=parent_fd)
                    os.close(parent_fd)
                    parent_fd = next_fd
                fd = os.open(components[-1], os.O_WRONLY | os.O_CREAT |
                             os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
                try:
                    source = archive.extractfile(member)
                    if source is None:
                        raise UnsafePreviewArchive("Archive payload missing")
                    remaining = member.size
                    with source:
                        while remaining:
                            chunk = source.read(min(65536, remaining))
                            if not chunk:
                                raise UnsafePreviewArchive("Truncated archive member")
                            view = memoryview(chunk)
                            while view:
                                written = os.write(fd, view)
                                view = view[written:]
                            remaining -= len(chunk)
                finally:
                    os.close(fd)
            finally:
                os.close(parent_fd)
    finally:
        os.close(root_fd)
    return count, total
