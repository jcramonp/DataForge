import unittest

import pandas as pd

from src.transformations.gold_olist import build_gold_dataset, parse_s3_uri


class GoldTransformationTests(unittest.TestCase):
    def test_parse_s3_uri(self):
        bucket, key = parse_s3_uri("s3://dataforge-gold/olist/order_items/v1/gold.parquet")
        self.assertEqual(bucket, "dataforge-gold")
        self.assertEqual(key, "olist/order_items/v1/gold.parquet")

    def test_build_gold_dataset_keeps_order_item_grain(self):
        customers = pd.DataFrame(
            {
                "customer_id": ["c1"],
                "customer_state": ["SP"],
            }
        )
        orders = pd.DataFrame(
            {
                "order_id": ["o1"],
                "customer_id": ["c1"],
                "order_status": ["delivered"],
                "order_purchase_timestamp": pd.to_datetime(["2026-01-01"]),
            }
        )
        order_items = pd.DataFrame(
            {
                "order_id": ["o1", "o1"],
                "order_item_id": [1, 2],
                "product_id": ["p1", "p2"],
                "price": [10.0, 20.0],
                "freight_value": [2.0, 3.0],
            }
        )
        products = pd.DataFrame(
            {
                "product_id": ["p1", "p2"],
                "product_category_name": ["cat_a", "cat_b"],
            }
        )

        gold = build_gold_dataset(customers, orders, order_items, products)

        self.assertEqual(len(gold), 2)
        self.assertEqual(list(gold["order_item_id"]), [1, 2])
        self.assertEqual(list(gold["item_total"]), [12.0, 23.0])

    def test_build_gold_dataset_excludes_items_with_missing_validated_product(self):
        customers = pd.DataFrame(
            {
                "customer_id": ["c1"],
                "customer_state": ["SP"],
            }
        )
        orders = pd.DataFrame(
            {
                "order_id": ["o1"],
                "customer_id": ["c1"],
                "order_status": ["delivered"],
                "order_purchase_timestamp": pd.to_datetime(["2026-01-01"]),
            }
        )
        order_items = pd.DataFrame(
            {
                "order_id": ["o1", "o1"],
                "order_item_id": [1, 2],
                "product_id": ["p1", "p_quarantined"],
                "price": [10.0, 20.0],
                "freight_value": [2.0, 3.0],
            }
        )
        products = pd.DataFrame(
            {
                "product_id": ["p1"],
                "product_category_name": ["cat_a"],
            }
        )

        gold = build_gold_dataset(customers, orders, order_items, products)

        self.assertEqual(len(gold), 1)
        self.assertEqual(gold.iloc[0]["product_id"], "p1")

    def test_gold_columns_match_alpha_contract(self):
        customers = pd.DataFrame({"customer_id": ["c1"], "customer_state": ["SP"]})
        orders = pd.DataFrame(
            {
                "order_id": ["o1"],
                "customer_id": ["c1"],
                "order_status": ["delivered"],
                "order_purchase_timestamp": pd.to_datetime(["2026-01-01"]),
            }
        )
        order_items = pd.DataFrame(
            {
                "order_id": ["o1"],
                "order_item_id": [1],
                "product_id": ["p1"],
                "price": [10.0],
                "freight_value": [2.0],
            }
        )
        products = pd.DataFrame(
            {"product_id": ["p1"], "product_category_name": ["cat_a"]}
        )

        gold = build_gold_dataset(customers, orders, order_items, products)

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


if __name__ == "__main__":
    unittest.main()
