"""Worker liveness/attestation admission tests; no actual runner required."""
import unittest
from datetime import datetime, timedelta, timezone
from app.services.preview_admission import WorkerCapacity
from app.services.preview_worker_registry import WorkerHeartbeat, available_worker, select_worker

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)
CAPACITY = WorkerCapacity("isolated-worker-1", True, True, 2000, 2048, 4096, 0, 2, True)

class WorkerRegistryTests(unittest.TestCase):
    def test_recent_worker_can_request_lease(self):
        hb = WorkerHeartbeat(CAPACITY, NOW - timedelta(seconds=10), NOW - timedelta(seconds=15))
        self.assertEqual(available_worker({"framework": "vite"}, hb, now=NOW)["action"], "request_durable_lease")

    def test_stale_heartbeat_fails_closed(self):
        hb = WorkerHeartbeat(CAPACITY, NOW - timedelta(seconds=31), NOW - timedelta(seconds=35))
        self.assertFalse(available_worker({"framework": "python"}, hb, now=NOW)["admitted"])

    def test_stale_attestation_fails_closed(self):
        hb = WorkerHeartbeat(CAPACITY, NOW - timedelta(seconds=10), NOW - timedelta(seconds=60))
        self.assertFalse(available_worker({"framework": "node"}, hb, now=NOW)["admitted"])

    def test_future_timestamps_are_not_accepted(self):
        hb = WorkerHeartbeat(CAPACITY, NOW + timedelta(seconds=1), NOW)
        self.assertFalse(available_worker({"framework": "node"}, hb, now=NOW)["admitted"])

    def test_selects_healthy_candidate_not_stale_worker(self):
        stale = WorkerHeartbeat(CAPACITY, NOW - timedelta(seconds=50), NOW - timedelta(seconds=50))
        smaller = WorkerCapacity("small", True, True, 1200, 1024, 2048, 0, 1, True)
        fresh = WorkerHeartbeat(smaller, NOW - timedelta(seconds=2), NOW - timedelta(seconds=3))
        selected = select_worker({"framework": "node"}, (stale, fresh), now=NOW)
        self.assertEqual(selected["worker_id"], "small")
        self.assertEqual(selected["action"], "request_durable_lease")

    def test_zero_eligible_workers_cannot_start(self):
        self.assertFalse(select_worker({"framework": "vite"}, (), now=NOW)["admitted"])

    def test_no_worker_fails_closed(self):
        self.assertFalse(available_worker({"framework": "vite"}, None, now=NOW)["admitted"])

if __name__ == "__main__":
    unittest.main()
