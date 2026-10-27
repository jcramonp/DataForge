"""Tests for PostgreSQL-backed assets API."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import unittest

import psycopg
from fastapi.testclient import TestClient

from src.api.main import app


class ApiAssetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @patch("src.api.main.list_assets")
    @patch("src.api.main.connect_postgres")
    def test_assets_use_postgres_and_filters(
        self,
        mock_connect,
        mock_list_assets,
    ):
        conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = conn

        mock_list_assets.return_value = [
            {
                "asset_id": 70,
                "layer": "gold",
                "asset_name": "ci-retail_orders_by_status_gold",
                "storage_uri": (
                    "s3://dataforge-gold/"
                    "ci-retail/orders_by_status.parquet"
                ),
                "format": "parquet",
                "row_count": 3,
                "checksum": "abc123",
                "created_at": datetime(
                    2026,
                    10,
                    26,
                    tzinfo=timezone.utc,
                ),
                "run_id": 70,
                "run_type": "gold",
                "run_status": "success",
                "input_rows": 4,
                "accepted_rows": 3,
                "rejected_rows": 0,
                "dataset_version_id": 10,
                "version_label": "v1",
                "dataset_id": 21,
                "dataset_code": "orders_by_status",
                "dataset_name": "Orders by Status",
                "source_id": 14,
                "source_code": "ci-retail-csv",
                "source_name": "CI Retail CSV",
                "source_type": "file",
                "project_id": 14,
                "project_code": "ci-retail-e2e",
                "project_name": "CI Retail E2E",
                "client_id": 14,
                "client_code": "ci-retail",
                "client_name": "CI Retail",
            }
        ]

        response = self.client.get(
            "/api/assets",
            params={
                "client_code": "ci-retail",
                "project_code": "ci-retail-e2e",
                "source_code": "ci-retail-csv",
                "layer": "gold",
                "limit": 25,
            },
        )

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["asset_id"], 70)
        self.assertEqual(body[0]["layer"], "gold")
        self.assertEqual(body[0]["row_count"], 3)

        mock_list_assets.assert_called_once_with(
            conn,
            client_code="ci-retail",
            project_code="ci-retail-e2e",
            source_code="ci-retail-csv",
            dataset_code=None,
            layer="gold",
            limit=25,
        )

    def test_invalid_layer_returns_422(self):
        response = self.client.get(
            "/api/assets",
            params={"layer": "raw"},
        )

        self.assertEqual(response.status_code, 422)

    def test_invalid_limit_returns_422(self):
        response = self.client.get(
            "/api/assets",
            params={"limit": 500},
        )

        self.assertEqual(response.status_code, 422)

    @patch(
        "src.api.main.connect_postgres",
        side_effect=psycopg.OperationalError(
            "secret-db-error"
        ),
    )
    def test_database_failure_returns_safe_503(
        self,
        _,
    ):
        response = self.client.get(
            "/api/assets"
        )

        self.assertEqual(response.status_code, 503)
        self.assertNotIn(
            "secret-db-error",
            response.text,
        )


if __name__ == "__main__":
    unittest.main()
