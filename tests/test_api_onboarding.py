"""FastAPI tests for self-service contract onboarding (#25)."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import psycopg
from fastapi.testclient import TestClient

from src.api.control_plane import (
    ControlPlaneConflictError,
    InlineSecretError,
    canonical_contract_payload,
)
from src.api.main import app
from src.contracts.loader import load_contract


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONTRACT_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "e2e"
    / "retail_contract.yaml"
)


def contract_payload() -> dict:
    return canonical_contract_payload(
        load_contract(CONTRACT_PATH)
    )


def registration_result(
    *,
    created: bool = True,
    reactivated: bool = False,
) -> dict:
    return {
        "client_id": 10,
        "project_id": 20,
        "source_id": 30,
        "contract_id": 40,
        "contract_version": "1.0",
        "revision": 1,
        "contract_hash": "a" * 64,
        "status": "active",
        "created": created,
        "reactivated": reactivated,
        "datasets": [
            {
                "dataset_id": 50,
                "dataset_code": "orders",
            }
        ],
    }


class ApiOnboardingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @patch("src.api.main.register_contract")
    @patch("src.api.main.connect_postgres")
    def test_new_contract_returns_201(
        self,
        mock_connect,
        mock_register,
    ):
        conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = conn

        mock_register.return_value = registration_result()

        response = self.client.post(
            "/api/onboarding/contracts",
            json=contract_payload(),
        )

        self.assertEqual(
            response.status_code,
            201,
        )

        body = response.json()

        self.assertEqual(
            body["contract_id"],
            40,
        )
        self.assertEqual(
            body["revision"],
            1,
        )
        self.assertTrue(
            body["created"],
        )
        self.assertEqual(
            body["datasets"],
            [
                {
                    "dataset_id": 50,
                    "dataset_code": "orders",
                }
            ],
        )

        mock_register.assert_called_once_with(
            conn,
            unittest.mock.ANY,
            created_by="api",
        )

    @patch("src.api.main.register_contract")
    @patch("src.api.main.connect_postgres")
    def test_identical_contract_returns_200(
        self,
        mock_connect,
        mock_register,
    ):
        mock_connect.return_value.__enter__.return_value = (
            MagicMock()
        )

        mock_register.return_value = registration_result(
            created=False,
        )

        response = self.client.post(
            "/api/onboarding/contracts",
            json=contract_payload(),
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertFalse(
            response.json()["created"],
        )

    @patch("src.api.main.register_contract")
    @patch("src.api.main.connect_postgres")
    def test_reactivated_contract_returns_200(
        self,
        mock_connect,
        mock_register,
    ):
        mock_connect.return_value.__enter__.return_value = (
            MagicMock()
        )

        mock_register.return_value = registration_result(
            created=False,
            reactivated=True,
        )

        response = self.client.post(
            "/api/onboarding/contracts",
            json=contract_payload(),
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertTrue(
            response.json()["reactivated"],
        )

    @patch("src.api.main.register_contract")
    @patch("src.api.main.connect_postgres")
    def test_metadata_identity_conflict_returns_409(
        self,
        mock_connect,
        mock_register,
    ):
        mock_connect.return_value.__enter__.return_value = (
            MagicMock()
        )

        mock_register.side_effect = (
            ControlPlaneConflictError(
                "Project code already belongs to another client"
            )
        )

        response = self.client.post(
            "/api/onboarding/contracts",
            json=contract_payload(),
        )

        self.assertEqual(
            response.status_code,
            409,
        )
        self.assertIn(
            "another client",
            response.json()["detail"],
        )

    @patch("src.api.main.register_contract")
    @patch("src.api.main.connect_postgres")
    def test_inline_secret_returns_422_without_leaking_value(
        self,
        mock_connect,
        mock_register,
    ):
        mock_connect.return_value.__enter__.return_value = (
            MagicMock()
        )

        mock_register.side_effect = InlineSecretError(
            "Inline credentials are not allowed. "
            "Sensitive field(s): "
            "contract.datasets[0].source_object.headers.Authorization"
        )

        response = self.client.post(
            "/api/onboarding/contracts",
            json=contract_payload(),
        )

        self.assertEqual(
            response.status_code,
            422,
        )

        detail = response.json()["detail"]

        self.assertIn(
            "Inline credentials",
            detail,
        )
        self.assertNotIn(
            "Bearer",
            detail,
        )

    @patch("src.api.main.register_contract")
    @patch("src.api.main.connect_postgres")
    def test_database_failure_returns_503(
        self,
        mock_connect,
        mock_register,
    ):
        mock_connect.return_value.__enter__.return_value = (
            MagicMock()
        )

        mock_register.side_effect = psycopg.OperationalError(
            "database unavailable"
        )

        response = self.client.post(
            "/api/onboarding/contracts",
            json=contract_payload(),
        )

        self.assertEqual(
            response.status_code,
            503,
        )

        self.assertEqual(
            response.json()["detail"],
            "Control-plane database unavailable",
        )

    @patch("src.api.main.connect_postgres")
    def test_invalid_contract_is_rejected_before_database_access(
        self,
        mock_connect,
    ):
        payload = contract_payload()
        payload.pop("datasets")

        response = self.client.post(
            "/api/onboarding/contracts",
            json=payload,
        )

        self.assertEqual(
            response.status_code,
            422,
        )

        mock_connect.assert_not_called()

    def test_openapi_documents_onboarding_contract(self):
        response = self.client.get(
            "/openapi.json"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        schema = response.json()

        self.assertIn(
            "/api/onboarding/contracts",
            schema["paths"],
        )

        operation = schema["paths"][
            "/api/onboarding/contracts"
        ]["post"]

        self.assertIn(
            "requestBody",
            operation,
        )

        self.assertIn(
            "200",
            operation["responses"],
        )
        self.assertIn(
            "201",
            operation["responses"],
        )
        self.assertIn(
            "409",
            operation["responses"],
        )
        self.assertIn(
            "422",
            operation["responses"],
        )
        self.assertIn(
            "503",
            operation["responses"],
        )


if __name__ == "__main__":
    unittest.main()
