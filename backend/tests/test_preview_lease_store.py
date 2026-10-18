"""Lease transaction behavior tested without deployment DB or customer execution."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.services import preview_lease_store

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)


class FakeDB:
    def __init__(self):
        self.flushed = False

    def flush(self):
        self.flushed = True


class PreviewLeaseStoreTests(unittest.TestCase):
    def setUp(self):
        self.owner = uuid4()
        self.workspace = uuid4()
        self.row = SimpleNamespace(user_id=self.owner, workspace_id=self.workspace,
                                   state="stopped", generation=0, worker_id=None,
                                   pool_id="old-pool", last_user_activity_at=NOW,
                                   started_at=None, expires_at=NOW)
        self.db = FakeDB()

    def update(self, event, at=NOW):
        with patch.object(preview_lease_store, "owned_for_update", return_value=self.row) as locked:
            updated = preview_lease_store.apply_transition(
                self.db, user_id=self.owner, workspace_id=self.workspace,
                event=event, now=at)
            locked.assert_called_once_with(self.db, user_id=self.owner,
                                           workspace_id=self.workspace)
            return updated

    def test_restart_clears_previous_allocation(self):
        row = self.update("start")
        self.assertEqual(row.state, "queued")
        self.assertEqual(row.generation, 1)
        self.assertIsNone(row.worker_id)
        self.assertIsNone(row.pool_id)
        self.assertIsNone(row.expires_at)
        self.assertTrue(self.db.flushed)

    def test_restart_rejected_until_old_worker_released(self):
        self.row.worker_id = "old-worker"
        with self.assertRaises(ValueError):
            self.update("start")
        self.assertEqual(self.row.generation, 0)
        self.assertEqual(self.row.worker_id, "old-worker")

    def test_stop_rejected_before_worker_cleanup(self):
        self.row.state = "running"
        self.row.worker_id = "still-running"
        with self.assertRaises(ValueError):
            self.update("stop")
        self.assertEqual(self.row.state, "running")

    def test_unauthorized_transition_fails_closed(self):
        with self.assertRaises(ValueError):
            self.update("worker_started")
        self.assertEqual(self.row.state, "stopped")
        self.assertFalse(self.db.flushed)

    def test_running_idle_expiry_marks_expired(self):
        self.row.state = "running"
        self.update("idle_expired", NOW + timedelta(seconds=300))
        self.assertEqual(self.row.state, "expired")
        self.assertEqual(self.row.expires_at, NOW + timedelta(seconds=300))

    def test_missing_owner_lease_does_not_create_a_new_one(self):
        with patch.object(preview_lease_store, "owned_for_update", return_value=None):
            with self.assertRaises(LookupError):
                preview_lease_store.apply_transition(
                    self.db, user_id=self.owner, workspace_id=self.workspace,
                    event="start", now=NOW)


if __name__ == "__main__":
    unittest.main()
