"""Generic schema discovery and data profiling engine for DataForge.

Inspects unknown datasets and generates technical facts and statistics
independent of any specific business domain or client.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from src.contracts.models import DataType


# Regex patterns for ISO-like dates and timestamps
_DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_REGEX = re.compile(
    r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$"
)


def _is_json_string(value: str) -> bool:
    """Check if a string represents valid JSON object or array."""
    stripped = value.strip()
    if not ((stripped.startswith("{") and stripped.endswith("}")) or
            (stripped.startswith("[") and stripped.endswith("]"))):
        return False
    try:
        json.loads(stripped)
        return True
    except (ValueError, TypeError):
        return False


def infer_data_type(series: pd.Series) -> DataType:
    """Infer the DataForge DataType of a Pandas Series without domain assumptions.

    Evaluates non-null values against supported types:
    boolean -> integer -> float -> date -> datetime -> json -> string.
    """
    non_null = series.dropna()
    if len(non_null) == 0:
        return DataType.STRING

    # 1. Boolean check
    if pd.api.types.is_bool_dtype(series):
        return DataType.BOOLEAN

    if non_null.apply(lambda v: isinstance(v, (bool, np.bool_))).all():
        return DataType.BOOLEAN

    # Check for string representations of boolean if all values match
    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        lowered = non_null.astype(str).str.strip().str.lower()
        if lowered.isin({"true", "false"}).all():
            return DataType.BOOLEAN

    # 2. Native Datetime check
    if pd.api.types.is_datetime64_any_dtype(series):
        # If all times are midnight (00:00:00) without tz or date-only, could be date
        try:
            time_parts = series.dt.time.dropna()
            if len(time_parts) > 0 and (time_parts == datetime.min.time()).all():
                return DataType.DATE
        except Exception:
            pass
        return DataType.DATETIME

    # 3. Numeric checks (integer vs float)
    if pd.api.types.is_integer_dtype(series):
        return DataType.INTEGER

    if pd.api.types.is_float_dtype(series):
        # Check if float values are actually whole numbers (e.g. integer column with NaNs)
        try:
            if (non_null % 1 == 0).all():
                # Verify values fit in standard integer ranges
                if non_null.min() >= -9223372036854775808 and non_null.max() <= 9223372036854775807:
                    return DataType.INTEGER
        except Exception:
            pass
        return DataType.FLOAT

    # 4. String/Object based type detection
    str_values = non_null.astype(str).str.strip()

    # Try numeric conversion from strings
    try:
        numeric_converted = pd.to_numeric(str_values, errors="raise")
        if (numeric_converted % 1 == 0).all() and not str_values.str.startswith("0").any() or (str_values == "0").all():
            return DataType.INTEGER
        return DataType.FLOAT
    except (ValueError, TypeError, OverflowError):
        pass

    # Try JSON detection
    if str_values.apply(_is_json_string).all():
        return DataType.JSON

    # Try Date / Datetime pattern detection
    if str_values.apply(lambda s: bool(_DATE_REGEX.match(s))).all():
        try:
            pd.to_datetime(str_values, format="mixed", errors="raise")
            return DataType.DATE
        except Exception:
            pass

    if str_values.apply(lambda s: bool(_DATETIME_REGEX.match(s))).all():
        try:
            pd.to_datetime(str_values, format="mixed", errors="raise", utc=True)
            return DataType.DATETIME
        except Exception:
            pass

    return DataType.STRING


def profile_column(
    series: pd.Series,
    inferred_type: DataType | None = None,
    sample_size: int = 5,
) -> dict[str, Any]:
    """Profile a single column, generating factual technical metrics."""
    data_type = inferred_type or infer_data_type(series)
    total_count = len(series)
    non_null = series.dropna()
    null_count = int(series.isna().sum())
    null_percentage = round(float((null_count / total_count * 100)), 2) if total_count > 0 else 0.0

    distinct_count = int(non_null.nunique())
    non_null_count = len(non_null)
    uniqueness_ratio = (
        round(float(distinct_count / non_null_count), 4) if non_null_count > 0 else 0.0
    )

    # Sample values (up to sample_size unique non-null samples, JSON-safe)
    unique_samples = non_null.drop_duplicates().head(sample_size).tolist()
    sample_values = [
        val.isoformat() if isinstance(val, (datetime, date)) else val
        for val in unique_samples
    ]

    profile: dict[str, Any] = {
        "name": str(series.name),
        "inferred_type": data_type.value,
        "physical_type": str(series.dtype),
        "total_count": total_count,
        "null_count": null_count,
        "null_percentage": null_percentage,
        "distinct_count": distinct_count,
        "uniqueness_ratio": uniqueness_ratio,
        "sample_values": sample_values,
        "stats": {},
    }

    if non_null_count == 0:
        return profile

    # Numeric statistics
    if data_type in {DataType.INTEGER, DataType.FLOAT}:
        try:
            numeric_series = pd.to_numeric(non_null, errors="coerce").dropna()
            if len(numeric_series) > 0:
                stats: dict[str, Any] = {
                    "min": float(numeric_series.min()) if data_type == DataType.FLOAT else int(numeric_series.min()),
                    "max": float(numeric_series.max()) if data_type == DataType.FLOAT else int(numeric_series.max()),
                    "mean": round(float(numeric_series.mean()), 4),
                    "median": float(numeric_series.median()) if data_type == DataType.FLOAT else int(numeric_series.median()),
                    "zeros_count": int((numeric_series == 0).sum()),
                    "negative_count": int((numeric_series < 0).sum()),
                }
                if len(numeric_series) > 1:
                    stats["std"] = round(float(numeric_series.std()), 4)
                else:
                    stats["std"] = 0.0
                profile["stats"] = stats
        except Exception:
            pass

    # String statistics
    elif data_type == DataType.STRING:
        try:
            str_series = non_null.astype(str)
            lengths = str_series.str.len()
            profile["stats"] = {
                "min_length": int(lengths.min()),
                "max_length": int(lengths.max()),
                "avg_length": round(float(lengths.mean()), 2),
                "empty_string_count": int((str_series.str.strip() == "").sum()),
            }
        except Exception:
            pass

    # Date / Datetime statistics
    elif data_type in {DataType.DATE, DataType.DATETIME}:
        try:
            parsed_dates = pd.to_datetime(non_null, format="mixed", errors="coerce").dropna()
            if len(parsed_dates) > 0:
                profile["stats"] = {
                    "min_date": parsed_dates.min().isoformat(),
                    "max_date": parsed_dates.max().isoformat(),
                }
        except Exception:
            pass

    return profile


def profile_dataframe(
    df: pd.DataFrame,
    dataset_name: str = "dataset",
    sample_size: int = 5,
) -> dict[str, Any]:
    """Profile an entire DataFrame, generating dataset-level and column-level facts."""
    row_count = len(df)
    col_count = len(df.columns)
    duplicate_rows = int(df.duplicated().sum()) if row_count > 0 else 0
    duplicate_rows_percentage = (
        round(float(duplicate_rows / row_count * 100), 2) if row_count > 0 else 0.0
    )

    try:
        memory_bytes = int(df.memory_usage(deep=True).sum())
    except Exception:
        memory_bytes = 0

    candidate_keys: list[str] = []
    columns_profile: dict[str, Any] = {}

    for column_name in df.columns:
        series = df[column_name]
        col_prof = profile_column(series, sample_size=sample_size)
        columns_profile[str(column_name)] = col_prof

        # A candidate primary key must have 0 nulls and 100% uniqueness (when rows > 0)
        if row_count > 0 and col_prof["null_count"] == 0 and col_prof["distinct_count"] == row_count:
            candidate_keys.append(str(column_name))

    return {
        "dataset_name": dataset_name,
        "row_count": row_count,
        "column_count": col_count,
        "duplicate_rows": duplicate_rows,
        "duplicate_rows_percentage": duplicate_rows_percentage,
        "candidate_keys": candidate_keys,
        "memory_bytes": memory_bytes,
        "columns": columns_profile,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def generate_contract_schema(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Generate a DataForge ColumnConfig schema draft from a DataFrame."""
    schema_fields: list[dict[str, Any]] = []

    for column_name in df.columns:
        series = df[column_name]
        inferred = infer_data_type(series)
        has_nulls = bool(series.isna().any())

        schema_fields.append(
            {
                "name": str(column_name),
                "type": inferred.value,
                "nullable": has_nulls,
                "classification": "internal",
            }
        )

    return schema_fields
