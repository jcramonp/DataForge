import json
import tempfile
import unittest
from pathlib import Path

from src.contracts import export_json_schema, load_contract


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ContractLoaderTests(unittest.TestCase):

    def test_loads_postgres_example(self):
        contract = load_contract(
            PROJECT_ROOT
            / "config"
            / "examples"
            / "postgres_sales.yaml"
        )

        self.assertEqual(contract.client.code, "demo-retail")
        self.assertEqual(contract.source.type.value, "postgresql")
        self.assertEqual(contract.datasets[0].code, "sales")
        self.assertEqual(contract.gold[0].code, "sales_gold")

    def test_loads_olist_example(self):
        contract = load_contract(
            PROJECT_ROOT
            / "config"
            / "examples"
            / "olist.yaml"
        )

        self.assertEqual(contract.client.code, "olist")
        self.assertEqual(len(contract.datasets), 4)

        self.assertEqual(
            [dataset.code for dataset in contract.datasets],
            [
                "customers",
                "orders",
                "order_items",
                "products",
            ],
        )

        self.assertEqual(
            contract.gold[0].code,
            "order_items_gold",
        )

    def test_unsupported_extension_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "contract.txt"
            path.write_text(
                "invalid",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                load_contract(path)

    def test_json_schema_can_be_exported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "schema.json"

            result = export_json_schema(target)

            self.assertTrue(result.exists())

            schema = json.loads(
                result.read_text(encoding="utf-8")
            )

            self.assertIn("$defs", schema)
            self.assertIn("properties", schema)


if __name__ == "__main__":
    unittest.main()