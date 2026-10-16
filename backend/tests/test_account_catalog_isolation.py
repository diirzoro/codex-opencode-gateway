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


def test_slow_user_catalog_does_not_block_another_user(monkeypatch):
    from threading import Event
    from concurrent.futures import ThreadPoolExecutor
    started,release=Event(),Event()
    monkeypatch.setattr(catalog,'_catalog_cache',{})
    def slow_request(*args):
        started.set();assert release.wait(3)
        return {'all':[{'id':'slow-owner','models':{}}]}
    slow=SimpleNamespace(generation='slow',request=slow_request,close=Mock())
    fast=SimpleNamespace(generation='fast',request=Mock(return_value={'all':[{'id':'fast-owner','models':{}}]}),close=Mock())
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(catalog.public_catalog,'/provider',service=slow)
        assert started.wait(1)
        try:
            second=pool.submit(catalog.public_catalog,'/provider',service=fast)
            assert second.result(timeout=1)['all'][0]['id']=='fast-owner'
        finally:release.set()
        assert first.result(timeout=1)['all'][0]['id']=='slow-owner'


def test_catalog_metadata_revision_invalidates_cache(monkeypatch):
    monkeypatch.setattr(catalog,'_catalog_cache',{})
    service=SimpleNamespace(generation='owner',discovery_revision=0,close=Mock(),request=Mock(side_effect=[{'all':[{'id':'before','models':{}}]},{'all':[{'id':'after','models':{}}]}]))
    assert catalog.public_catalog('/provider',service=service)['all'][0]['id']=='before'
    service.discovery_revision+=1
    assert catalog.public_catalog('/provider',service=service)['all'][0]['id']=='after'


def test_metadata_method_cache_copies_and_invalidates(monkeypatch):
    from backend.app.services import providers,opencode
    service=opencode.OpenCodeService('http://127.0.0.1:1')
    discover=Mock(return_value=[{'type':'api','label':'Runtime schema'}])
    monkeypatch.setattr(providers,'_discover_connection_methods',discover)
    try:
        first=providers.connection_methods(service,'fixture');first[0]['label']='mutated'
        assert providers.connection_methods(service,'fixture')[0]['label']=='Runtime schema'
        assert discover.call_count==1
        service.invalidate();providers.connection_methods(service,'fixture');assert discover.call_count==2
    finally:service.close()
