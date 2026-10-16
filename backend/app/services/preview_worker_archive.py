"""Validate untrusted Preview source archives before sandbox extraction.

This module is intended for a dedicated worker, NOT for extraction on the
Gateway host. Its successful result is necessary but not sufficient for safety.
"""
import stat
import tarfile
from pathlib import PurePosixPath

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
