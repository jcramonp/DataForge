"""Persisted overview regressions: scope, empty data, and unavailable services."""
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

import psycopg
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.control_plane import fetch_overview, list_orchestration_runs


class OverviewTests(unittest.TestCase):
    @patch("src.api.control_plane.list_datasets")
    @patch("src.api.control_plane.list_sources")
    def test_complete_totals_are_not_derived_from_recent_runs(self, sources, datasets):
        sources.return_value = [
            {"code": "orders", "client_code": "retail"},
            {"code": "orders", "client_code": "other"},
        ]
        datasets.return_value = [{"certification_status": "certified"}] * 3
        conn = MagicMock()
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value = (1000, Decimal(2000), 6)
        cur.fetchall.return_value = [(10, "orders", "orders", "source_to_bronze",
                                     "running", None, None, None, None, None)]
        result = fetch_overview(conn, client_code="retail", project_code="p", source_code="orders")
        self.assertEqual(result["summary"]["total_runs"], 1000)
        self.assertEqual(result["summary"]["total_rows_processed"], 2000)
        self.assertEqual(result["summary"]["certification_rate_pct"], 100.0)
        self.assertIsNone(result["recent_runs"][0]["input_rows"])
        for call in cur.execute.call_args_list:
            self.assertEqual(call.args[1], ("retail", "retail", "p", "p", "orders", "orders"))
        self.assertIn("source_to_bronze", cur.execute.call_args_list[0].args[0])
        self.assertIn("silver_quality_gate", cur.execute.call_args_list[0].args[0])

    @patch("src.api.control_plane.list_datasets", return_value=[])
    @patch("src.api.control_plane.list_sources", return_value=[])
    def test_empty_database_preserves_zero_metrics(self, sources, datasets):
        conn = MagicMock()
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value = (0, 0, 0)
        cur.fetchall.return_value = []
        result = fetch_overview(conn)
        self.assertTrue(all(value == 0 for value in result["summary"].values()))
        self.assertEqual(result["recent_runs"], [])
        self.assertEqual(result["source"], "database")

    @patch("src.api.main.fetch_overview")
    @patch("src.api.main.connect_postgres")
    def test_endpoint_forwards_complete_scope(self, connect, overview):
        overview.return_value = {"summary": {}, "recent_runs": [], "active_sources": []}
        scope = {"client_code": "c", "project_code": "p", "source_code": "s"}
        response = TestClient(app).get("/api/overview", params=scope)
        self.assertEqual(response.status_code, 200)
        overview.assert_called_once_with(connect.return_value.__enter__.return_value, **scope)

    @patch("src.api.main.connect_postgres", side_effect=psycopg.OperationalError("secret"))
    def test_unavailable_database_never_serves_demo_success(self, connect):
        response = TestClient(app).get("/api/overview")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret", response.text)

    def test_run_scope_is_applied_before_history_limit(self):
        conn = MagicMock()
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchall.return_value = []
        list_orchestration_runs(conn, client_code="c", project_code="p", source_code="s", limit=10)
        query, params = cur.execute.call_args.args
        self.assertIn("{resolved,source_code}", query)
        self.assertLess(query.index("WHERE"), query.index("LIMIT"))
        self.assertEqual(params, ("c", "c", "p", "p", "s", "s", 10))

    @patch("src.api.main.build_persisted_plan", side_effect=psycopg.OperationalError("secret"))
    def test_trigger_database_failure_is_safe(self, plan):
        response = TestClient(app).post("/api/pipelines/trigger", json={"contract_id": 1})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret", response.text)
