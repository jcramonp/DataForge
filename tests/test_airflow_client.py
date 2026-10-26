"""Unit tests for the Airflow REST client used to trigger dataforge_pipeline (#24)."""

import unittest
from unittest.mock import MagicMock, patch

from src.orchestration.airflow_client import DAG_ID, AirflowClient, AirflowClientError, build_conf
from src.orchestration.plan import STAGES


def _response(status: int, payload: dict | None = None) -> MagicMock:
    response = MagicMock(status_code=status, text=str(payload))
    response.json.return_value = payload or {}
    return response


class AirflowClientTests(unittest.TestCase):
    def setUp(self):
        self.client = AirflowClient("http://airflow:8080", "admin", "secret")
        self.session = MagicMock()
        self.client._session = self.session

    def test_trigger_authenticates_and_posts_run_conf(self):
        self.session.post.return_value = _response(201, {"access_token": "jwt"})
        self.session.request.return_value = _response(200, {"dag_run_id": "manual__1", "state": "queued"})

        conf = build_conf("config/examples/olist.yaml", datasets=["orders"])
        run = self.client.trigger(conf)

        self.assertEqual(run["dag_run_id"], "manual__1")
        self.session.post.assert_called_once_with(
            "http://airflow:8080/auth/token", json={"username": "admin", "password": "secret"}, timeout=30.0
        )
        method, url = self.session.request.call_args.args
        self.assertEqual((method, url), ("POST", f"http://airflow:8080/api/v2/dags/{DAG_ID}/dagRuns"))
        self.assertEqual(self.session.request.call_args.kwargs["json"], {"logical_date": None, "conf": conf})
        self.assertEqual(self.session.request.call_args.kwargs["headers"], {"Authorization": "Bearer jwt"})

    def test_expired_token_is_renewed_once(self):
        self.session.post.side_effect = [_response(201, {"access_token": "old"}), _response(201, {"access_token": "new"})]
        self.session.request.side_effect = [_response(401), _response(200, {"state": "running"})]
        self.assertEqual(self.client.get_run("manual__1")["state"], "running")
        self.assertEqual(self.session.post.call_count, 2)

    def test_errors_are_raised_with_context(self):
        self.session.post.return_value = _response(201, {"access_token": "jwt"})
        self.session.request.return_value = _response(400, {"detail": "bad conf"})
        with self.assertRaises(AirflowClientError) as ctx:
            self.client.trigger({})
        self.assertIn("400", str(ctx.exception))

    def test_bad_credentials(self):
        self.session.post.return_value = _response(401, {"detail": "invalid"})
        with self.assertRaises(AirflowClientError):
            self.client.get_run("x")

    @patch("src.orchestration.airflow_client.time.sleep")
    def test_wait_polls_until_terminal_state(self, _):
        self.session.post.return_value = _response(201, {"access_token": "jwt"})
        self.session.request.side_effect = [
            _response(200, {"state": "queued"}),
            _response(200, {"state": "running"}),
            _response(200, {"state": "success"}),
        ]
        self.assertEqual(self.client.wait("manual__1")["state"], "success")

    def test_default_conf_runs_every_stage(self):
        conf = build_conf("c.yaml")
        self.assertEqual(conf, {"contract": "c.yaml", "datasets": [], "gold": [], "stages": list(STAGES), "certification": "evaluate"})

    def test_persisted_contract_conf(self):
        conf = build_conf(
            contract_id=17,
            datasets=["orders"],
        )

        self.assertEqual(
            conf,
            {
                "contract_id": 17,
                "datasets": ["orders"],
                "gold": [],
                "stages": list(STAGES),
                "certification": "evaluate",
            },
        )

    def test_conf_requires_exactly_one_contract_reference(self):
        with self.assertRaises(ValueError):
            build_conf()

        with self.assertRaises(ValueError):
            build_conf(
                "contract.yaml",
                contract_id=17,
            )

        with self.assertRaises(ValueError):
            build_conf(contract_id=0)

    @patch.dict("os.environ", {"AIRFLOW_ADMIN_PASSWORD": "", "DATAFORGE_ENV_FILE": "/nonexistent"}, clear=False)
    def test_from_env_requires_a_password(self):
        with self.assertRaises(AirflowClientError):
            AirflowClient.from_env()


if __name__ == "__main__":
    unittest.main()
