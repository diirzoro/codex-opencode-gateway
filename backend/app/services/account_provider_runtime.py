"""Short-lived, user-isolated OpenCode validation runtime; never share auth daemon.

Used only during account-level API-key verification. It has no project files,
no access to other users' runtime directories and is destroyed after validation.
"""
import json
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from fastapi import HTTPException
from ..config import settings
from .opencode import OpenCodeService, STARTUP_TIMEOUT
from .policy import load, permission_config


@contextmanager
def isolated_validation(user_id, db):
    if settings.runtime_mode != "local":
        raise HTTPException(503, "Isolated OpenCode validation is not enabled")
    binary = shutil.which(settings.opencode_binary)
    if not binary:
        raise HTTPException(503, "OpenCode executable is not installed")
    parent = settings.runtime_root / str(user_id)
    parent.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="account-validation-", dir=parent))
    process = None
    service = None
    log = None
    try:
        env = {k: v for k, v in os.environ.items() if k.upper() in {
            "PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP",
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "SSL_CERT_FILE",
            "SSL_CERT_DIR", "NODE_EXTRA_CA_CERTS"}}
        for key, folder in {"HOME":"home", "USERPROFILE":"home", "APPDATA":"config",
                            "LOCALAPPDATA":"data", "XDG_CONFIG_HOME":"config",
                            "XDG_DATA_HOME":"data", "XDG_STATE_HOME":"state",
                            "XDG_CACHE_HOME":"cache"}.items():
            location = root / folder
            location.mkdir()
            env[key] = str(location)
        password = secrets.token_urlsafe(32)
        env.update(OPENCODE_SERVER_PASSWORD=password,
                   OPENCODE_CONFIG_CONTENT=json.dumps({
                       "autoupdate":False, "share":"disabled", "plugin":[],
                       "permission":permission_config(load(db))}))
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        log = open(root / "runtime.log", "a", encoding="utf-8")
        service = OpenCodeService(f"http://127.0.0.1:{port}", password, root)
        process = subprocess.Popen([binary, "serve", "--pure", "--hostname",
                                    "127.0.0.1", "--port", str(port)],
                                   cwd=root, env=env, stdout=log, stderr=log)
        deadline = time.monotonic() + STARTUP_TIMEOUT
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise HTTPException(503, "Account validation runtime exited unexpectedly")
            try:
                service.health(timeout=1)
                break
            except HTTPException:
                time.sleep(.1)
        else:
            raise HTTPException(504, "Account validation runtime startup timed out")
        yield service
    finally:
        if service is not None:
            service.close()
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if log is not None:
            log.close()
        shutil.rmtree(root, ignore_errors=True)
