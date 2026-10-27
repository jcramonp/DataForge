"""Tests for real PostgreSQL + MinIO quarantine API."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import unittest

import pandas as pd
import yaml
from fastapi.testclient import TestClient

from src.api.control_plane import ControlPlaneConflictError
from src.api.main import app
from src.api.quarantine import build_quarantine_records
from src.contracts.models import DataForgeContract


def retail_contract():
    payload = yaml.safe_load(
        Path(
            "tests/fixtures/e2e/retail_contract.yaml"
        ).read_text(encoding="utf-8")
    )
    return DataForgeContract.model_validate(payload)


def quarantine_frame():
    return pd.DataFrame(
        {
            "order_id": [
                "R4",
                pd.NA,
                "R6",
            ],
            "customer_email": [
                "r4@example.com",
                "r5@example.com",
                "r6@example.com",
            ],
            "amount": [
                -3.0,
                7.0,
                8.0,
            ],
            "status": [
                "PAID",
                "PAID",
                "LOST",
            ],
            "created_at": [
                "2026-01-04",
                "2026-01-05",
                "2026-01-06",
            ],
        }
    )


class QuarantineBuilderTests(unittest.TestCase):
    def test_reconstructs_only_critical_violations(self):
        contract = retail_contract()
        dataset = contract.datasets[0]

        records = build_quarantine_records(
            quarantine_frame(),
            dataset,
            asset_id=69,
            run_id=69,
            quarantined_at=datetime(
                2026,
                10,
                26,
                9,
                36,
                47,
                tzinfo=timezone.utc,
            ),
        )

        self.assertEqual(len(records), 3)

        by_rule = {
            item["rule_violated"]: item
            for item in records
        }

        self.assertEqual(
            set(by_rule),
            {
                "order_id_present",
                "amount_non_negative",
                "status_known",
            },
        )

        self.assertEqual(
            by_rule["amount_non_negative"]["record_id"],
            "R4",
        )
        self.assertEqual(
            by_rule["amount_non_negative"]["observed_value"],
            -3.0,
        )

        self.assertEqual(
            by_rule["order_id_present"]["record_id"],
            "row-2",
        )
        self.assertIsNone(
            by_rule["order_id_present"]["observed_value"]
        )

        self.assertEqual(
            by_rule["status_known"]["record_id"],
            "R6",
        )
        self.assertEqual(
            by_rule["status_known"]["observed_value"],
            "LOST",
        )

        self.assertNotIn(
            "email_format",
            by_rule,
        )


class ApiQuarantineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @patch("src.api.main.pd.read_parquet")
    @patch("src.api.main.create_s3_client")
    @patch("src.api.main.load_persisted_contract")
    @patch("src.api.main.get_dataset_quarantine_context")
    @patch("src.api.main.connect_postgres")
    def test_scoped_quarantine_uses_real_components(
        self,
        mock_connect,
        mock_context,
        mock_load_contract,
        mock_s3_factory,
        mock_read_parquet,
    ):
        conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = conn

        created_at = datetime(
            2026,
            10,
            26,
            9,
            36,
            47,
            tzinfo=timezone.utc,
        )

        mock_context.return_value = {
            "dataset_id": 20,
            "dataset_name": "Retail Orders",
            "source_id": 14,
            "client_code": "ci-retail",
            "project_code": "ci-retail-e2e",
            "source_code": "ci-retail-csv",
            "contract_id": 1,
            "asset": {
                "run_id": 69,
                "asset_id": 69,
                "storage_uri": (
                    "s3://dataforge-quarantine/"
                    "ci-retail/orders.parquet"
                ),
                "row_count": 3,
                "created_at": created_at,
            },
        }

        mock_load_contract.return_value = retail_contract()
        mock_read_parquet.return_value = quarantine_frame()

        response = self.client.get(
            "/api/datasets/orders/quarantine",
            params={
                "client_code": "ci-retail",
                "project_code": "ci-retail-e2e",
                "source_code": "ci-retail-csv",
            },
        )

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertEqual(len(body), 3)
        self.assertEqual(
            {
                item["rule_violated"]
                for item in body
            },
            {
                "order_id_present",
                "amount_non_negative",
                "status_known",
            },
        )

        mock_context.assert_called_once_with(
            conn,
            "orders",
            client_code="ci-retail",
            project_code="ci-retail-e2e",
            source_code="ci-retail-csv",
        )

        mock_load_contract.assert_called_once_with(1)

        mock_s3_factory.return_value.download_file.assert_called_once()

    @patch("src.api.main.get_dataset_quarantine_context")
    @patch("src.api.main.connect_postgres")
    def test_dataset_without_quarantine_returns_empty(
        self,
        mock_connect,
        mock_context,
    ):
        mock_connect.return_value.__enter__.return_value = MagicMock()

        mock_context.return_value = {
            "dataset_id": 20,
            "dataset_name": "Retail Orders",
            "source_id": 14,
            "client_code": "ci-retail",
            "project_code": "ci-retail-e2e",
            "source_code": "ci-retail-csv",
            "contract_id": 1,
            "asset": None,
        }

        response = self.client.get(
            "/api/datasets/orders/quarantine",
            params={
                "client_code": "ci-retail",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    @patch("src.api.main.get_dataset_quarantine_context")
    @patch("src.api.main.connect_postgres")
    def test_missing_dataset_returns_404(
        self,
        mock_connect,
        mock_context,
    ):
        mock_connect.return_value.__enter__.return_value = MagicMock()
        mock_context.return_value = None

        response = self.client.get(
            "/api/datasets/missing/quarantine"
        )

        self.assertEqual(response.status_code, 404)

    @patch(
        "src.api.main.get_dataset_quarantine_context",
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
            "/api/datasets/orders/quarantine"
        )

        self.assertEqual(response.status_code, 409)

    @patch("src.api.main.pd.read_parquet")
    @patch("src.api.main.create_s3_client")
    @patch("src.api.main.load_persisted_contract")
    @patch("src.api.main.get_dataset_quarantine_context")
    @patch("src.api.main.connect_postgres")
    def test_storage_failure_returns_safe_503(
        self,
        mock_connect,
        mock_context,
        mock_load_contract,
        mock_s3_factory,
        _mock_read_parquet,
    ):
        mock_connect.return_value.__enter__.return_value = MagicMock()

        mock_context.return_value = {
            "dataset_id": 20,
            "dataset_name": "Retail Orders",
            "source_id": 14,
            "client_code": "ci-retail",
            "project_code": "ci-retail-e2e",
            "source_code": "ci-retail-csv",
            "contract_id": 1,
            "asset": {
                "run_id": 69,
                "asset_id": 69,
                "storage_uri": (
                    "s3://dataforge-quarantine/"
                    "ci-retail/orders.parquet"
                ),
                "row_count": 3,
                "created_at": datetime.now(timezone.utc),
            },
        }

        mock_load_contract.return_value = retail_contract()

        mock_s3_factory.return_value.download_file.side_effect = (
            RuntimeError("secret-storage-error")
        )

        response = self.client.get(
            "/api/datasets/orders/quarantine",
            params={
                "client_code": "ci-retail",
            },
        )

        self.assertEqual(response.status_code, 503)
        self.assertNotIn(
            "secret-storage-error",
            response.text,
        )


if __name__ == "__main__":
    unittest.main()
