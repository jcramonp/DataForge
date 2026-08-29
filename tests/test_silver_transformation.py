import unittest

import pandas as pd

from src.transformations.silver_olist import (
    parse_s3_uri,
    transform_customers,
    transform_order_items,
    transform_orders,
    transform_products,
)


class SilverTransformationTests(unittest.TestCase):
    def test_parse_s3_uri(self):
        bucket, key = parse_s3_uri("s3://dataforge-bronze/olist/customers/file.parquet")
        self.assertEqual(bucket, "dataforge-bronze")
        self.assertEqual(key, "olist/customers/file.parquet")

    def test_transform_customers_standardizes_text_and_preserves_rows(self):
        frame = pd.DataFrame(
            {
                "customer_id": [" a ", "b"],
                "customer_unique_id": [" u1 ", "u2"],
                "customer_zip_code_prefix": [1234, 5678],
                "customer_city": [" Sao Paulo ", "RECIFE"],
                "customer_state": ["sp", " pe "],
            }
        )
        result = transform_customers(frame)
        self.assertEqual(len(result), len(frame))
        self.assertEqual(result["customer_id"].tolist(), ["a", "b"])
        self.assertEqual(result["customer_city"].tolist(), ["sao paulo", "recife"])
        self.assertEqual(result["customer_state"].tolist(), ["SP", "PE"])
        self.assertEqual(str(result["customer_zip_code_prefix"].dtype), "Int64")

    def test_transform_orders_parses_timestamps_and_preserves_missing_values(self):
        frame = pd.DataFrame(
            {
                "order_id": [" o1 ", "o2"],
                "customer_id": [" c1 ", "c2"],
                "order_status": [" Delivered ", "CANCELED"],
                "order_purchase_timestamp": ["2017-01-01 10:00:00", "2017-01-02 11:00:00"],
                "order_approved_at": ["2017-01-01 10:05:00", None],
                "order_delivered_carrier_date": ["2017-01-02 08:00:00", None],
                "order_delivered_customer_date": ["2017-01-03 09:00:00", None],
                "order_estimated_delivery_date": ["2017-01-05 00:00:00", "2017-01-08 00:00:00"],
            }
        )
        result = transform_orders(frame)
        self.assertEqual(len(result), len(frame))
        self.assertEqual(result["order_status"].tolist(), ["delivered", "canceled"])
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(result["order_purchase_timestamp"]))
        self.assertTrue(pd.isna(result.loc[1, "order_approved_at"]))

    def test_transform_order_items_standardizes_numeric_types(self):
        frame = pd.DataFrame(
            {
                "order_id": ["o1"],
                "order_item_id": ["1"],
                "product_id": [" p1 "],
                "seller_id": [" s1 "],
                "shipping_limit_date": ["2017-01-04 12:00:00"],
                "price": ["10.50"],
                "freight_value": ["2.25"],
            }
        )
        result = transform_order_items(frame)
        self.assertEqual(len(result), 1)
        self.assertEqual(str(result["order_item_id"].dtype), "Int64")
        self.assertEqual(str(result["price"].dtype), "Float64")
        self.assertEqual(str(result["freight_value"].dtype), "Float64")
        self.assertEqual(result.loc[0, "product_id"], "p1")

    def test_transform_products_corrects_column_names_and_preserves_nulls(self):
        frame = pd.DataFrame(
            {
                "product_id": [" p1 ", "p2"],
                "product_category_name": [" HOUSE_WARES ", None],
                "product_name_lenght": [10, None],
                "product_description_lenght": [100, None],
                "product_photos_qty": [1, None],
                "product_weight_g": [500, None],
                "product_length_cm": [20, None],
                "product_height_cm": [10, None],
                "product_width_cm": [15, None],
            }
        )
        result = transform_products(frame)
        self.assertEqual(len(result), len(frame))
        self.assertIn("product_name_length", result.columns)
        self.assertIn("product_description_length", result.columns)
        self.assertNotIn("product_name_lenght", result.columns)
        self.assertNotIn("product_description_lenght", result.columns)
        self.assertEqual(result.loc[0, "product_category_name"], "house_wares")
        self.assertTrue(pd.isna(result.loc[1, "product_category_name"]))
        self.assertEqual(str(result["product_weight_g"].dtype), "Int64")


if __name__ == "__main__":
    unittest.main()
