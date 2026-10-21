"""Connector primitives for DataForge.

This starter implementation introduces a generic connector abstraction so the
platform can ingest CSV, JSON, Parquet, PostgreSQL or REST sources without
hardcoding Olist-specific logic into the Bronze layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ConnectorError(RuntimeError):
    """Raised when a connector cannot connect or extract data."""


class BaseConnector(ABC):
    """Abstract contract for all DataForge source connectors."""

    source_type: str = "base"

    def __init__(self, config: dict[str, Any] | None = None):
        self.config: dict[str, Any] = config or {}
        self._last_schema: list[str] | None = None
        self._last_records: list[dict[str, Any]] = []

    def describe(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "config": self.config,
        }

    @abstractmethod
    def test_connection(self) -> bool:
        """Return True when the connector can reach its source."""

    @abstractmethod
    def extract(self) -> list[dict[str, Any]]:
        """Return records as a list of dictionaries."""

    def get_schema(self) -> list[str]:
        """Return the last extracted schema in column order."""
        if self._last_schema is not None:
            return list(self._last_schema)
        if self._last_records:
            return list(self._last_records[0].keys())
        return list(self.config.get("columns", []))

    def _set_last_result(self, records: list[dict[str, Any]]) -> None:
        self._last_records = records
        if records:
            self._last_schema = list(records[0].keys())


__all__ = ["BaseConnector", "ConnectorError"]
