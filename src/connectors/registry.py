"""Connector registry and contract integration."""

from __future__ import annotations

from collections.abc import Mapping

from src.connectors.base import (
    BaseConnector,
    ConnectorConfigurationError,
)
from src.connectors.credentials import (
    resolve_connection_reference,
)
from src.connectors.file_connector import (
    FileConnector,
)
from src.connectors.postgres_connector import (
    PostgresConnector,
)
from src.connectors.rest_connector import (
    RestConnector,
)
from src.contracts.models import (
    DataForgeContract,
    SourceConfig,
    SourceObjectConfig,
    SourceType,
)


CONNECTOR_REGISTRY: dict[
    SourceType,
    type[BaseConnector],
] = {
    SourceType.FILE: FileConnector,
    SourceType.POSTGRESQL: PostgresConnector,
    SourceType.REST: RestConnector,
}


def get_connector(
    source: SourceConfig,
    source_object: SourceObjectConfig,
    environ: Mapping[str, str] | None = None,
) -> BaseConnector:
    """Create the connector selected by contract metadata."""

    connector_class = CONNECTOR_REGISTRY.get(
        source.type
    )

    if connector_class is None:
        raise ConnectorConfigurationError(
            f"Unsupported source type: "
            f"{source.type.value}"
        )

    connection = resolve_connection_reference(
        source.connection_reference,
        environ=environ,
    )

    return connector_class(
        source=source,
        source_object=source_object,
        connection=connection,
    )


def get_dataset_connector(
    contract: DataForgeContract,
    dataset_code: str,
    environ: Mapping[str, str] | None = None,
) -> BaseConnector:
    """Create the correct connector for a configured dataset."""

    dataset = next(
        (
            item
            for item in contract.datasets
            if item.code == dataset_code
        ),
        None,
    )

    if dataset is None:
        raise ConnectorConfigurationError(
            f"Unknown dataset '{dataset_code}'"
        )

    return get_connector(
        source=contract.source,
        source_object=dataset.source_object,
        environ=environ,
    )