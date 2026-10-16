"""Unit tests of capacity reservation; no real PostgreSQL or runner started."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.services import preview_capacity_store

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)


class FakeDB:
    def __init__(self, *rows):
        self.rows = list(rows)
        self.flushes = 0

    def scalar(self, query):
        return self.rows.pop(0)

    def flush(self):
        self.flushes += 1


class PreviewCapacityStoreTests(unittest.TestCase):
    def setUp(self):
        self.owner = uuid4()
        self.workspace = uuid4()
        self.worker = SimpleNamespace(worker_id="verified-1", isolated=True, security_verified=True,
                                      reachable=True, cpu_free_millicores=2000, memory_free_mb=2048,
                                      disk_free_mb=4096, active_jobs=0, max_jobs=1,
                                      observed_at=NOW - timedelta(seconds=5),
                                      isolation_verified_at=NOW - timedelta(seconds=10))
        self.lease = SimpleNamespace(user_id=self.owner, workspace_id=self.workspace,
                                     state="queued", generation=3, worker_id=None)

    def test_slot_reserved_once(self):
        db = FakeDB(self.worker, self.lease)
        self.assertTrue(preview_capacity_store.reserve(
            db, user_id=self.owner, workspace_id=self.workspace, worker_id="verified-1",
            generation=3, framework="vite", now=NOW))
        self.assertEqual(self.worker.active_jobs, 1)
        self.assertEqual(self.lease.state, "starting")
        self.assertEqual(self.lease.worker_id, "verified-1")
        self.assertEqual(db.flushes, 1)

    def test_stale_heartbeat_cannot_reserve(self):
        self.worker.observed_at = NOW - timedelta(seconds=90)
        db = FakeDB(self.worker, self.lease)
        self.assertFalse(preview_capacity_store.reserve(
            db, user_id=self.owner, workspace_id=self.workspace, worker_id="verified-1",
            generation=3, framework="vite", now=NOW))
        self.assertEqual(self.worker.active_jobs, 0)

    def test_generation_mismatch_cannot_reserve(self):
        db = FakeDB(self.worker, self.lease)
        self.assertFalse(preview_capacity_store.reserve(
            db, user_id=self.owner, workspace_id=self.workspace, worker_id="verified-1",
            generation=2, framework="vite", now=NOW))

    def test_release_is_idempotent(self):
        self.lease.state = "starting"
        self.lease.worker_id = "verified-1"
        self.worker.active_jobs = 1
        db = FakeDB(self.lease, self.worker, self.lease)
        self.assertTrue(preview_capacity_store.release(
            db, user_id=self.owner, workspace_id=self.workspace, generation=3))
        self.assertEqual(self.worker.active_jobs, 0)
        self.assertIsNone(self.lease.worker_id)
        db2 = FakeDB(self.lease)
        self.assertFalse(preview_capacity_store.release(
            db2, user_id=self.owner, workspace_id=self.workspace, generation=3))

    def test_exhausted_worker_refuses_new_job(self):
        self.worker.active_jobs = 1
        db = FakeDB(self.worker, self.lease)
        self.assertFalse(preview_capacity_store.reserve(
            db, user_id=self.owner, workspace_id=self.workspace, worker_id="verified-1",
            generation=3, framework="python", now=NOW))
        self.assertEqual(db.flushes, 0)


if __name__ == "__main__":
    unittest.main()
