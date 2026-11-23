"""Regression tests: never persist provider API keys without real authentication.

Mocks never transmit real secrets, make live network requests, or touch accounts.
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from app.routes import management


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def get(self, url, headers):
        self.calls.append((url, headers))
        return self.response


def patch_http(monkeypatch, response):
    client = FakeClient(response)

    def make_client(**kwargs):
        assert kwargs["follow_redirects"] is False
        assert kwargs["trust_env"] is False
        return client

    monkeypatch.setattr(management._ai_httpx, "Client", make_client)
    return client


def test_unknown_provider_fails_closed_without_any_outbound_probe(monkeypatch):
    def never_client(**kwargs):
        raise AssertionError("Unknown providers must not trigger network requests")
    monkeypatch.setattr(management._ai_httpx, "Client", never_client)
    with pytest.raises(HTTPException) as exc:
        management._ai_verify("unconfigured-pi-provider", "dummy-key-for-test")
    assert exc.value.status_code == 422


def test_authenticated_opencode_zen_console_models(monkeypatch):
    response = SimpleNamespace(status_code=200, json=lambda: {
        "opencode": {"id": "opencode", "models": {"example": {"id": "example"}}}})
    client = patch_http(monkeypatch, response)
    assert management._ai_verify("opencode", "dummy-key-for-test") == "unknown"
    assert client.calls == [("https://opencode.ai/console/api/v1/models", {
        "Accept": "application/json", "Authorization": "Bearer dummy-key-for-test"})]


def test_zen_rejects_public_openai_list_shape(monkeypatch):
    patch_http(monkeypatch, SimpleNamespace(status_code=200, json=lambda: {
        "data": [{"id": "public-model"}]}))
    with pytest.raises(HTTPException) as exc:
        management._ai_verify("opencode", "dummy-key-for-test")
    assert exc.value.status_code == 503


def test_go_rejects_200_without_go_subscription(monkeypatch):
    patch_http(monkeypatch, SimpleNamespace(status_code=200, json=lambda: {
        "opencode": {"id": "opencode", "models": {"example": {}}}}))
    with pytest.raises(HTTPException) as exc:
        management._ai_verify("opencode-go", "dummy-key-for-test")
    assert exc.value.status_code == 403


def test_go_accepts_authenticated_active_go_models(monkeypatch):
    response = SimpleNamespace(status_code=200, json=lambda: {
        "opencode-go": {
            "id": "opencode-go",
            "models": {"example-go-model": {"id": "example-go-model"}}}})
    client = patch_http(monkeypatch, response)
    assert management._ai_verify("opencode-go", "dummy-key-for-test") == "unknown"
    assert client.calls[0][0] == "https://opencode.ai/console/api/v1/models"


@pytest.mark.parametrize("provider,status,expected", [
    ("opencode", 401, 422),
    ("opencode-go", 403, 403),
    ("openai", 401, 422),
    ("deepseek", 429, 429),
])
def test_failed_authentication_never_succeeds(monkeypatch, provider, status, expected):
    patch_http(monkeypatch, SimpleNamespace(status_code=status))
    with pytest.raises(HTTPException) as exc:
        management._ai_verify(provider, "dummy-key-for-test")
    assert exc.value.status_code == expected


def test_unknown_pi_provider_key_never_reaches_db_storage(monkeypatch):
    monkeypatch.setattr(management, "_ai_schema", lambda db: None)
    monkeypatch.setattr(management, "_ai_pi_supported_providers",
                        lambda db: [{"id": "supported-but-no-verifier"}])
    monkeypatch.setattr(management.credentials, "available", lambda: True)

    class FakeDB:
        def scalar(self, *args, **kwargs):
            return None
        def add(self, *args, **kwargs):
            raise AssertionError("Must not save unverified key")
        def commit(self):
            raise AssertionError("Must not commit unverified key")

    with pytest.raises(HTTPException) as exc:
        management._ai_save(SimpleNamespace(
            provider_id="supported-but-no-verifier",
            api_key="dummy-key-for-test"),
            SimpleNamespace(id="account-id"), FakeDB())
    assert exc.value.status_code == 422


def test_verified_connection_payload_preserves_existing_contract():
    item = management._ai_connection_payload(SimpleNamespace(
        id="connection-id", provider_id="openai", auth_status="verified",
        credit_status="unknown", last4="last", verified_at="some-date"))
    assert item["connected"] is True
    assert item["verified"] is True


def test_nvidia_uses_authenticated_real_inference_before_accepting_key(monkeypatch):
    calls = []
    class Client:
        def __init__(self, **kwargs):
            assert kwargs["trust_env"] is False
            assert kwargs["follow_redirects"] is False
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url, headers):
            calls.append(("get", url, headers))
            return SimpleNamespace(status_code=200, json=lambda: {
                "data": [{"id": "meta/llama-3.1-8b-instruct"}]})
        def post(self, url, headers, json):
            calls.append(("post", url, json))
            return SimpleNamespace(status_code=200, json=lambda: {
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "OK"}}]})
    monkeypatch.setattr(management._ai_httpx, "Client", Client)
    assert management._ai_verify("nvidia", "dummy-key-for-test") == "unknown"
    assert calls[0][1] == "https://integrate.api.nvidia.com/v1/models"
    assert calls[0][2]["Authorization"] == "Bearer dummy-key-for-test"
    assert calls[1][1] == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert calls[1][2]["max_tokens"] == 1


@pytest.mark.parametrize("status,expected", [(401, 422), (403, 403), (402, 402), (429, 429), (503, 503)])
def test_nvidia_model_catalog_success_does_not_bypass_inference_failure(monkeypatch, status, expected):
    class Client:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url, headers):
            return SimpleNamespace(status_code=200, json=lambda: {
                "data": [{"id": "meta/llama-3.1-8b-instruct"}]})
        def post(self, url, headers, json):
            return SimpleNamespace(status_code=status)
    monkeypatch.setattr(management._ai_httpx, "Client", Client)
    with pytest.raises(HTTPException) as exc:
        management._ai_verify("nvidia", "dummy-key-for-test")
    assert exc.value.status_code == expected


def test_nvidia_inference_failure_prevents_key_persistence(monkeypatch):
    monkeypatch.setattr(management, "_ai_schema", lambda db: None)
    monkeypatch.setattr(management, "_ai_pi_supported_providers",
                        lambda db: [{"id": "nvidia"}])
    monkeypatch.setattr(management.credentials, "available", lambda: True)
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, url, headers):
            return SimpleNamespace(status_code=200, json=lambda: {
                "data": [{"id": "meta/llama-3.1-8b-instruct"}]})
        def post(self, url, headers, json):
            return SimpleNamespace(status_code=403)
    monkeypatch.setattr(management._ai_httpx, "Client", Client)
    class FakeDB:
        def scalar(self, *args, **kwargs): return None
        def add(self, *args, **kwargs):
            raise AssertionError("Must not save NVIDIA key")
        def commit(self):
            raise AssertionError("Must not commit NVIDIA key")
    with pytest.raises(HTTPException) as exc:
        management._ai_save(SimpleNamespace(provider_id="nvidia",
             api_key="dummy-key-for-test"), SimpleNamespace(id="account-id"), FakeDB())
    assert exc.value.status_code == 403
