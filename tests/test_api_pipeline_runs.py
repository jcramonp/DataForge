"""Tests for real Airflow-backed pipeline API (#25 + #24)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.orchestration.airflow_client import AirflowClientError
from src.orchestration.plan import PlanError


class ApiPipelineRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @patch("src.api.main.AirflowClient")
    @patch("src.api.main.build_conf")
    @patch("src.api.main.build_persisted_plan")
    def test_trigger_uses_persisted_contract(
        self,
        mock_plan_builder,
        mock_build_conf,
        mock_airflow_class,
    ):
        plan = MagicMock()
        plan.datasets = ["orders"]
        plan.gold = []
        plan.stages = ["bronze"]
        plan.certification = "evaluate"

        mock_plan_builder.return_value = plan

        conf = {
            "contract_id": 17,
            "datasets": ["orders"],
            "gold": [],
            "stages": ["bronze"],
            "certification": "evaluate",
        }

        mock_build_conf.return_value = conf

        airflow = mock_airflow_class.from_env.return_value
        airflow.trigger.return_value = {
            "dag_run_id": "manual__17",
            "state": "queued",
        }

        response = self.client.post(
            "/api/pipelines/trigger",
            json={
                "contract_id": 17,
                "datasets": ["orders"],
                "stages": ["bronze"],
            },
        )

        self.assertEqual(response.status_code, 202)

        body = response.json()

        self.assertEqual(body["contract_id"], 17)
        self.assertEqual(
            body["external_run_id"],
            "manual__17",
        )
        self.assertEqual(body["state"], "queued")

        mock_plan_builder.assert_called_once_with(
            17,
            datasets=["orders"],
            gold=None,
            stages=["bronze"],
            certification="evaluate",
        )

        mock_build_conf.assert_called_once_with(
            contract_id=17,
            datasets=["orders"],
            gold=[],
            stages=["bronze"],
            certification="evaluate",
        )

        airflow.trigger.assert_called_once()

    @patch(
        "src.api.main.build_persisted_plan",
        side_effect=PlanError(
            "Configuration contract 999 was not found"
        ),
    )
    def test_missing_contract_returns_404(
        self,
        _,
    ):
        response = self.client.post(
            "/api/pipelines/trigger",
            json={
                "contract_id": 999,
            },
        )

        self.assertEqual(response.status_code, 404)

    @patch(
        "src.api.main.build_persisted_plan",
        side_effect=PlanError(
            "Unknown dataset(s): missing"
        ),
    )
    def test_invalid_plan_returns_422(
        self,
        _,
    ):
        response = self.client.post(
            "/api/pipelines/trigger",
            json={
                "contract_id": 17,
                "datasets": ["missing"],
            },
        )

        self.assertEqual(response.status_code, 422)

    @patch("src.api.main.AirflowClient")
    @patch("src.api.main.build_conf")
    @patch("src.api.main.build_persisted_plan")
    def test_airflow_failure_returns_safe_503(
        self,
        mock_plan_builder,
        mock_build_conf,
        mock_airflow_class,
    ):
        plan = MagicMock()
        plan.datasets = ["orders"]
        plan.gold = []
        plan.stages = ["bronze"]
        plan.certification = "evaluate"

        mock_plan_builder.return_value = plan
        mock_build_conf.return_value = {}

        mock_airflow_class.from_env.side_effect = (
            AirflowClientError(
                "secret-password-should-not-leak"
            )
        )

        response = self.client.post(
            "/api/pipelines/trigger",
            json={
                "contract_id": 17,
            },
        )

        self.assertEqual(response.status_code, 503)
        self.assertNotIn(
            "secret-password-should-not-leak",
            response.text,
        )

    @patch("src.api.main.AirflowClient")
    def test_live_run_status_uses_airflow(
        self,
        mock_airflow_class,
    ):
        airflow = mock_airflow_class.from_env.return_value

        airflow.get_run.return_value = {
            "dag_run_id": "manual__17",
            "state": "running",
            "start_date": "2026-10-26T14:00:00Z",
            "end_date": None,
        }

        airflow.task_instances.return_value = [
            {
                "task_id": "resolve_plan",
                "state": "success",
            }
        ]

        response = self.client.get(
            "/api/pipelines/runs/manual__17"
        )

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertEqual(body["state"], "running")
        self.assertEqual(
            body["tasks"][0]["task_id"],
            "resolve_plan",
        )

    @patch("src.api.main.list_orchestration_runs")
    @patch("src.api.main.connect_postgres")
    def test_run_history_comes_from_postgres(
        self,
        mock_connect,
        mock_list_runs,
    ):
        conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = conn

        mock_list_runs.return_value = [
            {
                "orchestration_run_id": 7,
                "orchestrator": "airflow",
                "external_run_id": "manual__17",
                "contract_reference": (
                    "db://configuration_contract/17"
                ),
                "client_code": "ci-retail",
                "project_code": "ci-retail-e2e",
                "status": "running",
                "started_at": "2026-10-26T14:00:00Z",
                "finished_at": None,
                "duration_seconds": None,
                "task_count": 1,
                "successful_tasks": 1,
                "failed_tasks": 0,
                "retried_attempts": 0,
                "error_message": None,
            }
        ]

        response = self.client.get(
            "/api/runs",
            params={"limit": 10},
        )

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertEqual(
            body[0]["orchestration_run_id"],
            7,
        )
        self.assertEqual(
            body[0]["external_run_id"],
            "manual__17",
        )

        mock_list_runs.assert_called_once_with(
            conn,
            limit=10,
            client_code=None,
            project_code=None,
            source_code=None,
        )


if __name__ == "__main__":
    unittest.main()
