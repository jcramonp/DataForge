"""Unit tests for readiness checks and run summaries (#32)."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.common.settings import get_settings
from src.ops.health import (
    check_configuration,
    check_contracts,
    check_postgres,
    check_storage,
)
from src.ops.run_summary import summarize_status_rows
from tests.test_common_settings import LOCAL_ENV


class ReadinessCheckTests(unittest.TestCase):
    def setUp(self):
        self.settings = get_settings(LOCAL_ENV)

    def test_configuration_check_passes_for_valid_settings(self):
        result = check_configuration(self.settings)
        self.assertTrue(result.ok)
        self.assertIn("environment=local", result.detail)

    def test_configuration_check_reports_problems(self):
        result = check_configuration(get_settings({"DATAFORGE_ENV": "test"}))
        self.assertFalse(result.ok)
        self.assertIn("POSTGRES_HOST", result.detail)

    def test_storage_check_heads_every_bucket(self):
        s3 = Mock()
        result = check_storage(self.settings, client_factory=lambda _: s3)
        self.assertTrue(result.ok)
        self.assertEqual(s3.head_bucket.call_count, 4)

    def test_storage_check_reports_missing_bucket(self):
        s3 = Mock()
        s3.head_bucket.side_effect = RuntimeError("NoSuchBucket")
        result = check_storage(self.settings, client_factory=lambda _: s3)
        self.assertFalse(result.ok)
        self.assertIn("NoSuchBucket", result.detail)

    @patch("src.ops.health.connect_postgres", side_effect=OSError("connection refused"))
    def test_postgres_check_never_raises(self, _):
        result = check_postgres(self.settings)
        self.assertFalse(result.ok)
        self.assertIn("connection refused", result.detail)

    def test_contract_check_validates_shipped_examples(self):
        result = check_contracts()
        self.assertTrue(result.ok, result.detail)

    def test_contract_check_fails_on_invalid_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "broken.yaml").write_text("contract_version: '1.0'\n", encoding="utf-8")
            result = check_contracts(Path(tmp))
        self.assertFalse(result.ok)


class RunSummaryTests(unittest.TestCase):
    def test_totals_and_failure_rate(self):
        rows = [
            {"run_type": "source_to_bronze", "status": "success", "run_count": 6, "rejected_rows": 0},
            {"run_type": "silver_quality_gate", "status": "success", "run_count": 2, "rejected_rows": 5},
            {"run_type": "silver_quality_gate", "status": "failed", "run_count": 2, "rejected_rows": None},
        ]
        totals = summarize_status_rows(rows)
        self.assertEqual(totals["total_runs"], 10)
        self.assertEqual(totals["successful_runs"], 8)
        self.assertEqual(totals["failed_runs"], 2)
        self.assertEqual(totals["failure_rate"], 0.2)
        self.assertEqual(totals["rejected_rows"], 5)

    def test_empty_summary(self):
        self.assertEqual(summarize_status_rows([])["failure_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
