"""BYOK verification and Pi-native fallback; no network or account data."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routes import management


def test_pi_native_provider_without_safe_probe_is_not_falsely_verified(monkeypatch):
    class NeverClient:
        def __init__(self, **kwargs):
            raise AssertionError("Unknown native provider must not probe arbitrary URLs")
    monkeypatch.setattr(management._ai_httpx, "Client", NeverClient)
    assert management._ai_verify("kimi-coding", "sample-secret-key") == "untested"


def test_opencode_zen_models_are_checked_on_a_fixed_url(monkeypatch):
    calls = []
    class Client:
        def __init__(self, **kw):
            assert kw["follow_redirects"] is False
            assert kw["trust_env"] is False
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url, headers):
            calls.append((url, headers))
            return SimpleNamespace(status_code=200, json=lambda: {"data": [{"id": "sample-model"}]})
    monkeypatch.setattr(management._ai_httpx, "Client", Client)
    assert management._ai_verify("opencode", "test-key") == "unknown"
    assert calls == [("https://opencode.ai/inference/v1/models", {
        "Accept": "application/json", "Authorization": "Bearer test-key"})]


def test_opencode_go_uses_non_inference_usage_probe(monkeypatch):
    calls = []
    class Client:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url, headers):
            calls.append(url)
            return SimpleNamespace(status_code=200, json=lambda: {"usage": {"requests": 0}})
    monkeypatch.setattr(management._ai_httpx, "Client", Client)
    assert management._ai_verify("opencode-go", "test-key") == "unknown"
    assert calls == ["https://opencode.ai/inference/go/v1/usage"]


def test_invalid_key_is_never_saved_as_verified(monkeypatch):
    class Client:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url, headers):
            return SimpleNamespace(status_code=401)
    monkeypatch.setattr(management._ai_httpx, "Client", Client)
    with pytest.raises(HTTPException) as err:
        management._ai_verify("opencode-go", "invalid-key")
    assert err.value.status_code == 422


def test_untested_status_is_connected_but_not_verified():
    item = management._ai_connection_payload(SimpleNamespace(
        id="connection-id", provider_id="kimi-coding", auth_status="untested",
        credit_status="untested", last4="last", verified_at="some-date"))
    assert item["connected"] is True
    assert item["verified"] is False
    assert item["verified_at"] is None


def test_oauth_only_providers_not_advertised_as_api_key_providers():
    assert {"openai-codex", "github-copilot"} <= management._AI_OAUTH_ONLY_PROVIDERS
    assert "openai" not in management._AI_OAUTH_ONLY_PROVIDERS
