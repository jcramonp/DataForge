"""Unit tests for structured logging with run context (#32)."""

import json
import logging
import unittest

from src.common.log import (
    ContextFilter,
    JsonFormatter,
    TextFormatter,
    bind_context,
    current_context,
    run_context,
)


def _record(message: str, **extra) -> logging.LogRecord:
    logger = logging.getLogger("dataforge.test")
    record = logger.makeRecord(
        "dataforge.test", logging.INFO, __file__, 1, message, (), None, extra=extra
    )
    ContextFilter().filter(record)
    return record


class RunContextTests(unittest.TestCase):
    def test_context_is_bound_and_restored(self):
        self.assertEqual(current_context(), {})
        with run_context(stage="source_to_bronze", dataset="orders"):
            bind_context(run_id=42)
            self.assertEqual(
                current_context(),
                {"stage": "source_to_bronze", "dataset": "orders", "run_id": 42},
            )
            with run_context(dataset="customers"):
                self.assertEqual(current_context()["dataset"], "customers")
            self.assertEqual(current_context()["dataset"], "orders")
        self.assertEqual(current_context(), {})

    def test_none_values_are_not_bound(self):
        with run_context(run_id=None, dataset="orders"):
            self.assertNotIn("run_id", current_context())


class FormatterTests(unittest.TestCase):
    def test_json_formatter_includes_context_and_extra(self):
        with run_context(run_id=7, dataset="orders", stage="silver_quality_gate"):
            record = _record("finished", rejected_rows=3)
        payload = json.loads(JsonFormatter().format(record))
        self.assertEqual(payload["message"], "finished")
        self.assertEqual(payload["level"], "INFO")
        self.assertEqual(payload["run_id"], 7)
        self.assertEqual(payload["dataset"], "orders")
        self.assertEqual(payload["stage"], "silver_quality_gate")
        self.assertEqual(payload["rejected_rows"], 3)
        self.assertIn("timestamp", payload)

    def test_json_formatter_includes_exception(self):
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            logger = logging.getLogger("dataforge.test")
            record = logger.makeRecord(
                "dataforge.test", logging.ERROR, __file__, 1, "failed", (), sys.exc_info()
            )
        payload = json.loads(JsonFormatter().format(record))
        self.assertIn("ValueError: boom", payload["exception"])

    def test_sensitive_fields_are_redacted(self):
        record = _record("connecting", password="hunter2", api_key="abc", host="db")
        payload = json.loads(JsonFormatter().format(record))
        self.assertEqual(payload["password"], "***")
        self.assertEqual(payload["api_key"], "***")
        self.assertEqual(payload["host"], "db")

    def test_text_formatter_shows_context(self):
        with run_context(run_id=9, dataset="orders"):
            record = _record("started")
        line = TextFormatter().format(record)
        self.assertIn("run_id=9", line)
        self.assertIn("dataset=orders", line)
        self.assertTrue(line.endswith("started"))


if __name__ == "__main__":
    unittest.main()
