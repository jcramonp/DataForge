"""Connector factory for DataForge."""

from __future__ import annotations

from typing import Any

from src.connectors.base import BaseConnector, ConnectorError
from src.connectors.file_connector import FileConnector
from src.connectors.postgres_connector import PostgresConnector
from src.connectors.rest_connector import RestConnector


_CONNECTORS: dict[str, type[BaseConnector]] = {
    FileConnector.source_type: FileConnector,
    PostgresConnector.source_type: PostgresConnector,
    RestConnector.source_type: RestConnector,
}


def get_connector(config: dict[str, Any]) -> BaseConnector:
    """Instantiate the appropriate connector for the given source configuration."""
    source_type = config.get("source_type")
    if not source_type:
        raise ConnectorError("A source configuration must define 'source_type'")

    connector_class = _CONNECTORS.get(source_type)
    if connector_class is None:
        supported = ", ".join(sorted(_CONNECTORS.keys()))
        raise ConnectorError(f"Unsupported source type '{source_type}'. Supported types: {supported}")

    return connector_class(config)


__all__ = ["get_connector"]
