"""Build safe row-level quarantine inspection records."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd

from src.contracts.models import (
    Classification,
    DatasetConfig,
    Severity,
)
from src.quality.quality_generic import compute_invalid_mask


SENSITIVE_CLASSIFICATIONS = {
    Classification.CONFIDENTIAL,
    Classification.RESTRICTED,
}


def _json_safe(value: Any) -> Any:
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()

    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass

    return value


def _record_identifier(
    row: pd.Series,
    dataset: DatasetConfig,
    row_number: int,
) -> str:
    values = []

    for key in dataset.keys.primary:
        value = row.get(key)

        try:
            missing = pd.isna(value)
        except (TypeError, ValueError):
            missing = value is None

        if missing:
            return f"row-{row_number}"

        values.append(str(value))

    if values:
        return "|".join(values)

    return f"row-{row_number}"


def _observed_value(
    row: pd.Series,
    dataset: DatasetConfig,
    column_name: str,
) -> Any:
    column = next(
        (
            item
            for item in dataset.schema_
            if item.name == column_name
        ),
        None,
    )

    if (
        column is not None
        and column.classification
        in SENSITIVE_CLASSIFICATIONS
    ):
        return "<REDACTED>"

    return _json_safe(row.get(column_name))


def build_quarantine_records(
    frame: pd.DataFrame,
    dataset: DatasetConfig,
    *,
    asset_id: int,
    run_id: int,
    quarantined_at: datetime,
) -> list[dict[str, Any]]:
    """Reconstruct critical row violations using the persisted contract."""

    records: list[dict[str, Any]] = []

    for rule in dataset.quality.rules:
        if rule.severity != Severity.CRITICAL:
            continue

        if rule.column not in frame.columns:
            continue

        invalid = compute_invalid_mask(
            frame[rule.column],
            rule,
        )

        for position, is_invalid in enumerate(
            invalid.tolist(),
            start=1,
        ):
            if not bool(is_invalid):
                continue

            row = frame.iloc[position - 1]

            records.append(
                {
                    "quarantine_id": (
                        f"{asset_id}:{position}:{rule.name}"
                    ),
                    "dataset": dataset.code,
                    "record_id": _record_identifier(
                        row,
                        dataset,
                        position,
                    ),
                    "rule_violated": rule.name,
                    "rule_type": rule.rule.value,
                    "severity": rule.severity.value,
                    "failed_field": rule.column,
                    "observed_value": _observed_value(
                        row,
                        dataset,
                        rule.column,
                    ),
                    "reason": (
                        "Record failed critical contract "
                        f"quality rule '{rule.name}'"
                    ),
                    "run_id": run_id,
                    "asset_id": asset_id,
                    "quarantined_at": (
                        quarantined_at.isoformat()
                    ),
                }
            )

    return records
