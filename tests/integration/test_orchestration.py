"""Generic orchestration against real PostgreSQL and MinIO (#24).

Runs the standalone entrypoint (the same plan/stages/run-state the Airflow DAG
uses) for two structurally different sources:

- the non-Olist CSV fixture (file source);
- ``config/examples/postgres_sales.yaml`` (postgresql source), reading from a
  throwaway source database seeded from ``tests/fixtures/postgres_sales/seed.sql``.

The Airflow DAG itself is executed end to end by the CI job "Airflow DAG".
"""

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import psycopg

from src.common.clients import connect_postgres
from src.ops.migrate import run_migrations
from src.orchestration.pipeline import run_pipeline
from src.orchestration.plan import build_plan
from tests.integration import (
    fetch_all,
    integration_settings,
    requires_integration,
    reset_buckets,
    reset_database,
)


RETAIL = "tests/fixtures/e2e/retail_contract.yaml"
POSTGRES_SALES = "config/examples/postgres_sales.yaml"
SOURCE_DB = "dataforge_it_sales_source"
SEED = Path(__file__).resolve().parents[1] / "fixtures" / "postgres_sales" / "seed.sql"


def prepare(settings) -> None:
    reset_database(settings)
    with connect_postgres(settings, autocommit=True) as conn:
        run_migrations(conn)
    reset_buckets(settings, "")


def seed_source_database(settings) -> str:
    """Create a disposable source database and return its connection JSON."""

    with connect_postgres(settings, autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {SOURCE_DB}")
        conn.execute(f"CREATE DATABASE {SOURCE_DB}")
    kwargs = settings.postgres.connection_kwargs()
    with psycopg.connect(**{**kwargs, "dbname": SOURCE_DB}, autocommit=True) as conn:
        conn.execute(SEED.read_text(encoding="utf-8"))
    return json.dumps(
        {
            "host": kwargs["host"],
            "port": kwargs["port"],
            "database": SOURCE_DB,
            "user": kwargs["user"],
            "password": kwargs["password"],
        }
    )


def task_rows(settings, orchestration_run_id):
    return fetch_all(
        settings,
        """
        SELECT stage, target, attempt, status, pipeline_run_id IS NOT NULL
        FROM orchestration_task_run
        WHERE orchestration_run_id = %s
        ORDER BY task_run_id
        """,
        (orchestration_run_id,),
    )


@requires_integration
class FileSourceOrchestrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = integration_settings()
        prepare(cls.settings)
        cls.outcome = run_pipeline(build_plan(RETAIL, certification="validate"), external_run_id="it__retail")

    def test_every_stage_succeeds_in_order(self):
        self.assertEqual(self.outcome["status"], "success", self.outcome["error"])
        rows = task_rows(self.settings, self.outcome["orchestration_run_id"])
        self.assertEqual(
            [(r[0], r[1], r[3]) for r in rows],
            [
                ("bronze", "orders", "success"),
                ("profiling", "orders", "success"),
                ("silver", "orders", "success"),
                ("gold", "orders_by_status", "success"),
                ("certification", "contract", "success"),
            ],
        )
        linked = {r[0]: r[4] for r in rows}
        self.assertTrue(linked["bronze"] and linked["profiling"] and linked["silver"] and linked["gold"])

    def test_run_is_closed_in_the_control_plane(self):
        row = fetch_all(
            self.settings,
            "SELECT orchestrator, external_run_id, status, task_count, failed_tasks FROM orchestration_run_summary",
        )
        self.assertEqual(row, [("cli", "it__retail", "success", 5, 0)])

    def test_profiling_is_persisted_and_traceable_to_its_bronze_asset(self):
        # orchestration_task_run -> pipeline_run(profiling) -> profiling_result -> Bronze asset
        rows = fetch_all(
            self.settings,
            """
            SELECT otr.status, pr.run_type, pr.status, prf.profile_id, prf.source_asset_id,
                   prf.row_count, prf.column_count, otr.summary_json
            FROM orchestration_task_run otr
            JOIN pipeline_run pr ON pr.run_id = otr.pipeline_run_id
            JOIN profiling_result prf ON prf.run_id = pr.run_id
            WHERE otr.orchestration_run_id = %s AND otr.stage = 'profiling'
            """,
            (self.outcome["orchestration_run_id"],),
        )
        self.assertEqual(len(rows), 1)
        task_status, run_type, run_status, profile_id, source_asset_id, row_count, column_count, summary = rows[0]
        self.assertEqual((task_status, run_type, run_status), ("success", "profiling", "success"))
        self.assertEqual((row_count, column_count), (7, 5))

        bronze_asset_id = fetch_all(
            self.settings,
            """
            SELECT da.asset_id
            FROM orchestration_task_run otr
            JOIN data_asset da ON da.run_id = otr.pipeline_run_id AND da.layer = 'bronze'
            WHERE otr.orchestration_run_id = %s AND otr.stage = 'bronze'
            """,
            (self.outcome["orchestration_run_id"],),
        )[0][0]
        self.assertEqual(source_asset_id, bronze_asset_id)

        # Compact summary only; the full profile lives in profiling_result.profile_json.
        self.assertEqual(summary["profile_id"], profile_id)
        self.assertEqual(summary["source_asset_id"], bronze_asset_id)
        self.assertNotIn("profile", summary)
        self.assertNotIn("columns", summary)

    def test_validate_mode_promotes_ready_gold_version(self):
        versions = self.outcome["results"]["certification"]["contract"]["versions"]
        gold = next(v for v in versions if v["target"] == "orders_by_status")
        self.assertEqual((gold["state_before"], gold["state_after"]), ("draft", "validated"))
        states = dict(
            fetch_all(
                self.settings,
                """
                SELECT d.dataset_code, dc.state
                FROM dataset_certification dc
                JOIN dataset_version dv USING (dataset_version_id)
                JOIN dataset d USING (dataset_id)
                WHERE dc.dataset_version_id = %s
                """,
                (gold["dataset_version_id"],),
            )
        )
        self.assertEqual(states, {"orders_by_status": "validated"})


@requires_integration
class PostgresSourceOrchestrationTests(unittest.TestCase):
    """A structurally different source type through the same orchestration."""

    @classmethod
    def setUpClass(cls):
        cls.settings = integration_settings()
        prepare(cls.settings)
        connection = seed_source_database(cls.settings)
        with patch.dict(os.environ, {"DATAFORGE_CONNECTION_DEMO_POSTGRES": connection}):
            cls.outcome = run_pipeline(build_plan(POSTGRES_SALES), external_run_id="it__sales")

    def test_pipeline_succeeds(self):
        self.assertEqual(self.outcome["status"], "success", self.outcome["error"])

    def test_profiling_persisted_for_the_postgres_source(self):
        profiling = self.outcome["results"]["profiling"]["sales"]
        self.assertEqual((profiling["row_count"], profiling["column_count"]), (5, 5))
        rows = fetch_all(
            self.settings,
            "SELECT run_type FROM pipeline_run pr JOIN profiling_result prf ON prf.run_id = pr.run_id "
            "WHERE prf.profile_id = %s",
            (profiling["profile_id"],),
        )
        self.assertEqual(rows, [("profiling",)])

    def test_quality_gate_and_gold_results(self):
        silver = self.outcome["results"]["silver"]["sales"]
        self.assertEqual((silver["input_rows"], silver["accepted_rows"], silver["rejected_rows"]), (5, 4, 1))
        gold = self.outcome["results"]["gold"]["sales_gold"]
        self.assertEqual((gold["input_rows"], gold["output_rows"]), (4, 4))


@requires_integration
class FailedOrchestrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = integration_settings()
        prepare(cls.settings)
        # Silver without any Bronze ingestion: the stage fails, Gold never runs.
        cls.outcome = run_pipeline(build_plan(RETAIL, stages="silver,gold"), external_run_id="it__failed")

    def test_run_fails_with_a_traceable_reason(self):
        self.assertEqual(self.outcome["status"], "failed")
        self.assertIn("silver[orders] failed", self.outcome["error"])
        self.assertIn("gold[orders_by_status] did not run", self.outcome["error"])

    def test_failed_attempt_is_recorded(self):
        rows = task_rows(self.settings, self.outcome["orchestration_run_id"])
        self.assertEqual([(r[0], r[3]) for r in rows], [("silver", "failed")])
        run = fetch_all(self.settings, "SELECT status, error_message FROM orchestration_run")[0]
        self.assertEqual(run[0], "failed")
        self.assertIn("No successful Bronze asset", run[1])


if __name__ == "__main__":
    unittest.main()
