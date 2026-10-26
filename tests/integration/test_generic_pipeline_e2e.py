"""End-to-end regression of the generic contract-driven pipeline (#32).

Runs a non-Olist CSV source through generic Bronze ingestion and the generic
Silver + Quality Gate against real PostgreSQL and S3-compatible storage, then
checks object storage, control-plane metadata, operational views and
readiness. A second scenario breaks a run on purpose and verifies it can be
traced to its run and dataset.
"""

import unittest
from pathlib import Path

from src.common.clients import connect_postgres, create_s3_client
from src.ingestion.bronze_generic import run_ingestion
from src.ops.health import run_readiness_checks
from src.ops.migrate import run_migrations
from src.ops.run_summary import fetch_run_summary
from src.transformations.silver_runner import parse_s3_uri, run_silver_pipeline
from tests.integration import (
    fetch_all,
    integration_settings,
    requires_integration,
    reset_buckets,
    reset_database,
)


CONTRACT = Path("tests/fixtures/e2e/retail_contract.yaml")
CLIENT_PREFIX = "ci-retail/"


def prepare_environment(settings) -> None:
    reset_database(settings)
    with connect_postgres(settings, autocommit=True) as conn:
        run_migrations(conn)
    reset_buckets(settings, CLIENT_PREFIX)


@requires_integration
class GenericPipelineEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = integration_settings()
        prepare_environment(cls.settings)
        cls.bronze = run_ingestion(CONTRACT)
        cls.silver = run_silver_pipeline(CONTRACT)
        cls.s3 = create_s3_client(cls.settings)

    def test_bronze_ingests_every_source_row(self):
        self.assertEqual(len(self.bronze), 1)
        result = self.bronze[0]
        self.assertEqual(result["dataset"], "orders")
        self.assertEqual(result["rows"], 7)
        bucket, key = parse_s3_uri(result["storage_uri"])
        self.assertEqual(bucket, self.settings.storage.bucket("bronze"))
        self.s3.head_object(Bucket=bucket, Key=key)

    def test_quality_gate_routes_only_critical_failures_to_quarantine(self):
        result = self.silver[0]
        self.assertEqual(result["input_rows"], 7)
        self.assertEqual(result["accepted_rows"], 4)
        self.assertEqual(result["rejected_rows"], 3)
        for uri in (result["validated_uri"], result["quarantine_uri"]):
            bucket, key = parse_s3_uri(uri)
            self.s3.head_object(Bucket=bucket, Key=key)

        severities = {
            r["rule_name"]: (r["severity"], r["status"]) for r in result["quality_results"]
        }
        self.assertEqual(severities["email_format"], ("warning", "fail"))
        self.assertEqual(severities["amount_non_negative"], ("critical", "fail"))

    def test_control_plane_metadata_is_recorded(self):
        runs = fetch_all(
            self.settings,
            "SELECT run_type, status, accepted_rows, rejected_rows FROM pipeline_run ORDER BY run_id",
        )
        self.assertEqual(
            runs,
            [("source_to_bronze", "success", 7, 0), ("silver_quality_gate", "success", 4, 3)],
        )
        layers = {r[0] for r in fetch_all(self.settings, "SELECT layer FROM data_asset")}
        self.assertEqual(layers, {"bronze", "silver", "quarantine"})
        quality = fetch_all(self.settings, "SELECT COUNT(*) FROM quality_result")[0][0]
        self.assertEqual(quality, 5)

    def test_operational_summary_reflects_runs(self):
        with connect_postgres(self.settings) as conn:
            summary = fetch_run_summary(conn)
        self.assertEqual(summary["totals"]["total_runs"], 2)
        self.assertEqual(summary["totals"]["failed_runs"], 0)
        self.assertEqual(summary["totals"]["rejected_rows"], 3)
        latest = {(d["dataset_code"], d["run_type"]): d["status"] for d in summary["datasets"]}
        self.assertEqual(latest[("orders", "silver_quality_gate")], "success")

    def test_services_report_ready(self):
        results = run_readiness_checks(self.settings)
        self.assertTrue(all(r.ok for r in results), [(r.name, r.detail) for r in results if not r.ok])


@requires_integration
class FailedPipelineTraceabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = integration_settings()
        prepare_environment(cls.settings)
        bronze = run_ingestion(CONTRACT)[0]
        # Simulate lost Bronze data so the Silver stage fails mid-run.
        bucket, key = parse_s3_uri(bronze["storage_uri"])
        create_s3_client(cls.settings).delete_object(Bucket=bucket, Key=key)
        try:
            run_silver_pipeline(CONTRACT)
        except Exception:
            pass
        else:
            raise AssertionError("Silver stage was expected to fail without its Bronze object")

    def test_failed_run_is_recorded_with_error(self):
        rows = fetch_all(
            self.settings,
            "SELECT status, error_message FROM pipeline_run WHERE run_type = 'silver_quality_gate'",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "failed")
        self.assertTrue(rows[0][1])

    def test_failure_view_links_run_to_dataset(self):
        with connect_postgres(self.settings) as conn:
            summary = fetch_run_summary(conn)
        self.assertEqual(summary["totals"]["failed_runs"], 1)
        failure = summary["recent_failures"][0]
        self.assertEqual(failure["client_code"], "ci-retail")
        self.assertEqual(failure["dataset_code"], "orders")
        self.assertEqual(failure["run_type"], "silver_quality_gate")


if __name__ == "__main__":
    unittest.main()
