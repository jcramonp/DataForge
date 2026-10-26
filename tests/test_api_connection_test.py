"""Tests for real source connection verification (#25 + #20)."""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, Mock, patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.connectors import ConnectorConnectionError


class ApiConnectionTestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_real_file_connection_succeeds(self):
        response = self.client.post(
            "/api/sources/test-connection",
            json={
                "source_type": "file",
                "target_object": (
                    "tests/fixtures/e2e/orders.csv"
                ),
            },
        )

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertTrue(body["success"])
        self.assertEqual(body["source_type"], "file")
        self.assertGreater(body["latency_ms"], 0)

    def test_missing_file_returns_safe_failure(self):
        response = self.client.post(
            "/api/sources/test-connection",
            json={
                "source_type": "file",
                "target_object": (
                    "tests/fixtures/e2e/does-not-exist.csv"
                ),
            },
        )

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertFalse(body["success"])
        self.assertEqual(
            body["message"],
            "file connection could not be established.",
        )

    @patch(
        "src.connectors.postgres_connector.psycopg.connect"
    )
    def test_postgres_uses_connection_reference(
        self,
        mock_connect,
    ):
        connection = MagicMock()
        cursor = MagicMock()

        mock_connect.return_value.__enter__.return_value = (
            connection
        )

        connection.cursor.return_value.__enter__.return_value = (
            cursor
        )

        environment = {
            "DATAFORGE_CONNECTION_API_TEST_POSTGRES": (
                json.dumps(
                    {
                        "host": "localhost",
                        "port": 5432,
                        "database": "demo",
                        "user": "demo",
                        "password": "secret",
                    }
                )
            )
        }

        with patch.dict(
            os.environ,
            environment,
            clear=False,
        ):
            response = self.client.post(
                "/api/sources/test-connection",
                json={
                    "source_type": "postgresql",
                    "connection_reference": (
                        "api-test-postgres"
                    ),
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        mock_connect.assert_called_once()

    @patch(
        "src.connectors.rest_connector.requests.get"
    )
    def test_public_rest_endpoint_is_actually_checked(
        self,
        mock_get,
    ):
        fake_response = Mock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {
            "status": "ok",
        }

        mock_get.return_value = fake_response

        response = self.client.post(
            "/api/sources/test-connection",
            json={
                "source_type": "rest",
                "target_object": (
                    "https://example.com/health"
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        mock_get.assert_called_once()

    @patch("src.api.main.get_connector")
    def test_connection_error_does_not_leak_secrets(
        self,
        mock_get_connector,
    ):
        connector = MagicMock()

        connector.test_connection.side_effect = (
            ConnectorConnectionError(
                "request failed: "
                "https://example.com?"
                "api_key=SUPER-SECRET-TOKEN"
            )
        )

        mock_get_connector.return_value = connector

        response = self.client.post(
            "/api/sources/test-connection",
            json={
                "source_type": "rest",
                "target_object": (
                    "https://example.com/health"
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["success"])

        serialized = response.text

        self.assertNotIn(
            "SUPER-SECRET-TOKEN",
            serialized,
        )
        self.assertNotIn(
            "api_key",
            serialized,
        )


if __name__ == "__main__":
    unittest.main()
