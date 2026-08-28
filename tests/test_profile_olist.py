import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.discovery.profile_olist import profile_dataset, to_markdown


class OlistProfilerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.raw_dir = self.root / "raw"
        self.raw_dir.mkdir()
        self.contract_path = self.root / "contract.json"
        self.contract_path.write_text(
            json.dumps(
                {
                    "dataset": "test",
                    "source_url": "https://example.test",
                    "raw_directory": str(self.raw_dir),
                    "tables": {
                        "customers": {
                            "file": "customers.csv",
                            "primary_key": ["customer_id"],
                            "required_columns": ["customer_id", "city"],
                            "potential_pii": ["customer_id"],
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_rows(self, rows):
        with (self.raw_dir / "customers.csv").open(
            "w", encoding="utf-8", newline=""
        ) as target:
            writer = csv.DictWriter(target, fieldnames=["customer_id", "city"])
            writer.writeheader()
            writer.writerows(rows)

    def test_profiles_missing_duplicates_and_primary_keys(self):
        self.write_rows(
            [
                {"customer_id": "c1", "city": "Medellin"},
                {"customer_id": "c1", "city": "Medellin"},
                {"customer_id": "", "city": ""},
            ]
        )

        result = profile_dataset(self.contract_path)
        customers = result["tables"]["customers"]

        self.assertEqual(customers["row_count"], 3)
        self.assertEqual(customers["duplicate_rows"], 1)
        self.assertEqual(customers["duplicate_primary_keys"], 1)
        self.assertEqual(customers["null_primary_keys"], 1)
        self.assertEqual(customers["missing_values"]["city"]["count"], 1)
        self.assertIn("| customers | 3 | 2 | 1 | 1 | 1 | profiled |", to_markdown(result))

    def test_reports_a_missing_source_file(self):
        result = profile_dataset(self.contract_path)
        self.assertFalse(result["tables"]["customers"]["exists"])


if __name__ == "__main__":
    unittest.main()
