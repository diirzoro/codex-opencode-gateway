"""Tests for read-only host probe; fake filesystems, no VPS actions."""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from app.services.preview_host_probe import read_host_telemetry


class HostProbeTests(unittest.TestCase):
    @patch("app.services.preview_host_probe.disk_usage")
    @patch("app.services.preview_host_probe.Path.read_text")
    def test_reads_ram_and_storage_without_attesting_itself(self, mem, disk):
        mem.return_value = "MemTotal: 4194304 kB\nMemAvailable: 3145728 kB\n"
        disk.return_value = SimpleNamespace(total=80 * 1024**3, free=12 * 1024**3)
        result = read_host_telemetry(storage=Path("/var/lib/preview"), active_previews=0)
        self.assertEqual(result.total_ram_mb, 4096)
        self.assertEqual(result.available_ram_mb, 3072)
        self.assertEqual(result.free_disk_mb, 12288)
        self.assertFalse(result.collector_verified)

    @patch("app.services.preview_host_probe.Path.read_text", return_value="MemTotal: 4194304 kB\n")
    def test_missing_mem_available_fails_closed(self, _):
        with self.assertRaises(ValueError):
            read_host_telemetry(storage=Path("/var/lib/preview"), active_previews=0)


if __name__ == "__main__":
    unittest.main()
