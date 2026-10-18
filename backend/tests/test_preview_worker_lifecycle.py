"""Isolated worker lifecycle policy tests; no runtime is invoked."""
import unittest
from datetime import datetime, timedelta, timezone
from app.services.preview_worker_lifecycle import (
    WorkerJob, may_launch, started, activity, needs_cleanup, stopped,
)

T0 = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)


class PreviewWorkerLifecycleTests(unittest.TestCase):
    def job(self):
        return WorkerJob("job-1", 2, "queued", T0)

    def test_manual_start_only(self):
        self.assertFalse(may_launch(self.job(), explicit_start=False))
        self.assertTrue(may_launch(self.job(), explicit_start=True))
        self.assertFalse(may_launch(started(self.job(), "container-1"), explicit_start=True))

    def test_poll_does_not_extend_timeout(self):
        job = started(self.job(), "container-1")
        polled = activity(job, at=T0 + timedelta(seconds=299), genuine_user_action=False)
        self.assertEqual(polled.last_user_activity, T0)
        self.assertTrue(needs_cleanup(polled, now=T0 + timedelta(seconds=300)))

    def test_user_activity_extends_idle(self):
        job = started(self.job(), "container-1")
        updated = activity(job, at=T0 + timedelta(seconds=200), genuine_user_action=True)
        self.assertFalse(needs_cleanup(updated, now=T0 + timedelta(seconds=300)))
        self.assertTrue(needs_cleanup(updated, now=T0 + timedelta(seconds=500)))

    def test_late_activity_cannot_resurrect_expired(self):
        job = started(self.job(), "container-1")
        unchanged = activity(job, at=T0 + timedelta(seconds=301), genuine_user_action=True)
        self.assertEqual(unchanged.last_user_activity, T0)

    def test_cleanup_requires_both_confirmations(self):
        job = started(self.job(), "container-1")
        with self.assertRaises(ValueError):
            stopped(job, routing_revoked=True, container_destroyed=False)
        with self.assertRaises(ValueError):
            stopped(job, routing_revoked=False, container_destroyed=True)
        done = stopped(job, routing_revoked=True, container_destroyed=True)
        self.assertEqual(done.state, "stopped")
        self.assertIsNone(done.container_id)


if __name__ == "__main__":
    unittest.main()
