"""Operational status summary for pipeline runs and failures.

Reads the views created by ``database/migrations/0003_operational_views.sql``.

Usage::

    python -m src.ops.run_summary            # human-readable summary
    python -m src.ops.run_summary --json     # machine-readable summary
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from typing import Any

import psycopg

from src.common.clients import connect_postgres


def _rows(conn: psycopg.Connection, query: str, params: tuple = ()) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(query, params)
        columns = [col.name for col in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        # SUM(bigint) comes back as numeric; keep row counts as integers.
        return int(value) if value == value.to_integral_value() else float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _clean(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: _jsonable(v) for k, v in row.items()} for row in rows]


def summarize_status_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per (run_type, status) rows into overall totals."""

    def total(status: str | None = None) -> int:
        return int(
            sum(r["run_count"] for r in rows if status is None or r["status"] == status)
        )

    total_runs = total()
    failed = total("failed")
    return {
        "total_runs": total_runs,
        "successful_runs": total("success"),
        "failed_runs": failed,
        "running_runs": total("running"),
        "failure_rate": round(failed / total_runs, 4) if total_runs else 0.0,
        "rejected_rows": int(sum(r["rejected_rows"] or 0 for r in rows)),
    }


def fetch_run_summary(conn: psycopg.Connection, recent_failures: int = 10) -> dict[str, Any]:
    by_stage = _clean(
        _rows(
            conn,
            "SELECT * FROM pipeline_run_status_summary ORDER BY run_type, status",
        )
    )
    failures = _clean(
        _rows(
            conn,
            "SELECT * FROM pipeline_run_failures ORDER BY started_at DESC LIMIT %s",
            (recent_failures,),
        )
    )
    datasets = _clean(
        _rows(
            conn,
            "SELECT * FROM dataset_latest_run ORDER BY client_code, dataset_code, run_type",
        )
    )
    return {
        "totals": summarize_status_rows(by_stage),
        "by_stage": by_stage,
        "recent_failures": failures,
        "datasets": datasets,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize DataForge pipeline runs")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--failures", type=int, default=10, help="Number of recent failures")
    args = parser.parse_args(argv)

    with connect_postgres() as conn:
        summary = fetch_run_summary(conn, args.failures)

    if args.json:
        print(json.dumps(summary, indent=2, default=str))
        return 0

    t = summary["totals"]
    print(
        f"Runs: {t['total_runs']} total | {t['successful_runs']} success | "
        f"{t['failed_runs']} failed | {t['running_runs']} running | "
        f"failure rate {t['failure_rate']:.1%} | rejected rows {t['rejected_rows']}"
    )
    print("\nBy stage:")
    for row in summary["by_stage"]:
        print(
            f"  {row['run_type']:<22} {row['status']:<8} runs={row['run_count']:<5} "
            f"accepted={row['accepted_rows']:<8} rejected={row['rejected_rows']:<6} "
            f"avg={row['avg_duration_seconds']}s"
        )
    print("\nRecent failures:")
    if not summary["recent_failures"]:
        print("  none")
    for row in summary["recent_failures"]:
        print(
            f"  run_id={row['run_id']} {row['client_code']}/{row['dataset_code']} "
            f"{row['run_type']} at {row['started_at']}: {row['error_message']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
