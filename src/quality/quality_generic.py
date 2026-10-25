"""Generic Quality Gate engine for DataForge.

Evaluates declarative quality rules using deterministic pandas masks and
Great Expectations, partitioning records into Validated Silver and Quarantine
based on rule severity.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import pandas as pd

from src.contracts.models import QualityRuleConfig, QualityRuleType, Severity

logger = logging.getLogger(__name__)


def compute_invalid_mask(series: pd.Series, rule: QualityRuleConfig) -> pd.Series:
    """Compute boolean mask where True indicates that a row FAILS the rule."""
    rule_type = rule.rule
    allow_null = rule.allow_null

    # 1. NOT_NULL
    if rule_type == QualityRuleType.NOT_NULL:
        return series.isna()

    # 2. UNIQUE
    elif rule_type == QualityRuleType.UNIQUE:
        # Flag duplicate occurrences (excluding nulls if allow_null is True)
        duplicated = series.duplicated(keep=False)
        if allow_null:
            return duplicated & series.notna()
        return duplicated | series.isna()

    # 3. GREATER_THAN / GREATER_THAN_OR_EQUAL
    elif rule_type == QualityRuleType.GREATER_THAN:
        threshold = rule.value
        numeric_series = pd.to_numeric(series, errors="coerce")
        invalid = numeric_series <= threshold
        if allow_null:
            return invalid & series.notna()
        return invalid | series.isna()

    elif rule_type == QualityRuleType.GREATER_THAN_OR_EQUAL:
        threshold = rule.value
        numeric_series = pd.to_numeric(series, errors="coerce")
        invalid = numeric_series < threshold
        if allow_null:
            return invalid & series.notna()
        return invalid | series.isna()

    # 4. LESS_THAN / LESS_THAN_OR_EQUAL
    elif rule_type == QualityRuleType.LESS_THAN:
        threshold = rule.value
        numeric_series = pd.to_numeric(series, errors="coerce")
        invalid = numeric_series >= threshold
        if allow_null:
            return invalid & series.notna()
        return invalid | series.isna()

    elif rule_type == QualityRuleType.LESS_THAN_OR_EQUAL:
        threshold = rule.value
        numeric_series = pd.to_numeric(series, errors="coerce")
        invalid = numeric_series > threshold
        if allow_null:
            return invalid & series.notna()
        return invalid | series.isna()

    # 5. BETWEEN
    elif rule_type == QualityRuleType.BETWEEN:
        min_val = rule.min_value
        max_val = rule.max_value
        numeric_series = pd.to_numeric(series, errors="coerce")
        invalid = (numeric_series < min_val) | (numeric_series > max_val)
        if allow_null:
            return invalid & series.notna()
        return invalid | series.isna()

    # 6. ALLOWED_VALUES
    elif rule_type == QualityRuleType.ALLOWED_VALUES:
        allowed = set(rule.values or [])
        invalid = ~series.isin(allowed)
        if allow_null:
            return invalid & series.notna()
        return invalid | series.isna()

    # 7. REGEX
    elif rule_type == QualityRuleType.REGEX:
        pattern = rule.pattern or ".*"
        str_series = series.astype("string")
        matches = str_series.str.contains(pattern, regex=True, na=False)
        invalid = ~matches
        if allow_null:
            return invalid & series.notna()
        return invalid | series.isna()

    return pd.Series(False, index=series.index)


def _build_gx_expectation(rule: QualityRuleConfig):
    """Attempt to construct an equivalent Great Expectations expectation if available."""
    try:
        import great_expectations as gx

        col = rule.column
        mostly = rule.mostly
        rule_type = rule.rule

        if rule_type == QualityRuleType.NOT_NULL:
            return gx.expectations.ExpectColumnValuesToNotBeNull(column=col, mostly=mostly)

        elif rule_type == QualityRuleType.UNIQUE:
            return gx.expectations.ExpectColumnValuesToBeUnique(column=col, mostly=mostly)

        elif rule_type == QualityRuleType.BETWEEN:
            return gx.expectations.ExpectColumnValuesToBeBetween(
                column=col,
                min_value=rule.min_value,
                max_value=rule.max_value,
                mostly=mostly,
            )

        elif rule_type == QualityRuleType.ALLOWED_VALUES:
            return gx.expectations.ExpectColumnValuesToBeInSet(
                column=col,
                value_set=rule.values or [],
                mostly=mostly,
            )

        elif rule_type == QualityRuleType.REGEX:
            return gx.expectations.ExpectColumnValuesToMatchRegex(
                column=col,
                regex=rule.pattern or ".*",
                mostly=mostly,
            )

        elif rule_type in {QualityRuleType.GREATER_THAN, QualityRuleType.GREATER_THAN_OR_EQUAL}:
            return gx.expectations.ExpectColumnValuesToBeBetween(
                column=col,
                min_value=rule.value,
                strict_min=(rule_type == QualityRuleType.GREATER_THAN),
                mostly=mostly,
            )

        elif rule_type in {QualityRuleType.LESS_THAN, QualityRuleType.LESS_THAN_OR_EQUAL}:
            return gx.expectations.ExpectColumnValuesToBeBetween(
                column=col,
                max_value=rule.value,
                strict_max=(rule_type == QualityRuleType.LESS_THAN),
                mostly=mostly,
            )
    except Exception as exc:
        logger.debug("Great Expectations expectation creation skipped: %s", exc)

    return None


def evaluate_quality_rules(
    frame: pd.DataFrame,
    rules: list[QualityRuleConfig],
    dataset_code: str = "dataset",
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    """Evaluate quality rules, separating Validated Silver and Quarantine.

    - Rules with severity 'critical' route failing rows to Quarantine.
    - Rules with severity 'warning' are evaluated and recorded without routing to Quarantine.
    """
    total_rows = len(frame)
    quarantine_mask = pd.Series(False, index=frame.index)
    results: list[dict[str, Any]] = []

    # Optional GX context setup for batch evaluation
    gx_batch = None
    try:
        import great_expectations as gx

        os.environ.setdefault("GX_ANALYTICS_ENABLED", "false")
        context = gx.get_context(mode="ephemeral")
        datasource = context.data_sources.add_pandas(f"df_{dataset_code}_pandas")
        asset = datasource.add_dataframe_asset(name=f"df_{dataset_code}_asset")
        definition = asset.add_batch_definition_whole_dataframe("whole_dataframe")
        gx_batch = definition.get_batch(batch_parameters={"dataframe": frame})
    except Exception:
        gx_batch = None

    for rule in rules:
        col = rule.column
        if col not in frame.columns:
            logger.warning("Quality rule '%s' references missing column '%s'", rule.name, col)
            continue

        invalid_mask = compute_invalid_mask(frame[col], rule)
        failed_rows = int(invalid_mask.sum())
        failure_pct = round(float(failed_rows / total_rows * 100.0), 4) if total_rows > 0 else 0.0

        # Try evaluating with Great Expectations
        gx_success = None
        if gx_batch is not None:
            expectation = _build_gx_expectation(rule)
            if expectation is not None:
                try:
                    validation = gx_batch.validate(expectation)
                    gx_success = bool(validation.success)
                except Exception:
                    gx_success = None

        if gx_success is None:
            # Fallback to mostly threshold
            pass_ratio = (total_rows - failed_rows) / total_rows if total_rows > 0 else 1.0
            gx_success = pass_ratio >= rule.mostly

        # Critical rules trigger quarantine routing
        if rule.severity == Severity.CRITICAL:
            quarantine_mask |= invalid_mask

        status = "pass" if (failed_rows == 0 or gx_success) else "fail"

        results.append(
            {
                "rule_name": rule.name,
                "rule_type": rule.rule.value,
                "column": rule.column,
                "severity": rule.severity.value,
                "status": status,
                "failed_rows": failed_rows,
                "failure_percentage": failure_pct,
                "gx_success": gx_success,
            }
        )

    validated_frame = frame.loc[~quarantine_mask].copy()
    quarantine_frame = frame.loc[quarantine_mask].copy()

    return validated_frame, quarantine_frame, results
