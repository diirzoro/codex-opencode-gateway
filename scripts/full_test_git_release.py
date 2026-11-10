#!/usr/bin/env python3
"""TEST deploy: sync changed files, prune retired source, migrate if needed, restart changed processes."""
import argparse
import fcntl
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile

ROOT = Path("/home/tahir/opencode-gateway-test")
PI_TARGET = Path("/home/tahir/pi-test/pi-central.mjs")
REVISION = ROOT / ".test-full-release-revision"
LOCK = Path("/home/tahir/.gateway-test-deploy.lock")
GATE = "/usr/local/sbin/opencode-gateway-test-migrate"
SKIP_DIRS = {
    ".git", ".github", ".venv", "node_modules", "workspaces",
    "runtime", "releases", "__pycache__", ".pytest_cache",
    "tests", "test", "__tests__", "screenshots", "screenshot",
    "test-results", "playwright-report",
}
SKIP_SUFFIXES = (".pyc", ".pyo", ".log")
# Old source files that existed outside the tracked release, within TEST only.
RETIRED_FILES = {
    "backend/app/routes/agent.py",
    "backend/app/services/message_queue.py",
    "backend/app/services/opencode.py",
    "backend/app/services/opencode_catalog.py",
    "backend/app/services/account_provider_runtime.py",
    "backend/app/services/session_recovery.py",
    "backend/app/services/native_control_bridge.py",
    "backend/app/services/chat_attachments.py",
    "backend/app/services/account_provider_sync.py",
    "backend/app/services/native_provider_accounts.py",
    "backend/app/services/user_provider_credentials.py",
    "backend/app/services/providers.py",
    "backend/app/services/runtime_snapshot.py",
    "backend/app/services/archive_storage.py",
    "backend/alembic/versions/0034_project_native_session_binding.py",
    "assets/native-direct/app.js",
    "assets/native-direct/index.html",
    ".github/workflows/promote-native-live.yml",
    ".github/workflows/reset-native-provider-auth.yml",
    "backend/scripts/audit_opencode_memory.py",
    "deployment/OPENCODE_INTEGRATION.md",
    "deployment/check_opencode_runtime.sh",
    "docs/OPENCODE_GATEWAY_CURRENT_AGREEMENT_AR.md",
    "scripts/install-live-native-discovery.sh",
    "scripts/live-native-promote.sh",
}

SUDO_PASSWORD = None

def run(*cmd, timeout=90, stdin=None):
    result = subprocess.run(list(cmd), input=stdin, check=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=timeout)
    return result.stdout

def sudo(*args, timeout=180):
    if SUDO_PASSWORD:
        return run("sudo", "-S", "-p", "", *args, timeout=timeout,
                   stdin=(SUDO_PASSWORD + "\n").encode())
    return run("sudo", "-n", *args, timeout=timeout)

def git(*args):
    return run("git", "-C", str(ROOT), *args)

def paths(revision):
    result = set()
    for name in git("ls-tree", "-r", "--name-only", revision).decode().splitlines():
        parts = PurePosixPath(name).parts
        if (not parts or any(part in SKIP_DIRS for part in parts)
                or name.endswith(SKIP_SUFFIXES)
                or name in {".env", "runtime.env", "native-release.env"}):
            continue
        result.add(name)
    return result

def check_destination(p):
    if not (p.is_relative_to(ROOT) or p == PI_TARGET):
        raise RuntimeError("Destination outside TEST source")
    if p.is_symlink() or (p.exists() and (not p.is_file() or p.stat().st_nlink != 1)):
        raise RuntimeError("Unsafe source-file destination: " + str(p))
    boundary = ROOT if p.is_relative_to(ROOT) else PI_TARGET.parent
    parent = p.parent
    while parent != boundary:
        if parent.is_symlink():
            raise RuntimeError("Symlink in destination")
        parent = parent.parent
    if boundary.is_symlink():
        raise RuntimeError("Symlink in destination root")

def write_if_changed(p, data):
    check_destination(p)
    if p.is_file() and p.read_bytes() == data:
        return False
    p.parent.mkdir(parents=True, exist_ok=True)
    previous = p.stat() if p.exists() else None
    if previous and previous.st_uid != os.geteuid():
        raise RuntimeError("File requires another owner: " + str(p))
    fd, tmp = tempfile.mkstemp(prefix=".deploy-", dir=p.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(tmp, stat.S_IMODE(previous.st_mode) if previous else 0o644)
        os.replace(tmp, p)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)
    return True

def previous_revision():
    if REVISION.is_file():
        value = REVISION.read_text().strip()
        if re.fullmatch(r"[0-9a-f]{40}", value):
            try:
                if git("cat-file", "-t", value).strip() == b"commit":
                    return value
            except subprocess.CalledProcessError:
                pass
    # Only for cleanup comparison; never delete untracked runtime data.
    return git("rev-parse", "HEAD").decode().strip()

def deploy(revision):
    desired = paths(revision)
    if not {"backend/app/main.py", "integration/pi-central.mjs"} <= desired:
        raise RuntimeError("Incomplete Pi Gateway source tree")

    before = previous_revision()
    previous = paths(before)
    deleted = sorted((previous - desired) | (RETIRED_FILES - desired))

    changed = []
    for name in sorted(desired):
        data = git("show", revision + ":" + name)
        if write_if_changed(ROOT / name, data):
            changed.append(name)
            print("UPDATED", name, flush=True)

    removed = []
    for name in deleted:
        target = ROOT / name
        check_destination(target)
        if target.is_file():
            if target.stat().st_uid != os.geteuid():
                raise RuntimeError("Obsolete file not owned by deploy user: " + name)
            target.unlink()
            removed.append(name)
            print("REMOVED_OBSOLETE_SOURCE", name, flush=True)

    # The installed Pi executable, its auth.json, sessions and service unit
    # are not modified. Update the one existing bridge source used by its unit.
    if not PI_TARGET.is_file():
        raise RuntimeError("Existing Pi Central bridge source is missing")
    pi_changed = write_if_changed(PI_TARGET, (ROOT / "integration/pi-central.mjs").read_bytes())

    migration_changed = any(
        x.startswith("backend/alembic/versions/")
        or x in {"backend/alembic/env.py", "backend/alembic.ini"}
        for x in changed
    )
    gateway_changed = any(x.startswith("backend/") for x in changed + removed)

    # Migrations and restarts only on actual changes. No health probing,
    # Nginx changes, service/unit installation or configuration rewrite.
    if migration_changed:
        sudo(GATE, "upgrade")
        print("TEST_MIGRATIONS_APPLIED", flush=True)
    if gateway_changed:
        sudo("/usr/bin/systemctl", "restart", "opencode-gateway-test.service")
        print("TEST_GATEWAY_RESTARTED", flush=True)
    if pi_changed:
        sudo("/usr/bin/systemctl", "restart", "pi-central.service")
        print("PI_CENTRAL_RESTARTED", flush=True)

    write_if_changed(REVISION, (revision + "\n").encode())
    print("DEPLOY_COMPLETE", "updated", len(changed), "removed", len(removed),
          "migration", migration_changed, "gateway_restart", gateway_changed,
          "pi_restart", pi_changed, flush=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["deploy"])
    parser.add_argument("sha")
    args = parser.parse_args()
    if os.geteuid() == 0 or Path.cwd() != ROOT:
        raise RuntimeError("Run from the existing TEST checkout as its deploy user")
    if not re.fullmatch(r"[0-9a-f]{40}", args.sha):
        raise RuntimeError("Invalid deployment SHA")
    if not (ROOT / ".git").is_dir():
        raise RuntimeError("Existing TEST Git checkout missing")
    if git("cat-file", "-t", args.sha).strip() != b"commit":
        raise RuntimeError("Unknown deployment commit")
    git("merge-base", "--is-ancestor", args.sha, "origin/updates")
    global SUDO_PASSWORD
    if os.environ.get("TEST_SUDO_PASS_STDIN") == "1":
        SUDO_PASSWORD = sys.stdin.readline().rstrip("\r\n")
        if not SUDO_PASSWORD:
            raise RuntimeError("Missing deploy sudo credential")
    with LOCK.open("a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        deploy(args.sha)

if __name__ == "__main__":
    main()
