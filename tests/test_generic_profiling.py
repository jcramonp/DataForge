"""Unit tests for the generic schema discovery and profiling engine."""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.contracts.models import ColumnConfig, DataType
from src.discovery import (
    generate_contract_schema,
    infer_data_type,
    profile_column,
    profile_contract,
    profile_dataframe,
    save_profile_reports,
    to_json,
    to_markdown,
)


class GenericProfilingTests(unittest.TestCase):
    def test_infer_data_type_integers(self):
        # Native integer
        s_int = pd.Series([1, 2, 3, 4])
        self.assertEqual(infer_data_type(s_int), DataType.INTEGER)

        # Float representing whole numbers (e.g. integer column with NaN)
        s_float_int = pd.Series([1.0, 2.0, None, 4.0])
        self.assertEqual(infer_data_type(s_float_int), DataType.INTEGER)

        # String integers
        s_str_int = pd.Series(["10", "20", "300"])
        self.assertEqual(infer_data_type(s_str_int), DataType.INTEGER)

    def test_infer_data_type_floats(self):
        s_float = pd.Series([1.5, 2.7, 3.14])
        self.assertEqual(infer_data_type(s_float), DataType.FLOAT)

        s_str_float = pd.Series(["1.5", "2.75", "100.99"])
        self.assertEqual(infer_data_type(s_str_float), DataType.FLOAT)

    def test_infer_data_type_booleans(self):
        s_bool = pd.Series([True, False, True])
        self.assertEqual(infer_data_type(s_bool), DataType.BOOLEAN)

        s_str_bool = pd.Series(["true", "False", "TRUE", None])
        self.assertEqual(infer_data_type(s_str_bool), DataType.BOOLEAN)

    def test_infer_data_type_dates_and_datetimes(self):
        # Date strings YYYY-MM-DD
        s_date = pd.Series(["2026-01-01", "2026-05-15", None])
        self.assertEqual(infer_data_type(s_date), DataType.DATE)

        # Datetime strings ISO
        s_datetime = pd.Series(["2026-01-01 10:30:00", "2026-05-15T14:22:10Z"])
        self.assertEqual(infer_data_type(s_datetime), DataType.DATETIME)

        # Native timestamp
        s_ts = pd.Series([datetime(2026, 1, 1, 10, 30), datetime(2026, 1, 2, 12, 0)])
        self.assertEqual(infer_data_type(s_ts), DataType.DATETIME)

    def test_infer_data_type_json(self):
        s_json = pd.Series(['{"user_id": 123, "active": true}', '{"items": [1, 2]}'])
        self.assertEqual(infer_data_type(s_json), DataType.JSON)

    def test_infer_data_type_string_and_empty(self):
        s_str = pd.Series(["Medellin", "Bogota", "Cali"])
        self.assertEqual(infer_data_type(s_str), DataType.STRING)

        s_empty = pd.Series([None, None])
        self.assertEqual(infer_data_type(s_empty), DataType.STRING)

    def test_profile_column_numeric_statistics(self):
        series = pd.Series([-10, 0, 10, 20, None], name="score")
        profile = profile_column(series)

        self.assertEqual(profile["name"], "score")
        self.assertEqual(profile["inferred_type"], "integer")
        self.assertEqual(profile["total_count"], 5)
        self.assertEqual(profile["null_count"], 1)
        self.assertEqual(profile["null_percentage"], 20.0)
        self.assertEqual(profile["distinct_count"], 4)
        self.assertEqual(profile["stats"]["min"], -10)
        self.assertEqual(profile["stats"]["max"], 20)
        self.assertEqual(profile["stats"]["mean"], 5.0)
        self.assertEqual(profile["stats"]["median"], 5)
        self.assertEqual(profile["stats"]["zeros_count"], 1)
        self.assertEqual(profile["stats"]["negative_count"], 1)

    def test_profile_column_string_statistics(self):
        series = pd.Series(["apple", "banana", "", "date", None], name="fruits")
        profile = profile_column(series)

        self.assertEqual(profile["name"], "fruits")
        self.assertEqual(profile["inferred_type"], "string")
        self.assertEqual(profile["null_count"], 1)
        self.assertEqual(profile["stats"]["min_length"], 0)
        self.assertEqual(profile["stats"]["max_length"], 6)
        self.assertEqual(profile["stats"]["empty_string_count"], 1)

    def test_profile_dataframe_and_candidate_keys(self):
        data = {
            "order_id": ["o1", "o2", "o3", "o4"],
            "customer_id": ["c1", "c1", "c2", "c3"],
            "amount": [100.5, 200.0, None, 450.25],
            "city": ["Medellin", "Bogota", "Medellin", "Cali"],
        }
        df = pd.DataFrame(data)
        # Duplicate row
        df_with_dup = pd.concat([df, df.iloc[[0]]], ignore_index=True)

        profile = profile_dataframe(df_with_dup, dataset_name="orders")

        self.assertEqual(profile["dataset_name"], "orders")
        self.assertEqual(profile["row_count"], 5)
        self.assertEqual(profile["column_count"], 4)
        self.assertEqual(profile["duplicate_rows"], 1)
        self.assertEqual(profile["duplicate_rows_percentage"], 20.0)
        self.assertIn("columns", profile)
        self.assertIn("order_id", profile["columns"])

        # In df without duplicate, order_id has 4 unique values and 0 nulls out of 4 rows -> candidate key
        clean_profile = profile_dataframe(df, dataset_name="orders")
        self.assertEqual(clean_profile["candidate_keys"], ["order_id"])

    def test_generate_contract_schema(self):
        df = pd.DataFrame({
            "id": [1, 2, 3],
            "name": ["Alpha", "Beta", None],
            "price": [19.99, 25.50, 99.0],
            "created_at": ["2026-01-01", "2026-01-02", "2026-01-03"],
        })
        schema_dict = generate_contract_schema(df)

        self.assertEqual(len(schema_dict), 4)
        self.assertEqual(schema_dict[0]["name"], "id")
        self.assertEqual(schema_dict[0]["type"], "integer")
        self.assertFalse(schema_dict[0]["nullable"])

        self.assertEqual(schema_dict[1]["name"], "name")
        self.assertTrue(schema_dict[1]["nullable"])

        # Validate that each item conforms to Pydantic ColumnConfig
        validated_columns = [ColumnConfig(**field) for field in schema_dict]
        self.assertEqual(len(validated_columns), 4)
        self.assertEqual(validated_columns[0].type, DataType.INTEGER)
        self.assertEqual(validated_columns[2].type, DataType.FLOAT)

    def test_reporter_markdown_and_json(self):
        df = pd.DataFrame({
            "user_id": ["u1", "u2", "u3"],
            "score": [10, 20, 30],
        })
        profile = profile_dataframe(df, dataset_name="users_test")

        # Test JSON serialization
        json_str = to_json(profile)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["dataset_name"], "users_test")
        self.assertEqual(parsed["row_count"], 3)

        # Test Markdown formatting
        md = to_markdown(profile)
        self.assertIn("# DataForge Discovery & Profiling Report: users_test", md)
        self.assertIn("`user_id`", md)
        self.assertIn("`score`", md)
        self.assertIn("Candidate Keys (Zero nulls & 100% unique)", md)

        # Test report file saving
        with tempfile.TemporaryDirectory() as temp_dir:
            json_file, md_file = save_profile_reports(profile, temp_dir, "test_report")
            self.assertTrue(Path(json_file).exists())
            self.assertTrue(Path(md_file).exists())
            self.assertGreater(Path(json_file).stat().st_size, 0)
            self.assertGreater(Path(md_file).stat().st_size, 0)

    def test_profile_contract_integration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_file = root / "sample.csv"
            data_file.write_text(
                "item_id,price,category\n1,19.99,tech\n2,29.99,home\n",
                encoding="utf-8",
            )
            contract_file = root / "contract.yaml"
            contract_file.write_text(
                f"""
contract_version: "1.0"
client:
  code: test_client
  name: Test Client
project:
  code: test_project
  name: Test Project
source:
  code: local_files
  name: Local Files
  type: file
datasets:
  - code: sample_items
    name: Sample Items
    source_object:
      path: {data_file.as_posix()}
      format: csv
    schema:
      - name: item_id
        type: integer
      - name: price
        type: float
      - name: category
        type: string
""",
                encoding="utf-8",
            )

            reports_dir = root / "reports"
            results = profile_contract(contract_file, output_dir=reports_dir)

            self.assertIn("sample_items", results)
            profile = results["sample_items"]
            self.assertEqual(profile["row_count"], 2)
            self.assertEqual(profile["column_count"], 3)
            self.assertEqual(profile["columns"]["item_id"]["inferred_type"], "integer")
            self.assertEqual(profile["columns"]["price"]["inferred_type"], "float")
            self.assertEqual(profile["columns"]["category"]["inferred_type"], "string")

            # Verify saved reports
            self.assertTrue((reports_dir / "sample_items.json").exists())
            self.assertTrue((reports_dir / "sample_items.md").exists())


if __name__ == "__main__":
    unittest.main()
