"""Persistent control-plane configuration services for DataForge (#25).

This module owns registration and retrieval of validated executable
DataForge contracts. PostgreSQL is the authoritative configuration store.

Important security rule:
credentials and secrets are never persisted inside contract_json. Contracts
reference credentials through source.connection_reference instead.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import psycopg

from src.contracts.models import DataForgeContract


class ControlPlaneConfigurationError(ValueError):
    """Base error for invalid control-plane configuration operations."""


class ControlPlaneConflictError(ControlPlaneConfigurationError):
    """Raised when metadata identity conflicts with existing ownership."""


class InlineSecretError(ControlPlaneConfigurationError):
    """Raised when a contract attempts to persist an inline credential."""


_SECRET_KEYS = {
    "authorization",
    "proxy_authorization",
    "x_api_key",
    "api_key",
    "apikey",
    "password",
    "passwd",
    "secret",
    "client_secret",
    "access_token",
    "refresh_token",
    "token",
    "private_key",
    "access_key",
    "secret_key",
}


def canonical_contract_payload(
    contract: DataForgeContract,
) -> dict[str, Any]:
    """Return the canonical JSON-compatible representation of a contract."""

    return contract.model_dump(
        mode="json",
        by_alias=True,
        exclude_none=False,
    )


def canonical_contract_json(
    contract: DataForgeContract,
) -> str:
    """Serialize a contract deterministically for hashing and persistence."""

    return json.dumps(
        canonical_contract_payload(contract),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def contract_hash(
    contract: DataForgeContract,
) -> str:
    """Return the stable SHA-256 hash of the canonical contract."""

    return hashlib.sha256(
        canonical_contract_json(contract).encode("utf-8")
    ).hexdigest()


def _normalize_key(key: str) -> str:
    normalized = re.sub(
        r"[^a-z0-9]+",
        "_",
        key.strip().lower(),
    )
    return normalized.strip("_")


def _find_inline_secret_paths(
    value: Any,
    path: str = "contract",
) -> list[str]:
    """Return paths whose keys look like inline credentials.

    Values are deliberately never included in errors or logs.
    """

    found: list[str] = []

    if isinstance(value, dict):
        for raw_key, nested in value.items():
            key = str(raw_key)
            normalized = _normalize_key(key)
            child_path = f"{path}.{key}"

            if normalized in _SECRET_KEYS:
                found.append(child_path)

            found.extend(
                _find_inline_secret_paths(
                    nested,
                    child_path,
                )
            )

    elif isinstance(value, list):
        for index, nested in enumerate(value):
            found.extend(
                _find_inline_secret_paths(
                    nested,
                    f"{path}[{index}]",
                )
            )

    return found


def ensure_no_inline_secrets(
    contract: DataForgeContract,
) -> None:
    """Reject secrets embedded directly in persisted contract configuration."""

    paths = sorted(
        set(
            _find_inline_secret_paths(
                canonical_contract_payload(contract)
            )
        )
    )

    if paths:
        raise InlineSecretError(
            "Inline credentials are not allowed in DataForge contracts. "
            "Use source.connection_reference and DATAFORGE_CONNECTION_* "
            "environment variables instead. Sensitive field(s): "
            + ", ".join(paths)
        )


def _upsert_client(
    conn: psycopg.Connection,
    contract: DataForgeContract,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO client (
                client_code,
                client_name,
                status
            )
            VALUES (%s, %s, 'active')
            ON CONFLICT (client_code)
            DO UPDATE SET
                client_name = EXCLUDED.client_name,
                status = 'active'
            RETURNING client_id
            """,
            (
                contract.client.code,
                contract.client.name,
            ),
        )
        row = cur.fetchone()

    if row is None:
        raise RuntimeError("Client metadata could not be persisted")

    return int(row[0])


def _upsert_project(
    conn: psycopg.Connection,
    contract: DataForgeContract,
    client_id: int,
) -> int:
    """Upsert a project without allowing project ownership to change."""

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO project (
                client_id,
                project_code,
                project_name,
                status
            )
            VALUES (%s, %s, %s, 'active')
            ON CONFLICT (project_code)
            DO UPDATE SET
                project_name = EXCLUDED.project_name,
                status = 'active'
            WHERE project.client_id = EXCLUDED.client_id
            RETURNING project_id
            """,
            (
                client_id,
                contract.project.code,
                contract.project.name,
            ),
        )
        row = cur.fetchone()

    if row is None:
        raise ControlPlaneConflictError(
            "Project code "
            f"'{contract.project.code}' already belongs to another client"
        )

    return int(row[0])


def _upsert_source(
    conn: psycopg.Connection,
    contract: DataForgeContract,
    project_id: int,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO data_source (
                project_id,
                source_code,
                source_type,
                source_name,
                connection_reference,
                active
            )
            VALUES (%s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (
                project_id,
                source_code
            )
            DO UPDATE SET
                source_type = EXCLUDED.source_type,
                source_name = EXCLUDED.source_name,
                connection_reference = EXCLUDED.connection_reference,
                active = TRUE
            RETURNING source_id
            """,
            (
                project_id,
                contract.source.code,
                contract.source.type.value,
                contract.source.name,
                contract.source.connection_reference,
            ),
        )
        row = cur.fetchone()

    if row is None:
        raise RuntimeError("Source metadata could not be persisted")

    return int(row[0])


def _upsert_datasets(
    conn: psycopg.Connection,
    contract: DataForgeContract,
    source_id: int,
) -> list[dict[str, Any]]:
    datasets: list[dict[str, Any]] = []

    with conn.cursor() as cur:
        for dataset in contract.datasets:
            cur.execute(
                """
                INSERT INTO dataset (
                    source_id,
                    dataset_code,
                    dataset_name,
                    logical_entity,
                    classification,
                    owner_name
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (
                    source_id,
                    dataset_code
                )
                DO UPDATE SET
                    dataset_name = EXCLUDED.dataset_name,
                    logical_entity = EXCLUDED.logical_entity,
                    classification = EXCLUDED.classification,
                    owner_name = EXCLUDED.owner_name
                RETURNING dataset_id
                """,
                (
                    source_id,
                    dataset.code,
                    dataset.name,
                    dataset.code,
                    dataset.classification.value,
                    dataset.owner,
                ),
            )

            row = cur.fetchone()

            if row is None:
                raise RuntimeError(
                    "Dataset metadata could not be persisted for "
                    f"'{dataset.code}'"
                )

            datasets.append(
                {
                    "dataset_id": int(row[0]),
                    "dataset_code": dataset.code,
                }
            )

    return datasets


def _lock_source_configuration(
    conn: psycopg.Connection,
    source_id: int,
) -> None:
    """Serialize configuration changes for one source.

    The transaction-scoped PostgreSQL advisory lock prevents concurrent API
    requests for the same source from calculating the same next revision.
    PostgreSQL releases the lock automatically when the transaction ends.
    """

    with conn.cursor() as cur:
        cur.execute(
            "SELECT pg_advisory_xact_lock(%s)",
            (source_id,),
        )


def _persist_contract_revision(
    conn: psycopg.Connection,
    contract: DataForgeContract,
    source_id: int,
    payload_json: str,
    digest: str,
    created_by: str,
) -> dict[str, Any]:
    """Persist or reactivate one immutable logical contract revision."""

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                contract_id,
                revision,
                status
            FROM configuration_contract
            WHERE source_id = %s
              AND contract_hash = %s
            """,
            (
                source_id,
                digest,
            ),
        )
        existing = cur.fetchone()

        if existing is not None:
            contract_id = int(existing[0])
            revision = int(existing[1])
            current_status = str(existing[2])

            if current_status == "active":
                return {
                    "contract_id": contract_id,
                    "revision": revision,
                    "status": "active",
                    "created": False,
                    "reactivated": False,
                }

            cur.execute(
                """
                UPDATE configuration_contract
                SET
                    status = 'archived',
                    archived_at = NOW()
                WHERE source_id = %s
                  AND status = 'active'
                """,
                (source_id,),
            )

            cur.execute(
                """
                UPDATE configuration_contract
                SET
                    status = 'active',
                    activated_at = NOW(),
                    archived_at = NULL
                WHERE contract_id = %s
                """,
                (contract_id,),
            )

            return {
                "contract_id": contract_id,
                "revision": revision,
                "status": "active",
                "created": False,
                "reactivated": True,
            }

        cur.execute(
            """
            SELECT COALESCE(MAX(revision), 0) + 1
            FROM configuration_contract
            WHERE source_id = %s
            """,
            (source_id,),
        )
        revision = int(cur.fetchone()[0])

        cur.execute(
            """
            UPDATE configuration_contract
            SET
                status = 'archived',
                archived_at = NOW()
            WHERE source_id = %s
              AND status = 'active'
            """,
            (source_id,),
        )

        cur.execute(
            """
            INSERT INTO configuration_contract (
                source_id,
                contract_version,
                revision,
                contract_hash,
                contract_json,
                status,
                created_by,
                activated_at
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s::jsonb,
                'active',
                %s,
                NOW()
            )
            RETURNING contract_id
            """,
            (
                source_id,
                contract.contract_version,
                revision,
                digest,
                payload_json,
                created_by,
            ),
        )

        row = cur.fetchone()

    if row is None:
        raise RuntimeError(
            "Configuration contract revision could not be persisted"
        )

    return {
        "contract_id": int(row[0]),
        "revision": revision,
        "status": "active",
        "created": True,
        "reactivated": False,
    }


def register_contract(
    conn: psycopg.Connection,
    contract: DataForgeContract,
    *,
    created_by: str = "api",
    expected_base_hash: str | None = None,
) -> dict[str, Any]:
    """Persist a validated contract and its control-plane identity atomically.

    Re-submitting the exact same contract is idempotent. A changed contract
    creates a new revision and archives the previously active revision.
    """

    ensure_no_inline_secrets(contract)

    payload_json = canonical_contract_json(contract)
    digest = hashlib.sha256(
        payload_json.encode("utf-8")
    ).hexdigest()

    with conn.transaction():
        client_id = _upsert_client(
            conn,
            contract,
        )

        project_id = _upsert_project(
            conn,
            contract,
            client_id,
        )

        source_id = _upsert_source(
            conn,
            contract,
            project_id,
        )

        _lock_source_configuration(
            conn,
            source_id,
        )

        if expected_base_hash is not None:
            active = get_active_contract(
                conn, client_code=contract.client.code,
                project_code=contract.project.code, source_code=contract.source.code,
            )
            if active is None or contract_hash(DataForgeContract.model_validate(active['contract'])) != expected_base_hash:
                raise ControlPlaneConflictError(
                    "Active contract changed; regenerate and review a new proposal"
                )

        datasets = _upsert_datasets(
            conn,
            contract,
            source_id,
        )

        persisted = _persist_contract_revision(
            conn=conn,
            contract=contract,
            source_id=source_id,
            payload_json=payload_json,
            digest=digest,
            created_by=created_by,
        )

    return {
        "client_id": client_id,
        "project_id": project_id,
        "source_id": source_id,
        "contract_id": persisted["contract_id"],
        "contract_version": contract.contract_version,
        "revision": persisted["revision"],
        "contract_hash": digest,
        "status": persisted["status"],
        "created": persisted["created"],
        "reactivated": persisted["reactivated"],
        "datasets": datasets,
    }


def list_clients(
    conn: psycopg.Connection,
) -> list[dict[str, Any]]:
    """Return registered clients and control-plane object counts."""

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                c.client_id,
                c.client_code,
                c.client_name,
                c.status,
                c.created_at,
                COUNT(DISTINCT p.project_id),
                COUNT(DISTINCT ds.source_id),
                COUNT(DISTINCT d.dataset_id)
            FROM client c
            LEFT JOIN project p
                ON p.client_id = c.client_id
            LEFT JOIN data_source ds
                ON ds.project_id = p.project_id
            LEFT JOIN dataset d
                ON d.source_id = ds.source_id
            GROUP BY
                c.client_id,
                c.client_code,
                c.client_name,
                c.status,
                c.created_at
            ORDER BY c.client_code
            """
        )

        rows = cur.fetchall()

    return [
        {
            "client_id": int(row[0]),
            "code": row[1],
            "name": row[2],
            "status": row[3],
            "created_at": row[4],
            "projects_count": int(row[5]),
            "sources_count": int(row[6]),
            "datasets_count": int(row[7]),
        }
        for row in rows
    ]


def list_projects(
    conn: psycopg.Connection,
    *,
    client_code: str | None = None,
) -> list[dict[str, Any]]:
    """Return projects, optionally scoped to one client."""

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                p.project_id,
                p.project_code,
                p.project_name,
                p.status,
                p.created_at,
                c.client_id,
                c.client_code,
                c.client_name,
                COUNT(DISTINCT ds.source_id),
                COUNT(DISTINCT d.dataset_id)
            FROM project p
            JOIN client c
                ON c.client_id = p.client_id
            LEFT JOIN data_source ds
                ON ds.project_id = p.project_id
            LEFT JOIN dataset d
                ON d.source_id = ds.source_id
            WHERE (%s::text IS NULL OR c.client_code = %s)
            GROUP BY
                p.project_id,
                p.project_code,
                p.project_name,
                p.status,
                p.created_at,
                c.client_id,
                c.client_code,
                c.client_name
            ORDER BY c.client_code, p.project_code
            """,
            (
                client_code,
                client_code,
            ),
        )

        rows = cur.fetchall()

    return [
        {
            "project_id": int(row[0]),
            "code": row[1],
            "name": row[2],
            "status": row[3],
            "created_at": row[4],
            "client_id": int(row[5]),
            "client_code": row[6],
            "client_name": row[7],
            "sources_count": int(row[8]),
            "datasets_count": int(row[9]),
        }
        for row in rows
    ]


def list_sources(
    conn: psycopg.Connection,
    *,
    client_code: str | None = None,
    project_code: str | None = None,
) -> list[dict[str, Any]]:
    """Return registered sources with datasets from persisted metadata.

    When an executable contract is active, configuration-level dataset
    information such as schema size is derived from that persisted contract.
    Sources created by older pipeline runs remain visible even when they do
    not yet have an active configuration_contract row.
    """

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                c.client_code,
                c.client_name,
                p.project_code,
                p.project_name,

                ds.source_id,
                ds.source_code,
                ds.source_type,
                ds.source_name,
                ds.connection_reference,
                ds.active,
                ds.created_at,

                acc.contract_id,
                acc.revision,
                acc.contract_json,

                d.dataset_id,
                d.dataset_code,
                d.dataset_name,
                d.classification,
                d.owner_name

            FROM data_source ds

            JOIN project p
                ON p.project_id = ds.project_id

            JOIN client c
                ON c.client_id = p.client_id

            LEFT JOIN active_configuration_contract acc
                ON acc.source_id = ds.source_id

            LEFT JOIN dataset d
                ON d.source_id = ds.source_id

            WHERE
                (%s::text IS NULL OR c.client_code = %s)
                AND (%s::text IS NULL OR p.project_code = %s)

            ORDER BY
                c.client_code,
                p.project_code,
                ds.source_code,
                d.dataset_code
            """,
            (
                client_code,
                client_code,
                project_code,
                project_code,
            ),
        )

        rows = cur.fetchall()

    grouped: dict[int, dict[str, Any]] = {}
    contract_cache: dict[int, DataForgeContract | None] = {}

    for row in rows:
        source_id = int(row[4])

        if source_id not in grouped:
            raw_contract = row[13]

            contract = (
                DataForgeContract.model_validate(raw_contract)
                if raw_contract is not None
                else None
            )

            contract_cache[source_id] = contract

            grouped[source_id] = {
                "source_id": source_id,
                "code": row[5],
                "name": row[7],
                "type": row[6],
                "client_code": row[0],
                "client_name": row[1],
                "project_code": row[2],
                "project_name": row[3],
                "connection_reference": row[8],
                "active": bool(row[9]),
                "status": (
                    "active"
                    if row[9]
                    else "inactive"
                ),
                "created_at": row[10],
                "contract_id": (
                    int(row[11])
                    if row[11] is not None
                    else None
                ),
                "contract_revision": (
                    int(row[12])
                    if row[12] is not None
                    else None
                ),
                "datasets": [],
            }

        if row[14] is None:
            continue

        dataset_code = row[15]
        contract = contract_cache[source_id]

        configured_dataset = None

        if contract is not None:
            configured_dataset = next(
                (
                    dataset
                    for dataset in contract.datasets
                    if dataset.code == dataset_code
                ),
                None,
            )

        grouped[source_id]["datasets"].append(
            {
                "dataset_id": int(row[14]),
                "code": dataset_code,
                "name": row[16],
                "classification": (
                    configured_dataset.classification.value
                    if configured_dataset is not None
                    else row[17]
                ),
                "owner": (
                    configured_dataset.owner
                    if configured_dataset is not None
                    else row[18]
                ),
                "columns_count": (
                    len(configured_dataset.schema_)
                    if configured_dataset is not None
                    else 0
                ),
            }
        )

    return list(grouped.values())


def list_datasets(
    conn: psycopg.Connection,
    *,
    client_code: str | None = None,
    project_code: str | None = None,
    source_code: str | None = None,
) -> list[dict[str, Any]]:
    """Return dataset configuration plus real operational state."""

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                c.client_code,
                c.client_name,
                p.project_code,
                p.project_name,

                ds.source_code,
                ds.source_type,

                d.dataset_id,
                d.dataset_code,
                d.dataset_name,
                d.classification,
                d.owner_name,

                acc.contract_json,

                latest_cert.certification_state,

                layer_state.has_bronze,
                layer_state.has_silver,
                layer_state.has_quarantine,
                layer_state.has_gold

            FROM dataset d

            JOIN data_source ds
                ON ds.source_id = d.source_id

            JOIN project p
                ON p.project_id = ds.project_id

            JOIN client c
                ON c.client_id = p.client_id

            LEFT JOIN active_configuration_contract acc
                ON acc.source_id = ds.source_id

            LEFT JOIN LATERAL (
                SELECT
                    dc.state AS certification_state
                FROM dataset_version dv
                LEFT JOIN dataset_certification dc
                    ON dc.dataset_version_id =
                       dv.dataset_version_id
                WHERE dv.dataset_id = d.dataset_id
                ORDER BY
                    dv.discovered_at DESC,
                    dv.dataset_version_id DESC
                LIMIT 1
            ) latest_cert
                ON TRUE

            LEFT JOIN LATERAL (
                SELECT
                    COALESCE(
                        BOOL_OR(da.layer = 'bronze'),
                        FALSE
                    ) AS has_bronze,

                    COALESCE(
                        BOOL_OR(da.layer = 'silver'),
                        FALSE
                    ) AS has_silver,

                    COALESCE(
                        BOOL_OR(da.layer = 'quarantine'),
                        FALSE
                    ) AS has_quarantine,

                    COALESCE(
                        BOOL_OR(da.layer = 'gold'),
                        FALSE
                    ) AS has_gold

                FROM dataset_version dv2

                JOIN pipeline_run pr
                    ON pr.dataset_version_id =
                       dv2.dataset_version_id

                JOIN data_asset da
                    ON da.run_id = pr.run_id

                WHERE dv2.dataset_id = d.dataset_id
            ) layer_state
                ON TRUE

            WHERE
                (%s::text IS NULL OR c.client_code = %s)
                AND (%s::text IS NULL OR p.project_code = %s)
                AND (%s::text IS NULL OR ds.source_code = %s)

            ORDER BY
                c.client_code,
                p.project_code,
                ds.source_code,
                d.dataset_code
            """,
            (
                client_code,
                client_code,
                project_code,
                project_code,
                source_code,
                source_code,
            ),
        )

        rows = cur.fetchall()

    results: list[dict[str, Any]] = []
    contract_cache: dict[str, DataForgeContract | None] = {}

    for row in rows:
        cache_key = (
            f"{row[0]}::{row[2]}::{row[4]}"
        )

        if cache_key not in contract_cache:
            contract_cache[cache_key] = (
                DataForgeContract.model_validate(row[11])
                if row[11] is not None
                else None
            )

        contract = contract_cache[cache_key]

        configured_dataset = None

        if contract is not None:
            configured_dataset = next(
                (
                    dataset
                    for dataset in contract.datasets
                    if dataset.code == row[7]
                ),
                None,
            )

        schema = []

        if configured_dataset is not None:
            schema = [
                {
                    "name": column.name,
                    "type": column.type.value,
                    "nullable": column.nullable,
                    "classification": (
                        column.classification.value
                    ),
                    "description": column.description,
                }
                for column in configured_dataset.schema_
            ]

        gold_configured = False

        if (
            contract is not None
            and configured_dataset is not None
        ):
            gold_configured = any(
                gold.enabled
                and gold.base_dataset
                == configured_dataset.code
                for gold in contract.gold
            )

        results.append(
            {
                "dataset_id": int(row[6]),
                "code": row[7],
                "name": row[8],
                "client": row[0],
                "client_name": row[1],
                "project": row[2],
                "project_name": row[3],
                "source_code": row[4],
                "source_type": row[5],
                "classification": (
                    configured_dataset.classification.value
                    if configured_dataset is not None
                    else row[9]
                ),
                "owner": (
                    configured_dataset.owner
                    if configured_dataset is not None
                    else row[10]
                ),
                "certification_status": (
                    row[12]
                    or "draft"
                ),
                "columns_count": len(schema),
                "primary_keys": (
                    configured_dataset.keys.primary
                    if configured_dataset is not None
                    else []
                ),
                "rules_count": (
                    len(configured_dataset.quality.rules)
                    if configured_dataset is not None
                    else 0
                ),
                "transformations_count": (
                    len(
                        configured_dataset
                        .silver
                        .transformations
                    )
                    if configured_dataset is not None
                    else 0
                ),
                "gold_configured": gold_configured,
                "layers": {
                    "bronze": bool(row[13]),
                    "silver": bool(row[14]),
                    "quarantine": bool(row[15]),
                    "gold": bool(row[16]),
                },
                "schema": schema,
            }
        )

    return results


def get_active_contract(
    conn: psycopg.Connection,
    *,
    client_code: str,
    project_code: str,
    source_code: str,
) -> dict[str, Any] | None:
    """Load the active persisted contract for an exact source scope."""

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                contract_id,
                source_id,
                contract_version,
                revision,
                contract_hash,
                contract_json,
                created_by,
                created_at,
                activated_at
            FROM active_configuration_contract
            WHERE client_code = %s
              AND project_code = %s
              AND source_code = %s
            """,
            (
                client_code,
                project_code,
                source_code,
            ),
        )
        row = cur.fetchone()

    if row is None:
        return None

    contract = DataForgeContract.model_validate(
        row[5]
    )

    return {
        "contract_id": int(row[0]),
        "source_id": int(row[1]),
        "contract_version": row[2],
        "revision": int(row[3]),
        "contract_hash": row[4],
        "contract": contract,
        "created_by": row[6],
        "created_at": row[7],
        "activated_at": row[8],
    }


def get_contract_by_id(
    conn: psycopg.Connection,
    contract_id: int,
) -> dict[str, Any] | None:
    """Load one persisted contract revision by identifier."""

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                cc.contract_id,
                cc.source_id,
                cc.contract_version,
                cc.revision,
                cc.contract_hash,
                cc.contract_json,
                cc.status,
                cc.created_by,
                cc.created_at,
                cc.activated_at,
                cc.archived_at
            FROM configuration_contract cc
            WHERE cc.contract_id = %s
            """,
            (contract_id,),
        )
        row = cur.fetchone()

    if row is None:
        return None

    contract = DataForgeContract.model_validate(
        row[5]
    )

    return {
        "contract_id": int(row[0]),
        "source_id": int(row[1]),
        "contract_version": row[2],
        "revision": int(row[3]),
        "contract_hash": row[4],
        "contract": contract,
        "status": row[6],
        "created_by": row[7],
        "created_at": row[8],
        "activated_at": row[9],
        "archived_at": row[10],
    }



def list_orchestration_runs(
    conn,
    *,
    limit: int = 50,
    client_code: str | None = None,
    project_code: str | None = None,
    source_code: str | None = None,
) -> list[dict[str, object]]:
    """Return recent real orchestration runs from PostgreSQL."""

    safe_limit = max(
        1,
        min(limit, 200),
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                orchestration_run_id,
                orchestrator,
                external_run_id,
                contract_path,
                client_code,
                project_code,
                status,
                started_at,
                finished_at,
                duration_seconds,
                task_count,
                successful_tasks,
                failed_tasks,
                retried_attempts,
                error_message
            FROM orchestration_run_summary
            WHERE (%s::text IS NULL OR client_code = %s)
              AND (%s::text IS NULL OR project_code = %s)
              AND (%s::text IS NULL OR EXISTS (
                  SELECT 1 FROM orchestration_run original
                  WHERE original.orchestration_run_id =
                      orchestration_run_summary.orchestration_run_id
                    AND original.parameters_json #>> '{resolved,source_code}' = %s
              ))
            ORDER BY started_at DESC,
                     orchestration_run_id DESC
            LIMIT %s
            """,
            (client_code, client_code, project_code, project_code,
             source_code, source_code, safe_limit),
        )

        rows = cur.fetchall()

    return [
        {
            "orchestration_run_id": int(row[0]),
            "orchestrator": row[1],
            "external_run_id": row[2],
            "contract_reference": row[3],
            "client_code": row[4],
            "project_code": row[5],
            "status": row[6],
            "started_at": row[7],
            "finished_at": row[8],
            "duration_seconds": (
                float(row[9])
                if row[9] is not None
                else None
            ),
            "task_count": int(row[10]),
            "successful_tasks": int(row[11]),
            "failed_tasks": int(row[12]),
            "retried_attempts": int(row[13]),
            "error_message": row[14],
        }
        for row in rows
    ]



def _resolve_dataset_identity(
    conn,
    dataset_code: str,
    *,
    client_code: str | None = None,
    project_code: str | None = None,
    source_code: str | None = None,
) -> dict[str, object] | None:
    """Resolve one dataset, optionally scoped to client/project/source."""

    conditions = ["d.dataset_code = %s"]
    parameters: list[object] = [dataset_code]

    if client_code is not None:
        conditions.append("c.client_code = %s")
        parameters.append(client_code)

    if project_code is not None:
        conditions.append("p.project_code = %s")
        parameters.append(project_code)

    if source_code is not None:
        conditions.append("ds.source_code = %s")
        parameters.append(source_code)

    where_clause = " AND ".join(conditions)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                d.dataset_id,
                d.dataset_name,
                d.source_id,
                c.client_code,
                p.project_code,
                ds.source_code
            FROM dataset d
            JOIN data_source ds
                ON ds.source_id = d.source_id
            JOIN project p
                ON p.project_id = ds.project_id
            JOIN client c
                ON c.client_id = p.client_id
            WHERE {where_clause}
            ORDER BY d.dataset_id
            """,
            parameters,
        )

        rows = cur.fetchall()

    if not rows:
        return None

    if len(rows) > 1:
        raise ControlPlaneConflictError(
            f"Dataset code '{dataset_code}' is ambiguous; "
            "provide client_code, project_code, or source_code"
        )

    row = rows[0]

    return {
        "dataset_id": int(row[0]),
        "dataset_name": row[1],
        "source_id": int(row[2]),
        "client_code": row[3],
        "project_code": row[4],
        "source_code": row[5],
    }


def list_dataset_quality_results(
    conn,
    dataset_code: str,
    *,
    client_code: str | None = None,
    project_code: str | None = None,
    source_code: str | None = None,
) -> list[dict[str, object]] | None:
    """Return latest successful quality evaluation for one dataset."""

    identity = _resolve_dataset_identity(
        conn,
        dataset_code,
        client_code=client_code,
        project_code=project_code,
        source_code=source_code,
    )

    if identity is None:
        return None

    dataset_id = int(identity["dataset_id"])

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT pr.run_id
            FROM dataset_version dv
            JOIN pipeline_run pr
                ON pr.dataset_version_id = dv.dataset_version_id
            WHERE dv.dataset_id = %s
              AND pr.run_type = 'silver_quality_gate'
              AND pr.status = 'success'
            ORDER BY
                pr.finished_at DESC NULLS LAST,
                pr.run_id DESC
            LIMIT 1
            """,
            (dataset_id,),
        )

        run_row = cur.fetchone()

    if run_row is None:
        return []

    run_id = int(run_row[0])

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                quality_result_id,
                rule_name,
                rule_type,
                status,
                failed_rows,
                failure_percentage,
                details_json,
                evaluated_at
            FROM quality_result
            WHERE run_id = %s
            ORDER BY quality_result_id
            """,
            (run_id,),
        )

        rows = cur.fetchall()

    results = []

    for row in rows:
        details = row[6] or {}

        results.append(
            {
                "quality_result_id": int(row[0]),
                "run_id": run_id,
                "name": row[1],
                "rule_type": row[2],
                "column": details.get("column"),
                "severity": details.get("severity"),
                "status": row[3],
                "failed_rows": int(row[4]),
                "failure_percentage": (
                    float(row[5])
                    if row[5] is not None
                    else 0.0
                ),
                "gx_success": details.get("gx_success"),
                "evaluated_at": row[7],
            }
        )

    return results


def get_dataset_quarantine_context(
    conn,
    dataset_code: str,
    *,
    client_code: str | None = None,
    project_code: str | None = None,
    source_code: str | None = None,
) -> dict[str, object] | None:
    """Resolve latest quarantine asset and active contract."""

    identity = _resolve_dataset_identity(
        conn,
        dataset_code,
        client_code=client_code,
        project_code=project_code,
        source_code=source_code,
    )

    if identity is None:
        return None

    dataset_id = int(identity["dataset_id"])
    source_id = int(identity["source_id"])

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT contract_id
            FROM configuration_contract
            WHERE source_id = %s
              AND status = 'active'
            LIMIT 1
            """,
            (source_id,),
        )

        contract_row = cur.fetchone()

    contract_id = (
        int(contract_row[0])
        if contract_row is not None
        else None
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                pr.run_id,
                da.asset_id,
                da.storage_uri,
                da.row_count,
                da.created_at
            FROM dataset_version dv
            JOIN pipeline_run pr
                ON pr.dataset_version_id = dv.dataset_version_id
            JOIN data_asset da
                ON da.run_id = pr.run_id
            WHERE dv.dataset_id = %s
              AND pr.run_type = 'silver_quality_gate'
              AND pr.status = 'success'
              AND da.layer = 'quarantine'
            ORDER BY
                pr.finished_at DESC NULLS LAST,
                pr.run_id DESC
            LIMIT 1
            """,
            (dataset_id,),
        )

        asset_row = cur.fetchone()

    result = {
        **identity,
        "contract_id": contract_id,
        "asset": None,
    }

    if asset_row is not None:
        result["asset"] = {
            "run_id": int(asset_row[0]),
            "asset_id": int(asset_row[1]),
            "storage_uri": asset_row[2],
            "row_count": int(asset_row[3]),
            "created_at": asset_row[4],
        }

    return result



def list_assets(
    conn,
    *,
    client_code: str | None = None,
    project_code: str | None = None,
    source_code: str | None = None,
    dataset_code: str | None = None,
    layer: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    """List persisted data assets with control-plane identity."""

    conditions = []
    parameters: list[object] = []

    if client_code is not None:
        conditions.append("c.client_code = %s")
        parameters.append(client_code)

    if project_code is not None:
        conditions.append("p.project_code = %s")
        parameters.append(project_code)

    if source_code is not None:
        conditions.append("ds.source_code = %s")
        parameters.append(source_code)

    if dataset_code is not None:
        conditions.append("d.dataset_code = %s")
        parameters.append(dataset_code)

    if layer is not None:
        conditions.append("da.layer = %s")
        parameters.append(layer)

    where_clause = (
        "WHERE " + " AND ".join(conditions)
        if conditions
        else ""
    )

    safe_limit = max(1, min(int(limit), 200))
    parameters.append(safe_limit)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                da.asset_id,
                da.layer,
                da.asset_name,
                da.storage_uri,
                da.format,
                da.row_count,
                da.checksum,
                da.created_at,

                pr.run_id,
                pr.run_type,
                pr.status,
                pr.input_rows,
                pr.accepted_rows,
                pr.rejected_rows,

                dv.dataset_version_id,
                dv.version_label,

                d.dataset_id,
                d.dataset_code,
                d.dataset_name,

                ds.source_id,
                ds.source_code,
                ds.source_name,
                ds.source_type,

                p.project_id,
                p.project_code,
                p.project_name,

                c.client_id,
                c.client_code,
                c.client_name

            FROM data_asset da
            JOIN pipeline_run pr
                ON pr.run_id = da.run_id
            JOIN dataset_version dv
                ON dv.dataset_version_id = pr.dataset_version_id
            JOIN dataset d
                ON d.dataset_id = dv.dataset_id
            JOIN data_source ds
                ON ds.source_id = d.source_id
            JOIN project p
                ON p.project_id = ds.project_id
            JOIN client c
                ON c.client_id = p.client_id

            {where_clause}

            ORDER BY
                da.created_at DESC,
                da.asset_id DESC

            LIMIT %s
            """,
            parameters,
        )

        rows = cur.fetchall()

    return [
        {
            "asset_id": int(row[0]),
            "layer": row[1],
            "asset_name": row[2],
            "storage_uri": row[3],
            "format": row[4],
            "row_count": (
                int(row[5])
                if row[5] is not None
                else None
            ),
            "checksum": row[6],
            "created_at": row[7],

            "run_id": int(row[8]),
            "run_type": row[9],
            "run_status": row[10],
            "input_rows": (
                int(row[11])
                if row[11] is not None
                else None
            ),
            "accepted_rows": (
                int(row[12])
                if row[12] is not None
                else None
            ),
            "rejected_rows": (
                int(row[13])
                if row[13] is not None
                else None
            ),

            "dataset_version_id": int(row[14]),
            "version_label": row[15],

            "dataset_id": int(row[16]),
            "dataset_code": row[17],
            "dataset_name": row[18],

            "source_id": int(row[19]),
            "source_code": row[20],
            "source_name": row[21],
            "source_type": row[22],

            "project_id": int(row[23]),
            "project_code": row[24],
            "project_name": row[25],

            "client_id": int(row[26]),
            "client_code": row[27],
            "client_name": row[28],
        }
        for row in rows
    ]



def get_lineage_graph(
    conn,
    *,
    client_code: str | None = None,
    project_code: str | None = None,
    source_code: str | None = None,
    dataset_code: str | None = None,
    limit: int = 500,
) -> dict[str, object]:
    """Build an asset-to-asset lineage graph from persisted lineage edges."""

    conditions = []
    parameters: list[object] = []

    if client_code is not None:
        conditions.append("c.client_code = %s")
        parameters.append(client_code)

    if project_code is not None:
        conditions.append("p.project_code = %s")
        parameters.append(project_code)

    if source_code is not None:
        conditions.append("ds.source_code = %s")
        parameters.append(source_code)

    if dataset_code is not None:
        conditions.append("d.dataset_code = %s")
        parameters.append(dataset_code)

    where_clause = (
        "WHERE " + " AND ".join(conditions)
        if conditions
        else ""
    )

    safe_limit = max(1, min(int(limit), 1000))
    parameters.append(safe_limit)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            WITH scoped_assets AS (
                SELECT da.asset_id
                FROM data_asset da
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

                {where_clause}
            )
            SELECT
                ale.lineage_id,
                ale.relation_type,

                ale.parent_asset_id,
                ale.parent_layer,
                ale.parent_asset_name,
                ale.parent_storage_uri,
                ale.parent_dataset_code,
                ale.parent_version_label,

                ale.child_asset_id,
                ale.child_layer,
                ale.child_asset_name,
                ale.child_storage_uri,
                ale.child_dataset_code,
                ale.child_version_label,

                ale.created_by_run_id,
                ale.metadata_json,
                ale.created_at

            FROM asset_lineage_edges ale

            WHERE EXISTS (
                SELECT 1
                FROM scoped_assets sa
                WHERE sa.asset_id = ale.parent_asset_id
                   OR sa.asset_id = ale.child_asset_id
            )

            ORDER BY ale.lineage_id
            LIMIT %s
            """,
            parameters,
        )

        rows = cur.fetchall()

    nodes: dict[int, dict[str, object]] = {}
    links: list[dict[str, object]] = []

    for row in rows:
        parent_asset_id = int(row[2])
        child_asset_id = int(row[8])

        nodes[parent_asset_id] = {
            "id": f"asset-{parent_asset_id}",
            "asset_id": parent_asset_id,
            "name": row[4],
            "type": "asset",
            "layer": row[3],
            "dataset_code": row[6],
            "version_label": row[7],
            "storage_uri": row[5],
        }

        nodes[child_asset_id] = {
            "id": f"asset-{child_asset_id}",
            "asset_id": child_asset_id,
            "name": row[10],
            "type": "asset",
            "layer": row[9],
            "dataset_code": row[12],
            "version_label": row[13],
            "storage_uri": row[11],
        }

        links.append(
            {
                "lineage_id": int(row[0]),
                "source": f"asset-{parent_asset_id}",
                "target": f"asset-{child_asset_id}",
                "relation_type": row[1],
                "created_by_run_id": (
                    int(row[14])
                    if row[14] is not None
                    else None
                ),
                "metadata": row[15] or {},
                "created_at": row[16],
            }
        )

    return {
        "nodes": list(nodes.values()),
        "links": links,
    }



def list_certification_targets(
    conn,
    *,
    client_code: str | None = None,
    project_code: str | None = None,
    source_code: str | None = None,
    dataset_code: str | None = None,
) -> list[dict[str, object]]:
    """Return latest dataset versions and their certification records."""

    conditions = []
    parameters: list[object] = []

    if client_code is not None:
        conditions.append("c.client_code = %s")
        parameters.append(client_code)

    if project_code is not None:
        conditions.append("p.project_code = %s")
        parameters.append(project_code)

    if source_code is not None:
        conditions.append("ds.source_code = %s")
        parameters.append(source_code)

    if dataset_code is not None:
        conditions.append("d.dataset_code = %s")
        parameters.append(dataset_code)

    where_clause = (
        "WHERE " + " AND ".join(conditions)
        if conditions
        else ""
    )

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT DISTINCT ON (d.dataset_id)
                c.client_code,
                p.project_code,
                ds.source_code,

                d.dataset_id,
                d.dataset_code,
                d.dataset_name,

                dv.dataset_version_id,
                dv.version_label,

                dc.certification_id,
                dc.state,
                dc.criteria_json,
                dc.last_evaluated_at,
                dc.validated_at,
                dc.certified_at,
                dc.created_at,
                dc.updated_at

            FROM dataset d
            JOIN data_source ds
                ON ds.source_id = d.source_id
            JOIN project p
                ON p.project_id = ds.project_id
            JOIN client c
                ON c.client_id = p.client_id
            JOIN dataset_version dv
                ON dv.dataset_id = d.dataset_id
            LEFT JOIN dataset_certification dc
                ON dc.dataset_version_id =
                   dv.dataset_version_id

            {where_clause}

            ORDER BY
                d.dataset_id,
                dv.dataset_version_id DESC
            """,
            parameters,
        )

        rows = cur.fetchall()

    return [
        {
            "client_code": row[0],
            "project_code": row[1],
            "source_code": row[2],

            "dataset_id": int(row[3]),
            "dataset_code": row[4],
            "dataset_name": row[5],

            "dataset_version_id": int(row[6]),
            "version_label": row[7],

            "certification_id": (
                int(row[8])
                if row[8] is not None
                else None
            ),
            "state": row[9],
            "stored_criteria": row[10] or {},
            "last_evaluated_at": row[11],
            "validated_at": row[12],
            "certified_at": row[13],
            "created_at": row[14],
            "updated_at": row[15],
        }
        for row in rows
    ]


def resolve_latest_dataset_version(
    conn,
    dataset_code: str,
    *,
    client_code: str | None = None,
    project_code: str | None = None,
    source_code: str | None = None,
) -> dict[str, object] | None:
    """Resolve the latest version of exactly one dataset."""

    identity = _resolve_dataset_identity(
        conn,
        dataset_code,
        client_code=client_code,
        project_code=project_code,
        source_code=source_code,
    )

    if identity is None:
        return None

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                dataset_version_id,
                version_label
            FROM dataset_version
            WHERE dataset_id = %s
            ORDER BY dataset_version_id DESC
            LIMIT 1
            """,
            (identity["dataset_id"],),
        )

        row = cur.fetchone()

    return {
        **identity,
        "dataset_version_id": (
            int(row[0])
            if row is not None
            else None
        ),
        "version_label": (
            row[1]
            if row is not None
            else None
        ),
    }


def fetch_overview(
    conn,
    *,
    client_code: str | None = None,
    project_code: str | None = None,
    source_code: str | None = None,
) -> dict[str, Any]:
    """Read complete scoped totals, independently of recent-history limits.

    Processed rows count successful Bronze input once per ingestion run.
    Rejected rows count successful Silver quality gates. These are cumulative
    execution metrics, not the size of the latest materialized dataset.
    """
    sources = list_sources(conn, client_code=client_code, project_code=project_code)
    if source_code is not None:
        sources = [source for source in sources if source["code"] == source_code]
    datasets = list_datasets(
        conn, client_code=client_code, project_code=project_code, source_code=source_code,
    )
    scope = (client_code, client_code, project_code, project_code, source_code, source_code)
    joins = """
        FROM pipeline_run pr
        JOIN dataset_version dv ON dv.dataset_version_id = pr.dataset_version_id
        JOIN dataset d ON d.dataset_id = dv.dataset_id
        JOIN data_source ds ON ds.source_id = d.source_id
        JOIN project p ON p.project_id = ds.project_id
        JOIN client c ON c.client_id = p.client_id
        WHERE (%s::text IS NULL OR c.client_code = %s)
          AND (%s::text IS NULL OR p.project_code = %s)
          AND (%s::text IS NULL OR ds.source_code = %s)
    """
    with conn.cursor() as cur:
        cur.execute(
            """SELECT COUNT(*),
                COALESCE(SUM(pr.input_rows) FILTER (
                    WHERE pr.run_type = 'source_to_bronze' AND pr.status = 'success'), 0),
                COALESCE(SUM(pr.rejected_rows) FILTER (
                    WHERE pr.run_type = 'silver_quality_gate' AND pr.status = 'success'), 0)
            """ + joins,
            scope,
        )
        total_runs, processed, quarantined = cur.fetchone()
        cur.execute(
            """SELECT pr.run_id, d.dataset_code, ds.source_code, pr.run_type,
                pr.status, pr.input_rows, pr.accepted_rows, pr.rejected_rows,
                EXTRACT(EPOCH FROM (pr.finished_at - pr.started_at)), pr.started_at
            """ + joins + " ORDER BY pr.started_at DESC, pr.run_id DESC LIMIT 5",
            scope,
        )
        rows = cur.fetchall()
    certified = sum(d["certification_status"] == "certified" for d in datasets)
    return {
        "source": "database",
        "summary": {
            "total_clients": len({s["client_code"] for s in sources}),
            "total_sources": len(sources),
            "total_datasets": len(datasets),
            "total_runs": int(total_runs),
            "total_rows_processed": int(processed),
            "total_quarantined_rows": int(quarantined),
            "certified_datasets": certified,
            "certification_rate_pct": round(certified / len(datasets) * 100, 1) if datasets else 0.0,
        },
        "recent_runs": [
            {
                "run_id": int(row[0]), "dataset": row[1], "source": row[2],
                "layer": row[3], "status": row[4], "input_rows": row[5],
                "accepted_rows": row[6], "rejected_rows": row[7],
                "duration_sec": float(row[8]) if row[8] is not None else None,
                "created_at": row[9],
            }
            for row in rows
        ],
        "active_sources": sources,
    }
