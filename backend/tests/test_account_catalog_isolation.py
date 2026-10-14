"""Public discovery may use an owned runtime, never another user's cached data."""
import os
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1/test")
from backend.app.services import opencode_catalog as catalog


def test_public_catalog_is_scoped_to_runtime_and_does_not_close_it(monkeypatch):
    monkeypatch.setattr(catalog, "_catalog_cache", {})
    def service(generation, provider):
        return SimpleNamespace(generation=generation, close=Mock(), request=Mock(return_value={
            "all":[{"id":provider,"name":provider,"models":{"model":{"key":"must-not-return"}},"apiKey":"private"}],
            "connected":[provider],"secret":"must-not-return"}))
    first, second=service("owner-a", "first"), service("owner-b", "second")
    a=catalog.public_catalog("/provider", service=first)
    b=catalog.public_catalog("/provider", service=second)
    assert a["all"][0]["id"] == "first" and b["all"][0]["id"] == "second"
    assert a["connected"] == [] and a["all"][0]["models"] == {"model":None}
    assert "apiKey" not in a["all"][0] and "secret" not in a
    a["all"].clear()
    assert catalog.public_catalog("/provider", service=first)["all"]
    first.request.assert_called_once()
    first.close.assert_not_called();second.close.assert_not_called()


def test_schema_check_reuses_request_transaction(monkeypatch):
    from backend.app.services import user_provider_credentials
    connection=object();db=Mock();db.connection.return_value=connection
    inspect=Mock();inspect.return_value.has_table.return_value=True
    monkeypatch.setattr(user_provider_credentials,"inspect",inspect)
    user_provider_credentials.require_schema(db)
    inspect.assert_called_once_with(connection)
    db.get_bind.assert_not_called()
