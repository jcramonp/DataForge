"""Generic source connectors for DataForge."""

from src.connectors.base import (
    BaseConnector,
    ConnectorConfigurationError,
    ConnectorConnectionError,
    ConnectorError,
    ConnectorExtractionError,
)
from src.connectors.file_connector import (
    FileConnector,
)
from src.connectors.postgres_connector import (
    PostgresConnector,
)
from src.connectors.registry import (
    get_connector,
    get_dataset_connector,
)
from src.connectors.rest_connector import (
    RestConnector,
)

__all__ = [
    "BaseConnector",
    "ConnectorError",
    "ConnectorConfigurationError",
    "ConnectorConnectionError",
    "ConnectorExtractionError",
    "FileConnector",
    "PostgresConnector",
    "RestConnector",
    "get_connector",
    "get_dataset_connector",
]