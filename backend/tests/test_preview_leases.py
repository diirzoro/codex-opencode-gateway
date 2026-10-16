"""Unit tests of preview lease transitions; no runtime is started."""
import unittest
from datetime import datetime, timedelta, timezone
from app.services.preview_leases import PreviewLease, transition, should_expire

T0 = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)

class PreviewLeaseTests(unittest.TestCase):
    def lease(self, state="stopped"):
        return PreviewLease("owner-A", "workspace-A", state, T0)

    def test_manual_start_and_worker_lifecycle(self):
        queued = transition(self.lease(), "start", now=T0)
        self.assertEqual(queued.state, "queued")
        starting = transition(queued, "worker_reserved", now=T0)
        running = transition(starting, "worker_started", now=T0)
        self.assertEqual(running.state, "running")
        self.assertFalse(should_expire(running, now=T0 + timedelta(seconds=299)))
        self.assertTrue(should_expire(running, now=T0 + timedelta(seconds=300)))

    def test_genuine_activity_extends_idle_not_polls(self):
        running = self.lease("running")
        with self.assertRaises(ValueError):
            transition(running, "status_poll", now=T0 + timedelta(seconds=250))
        touched = transition(running, "user_activity", now=T0 + timedelta(seconds=250))
        self.assertFalse(should_expire(touched, now=T0 + timedelta(seconds=500)))
        self.assertTrue(should_expire(touched, now=T0 + timedelta(seconds=550)))

    def test_expired_requires_explicit_new_start(self):
        expired = transition(self.lease("running"), "idle_expired", now=T0 + timedelta(seconds=300))
        self.assertEqual(expired.state, "expired")
        for event in ("worker_started", "user_activity", "status_poll"):
            with self.subTest(event=event), self.assertRaises(ValueError):
                transition(expired, event, now=T0 + timedelta(seconds=301))
        self.assertEqual(transition(expired, "start", now=T0 + timedelta(seconds=302)).state, "queued")

    def test_stop_no_automatic_resume(self):
        stopped = transition(self.lease("running"), "stop", now=T0)
        self.assertEqual(stopped.state, "stopped")
        with self.assertRaises(ValueError):
            transition(stopped, "worker_reserved", now=T0)

    def test_timezone_aware_only(self):
        with self.assertRaises(ValueError):
            should_expire(self.lease("running"), now=datetime(2026, 10, 16))

if __name__ == "__main__":
    unittest.main()
