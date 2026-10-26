"""Tests for PostgreSQL-backed lineage API."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import unittest

import psycopg
from fastapi.testclient import TestClient

from src.api.main import app


class ApiLineageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @patch("src.api.main.get_lineage_graph")
    @patch("src.api.main.connect_postgres")
    def test_lineage_uses_postgres_and_filters(
        self,
        mock_connect,
        mock_graph,
    ):
        conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = conn

        mock_graph.return_value = {
            "nodes": [
                {
                    "id": "asset-67",
                    "asset_id": 67,
                    "name": "orders",
                    "type": "asset",
                    "layer": "bronze",
                    "dataset_code": "orders",
                    "version_label": "abc123",
                    "storage_uri": "s3://bronze/orders.parquet",
                },
                {
                    "id": "asset-68",
                    "asset_id": 68,
                    "name": "orders",
                    "type": "asset",
                    "layer": "silver",
                    "dataset_code": "orders",
                    "version_label": "abc123",
                    "storage_uri": "s3://silver/orders.parquet",
                },
            ],
            "links": [
                {
                    "lineage_id": 41,
                    "source": "asset-67",
                    "target": "asset-68",
                    "relation_type": "validated_from",
                    "created_by_run_id": 69,
                    "metadata": {
                        "pipeline_stage": "silver_quality_gate",
                    },
                    "created_at": datetime(
                        2026,
                        10,
                        26,
                        tzinfo=timezone.utc,
                    ),
                }
            ],
        }

        response = self.client.get(
            "/api/lineage",
            params={
                "client_code": "ci-retail",
                "project_code": "ci-retail-e2e",
                "source_code": "ci-retail-csv",
                "dataset_code": "orders",
                "limit": 100,
            },
        )

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertEqual(len(body["nodes"]), 2)
        self.assertEqual(len(body["links"]), 1)

        self.assertEqual(
            body["links"][0]["relation_type"],
            "validated_from",
        )

        mock_graph.assert_called_once_with(
            conn,
            client_code="ci-retail",
            project_code="ci-retail-e2e",
            source_code="ci-retail-csv",
            dataset_code="orders",
            limit=100,
        )

    def test_invalid_limit_returns_422(self):
        response = self.client.get(
            "/api/lineage",
            params={"limit": 1500},
        )

        self.assertEqual(response.status_code, 422)

    @patch(
        "src.api.main.connect_postgres",
        side_effect=psycopg.OperationalError(
            "secret-lineage-db-error"
        ),
    )
    def test_database_failure_returns_safe_503(
        self,
        _,
    ):
        response = self.client.get(
            "/api/lineage"
        )

        self.assertEqual(response.status_code, 503)
        self.assertNotIn(
            "secret-lineage-db-error",
            response.text,
        )


if __name__ == "__main__":
    unittest.main()
