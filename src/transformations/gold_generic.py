"""Generic, contract-driven Gold analytical transformation engine for DataForge.

Executes declarative transformation plans (join, derive, select, drop, filter,
rename, group_by, aggregate) across validated datasets without client-specific scripts.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from src.contracts.models import (
    AggregationConfig,
    AggregationFunction,
    DerivedOperation,
    FilterOperator,
    GoldConfig,
    GoldOperation,
    GoldStepConfig,
    JoinHow,
)

logger = logging.getLogger(__name__)


def execute_select(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Select only the specified columns in order."""
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"Select operation references unknown columns: {missing}")
    return df[columns].copy()


def execute_drop(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Drop specified columns if they exist."""
    existing = [c for c in columns if c in df.columns]
    return df.drop(columns=existing).copy()


def execute_rename(df: pd.DataFrame, from_col: str, to_col: str) -> pd.DataFrame:
    """Rename a single column from_col -> to_col."""
    if from_col not in df.columns:
        raise ValueError(f"Rename operation: column '{from_col}' not found in DataFrame")
    return df.rename(columns={from_col: to_col}).copy()


def execute_filter(
    df: pd.DataFrame,
    column: str,
    operator: FilterOperator,
    value: Any,
) -> pd.DataFrame:
    """Filter rows based on operator and threshold value."""
    if column not in df.columns:
        raise ValueError(f"Filter operation: column '{column}' not found in DataFrame")

    series = df[column]

    if operator == FilterOperator.EQUAL:
        mask = series == value
    elif operator == FilterOperator.NOT_EQUAL:
        mask = series != value
    elif operator == FilterOperator.GREATER_THAN:
        mask = pd.to_numeric(series, errors="coerce") > value
    elif operator == FilterOperator.GREATER_THAN_OR_EQUAL:
        mask = pd.to_numeric(series, errors="coerce") >= value
    elif operator == FilterOperator.LESS_THAN:
        mask = pd.to_numeric(series, errors="coerce") < value
    elif operator == FilterOperator.LESS_THAN_OR_EQUAL:
        mask = pd.to_numeric(series, errors="coerce") <= value
    elif operator == FilterOperator.IN:
        allowed = value if isinstance(value, (list, tuple, set)) else [value]
        mask = series.isin(allowed)
    elif operator == FilterOperator.NOT_IN:
        disallowed = value if isinstance(value, (list, tuple, set)) else [value]
        mask = ~series.isin(disallowed)
    else:
        raise ValueError(f"Unsupported filter operator: {operator}")

    return df.loc[mask.fillna(False)].copy()


def execute_join(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    left_on: list[str],
    right_on: list[str],
    how: JoinHow = JoinHow.INNER,
) -> pd.DataFrame:
    """Join left and right DataFrames on specified keys, resolving duplicate columns."""
    for col in left_on:
        if col not in left_df.columns:
            raise ValueError(f"Join operation: left key '{col}' not found in left DataFrame")

    for col in right_on:
        if col not in right_df.columns:
            raise ValueError(f"Join operation: right key '{col}' not found in right DataFrame")

    how_str = how.value if hasattr(how, "value") else str(how)

    if left_on == right_on:
        overlap = [c for c in right_df.columns if c in left_df.columns and c not in left_on]
        joined = pd.merge(
            left_df,
            right_df,
            on=left_on,
            how=how_str,
            suffixes=("", "_right_dup"),
        )
        right_dup_cols = [f"{c}_right_dup" for c in overlap]
        if right_dup_cols:
            joined = joined.drop(columns=right_dup_cols)
        return joined
    else:
        overlap = [c for c in right_df.columns if c in left_df.columns]
        joined = pd.merge(
            left_df,
            right_df,
            left_on=left_on,
            right_on=right_on,
            how=how_str,
            suffixes=("", "_right_dup"),
        )
        right_dup_cols = [f"{c}_right_dup" for c in overlap if c not in right_on]
        if right_dup_cols:
            joined = joined.drop(columns=right_dup_cols)
        return joined


def execute_derive(
    df: pd.DataFrame,
    operation: DerivedOperation,
    operands: list[str],
    output_column: str,
) -> pd.DataFrame:
    """Calculate an arithmetic derived column across specified operand columns."""
    for op in operands:
        if op not in df.columns:
            raise ValueError(f"Derive operation: operand column '{op}' not found in DataFrame")

    result = df.copy()
    acc = pd.to_numeric(result[operands[0]], errors="coerce")

    for next_col in operands[1:]:
        next_series = pd.to_numeric(result[next_col], errors="coerce")

        if operation == DerivedOperation.ADD:
            acc = acc + next_series
        elif operation == DerivedOperation.SUBTRACT:
            acc = acc - next_series
        elif operation == DerivedOperation.MULTIPLY:
            acc = acc * next_series
        elif operation == DerivedOperation.DIVIDE:
            acc = acc / next_series.replace(0, np.nan)
        else:
            raise ValueError(f"Unsupported derive operation: {operation}")

    result[output_column] = acc
    return result


def execute_aggregate(
    df: pd.DataFrame,
    group_by_columns: list[str] | None,
    aggregations: list[AggregationConfig],
) -> pd.DataFrame:
    """Perform group-by aggregations using declared alias mappings."""
    alias_map = {}

    for agg in aggregations:
        col = agg.column
        if col not in df.columns:
            raise ValueError(f"Aggregate operation: column '{col}' not found in DataFrame")

        fn = agg.function
        if fn == AggregationFunction.SUM:
            agg_func = "sum"
        elif fn == AggregationFunction.AVG:
            agg_func = "mean"
        elif fn == AggregationFunction.MIN:
            agg_func = "min"
        elif fn == AggregationFunction.MAX:
            agg_func = "max"
        elif fn == AggregationFunction.COUNT:
            agg_func = "count"
        elif fn == AggregationFunction.NUNIQUE:
            agg_func = "nunique"
        else:
            agg_func = "sum"

        alias_map[agg.alias] = (col, agg_func)

    if group_by_columns:
        for grp in group_by_columns:
            if grp not in df.columns:
                raise ValueError(f"GroupBy operation: group column '{grp}' not found in DataFrame")

        grouped = df.groupby(group_by_columns, as_index=False)
        return grouped.agg(
            **{alias: pd.NamedAgg(column=col, aggfunc=fn) for alias, (col, fn) in alias_map.items()}
        )
    else:
        res = {
            alias: [df[col].agg(fn)]
            for alias, (col, fn) in alias_map.items()
        }
        return pd.DataFrame(res)


def execute_gold_step(
    current_df: pd.DataFrame,
    step: GoldStepConfig,
    datasets_by_code: dict[str, pd.DataFrame],
    pending_group_by: list[str] | None = None,
) -> tuple[pd.DataFrame, list[str] | None]:
    """Execute a single declarative step from a Gold plan."""
    op = step.operation

    if op == GoldOperation.SELECT:
        return execute_select(current_df, step.columns or []), pending_group_by

    elif op == GoldOperation.DROP:
        return execute_drop(current_df, step.columns or []), pending_group_by

    elif op == GoldOperation.RENAME:
        if not step.from_column or not step.to_column:
            raise ValueError("Rename requires 'from' and 'to' columns")
        return execute_rename(current_df, step.from_column, step.to_column), pending_group_by

    elif op == GoldOperation.FILTER:
        if not step.column or not step.operator or step.value is None:
            raise ValueError("Filter requires 'column', 'operator' and 'value'")
        return execute_filter(current_df, step.column, step.operator, step.value), pending_group_by

    elif op == GoldOperation.JOIN:
        if not step.right_dataset or not step.left_on or not step.right_on:
            raise ValueError("Join requires 'right_dataset', 'left_on' and 'right_on'")

        if step.right_dataset not in datasets_by_code:
            raise ValueError(
                f"Join operation: dataset '{step.right_dataset}' not found in available validated datasets"
            )

        right_df = datasets_by_code[step.right_dataset]
        joined = execute_join(
            left_df=current_df,
            right_df=right_df,
            left_on=step.left_on,
            right_on=step.right_on,
            how=step.how,
        )
        return joined, pending_group_by

    elif op == GoldOperation.DERIVE:
        if not step.derived_operation or not step.operands or not step.output_column:
            raise ValueError("Derive requires 'derived_operation', 'operands' and 'output_column'")
        derived = execute_derive(
            current_df,
            operation=step.derived_operation,
            operands=step.operands,
            output_column=step.output_column,
        )
        return derived, pending_group_by

    elif op == GoldOperation.GROUP_BY:
        return current_df, step.columns

    elif op == GoldOperation.AGGREGATE:
        if not step.aggregations:
            raise ValueError("Aggregate requires 'aggregations'")
        aggregated = execute_aggregate(
            current_df,
            group_by_columns=pending_group_by,
            aggregations=step.aggregations,
        )
        return aggregated, None

    return current_df, pending_group_by


def build_gold_dataset_from_plan(
    gold_config: GoldConfig,
    datasets_by_code: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Build a curated analytical Gold dataset by executing its declared plan."""
    base_code = gold_config.base_dataset
    if base_code not in datasets_by_code:
        raise ValueError(
            f"Base dataset '{base_code}' for Gold '{gold_config.code}' not found in provided datasets"
        )

    current_df = datasets_by_code[base_code].copy()
    pending_group_by: list[str] | None = None

    for idx, step in enumerate(gold_config.plan):
        logger.debug(
            "Executing Gold step %d (%s) on dataset '%s'",
            idx + 1,
            step.operation.value,
            gold_config.code,
        )
        current_df, pending_group_by = execute_gold_step(
            current_df=current_df,
            step=step,
            datasets_by_code=datasets_by_code,
            pending_group_by=pending_group_by,
        )

    return current_df
