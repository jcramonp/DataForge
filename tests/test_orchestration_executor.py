"""Unit tests for orchestration execution, run state and the CLI runner (#24)."""

import unittest
from unittest.mock import MagicMock, call, patch

import psycopg
from botocore.exceptions import EndpointConnectionError

from src.connectors.base import ConnectorConfigurationError, ConnectorConnectionError
from src.orchestration import executor, pipeline
from src.orchestration.plan import PlanError, build_plan
from src.orchestration.state import evaluate_run_outcome


RETAIL = "tests/fixtures/e2e/retail_contract.yaml"
OLIST = "config/examples/olist.yaml"


class RetryClassificationTests(unittest.TestCase):
    def test_transient_infrastructure_errors_are_retryable(self):
        for exc in (
            psycopg.OperationalError("server closed the connection"),
            EndpointConnectionError(endpoint_url="http://minio:9000"),
            ConnectorConnectionError("source unreachable"),
            TimeoutError(),
            ConnectionResetError(),
        ):
            with self.subTest(exc=type(exc).__name__):
                self.assertTrue(executor.is_retryable(exc))

    def test_contract_configuration_and_data_errors_are_not(self):
        for exc in (
            PlanError("bad request"),
            ConnectorConfigurationError("missing credentials"),
            FileNotFoundError("orders.csv"),
            RuntimeError("No successful Bronze asset found"),
            ValueError("bad cast"),
        ):
            with self.subTest(exc=type(exc).__name__):
                self.assertFalse(executor.is_retryable(exc))


class RunOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.plan = build_plan(RETAIL, stages=["bronze", "silver"])

    def test_success_requires_every_planned_task(self):
        states = {
            ("bronze", "orders"): {"status": "success", "attempt": 2, "error_message": None},
            ("silver", "orders"): {"status": "success", "attempt": 1, "error_message": None},
        }
        self.assertEqual(evaluate_run_outcome(self.plan, states), ("success", None))

    def test_failed_and_missing_tasks_fail_the_run(self):
        states = {("bronze", "orders"): {"status": "failed", "attempt": 3, "error_message": "boom"}}
        status, error = evaluate_run_outcome(self.plan, states)
        self.assertEqual(status, "failed")
        self.assertIn("bronze[orders] failed: boom", error)
        self.assertIn("silver[orders] did not run", error)


def _fake_connection():
    conn = MagicMock()
    conn.__enter__.return_value = conn
    return conn


class ExecuteTaskTests(unittest.TestCase):
    def setUp(self):
        self.plan = build_plan(RETAIL)
        patcher = patch("src.orchestration.executor.connect_postgres", side_effect=lambda *a, **k: _fake_connection())
        patcher.start()
        self.addCleanup(patcher.stop)

    @patch("src.orchestration.executor.state")
    def test_success_records_attempt_and_links_pipeline_run(self, state):
        state.start_task_run.return_value = 7
        bronze = MagicMock(return_value={"run_id": 41, "rows": 7})
        with patch.dict(executor.STAGE_FUNCTIONS, {"bronze": bronze}):
            summary = executor.execute_task(self.plan, 3, "bronze", "orders", attempt=2, external_run_id="manual__1")

        self.assertEqual(summary["run_id"], 41)
        bronze.assert_called_once_with(self.plan, "orders")
        state.start_task_run.assert_called_once_with(unittest.mock.ANY, 3, "bronze", "orders", 2)
        state.finish_task_run.assert_called_once_with(
            unittest.mock.ANY, 7, "success", pipeline_run_id=41, summary={"run_id": 41, "rows": 7}
        )

    @patch("src.orchestration.executor.state")
    def test_profiling_summary_is_not_persisted(self, state):
        state.start_task_run.return_value = 8
        profiling = MagicMock(return_value={"row_count": 7, "columns": {}})
        with patch.dict(executor.STAGE_FUNCTIONS, {"profiling": profiling}):
            executor.execute_task(self.plan, 3, "profiling", "orders")
        self.assertIsNone(state.finish_task_run.call_args.kwargs["summary"])

    @patch("src.orchestration.executor.state")
    def test_certification_runs_once_for_the_plan(self, state):
        certification = MagicMock(return_value={"mode": "evaluate", "versions": []})
        with patch.dict(executor.STAGE_FUNCTIONS, {"certification": certification}):
            executor.execute_task(self.plan, 3, "certification", "contract")
        certification.assert_called_once_with(self.plan)

    @patch("src.orchestration.executor.state")
    def test_failure_is_recorded_and_reraised(self, state):
        state.start_task_run.return_value = 9
        silver = MagicMock(side_effect=RuntimeError("No successful Bronze asset found"))
        with patch.dict(executor.STAGE_FUNCTIONS, {"silver": silver}):
            with self.assertRaises(RuntimeError):
                executor.execute_task(self.plan, 3, "silver", "orders")
        self.assertEqual(state.finish_task_run.call_args.args[1:], (9, "failed"))
        self.assertIn("RuntimeError: No successful Bronze asset", state.finish_task_run.call_args.kwargs["error_message"])


class CliPipelineTests(unittest.TestCase):
    def setUp(self):
        # main() configures process-wide logging; keep the test output clean.
        patcher = patch("src.orchestration.pipeline.configure_logging")
        patcher.start()
        self.addCleanup(patcher.stop)

    @patch("src.orchestration.pipeline.executor")
    def test_runs_stages_in_order_and_closes_the_run(self, mocked):
        mocked.start_run.return_value = 5
        mocked.execute_task.side_effect = lambda plan, rid, stage, target, **kw: {"run_id": 1}
        mocked.finish_run.return_value = ("success", None)

        outcome = pipeline.run_pipeline(build_plan(RETAIL), external_run_id="cli__test")

        executed = [c.args[2:4] for c in mocked.execute_task.call_args_list]
        self.assertEqual(
            executed,
            [
                ("bronze", "orders"),
                ("profiling", "orders"),
                ("silver", "orders"),
                ("gold", "orders_by_status"),
                ("certification", "contract"),
            ],
        )
        mocked.start_run.assert_called_once()
        self.assertEqual(mocked.start_run.call_args.args[1:], ("cli", "cli__test"))
        self.assertEqual(outcome["status"], "success")

    @patch("src.orchestration.pipeline.executor")
    def test_failed_dataset_stops_its_chain_and_downstream_but_not_other_datasets(self, mocked):
        mocked.start_run.return_value = 6

        def run(plan, rid, stage, target, **kw):
            if (stage, target) == ("bronze", "orders"):
                raise RuntimeError("source down")
            return {"run_id": 1}

        mocked.execute_task.side_effect = run
        mocked.finish_run.return_value = ("failed", "bronze[orders] failed")

        outcome = pipeline.run_pipeline(build_plan(OLIST, stages="bronze,silver,gold"))

        executed = [c.args[2:4] for c in mocked.execute_task.call_args_list]
        self.assertIn(("bronze", "customers"), executed)
        self.assertIn(("silver", "customers"), executed)
        self.assertIn(("silver", "products"), executed)
        self.assertNotIn(("silver", "orders"), executed)
        self.assertFalse(any(stage == "gold" for stage, _ in executed))
        self.assertEqual(outcome["status"], "failed")

    def test_cli_rejects_invalid_requests_without_touching_the_database(self):
        with patch("src.orchestration.pipeline.run_pipeline") as run:
            code = pipeline.main(["--contract", RETAIL, "--stages", "platinum"])
        self.assertEqual(code, 2)
        run.assert_not_called()

    @patch("src.orchestration.pipeline.run_pipeline")
    def test_cli_exit_code_reflects_run_status(self, run):
        run.return_value = {"orchestration_run_id": 1, "external_run_id": "x", "status": "failed", "error": "e", "results": {}}
        self.assertEqual(pipeline.main(["--contract", RETAIL]), 1)
        run.return_value["status"] = "success"
        self.assertEqual(pipeline.main(["--contract", RETAIL]), 0)
        self.assertEqual(run.call_args.args[0].datasets, ["orders"])


class StartRunTests(unittest.TestCase):
    @patch("src.orchestration.executor.state")
    @patch("src.orchestration.executor.connect_postgres", side_effect=lambda *a, **k: _fake_connection())
    def test_start_run_registers_the_external_run(self, _, state):
        state.start_orchestration_run.return_value = 12
        plan = build_plan(RETAIL)
        self.assertEqual(executor.start_run(plan, "airflow", "manual__2026"), 12)
        self.assertEqual(state.start_orchestration_run.call_args, call(unittest.mock.ANY, plan, "airflow", "manual__2026"))


if __name__ == "__main__":
    unittest.main()
