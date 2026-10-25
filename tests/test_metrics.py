"""Pruebas de sysmonitor.metrics con psutil mockeado."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sysmonitor import metrics


def _partition(mountpoint: str) -> SimpleNamespace:
    return SimpleNamespace(mountpoint=mountpoint)


def _usage(percent: float) -> SimpleNamespace:
    return SimpleNamespace(percent=percent, used=50, total=100)


class TestMetrics(unittest.TestCase):
    """Casos de lectura de métricas."""

    @patch("sysmonitor.metrics.psutil.cpu_percent", return_value=42.5)
    def test_get_cpu(self, _cpu: object) -> None:
        self.assertEqual(metrics.get_cpu(interval=0).percent, 42.5)

    @patch("sysmonitor.metrics.psutil.virtual_memory")
    def test_get_memory(self, vm: object) -> None:
        vm.return_value = SimpleNamespace(percent=60.0, used=6, total=10)
        result = metrics.get_memory()
        self.assertEqual((result.percent, result.used_bytes, result.total_bytes),
                         (60.0, 6, 10))

    @patch("sysmonitor.metrics.psutil.net_io_counters")
    def test_get_network(self, net: object) -> None:
        net.return_value = SimpleNamespace(bytes_sent=7, bytes_recv=9)
        result = metrics.get_network()
        self.assertEqual((result.bytes_sent, result.bytes_recv), (7, 9))

    @patch("sysmonitor.metrics.psutil.disk_usage")
    @patch("sysmonitor.metrics.psutil.disk_partitions")
    def test_get_disks_normal(self, parts: object, usage: object) -> None:
        parts.return_value = [_partition("/"), _partition("/home")]
        usage.side_effect = [_usage(10.0), _usage(20.0)]
        result = metrics.get_disks()
        self.assertEqual([d.mountpoint for d in result], ["/", "/home"])
        self.assertEqual([d.percent for d in result], [10.0, 20.0])

    @patch("sysmonitor.metrics.psutil.disk_usage")
    @patch("sysmonitor.metrics.psutil.disk_partitions")
    def test_get_disks_skips_permission_error(
        self, parts: object, usage: object
    ) -> None:
        parts.return_value = [_partition("/"), _partition("/root"), _partition("/home")]
        usage.side_effect = [_usage(10.0), PermissionError(), _usage(30.0)]
        with self.assertLogs("sysmonitor.metrics", level="WARNING") as logs:
            result = metrics.get_disks()
        self.assertEqual([d.mountpoint for d in result], ["/", "/home"])
        self.assertIn("/root", logs.output[0])


if __name__ == "__main__":
    unittest.main()
