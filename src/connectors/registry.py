"""REST connector for DataForge."""

from __future__ import annotations

from typing import Any

import requests

from src.connectors.base import BaseConnector, ConnectorError


class RestConnector(BaseConnector):
    """Generic connector for REST JSON APIs."""

    source_type = "rest"

    def test_connection(self) -> bool:
        url = self.config.get("url")
        if not url:
            raise ConnectorError("REST connector requires a 'url' configuration")

        response = requests.get(
            url,
            params=self.config.get("params", {}),
            headers=self.config.get("headers", {}),
            timeout=self.config.get("timeout", 30),
        )
        response.raise_for_status()
        return True

    def extract(self) -> list[dict[str, Any]]:
        url = self.config.get("url")
        if not url:
            raise ConnectorError("REST connector requires a 'url' configuration")

        response = requests.get(
            url,
            params=self.config.get("params", {}),
            headers=self.config.get("headers", {}),
            timeout=self.config.get("timeout", 30),
        )
        response.raise_for_status()

        payload = response.json()
        items = payload
        if isinstance(payload, dict):
            for key in ("items", "results", "data"):
                if key in payload and isinstance(payload[key], list):
                    items = payload[key]
                    break
            else:
                items = [payload]

        if not isinstance(items, list):
            raise ConnectorError("REST payload is not a list or a list-bearing object")

        self._set_last_result(items)
        return items


__all__ = ["RestConnector"]
