"""Unit and integration tests for DataForge FastAPI Control Plane."""

import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.api.main import app
from src.governance.certification import CertificationTransitionError


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

    @patch("src.api.main.fetch_overview")
    @patch("src.api.main.connect_postgres")
    def test_overview_endpoint(self, connect, overview):
        overview.return_value = {
            "source": "database", "summary": {"total_datasets": 0},
            "recent_runs": [], "active_sources": [],
        }
        response = self.client.get("/api/overview")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), overview.return_value)

    @patch("src.api.main.list_sources")
    @patch("src.api.main.connect_postgres")
    def test_sources_endpoint(
        self,
        mock_connect_postgres,
        mock_list_sources,
    ):
        conn = MagicMock()
        mock_connect_postgres.return_value.__enter__.return_value = conn

        mock_list_sources.return_value = [
            {
                "source_id": 1,
                "code": "olist-csv",
                "name": "Olist CSV",
                "type": "file",
                "client_code": "olist",
                "client_name": "Olist",
                "project_code": "olist-alpha",
                "project_name": "Olist Alpha",
                "connection_reference": "env:DATA_RAW_DIR",
                "active": True,
                "status": "active",
                "created_at": "2026-10-26T00:00:00Z",
                "contract_id": 1,
                "contract_revision": 1,
                "datasets": [
                    {
                        "dataset_id": 1,
                        "code": "customers",
                        "name": "Customers",
                        "classification": "internal",
                        "owner": None,
                        "columns_count": 5,
                    }
                ],
            }
        ]

        response = self.client.get(
            "/api/sources"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.json()[0]["code"],
            "olist-csv",
        )

        mock_list_sources.assert_called_once_with(
            conn,
            client_code=None,
            project_code=None,
        )

    def test_test_connection_endpoint(self):
        payload = {
            "source_type": "file",
            "target_object": "tests/fixtures/e2e/orders.csv",
        }
        response = self.client.post("/api/sources/test-connection", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["source_type"], "file")
        self.assertGreater(data["latency_ms"], 0)

    @patch("src.api.main.list_datasets")
    @patch("src.api.main.connect_postgres")
    def test_datasets_endpoint(
        self,
        mock_connect_postgres,
        mock_list_datasets,
    ):
        conn = MagicMock()
        mock_connect_postgres.return_value.__enter__.return_value = conn

        mock_list_datasets.return_value = [
            {
                "dataset_id": 1,
                "code": "customers",
                "name": "Customers",
                "client": "olist",
                "client_name": "Olist",
                "project": "olist-alpha",
                "project_name": "Olist Alpha",
                "source_code": "olist-csv",
                "source_type": "file",
                "classification": "internal",
                "owner": None,
                "certification_status": "draft",
                "columns_count": 1,
                "primary_keys": ["customer_id"],
                "rules_count": 1,
                "transformations_count": 0,
                "gold_configured": False,
                "layers": {
                    "bronze": False,
                    "silver": False,
                    "quarantine": False,
                    "gold": False,
                },
                "schema": [
                    {
                        "name": "customer_id",
                        "type": "string",
                        "nullable": False,
                        "classification": "internal",
                        "description": None,
                    }
                ],
            }
        ]

        response = self.client.get(
            "/api/datasets"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.json()[0]["code"],
            "customers",
        )

        mock_list_datasets.assert_called_once_with(
            conn,
            client_code=None,
            project_code=None,
            source_code=None,
        )

    @patch("src.api.main.get_latest_profile")
    @patch("src.api.main.connect_postgres")
    def test_dataset_profiling_endpoint(
        self,
        mock_connect_postgres,
        mock_get_latest_profile,
    ):
        conn = MagicMock()
        mock_connect_postgres.return_value.__enter__.return_value = conn

        mock_get_latest_profile.return_value = {
            "profile_id": 1,
            "client_code": "olist",
            "project_code": "olist-alpha",
            "source_code": "olist-csv",
            "dataset_code": "customers",
            "dataset_version_id": 1,
            "version_label": "version-1",
            "run_id": 60,
            "source_asset_id": 24,
            "source_storage_uri": "s3://dataforge-bronze/customers.parquet",
            "row_count": 99441,
            "column_count": 5,
            "generated_at": None,
            "profile": {
                "dataset_name": "customers",
                "row_count": 99441,
                "column_count": 5,
                "duplicate_rows": 0,
                "duplicate_rows_percentage": 0.0,
                "candidate_keys": ["customer_id"],
                "columns": {
                    "customer_id": {
                        "name": "customer_id",
                        "inferred_type": "string",
                    }
                },
                "generated_at_utc": "2026-10-26T05:00:00+00:00",
            },
        }

        response = self.client.get(
            "/api/datasets/customers/profiling",
            params={
                "client_code": "olist",
                "project_code": "olist-alpha",
                "source_code": "olist-csv",
            },
        )

        self.assertEqual(response.status_code, 200)

        profile = response.json()

        self.assertEqual(profile["dataset_name"], "customers")
        self.assertIn("customer_id", profile["columns"])
        self.assertEqual(profile["control_plane"]["profile_id"], 1)
        self.assertEqual(profile["control_plane"]["run_id"], 60)
        self.assertEqual(profile["control_plane"]["source_asset_id"], 24)

        mock_get_latest_profile.assert_called_once_with(
            conn=conn,
            dataset_code="customers",
            client_code="olist",
            project_code="olist-alpha",
            source_code="olist-csv",
        )

    @patch("src.api.main.get_latest_profile")
    @patch("src.api.main.connect_postgres")
    def test_dataset_profiling_endpoint_returns_404_when_missing(
        self,
        mock_connect_postgres,
        mock_get_latest_profile,
    ):
        mock_get_latest_profile.return_value = None

        response = self.client.get(
            "/api/datasets/missing/profiling"
        )

        self.assertEqual(response.status_code, 404)

    @patch("src.api.main.get_latest_profile")
    @patch("src.api.main.connect_postgres")
    def test_dataset_profiling_endpoint_rejects_ambiguous_code(
        self,
        mock_connect_postgres,
        mock_get_latest_profile,
    ):
        mock_get_latest_profile.side_effect = ValueError(
            "Ambiguous dataset profiling lookup for dataset='orders'."
        )

        response = self.client.get(
            "/api/datasets/orders/profiling"
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn(
            "Ambiguous dataset profiling lookup",
            response.json()["detail"],
        )

    @patch("src.api.main.get_dataset_quarantine_context")
    @patch("src.api.main.connect_postgres")
    def test_quarantine_requires_active_contract(self, connect, context):
        context.return_value = {"asset": {"asset_id": 1}, "contract_id": None}
        response = self.client.get("/api/datasets/products/quarantine")
        self.assertEqual(response.status_code, 409)
        self.assertIn("no active configuration contract", response.json()["detail"])

    @patch("src.api.main.AirflowClient")
    @patch("src.api.main.build_conf")
    @patch("src.api.main.build_persisted_plan")
    def test_trigger_pipeline_endpoint(
        self,
        mock_build_plan,
        mock_build_conf,
        mock_airflow_class,
    ):
        plan = MagicMock()
        plan.datasets = ["products"]
        plan.gold = []
        plan.stages = [
            "bronze",
            "profiling",
            "silver",
        ]
        plan.certification = "evaluate"

        mock_build_plan.return_value = plan

        conf = {
            "contract_id": 17,
            "datasets": ["products"],
            "gold": [],
            "stages": [
                "bronze",
                "profiling",
                "silver",
            ],
            "certification": "evaluate",
        }

        mock_build_conf.return_value = conf

        airflow = mock_airflow_class.from_env.return_value
        airflow.trigger.return_value = {
            "dag_run_id": "manual__api-test",
            "state": "queued",
        }

        response = self.client.post(
            "/api/pipelines/trigger",
            json={
                "contract_id": 17,
                "datasets": ["products"],
                "stages": [
                    "bronze",
                    "profiling",
                    "silver",
                ],
            },
        )

        self.assertEqual(response.status_code, 202)

        body = response.json()

        self.assertEqual(
            body["external_run_id"],
            "manual__api-test",
        )
        self.assertEqual(body["state"], "queued")
        self.assertEqual(body["contract_id"], 17)

    @patch("src.api.main.list_assets")
    @patch("src.api.main.connect_postgres")
    def test_assets_endpoint(self, connect, assets):
        assets.return_value = []
        response = self.client.get("/api/assets")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    @patch("src.api.main.get_lineage_graph")
    @patch("src.api.main.connect_postgres")
    def test_lineage_endpoint(self, connect, graph):
        graph.return_value = {"nodes": [], "links": []}
        response = self.client.get("/api/lineage")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), graph.return_value)

    @patch("src.api.main.transition_certification",
           side_effect=CertificationTransitionError("Invalid certification transition: draft -> certified"))
    @patch("src.api.main.resolve_latest_dataset_version")
    @patch("src.api.main.connect_postgres")
    def test_certification_cannot_skip_validation(self, connect, resolve, transition):
        resolve.return_value = {"dataset_version_id": 11}
        response = self.client.post(
            "/api/certification/order_items",
            json={"status": "certified", "certified_by": "test"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("draft -> certified", response.json()["detail"])

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
