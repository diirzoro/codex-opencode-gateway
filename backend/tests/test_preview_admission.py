"""Read-only secure admission decisions; no containers are started."""
import unittest
from app.services.preview_admission import WorkerCapacity, assess_worker, request_start

GOOD = WorkerCapacity("test-worker", True, True, 2000, 2048, 4096, 0, 2, True)

class WorkerAdmissionTests(unittest.TestCase):
    def test_preview_never_auto_starts(self):
        for framework in ("html", "vite", "python"):
            with self.subTest(framework=framework):
                result = request_start({"framework": framework}, GOOD, explicit_start=False)
                self.assertFalse(result["admitted"])
                self.assertEqual(result["action"], "await_user_start")

    def test_explicit_start_only_checks_eligibility(self):
        result = request_start({"framework": "vite"}, GOOD, explicit_start=True)
        self.assertEqual(result["action"], "request_durable_lease")

    def test_static_needs_no_worker(self):
        self.assertEqual(assess_worker({"framework": "html"}, None)["action"], "serve_static")

    def test_unknown_is_not_executed(self):
        self.assertFalse(assess_worker({"framework": "unknown"}, GOOD)["admitted"])

    def test_no_verified_worker_fails_closed(self):
        self.assertFalse(assess_worker({"framework": "vite"}, None)["admitted"])
        unverified = WorkerCapacity("w", True, False, 9999, 9999, 9999, 0, 100, True)
        self.assertFalse(assess_worker({"framework": "python"}, unverified)["admitted"])
        offline = WorkerCapacity("w", True, True, 9999, 9999, 9999, 0, 100, False)
        self.assertFalse(assess_worker({"framework": "python"}, offline)["admitted"])

    def test_measured_capacity_and_queue(self):
        too_small = WorkerCapacity("w", True, True, 500, 256, 200, 0, 1, True)
        self.assertEqual(assess_worker({"framework": "vite"}, too_small)["action"], "queue")
        full = WorkerCapacity("w", True, True, 2000, 4096, 4096, 2, 2, True)
        self.assertEqual(assess_worker({"framework": "node"}, full)["action"], "queue")

    def test_admission_does_not_start_execution(self):
        outcome = assess_worker({"framework": "python"}, GOOD)
        self.assertEqual(outcome["action"], "request_durable_lease")
        self.assertEqual(outcome["worker_id"], "test-worker")

    def test_ambiguous_next_needs_inspection(self):
        self.assertFalse(assess_worker({"framework": "nextjs"}, GOOD)["admitted"])

    def test_invalid_registry_metrics_fail_closed(self):
        invalid = WorkerCapacity("w", True, True, -1, 1000, 1000, 0, 2, True)
        self.assertFalse(assess_worker({"framework": "node"}, invalid)["admitted"])

if __name__ == "__main__":
    unittest.main()
