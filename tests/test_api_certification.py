"""Tests for governance-backed certification API."""

from unittest.mock import MagicMock, patch
import unittest

import psycopg
from fastapi.testclient import TestClient

from src.api.control_plane import ControlPlaneConflictError
from src.api.main import app
from src.governance.certification import (
    CertificationTransitionError,
)


TARGET = {
    "client_code": "ci-retail",
    "project_code": "ci-retail-e2e",
    "source_code": "ci-retail-csv",
    "dataset_id": 23,
    "dataset_code": "orders_by_status",
    "dataset_name": "Orders by Status",
    "dataset_version_id": 22,
    "version_label": "gold-test",
    "certification_id": 12,
    "state": "draft",
    "stored_criteria": {},
    "last_evaluated_at": None,
    "validated_at": None,
    "certified_at": None,
    "created_at": None,
    "updated_at": None,
}

EVALUATION = {
    "dataset_version_id": 22,
    "criteria": {
        "schema": True,
        "ownership": True,
        "version": True,
        "quality": True,
        "lineage": True,
    },
    "details": {
        "asset_available": True,
        "asset_count": 1,
        "assets_with_upstream_lineage": 1,
        "quality_evaluated": True,
        "quality_rule_count": 5,
        "critical_quality_failures": 3,
        "successful_quality_gate_runs": 1,
    },
    "validation_ready": True,
    "certification_ready": True,
}


class ApiCertificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @patch("src.api.main.evaluate_certification")
    @patch("src.api.main.list_certification_targets")
    @patch("src.api.main.connect_postgres")
    def test_list_certifications_uses_real_services(
        self,
        mock_connect,
        mock_targets,
        mock_evaluate,
    ):
        conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = conn

        mock_targets.return_value = [TARGET]
        mock_evaluate.return_value = EVALUATION

        response = self.client.get(
            "/api/certification",
            params={
                "client_code": "ci-retail",
                "project_code": "ci-retail-e2e",
                "source_code": "ci-retail-csv",
                "dataset_code": "orders_by_status",
            },
        )

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["status"], "draft")
        self.assertTrue(body[0]["certification_ready"])
        self.assertTrue(body[0]["criteria"]["quality"])

        mock_targets.assert_called_once_with(
            conn,
            client_code="ci-retail",
            project_code="ci-retail-e2e",
            source_code="ci-retail-csv",
            dataset_code="orders_by_status",
        )

        mock_evaluate.assert_called_once_with(
            conn,
            22,
        )

    @patch(
        "src.api.main.transition_certification",
        side_effect=CertificationTransitionError(
            "Invalid certification transition: draft -> certified"
        ),
    )
    @patch("src.api.main.resolve_latest_dataset_version")
    @patch("src.api.main.connect_postgres")
    def test_invalid_transition_returns_409(
        self,
        mock_connect,
        mock_resolve,
        _,
    ):
        mock_connect.return_value.__enter__.return_value = MagicMock()

        mock_resolve.return_value = {
            **TARGET,
            "source_id": 14,
        }

        response = self.client.post(
            "/api/certification/orders_by_status",
            params={
                "client_code": "ci-retail",
            },
            json={
                "status": "certified",
                "certified_by": "api-test",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn(
            "draft -> certified",
            response.json()["detail"],
        )

    @patch("src.api.main.get_certification_history")
    @patch("src.api.main.evaluate_certification")
    @patch("src.api.main.transition_certification")
    @patch("src.api.main.resolve_latest_dataset_version")
    @patch("src.api.main.connect_postgres")
    def test_valid_transition_returns_updated_state(
        self,
        mock_connect,
        mock_resolve,
        mock_transition,
        mock_evaluate,
        mock_history,
    ):
        conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = conn

        mock_resolve.return_value = {
            **TARGET,
            "source_id": 14,
        }

        mock_transition.return_value = {
            "certification_id": 12,
            "dataset_version_id": 22,
            "state": "validated",
            "criteria": {},
            "last_evaluated_at": None,
            "validated_at": None,
            "certified_at": None,
            "created_at": None,
            "updated_at": None,
        }

        mock_evaluate.return_value = EVALUATION

        mock_history.return_value = [
            {
                "transition_id": 12,
                "from_state": "draft",
                "to_state": "validated",
                "reason": "API test",
                "criteria": {},
                "changed_by": "api-test",
                "changed_at": None,
            }
        ]

        response = self.client.post(
            "/api/certification/orders_by_status",
            params={
                "client_code": "ci-retail",
                "project_code": "ci-retail-e2e",
                "source_code": "ci-retail-csv",
            },
            json={
                "status": "validated",
                "certified_by": "api-test",
                "notes": "API test",
            },
        )

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertEqual(
            body["status"],
            "validated",
        )
        self.assertTrue(
            body["certification_ready"]
        )
        self.assertEqual(
            body["history"][0]["changed_by"],
            "api-test",
        )

        mock_transition.assert_called_once_with(
            conn,
            22,
            "validated",
            reason="API test",
            changed_by="api-test",
        )

    @patch("src.api.main.get_certification_history")
    @patch("src.api.main.get_certification_record")
    @patch("src.api.main.resolve_latest_dataset_version")
    @patch("src.api.main.connect_postgres")
    def test_history_uses_persisted_governance_data(
        self,
        mock_connect,
        mock_resolve,
        mock_current,
        mock_history,
    ):
        conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = conn

        mock_resolve.return_value = {
            **TARGET,
            "source_id": 14,
        }

        mock_current.return_value = {
            "certification_id": 12,
            "dataset_version_id": 22,
            "state": "certified",
            "criteria": {},
            "last_evaluated_at": None,
            "validated_at": None,
            "certified_at": None,
            "created_at": None,
            "updated_at": None,
        }

        mock_history.return_value = [
            {
                "transition_id": 11,
                "from_state": None,
                "to_state": "draft",
                "reason": "Dataset version created",
                "criteria": {},
                "changed_by": "system",
                "changed_at": None,
            },
            {
                "transition_id": 12,
                "from_state": "draft",
                "to_state": "validated",
                "reason": "Governance validation",
                "criteria": {},
                "changed_by": "api-test",
                "changed_at": None,
            },
            {
                "transition_id": 13,
                "from_state": "validated",
                "to_state": "certified",
                "reason": "Governance certification",
                "criteria": {},
                "changed_by": "api-test",
                "changed_at": None,
            },
        ]

        response = self.client.get(
            "/api/certification/orders_by_status/history",
            params={
                "client_code": "ci-retail",
            },
        )

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertEqual(
            body["certification"]["state"],
            "certified",
        )
        self.assertEqual(
            len(body["history"]),
            3,
        )
        self.assertEqual(
            body["history"][0]["to_state"],
            "draft",
        )

    @patch(
        "src.api.main.resolve_latest_dataset_version",
        side_effect=ControlPlaneConflictError(
            "Dataset code 'orders' is ambiguous"
        ),
    )
    @patch("src.api.main.connect_postgres")
    def test_ambiguous_dataset_transition_returns_409(
        self,
        mock_connect,
        _,
    ):
        mock_connect.return_value.__enter__.return_value = MagicMock()

        response = self.client.post(
            "/api/certification/orders",
            json={
                "status": "validated",
            },
        )

        self.assertEqual(response.status_code, 409)

    @patch(
        "src.api.main.connect_postgres",
        side_effect=psycopg.OperationalError(
            "secret-certification-db-error"
        ),
    )
    def test_database_failure_returns_safe_503(
        self,
        _,
    ):
        response = self.client.get(
            "/api/certification"
        )

        self.assertEqual(response.status_code, 503)
        self.assertNotIn(
            "secret-certification-db-error",
            response.text,
        )


if __name__ == "__main__":
    unittest.main()
