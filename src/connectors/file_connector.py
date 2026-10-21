"""File-based connectors for DataForge."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.connectors.base import BaseConnector, ConnectorError


class FileConnector(BaseConnector):
    """Generic connector for local file sources such as CSV, JSON, or Parquet."""

    source_type = "file"

    def test_connection(self) -> bool:
        path = self.config.get("path")
        if not path:
            raise ConnectorError("File connector requires a 'path' configuration")
        return Path(path).exists()

    def extract(self) -> list[dict[str, Any]]:
        path_value = self.config.get("path")
        if not path_value:
            raise ConnectorError("File connector requires a 'path' configuration")

        path = Path(path_value)
        if not path.exists():
            raise ConnectorError(f"Source file not found: {path}")

        file_type = self.config.get("file_type") or path.suffix.lower().lstrip(".")

        if file_type == "csv":
            frame = pd.read_csv(path)
        elif file_type == "json":
            frame = pd.read_json(path)
        elif file_type in {"parquet", "pq"}:
            frame = pd.read_parquet(path)
        else:
            raise ConnectorError(f"Unsupported file source type: {file_type}")

        records = frame.to_dict(orient="records")
        self._set_last_result(records)
        return records


__all__ = ["FileConnector"]
