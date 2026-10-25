"""DataForge generic schema discovery and data profiling package."""

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
from src.discovery.run_profiling import (
    profile_contract,
    profile_contract_dataset,
)

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
