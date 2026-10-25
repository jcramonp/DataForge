"""Loading and schema-export utilities for DataForge contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from src.contracts.models import DataForgeContract


SUPPORTED_EXTENSIONS = {".yaml", ".yml", ".json"}


def _read_raw_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Contract file not found: {path}"
        )

    suffix = path.suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported contract format '{suffix}'. "
            "Supported formats: .yaml, .yml, .json"
        )

    with path.open("r", encoding="utf-8") as handle:
        if suffix in {".yaml", ".yml"}:
            raw = yaml.safe_load(handle)
        else:
            raw = json.load(handle)

    if not isinstance(raw, dict):
        raise ValueError(
            "The root of a DataForge contract "
            "must be an object/mapping"
        )

    return raw


def load_contract(
    path: str | Path,
) -> DataForgeContract:
    """Load and validate one DataForge configuration contract."""

    contract_path = Path(path)

    raw = _read_raw_config(contract_path)

    return DataForgeContract.model_validate(raw)


def export_json_schema(
    output_path: str | Path,
) -> Path:
    """Export the versioned DataForge contract as JSON Schema."""

    target = Path(output_path)

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    schema = DataForgeContract.model_json_schema(
        by_alias=True
    )

    target.write_text(
        json.dumps(
            schema,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return target