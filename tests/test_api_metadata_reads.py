"""Tests for PostgreSQL-backed metadata read endpoints (#25)."""

from __future__ import annotations

from pathlib import Path

import unittest
from unittest.mock import MagicMock, patch

import psycopg
from fastapi.testclient import TestClient

from src.api.main import app
from src.contracts.loader import load_contract


class ApiMetadataReadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @patch("src.api.main.list_clients")
    @patch("src.api.main.connect_postgres")
    def test_clients_endpoint(
        self,
        mock_connect,
        mock_list_clients,
    ):
        conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = conn

        mock_list_clients.return_value = [
            {
                "client_id": 1,
                "code": "ci-retail",
                "name": "CI Retail",
                "status": "active",
                "created_at": "2026-10-26T00:00:00Z",
                "projects_count": 1,
                "sources_count": 1,
                "datasets_count": 1,
            }
        ]

        response = self.client.get("/api/clients")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()[0]["code"],
            "ci-retail",
        )

        mock_list_clients.assert_called_once_with(conn)

    @patch("src.api.main.list_projects")
    @patch("src.api.main.connect_postgres")
    def test_projects_endpoint_forwards_client_filter(
        self,
        mock_connect,
        mock_list_projects,
    ):
        conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = conn
        mock_list_projects.return_value = []

        response = self.client.get(
            "/api/projects",
            params={
                "client_code": "ci-retail",
            },
        )

        self.assertEqual(response.status_code, 200)

        mock_list_projects.assert_called_once_with(
            conn,
            client_code="ci-retail",
        )

    @patch("src.api.main.list_sources")
    @patch("src.api.main.connect_postgres")
    def test_sources_endpoint_forwards_scope_filters(
        self,
        mock_connect,
        mock_list_sources,
    ):
        conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = conn
        mock_list_sources.return_value = []

        response = self.client.get(
            "/api/sources",
            params={
                "client_code": "ci-retail",
                "project_code": "ci-retail-e2e",
            },
        )

        self.assertEqual(response.status_code, 200)

        mock_list_sources.assert_called_once_with(
            conn,
            client_code="ci-retail",
            project_code="ci-retail-e2e",
        )

    @patch("src.api.main.list_datasets")
    @patch("src.api.main.connect_postgres")
    def test_datasets_endpoint_forwards_scope_filters(
        self,
        mock_connect,
        mock_list_datasets,
    ):
        conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = conn
        mock_list_datasets.return_value = []

        response = self.client.get(
            "/api/datasets",
            params={
                "client_code": "ci-retail",
                "project_code": "ci-retail-e2e",
                "source_code": "ci-retail-csv",
            },
        )

        self.assertEqual(response.status_code, 200)

        mock_list_datasets.assert_called_once_with(
            conn,
            client_code="ci-retail",
            project_code="ci-retail-e2e",
            source_code="ci-retail-csv",
        )

    @patch("src.api.main.get_active_contract")
    @patch("src.api.main.connect_postgres")
    def test_active_contract_endpoint(
        self,
        mock_connect,
        mock_get_active_contract,
    ):
        conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = conn

        contract = load_contract(
            Path("tests/fixtures/e2e/retail_contract.yaml")
        )

        mock_get_active_contract.return_value = {
            "contract_id": 10,
            "source_id": 20,
            "contract_version": "1.0",
            "revision": 1,
            "contract_hash": "a" * 64,
            "contract": contract,
            "created_by": "api",
            "created_at": "2026-10-26T00:00:00Z",
            "activated_at": "2026-10-26T00:00:00Z",
        }

        response = self.client.get(
            "/api/onboarding/contracts/"
            "ci-retail/ci-retail-e2e/ci-retail-csv"
        )

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertEqual(body["status"], "active")
        self.assertEqual(body["revision"], 1)
        self.assertEqual(
            body["contract"]["source"]["code"],
            "ci-retail-csv",
        )

        mock_get_active_contract.assert_called_once_with(
            conn,
            client_code="ci-retail",
            project_code="ci-retail-e2e",
            source_code="ci-retail-csv",
        )

    @patch("src.api.main.get_active_contract")
    @patch("src.api.main.connect_postgres")
    def test_missing_active_contract_returns_404(
        self,
        mock_connect,
        mock_get_active_contract,
    ):
        mock_connect.return_value.__enter__.return_value = (
            MagicMock()
        )
        mock_get_active_contract.return_value = None

        response = self.client.get(
            "/api/onboarding/contracts/"
            "missing/project/source"
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn(
            "No active configuration contract",
            response.json()["detail"],
        )

    @patch("src.api.main.list_clients")
    @patch("src.api.main.connect_postgres")
    def test_metadata_database_failure_returns_503(
        self,
        mock_connect,
        mock_list_clients,
    ):
        mock_connect.return_value.__enter__.return_value = (
            MagicMock()
        )

        mock_list_clients.side_effect = psycopg.OperationalError(
            "offline"
        )

        response = self.client.get("/api/clients")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Control-plane database unavailable",
        )

    def test_openapi_contains_metadata_routes(self):
        response = self.client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)

        paths = response.json()["paths"]

        expected = [
            "/api/clients",
            "/api/projects",
            "/api/sources",
            "/api/datasets",
            (
                "/api/onboarding/contracts/"
                "{client_code}/{project_code}/{source_code}"
            ),
        ]

        for route in expected:
            self.assertIn(route, paths)


if __name__ == "__main__":
    unittest.main()
