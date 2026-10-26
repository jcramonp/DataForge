"""Tests for Generic Gold runner governance integration."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from src.contracts.loader import load_contract
from src.governance.metadata import dataframe_schema_hash
from src.transformations.gold_runner import (
    execute_gold_pipeline_for_dataset,
    latest_validated_silver_asset,
    register_gold_asset,
    update_dataset_version_schema,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class GenericGoldRunnerMetadataTests(unittest.TestCase):
    def test_latest_validated_silver_asset_is_fully_scoped(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value

        cursor.fetchone.return_value = (
            101,
            202,
            "source-checksum",
            "s3://dataforge-silver/products.parquet",
            32947,
            303,
        )

        result = latest_validated_silver_asset(
            conn=conn,
            client_code="olist",
            project_code="olist-alpha",
            source_code="olist-csv",
            dataset_code="products",
        )

        self.assertEqual(result["asset_id"], 101)
        self.assertEqual(result["dataset_version_id"], 202)
        self.assertEqual(result["source_checksum"], "source-checksum")
        self.assertEqual(result["row_count"], 32947)
        self.assertEqual(result["silver_run_id"], 303)

        sql = cursor.execute.call_args.args[0]
        params = cursor.execute.call_args.args[1]

        self.assertIn("da.asset_id", sql)
        self.assertIn("p.project_code = %s", sql)
        self.assertIn("ds.source_code = %s", sql)

        self.assertEqual(
            params,
            (
                "olist",
                "olist-alpha",
                "olist-csv",
                "products",
            ),
        )

    def test_register_gold_asset_returns_asset_id(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value

        cursor.fetchone.return_value = (777,)

        asset_id = register_gold_asset(
            conn=conn,
            run_id=55,
            client_code="olist",
            gold_code="order_items_gold",
            storage_uri="s3://dataforge-gold/order_items_gold.parquet",
            row_count=100,
            checksum="gold-checksum",
        )

        self.assertEqual(asset_id, 777)

        sql = cursor.execute.call_args.args[0]
        self.assertIn("RETURNING asset_id", sql)

    def test_update_dataset_version_schema_persists_hash(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value

        frame = pd.DataFrame(
            {
                "id": pd.Series([1, 2], dtype="Int64"),
                "value": pd.Series(["a", "b"], dtype="string"),
            }
        )

        expected = dataframe_schema_hash(frame)

        result = update_dataset_version_schema(
            conn=conn,
            dataset_version_id=88,
            frame=frame,
        )

        self.assertEqual(result, expected)

        sql = cursor.execute.call_args.args[0]
        params = cursor.execute.call_args.args[1]

        self.assertIn("SET schema_hash = %s", sql)
        self.assertEqual(params, (expected, 88))


class GenericGoldRunnerGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.contract = load_contract(
            PROJECT_ROOT / "config" / "examples" / "olist.yaml"
        )
        self.gold_config = self.contract.gold[0]
        self.s3 = MagicMock()
        self.conn = MagicMock()

    @patch(
        "src.transformations.gold_runner.evaluate_certification"
    )
    @patch(
        "src.transformations.gold_runner.finish_gold_pipeline_run"
    )
    @patch(
        "src.transformations.gold_runner.register_lineage_edges"
    )
    @patch(
        "src.transformations.gold_runner.register_gold_asset"
    )
    @patch(
        "src.transformations.gold_runner.sha256_file"
    )
    @patch(
        "src.transformations.gold_runner.update_dataset_version_schema"
    )
    @patch(
        "src.transformations.gold_runner.build_gold_dataset_from_plan"
    )
    @patch(
        "src.transformations.gold_runner.pd.read_parquet"
    )
    @patch(
        "src.transformations.gold_runner.start_gold_pipeline_run"
    )
    @patch(
        "src.transformations.gold_runner.ensure_gold_dataset_version"
    )
    @patch(
        "src.transformations.gold_runner.latest_validated_silver_asset"
    )
    def test_gold_registers_schema_lineage_and_certification_evaluation(
        self,
        mock_latest,
        mock_ensure_version,
        mock_start_run,
        mock_read_parquet,
        mock_build_gold,
        mock_update_schema,
        mock_sha256,
        mock_register_asset,
        mock_register_lineage,
        mock_finish_run,
        mock_evaluate_certification,
    ):
        asset_ids = {
            "order_items": 101,
            "orders": 102,
            "customers": 103,
            "products": 104,
        }

        row_counts = {
            "order_items": 112650,
            "orders": 99441,
            "customers": 99441,
            "products": 32947,
        }

        def latest_side_effect(
            conn,
            client_code,
            project_code,
            source_code,
            dataset_code,
        ):
            self.assertEqual(client_code, "olist")
            self.assertEqual(project_code, "olist-alpha")
            self.assertEqual(source_code, "olist-csv")

            return {
                "asset_id": asset_ids[dataset_code],
                "dataset_version_id": asset_ids[dataset_code] + 1000,
                "source_checksum": f"checksum-{dataset_code}",
                "storage_uri": (
                    f"s3://dataforge-silver/{dataset_code}.parquet"
                ),
                "row_count": row_counts[dataset_code],
                "silver_run_id": asset_ids[dataset_code] + 2000,
            }

        mock_latest.side_effect = latest_side_effect

        mock_ensure_version.return_value = 500
        mock_start_run.return_value = 600

        mock_read_parquet.return_value = pd.DataFrame(
            {"placeholder": [1]}
        )

        gold_df = pd.DataFrame(
            {
                "order_id": ["o1", "o2"],
                "item_total": [12.5, 25.0],
            }
        )

        mock_build_gold.return_value = gold_df
        mock_update_schema.return_value = "gold-schema-hash"
        mock_sha256.return_value = "gold-file-checksum"
        mock_register_asset.return_value = 700

        mock_evaluate_certification.return_value = {
            "dataset_version_id": 500,
            "criteria": {
                "schema": True,
                "ownership": True,
                "version": True,
                "quality": True,
                "lineage": True,
            },
            "details": {
                "asset_available": True,
            },
            "validation_ready": True,
            "certification_ready": True,
        }

        result = execute_gold_pipeline_for_dataset(
            contract=self.contract,
            gold_config=self.gold_config,
            s3=self.s3,
            conn=self.conn,
            gold_bucket="dataforge-gold",
        )

        self.assertEqual(result["dataset_version_id"], 500)
        self.assertEqual(result["run_id"], 600)
        self.assertEqual(result["gold_asset_id"], 700)
        self.assertEqual(result["schema_hash"], "gold-schema-hash")
        self.assertEqual(result["input_rows"], 112650)
        self.assertEqual(result["output_rows"], 2)

        self.assertEqual(
            result["parent_asset_ids"],
            asset_ids,
        )

        self.assertTrue(
            result["certification"]["certification_ready"]
        )

        mock_update_schema.assert_called_once_with(
            conn=self.conn,
            dataset_version_id=500,
            frame=gold_df,
        )

        mock_register_asset.assert_called_once()

        mock_register_lineage.assert_called_once()

        edges = mock_register_lineage.call_args.args[1]

        self.assertEqual(len(edges), 4)

        self.assertEqual(
            {edge["parent_asset_id"] for edge in edges},
            {101, 102, 103, 104},
        )

        for edge in edges:
            self.assertEqual(
                edge["child_asset_id"],
                700,
            )
            self.assertEqual(
                edge["relation_type"],
                "joined_from",
            )
            self.assertEqual(
                edge["created_by_run_id"],
                600,
            )
            self.assertEqual(
                edge["metadata"]["stage"],
                "silver_to_gold",
            )

        mock_finish_run.assert_called_once_with(
            self.conn,
            run_id=600,
            status="success",
            accepted_rows=2,
            rejected_rows=112648,
        )

        mock_evaluate_certification.assert_called_once_with(
            conn=self.conn,
            dataset_version_id=500,
        )

        self.assertGreaterEqual(
            self.conn.commit.call_count,
            2,
        )


if __name__ == "__main__":
    unittest.main()
