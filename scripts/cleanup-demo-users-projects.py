#!/usr/bin/env python3
"""Permanently remove demo accounts/projects from isolated TEST and LIVE DBs.

Keeps exactly usernames admin and testuser in EACH DB. Keeps platform settings,
plans, locations, mail/GitHub settings and those users' subscriptions. No dumps,
backups or file-level deletions. Does not touch the shared OpenCode Native server.
"""
import argparse
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

ROOT = Path("/home/tahir")
TARGET = {
    "TEST": ("opencode-gateway-test", "opencode_gateway_test", "https://test.opencode-gateway.codes", "8001"),
    "LIVE": ("opencode-gateway", "opencode_gateway", "https://opencode-gateway.codes", "8000"),
}
CLEAR = {
    "account_audit", "admin_mail_drafts", "auth_sessions", "email_notification_receipts",
    "email_verifications", "execution_events", "github_auth_states", "github_connections",
    "github_identity_registry", "password_resets", "payment_orders",
    "pending_registrations", "preview_runtime_leases", "projects",
    "provider_credentials", "user_provider_credentials", "workspace_sessions", "workspaces",
}
PRESERVE = {
    "alembic_version", "billing_methods", "cities", "countries", "email_delivery_settings",
    "email_service_policies", "github_app_settings", "homepage_items", "plans",
    "platform_policy", "preview_worker_capacities", "regions", "subscriptions", "users",
}
ALLOWED = CLEAR | PRESERVE
ENV_PASSWORD = None


def die(reason):
    raise RuntimeError(reason)


def private_file(path):
    global ENV_PASSWORD
    if path.is_symlink() or not path.is_file():
        die("ENV_FILE_MISSING_OR_UNSAFE")
    try:
        return path.read_text()
    except PermissionError:
        if ENV_PASSWORD is None:
            try:
                with os.fdopen(3, "r") as src:
                    ENV_PASSWORD = src.readline().rstrip("\n")
            except OSError:
                die("SUDO_AUTHORIZATION_REQUIRED")
        if not ENV_PASSWORD:
            die("SUDO_AUTHORIZATION_REQUIRED")
        proc = subprocess.run(
            ["sudo", "-S", "-p", "", "/usr/bin/cat", str(path)],
            input=ENV_PASSWORD + "\n", text=True, capture_output=True, timeout=12)
        if proc.returncode:
            die("ENV_FILE_READ_DENIED")
        return proc.stdout


def connection_url(side):
    folder, name, domain, port = TARGET[side]
    env = {}
    for line in private_file(ROOT / folder / ".env").splitlines():
        line = line.strip().removeprefix("export ")
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() in {"DATABASE_URL", "PUBLIC_BASE_URL", "APP_PORT"}:
            tokens = shlex.split(v, comments=True)
            if len(tokens) > 1:
                die(side + "_ENV_VALUE_INVALID")
            env[k.strip()] = tokens[0] if tokens else ""
    url = make_url(env.get("DATABASE_URL", ""))
    if url.get_backend_name() != "postgresql" or url.database != name or url.host not in ("127.0.0.1", "localhost", "::1"):
        die(side + "_DATABASE_BOUNDARY")
    if env.get("PUBLIC_BASE_URL", "").rstrip("/") != domain or env.get("APP_PORT") != port:
        die(side + "_DOMAIN_PORT_BOUNDARY")
    return url


def verify(conn, side):
    folder, name, _, _ = TARGET[side]
    if conn.execute(text("SELECT current_database()")).scalar_one() != name:
        die(side + "_WRONG_DATABASE")
    ins = inspect(conn)
    tables = set(ins.get_table_names())
    if tables != ALLOWED:
        die(side + "_SCHEMA_CHANGED_REVIEW_REQUIRED")
    selected = list(conn.execute(text(
        "SELECT id, username, role FROM users WHERE lower(username) IN ('admin', 'testuser')"
        " ORDER BY username FOR UPDATE"
    )).mappings())
    if len(selected) != 2 or {r["username"].lower() for r in selected} != {"admin", "testuser"}:
        die(side + "_TWO_KEEP_ACCOUNTS_NOT_FOUND")
    admin = next(r for r in selected if r["username"].lower() == "admin")
    tester = next(r for r in selected if r["username"].lower() == "testuser")
    if str(admin["role"]).lower() not in ("admin", "owner") or str(tester["role"]).lower() in ("admin", "owner"):
        die(side + "_KEEP_ACCOUNT_ROLES_MISMATCH")
    return ins, admin["id"], tester["id"]


def delete_order(ins):
    # Child tables first; never disable foreign-key constraints or use CASCADE.
    dependencies = {table: set() for table in CLEAR}
    for child in CLEAR:
        for fk in ins.get_foreign_keys(child):
            parent = fk.get("referred_table")
            if parent in CLEAR:
                dependencies[parent].add(child)
    order = []
    remaining = set(CLEAR)
    while remaining:
        leaves = sorted(t for t in remaining if not dependencies[t].intersection(remaining))
        if not leaves:
            die("CIRCULAR_FOREIGN_KEYS_REVIEW_REQUIRED")
        order.extend(leaves)
        remaining.difference_update(leaves)
    # Protect config/lookup tables referencing user rows before removing users.
    references = {t for t in ALLOWED - CLEAR - {"users"} if
                  any(fk.get("referred_table") == "users" for fk in ins.get_foreign_keys(t))}
    if references != {"billing_methods", "email_delivery_settings", "github_app_settings", "subscriptions"}:
        die("UNREVIEWED_USERS_FOREIGN_KEY_REFERENCE")
    return order


def perform(conn, side, apply):
    ins, admin, tester = verify(conn, side)
    order = delete_order(ins)
    keep = {"admin": admin, "testuser": tester}
    counts = {t: conn.execute(text('SELECT count(*) FROM "' + t + '"')).scalar_one() for t in CLEAR}
    before_users = conn.execute(text("SELECT count(*) FROM users")).scalar_one()
    if not apply:
        print(side + "_KEEP=admin,testuser")
        print(side + "_USERS_TO_DELETE=" + str(before_users - 2))
        print(side + "_PROJECTS_TO_DELETE=" + str(counts["projects"]))
        print(side + "_WORKSPACES_TO_DELETE=" + str(counts["workspaces"]))
        print(side + "_SESSIONS_TO_DELETE=" + str(counts["workspace_sessions"]))
        print(side + "_OTHER_TRANSIENT_ROWS_TO_DELETE=" +
              str(sum(value for key, value in counts.items() if key not in ("projects", "workspaces", "workspace_sessions"))))
        return
    # Preserve encrypted platform configuration. Its audit actor must remain an account.
    for table in ("email_delivery_settings", "github_app_settings"):
        conn.execute(text('UPDATE "' + table + '" SET updated_by=:admin WHERE updated_by IS NOT NULL AND updated_by<>:admin'),
                     {"admin": admin})
    for table in order:
        conn.execute(text('DELETE FROM "' + table + '"'))
    conn.execute(text("DELETE FROM subscriptions WHERE user_id<>:a AND user_id<>:b"),
                 {"a": admin, "b": tester})
    conn.execute(text("DELETE FROM billing_methods WHERE user_id IS NOT NULL AND user_id<>:a AND user_id<>:b"),
                 {"a": admin, "b": tester})
    conn.execute(text("DELETE FROM users WHERE id<>:a AND id<>:b"), {"a": admin, "b": tester})
    now = conn.execute(text("SELECT count(*) FROM users")).scalar_one()
    if now != 2:
        die(side + "_POST_DELETE_USER_COUNT_INVALID")
    for table in CLEAR:
        left = conn.execute(text('SELECT count(*) FROM "' + table + '"')).scalar_one()
        if left:
            die(side + "_POST_DELETE_NONEMPTY_" + table)
    print(side + "_CLEANUP_VERIFIED=YES", flush=True)
    print(side + "_USERS_REMAIN=2", flush=True)
    print(side + "_PROJECTS_REMAIN=0", flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("audit", "apply"))
    args = p.parse_args()
    if os.geteuid() == 0:
        die("RUN_AS_TAHIR_NOT_ROOT")
    engines = {side: create_engine(connection_url(side), pool_pre_ping=True) for side in TARGET}
    try:
        # Verify both DB identities and exact account selection before modifying either.
        for side, engine in engines.items():
            with engine.begin() as conn:
                conn.execute(text("SET LOCAL lock_timeout='8s'"))
                verify(conn, side)
                delete_order(inspect(conn))
        if args.mode == "audit":
            for side, engine in engines.items():
                with engine.begin() as conn:
                    perform(conn, side, False)
            print("CLEANUP_PREFLIGHT_PASSED", flush=True)
        else:
            for side, engine in engines.items():
                with engine.begin() as conn:
                    conn.execute(text("SET LOCAL lock_timeout='8s'"))
                    conn.execute(text("SELECT pg_advisory_xact_lock(867530921)"))
                    perform(conn, side, True)
            print("CLEANUP_BOTH_DATABASES_COMMITTED", flush=True)
    finally:
        for e in engines.values():
            e.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("CLEANUP_FAILED=" + (str(exc) if isinstance(exc, RuntimeError)
                                  else type(exc).__name__), file=sys.stderr)
        sys.exit(1)
