"""Refresh the operational reporting snapshot; never changes live API totals."""

from src.common.clients import connect_postgres


def main() -> None:
    with connect_postgres(autocommit=True) as conn:
        conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY metadata_run_totals_cache")
        rows = conn.execute("SELECT COUNT(*) FROM metadata_run_totals").fetchone()[0]
        print(f"Refreshed metadata_run_totals: {rows} groups (snapshot, not live metrics).")


if __name__ == "__main__":
    main()
