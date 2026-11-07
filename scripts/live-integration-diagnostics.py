#!/usr/bin/env python3
"""Read-only production email/GitHub readiness report for GitHub Actions.

No credentials, addresses, tokens, private keys, or DB contents are printed.
No emails are sent and no app or database changes are made.
"""
from __future__ import annotations

from sqlalchemy import inspect, text

from app.config import settings
from app.database import SessionLocal
from app.services import (
    admin_email_config, credentials, email_delivery, email_service_policies,
    email_verification, github, github_app_config,
)

def mark(name: str, value: bool) -> None:
    print(f"{name}={'PASS' if value else 'FAIL'}", flush=True)

def main() -> None:
    print("=== LIVE integration readiness (read-only; no backup, no deployment) ===", flush=True)
    mark("LIVE_ORIGIN", settings.public_base_url.rstrip("/") == "https://opencode-gateway.codes")
    mark("LIVE_PORT", settings.app_port == 8000)
    mark("GITHUB_CALLBACK", settings.github_callback_url == "https://opencode-gateway.codes/api/github/callback")
    mark("ENCRYPTION_KEY_PRESENT", credentials.available())
    with SessionLocal() as db:
        mark("LIVE_DATABASE", db.execute(text("SELECT current_database()")).scalar_one() == "opencode_gateway")
        inspector = inspect(db.connection())
        mark("EMAIL_SETTINGS_SCHEMA", inspector.has_table("email_delivery_settings"))
        mark("STAGED_REGISTRATION_SCHEMA", inspector.has_table("pending_registrations"))
        mark("GITHUB_SETTINGS_SCHEMA", github_app_config.schema_ready(db))
        mark("GITHUB_IDENTITY_SCHEMA", inspector.has_table("github_identity_registry"))
        try:
            mail = email_verification.smtp_settings(db)
            mail_ready = email_delivery.ready(mail)
            print("EMAIL_PROVIDER=" + (str(mail.get("provider") or "smtp").upper() if mail else "NONE"), flush=True)
            mark("EMAIL_SENDING_CONFIGURED", mail_ready)
        except Exception:
            mail_ready = False
            mark("EMAIL_SENDING_CONFIGURED", False)
            print("EMAIL_CONFIGURATION_ERROR=CHECK_ENCRYPTION_AND_SAVED_SETTINGS")
        try:
            registration_enabled = email_service_policies.enabled(db, "registration_verification", True)
            mark("REGISTRATION_EMAIL_POLICY_ENABLED", registration_enabled)
            github_email_enabled = email_service_policies.enabled(db, "github_connection_verification", True)
            mark("GITHUB_EMAIL_POLICY_ENABLED", github_email_enabled)
        except Exception:
            mark("EMAIL_SERVICE_POLICY_READABLE", False)
            registration_enabled = github_email_enabled = False
        try:
            github_ready = github.configured(db)
            mark("GITHUB_APP_CONFIGURED", github_ready)
        except Exception:
            github_ready = False
            mark("GITHUB_APP_CONFIGURED", False)
            print("GITHUB_CONFIG_ERROR=CHECK_ENCRYPTION_AND_SAVED_SETTINGS")
    if not mail_ready:
        print("::warning::LIVE registration is blocked: configure an authorized email provider in the LIVE Admin integrations.")
    if not github_ready:
        print("::warning::LIVE GitHub linking is unavailable: configure the GitHub App in LIVE Admin settings.")
    if not github_email_enabled:
        print("::warning::LIVE GitHub email-verification policy is disabled.")
    print("DELIVERY_VERIFIED=NOT_TESTED")
    print("GITHUB_OAUTH_END_TO_END=NOT_TESTED")
    print("LIVE_INTEGRATION_DIAGNOSTIC_FINISHED")

if __name__ == "__main__":
    main()
