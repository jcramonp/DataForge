"""Generic Silver transformation engine for DataForge.

Applies declarative, contract-driven transformations to raw/Bronze datasets
without client-specific branching or hardcoded domain logic.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.contracts.models import (
    DataType,
    DatasetConfig,
    TransformationConfig,
    TransformationOperation,
)

logger = logging.getLogger(__name__)


def apply_trim(series: pd.Series) -> pd.Series:
    """Trim leading and trailing whitespace from string values while preserving nulls."""
    return series.astype("string").str.strip()


def apply_lower(series: pd.Series) -> pd.Series:
    """Convert string values to lowercase while preserving nulls."""
    return series.astype("string").str.lower()


def apply_upper(series: pd.Series) -> pd.Series:
    """Convert string values to uppercase while preserving nulls."""
    return series.astype("string").str.upper()


def apply_cast(series: pd.Series, target_type: DataType) -> pd.Series:
    """Cast a Series into the specified DataForge DataType using nullable types."""
    if target_type == DataType.STRING:
        return series.astype("string")

    elif target_type == DataType.INTEGER:
        return pd.to_numeric(series, errors="coerce").astype("Int64")

    elif target_type == DataType.FLOAT:
        return pd.to_numeric(series, errors="coerce").astype("Float64")

    elif target_type == DataType.BOOLEAN:
        if pd.api.types.is_bool_dtype(series):
            return series.astype("boolean")
        # Handle string or numeric boolean conversions
        def _parse_bool(val: Any) -> bool | None:
            if pd.isna(val) or val is None:
                return None
            if isinstance(val, bool):
                return val
            s = str(val).strip().lower()
            if s in {"true", "t", "1", "1.0", "yes", "y"}:
                return True
            if s in {"false", "f", "0", "0.0", "no", "n"}:
                return False
            return None

        return series.map(_parse_bool).astype("boolean")

    elif target_type in {DataType.DATE, DataType.DATETIME}:
        return pd.to_datetime(series, format="mixed", errors="coerce", utc=True)

    elif target_type == DataType.JSON:
        return series

    return series


def apply_transformations(
    df: pd.DataFrame,
    transformations: list[TransformationConfig],
) -> pd.DataFrame:
    """Apply a sequential list of declarative transformations to a DataFrame."""
    result = df.copy()

    for transformation in transformations:
        op = transformation.operation

        if op == TransformationOperation.TRIM:
            if transformation.column in result.columns:
                result[transformation.column] = apply_trim(result[transformation.column])

        elif op == TransformationOperation.LOWER:
            if transformation.column in result.columns:
                result[transformation.column] = apply_lower(result[transformation.column])

        elif op == TransformationOperation.UPPER:
            if transformation.column in result.columns:
                result[transformation.column] = apply_upper(result[transformation.column])

        elif op == TransformationOperation.CAST:
            if transformation.column in result.columns and transformation.target_type is not None:
                result[transformation.column] = apply_cast(
                    result[transformation.column],
                    transformation.target_type,
                )

        elif op == TransformationOperation.RENAME:
            from_col = transformation.from_column
            to_col = transformation.to_column
            if from_col and to_col and from_col in result.columns:
                result = result.rename(columns={from_col: to_col})

    return result


def transform_dataset(
    bronze_frame: pd.DataFrame,
    dataset: DatasetConfig,
) -> pd.DataFrame:
    """Transform a Bronze DataFrame into baseline Silver using contract rules."""
    transformations = dataset.silver.transformations
    transformed = apply_transformations(bronze_frame, transformations)

    if len(transformed) != len(bronze_frame):
        raise RuntimeError(
            f"Silver transformation unexpectedly changed row count for '{dataset.code}': "
            f"{len(bronze_frame)} -> {len(transformed)}"
        )

    return transformed
