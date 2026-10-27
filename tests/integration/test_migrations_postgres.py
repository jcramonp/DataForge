"""Migration workflow against a real PostgreSQL instance (#32)."""

import unittest

from src.common.clients import connect_postgres
from src.ops.migrate import MigrationError, discover_migrations, migration_status, run_migrations
from tests.integration import fetch_all, integration_settings, requires_integration, reset_database


EXPECTED_TABLES = {
    "client",
    "project",
    "data_source",
    "dataset",
    "dataset_version",
    "pipeline_run",
    "quality_result",
    "data_asset",
    "asset_lineage",
    "dataset_certification",
    "certification_transition",
    "profiling_result",
    "orchestration_run",
    "orchestration_task_run",
    "schema_migrations",
}

EXPECTED_VIEWS = {
    "dataset_lineage_summary",
    "data_quality_summary",
    "pipeline_run_status_summary",
    "pipeline_run_failures",
    "dataset_latest_run",
    "asset_lineage_edges",
    "dataset_certification_summary",
    "dataset_profiling_history",
    "dataset_latest_profile",
    "orchestration_task_latest",
    "orchestration_run_summary",
}


@requires_integration
class MigrationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = integration_settings()

    def setUp(self):
        reset_database(self.settings)

    def test_fresh_database_is_migrated_and_rerun_is_a_noop(self):
        migrations = discover_migrations()
        with connect_postgres(self.settings, autocommit=True) as conn:
            first = run_migrations(conn)
            second = run_migrations(conn)
            status = migration_status(conn)

        self.assertEqual(len(first.pending), len(migrations))
        self.assertEqual(second.pending, [])
        self.assertEqual(len(status.applied), len(migrations))

        tables = {r[0] for r in fetch_all(self.settings, "SELECT tablename FROM pg_tables WHERE schemaname = 'public'")}
        views = {r[0] for r in fetch_all(self.settings, "SELECT viewname FROM pg_views WHERE schemaname = 'public'")}
        self.assertTrue(EXPECTED_TABLES <= tables, EXPECTED_TABLES - tables)
        self.assertTrue(EXPECTED_VIEWS <= views, EXPECTED_VIEWS - views)

    def test_database_bootstrapped_by_docker_init_is_adopted(self):
        # docker-entrypoint-initdb.d runs the raw SQL files without recording
        # them; the runner must re-apply them safely and record each version.
        with connect_postgres(self.settings, autocommit=True) as conn:
            with conn.cursor() as cur:
                for migration in discover_migrations():
                    cur.execute(migration.sql)
            plan = run_migrations(conn)
            status = migration_status(conn)

        self.assertEqual(len(plan.pending), len(discover_migrations()))
        self.assertEqual(status.pending, [])

    def test_edited_applied_migration_is_rejected(self):
        with connect_postgres(self.settings, autocommit=True) as conn:
            run_migrations(conn)
            with conn.cursor() as cur:
                cur.execute("UPDATE schema_migrations SET checksum = %s WHERE version = '0001'", ("0" * 64,))
            with self.assertRaises(MigrationError):
                run_migrations(conn)


if __name__ == "__main__":
    unittest.main()
