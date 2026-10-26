"""Tests for persistent generic profiling service (#21)."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from src.contracts.loader import load_contract
from src.discovery.service import (
    execute_profiling_for_dataset,
    latest_bronze_asset,
    persist_profile_result,
    redact_sensitive_samples,
    start_profiling_run,
    get_latest_profile,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ProfilingMetadataTests(unittest.TestCase):
    def test_latest_bronze_asset_is_fully_scoped(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (
            101,
            202,
            "source-checksum",
            "s3://dataforge-bronze/client/project/orders/orders.parquet",
            7,
            "asset-checksum",
        )

        result = latest_bronze_asset(
            conn=conn,
            client_code="ci-retail",
            project_code="ci-retail-e2e",
            source_code="ci-retail-csv",
            dataset_code="orders",
        )

        self.assertEqual(result["asset_id"], 101)
        self.assertEqual(result["dataset_version_id"], 202)
        self.assertEqual(result["row_count"], 7)
        self.assertEqual(result["asset_checksum"], "asset-checksum")

        sql = cursor.execute.call_args.args[0]
        params = cursor.execute.call_args.args[1]

        self.assertIn("p.project_code = %s", sql)
        self.assertIn("ds.source_code = %s", sql)
        self.assertIn("pr.run_type = 'source_to_bronze'", sql)
        self.assertIn("da.layer = 'bronze'", sql)

        self.assertEqual(
            params,
            (
                "ci-retail",
                "ci-retail-e2e",
                "ci-retail-csv",
                "orders",
            ),
        )

    def test_start_profiling_run_uses_profiling_stage(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (77,)

        run_id = start_profiling_run(
            conn=conn,
            dataset_version_id=12,
            input_rows=7,
        )

        self.assertEqual(run_id, 77)

        sql = cursor.execute.call_args.args[0]
        self.assertIn("'profiling'", sql)
        self.assertIn("'running'", sql)

    def test_persist_profile_result_returns_profile_id(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (88,)

        profile = {
            "dataset_name": "orders",
            "row_count": 2,
            "column_count": 2,
            "duplicate_rows": 0,
            "duplicate_rows_percentage": 0.0,
            "candidate_keys": ["order_id"],
            "memory_bytes": 100,
            "columns": {
                "order_id": {
                    "name": "order_id",
                    "inferred_type": "string",
                }
            },
            "generated_at_utc": "2026-10-26T05:00:00+00:00",
        }

        profile_id = persist_profile_result(
            conn=conn,
            run_id=77,
            source_asset_id=101,
            profile=profile,
        )

        self.assertEqual(profile_id, 88)

        sql = cursor.execute.call_args.args[0]
        self.assertIn("INSERT INTO profiling_result", sql)
        self.assertIn("RETURNING profile_id", sql)


    def test_sensitive_samples_are_redacted(self):
        contract = load_contract(
            PROJECT_ROOT
            / "tests"
            / "fixtures"
            / "e2e"
            / "retail_contract.yaml"
        )
        dataset = contract.datasets[0]

        profile = {
            "dataset_name": "orders",
            "columns": {
                "order_id": {
                    "sample_values": ["R1", "R2"],
                },
                "customer_email": {
                    "sample_values": [
                        "alice@example.com",
                        "bob@example.com",
                    ],
                },
                "amount": {
                    "sample_values": [10.0, 20.0],
                },
            },
        }

        safe = redact_sensitive_samples(
            profile=profile,
            dataset=dataset,
        )

        self.assertEqual(
            safe["columns"]["order_id"]["sample_values"],
            ["R1", "R2"],
        )
        self.assertEqual(
            safe["columns"]["amount"]["sample_values"],
            [10.0, 20.0],
        )
        self.assertEqual(
            safe["columns"]["customer_email"]["sample_values"],
            [],
        )
        self.assertTrue(
            safe["columns"]["customer_email"]["sample_values_redacted"]
        )

        # The original profiler result must remain untouched.
        self.assertEqual(
            profile["columns"]["customer_email"]["sample_values"],
            [
                "alice@example.com",
                "bob@example.com",
            ],
        )


class ProfilingExecutionTests(unittest.TestCase):
    def setUp(self):
        self.contract = load_contract(
            PROJECT_ROOT
            / "tests"
            / "fixtures"
            / "e2e"
            / "retail_contract.yaml"
        )

    @patch("src.discovery.service.finish_profiling_run")
    @patch("src.discovery.service.persist_profile_result")
    @patch("src.discovery.service.profile_dataframe")
    @patch("src.discovery.service.pd.read_parquet")
    @patch("src.discovery.service.sha256_file")
    @patch("src.discovery.service.start_profiling_run")
    @patch("src.discovery.service.latest_bronze_asset")
    def test_success_profiles_exact_bronze_asset(
        self,
        mock_latest,
        mock_start,
        mock_sha256,
        mock_read,
        mock_profile,
        mock_persist,
        mock_finish,
    ):
        conn = MagicMock()
        s3 = MagicMock()

        mock_latest.return_value = {
            "asset_id": 101,
            "dataset_version_id": 202,
            "source_checksum": "source-checksum",
            "storage_uri": "s3://dataforge-bronze/orders.parquet",
            "row_count": 2,
            "asset_checksum": "bronze-checksum",
        }

        mock_start.return_value = 303
        mock_sha256.return_value = "bronze-checksum"

        frame = pd.DataFrame(
            {
                "order_id": ["r1", "r2"],
                "amount": [10.0, 20.0],
            }
        )
        mock_read.return_value = frame

        profile = {
            "dataset_name": "orders",
            "row_count": 2,
            "column_count": 2,
            "duplicate_rows": 0,
            "duplicate_rows_percentage": 0.0,
            "candidate_keys": ["order_id", "amount"],
            "memory_bytes": 200,
            "columns": {},
            "generated_at_utc": "2026-10-26T05:00:00+00:00",
        }
        mock_profile.return_value = profile
        mock_persist.return_value = 404

        result = execute_profiling_for_dataset(
            contract=self.contract,
            dataset_code="orders",
            s3=s3,
            conn=conn,
        )

        self.assertEqual(result["profile_id"], 404)
        self.assertEqual(result["run_id"], 303)
        self.assertEqual(result["source_asset_id"], 101)
        self.assertEqual(result["dataset_version_id"], 202)
        self.assertEqual(result["row_count"], 2)

        mock_persist.assert_called_once_with(
            conn=conn,
            run_id=303,
            source_asset_id=101,
            profile=profile,
        )

        mock_finish.assert_called_once_with(
            conn=conn,
            run_id=303,
            status="success",
            accepted_rows=2,
            rejected_rows=0,
        )

        self.assertGreaterEqual(conn.commit.call_count, 2)

    @patch("src.discovery.service.finish_profiling_run")
    @patch("src.discovery.service.sha256_file")
    @patch("src.discovery.service.start_profiling_run")
    @patch("src.discovery.service.latest_bronze_asset")
    def test_checksum_mismatch_records_failed_run(
        self,
        mock_latest,
        mock_start,
        mock_sha256,
        mock_finish,
    ):
        conn = MagicMock()
        s3 = MagicMock()

        mock_latest.return_value = {
            "asset_id": 101,
            "dataset_version_id": 202,
            "source_checksum": "source-checksum",
            "storage_uri": "s3://dataforge-bronze/orders.parquet",
            "row_count": 7,
            "asset_checksum": "expected-checksum",
        }

        mock_start.return_value = 303
        mock_sha256.return_value = "different-checksum"

        with self.assertRaisesRegex(
            RuntimeError,
            "Bronze asset checksum mismatch",
        ):
            execute_profiling_for_dataset(
                contract=self.contract,
                dataset_code="orders",
                s3=s3,
                conn=conn,
            )

        conn.rollback.assert_called_once()

        mock_finish.assert_called_once()
        failure_call = mock_finish.call_args.kwargs

        self.assertEqual(failure_call["run_id"], 303)
        self.assertEqual(failure_call["status"], "failed")
        self.assertIn(
            "Bronze asset checksum mismatch",
            failure_call["error_message"],
        )


class ProfilingReadServiceTests(unittest.TestCase):
    def test_get_latest_profile_returns_unique_dataset(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value

        profile = {
            "dataset_name": "customers",
            "row_count": 99441,
            "column_count": 5,
            "columns": {
                "customer_id": {
                    "inferred_type": "string",
                }
            },
        }

        cursor.fetchall.return_value = [
            (
                1,
                "olist",
                "olist-alpha",
                "olist-csv",
                "customers",
                1,
                "abc123",
                60,
                24,
                "s3://dataforge-bronze/olist/customers.parquet",
                99441,
                5,
                None,
                profile,
            )
        ]

        result = get_latest_profile(
            conn=conn,
            dataset_code="customers",
            client_code="olist",
            project_code="olist-alpha",
            source_code="olist-csv",
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["profile_id"], 1)
        self.assertEqual(result["run_id"], 60)
        self.assertEqual(result["source_asset_id"], 24)
        self.assertEqual(result["profile"], profile)

        sql = cursor.execute.call_args.args[0]
        params = cursor.execute.call_args.args[1]

        self.assertIn("dataset_code = %s", sql)
        self.assertIn("client_code = %s", sql)
        self.assertIn("project_code = %s", sql)
        self.assertIn("source_code = %s", sql)

        self.assertEqual(
            params,
            (
                "customers",
                "olist",
                "olist-alpha",
                "olist-csv",
            ),
        )

    def test_get_latest_profile_returns_none_when_missing(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = []

        result = get_latest_profile(
            conn=conn,
            dataset_code="missing",
        )

        self.assertIsNone(result)

    def test_get_latest_profile_rejects_ambiguous_dataset_code(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value

        cursor.fetchall.return_value = [
            (
                1,
                "olist",
                "olist-alpha",
                "olist-csv",
                "orders",
                3,
                "version-a",
                61,
                25,
                "s3://bucket/olist-orders.parquet",
                99441,
                8,
                None,
                {},
            ),
            (
                5,
                "ci-retail",
                "ci-retail-e2e",
                "ci-retail-csv",
                "orders",
                7,
                "version-b",
                65,
                66,
                "s3://bucket/retail-orders.parquet",
                7,
                5,
                None,
                {},
            ),
        ]

        with self.assertRaisesRegex(
            ValueError,
            "Ambiguous dataset profiling lookup",
        ):
            get_latest_profile(
                conn=conn,
                dataset_code="orders",
            )


if __name__ == "__main__":
    unittest.main()
