"""Explicit asset-to-asset lineage services for DataForge."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any

import psycopg


ALLOWED_RELATION_TYPES = {
    "derived_from",
    "transformed_from",
    "validated_from",
    "quarantined_from",
    "joined_from",
}


class LineageError(RuntimeError):
    """Base error for DataForge lineage operations."""


class LineageConfigurationError(LineageError):
    """Raised when a lineage relationship is invalid."""


LINEAGE_RESULT_COLUMNS = (
    "asset_id",
    "layer",
    "asset_name",
    "storage_uri",
    "format",
    "row_count",
    "checksum",
    "run_id",
    "run_type",
    "run_status",
    "dataset_version_id",
    "version_label",
    "dataset_code",
    "source_code",
    "project_code",
    "client_code",
    "relation_type",
    "depth",
)


def register_lineage(
    conn: psycopg.Connection,
    parent_asset_id: int,
    child_asset_id: int,
    relation_type: str = "derived_from",
    created_by_run_id: int | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> int:
    """Register one idempotent parent -> child asset lineage edge."""

    if parent_asset_id == child_asset_id:
        raise LineageConfigurationError(
            "An asset cannot be its own lineage parent."
        )

    if relation_type not in ALLOWED_RELATION_TYPES:
        raise LineageConfigurationError(
            f"Unsupported lineage relation type: {relation_type}"
        )

    metadata_json = json.dumps(
        dict(metadata or {}),
        sort_keys=True,
        default=str,
    )

    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO asset_lineage (
                parent_asset_id,
                child_asset_id,
                relation_type,
                created_by_run_id,
                metadata_json
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s::jsonb
            )
            ON CONFLICT (
                parent_asset_id,
                child_asset_id,
                relation_type
            )
            DO UPDATE SET
                created_by_run_id = COALESCE(
                    EXCLUDED.created_by_run_id,
                    asset_lineage.created_by_run_id
                ),
                metadata_json =
                    asset_lineage.metadata_json
                    || EXCLUDED.metadata_json
            RETURNING lineage_id
            """,
            (
                parent_asset_id,
                child_asset_id,
                relation_type,
                created_by_run_id,
                metadata_json,
            ),
        )

        row = cursor.fetchone()

    if row is None:
        raise LineageError(
            "Lineage relationship could not be registered."
        )

    return int(row[0])


def register_lineage_edges(
    conn: psycopg.Connection,
    edges: Iterable[Mapping[str, Any]],
) -> list[int]:
    """Register multiple lineage edges using the same service."""

    lineage_ids: list[int] = []

    for edge in edges:
        lineage_ids.append(
            register_lineage(
                conn=conn,
                parent_asset_id=int(
                    edge["parent_asset_id"]
                ),
                child_asset_id=int(
                    edge["child_asset_id"]
                ),
                relation_type=str(
                    edge.get(
                        "relation_type",
                        "derived_from",
                    )
                ),
                created_by_run_id=(
                    int(edge["created_by_run_id"])
                    if edge.get("created_by_run_id")
                    is not None
                    else None
                ),
                metadata=edge.get("metadata"),
            )
        )

    return lineage_ids


def _lineage_rows(
    rows: list[tuple[Any, ...]],
) -> list[dict[str, Any]]:
    return [
        dict(
            zip(
                LINEAGE_RESULT_COLUMNS,
                row,
                strict=True,
            )
        )
        for row in rows
    ]


def get_upstream_lineage(
    conn: psycopg.Connection,
    asset_id: int,
) -> list[dict[str, Any]]:
    """Return all ancestors of an asset, nearest parents first.

    Recursive traversal is cycle-safe by keeping the visited asset IDs
    in the recursive path.
    """

    with conn.cursor() as cursor:
        cursor.execute(
            """
            WITH RECURSIVE lineage_tree AS (
                SELECT
                    al.parent_asset_id AS asset_id,
                    al.relation_type,
                    1 AS depth,
                    ARRAY[
                        al.child_asset_id,
                        al.parent_asset_id
                    ]::BIGINT[] AS path
                FROM asset_lineage al
                WHERE al.child_asset_id = %s

                UNION ALL

                SELECT
                    al.parent_asset_id AS asset_id,
                    al.relation_type,
                    lt.depth + 1 AS depth,
                    lt.path || al.parent_asset_id
                FROM asset_lineage al
                JOIN lineage_tree lt
                    ON al.child_asset_id = lt.asset_id
                WHERE NOT (
                    al.parent_asset_id = ANY(lt.path)
                )
            )
            SELECT
                da.asset_id,
                da.layer,
                da.asset_name,
                da.storage_uri,
                da.format,
                da.row_count,
                da.checksum,
                pr.run_id,
                pr.run_type,
                pr.status AS run_status,
                dv.dataset_version_id,
                dv.version_label,
                d.dataset_code,
                ds.source_code,
                p.project_code,
                c.client_code,
                lt.relation_type,
                lt.depth
            FROM lineage_tree lt
            JOIN data_asset da
                ON da.asset_id = lt.asset_id
            JOIN pipeline_run pr
                ON pr.run_id = da.run_id
            JOIN dataset_version dv
                ON dv.dataset_version_id =
                   pr.dataset_version_id
            JOIN dataset d
                ON d.dataset_id = dv.dataset_id
            JOIN data_source ds
                ON ds.source_id = d.source_id
            JOIN project p
                ON p.project_id = ds.project_id
            JOIN client c
                ON c.client_id = p.client_id
            ORDER BY
                lt.depth,
                da.asset_id
            """,
            (asset_id,),
        )

        rows = cursor.fetchall()

    return _lineage_rows(rows)


def get_downstream_lineage(
    conn: psycopg.Connection,
    asset_id: int,
) -> list[dict[str, Any]]:
    """Return all descendants of an asset, nearest children first."""

    with conn.cursor() as cursor:
        cursor.execute(
            """
            WITH RECURSIVE lineage_tree AS (
                SELECT
                    al.child_asset_id AS asset_id,
                    al.relation_type,
                    1 AS depth,
                    ARRAY[
                        al.parent_asset_id,
                        al.child_asset_id
                    ]::BIGINT[] AS path
                FROM asset_lineage al
                WHERE al.parent_asset_id = %s

                UNION ALL

                SELECT
                    al.child_asset_id AS asset_id,
                    al.relation_type,
                    lt.depth + 1 AS depth,
                    lt.path || al.child_asset_id
                FROM asset_lineage al
                JOIN lineage_tree lt
                    ON al.parent_asset_id = lt.asset_id
                WHERE NOT (
                    al.child_asset_id = ANY(lt.path)
                )
            )
            SELECT
                da.asset_id,
                da.layer,
                da.asset_name,
                da.storage_uri,
                da.format,
                da.row_count,
                da.checksum,
                pr.run_id,
                pr.run_type,
                pr.status AS run_status,
                dv.dataset_version_id,
                dv.version_label,
                d.dataset_code,
                ds.source_code,
                p.project_code,
                c.client_code,
                lt.relation_type,
                lt.depth
            FROM lineage_tree lt
            JOIN data_asset da
                ON da.asset_id = lt.asset_id
            JOIN pipeline_run pr
                ON pr.run_id = da.run_id
            JOIN dataset_version dv
                ON dv.dataset_version_id =
                   pr.dataset_version_id
            JOIN dataset d
                ON d.dataset_id = dv.dataset_id
            JOIN data_source ds
                ON ds.source_id = d.source_id
            JOIN project p
                ON p.project_id = ds.project_id
            JOIN client c
                ON c.client_id = p.client_id
            ORDER BY
                lt.depth,
                da.asset_id
            """,
            (asset_id,),
        )

        rows = cursor.fetchall()

    return _lineage_rows(rows)


def get_direct_parents(
    conn: psycopg.Connection,
    asset_id: int,
) -> list[int]:
    """Return the immediate parent asset IDs."""

    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT parent_asset_id
            FROM asset_lineage
            WHERE child_asset_id = %s
            ORDER BY parent_asset_id
            """,
            (asset_id,),
        )

        rows = cursor.fetchall()

    return [
        int(row[0])
        for row in rows
    ]


def get_direct_children(
    conn: psycopg.Connection,
    asset_id: int,
) -> list[int]:
    """Return the immediate child asset IDs."""

    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT child_asset_id
            FROM asset_lineage
            WHERE parent_asset_id = %s
            ORDER BY child_asset_id
            """,
            (asset_id,),
        )

        rows = cursor.fetchall()

    return [
        int(row[0])
        for row in rows
    ]