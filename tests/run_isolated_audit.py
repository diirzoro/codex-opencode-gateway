"""Run an in-memory PostgreSQL/PGlite compatibility audit, never production.

Usage: python tests/run_isolated_audit.py --pglite-command /path/to/pglite-server
Requires backend dependencies in the current Python interpreter. PGlite is an
optional external test tool, not a production dependency or native PG substitute.
"""
import argparse
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import tempfile
import time

parser = argparse.ArgumentParser()
parser.add_argument("--pglite-command", required=True)
parser.add_argument("--opencode-binary")
parser.add_argument("--run-browser", action="store_true")
parser.add_argument("--pytest-target", action="append", help="Run only selected affected test modules/nodes")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]
with tempfile.TemporaryDirectory(prefix="gateway-isolated-audit-") as directory:
    db_process = subprocess.Popen([args.pglite_command, "--host=127.0.0.1", "--port="+str(port),
                                   "--db=memory://", "--max-connections=8"],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        deadline = time.monotonic()+45
        while time.monotonic() < deadline:
            if select.select([db_process.stdout], [], [], 1)[0]:
                if "listening on" in db_process.stdout.readline():break
            if db_process.poll() is not None:raise RuntimeError("Disposable engine failed to start")
        else:raise RuntimeError("Disposable engine startup timed out")
        env = dict(os.environ, DATABASE_URL=f"postgresql+psycopg://postgres:postgres@127.0.0.1:{port}/postgres",
                   AUDIT_DISPOSABLE_DB="1", AUDIT_DB_ENGINE="pglite",
                   WORKSPACE_ROOT=directory+"/workspaces", RUNTIME_ROOT=directory+"/runtime",
                   CREDENTIALS_ENCRYPTION_KEY="disposable-fixture-only",
                   PUBLIC_BASE_URL="https://testserver", OPENCODE_RUNTIME_MODE="disabled")
        if args.opencode_binary:
            env.update(OPENCODE_RUNTIME_MODE="local", OPENCODE_BINARY=str(Path(args.opencode_binary).resolve()),
                       AUDIT_RUN_OPENCODE="1")
        for command, cwd in [(["-m", "alembic", "upgrade", "head"], root/"backend"),
                             (["-m", "pytest", *(args.pytest_target or ["backend/tests/test_disposable_database.py"]), "-q", "--tb=short"], root)]:
            result = subprocess.run([sys.executable, *command], cwd=cwd, env=env, timeout=180)
            if result.returncode:
                print("Isolated audit subprocess failed:", command[:3], "exit=",result.returncode,"database_exit=",db_process.poll(),flush=True)
                sys.exit(result.returncode)
        if args.run_browser:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0)); staging_port=sock.getsockname()[1]
            env.update(AUDIT_STAGING_PORT=str(staging_port), AUDIT_MAILBOX=directory+"/mailbox.json",
                       COOKIE_SECURE="false")
            app_process=subprocess.Popen([sys.executable,"-m","tests.staging_app"],cwd=root,env=env)
            try:
                for attempt in range(100):
                    try:
                        with socket.create_connection(("127.0.0.1",staging_port),timeout=.2):break
                    except OSError:time.sleep(.1)
                else:raise RuntimeError("Loopback staging startup failed")
                subprocess.run(["node","tests/browser/staging.cjs"],cwd=root,env=env,timeout=150,check=True)
            finally:
                app_process.terminate()
                try:app_process.wait(timeout=10)
                except subprocess.TimeoutExpired:app_process.kill();app_process.wait()
    finally:
        db_process.terminate()
        try:db_process.wait(timeout=5)
        except subprocess.TimeoutExpired:db_process.kill();db_process.wait()
