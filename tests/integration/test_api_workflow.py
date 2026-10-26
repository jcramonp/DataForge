"""Issue #25 acceptance against real PostgreSQL/MinIO and persisted contracts.

Airflow HTTP transport is tested separately; this executes the same generic
plan/stages locally so no external Airflow worker can point at another DB.
"""
import unittest
from fastapi.testclient import TestClient

from src.api.main import app
from src.common.clients import connect_postgres
from src.contracts.loader import load_contract
from src.ops.migrate import run_migrations
from src.orchestration.pipeline import run_pipeline
from src.orchestration.plan import build_persisted_plan
from tests.integration import integration_settings, requires_integration, reset_database, reset_buckets


@requires_integration
class ApiWorkflowIntegrationTests(unittest.TestCase):
    def test_persisted_contract_full_workflow_and_scope_isolation(self):
        settings = integration_settings()
        reset_database(settings)
        reset_buckets(settings, "ci-retail/")
        with connect_postgres(settings, autocommit=True) as conn:
            run_migrations(conn)
        api = TestClient(app)
        payload = load_contract("tests/fixtures/e2e/retail_contract.yaml").model_dump(mode="json", by_alias=True)
        registered = api.post("/api/onboarding/contracts", json=payload)
        self.assertEqual(registered.status_code, 201, registered.text)
        contract_id = registered.json()["contract_id"]
        repeated = api.post("/api/onboarding/contracts", json=payload)
        self.assertEqual(repeated.status_code, 200, repeated.text)
        self.assertEqual(repeated.json()["contract_id"], contract_id)
        scope = {"client_code":"ci-retail", "project_code":"ci-retail-e2e", "source_code":"ci-retail-csv"}
        plan = build_persisted_plan(contract_id)
        outcome = run_pipeline(plan, external_run_id="issue25__persisted_api")
        self.assertEqual(outcome["status"], "success", outcome)

        def get(path, **extra):
            response = api.get(path, params={**scope, **extra})
            self.assertEqual(response.status_code, 200, response.text)
            return response.json()

        datasets = get("/api/datasets")
        self.assertEqual({d["code"] for d in datasets}, {"orders", "orders_by_status"})
        profile = get("/api/datasets/orders/profiling")
        self.assertEqual(profile["row_count"], 7)
        self.assertEqual(profile["control_plane"]["client_code"], "ci-retail")
        rules = get("/api/datasets/orders/quality-rules")
        self.assertTrue(any(rule["status"] == "fail" for rule in rules))
        quarantine = get("/api/datasets/orders/quarantine")
        self.assertTrue(quarantine)
        self.assertTrue(all(row["severity"] == "critical" for row in quarantine))
        assets = get("/api/assets")
        self.assertEqual({a["layer"] for a in assets}, {"bronze", "silver", "quarantine", "gold"})
        graph = get("/api/lineage")
        by_layer = {a["layer"]: a["asset_id"] for a in assets}
        nodes = {node["id"]: node["asset_id"] for node in graph["nodes"]}
        edges = {(nodes[link["source"]], nodes[link["target"]], link["relation_type"])
                 for link in graph["links"]}
        self.assertIn((by_layer["bronze"], by_layer["silver"], "validated_from"), edges)
        self.assertIn((by_layer["bronze"], by_layer["quarantine"], "quarantined_from"), edges)
        self.assertIn((by_layer["silver"], by_layer["gold"], "derived_from"), edges)
        summary = get("/api/overview")["summary"]
        self.assertEqual(summary["total_rows_processed"], 7)
        self.assertEqual(summary["total_quarantined_rows"], 3)
        self.assertEqual(summary["total_sources"], 1)
        self.assertEqual(get("/api/runs")[0]["status"], "success")
        for state in ("validated", "certified"):
            response = api.post("/api/certification/orders", params=scope,
                                json={"status":state,"certified_by":"issue25-test"})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["new_status"], state)
        self.assertEqual(get("/api/overview")["summary"]["certified_datasets"], 1)

        # Equal dataset/source codes in another tenant must never read Retail's profile or assets.
        payload["client"] = {"code":"other-retail", "name":"Other Retail"}
        payload["project"] = {"code":"other-retail-project", "name":"Other Project"}
        payload["gold"] = []
        response = api.post("/api/onboarding/contracts", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        other = {**scope, "client_code":"other-retail", "project_code":"other-retail-project"}
        self.assertEqual(api.get("/api/assets", params=other).json(), [])
        self.assertEqual(api.get("/api/runs", params=other).json(), [])
        self.assertEqual(api.get("/api/datasets/orders/profiling", params=other).status_code, 404)
        self.assertEqual(api.get("/api/overview", params=other).json()["summary"]["total_rows_processed"], 0)
