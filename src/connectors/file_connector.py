"""File connector for CSV, JSON and Parquet sources."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.connectors.base import (
    BaseConnector,
    ConnectorConfigurationError,
    ConnectorConnectionError,
    ConnectorExtractionError,
)


class FileConnector(BaseConnector):
    """Read local CSV, JSON and Parquet files."""

    def _path(self) -> Path:
        path_value = self.source_object.path

        if not path_value:
            raise ConnectorConfigurationError(
                "File connector requires source_object.path"
            )

        return Path(path_value)

    def test_connection(self) -> bool:
        path = self._path()

        if not path.exists():
            raise ConnectorConnectionError(
                f"Source file not found: {path}"
            )

        if not path.is_file():
            raise ConnectorConnectionError(
                f"Source path is not a file: {path}"
            )

        return True

    def extract(self) -> pd.DataFrame:
        path = self._path()

        self.test_connection()

        file_format = self.source_object.format

        if file_format is None:
            raise ConnectorConfigurationError(
                "File connector requires source_object.format"
            )

        try:
            if file_format.value == "csv":
                return pd.read_csv(
                    path,
                    dtype_backend="numpy_nullable",
                )

            if file_format.value == "json":
                return pd.read_json(path)

            if file_format.value == "parquet":
                return pd.read_parquet(
                    path,
                    engine="pyarrow",
                )

            raise ConnectorConfigurationError(
                f"Unsupported file format: {file_format.value}"
            )

        except ConnectorConfigurationError:
            raise

        except Exception as exc:
            raise ConnectorExtractionError(
                f"Failed to extract file source "
                f"'{self.source.code}' from '{path}': {exc}"
            ) from exc