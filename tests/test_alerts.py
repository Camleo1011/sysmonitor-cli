"""Pruebas de sysmonitor.alerts con requests mockeado."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from sysmonitor.alerts import (
    Alert,
    AlertTracker,
    Thresholds,
    build_payload,
    detect_webhook_kind,
    evaluate,
    mask_url,
    send_webhook,
)
from sysmonitor.metrics import (
    CpuMetrics,
    DiskMetrics,
    MemoryMetrics,
    NetworkMetrics,
    Snapshot,
)

THRESHOLDS = Thresholds(cpu=90.0, mem=90.0, disk=90.0)
SECRET = "T000/B000/SECRETTOKEN"
SLACK_URL = f"https://hooks.slack.com/services/{SECRET}"
DISCORD_URL = f"https://discord.com/api/webhooks/{SECRET}"


def make_snapshot(
    cpu: float = 10.0, mem: float = 10.0, disks: tuple[float, ...] = (10.0,)
) -> Snapshot:
    """Crea un snapshot con los porcentajes indicados."""
    return Snapshot(
        cpu=CpuMetrics(cpu),
        memory=MemoryMetrics(mem, 1, 10),
        disks=[DiskMetrics(f"/d{i}", p, 1, 10) for i, p in enumerate(disks)],
        network=NetworkMetrics(0, 0),
    )


class TestEvaluate(unittest.TestCase):
    """Lógica de umbrales."""

    def test_just_below_equal_and_above(self) -> None:
        self.assertEqual(evaluate(make_snapshot(cpu=89.9), THRESHOLDS), [])
        self.assertEqual(evaluate(make_snapshot(cpu=90.0), THRESHOLDS), [])
        alerts = evaluate(make_snapshot(cpu=90.1), THRESHOLDS)
        self.assertEqual([a.key for a in alerts], ["cpu"])

    def test_each_metric_and_each_disk(self) -> None:
        snap = make_snapshot(mem=95.0, disks=(50.0, 99.0))
        keys = [a.key for a in evaluate(snap, THRESHOLDS)]
        self.assertEqual(keys, ["mem", "disk:/d1"])

    def test_message_contains_value_and_threshold(self) -> None:
        alert = evaluate(make_snapshot(cpu=95.0), THRESHOLDS)[0]
        self.assertIn("95.0%", alert.message)
        self.assertIn("90.0%", alert.message)


class TestTracker(unittest.TestCase):
    """Anti-spam y recuperación."""

    def test_alert_sent_once_while_condition_persists(self) -> None:
        tracker = AlertTracker()
        high = evaluate(make_snapshot(cpu=95.0), THRESHOLDS)
        self.assertEqual(len(tracker.update(high)), 1)
        self.assertEqual(tracker.update(high), [])
        self.assertEqual(tracker.update(high), [])

    def test_recovery_then_realert(self) -> None:
        tracker = AlertTracker()
        high = evaluate(make_snapshot(cpu=95.0), THRESHOLDS)
        tracker.update(high)
        recovered = tracker.update([])
        self.assertEqual(len(recovered), 1)
        self.assertTrue(recovered[0].resolved)
        self.assertIn("RESOLVED", recovered[0].message)
        self.assertEqual(tracker.update([]), [])
        self.assertEqual(len(tracker.update(high)), 1)


class TestWebhookHelpers(unittest.TestCase):
    """Detección de destino, payload y enmascarado."""

    def test_detect_kind(self) -> None:
        self.assertEqual(detect_webhook_kind(SLACK_URL), "slack")
        self.assertEqual(detect_webhook_kind(DISCORD_URL), "discord")
        self.assertEqual(
            detect_webhook_kind("https://discordapp.com/api/webhooks/x"), "discord"
        )
        self.assertEqual(detect_webhook_kind("https://example.com/hook"), "generic")

    def test_payloads(self) -> None:
        self.assertEqual(build_payload("slack", "hi"), {"text": "hi"})
        self.assertEqual(build_payload("discord", "hi"), {"content": "hi"})
        self.assertEqual(build_payload("generic", "hi"), {"text": "hi"})

    def test_mask_url_hides_secret(self) -> None:
        masked = mask_url(SLACK_URL)
        self.assertEqual(masked, "https://hooks.slack.com/***")
        self.assertNotIn(SECRET, masked)


class TestSendWebhook(unittest.TestCase):
    """Envío con manejo de errores."""

    @patch("sysmonitor.alerts.requests.post")
    def test_success_uses_timeout_and_slack_payload(self, post: MagicMock) -> None:
        self.assertTrue(send_webhook(SLACK_URL, "msg"))
        post.assert_called_once_with(SLACK_URL, json={"text": "msg"}, timeout=5)

    @patch("sysmonitor.alerts.requests.post")
    def test_discord_payload(self, post: MagicMock) -> None:
        send_webhook(DISCORD_URL, "msg")
        self.assertEqual(post.call_args.kwargs["json"], {"content": "msg"})

    @patch("sysmonitor.alerts.requests.post")
    def test_request_exception_is_logged_not_raised(self, post: MagicMock) -> None:
        post.side_effect = requests.ConnectTimeout(f"timeout for {SLACK_URL}")
        with self.assertLogs("sysmonitor.alerts", level="ERROR") as logs:
            self.assertFalse(send_webhook(SLACK_URL, "msg"))
        output = "\n".join(logs.output)
        self.assertIn("ConnectTimeout", output)
        self.assertNotIn(SECRET, output)

    @patch("sysmonitor.alerts.requests.post")
    def test_http_error_status_is_logged_not_raised(self, post: MagicMock) -> None:
        post.return_value.raise_for_status.side_effect = requests.HTTPError("404")
        with self.assertLogs("sysmonitor.alerts", level="ERROR"):
            self.assertFalse(send_webhook(SLACK_URL, "msg"))

    @patch("sysmonitor.alerts.requests.post")
    def test_non_https_is_rejected_without_request(self, post: MagicMock) -> None:
        url = f"http://hooks.slack.com/services/{SECRET}"
        with self.assertLogs("sysmonitor.alerts", level="ERROR") as logs:
            self.assertFalse(send_webhook(url, "msg"))
        post.assert_not_called()
        self.assertNotIn(SECRET, "\n".join(logs.output))

    @patch("sysmonitor.alerts.requests.post")
    def test_unknown_host_warns_but_sends(self, post: MagicMock) -> None:
        with self.assertLogs("sysmonitor.alerts", level="WARNING"):
            self.assertTrue(send_webhook("https://example.com/hook", "msg"))
        post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
