"""Stage functions delegate to the existing generic runners (#24)."""

import unittest
from unittest.mock import MagicMock, patch


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
    @patch("src.orchestration.stages.create_s3_client")
    @patch("src.orchestration.stages.connect_postgres")
    @patch("src.orchestration.stages.profiling_service.execute_profiling_for_dataset")
    def test_delegates_to_governed_profiling_service(self, execute, connect, s3_factory):
        conn = _connection()
        connect.return_value = conn
        execute.return_value = {
            "dataset": "orders",
            "profile_id": 9,
            "run_id": 14,
            "dataset_version_id": 2,
            "source_asset_id": 5,
            "source_checksum": "a" * 64,
            "row_count": 7,
            "column_count": 5,
            "profile": {"columns": {"order_id": {"sample_values": ["R1"]}}},
        }

        summary = stages.run_profiling(build_plan(RETAIL), "orders")

        kwargs = execute.call_args.kwargs
        self.assertEqual(kwargs["dataset_code"], "orders")
        self.assertEqual(kwargs["contract"].client.code, "ci-retail")
        self.assertIs(kwargs["s3"], s3_factory.return_value)
        self.assertIs(kwargs["conn"], conn)
        self.assertEqual(
            summary,
            {
                "dataset": "orders",
                "run_id": 14,
                "profile_id": 9,
                "dataset_version_id": 2,
                "source_asset_id": 5,
                "row_count": 7,
                "column_count": 5,
            },
        )
        # The full profile stays in profiling_result, not in the orchestration summary.
        self.assertNotIn("profile", summary)

    @patch("src.orchestration.stages.create_s3_client")
    @patch("src.orchestration.stages.connect_postgres")
    @patch(
        "src.orchestration.stages.profiling_service.execute_profiling_for_dataset",
        side_effect=RuntimeError("Bronze asset checksum mismatch"),
    )
    def test_profiling_failures_propagate(self, execute, connect, _):
        connect.return_value = _connection()
        with self.assertRaises(RuntimeError):
            stages.run_profiling(build_plan(RETAIL), "orders")


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
