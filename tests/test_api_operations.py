"""API health, readiness, request tracing and operational summary (#32)."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.common.settings import get_settings
from src.ops.health import CheckResult
from tests.test_common_settings import AWS_ENV, LOCAL_ENV


def _checks(*failing: str) -> list[CheckResult]:
    names = ["configuration", "postgres", "object_storage", "contracts"]
    return [CheckResult(name, name not in failing, "detail", 1.0) for name in names]


class ApiOperationsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_reports_environment(self):
        with patch("src.api.main.get_settings", return_value=get_settings(LOCAL_ENV)):
            data = self.client.get("/api/health").json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["environment"], "local")

    @patch("src.api.main.run_readiness_checks", return_value=_checks())
    def test_ready_returns_200_when_all_checks_pass(self, _):
        response = self.client.get("/api/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ready")
        self.assertEqual(len(response.json()["checks"]), 4)

    @patch("src.api.main.run_readiness_checks", return_value=_checks("postgres"))
    def test_ready_returns_503_when_a_dependency_fails(self, _):
        response = self.client.get("/api/ready")
        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertEqual(body["status"], "not_ready")
        failed = [c["name"] for c in body["checks"] if not c["ok"]]
        self.assertEqual(failed, ["postgres"])

    def test_request_id_is_propagated_or_generated(self):
        echoed = self.client.get("/api/health", headers={"X-Request-ID": "trace-123"})
        self.assertEqual(echoed.headers["X-Request-ID"], "trace-123")
        generated = self.client.get("/api/health")
        self.assertEqual(len(generated.headers["X-Request-ID"]), 32)

    def test_ops_summary_from_database(self):
        summary = {"totals": {"total_runs": 1}, "by_stage": [], "recent_failures": [], "datasets": []}
        with (
            patch("src.api.main.connect_postgres"),
            patch("src.api.main.fetch_run_summary", return_value=summary),
        ):
            data = self.client.get("/api/ops/summary").json()
        self.assertEqual(data["source"], "database")
        self.assertEqual(data["totals"]["total_runs"], 1)

    def test_ops_summary_fails_loudly_locally(self):
        with (
            patch("src.api.main.get_settings", return_value=get_settings(LOCAL_ENV)),
            patch("src.api.main.connect_postgres", side_effect=OSError("secret-offline")),
        ):
            response = self.client.get("/api/ops/summary")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Control-plane database unavailable")

    def test_ops_summary_fails_loudly_outside_local(self):
        with (
            patch("src.api.main.get_settings", return_value=get_settings(AWS_ENV)),
            patch("src.api.main.connect_postgres", side_effect=OSError("offline")),
        ):
            response = self.client.get("/api/ops/summary")
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
