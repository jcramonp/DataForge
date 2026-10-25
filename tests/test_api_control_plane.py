"""Unit and integration tests for DataForge FastAPI Control Plane."""

import unittest
from fastapi.testclient import TestClient

from src.api.main import app


class ControlPlaneApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_endpoint(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("version", data)

    def test_overview_endpoint(self):
        response = self.client.get("/api/overview")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("summary", data)
        self.assertIn("total_datasets", data["summary"])
        self.assertIn("recent_runs", data)

    def test_sources_endpoint(self):
        response = self.client.get("/api/sources")
        self.assertEqual(response.status_code, 200)
        sources = response.json()
        self.assertGreaterEqual(len(sources), 1)
        self.assertEqual(sources[0]["code"], "olist-csv")

    def test_test_connection_endpoint(self):
        payload = {
            "source_type": "file",
            "connection_reference": "env:DATA_RAW_DIR",
            "target_object": "data/raw/olist/*.csv",
        }
        response = self.client.post("/api/sources/test-connection", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["source_type"], "file")
        self.assertGreater(data["latency_ms"], 0)

    def test_datasets_endpoint(self):
        response = self.client.get("/api/datasets")
        self.assertEqual(response.status_code, 200)
        datasets = response.json()
        self.assertGreaterEqual(len(datasets), 1)
        codes = [d["code"] for d in datasets]
        self.assertIn("customers", codes)

    def test_dataset_profiling_endpoint(self):
        response = self.client.get("/api/datasets/customers/profiling")
        self.assertEqual(response.status_code, 200)
        profile = response.json()
        self.assertEqual(profile["dataset_name"], "customers")
        self.assertIn("columns", profile)
        self.assertIn("customer_id", profile["columns"])

    def test_quarantine_endpoint(self):
        response = self.client.get("/api/datasets/products/quarantine")
        self.assertEqual(response.status_code, 200)
        records = response.json()
        self.assertGreater(len(records), 0)
        self.assertEqual(records[0]["severity"], "critical")
        self.assertEqual(records[0]["failed_field"], "product_weight_g")

    def test_trigger_pipeline_endpoint(self):
        response = self.client.post("/api/pipelines/trigger", json={"dataset": "products"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("run", data)
        self.assertEqual(data["run"]["dataset"], "products")
        self.assertEqual(data["run"]["status"], "success")

    def test_assets_endpoint(self):
        response = self.client.get("/api/assets")
        self.assertEqual(response.status_code, 200)
        assets = response.json()
        layers = {a["layer"] for a in assets}
        self.assertIn("bronze", layers)
        self.assertIn("silver", layers)
        self.assertIn("quarantine", layers)
        self.assertIn("gold", layers)

    def test_lineage_endpoint(self):
        response = self.client.get("/api/lineage")
        self.assertEqual(response.status_code, 200)
        lineage = response.json()
        self.assertIn("nodes", lineage)
        self.assertIn("links", lineage)

    def test_certification_endpoints(self):
        # GET certification
        response = self.client.get("/api/certification")
        self.assertEqual(response.status_code, 200)
        cert_list = response.json()
        self.assertGreater(len(cert_list), 0)

        # UPDATE certification
        update_payload = {"status": "certified", "certified_by": "gabriela611"}
        res_post = self.client.post("/api/certification/order_items", json=update_payload)
        self.assertEqual(res_post.status_code, 200)
        self.assertEqual(res_post.json()["new_status"], "certified")

    def test_copilot_suggest_endpoint(self):
        payload = {
            "dataset_code": "products",
            "requirement": "El peso debe ser mayor a cero y no puede ser nulo",
            "context_columns": ["product_weight_g"],
        }
        response = self.client.post("/api/copilot/suggest", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(len(data["proposed_rules"]), 0)
        self.assertTrue(data["is_valid_contract"])


if __name__ == "__main__":
    unittest.main()
