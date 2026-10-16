"""Dynamic Preview never starts in Gateway without an accepted isolated worker."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from app.services import preview_runner


class PreviewRunnerReadinessTests(unittest.TestCase):
    def test_start_fails_with_actionable_worker_details(self):
        with patch.object(preview_runner.preview, "detect", return_value={"framework": "node"}):
            with self.assertRaises(HTTPException) as caught:
                preview_runner.start(SimpleNamespace(id="not-used"))
        self.assertEqual(caught.exception.status_code, 503)
        detail = caught.exception.detail
        self.assertEqual(detail["code"], "PREVIEW_WORKER_NOT_READY")
        self.assertEqual(detail["framework"], "node")
        self.assertIs(detail["execution_started"], False)
        self.assertIs(detail["retry_automatically"], False)

    def test_limits_cover_build_admission_estimates(self):
        from app.services.preview_admission import BUILD_REQUIREMENTS
        cpu, ram, disk = BUILD_REQUIREMENTS
        self.assertGreaterEqual(preview_runner.LIMITS["cpu_cores"] * 1000, cpu)
        self.assertGreaterEqual(preview_runner.LIMITS["memory_mb"], ram)
        self.assertGreaterEqual(preview_runner.LIMITS["disk_mb"], disk)


if __name__ == "__main__":
    unittest.main()
