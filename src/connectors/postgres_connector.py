"""PostgreSQL connector for DataForge."""

from __future__ import annotations

from typing import Any

import pandas as pd
import psycopg

from src.connectors.base import BaseConnector, ConnectorError


class PostgresConnector(BaseConnector):
    """Generic connector for PostgreSQL tables or SQL queries."""

    source_type = "postgres"

    def _connect(self):
        return psycopg.connect(
            host=self.config.get("host", "localhost"),
            port=int(self.config.get("port", 5432)),
            dbname=self.config.get("database", "postgres"),
            user=self.config.get("user", "postgres"),
            password=self.config.get("password", "postgres"),
        )

    def test_connection(self) -> bool:
        try:
            with self._connect() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
            return True
        except Exception as exc:  # pragma: no cover - exercised by integration tests
            raise ConnectorError(f"PostgreSQL connection failed: {exc}") from exc

    def extract(self) -> list[dict[str, Any]]:
        table_name = self.config.get("table")
        query = self.config.get("query")

        if not table_name and not query:
            raise ConnectorError("PostgreSQL connector requires either 'table' or 'query'")

        with self._connect() as conn:
            if query:
                frame = pd.read_sql(query, conn)
            else:
                frame = pd.read_sql(f"SELECT * FROM {table_name}", conn)

        records = frame.to_dict(orient="records")
        self._set_last_result(records)
        return records


__all__ = ["PostgresConnector"]
