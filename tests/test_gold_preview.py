"""Consumption checks using real Parquet bytes and mocked external clients."""
import hashlib
import io
import unittest
from unittest.mock import MagicMock, patch

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient

from src.api.gold_preview import GoldPreviewError, read_gold_preview, MAX_OBJECT_BYTES
from src.api.main import app


class GoldPreviewTests(unittest.TestCase):
    def setUp(self):
        buffer = io.BytesIO()
        pq.write_table(pa.table({"userId": list(range(1, 9)), "total_tareas": [20] * 8}), buffer)
        self.data = buffer.getvalue()
        self.asset = dict(asset_id=8, asset_name="Tasks by user", layer="gold", format="parquet",
                          storage_uri="s3://gold/demo/tasks.parquet", checksum=hashlib.sha256(self.data).hexdigest())
        self.s3 = MagicMock()
        self.body = io.BytesIO(self.data)
        self.s3.get_object.return_value = {"Body": self.body, "ContentLength": len(self.data)}

    def test_real_gold_content_and_limit(self):
        result = read_gold_preview(self.asset, self.s3, "gold", 3)
        self.assertEqual(result["rows"], [{"userId": n, "total_tareas": 20} for n in range(1, 4)])
        self.assertEqual(result["total_rows"], 8)
        self.assertTrue(result["truncated"])
        self.assertTrue(self.body.closed)

    def test_rejects_untrusted_uri_or_non_gold_before_storage(self):
        for changes in ({"layer": "bronze"}, {"storage_uri": "s3://other/tasks.parquet"},
                        {"storage_uri": "https://example.com/tasks.parquet"}):
            with self.subTest(changes=changes), self.assertRaises(GoldPreviewError):
                read_gold_preview(self.asset | changes, self.s3, "gold", 100)
        self.s3.get_object.assert_not_called()

    def test_rejects_oversize_and_closes_body(self):
        self.s3.get_object.return_value["ContentLength"] = MAX_OBJECT_BYTES + 1
        with self.assertRaisesRegex(GoldPreviewError, "10 MiB"):
            read_gold_preview(self.asset, self.s3, "gold", 100)
        self.assertTrue(self.body.closed)

    def test_rejects_overwritten_or_unverified_asset(self):
        with self.assertRaisesRegex(GoldPreviewError, "checksum"):
            read_gold_preview(self.asset | {"checksum": "bad"}, self.s3, "gold", 100)
        self.assertTrue(self.body.closed)

    def test_empty_parquet_keeps_columns(self):
        buffer = io.BytesIO()
        pq.write_table(pa.table({"userId": pa.array([], type=pa.int64())}), buffer)
        data = buffer.getvalue()
        self.s3.get_object.return_value = {"Body": io.BytesIO(data)}
        result = read_gold_preview(self.asset | {"checksum": hashlib.sha256(data).hexdigest()}, self.s3, "gold", 100)
        self.assertEqual(result["columns"], ["userId"])
        self.assertEqual(result["rows"], [])
        self.assertFalse(result["truncated"])

    @patch("src.api.main.connect_postgres")
    @patch("src.api.main.lookup_asset")
    @patch("src.api.main.create_s3_client")
    @patch("src.api.main.get_settings")
    def test_endpoint_returns_real_content_and_safe_errors(self, settings, s3, lookup, connect):
        client = TestClient(app)
        settings.return_value.storage.bucket.return_value = "gold"
        s3.return_value = self.s3
        lookup.return_value = self.asset
        response = client.get("/api/assets/8/gold-preview")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(sum(row["total_tareas"] for row in response.json()["rows"]), 160)
        lookup.return_value = None
        self.assertEqual(client.get("/api/assets/9/gold-preview").status_code, 404)
        lookup.return_value = self.asset | {"layer": "silver"}
        self.assertEqual(client.get("/api/assets/6/gold-preview").status_code, 422)
        lookup.return_value = self.asset
        s3.side_effect = RuntimeError("sensitive upstream value")
        response = client.get("/api/assets/8/gold-preview")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("sensitive", response.text)

    @patch("src.api.main.connect_postgres")
    def test_endpoint_rejects_unbounded_requests_before_database(self, connect):
        client = TestClient(app)
        for path in ("/api/assets/0/gold-preview", "/api/assets/8/gold-preview?limit=101",
                     "/api/assets/8/gold-preview?limit=0"):
            self.assertEqual(client.get(path).status_code, 422)
        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
