#!/usr/bin/env python3
"""Read-only preflight for TEST -> LIVE complete account/config migration.
Never prints secrets, user identities, session hashes or database connection URLs.
"""
import base64
import hashlib
import os
from pathlib import Path
import subprocess
import sys

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

ROOT = Path("/home/tahir")
SERVICES = {"TEST": ("opencode-gateway-test", "opencode_gateway_test",
                     "https://test.opencode-gateway.codes", "8001"),
            "LIVE": ("opencode-gateway", "opencode_gateway",
                     "https://opencode-gateway.codes", "8000")}
SUDO = None
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}


def protected_read(path):
    global SUDO
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("UNSAFE_OR_ABSENT_CONFIG")
    try:
        return path.read_text()
    except PermissionError:
        if SUDO is None:
            with os.fdopen(3, "r") as reader:
                SUDO = reader.readline().rstrip("\n")
        if not SUDO:
            raise RuntimeError("SUDO_CREDENTIAL_MISSING")
        result = subprocess.run(
            ["sudo", "-S", "-p", "", "/usr/bin/cat", str(path)],
            input=SUDO + "\n", text=True, capture_output=True, timeout=12)
        if result.returncode:
            raise RuntimeError("PROTECTED_CONFIG_READ_DENIED")
        return result.stdout


def settings_file(path):
    values = {}
    for line in protected_read(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        k, v = stripped.removeprefix("export ").split("=", 1)
        if k.strip() in {"DATABASE_URL", "CREDENTIALS_ENCRYPTION_KEY",
                         "PUBLIC_BASE_URL", "APP_PORT"}:
            import shlex
            parsed = shlex.split(v.strip(), comments=True)
            values[k.strip()] = parsed[0] if len(parsed) == 1 else ""
    return values


def service_key(name):
    proc = subprocess.run(
        ["systemctl", "show", name + ".service", "-p", "MainPID", "--value"],
        text=True, capture_output=True, timeout=8)
    pid = proc.stdout.strip()
    if not pid.isdecimal() or pid == "0":
        return ""
    try:
        raw = protected_read(Path("/proc") / pid / "environ")
    except (OSError, RuntimeError, UnicodeDecodeError):
        return ""
    for line in raw.split("\0"):
        if line.startswith("CREDENTIALS_ENCRYPTION_KEY="):
            return line.partition("=")[2]
    return ""


def fernet(key):
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest()))


def decryptable(token, keys):
    if not token:
        return False
    for key in keys:
        try:
            fernet(key).decrypt(token.encode())
            return True
        except (InvalidToken, ValueError, TypeError):
            continue
    return False


def run():
    if os.geteuid() == 0:
        raise RuntimeError("RUN_AS_TAHIR_NOT_ROOT")
    engines = {}
    keys = {}
    totals = {}
    try:
        for side, (folder, expected_db, domain, port) in SERVICES.items():
            path = ROOT / folder / ".env"
            v = settings_file(path)
            url = make_url(v.get("DATABASE_URL", ""))
            if url.get_backend_name() != "postgresql" or url.database != expected_db \
                    or url.host not in ALLOWED_HOSTS:
                raise RuntimeError(side + "_DATABASE_IDENTITY_INVALID")
            if v.get("PUBLIC_BASE_URL", "").rstrip("/") != domain or v.get("APP_PORT") != port:
                raise RuntimeError(side + "_ORIGIN_OR_PORT_INVALID")
            options = [v.get("CREDENTIALS_ENCRYPTION_KEY"), service_key(folder)]
            keys[side] = tuple(dict.fromkeys(k for k in options if k))
            print(side + "_ENV_KEY_PRESENT=" + str(bool(options[0])).upper(), flush=True)
            print(side + "_SERVICE_KEY_PRESENT=" + str(bool(options[1])).upper(), flush=True)
            engine = create_engine(url, pool_pre_ping=True)
            engines[side] = engine
            with engine.connect() as conn:
                if conn.execute(text("SELECT current_database()")).scalar_one() != expected_db:
                    raise RuntimeError(side + "_DATABASE_CONNECTION_MISMATCH")
                tables = sorted(inspect(conn).get_table_names())
                totals[side] = {}
                for table in tables:
                    if not table.isidentifier():
                        raise RuntimeError("UNSAFE_TABLE_IDENTIFIER")
                    totals[side][table] = conn.execute(
                        text('SELECT count(*) FROM "' + table + '"')).scalar_one()
                print(side + "_TABLES=" + str(len(tables)), flush=True)
                for t in ("users", "projects", "workspaces", "workspace_sessions",
                          "auth_sessions", "github_connections", "user_provider_credentials",
                          "provider_credentials", "email_delivery_settings",
                          "github_app_settings", "email_service_policies", "subscriptions"):
                    print(side + "_" + t.upper() + "=" + str(totals[side].get(t, "ABSENT")), flush=True)
                if side == "TEST":
                    for tab, col in (
                        ("email_delivery_settings", "encrypted_data"),
                        ("github_app_settings", "encrypted_data"),
                        ("user_provider_credentials", "ciphertext"),
                        ("provider_credentials", "ciphertext"),
                        ("github_connections", "user_token"),
                        ("pending_registrations", "payload_ciphertext"),
                    ):
                        if tab not in tables:
                            continue
                        samples = conn.execute(
                            text('SELECT "' + col + '" FROM "' + tab + '" WHERE "' + col + '" IS NOT NULL')).scalars().all()
                        tested = len(samples)
                        candidates = tuple(dict.fromkeys((*keys.get("TEST", ()), *keys.get("LIVE", ()))))
                        passed = sum(decryptable(token, candidates) for token in samples)
                        print("TEST_" + tab.upper() + "_DECRYPTABLE=" +
                              str(passed) + "/" + str(tested), flush=True)
        src = totals["TEST"]; dst = totals["LIVE"]
        if set(src) != set(dst):
            missing = sorted(set(src) - set(dst))
            print("SCHEMA_TABLE_SET_MATCH=NO", flush=True)
            print("MISSING_LIVE_TABLES=" + ",".join(missing), flush=True)
        else:
            print("SCHEMA_TABLE_SET_MATCH=YES", flush=True)
        from sqlalchemy import MetaData
        for table in sorted(set(totals["TEST"]) & set(totals["LIVE"])):
            with engines["TEST"].connect() as source, engines["LIVE"].connect() as target:
                src_ins = inspect(source)
                pk = src_ins.get_pk_constraint(table).get("constrained_columns") or []
                if not pk:
                    continue
                columns = ",".join('"' + k + '"' for k in pk)
                ids_source = {tuple(row) for row in source.execute(
                    text('SELECT ' + columns + ' FROM "' + table + '"')).all()}
                ids_live = {tuple(row) for row in target.execute(
                    text('SELECT ' + columns + ' FROM "' + table + '"')).all()}
                overlap = len(ids_source & ids_live)
                newly = len(ids_source - ids_live)
                if newly or overlap:
                    print("TABLE_DELTA_" + table.upper() + "=" + str(newly) +
                          "_NEW_" + str(overlap) + "_SHARED", flush=True)
        with engines["TEST"].connect() as sc, engines["LIVE"].connect() as dc:
            src = sc.execute(text("""SELECT id, username_identity, email_identity,
                                            phone_identity FROM users""")).mappings().all()
            dst = dc.execute(text("""SELECT id, username_identity, email_identity,
                                            phone_identity FROM users""")).mappings().all()
            identities = ("username_identity", "email_identity", "phone_identity")
            collisions = 0
            for source_user in src:
                for live_user in dst:
                    if source_user["id"] == live_user["id"]:
                        continue
                    if any(source_user[k] is not None and source_user[k] == live_user[k]
                           for k in identities):
                        collisions += 1
            print("ACCOUNT_IDENTITY_COLLISIONS=" + str(collisions), flush=True)
        print("READ_ONLY_AUDIT_FINISHED", flush=True)
    finally:
        for e in engines.values():
            e.dispose()


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("AUDIT_FAILED=" + (str(exc) if isinstance(exc, RuntimeError)
                                else type(exc).__name__), file=sys.stderr)
        sys.exit(1)
