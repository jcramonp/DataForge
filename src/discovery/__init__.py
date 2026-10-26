"""DataForge generic schema discovery and data profiling package."""

from __future__ import annotations

from typing import Any

from src.discovery.engine import (
    generate_contract_schema,
    infer_data_type,
    profile_column,
    profile_dataframe,
)
from src.discovery.reporter import (
    save_profile_reports,
    to_json,
    to_markdown,
)


def profile_contract_dataset(*args: Any, **kwargs: Any):
    """Lazy compatibility wrapper for contract dataset profiling."""
    from src.discovery.run_profiling import (
        profile_contract_dataset as implementation,
    )

    return implementation(*args, **kwargs)


def profile_contract(*args: Any, **kwargs: Any):
    """Lazy compatibility wrapper for contract profiling."""
    from src.discovery.run_profiling import (
        profile_contract as implementation,
    )

    return implementation(*args, **kwargs)


__all__ = [
    "infer_data_type",
    "profile_column",
    "profile_dataframe",
    "generate_contract_schema",
    "to_markdown",
    "to_json",
    "save_profile_reports",
    "profile_contract",
    "profile_contract_dataset",
]
