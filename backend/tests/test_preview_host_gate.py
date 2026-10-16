"""Conservative one-slot VPS headroom policy tests; no live host metrics."""
import unittest
from app.services.preview_host_gate import HostTelemetry, permit_preview

class HostGateTests(unittest.TestCase):
    def test_healthy_one_slot_host(self):
        host = HostTelemetry(4096, 2800, 81920, 15000, 0, True)
        self.assertTrue(permit_preview(host)["admitted"])

    def test_missing_or_unverified_telemetry_fails_closed(self):
        self.assertFalse(permit_preview(None)["admitted"])
        self.assertFalse(permit_preview(HostTelemetry(4096, 2800, 81920, 15000, 0, False))["admitted"])

    def test_a_second_preview_is_rejected(self):
        self.assertFalse(permit_preview(HostTelemetry(4096, 2800, 81920, 15000, 1, True))["admitted"])

    def test_low_ram_is_rejected(self):
        self.assertFalse(permit_preview(HostTelemetry(4096, 1700, 81920, 15000, 0, True))["admitted"])

    def test_low_disk_is_rejected(self):
        self.assertFalse(permit_preview(HostTelemetry(4096, 2800, 81920, 3000, 0, True))["admitted"])

    def test_invalid_readings_are_rejected(self):
        self.assertFalse(permit_preview(HostTelemetry(4096, 5000, 81920, 15000, 0, True))["admitted"])
        self.assertFalse(permit_preview(HostTelemetry(4096, True, 81920, 15000, 0, True))["admitted"])

if __name__ == "__main__":
    unittest.main()
