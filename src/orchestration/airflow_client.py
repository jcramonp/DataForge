"""Trigger and monitor ``dataforge_pipeline`` runs through the Airflow 3 REST API.

Used from the command line and intended for the control-plane API (#25)::

    python -m src.orchestration.airflow_client --contract config/examples/olist.yaml --wait
    python -m src.orchestration.airflow_client --contract tests/fixtures/e2e/retail_contract.yaml \\
        --stages bronze,profiling,silver --datasets orders --wait

Configuration (environment / ``.env``): ``AIRFLOW_API_URL`` (default
``http://localhost:8080``), ``AIRFLOW_ADMIN_USERNAME`` and
``AIRFLOW_ADMIN_PASSWORD``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any

import requests

from src.common.settings import load_environment_file
from src.orchestration.plan import CERTIFICATION_MODES, STAGES


DAG_ID = "dataforge_pipeline"
TERMINAL_STATES = {"success", "failed"}


class AirflowClientError(RuntimeError):
    pass


@dataclass
class AirflowClient:
    base_url: str
    username: str
    password: str
    timeout: float = 30.0

    @classmethod
    def from_env(cls) -> "AirflowClient":
        load_environment_file()
        password = os.environ.get("AIRFLOW_ADMIN_PASSWORD")
        if not password:
            raise AirflowClientError("AIRFLOW_ADMIN_PASSWORD is not set")
        return cls(
            base_url=os.environ.get("AIRFLOW_API_URL", "http://localhost:8080").rstrip("/"),
            username=os.environ.get("AIRFLOW_ADMIN_USERNAME", "admin"),
            password=password,
        )

    def __post_init__(self) -> None:
        self._session = requests.Session()
        self._token: str | None = None

    def _authenticate(self) -> None:
        response = self._session.post(
            f"{self.base_url}/auth/token",
            json={"username": self.username, "password": self.password},
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise AirflowClientError(
                f"Airflow authentication failed ({response.status_code}): {response.text[:300]}"
            )
        self._token = response.json()["access_token"]

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        if self._token is None:
            self._authenticate()
        for attempt in (1, 2):
            response = self._session.request(
                method,
                f"{self.base_url}/api/v2{path}",
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=self.timeout,
                **kwargs,
            )
            if response.status_code == 401 and attempt == 1:
                self._authenticate()  # token expired
                continue
            if response.status_code >= 400:
                raise AirflowClientError(
                    f"Airflow API {method} {path} failed ({response.status_code}): {response.text[:500]}"
                )
            return response.json()
        raise AirflowClientError("unreachable")

    def trigger(self, conf: dict[str, Any], dag_run_id: str | None = None, note: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"logical_date": None, "conf": conf}
        if dag_run_id:
            body["dag_run_id"] = dag_run_id
        if note:
            body["note"] = note
        return self._request("POST", f"/dags/{DAG_ID}/dagRuns", json=body)

    def get_run(self, dag_run_id: str) -> dict[str, Any]:
        return self._request("GET", f"/dags/{DAG_ID}/dagRuns/{dag_run_id}")

    def task_instances(self, dag_run_id: str) -> list[dict[str, Any]]:
        data = self._request("GET", f"/dags/{DAG_ID}/dagRuns/{dag_run_id}/taskInstances", params={"limit": 500})
        return data.get("task_instances", [])

    def wait(self, dag_run_id: str, timeout_seconds: float = 3600, poll_seconds: float = 5) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        while True:
            run = self.get_run(dag_run_id)
            if run.get("state") in TERMINAL_STATES:
                return run
            if time.monotonic() > deadline:
                raise AirflowClientError(f"Timed out waiting for {dag_run_id} (state={run.get('state')})")
            time.sleep(poll_seconds)


def build_conf(
    contract: str | None = None,
    datasets: list[str] | None = None,
    gold: list[str] | None = None,
    stages: list[str] | None = None,
    certification: str = "evaluate",
    *,
    contract_id: int | None = None,
) -> dict[str, Any]:
    """Build parameters accepted by the generic DataForge DAG.

    Exactly one immutable contract reference is required:
    a filesystem path for legacy/CLI use or a persisted contract_id
    for control-plane initiated runs.
    """

    if (contract is None) == (contract_id is None):
        raise ValueError(
            "Exactly one of contract or contract_id must be provided"
        )

    if contract_id is not None and contract_id < 1:
        raise ValueError(
            "contract_id must be a positive integer"
        )

    conf: dict[str, Any] = {
        "datasets": datasets or [],
        "gold": gold or [],
        "stages": stages or list(STAGES),
        "certification": certification,
    }

    if contract_id is not None:
        conf["contract_id"] = contract_id
    else:
        conf["contract"] = contract

    return conf


def _split(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"Trigger the {DAG_ID} Airflow DAG")
    contract_group = parser.add_mutually_exclusive_group(
        required=True
    )
    contract_group.add_argument("--contract")
    contract_group.add_argument(
        "--contract-id",
        type=int,
    )
    parser.add_argument("--datasets", default="")
    parser.add_argument("--gold", default="")
    parser.add_argument("--stages", default="")
    parser.add_argument("--certification", default="evaluate", choices=CERTIFICATION_MODES)
    parser.add_argument("--wait", action="store_true", help="Wait until the run finishes")
    parser.add_argument("--timeout", type=float, default=3600)
    args = parser.parse_args(argv)

    client = AirflowClient.from_env()
    conf = build_conf(
        args.contract,
        _split(args.datasets),
        _split(args.gold),
        _split(args.stages),
        args.certification,
        contract_id=args.contract_id,
    )
    run = client.trigger(conf)
    run_id = run["dag_run_id"]
    print(f"Triggered {DAG_ID} run {run_id}")
    print(json.dumps(conf))

    if not args.wait:
        return 0

    final = client.wait(run_id, timeout_seconds=args.timeout)
    print(f"Run {run_id}: {final['state'].upper()}")
    for ti in sorted(client.task_instances(run_id), key=lambda t: (t.get("start_date") or "", t["task_id"])):
        label = ti.get("rendered_map_index") or (ti["map_index"] if ti.get("map_index", -1) >= 0 else "")
        target = f"[{label}]" if label != "" else ""
        print(f"  {ti['task_id'] + target:<32} {ti.get('state')!s:<16} try={ti.get('try_number')}")
    return 0 if final["state"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
