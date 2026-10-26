"""Stage functions delegate to the existing generic runners (#24)."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from src.orchestration import stages
from src.orchestration.plan import build_plan


RETAIL = "tests/fixtures/e2e/retail_contract.yaml"


def _connection():
    conn = MagicMock()
    conn.__enter__.return_value = conn
    return conn


class RunnerDelegationTests(unittest.TestCase):
    def setUp(self):
        self.plan = build_plan(RETAIL)

    @patch("src.orchestration.stages.bronze_generic")
    def test_bronze_uses_generic_ingestion(self, bronze):
        bronze.postgres_connection.return_value = _connection()
        bronze.ingest_dataset.return_value = {
            "dataset": "orders",
            "source_type": "file",
            "rows": 7,
            "source_checksum": "a" * 64,
            "storage_uri": "s3://dataforge-bronze/x.parquet",
            "run_id": 11,
        }
        summary = stages.run_bronze(self.plan, "orders")

        kwargs = bronze.ingest_dataset.call_args.kwargs
        self.assertEqual(kwargs["dataset_code"], "orders")
        self.assertEqual(kwargs["contract"].client.code, "ci-retail")
        self.assertEqual(kwargs["bucket"], "dataforge-bronze")
        self.assertEqual(summary["run_id"], 11)
        self.assertEqual(summary["rows"], 7)

    @patch("src.orchestration.stages.silver_runner")
    def test_silver_uses_generic_runner_and_summarizes_failed_rules(self, silver):
        silver.postgres_connection.return_value = _connection()
        silver.execute_silver_pipeline_for_dataset.return_value = {
            "dataset": "orders",
            "input_rows": 7,
            "accepted_rows": 4,
            "rejected_rows": 3,
            "validated_uri": "s3://silver/v.parquet",
            "quarantine_uri": "s3://quarantine/q.parquet",
            "run_id": 12,
            "quality_results": [
                {"rule_name": "amount_non_negative", "severity": "critical", "status": "fail", "failed_rows": 1},
                {"rule_name": "order_id_unique", "severity": "critical", "status": "pass", "failed_rows": 0},
            ],
        }
        summary = stages.run_silver(self.plan, "orders")

        kwargs = silver.execute_silver_pipeline_for_dataset.call_args.kwargs
        self.assertEqual((kwargs["silver_bucket"], kwargs["quarantine_bucket"]), ("dataforge-silver", "dataforge-quarantine"))
        self.assertEqual(summary["rejected_rows"], 3)
        self.assertEqual(summary["failed_rules"], [{"rule": "amount_non_negative", "severity": "critical", "failed_rows": 1}])

    @patch("src.orchestration.stages.gold_runner")
    def test_gold_uses_generic_runner(self, gold):
        gold.postgres_connection.return_value = _connection()
        gold.execute_gold_pipeline_for_dataset.return_value = {
            "gold_code": "orders_by_status",
            "dataset_version_id": 5,
            "run_id": 13,
            "input_rows": 4,
            "output_rows": 3,
            "excluded_rows": 1,
            "storage_uri": "s3://gold/g.parquet",
            "certification": {"validation_ready": True, "certification_ready": False},
        }
        summary = stages.run_gold(self.plan, "orders_by_status")

        kwargs = gold.execute_gold_pipeline_for_dataset.call_args.kwargs
        self.assertEqual(kwargs["gold_config"].code, "orders_by_status")
        self.assertEqual(kwargs["gold_bucket"], "dataforge-gold")
        self.assertTrue(summary["validation_ready"])
        self.assertEqual(summary["output_rows"], 3)

    def test_unknown_gold_code_fails(self):
        with self.assertRaises(ValueError):
            stages.run_gold(self.plan, "missing_gold")


class ProfilingStageTests(unittest.TestCase):
    @patch("src.orchestration.stages.silver_runner")
    def test_profiles_latest_bronze_asset_with_existing_engine(self, silver):
        silver.postgres_connection.return_value = _connection()
        silver.latest_bronze_asset.return_value = {"asset_id": 3, "storage_uri": "s3://dataforge-bronze/orders.parquet"}
        silver.parse_s3_uri.return_value = ("dataforge-bronze", "orders.parquet")

        frame = pd.DataFrame({"order_id": ["R1", "R2", "R3"], "amount": [1.0, None, 3.0]})

        def download(bucket, key, path):
            frame.to_parquet(path, index=False)

        silver.minio_client.return_value.download_file.side_effect = download

        with tempfile.TemporaryDirectory() as reports:
            before = set(Path(reports).iterdir())
            summary = stages.run_profiling(build_plan(RETAIL), "orders")
            self.assertEqual(set(Path(reports).iterdir()), before)

        silver.latest_bronze_asset.assert_called_once_with(
            unittest.mock.ANY, "ci-retail", "ci-retail-e2e", "ci-retail-csv", "orders"
        )
        self.assertEqual(summary["row_count"], 3)
        self.assertEqual(summary["column_count"], 2)
        self.assertEqual(summary["candidate_keys"], ["order_id"])
        self.assertEqual(summary["columns"]["amount"]["null_percentage"], 33.33)


class CertificationStageTests(unittest.TestCase):
    def _run(self, mode, states, ready):
        plan = build_plan(RETAIL, certification=mode)
        versions = {"orders": 21, "orders_by_status": 22}
        with (
            patch("src.orchestration.stages.silver_runner.postgres_connection", return_value=_connection()),
            patch("src.orchestration.stages.latest_successful_version", side_effect=lambda c, p, code, rt: versions[code]),
            patch(
                "src.orchestration.stages.evaluate_certification",
                side_effect=lambda c, vid: {
                    "validation_ready": ready[vid],
                    "certification_ready": False,
                    "criteria": {},
                },
            ),
            patch("src.orchestration.stages.get_certification", side_effect=lambda c, vid: {"state": states[vid]}),
            patch("src.orchestration.stages.transition_certification") as transition,
        ):
            result = stages.run_certification(plan)
        return result, transition

    def test_evaluate_never_changes_state(self):
        result, transition = self._run("evaluate", {21: "draft", 22: "draft"}, {21: True, 22: True})
        transition.assert_not_called()
        self.assertEqual([v["state_after"] for v in result["versions"]], ["draft", "draft"])

    def test_validate_promotes_only_ready_drafts_and_never_certifies(self):
        result, transition = self._run("validate", {21: "draft", 22: "draft"}, {21: False, 22: True})
        transition.assert_called_once()
        self.assertEqual(transition.call_args.args[1:3], (22, "validated"))
        self.assertEqual(transition.call_args.kwargs["changed_by"], stages.ORCHESTRATOR_ACTOR)
        self.assertEqual({v["target"]: v["state_after"] for v in result["versions"]}, {"orders": "draft", "orders_by_status": "validated"})

    def test_already_validated_versions_are_left_alone(self):
        _, transition = self._run("validate", {21: "validated", 22: "certified"}, {21: True, 22: True})
        transition.assert_not_called()

    def test_missing_processed_version_fails(self):
        plan = build_plan(RETAIL)
        with (
            patch("src.orchestration.stages.silver_runner.postgres_connection", return_value=_connection()),
            patch("src.orchestration.stages.latest_successful_version", return_value=None),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                stages.run_certification(plan)
        self.assertIn("orders", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
