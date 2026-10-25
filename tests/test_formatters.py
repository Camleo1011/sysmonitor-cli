"""Pruebas de sysmonitor.formatters."""

import json
import unittest

from sysmonitor.formatters import format_bytes, format_json, format_text
from sysmonitor.metrics import (
    CpuMetrics,
    DiskMetrics,
    MemoryMetrics,
    NetworkMetrics,
    Snapshot,
)

SNAPSHOT = Snapshot(
    cpu=CpuMetrics(percent=12.5),
    memory=MemoryMetrics(percent=50.0, used_bytes=1024**3, total_bytes=2 * 1024**3),
    disks=[DiskMetrics("/", 30.0, 3 * 1024**3, 10 * 1024**3)],
    network=NetworkMetrics(bytes_sent=2048, bytes_recv=512),
)


class TestFormatters(unittest.TestCase):
    """Casos de salida en texto y JSON."""

    def test_format_bytes(self) -> None:
        self.assertEqual(format_bytes(0), "0.0 B")
        self.assertEqual(format_bytes(1536), "1.5 KiB")
        self.assertEqual(format_bytes(1024**3), "1.0 GiB")

    def test_text_contains_all_metrics(self) -> None:
        text = format_text(SNAPSHOT)
        self.assertIn("CPU: 12.5%", text)
        self.assertIn("RAM: 50.0% (1.0 GiB / 2.0 GiB)", text)
        self.assertIn("/: 30.0%", text)
        self.assertIn("sent 2.0 KiB", text)
        self.assertIn("received 512.0 B", text)

    def test_json_is_valid_and_complete(self) -> None:
        data = json.loads(format_json(SNAPSHOT))
        self.assertEqual(data["cpu"]["percent"], 12.5)
        self.assertEqual(data["memory"]["total_bytes"], 2 * 1024**3)
        self.assertEqual(data["disks"][0]["mountpoint"], "/")
        self.assertEqual(data["network"]["bytes_sent"], 2048)

    def test_json_with_no_disks(self) -> None:
        empty = Snapshot(SNAPSHOT.cpu, SNAPSHOT.memory, [], SNAPSHOT.network)
        self.assertEqual(json.loads(format_json(empty))["disks"], [])


if __name__ == "__main__":
    unittest.main()
