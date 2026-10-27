"""Common connector interface for DataForge."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

import pandas as pd

from src.contracts.models import SourceConfig, SourceObjectConfig


class ConnectorError(RuntimeError):
    """Base error raised by DataForge connectors."""


class ConnectorConfigurationError(ConnectorError):
    """Raised when connector configuration is incomplete or invalid."""


class ConnectorConnectionError(ConnectorError):
    """Raised when a source cannot be reached."""


class ConnectorExtractionError(ConnectorError):
    """Raised when extraction fails after configuration is valid."""


class BaseConnector(ABC):
    """Common interface implemented by every DataForge source connector."""

    def __init__(
        self,
        source: SourceConfig,
        source_object: SourceObjectConfig,
        connection: Mapping[str, Any] | None = None,
    ) -> None:
        self.source = source
        self.source_object = source_object
        self.connection = dict(connection or {})

    @property
    def source_type(self) -> str:
        return self.source.type.value

    def describe(self) -> dict[str, Any]:
        """Return non-secret connector metadata."""

        return {
            "source_code": self.source.code,
            "source_type": self.source.type.value,
            "connection_reference": self.source.connection_reference,
        }

    @abstractmethod
    def test_connection(self) -> bool:
        """Verify that the configured source can be reached."""

    @abstractmethod
    def extract(self) -> pd.DataFrame:
        """Extract source records as the standard DataForge dataframe output."""