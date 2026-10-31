#!/usr/bin/env python3
"""Synchronize TEST platform email and GitHub App settings into LIVE, safely.

This is a one-way platform integration migration, not a database clone. TEST
and LIVE must retain separate databases and environment secrets. No backups,
file deletions, native service changes, account or session copies occur.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

TEST_ENV = Path("/home/tahir/opencode-gateway-test/.env")
LIVE_ENV = Path("/home/tahir/opencode-gateway/.env")
ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1"}
EMAIL_TABLE = "email_delivery_settings"
GITHUB_TABLE = "github_app_settings"
POLICY_TABLE = "email_service_policies"
# Only these platform-level preferences are safe to promote, never user data.
POLICIES = frozenset({
    "registration_verification", "password_reset", "github_connection_verification",
    "welcome_email", "account_suspension", "payment_receipt", "login_security",
    "password_changed", "email_changed", "payment_failed", "unusual_activity",
    "subscription_expiry", "renewal_reminder", "trial_expiring", "system_updates",
    "service_incident", "backup_status", "support_received",
})


def fail(message):
    raise RuntimeError(message)


_sudo_authorization = None


def _private_env_text(path):
    """Read only the two approved local .env files. Use sudo cat only if unreadable.

    Password is supplied over a dedicated inherited FD, never an environment
    variable, command argument, logged output, temporary file or repository.
    Application database operations still run as the unprivileged SSH user.
    """
    global _sudo_authorization
    if path not in (TEST_ENV, LIVE_ENV):
        fail("PRIVATE_ENV_PATH_NOT_ALLOWLISTED")
    try:
        return path.read_text()
    except PermissionError:
        if _sudo_authorization is None:
            try:
                with os.fdopen(3, "r", encoding="utf-8") as reader:
                    _sudo_authorization = reader.readline().rstrip("\n")
            except OSError:
                fail("PROTECTED_ENV_SUDO_CREDENTIAL_NOT_PROVIDED")
        if not _sudo_authorization:
            fail("PROTECTED_ENV_SUDO_CREDENTIAL_EMPTY")
        try:
            result = subprocess.run(
                ["sudo", "-S", "-p", "", "/usr/bin/cat", str(path)],
                input=_sudo_authorization + "\n",
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, check=False, timeout=12,
            )
        except (OSError, subprocess.TimeoutExpired):
            fail("PROTECTED_ENV_PRIVILEGED_READ_UNAVAILABLE")
        if result.returncode != 0:
            fail("PROTECTED_ENV_PRIVILEGED_READ_REJECTED")
        return result.stdout


def env_file(path):
    if not path.is_file() or path.is_symlink():
        fail("MISSING_OR_UNSAFE_ENV_FILE")
    values = {}
    for line in _private_env_text(path).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        name, raw = line.split("=", 1)
        name = name.strip()
        if name not in {"DATABASE_URL", "CREDENTIALS_ENCRYPTION_KEY", "PUBLIC_BASE_URL", "APP_PORT"}:
            continue
        parts = shlex.split(raw, comments=True)
        if len(parts) > 1:
            fail("INVALID_ENV_VALUE_" + name)
        values[name] = parts[0] if parts else ""
    return values


def validated(label, path, domain, database, port):
    values = env_file(path)
    url = make_url(values.get("DATABASE_URL", ""))
    if url.get_backend_name() != "postgresql" or url.database != database:
        fail(label + "_DATABASE_IDENTITY_MISMATCH")
    if url.host not in ALLOWED_HOSTS:
        fail(label + "_DATABASE_HOST_NOT_LOCAL")
    if values.get("PUBLIC_BASE_URL", "").rstrip("/") != domain:
        fail(label + "_PUBLIC_ORIGIN_MISMATCH")
    if str(values.get("APP_PORT", "")) != str(port):
        fail(label + "_PORT_MISMATCH")
    if not values.get("CREDENTIALS_ENCRYPTION_KEY"):
        fail(label + "_ENCRYPTION_KEY_MISSING")
    return values, url


def cipher(key):
    raw = hashlib.sha256(key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(raw))


def unseal(token, key, label):
    try:
        data = json.loads(cipher(key).decrypt(token.encode()).decode())
    except (InvalidToken, ValueError, TypeError, UnicodeError):
        fail(label + "_CANNOT_DECRYPT_WITH_TEST_KEY")
    if not isinstance(data, dict):
        fail(label + "_INVALID_PAYLOAD")
    return data


def seal(payload, key):
    return cipher(key).encrypt(json.dumps(payload).encode()).decode()


def read_one(conn, table):
    return conn.execute(text("SELECT encrypted_data FROM " + table + " WHERE id=1")).scalar_one_or_none()


def mail_ready(config):
    if not config:
        return False
    if config.get("provider") == "brevo":
        return bool(config.get("api_key") and config.get("smtp_from"))
    return all(config.get(k) for k in ("smtp_host", "smtp_from", "smtp_username", "smtp_password"))


def github_ready(config):
    return bool(
        config and config.get("github_app_id")
        and config.get("github_app_slug")
        and config.get("github_client_id")
        and config.get("github_client_secret")
        and config.get("github_private_key")
    )


def upsert_email(conn, encrypted, actor):
    conn.execute(text("""
      INSERT INTO email_delivery_settings (id, encrypted_data, updated_by)
      VALUES (1, :payload, :actor)
      ON CONFLICT (id) DO UPDATE SET encrypted_data=excluded.encrypted_data,
          updated_by=excluded.updated_by, updated_at=CURRENT_TIMESTAMP
    """), {"payload": encrypted, "actor": actor})


def upsert_github(conn, encrypted, actor):
    conn.execute(text("""
      INSERT INTO github_app_settings (id, encrypted_data, updated_by)
      VALUES (1, :payload, :actor)
      ON CONFLICT (id) DO UPDATE SET encrypted_data=excluded.encrypted_data,
          updated_by=excluded.updated_by, updated_at=CURRENT_TIMESTAMP
    """), {"payload": encrypted, "actor": actor})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("audit", "apply"))
    args = parser.parse_args()
    if os.geteuid() == 0:
        fail("RUN_AS_TAHIR_NOT_ROOT")
    test, test_url = validated("TEST", TEST_ENV, "https://test.opencode-gateway.codes", "opencode_gateway_test", 8001)
    live, live_url = validated("LIVE", LIVE_ENV, "https://opencode-gateway.codes", "opencode_gateway", 8000)
    if test_url.database == live_url.database:
        fail("SAME_DATABASE_BLOCKED")
    test_engine = create_engine(test_url, pool_pre_ping=True)
    live_engine = create_engine(live_url, pool_pre_ping=True)
    try:
        # Read TEST first and validate every proposed value before starting LIVE writes.
        with test_engine.connect() as src:
            if src.execute(text("SELECT current_database()")).scalar_one() != "opencode_gateway_test":
                fail("TEST_CONNECTED_TO_WRONG_DATABASE")
            inspector = inspect(src)
            for table in (EMAIL_TABLE, GITHUB_TABLE, POLICY_TABLE):
                if not inspector.has_table(table):
                    fail("TEST_MISSING_PLATFORM_SCHEMA_" + table)
            source_email = read_one(src, EMAIL_TABLE)
            source_github = read_one(src, GITHUB_TABLE)
            policies = src.execute(text("SELECT service_id, enabled FROM email_service_policies")).all()
        if not source_email:
            fail("TEST_EMAIL_SETTINGS_MISSING")
        if not source_github:
            fail("TEST_GITHUB_APP_SETTINGS_MISSING")
        source_email_data = unseal(source_email, test["CREDENTIALS_ENCRYPTION_KEY"], "TEST_EMAIL") if source_email else None
        source_github_data = unseal(source_github, test["CREDENTIALS_ENCRYPTION_KEY"], "TEST_GITHUB") if source_github else None
        if source_email_data is not None and not mail_ready(source_email_data):
            fail("TEST_EMAIL_PROVIDER_INCOMPLETE")
        if source_github_data is not None and not github_ready(source_github_data):
            fail("TEST_GITHUB_APP_INCOMPLETE")
        print("TEST_EMAIL_SETTINGS=" + ("READY" if source_email_data else "ABSENT"), flush=True)
        print("TEST_GITHUB_APP_SETTINGS=" + ("READY" if source_github_data else "ABSENT"), flush=True)
        print("TEST_EMAIL_PROVIDER=" + str((source_email_data or {}).get("provider") or "smtp").upper(), flush=True)
        print("TEST_EMAIL_POLICY_ROWS=" + str(sum(1 for k, _ in policies if k in POLICIES)), flush=True)
        # Transaction ensures LIVE integration rows and policies change together or not at all.
        with live_engine.begin() as dest:
            if dest.execute(text("SELECT current_database()")).scalar_one() != "opencode_gateway":
                fail("LIVE_CONNECTED_TO_WRONG_DATABASE")
            inspector = inspect(dest)
            for table in (EMAIL_TABLE, GITHUB_TABLE, POLICY_TABLE, "github_connections", "users"):
                if not inspector.has_table(table):
                    fail("LIVE_MISSING_PLATFORM_SCHEMA_" + table)
            actor = dest.execute(text(
                "SELECT id FROM users WHERE role IN ('admin','owner') ORDER BY id LIMIT 1"
            )).scalar_one_or_none()
            if source_email_data and actor is None:
                fail("LIVE_ADMIN_REQUIRED_FOR_EMAIL_SETTINGS_FK")
            existing_github = read_one(dest, GITHUB_TABLE)
            if existing_github and source_github_data:
                try:
                    current_github = json.loads(cipher(live["CREDENTIALS_ENCRYPTION_KEY"]).decrypt(existing_github.encode()).decode())
                except (InvalidToken, ValueError, TypeError, UnicodeError):
                    fail("LIVE_EXISTING_GITHUB_KEY_UNREADABLE")
                new_identity = (source_github_data["github_app_id"], source_github_data["github_client_id"])
                old_identity = (current_github.get("github_app_id"), current_github.get("github_client_id"))
                links = dest.execute(text("SELECT COUNT(*) FROM github_connections")).scalar_one()
                if old_identity != new_identity and links:
                    fail("LIVE_LINKED_ACCOUNTS_PROTECT_EXISTING_GITHUB_APP_IDENTITY")
            print("LIVE_EMAIL_SETTINGS_BEFORE=" + ("PRESENT" if read_one(dest, EMAIL_TABLE) else "ABSENT"), flush=True)
            print("LIVE_GITHUB_APP_BEFORE=" + ("PRESENT" if existing_github else "ABSENT"), flush=True)
            if args.mode == "apply":
                if source_email_data:
                    upsert_email(dest, seal(source_email_data, live["CREDENTIALS_ENCRYPTION_KEY"]), actor)
                if source_github_data:
                    upsert_github(dest, seal(source_github_data, live["CREDENTIALS_ENCRYPTION_KEY"]), actor)
                for service_id, enabled in policies:
                    if service_id not in POLICIES:
                        continue
                    dest.execute(text("""
                      INSERT INTO email_service_policies(service_id,enabled)
                      VALUES(:id,:enabled)
                      ON CONFLICT(service_id) DO UPDATE
                      SET enabled=excluded.enabled,updated_at=CURRENT_TIMESTAMP
                    """), {"id": service_id, "enabled": enabled})
                if source_email_data:
                    check_email = unseal(read_one(dest, EMAIL_TABLE), live["CREDENTIALS_ENCRYPTION_KEY"], "LIVE_EMAIL_VERIFY")
                    if not mail_ready(check_email):
                        fail("LIVE_EMAIL_VERIFY_FAILED")
                if source_github_data:
                    check_github = unseal(read_one(dest, GITHUB_TABLE), live["CREDENTIALS_ENCRYPTION_KEY"], "LIVE_GITHUB_VERIFY")
                    if not github_ready(check_github):
                        fail("LIVE_GITHUB_VERIFY_FAILED")
            print("INTEGRATIONS_SYNC=" + ("APPLIED" if args.mode == "apply" else "AUDITED"), flush=True)
            print("NO_BACKUP_NO_ACCOUNT_COPY_NO_NATIVE_RESTART", flush=True)
    finally:
        test_engine.dispose()
        live_engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Do not leak SQL URLs, provider credentials or encrypted data into CI logs.
        if isinstance(exc, RuntimeError):
            message = str(exc)
        elif isinstance(exc, PermissionError):
            resource = getattr(exc, "filename", None)
            message = ("TEST_ENV_ACCESS_DENIED" if resource == str(TEST_ENV)
                       else "LIVE_ENV_ACCESS_DENIED" if resource == str(LIVE_ENV)
                       else "OTHER_PERMISSION_DENIED")
        else:
            message = type(exc).__name__
        print("INTEGRATIONS_SYNC_FAILED=" + message, file=sys.stderr)
        sys.exit(1)
