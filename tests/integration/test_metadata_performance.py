"""PostgreSQL equivalence and fresh-install checks in rolled-back private schemas."""

import unittest
from uuid import uuid4

from psycopg import sql

from src.common.clients import connect_postgres
from src.ops.migrate import discover_migrations
from src.performance.benchmark_metadata import benchmark
from tests.integration import requires_integration


@requires_integration
class MetadataPerformanceTests(unittest.TestCase):
    def test_queries_preserve_results_after_optimization_and_refresh(self):
        result = benchmark(rows=12_000, repetitions=3)
        self.assertTrue(result["equal_results"])
        self.assertTrue(result["isolated_schema_rolled_back"])
        for name in result["queries"]:
            self.assertEqual(result["before"][name]["result"], result["after"][name]["result"])

    def test_fresh_schema_accepts_all_migrations_twice(self):
        schema = "df_migration_test_" + uuid4().hex
        with connect_postgres() as conn:
            try:
                conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
                conn.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(schema)))
                for _ in range(2):
                    for migration in discover_migrations():
                        conn.execute(migration.sql)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM metadata_run_totals").fetchone()[0], 0)
            finally:
                conn.rollback()
            self.assertIsNone(conn.execute("SELECT to_regnamespace(%s)", (schema,)).fetchone()[0])
