"""Regression tests for the read-only audit / protected TEST-to-LIVE integration sync."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sync_test_platform_integrations", ROOT / "scripts/sync-test-platform-integrations.py"
)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def test_fernet_reencrypt_never_copies_test_ciphertext_as_live():
    test_key = "separate-test-encryption-key"
    live_key = "separate-live-encryption-key"
    payload = {"provider": "resend", "smtp_from": "test@example.invalid",
               "smtp_host": "smtp.resend.com", "smtp_username": "resend",
               "smtp_password": "test-private"}
    test_ciphertext = sync.seal(payload, test_key)
    live_ciphertext = sync.seal(sync.unseal(test_ciphertext, test_key, "TEST"), live_key)
    assert test_ciphertext != live_ciphertext
    assert sync.unseal(live_ciphertext, live_key, "LIVE") == payload
    with pytest.raises(RuntimeError, match="CANNOT_DECRYPT"):
        sync.unseal(live_ciphertext, test_key, "TEST")


def test_email_and_github_settings_require_real_credentials():
    assert not sync.mail_ready({"provider": "resend", "smtp_from": "test@example.invalid"})
    assert sync.mail_ready({"provider": "brevo", "smtp_from": "test@example.invalid",
                            "api_key": "configured-token"})
    assert not sync.github_ready({"github_app_id": 10, "github_app_slug": "test-app"})
    assert sync.github_ready({"github_app_id": 10, "github_app_slug": "test-app",
                              "github_client_id": "id", "github_client_secret": "secret",
                              "github_private_key": "key"})


def test_sync_env_parser_only_reads_allowlisted_variables(tmp_path):
    path = tmp_path / ".env"
    path.write_text("PUBLIC_BASE_URL='https://test.opencode-gateway.codes'\n"
                    "APP_PORT=8001\n"
                    "DATABASE_URL='postgresql+psycopg://test:pw@127.0.0.1/db'\n"
                    "CREDENTIALS_ENCRYPTION_KEY='token with spaces'\n"
                    "OTHER_SECRET=not-for-export\n")
    values = sync.env_file(path)
    assert values["CREDENTIALS_ENCRYPTION_KEY"] == "token with spaces"
    assert "OTHER_SECRET" not in values
    with pytest.raises(RuntimeError, match="MISSING_OR_UNSAFE"):
        sync.env_file(tmp_path / "not-found")
