"""Metadata helpers shared across DataForge pipeline stages."""

from __future__ import annotations

import hashlib
import json

import pandas as pd


def dataframe_schema_hash(
    frame: pd.DataFrame,
) -> str:
    """Return a deterministic hash of dataframe column metadata."""

    schema = [
        {
            "name": str(column),
            "dtype": str(
                frame[column].dtype
            ),
        }
        for column in frame.columns
    ]

    return hashlib.sha256(
        json.dumps(
            schema,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()