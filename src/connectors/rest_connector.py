"""REST JSON connector for DataForge."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import pandas as pd
import requests

from src.connectors.base import (
    BaseConnector,
    ConnectorConfigurationError,
    ConnectorConnectionError,
    ConnectorExtractionError,
)
from src.contracts.models import RestPaginationStrategy


class RestConnector(BaseConnector):
    """Extract tabular records from GET-based JSON APIs."""

    def _url(self) -> str:
        endpoint = self.source_object.endpoint

        if not endpoint:
            raise ConnectorConfigurationError(
                "REST connector requires source_object.endpoint"
            )

        if endpoint.startswith(
            ("http://", "https://")
        ):
            return endpoint

        base_url = self.connection.get("base_url")

        if not base_url:
            raise ConnectorConfigurationError(
                "Relative REST endpoints require "
                "'base_url' in the resolved connection"
            )

        return urljoin(
            f"{base_url.rstrip('/')}/",
            endpoint.lstrip("/"),
        )

    def _headers(self) -> dict[str, str]:
        configured = dict(
            self.source_object.headers
        )

        secret_headers = self.connection.get(
            "headers",
            {},
        )

        if not isinstance(secret_headers, dict):
            raise ConnectorConfigurationError(
                "REST connection 'headers' must be an object"
            )

        configured.update(
            {
                str(key): str(value)
                for key, value
                in secret_headers.items()
            }
        )

        return configured

    def _params(self) -> dict[str, Any]:
        configured = dict(
            self.source_object.params
        )

        secret_params = self.connection.get(
            "params",
            {},
        )

        if not isinstance(secret_params, dict):
            raise ConnectorConfigurationError(
                "REST connection 'params' must be an object"
            )

        configured.update(secret_params)

        return configured

    def _request(
        self,
        params: dict[str, Any],
    ) -> Any:
        response = requests.get(
            self._url(),
            params=params,
            headers=self._headers(),
            timeout=self.source_object.timeout_seconds,
        )

        response.raise_for_status()

        try:
            return response.json()
        except ValueError as exc:
            raise ConnectorExtractionError(
                f"REST source '{self.source.code}' "
                "did not return valid JSON"
            ) from exc

    @staticmethod
    def _lookup_path(
        payload: Any,
        path: str,
    ) -> Any:
        current = payload

        for part in path.split("."):
            if not isinstance(current, dict):
                raise ConnectorExtractionError(
                    f"Cannot resolve REST records_path '{path}'"
                )

            if part not in current:
                raise ConnectorExtractionError(
                    f"REST records_path '{path}' "
                    f"does not contain '{part}'"
                )

            current = current[part]

        return current

    def _records_from_payload(
        self,
        payload: Any,
    ) -> list[dict[str, Any]]:
        records_path = self.source_object.records_path

        if records_path:
            payload = self._lookup_path(
                payload,
                records_path,
            )

        elif isinstance(payload, dict):
            for key in (
                "items",
                "results",
                "data",
            ):
                candidate = payload.get(key)

                if isinstance(candidate, list):
                    payload = candidate
                    break
            else:
                payload = [payload]

        if isinstance(payload, dict):
            payload = [payload]

        if not isinstance(payload, list):
            raise ConnectorExtractionError(
                "REST JSON payload must resolve to "
                "an object or list of objects"
            )

        if not all(
            isinstance(item, dict)
            for item in payload
        ):
            raise ConnectorExtractionError(
                "REST records must be JSON objects"
            )

        return payload

    def test_connection(self) -> bool:
        try:
            self._request(
                self._params()
            )

            return True

        except ConnectorConfigurationError:
            raise

        except requests.RequestException as exc:
            raise ConnectorConnectionError(
                f"REST connection failed for "
                f"source '{self.source.code}': {exc}"
            ) from exc

    def _extract_without_pagination(
        self,
    ) -> list[dict[str, Any]]:
        payload = self._request(
            self._params()
        )

        return self._records_from_payload(
            payload
        )

    def _extract_page_pagination(
        self,
    ) -> list[dict[str, Any]]:
        pagination = self.source_object.pagination

        records: list[dict[str, Any]] = []

        page = pagination.start_page

        for _ in range(pagination.max_pages):
            params = self._params()

            params[
                pagination.page_param
            ] = page

            params[
                pagination.page_size_param
            ] = pagination.page_size

            payload = self._request(params)

            batch = self._records_from_payload(
                payload
            )

            records.extend(batch)

            if len(batch) < pagination.page_size:
                break

            page += 1

        return records

    def _extract_offset_pagination(
        self,
    ) -> list[dict[str, Any]]:
        pagination = self.source_object.pagination

        records: list[dict[str, Any]] = []

        offset = pagination.start_offset

        for _ in range(pagination.max_pages):
            params = self._params()

            params[
                pagination.offset_param
            ] = offset

            params[
                pagination.limit_param
            ] = pagination.page_size

            payload = self._request(params)

            batch = self._records_from_payload(
                payload
            )

            records.extend(batch)

            if len(batch) < pagination.page_size:
                break

            offset += pagination.page_size

        return records

    def extract(self) -> pd.DataFrame:
        try:
            strategy = (
                self.source_object
                .pagination
                .strategy
            )

            if strategy == RestPaginationStrategy.NONE:
                records = (
                    self._extract_without_pagination()
                )

            elif strategy == RestPaginationStrategy.PAGE:
                records = (
                    self._extract_page_pagination()
                )

            elif strategy == RestPaginationStrategy.OFFSET:
                records = (
                    self._extract_offset_pagination()
                )

            else:
                raise ConnectorConfigurationError(
                    f"Unsupported REST pagination strategy: "
                    f"{strategy}"
                )

            return pd.DataFrame(records)

        except (
            ConnectorConfigurationError,
            ConnectorExtractionError,
        ):
            raise

        except requests.RequestException as exc:
            raise ConnectorExtractionError(
                f"REST extraction failed for "
                f"source '{self.source.code}': {exc}"
            ) from exc