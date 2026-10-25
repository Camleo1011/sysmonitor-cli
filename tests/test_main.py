"""Pruebas de sysmonitor.main (CLI)."""

import argparse
import contextlib
import io
import json
import unittest
from unittest.mock import MagicMock, patch

import requests

from sysmonitor import __version__
from sysmonitor.main import main, percentage, positive_int
from sysmonitor.metrics import (
    CpuMetrics,
    DiskMetrics,
    MemoryMetrics,
    NetworkMetrics,
    Snapshot,
)

SNAPSHOT = Snapshot(
    cpu=CpuMetrics(10.0),
    memory=MemoryMetrics(20.0, 2, 10),
    disks=[DiskMetrics("/", 30.0, 3, 10)],
    network=NetworkMetrics(1, 2),
)


def run(argv: list[str]) -> tuple[int, str, str]:
    """Ejecuta main capturando stdout y stderr."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def run_exit(argv: list[str]) -> int:
    """Ejecuta main esperando SystemExit y devuelve su código."""
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(
        io.StringIO()
    ):
        with unittest.TestCase().assertRaises(SystemExit) as ctx:
            main(argv)
    return ctx.exception.code


class TestValidators(unittest.TestCase):
    """Validadores type= de argparse."""

    def test_percentage_bounds(self) -> None:
        self.assertEqual(percentage("0"), 0.0)
        self.assertEqual(percentage("100"), 100.0)
        for bad in ("100.1", "-1", "abc", "nan"):
            with self.assertRaises(argparse.ArgumentTypeError):
                percentage(bad)

    def test_positive_int(self) -> None:
        self.assertEqual(positive_int("1"), 1)
        for bad in ("0", "-5", "1.5", "x"):
            with self.assertRaises(argparse.ArgumentTypeError):
                positive_int(bad)


class TestMain(unittest.TestCase):
    """Comportamiento de la CLI."""

    def test_invalid_args_exit_2(self) -> None:
        self.assertEqual(run_exit(["--cpu-threshold", "101"]), 2)
        self.assertEqual(run_exit(["--mem-threshold", "-1"]), 2)
        self.assertEqual(run_exit(["--interval", "0"]), 2)
        self.assertEqual(run_exit(["--format", "xml"]), 2)

    def test_version(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as ctx:
            main(["--version"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn(__version__, out.getvalue())

    @patch("sysmonitor.main.collect_snapshot", return_value=SNAPSHOT)
    def test_once_json_is_parseable(self, _snap: object) -> None:
        code, out, _ = run(["--once", "--format", "json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["cpu"]["percent"], 10.0)

    @patch("sysmonitor.main.collect_snapshot", return_value=SNAPSHOT)
    def test_once_text(self, _snap: object) -> None:
        code, out, _ = run(["--once"])
        self.assertEqual(code, 0)
        self.assertIn("CPU: 10.0%", out)

    @patch("sysmonitor.main.time.sleep", side_effect=KeyboardInterrupt)
    @patch("sysmonitor.main.collect_snapshot", return_value=SNAPSHOT)
    def test_ctrl_c_exits_130(self, _snap: object, _sleep: object) -> None:
        code, _, err = run(["--interval", "1"])
        self.assertEqual(code, 130)
        self.assertIn("Interrupted", err)

    @patch("sysmonitor.main.collect_snapshot", side_effect=RuntimeError("boom"))
    def test_unexpected_error_exits_1(self, _snap: object) -> None:
        with self.assertLogs("sysmonitor.main", level="ERROR") as logs:
            code, _, _ = run(["--once"])
        self.assertEqual(code, 1)
        self.assertIn("boom", "\n".join(logs.output))


HIGH_CPU = Snapshot(
    cpu=CpuMetrics(95.0),
    memory=MemoryMetrics(20.0, 2, 10),
    disks=[],
    network=NetworkMetrics(1, 2),
)
WEBHOOK = "https://hooks.slack.com/services/T000/B000/SECRETTOKEN"


class TestAlertIntegration(unittest.TestCase):
    """Alertas dentro del bucle principal."""

    @patch("sysmonitor.main.send_webhook")
    @patch("sysmonitor.main.time.sleep")
    @patch("sysmonitor.main.collect_snapshot")
    def test_alert_sent_once_then_recovery(
        self, collect: MagicMock, sleep: MagicMock, send: MagicMock
    ) -> None:
        collect.side_effect = [HIGH_CPU, HIGH_CPU, SNAPSHOT]
        sleep.side_effect = [None, None, KeyboardInterrupt]
        with self.assertLogs("sysmonitor.main", level="INFO") as logs:
            code, _, _ = run(["--webhook", WEBHOOK])
        self.assertEqual(code, 130)
        messages = [call.args[1] for call in send.call_args_list]
        self.assertEqual(len(messages), 2)
        self.assertIn("[ALERT] CPU", messages[0])
        self.assertIn("[RESOLVED] CPU", messages[1])
        self.assertEqual(len(logs.output), 2)

    @patch("sysmonitor.main.send_webhook")
    @patch("sysmonitor.main.collect_snapshot", return_value=HIGH_CPU)
    def test_without_webhook_logs_but_does_not_send(
        self, _snap: MagicMock, send: MagicMock
    ) -> None:
        with self.assertLogs("sysmonitor.main", level="WARNING") as logs:
            code, _, _ = run(["--once"])
        self.assertEqual(code, 0)
        send.assert_not_called()
        self.assertIn("[ALERT] CPU", logs.output[0])

    @patch("sysmonitor.alerts.requests.post")
    @patch("sysmonitor.main.collect_snapshot", return_value=HIGH_CPU)
    def test_webhook_failure_does_not_stop_monitoring(
        self, _snap: MagicMock, post: MagicMock
    ) -> None:
        post.side_effect = requests.ConnectionError("down")
        with self.assertLogs("sysmonitor.alerts", level="ERROR"):
            code, _, _ = run(["--once", "--webhook", WEBHOOK])
        self.assertEqual(code, 0)

    @patch("sysmonitor.main.send_webhook")
    @patch("sysmonitor.main.collect_snapshot", return_value=HIGH_CPU)
    def test_custom_threshold_suppresses_alert(
        self, _snap: MagicMock, send: MagicMock
    ) -> None:
        run(["--once", "--cpu-threshold", "95", "--webhook", WEBHOOK])
        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
