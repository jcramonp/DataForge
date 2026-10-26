"""Comprehensive unit and integration tests for Generic Configurable Gold Engine."""

import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.contracts.loader import load_contract
from src.contracts.models import (
    AggregationConfig,
    AggregationFunction,
    DerivedOperation,
    FilterOperator,
    GoldConfig,
    GoldOperation,
    GoldStepConfig,
    JoinHow,
)
from src.transformations.gold_generic import (
    build_gold_dataset_from_plan,
    execute_aggregate,
    execute_derive,
    execute_drop,
    execute_filter,
    execute_gold_step,
    execute_join,
    execute_rename,
    execute_select,
)
from src.transformations.gold_runner import parse_s3_uri

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class GenericGoldOperationsTests(unittest.TestCase):
    def test_execute_select(self):
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6]})
        selected = execute_select(df, ["c", "a"])
        self.assertEqual(list(selected.columns), ["c", "a"])
        self.assertEqual(selected["c"].tolist(), [5, 6])

        with self.assertRaises(ValueError):
            execute_select(df, ["non_existent"])

    def test_execute_drop(self):
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6]})
        dropped = execute_drop(df, ["b", "unknown"])
        self.assertEqual(list(dropped.columns), ["a", "c"])

    def test_execute_rename(self):
        df = pd.DataFrame({"old_name": [10, 20]})
        renamed = execute_rename(df, "old_name", "new_name")
        self.assertIn("new_name", renamed.columns)
        self.assertNotIn("old_name", renamed.columns)
        self.assertEqual(renamed["new_name"].tolist(), [10, 20])

        with self.assertRaises(ValueError):
            execute_rename(df, "missing", "target")

    def test_execute_filter_operators(self):
        df = pd.DataFrame(
            {
                "status": ["active", "pending", "closed", "active"],
                "score": [10, 25, 50, 75],
            }
        )

        eq_res = execute_filter(df, "status", FilterOperator.EQUAL, "active")
        self.assertEqual(len(eq_res), 2)

        ne_res = execute_filter(df, "status", FilterOperator.NOT_EQUAL, "active")
        self.assertEqual(len(ne_res), 2)

        gt_res = execute_filter(df, "score", FilterOperator.GREATER_THAN, 25)
        self.assertEqual(len(gt_res), 2)
        self.assertEqual(gt_res["score"].tolist(), [50, 75])

        gte_res = execute_filter(df, "score", FilterOperator.GREATER_THAN_OR_EQUAL, 25)
        self.assertEqual(len(gte_res), 3)

        lt_res = execute_filter(df, "score", FilterOperator.LESS_THAN, 50)
        self.assertEqual(len(lt_res), 2)

        lte_res = execute_filter(df, "score", FilterOperator.LESS_THAN_OR_EQUAL, 50)
        self.assertEqual(len(lte_res), 3)

        in_res = execute_filter(df, "status", FilterOperator.IN, ["pending", "closed"])
        self.assertEqual(len(in_res), 2)

        not_in_res = execute_filter(df, "status", FilterOperator.NOT_IN, ["active"])
        self.assertEqual(len(not_in_res), 2)

        with self.assertRaises(ValueError):
            execute_filter(df, "missing_col", FilterOperator.EQUAL, "x")

    def test_execute_join_and_deduplication(self):
        left = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "left_val": ["L1", "L2", "L3"],
                "shared_name": ["Alpha", "Beta", "Gamma"],
            }
        )
        right = pd.DataFrame(
            {
                "id": [2, 3, 4],
                "right_val": ["R2", "R3", "R4"],
                "shared_name": ["Beta_dup", "Gamma_dup", "Delta"],
            }
        )

        inner = execute_join(left, right, left_on=["id"], right_on=["id"], how=JoinHow.INNER)
        self.assertEqual(len(inner), 2)
        self.assertEqual(inner["id"].tolist(), [2, 3])
        # Duplicate column from right side should be dropped, preserving left's column
        self.assertIn("shared_name", inner.columns)
        self.assertNotIn("shared_name_right_dup", inner.columns)
        self.assertEqual(inner["shared_name"].tolist(), ["Beta", "Gamma"])

        left_join = execute_join(left, right, left_on=["id"], right_on=["id"], how=JoinHow.LEFT)
        self.assertEqual(len(left_join), 3)
        self.assertTrue(pd.isna(left_join.loc[left_join["id"] == 1, "right_val"].iloc[0]))

    def test_execute_derive(self):
        df = pd.DataFrame(
            {
                "price": [100.0, 200.0],
                "freight": [15.0, 25.0],
                "discount": [5.0, 10.0],
                "tax": [2.0, 0.0],
            }
        )

        # Addition: price + freight
        add_res = execute_derive(
            df,
            operation=DerivedOperation.ADD,
            operands=["price", "freight"],
            output_column="total_cost",
        )
        self.assertEqual(add_res["total_cost"].tolist(), [115.0, 225.0])

        # Subtraction: price - discount
        sub_res = execute_derive(
            df,
            operation=DerivedOperation.SUBTRACT,
            operands=["price", "discount"],
            output_column="net_price",
        )
        self.assertEqual(sub_res["net_price"].tolist(), [95.0, 190.0])

        # Multiplication
        mul_res = execute_derive(
            df,
            operation=DerivedOperation.MULTIPLY,
            operands=["freight", "tax"],
            output_column="freight_tax",
        )
        self.assertEqual(mul_res["freight_tax"].tolist(), [30.0, 0.0])

        # Division with zero
        div_res = execute_derive(
            df,
            operation=DerivedOperation.DIVIDE,
            operands=["freight", "tax"],
            output_column="ratio",
        )
        self.assertEqual(div_res["ratio"].iloc[0], 7.5)
        self.assertTrue(pd.isna(div_res["ratio"].iloc[1]))

    def test_execute_aggregate(self):
        df = pd.DataFrame(
            {
                "category": ["electronics", "electronics", "furniture", "furniture"],
                "units": [2, 5, 1, 3],
                "revenue": [200.0, 500.0, 150.0, 450.0],
            }
        )

        aggs = [
            AggregationConfig(column="units", function=AggregationFunction.SUM, alias="total_units"),
            AggregationConfig(column="revenue", function=AggregationFunction.AVG, alias="avg_revenue"),
            AggregationConfig(column="revenue", function=AggregationFunction.MAX, alias="max_revenue"),
            AggregationConfig(column="units", function=AggregationFunction.COUNT, alias="order_count"),
        ]

        agg_df = execute_aggregate(
            df,
            group_by_columns=["category"],
            aggregations=aggs,
        )

        self.assertEqual(len(agg_df), 2)
        self.assertIn("category", agg_df.columns)
        self.assertIn("total_units", agg_df.columns)
        self.assertIn("avg_revenue", agg_df.columns)

        elec_row = agg_df[agg_df["category"] == "electronics"].iloc[0]
        self.assertEqual(elec_row["total_units"], 7)
        self.assertEqual(elec_row["avg_revenue"], 350.0)
        self.assertEqual(elec_row["max_revenue"], 500.0)
        self.assertEqual(elec_row["order_count"], 2)

    def test_execute_aggregate_without_group_by(self):
        df = pd.DataFrame({"val": [10, 20, 30]})
        aggs = [
            AggregationConfig(column="val", function=AggregationFunction.SUM, alias="grand_total"),
            AggregationConfig(column="val", function=AggregationFunction.MIN, alias="min_val"),
        ]
        agg_df = execute_aggregate(df, group_by_columns=None, aggregations=aggs)
        self.assertEqual(len(agg_df), 1)
        self.assertEqual(agg_df["grand_total"].iloc[0], 60)
        self.assertEqual(agg_df["min_val"].iloc[0], 10)


class GenericGoldPipelineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.customers = pd.DataFrame(
            {
                "customer_id": ["c1", "c2"],
                "customer_state": ["SP", "RJ"],
                "customer_zip_code_prefix": [1000, 2000],
            }
        )
        self.orders = pd.DataFrame(
            {
                "order_id": ["o1", "o2"],
                "customer_id": ["c1", "c2"],
                "order_status": ["delivered", "shipped"],
                "order_purchase_timestamp": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            }
        )
        self.order_items = pd.DataFrame(
            {
                "order_id": ["o1", "o1", "o2"],
                "order_item_id": [1, 2, 1],
                "product_id": ["p1", "p2", "p_quarantined"],
                "seller_id": ["s1", "s2", "s3"],
                "price": [10.0, 20.0, 100.0],
                "freight_value": [2.5, 3.5, 10.0],
            }
        )
        self.products = pd.DataFrame(
            {
                "product_id": ["p1", "p2"],  # Note: p_quarantined is absent
                "product_category_name": ["health_beauty", "toys"],
                "product_weight_g": [500, 800],
            }
        )

        self.datasets = {
            "customers": self.customers,
            "orders": self.orders,
            "order_items": self.order_items,
            "products": self.products,
        }

    def test_build_gold_dataset_from_declared_plan(self):
        gold_config = GoldConfig(
            code="order_items_gold",
            name="Olist Gold Order Items",
            base_dataset="order_items",
            enabled=True,
            plan=[
                GoldStepConfig(
                    operation=GoldOperation.JOIN,
                    right_dataset="orders",
                    left_on=["order_id"],
                    right_on=["order_id"],
                    how=JoinHow.INNER,
                ),
                GoldStepConfig(
                    operation=GoldOperation.JOIN,
                    right_dataset="customers",
                    left_on=["customer_id"],
                    right_on=["customer_id"],
                    how=JoinHow.INNER,
                ),
                GoldStepConfig(
                    operation=GoldOperation.JOIN,
                    right_dataset="products",
                    left_on=["product_id"],
                    right_on=["product_id"],
                    how=JoinHow.INNER,
                ),
                GoldStepConfig(
                    operation=GoldOperation.DERIVE,
                    derived_operation=DerivedOperation.ADD,
                    operands=["price", "freight_value"],
                    output_column="item_total",
                ),
                GoldStepConfig(
                    operation=GoldOperation.SELECT,
                    columns=[
                        "order_id",
                        "order_item_id",
                        "customer_id",
                        "customer_state",
                        "order_status",
                        "order_purchase_timestamp",
                        "product_id",
                        "product_category_name",
                        "price",
                        "freight_value",
                        "item_total",
                    ],
                ),
            ],
        )

        gold = build_gold_dataset_from_plan(gold_config, self.datasets)

        # 3 initial order_items, but 1 item references missing validated product p_quarantined
        self.assertEqual(len(gold), 2)
        self.assertEqual(list(gold["order_item_id"]), [1, 2])
        self.assertEqual(list(gold["item_total"]), [12.5, 23.5])
        self.assertEqual(
            list(gold.columns),
            [
                "order_id",
                "order_item_id",
                "customer_id",
                "customer_state",
                "order_status",
                "order_purchase_timestamp",
                "product_id",
                "product_category_name",
                "price",
                "freight_value",
                "item_total",
            ],
        )

    def test_olist_yaml_contract_plan_execution(self):
        contract_path = PROJECT_ROOT / "config" / "examples" / "olist.yaml"
        self.assertTrue(contract_path.exists())
        contract = load_contract(contract_path)

        self.assertGreater(len(contract.gold), 0)
        gold_config = contract.gold[0]
        self.assertEqual(gold_config.code, "order_items_gold")

        gold = build_gold_dataset_from_plan(gold_config, self.datasets)
        self.assertEqual(len(gold), 2)
        self.assertEqual(list(gold["item_total"]), [12.5, 23.5])

    def test_execute_gold_step_group_by_and_aggregate(self):
        df = pd.DataFrame(
            {
                "city": ["Medellin", "Medellin", "Bogota"],
                "sales": [100, 200, 150],
            }
        )
        group_step = GoldStepConfig(operation=GoldOperation.GROUP_BY, columns=["city"])
        df_after_grp, pending_grp = execute_gold_step(df, group_step, {})
        self.assertEqual(pending_grp, ["city"])

        agg_step = GoldStepConfig(
            operation=GoldOperation.AGGREGATE,
            aggregations=[
                AggregationConfig(column="sales", function=AggregationFunction.SUM, alias="city_sales")
            ],
        )
        df_final, pending_after = execute_gold_step(
            df_after_grp,
            agg_step,
            {},
            pending_group_by=pending_grp,
        )
        self.assertIsNone(pending_after)
        self.assertEqual(len(df_final), 2)
        self.assertEqual(
            df_final[df_final["city"] == "Medellin"]["city_sales"].iloc[0], 300
        )

    def test_build_gold_dataset_missing_base_dataset_raises(self):
        config = GoldConfig(
            code="test_gold",
            name="Test Gold",
            base_dataset="non_existent",
            plan=[],
        )
        with self.assertRaises(ValueError) as ctx:
            build_gold_dataset_from_plan(config, self.datasets)
        self.assertIn("non_existent", str(ctx.exception))

    def test_build_gold_dataset_missing_join_dataset_raises(self):
        config = GoldConfig(
            code="test_gold",
            name="Test Gold",
            base_dataset="order_items",
            plan=[
                GoldStepConfig(
                    operation=GoldOperation.JOIN,
                    right_dataset="ghost_dataset",
                    left_on=["order_id"],
                    right_on=["order_id"],
                )
            ],
        )
        with self.assertRaises(ValueError) as ctx:
            build_gold_dataset_from_plan(config, self.datasets)
        self.assertIn("ghost_dataset", str(ctx.exception))

    def test_parse_s3_uri(self):
        bucket, key = parse_s3_uri("s3://dataforge-gold/olist/order_items/gold_v1/order_items.parquet")
        self.assertEqual(bucket, "dataforge-gold")
        self.assertEqual(key, "olist/order_items/gold_v1/order_items.parquet")

        with self.assertRaises(ValueError):
            parse_s3_uri("http://invalid-uri/test")

        with self.assertRaises(ValueError):
            parse_s3_uri("s3://")



if __name__ == "__main__":
    unittest.main()
