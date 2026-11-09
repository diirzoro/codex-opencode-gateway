#!/usr/bin/env python3
"""Deploy changed TEST source files only. No service or infrastructure actions."""
import argparse
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile

ROOT = Path("/home/tahir/opencode-gateway-test")
PI_TARGET = Path("/home/tahir/pi-test/pi-central.mjs")

# Only source files tracked by the reviewed commit are copied. Ignore runtime
# data, user workspaces, secrets, generated artifacts and Git metadata.
SKIP_DIRS = {
    ".git", ".github", ".venv", "node_modules", "workspaces",
    "runtime", "releases", "__pycache__", ".pytest_cache",
    "tests", "test", "__tests__", "screenshots", "screenshot",
    "test-results", "playwright-report",
}
SKIP_SUFFIXES = (".pyc", ".pyo", ".log")


def git(*args):
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=90,
    ).stdout


def source_paths(revision):
    names = []
    for name in git("ls-tree", "-r", "--name-only", revision).decode().splitlines():
        parts = PurePosixPath(name).parts
        if not parts or any(part in SKIP_DIRS for part in parts):
            continue
        if name in {".env", "runtime.env", "native-release.env"}:
            continue
        if name.endswith(SKIP_SUFFIXES):
            continue
        names.append(name)
    if "integration/pi-central.mjs" not in names or "backend/app/main.py" not in names:
        raise RuntimeError("Required existing TEST project source is missing")
    return names


def safe_file(path):
    if not path.is_relative_to(ROOT) and path != PI_TARGET:
        raise RuntimeError("Destination outside the approved TEST source locations")
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise RuntimeError(f"Unsafe destination: {path}")
    boundary = ROOT if path.is_relative_to(ROOT) else PI_TARGET.parent
    parent = path.parent
    while parent != boundary:
        if parent.is_symlink():
            raise RuntimeError(f"Symlink in destination path: {parent}")
        parent = parent.parent
    if boundary.is_symlink():
        raise RuntimeError("Source root is a symlink")


def overwrite_if_changed(path, data):
    safe_file(path)
    if path.is_file() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.stat() if path.exists() else None
    if existing and existing.st_uid != os.geteuid():
        raise RuntimeError(f"File is not owned by current deploy user: {path}")
    fd, tmp = tempfile.mkstemp(prefix=".deploy-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.chmod(tmp, stat.S_IMODE(existing.st_mode) if existing else 0o644)
        os.replace(tmp, path)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["deploy"])
    parser.add_argument("sha")
    args = parser.parse_args()

    if os.geteuid() == 0 or Path.cwd() != ROOT:
        raise RuntimeError("Run as the existing TEST account from its project directory")
    if not re.fullmatch(r"[0-9a-f]{40}", args.sha):
        raise RuntimeError("Invalid commit SHA")
    if not (ROOT / ".git").is_dir():
        raise RuntimeError("The existing TEST project checkout was not found")
    if git("cat-file", "-t", args.sha).strip() != b"commit":
        raise RuntimeError("Unknown commit")
    git("merge-base", "--is-ancestor", args.sha, "origin/updates")

    changed = 0
    for name in source_paths(args.sha):
        path = ROOT / name
        data = git("show", f"{args.sha}:{name}")
        if overwrite_if_changed(path, data):
            changed += 1
            print("UPDATED", name, flush=True)

    # Update the *existing* Pi Central source file, never create a second Pi
    # runtime/service. Activation/restart belongs to the VPS terminal, not CI.
    if not PI_TARGET.is_file():
        raise RuntimeError("Existing Pi Central source file is missing")
    pi_source = (ROOT / "integration/pi-central.mjs").read_bytes()
    pi_updated = overwrite_if_changed(PI_TARGET, pi_source)
    if pi_updated:
        print("PI_SOURCE_UPDATED_NO_RESTART", flush=True)

    print("FILES_UPDATED", changed, "PI_SOURCE_UPDATED", pi_updated, flush=True)
    print("DEPLOY_FILES_ONLY_COMPLETE", args.sha, flush=True)


if __name__ == "__main__":
    main()
