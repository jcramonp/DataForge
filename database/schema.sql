from __future__ import annotations

import json
from pathlib import Path

from src.connectors.file_connector import FileConnector
from src.connectors.registry import get_connector


def test_file_connector_extracts_csv(tmp_path: Path):
    source = tmp_path / "demo.csv"
    source.write_text("id,name\n1,Ana\n2,Beto\n", encoding="utf-8")

    connector = FileConnector({"path": str(source), "file_type": "csv"})
    records = connector.extract()

    assert len(records) == 2
    assert connector.get_schema() == ["id", "name"]
    assert records[0]["name"] == "Ana"


def test_registry_creates_file_connector():
    connector = get_connector({"source_type": "file", "path": "demo.csv", "file_type": "csv"})
    assert connector.source_type == "file"


def test_rest_connector_supports_payload_variants():
    payload = {"items": [{"id": 1, "name": "Alpha"}]}
    connector = get_connector({"source_type": "rest", "url": "https://example.com"})
    connector._set_last_result(payload["items"])
    assert connector.extract() == payload["items"]


def test_registry_rejects_unknown_type():
    try:
        get_connector({"source_type": "unsupported"})
        assert False, "Expected ConnectorError for unsupported connector type"
    except Exception as exc:  # pragma: no cover - sanity guard for registry errors
        assert "Unsupported source type" in str(exc)
