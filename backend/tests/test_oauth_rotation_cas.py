"""Focused, offline tenant-scoped OAuth rotation concurrency guard tests.

These are mock-level tests. Native PostgreSQL concurrent transactions and real
OpenCode OAuth refresh are separate unresolved release gates.
"""
import os
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("DATABASE_URL","postgresql+psycopg://test:test@127.0.0.1/test")
from backend.app.services import user_provider_credentials as store


def test_current_ciphertext_can_be_replaced_without_committing():
    db=Mock()
    row=SimpleNamespace(ciphertext="old-encrypted")
    db.scalar.return_value=row
    assert store.replace_encrypted_if_current(db,"user-one","provider","old-encrypted","new-encrypted")
    assert row.ciphertext=="new-encrypted"
    db.commit.assert_not_called()


def test_stale_refresh_cannot_overwrite_newer_ciphertext():
    db=Mock()
    row=SimpleNamespace(ciphertext="already-rotated")
    db.scalar.return_value=row
    assert not store.replace_encrypted_if_current(db,"user-one","provider","old-encrypted","stale-encrypted")
    assert row.ciphertext=="already-rotated"
    db.commit.assert_not_called()


def test_deleted_connection_is_not_recreated_on_late_rotation():
    db=Mock()
    db.scalar.return_value=None
    assert not store.replace_encrypted_if_current(db,"user-one","provider","old","new")
    db.add.assert_not_called()
    db.commit.assert_not_called()
