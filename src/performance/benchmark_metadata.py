"""Compare identical PostgreSQL queries before/after migration 0008.

Synthetic volume is isolated in a transaction-local schema and rolled back.
No production tables, indexes, planner switches or data are removed/disabled.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from time import perf_counter
from uuid import uuid4

from psycopg import sql

from src.common.clients import connect_postgres
from src.common.settings import PROJECT_ROOT


AGGREGATION = """
SELECT dv.dataset_id, pr.run_type, pr.status, COUNT(*) AS run_count,
       COALESCE(SUM(pr.input_rows), 0) AS input_rows,
       COALESCE(SUM(pr.accepted_rows), 0) AS accepted_rows,
       COALESCE(SUM(pr.rejected_rows), 0) AS rejected_rows
FROM pipeline_run pr
JOIN dataset_version dv ON dv.dataset_version_id = pr.dataset_version_id
GROUP BY dv.dataset_id, pr.run_type, pr.status
"""
QUERIES = {
    "latest_version_index": """SELECT dataset_version_id, version_label
FROM dataset_version WHERE dataset_id = 42
ORDER BY discovered_at DESC, dataset_version_id DESC LIMIT 1""",
    "materialized_run_totals": """SELECT * FROM metadata_run_totals
WHERE dataset_id = 42 ORDER BY run_type, status""",
}


def measure(conn, query: str, repetitions: int) -> dict:
    expected = conn.execute(query).fetchall()  # Warm cache, validate every sample.
    plans = []
    for _ in range(repetitions):
        plan = conn.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + query).fetchone()[0][0]
        plans.append(plan)
        if conn.execute(query).fetchall() != expected:
            raise RuntimeError("Query result changed during benchmark")
    return {
        "median_ms": median(p["Execution Time"] for p in plans),
        "samples_ms": [p["Execution Time"] for p in plans],
        "result": [list(row) for row in expected],
        "plan": plans[-1],
    }


def benchmark(rows: int, repetitions: int) -> dict:
    schema = "df_benchmark_" + uuid4().hex
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "data": "synthetic isolated PostgreSQL metadata, not business/production rows",
              "dataset_versions": rows, "pipeline_runs": rows,
              "repetitions": repetitions, "cache": "warm; one untimed result query per case",
              "queries": QUERIES, "before": {}, "after": {}}
    with connect_postgres() as conn:
        try:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            conn.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(schema)))
            conn.execute("SET LOCAL statement_timeout = '120s'")
            report["postgres_version"] = conn.execute("SELECT version()").fetchone()[0]
            conn.execute("""CREATE TABLE dataset_version (
                dataset_version_id BIGINT PRIMARY KEY, dataset_id BIGINT NOT NULL,
                version_label TEXT NOT NULL, discovered_at TIMESTAMPTZ NOT NULL)""")
            conn.execute("""CREATE TABLE pipeline_run (
                run_id BIGINT PRIMARY KEY, dataset_version_id BIGINT NOT NULL,
                run_type TEXT NOT NULL, status TEXT NOT NULL,
                input_rows BIGINT, accepted_rows BIGINT, rejected_rows BIGINT)""")
            conn.execute("""INSERT INTO dataset_version
                SELECT i, i %% 1000, 'v' || i,
                TIMESTAMPTZ '2025-01-01' + i * INTERVAL '1 second'
                FROM generate_series(1, %s) i""", (rows,))
            conn.execute("""INSERT INTO pipeline_run
                SELECT i, i, CASE WHEN i %% 3 = 0 THEN 'source_to_bronze'
                ELSE 'silver_quality_gate' END,
                CASE WHEN i %% 7 = 0 THEN 'failed' ELSE 'success' END,
                100, 95, 5 FROM generate_series(1, %s) i""", (rows,))
            # Existing production index is part of the baseline, not removed.
            conn.execute("CREATE INDEX idx_dataset_version_dataset_id ON dataset_version(dataset_id)")
            conn.execute("ANALYZE dataset_version")
            conn.execute("ANALYZE pipeline_run")
            conn.execute("CREATE VIEW metadata_run_totals AS " + AGGREGATION)
            for name, query in QUERIES.items():
                report["before"][name] = measure(conn, query, repetitions)
            start = perf_counter()
            conn.execute((PROJECT_ROOT / "database/migrations/0008_metadata_performance.sql").read_text())
            report["build_ms"] = (perf_counter() - start) * 1000
            conn.execute("ANALYZE metadata_run_totals_cache")
            for name, query in QUERIES.items():
                report["after"][name] = measure(conn, query, repetitions)
                if report["before"][name]["result"] != report["after"][name]["result"]:
                    raise RuntimeError(f"Before/after results differ: {name}")
            start = perf_counter()
            conn.execute("REFRESH MATERIALIZED VIEW metadata_run_totals_cache")
            report["refresh_ms"] = (perf_counter() - start) * 1000
            # Migration is idempotent; running twice must preserve query results.
            conn.execute((PROJECT_ROOT / "database/migrations/0008_metadata_performance.sql").read_text())
            for name, query in QUERIES.items():
                if [list(row) for row in conn.execute(query).fetchall()] != report["after"][name]["result"]:
                    raise RuntimeError("Migration replay changed results")
        finally:
            conn.rollback()  # Also removes our schema on success or failure.
    report["isolated_schema_rolled_back"] = True
    report["equal_results"] = True
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=300_000)
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.rows < 1000 or args.repetitions < 3:
        parser.error("Use at least 1000 rows and 3 repetitions")
    report = benchmark(args.rows, args.repetitions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    for name in QUERIES:
        before = report["before"][name]["median_ms"]
        after = report["after"][name]["median_ms"]
        print(f"{name}: {before:.3f} -> {after:.3f} ms; equal results")


if __name__ == "__main__":
    main()
