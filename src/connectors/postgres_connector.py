"""PostgreSQL connector for DataForge."""

from __future__ import annotations

from typing import Any

import pandas as pd
import psycopg
from psycopg import sql

from src.connectors.base import (
    BaseConnector,
    ConnectorConfigurationError,
    ConnectorConnectionError,
    ConnectorExtractionError,
)


class PostgresConnector(BaseConnector):
    """Extract PostgreSQL tables or explicitly configured SELECT queries."""

    REQUIRED_CONNECTION_FIELDS = {
        "host",
        "database",
        "user",
        "password",
    }

    def _connection_kwargs(self) -> dict[str, Any]:
        missing = sorted(
            field
            for field in self.REQUIRED_CONNECTION_FIELDS
            if not self.connection.get(field)
        )

        if missing:
            raise ConnectorConfigurationError(
                "PostgreSQL connection is missing required "
                f"fields: {missing}"
            )

        return {
            "host": self.connection["host"],
            "port": int(
                self.connection.get(
                    "port",
                    5432,
                )
            ),
            "dbname": self.connection["database"],
            "user": self.connection["user"],
            "password": self.connection["password"],
            "connect_timeout": int(
                self.connection.get(
                    "connect_timeout",
                    10,
                )
            ),
        }

    def _connect(self):
        return psycopg.connect(
            **self._connection_kwargs()
        )

    def test_connection(self) -> bool:
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()

            return True

        except ConnectorConfigurationError:
            raise

        except Exception as exc:
            raise ConnectorConnectionError(
                f"PostgreSQL connection failed for "
                f"source '{self.source.code}': {exc}"
            ) from exc

    @staticmethod
    def _validate_read_query(query: str) -> str:
        normalized = query.strip()

        if normalized.endswith(";"):
            normalized = normalized[:-1].rstrip()

        if ";" in normalized:
            raise ConnectorConfigurationError(
                "PostgreSQL query must contain exactly one statement"
            )

        if not normalized.lower().startswith("select"):
            raise ConnectorConfigurationError(
                "Only read-only SELECT queries are supported"
            )

        return normalized

    def _table_query(self):
        table = self.source_object.table

        if not table:
            raise ConnectorConfigurationError(
                "PostgreSQL table extraction requires "
                "source_object.table"
            )

        schema_name = (
            self.source_object.schema_name
            or "public"
        )

        return sql.SQL(
            "SELECT * FROM {}.{}"
        ).format(
            sql.Identifier(schema_name),
            sql.Identifier(table),
        )

    def extract(self) -> pd.DataFrame:
        configured_query = self.source_object.query

        if configured_query:
            statement: Any = self._validate_read_query(
                configured_query
            )
        else:
            statement = self._table_query()

        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(statement)

                    rows = cursor.fetchall()

                    column_names = [
                        description.name
                        for description in cursor.description
                    ]

            return pd.DataFrame(
                rows,
                columns=column_names,
            )

        except ConnectorConfigurationError:
            raise

        except Exception as exc:
            raise ConnectorExtractionError(
                f"PostgreSQL extraction failed for "
                f"source '{self.source.code}': {exc}"
            ) from exc