"""Tests for generic Silver runner governance integration."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from src.contracts.loader import load_contract
from src.transformations.silver_runner import (
    execute_silver_pipeline_for_dataset,
    latest_bronze_asset,
    register_data_asset,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class GenericSilverRunnerMetadataTests(unittest.TestCase):
    def test_latest_bronze_asset_returns_asset_and_source_checksum(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value

        cursor.fetchone.return_value = (
            101,
            202,
            "source-checksum-abc",
            "s3://dataforge-bronze/client/project/products/products.parquet",
            10,
        )

        result = latest_bronze_asset(
            conn,
            client_code="olist",
            project_code="olist-alpha",
            source_code="olist-csv",
            dataset_code="products",
        )

        self.assertEqual(result["asset_id"], 101)
        self.assertEqual(result["dataset_version_id"], 202)
        self.assertEqual(
            result["source_checksum"],
            "source-checksum-abc",
        )
        self.assertEqual(
            result["storage_uri"],
            "s3://dataforge-bronze/client/project/products/products.parquet",
        )
        self.assertEqual(result["row_count"], 10)

        sql = cursor.execute.call_args.args[0]

        self.assertIn("da.asset_id", sql)
        self.assertIn("dv.source_checksum", sql)
        self.assertIn("p.project_code = %s", sql)
        self.assertIn("ds.source_code = %s", sql)

        params = cursor.execute.call_args.args[1]

        self.assertEqual(
            params,
            (
                "olist",
                "olist-alpha",
                "olist-csv",
                "products",
            ),
        )

    def test_register_data_asset_returns_asset_id(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (321,)

        asset_id = register_data_asset(
            conn=conn,
            run_id=55,
            layer="silver",
            asset_name="olist_products_silver_validated",
            storage_uri="s3://dataforge-silver/products.parquet",
            row_count=3,
            checksum="abc123",
        )

        self.assertEqual(asset_id, 321)

        sql = cursor.execute.call_args.args[0]
        self.assertIn("RETURNING asset_id", sql)


class GenericSilverRunnerLineageTests(unittest.TestCase):
    def setUp(self):
        self.contract = load_contract(
            PROJECT_ROOT / "config" / "examples" / "olist.yaml"
        )

        self.s3 = MagicMock()
        self.conn = MagicMock()

        self.bronze_frame = pd.DataFrame(
            {
                "product_id": ["p1", "p2", "p3"],
                "product_category_name": ["books", "toys", "games"],
                "product_name_lenght": [10, 20, 30],
                "product_description_lenght": [100, 200, 300],
                "product_photos_qty": [1, 2, 3],
                "product_weight_g": [500.0, 0.0, 800.0],
                "product_length_cm": [10.0, 20.0, 30.0],
                "product_height_cm": [5.0, 10.0, 15.0],
                "product_width_cm": [8.0, 12.0, 18.0],
            }
        )

        self.validated_frame = pd.DataFrame(
            {
                "product_id": ["p1", "p3"],
                "product_category_name": ["books", "games"],
                "product_name_length": [10, 30],
                "product_description_length": [100, 300],
                "product_photos_qty": [1, 3],
                "product_weight_g": [500.0, 800.0],
                "product_length_cm": [10.0, 30.0],
                "product_height_cm": [5.0, 15.0],
                "product_width_cm": [8.0, 18.0],
            }
        )

        self.quarantine_frame = pd.DataFrame(
            {
                "product_id": ["p2"],
                "product_weight_g": [0.0],
            }
        )

        self.quality_results = [
            {
                "rule_name": "product_weight_positive_when_present",
                "rule_type": "greater_than",
                "column": "product_weight_g",
                "severity": "critical",
                "status": "fail",
                "failed_rows": 1,
                "failure_percentage": 33.3333,
            }
        ]

    @patch(
        "src.transformations.silver_runner.finish_pipeline_run"
    )
    @patch(
        "src.transformations.silver_runner.record_quality_results"
    )
    @patch(
        "src.transformations.silver_runner.register_lineage"
    )
    @patch(
        "src.transformations.silver_runner.register_data_asset"
    )
    @patch(
        "src.transformations.silver_runner.evaluate_quality_rules"
    )
    @patch(
        "src.transformations.silver_runner.transform_dataset"
    )
    @patch(
        "src.transformations.silver_runner.pd.read_parquet"
    )
    @patch(
        "src.transformations.silver_runner.sha256_file"
    )
    @patch(
        "src.transformations.silver_runner.start_pipeline_run"
    )
    @patch(
        "src.transformations.silver_runner.latest_bronze_asset"
    )
    def test_validated_and_quarantine_assets_register_lineage(
        self,
        mock_latest_bronze,
        mock_start_run,
        mock_sha256,
        mock_read_parquet,
        mock_transform,
        mock_quality,
        mock_register_asset,
        mock_register_lineage,
        mock_record_quality,
        mock_finish_run,
    ):
        mock_latest_bronze.return_value = {
            "asset_id": 10,
            "dataset_version_id": 20,
            "source_checksum": "source-checksum-123456789",
            "storage_uri": (
                "s3://dataforge-bronze/"
                "olist/olist-alpha/products/products.parquet"
            ),
            "row_count": 3,
        }

        mock_start_run.return_value = 30
        mock_sha256.side_effect = [
            "validated-checksum",
            "quarantine-checksum",
        ]
        mock_read_parquet.return_value = self.bronze_frame
        mock_transform.return_value = self.bronze_frame
        mock_quality.return_value = (
            self.validated_frame,
            self.quarantine_frame,
            self.quality_results,
        )

        mock_register_asset.side_effect = [40, 41]

        result = execute_silver_pipeline_for_dataset(
            contract=self.contract,
            dataset_code="products",
            s3=self.s3,
            conn=self.conn,
            silver_bucket="dataforge-silver",
            quarantine_bucket="dataforge-quarantine",
        )

        self.assertEqual(result["bronze_asset_id"], 10)
        self.assertEqual(result["validated_asset_id"], 40)
        self.assertEqual(result["quarantine_asset_id"], 41)

        self.assertEqual(
            mock_register_lineage.call_count,
            2,
        )

        validated_call = mock_register_lineage.call_args_list[0].kwargs

        self.assertEqual(
            validated_call["parent_asset_id"],
            10,
        )
        self.assertEqual(
            validated_call["child_asset_id"],
            40,
        )
        self.assertEqual(
            validated_call["relation_type"],
            "validated_from",
        )
        self.assertEqual(
            validated_call["created_by_run_id"],
            30,
        )

        quarantine_call = mock_register_lineage.call_args_list[1].kwargs

        self.assertEqual(
            quarantine_call["parent_asset_id"],
            10,
        )
        self.assertEqual(
            quarantine_call["child_asset_id"],
            41,
        )
        self.assertEqual(
            quarantine_call["relation_type"],
            "quarantined_from",
        )
        self.assertEqual(
            quarantine_call["created_by_run_id"],
            30,
        )

        mock_finish_run.assert_called_once_with(
            self.conn,
            30,
            status="success",
            accepted_rows=2,
            rejected_rows=1,
        )

        self.assertGreaterEqual(
            self.conn.commit.call_count,
            2,
        )


if __name__ == "__main__":
    unittest.main()
