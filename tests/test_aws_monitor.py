"""State transitions and delivery failures without hitting AWS or production."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location("aws_monitor", Path(__file__).parents[1] / "scripts/aws/monitor.py")
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


class MonitorTests(unittest.TestCase):
    def test_two_failures_then_single_alert_then_recovery(self):
        send = Mock()
        state, count = monitor.evaluate({}, False, True, [], send)
        self.assertEqual(count, 0)
        state, count = monitor.evaluate(state, False, True, [], send)
        self.assertEqual(count, 1)
        state, count = monitor.evaluate(state, False, True, [], send)
        self.assertEqual(count, 0)
        state, count = monitor.evaluate(state, True, True, [], send)
        self.assertEqual(count, 1)
        self.assertEqual(send.call_count, 2)
        self.assertFalse(state["application"]["alerted"])

    def test_transient_failure_does_not_alert(self):
        send = Mock()
        state, _ = monitor.evaluate({}, False, True, [], send)
        state, _ = monitor.evaluate(state, True, True, [], send)
        self.assertEqual(state["application"]["failures"], 0)
        send.assert_not_called()

    def test_history_baseline_then_new_failed_and_no_repeat(self):
        send = Mock()
        old = {"orchestration_run_id": 1, "status": "failed"}
        running = {"orchestration_run_id": 2, "status": "running"}
        state, count = monitor.evaluate({}, True, True, [old, running], send)
        self.assertEqual(count, 0)
        failed = running | {"status": "failed", "error_message": "PRIVATE FAILURE TEXT"}
        state, count = monitor.evaluate(state, True, True, [failed, old], send)
        self.assertEqual(count, 1)
        self.assertNotIn("PRIVATE FAILURE TEXT", str(send.call_args))
        state, count = monitor.evaluate(state, True, True, [failed, old], send)
        self.assertEqual(count, 0)
        self.assertEqual(send.call_count, 1)

    def test_history_unavailability_and_recovery(self):
        send = Mock()
        state, _ = monitor.evaluate({}, True, False, [], send)
        state, _ = monitor.evaluate(state, True, False, [], send)
        self.assertIn("run_history unavailable", send.call_args.args[0])
        state, _ = monitor.evaluate(state, True, True, [], send)
        self.assertIn("run_history recovered", send.call_args.args[0])

    def test_delivery_failure_never_marks_event_sent(self):
        before = {"history_initialized": True, "notified_failures": []}
        send = Mock(side_effect=RuntimeError("SNS unavailable"))
        with self.assertRaises(RuntimeError):
            monitor.evaluate(before, True, True, [{"orchestration_run_id": 4, "status": "failed"}], send)
        self.assertEqual(before["notified_failures"], [])

    def test_successful_alert_checkpoint_survives_later_delivery_failure(self):
        snapshots = []
        previous = {"application": {"failures": 1, "alerted": False}, "history_initialized": True}
        send = Mock(side_effect=[None, RuntimeError("SNS failed")])
        with self.assertRaises(RuntimeError):
            monitor.evaluate(previous, False, True, [{"orchestration_run_id": 8, "status": "failed"}], send,
                             checkpoint=lambda s: snapshots.append(json.loads(json.dumps(s))))
        self.assertTrue(snapshots[-1]["application"]["alerted"])

    def test_group_many_failures_in_one_message(self):
        send = Mock()
        runs = [{"orchestration_run_id": n, "status": "failed"} for n in range(1, 201)]
        state, count = monitor.evaluate({"history_initialized": True}, True, True, runs, send)
        self.assertEqual(count, 1)
        self.assertEqual(len(state["notified_failures"]), 200)

    def test_observation_rejects_invalid_readiness_and_history(self):
        fetch = Mock(side_effect=[{"status": "ready", "checks": []}, {"detail": "error"}])
        self.assertEqual(monitor.observe(fetch), (False, False, []))
        fetch = Mock(side_effect=TimeoutError())
        self.assertEqual(monitor.observe(fetch), (False, False, []))

    def test_observation_accepts_real_response_shapes(self):
        runs = [{"orchestration_run_id": 3, "status": "success"}]
        fetch = Mock(side_effect=[{"status": "ready", "checks": [{"ok": True}]}, runs])
        self.assertEqual(monitor.observe(fetch), (True, True, runs))

    def test_atomic_private_state(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.json"
            monitor.save_state(path, {"history_initialized": True})
            self.assertEqual(json.loads(path.read_text()), {"history_initialized": True})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    @patch.object(monitor.subprocess, "run")
    def test_publisher_requires_sns_ack(self, run):
        run.return_value.stdout = '{}'
        with self.assertRaises(RuntimeError):
            monitor.publish({"region": "us-east-1", "topic_arn": "topic"}, "test", "test")
        run.return_value.stdout = '{"MessageId":"id"}'
        monitor.publish({"region": "us-east-1", "topic_arn": "topic"}, "test", "test")


if __name__ == "__main__":
    unittest.main()
