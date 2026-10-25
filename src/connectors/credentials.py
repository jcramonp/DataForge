"""Resolve connector credentials without storing secrets in contracts."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from typing import Any

from src.connectors.base import ConnectorConfigurationError


ENV_PREFIX = "DATAFORGE_CONNECTION_"


def connection_env_name(reference: str) -> str:
    """Convert a connection reference into its environment variable name."""

    normalized = re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        reference,
    ).strip("_").upper()

    if not normalized:
        raise ConnectorConfigurationError(
            "Connection reference cannot be empty"
        )

    return f"{ENV_PREFIX}{normalized}"


def resolve_connection_reference(
    reference: str | None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Resolve a connection reference from a JSON environment variable."""

    if reference is None:
        return {}

    environment = environ if environ is not None else os.environ

    variable_name = connection_env_name(reference)
    raw_value = environment.get(variable_name)

    if raw_value is None:
        raise ConnectorConfigurationError(
            f"Connection reference '{reference}' was not found. "
            f"Expected environment variable '{variable_name}'."
        )

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ConnectorConfigurationError(
            f"Environment variable '{variable_name}' "
            "must contain a valid JSON object"
        ) from exc

    if not isinstance(parsed, dict):
        raise ConnectorConfigurationError(
            f"Environment variable '{variable_name}' "
            "must contain a JSON object"
        )

    return parsed