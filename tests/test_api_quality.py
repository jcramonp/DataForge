"""Tests for PostgreSQL-backed quality API."""

import unittest
from unittest.mock import MagicMock, patch

import psycopg
from fastapi.testclient import TestClient

from src.api.control_plane import ControlPlaneConflictError
from src.api.main import app


class ApiQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @patch("src.api.main.list_dataset_quality_results")
    @patch("src.api.main.connect_postgres")
    def test_quality_results_come_from_postgres(
        self,
        mock_connect,
        mock_quality,
    ):
        conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = conn

        mock_quality.return_value = [
            {
                "quality_result_id": 1,
                "run_id": 69,
                "name": "amount_non_negative",
                "rule_type": "greater_than_or_equal",
                "column": "amount",
                "severity": "critical",
                "status": "fail",
                "failed_rows": 1,
                "failure_percentage": 14.2857,
                "gx_success": False,
                "evaluated_at": "2026-10-26T09:36:00Z",
            }
        ]

        response = self.client.get(
            "/api/datasets/orders/quality-rules",
            params={
                "client_code": "ci-retail",
                "project_code": "ci-retail-e2e",
                "source_code": "ci-retail-csv",
            },
        )

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertEqual(body[0]["run_id"], 69)
        self.assertEqual(
            body[0]["name"],
            "amount_non_negative",
        )

        mock_quality.assert_called_once_with(
            conn,
            "orders",
            client_code="ci-retail",
            project_code="ci-retail-e2e",
            source_code="ci-retail-csv",
        )

    @patch("src.api.main.list_dataset_quality_results")
    @patch("src.api.main.connect_postgres")
    def test_missing_dataset_returns_404(
        self,
        mock_connect,
        mock_quality,
    ):
        mock_connect.return_value.__enter__.return_value = MagicMock()
        mock_quality.return_value = None

        response = self.client.get(
            "/api/datasets/missing/quality-rules"
        )

        self.assertEqual(response.status_code, 404)

    @patch(
        "src.api.main.list_dataset_quality_results",
        side_effect=ControlPlaneConflictError(
            "Dataset code 'orders' is ambiguous"
        ),
    )
    @patch("src.api.main.connect_postgres")
    def test_ambiguous_dataset_returns_409(
        self,
        mock_connect,
        _,
    ):
        mock_connect.return_value.__enter__.return_value = MagicMock()

        response = self.client.get(
            "/api/datasets/orders/quality-rules"
        )

        self.assertEqual(response.status_code, 409)

    @patch(
        "src.api.main.connect_postgres",
        side_effect=psycopg.OperationalError("offline"),
    )
    def test_database_failure_returns_safe_503(
        self,
        _,
    ):
        response = self.client.get(
            "/api/datasets/orders/quality-rules"
        )

        self.assertEqual(response.status_code, 503)
        self.assertNotIn("offline", response.text)


if __name__ == "__main__":
    unittest.main()
