import hashlib
import tempfile
import unittest
from pathlib import Path

from src.ingestion.bronze_olist import load_contract, sha256_file, validate_source_file


class BronzeIngestionTests(unittest.TestCase):
    def test_contract_contains_exact_alpha_tables(self):
        contract = load_contract()
        self.assertEqual(
            set(contract["tables"].keys()),
            {"customers", "orders", "order_items", "products"},
        )

    def test_sha256_file_matches_known_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.txt"
            path.write_bytes(b"dataforge")
            expected = hashlib.sha256(b"dataforge").hexdigest()
            self.assertEqual(sha256_file(path), expected)

    def test_validate_source_file_accepts_required_columns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.csv"
            path.write_text("id,value\n1,a\n2,b\n", encoding="utf-8")
            frame = validate_source_file(path, ["id", "value"])
            self.assertEqual(len(frame), 2)

    def test_validate_source_file_rejects_missing_columns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.csv"
            path.write_text("id\n1\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_source_file(path, ["id", "value"])

    def test_validate_source_file_rejects_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "missing.csv"
            with self.assertRaises(FileNotFoundError):
                validate_source_file(path, ["id"])


if __name__ == "__main__":
    unittest.main()
