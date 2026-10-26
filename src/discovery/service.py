"""Persistent generic profiling service for DataForge (#21).

Profiles the exact latest successful Bronze asset for a contract dataset,
records the execution as a profiling pipeline run and persists the structured
technical profile in the control plane.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import psycopg

from src.common.clients import connect_postgres, create_s3_client
from src.common.log import bind_context, run_context
from src.common.settings import load_environment_file
from src.contracts.loader import load_contract
from src.contracts.models import Classification, DataForgeContract, DatasetConfig
from src.discovery.engine import profile_dataframe


logger = logging.getLogger("src.discovery.service")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_s3_uri(storage_uri: str) -> tuple[str, str]:
    """Split an s3:// URI into bucket and key."""
    parsed = urlparse(storage_uri)
    key = parsed.path.lstrip("/")

    if parsed.scheme != "s3" or not parsed.netloc or not key:
        raise ValueError(f"Invalid S3 URI: {storage_uri}")

    return parsed.netloc, key


def sha256_file(path: Path) -> str:
    """Calculate the SHA-256 digest of a local file."""
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def latest_bronze_asset(
    conn: psycopg.Connection,
    client_code: str,
    project_code: str,
    source_code: str,
    dataset_code: str,
) -> dict[str, Any]:
    """Return the latest successful Bronze asset for one exact dataset scope."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                da.asset_id,
                pr.dataset_version_id,
                dv.source_checksum,
                da.storage_uri,
                da.row_count,
                da.checksum
            FROM client c
            JOIN project p
                ON p.client_id = c.client_id
            JOIN data_source ds
                ON ds.project_id = p.project_id
            JOIN dataset d
                ON d.source_id = ds.source_id
            JOIN dataset_version dv
                ON dv.dataset_id = d.dataset_id
            JOIN pipeline_run pr
                ON pr.dataset_version_id = dv.dataset_version_id
            JOIN data_asset da
                ON da.run_id = pr.run_id
            WHERE c.client_code = %s
              AND p.project_code = %s
              AND ds.source_code = %s
              AND d.dataset_code = %s
              AND pr.run_type = 'source_to_bronze'
              AND pr.status = 'success'
              AND da.layer = 'bronze'
            ORDER BY
                pr.finished_at DESC NULLS LAST,
                pr.run_id DESC
            LIMIT 1
            """,
            (
                client_code,
                project_code,
                source_code,
                dataset_code,
            ),
        )
        row = cur.fetchone()

    if row is None:
        raise RuntimeError(
            "No successful Bronze asset found for "
            f"client='{client_code}', "
            f"project='{project_code}', "
            f"source='{source_code}', "
            f"dataset='{dataset_code}'"
        )

    return {
        "asset_id": int(row[0]),
        "dataset_version_id": int(row[1]),
        "source_checksum": row[2],
        "storage_uri": row[3],
        "row_count": int(row[4]),
        "asset_checksum": row[5],
    }


def start_profiling_run(
    conn: psycopg.Connection,
    dataset_version_id: int,
    input_rows: int,
) -> int:
    """Create a traceable profiling pipeline run."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO pipeline_run (
                dataset_version_id,
                run_type,
                status,
                input_rows
            )
            VALUES (%s, 'profiling', 'running', %s)
            RETURNING run_id
            """,
            (
                dataset_version_id,
                input_rows,
            ),
        )
        row = cur.fetchone()

    if row is None:
        raise RuntimeError("Profiling pipeline run could not be created")

    return int(row[0])


def finish_profiling_run(
    conn: psycopg.Connection,
    run_id: int,
    status: str,
    accepted_rows: int | None = None,
    rejected_rows: int | None = None,
    error_message: str | None = None,
) -> None:
    """Finish a profiling run with success or failure metadata."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE pipeline_run
            SET status = %s,
                finished_at = %s,
                accepted_rows = %s,
                rejected_rows = %s,
                error_message = %s
            WHERE run_id = %s
            """,
            (
                status,
                utc_now(),
                accepted_rows,
                rejected_rows,
                error_message,
                run_id,
            ),
        )


def normalize_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Return a PostgreSQL JSONB-safe copy of a generated profile."""
    return json.loads(
        json.dumps(
            profile,
            ensure_ascii=False,
            default=str,
            allow_nan=False,
        )
    )


def redact_sensitive_samples(
    profile: dict[str, Any],
    dataset: DatasetConfig,
) -> dict[str, Any]:
    """Remove raw samples from confidential or restricted profile columns."""
    safe_profile = deepcopy(profile)

    sensitive_classifications = {
        Classification.CONFIDENTIAL,
        Classification.RESTRICTED,
    }

    dataset_is_sensitive = (
        dataset.classification in sensitive_classifications
    )

    sensitive_columns = {
        column.name
        for column in dataset.schema_
        if (
            dataset_is_sensitive
            or column.classification in sensitive_classifications
        )
    }

    columns = safe_profile.get("columns")

    if not isinstance(columns, dict):
        return safe_profile

    for column_name in sensitive_columns:
        column_profile = columns.get(column_name)

        if not isinstance(column_profile, dict):
            continue

        if "sample_values" in column_profile:
            column_profile["sample_values"] = []
            column_profile["sample_values_redacted"] = True

    return safe_profile


def persist_profile_result(
    conn: psycopg.Connection,
    run_id: int,
    source_asset_id: int,
    profile: dict[str, Any],
) -> int:
    """Persist one complete technical profile and return its identifier."""
    normalized = normalize_profile(profile)

    generated_at_raw = normalized["generated_at_utc"]
    generated_at = datetime.fromisoformat(generated_at_raw)

    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO profiling_result (
                run_id,
                source_asset_id,
                profile_version,
                row_count,
                column_count,
                duplicate_rows,
                duplicate_rows_percentage,
                candidate_keys_json,
                profile_json,
                generated_at
            )
            VALUES (
                %s,
                %s,
                '1.0',
                %s,
                %s,
                %s,
                %s,
                %s::jsonb,
                %s::jsonb,
                %s
            )
            RETURNING profile_id
            """,
            (
                run_id,
                source_asset_id,
                int(normalized["row_count"]),
                int(normalized["column_count"]),
                int(normalized["duplicate_rows"]),
                float(normalized["duplicate_rows_percentage"]),
                json.dumps(
                    normalized["candidate_keys"],
                    ensure_ascii=False,
                ),
                json.dumps(
                    normalized,
                    ensure_ascii=False,
                ),
                generated_at,
            ),
        )
        row = cur.fetchone()

    if row is None:
        raise RuntimeError("Profiling result could not be persisted")

    return int(row[0])


def execute_profiling_for_dataset(
    contract: DataForgeContract,
    dataset_code: str,
    s3,
    conn: psycopg.Connection,
) -> dict[str, Any]:
    """Profile and persist one contract dataset from its latest Bronze asset."""
    with run_context(
        stage="profiling",
        client=contract.client.code,
        project=contract.project.code,
        dataset=dataset_code,
    ):
        logger.info("Profiling started")

        try:
            result = _execute_profiling_for_dataset(
                contract=contract,
                dataset_code=dataset_code,
                s3=s3,
                conn=conn,
            )
        except Exception:
            logger.exception("Profiling failed")
            raise

        logger.info(
            "Profiling finished",
            extra={
                "profile_id": result["profile_id"],
                "row_count": result["row_count"],
                "column_count": result["column_count"],
            },
        )

        return result


def _execute_profiling_for_dataset(
    contract: DataForgeContract,
    dataset_code: str,
    s3,
    conn: psycopg.Connection,
) -> dict[str, Any]:
    dataset = next(
        (item for item in contract.datasets if item.code == dataset_code),
        None,
    )

    if dataset is None:
        raise ValueError(
            f"Dataset '{dataset_code}' not found in contract"
        )

    bronze = latest_bronze_asset(
        conn=conn,
        client_code=contract.client.code,
        project_code=contract.project.code,
        source_code=contract.source.code,
        dataset_code=dataset.code,
    )

    run_id = start_profiling_run(
        conn=conn,
        dataset_version_id=bronze["dataset_version_id"],
        input_rows=bronze["row_count"],
    )

    conn.commit()
    bind_context(run_id=run_id)

    try:
        bronze_bucket, bronze_key = parse_s3_uri(
            bronze["storage_uri"]
        )

        with tempfile.TemporaryDirectory(
            prefix="dataforge-profiling-"
        ) as temporary_directory:
            bronze_path = (
                Path(temporary_directory)
                / f"{dataset.code}_bronze.parquet"
            )

            s3.download_file(
                bronze_bucket,
                bronze_key,
                str(bronze_path),
            )

            downloaded_checksum = sha256_file(bronze_path)

            if downloaded_checksum != bronze["asset_checksum"]:
                raise RuntimeError(
                    "Bronze asset checksum mismatch for "
                    f"dataset '{dataset.code}': "
                    f"expected {bronze['asset_checksum']}, "
                    f"got {downloaded_checksum}"
                )

            frame = pd.read_parquet(
                bronze_path,
                engine="pyarrow",
            )

            if len(frame) != bronze["row_count"]:
                raise RuntimeError(
                    "Bronze asset row-count mismatch for "
                    f"dataset '{dataset.code}': "
                    f"expected {bronze['row_count']}, "
                    f"got {len(frame)}"
                )

            profile = profile_dataframe(
                frame,
                dataset_name=dataset.code,
            )

            profile = redact_sensitive_samples(
                profile=profile,
                dataset=dataset,
            )

        profile_id = persist_profile_result(
            conn=conn,
            run_id=run_id,
            source_asset_id=bronze["asset_id"],
            profile=profile,
        )

        finish_profiling_run(
            conn=conn,
            run_id=run_id,
            status="success",
            accepted_rows=len(frame),
            rejected_rows=0,
        )

        conn.commit()

        return {
            "dataset": dataset.code,
            "profile_id": profile_id,
            "run_id": run_id,
            "dataset_version_id": bronze["dataset_version_id"],
            "source_asset_id": bronze["asset_id"],
            "source_checksum": bronze["source_checksum"],
            "row_count": profile["row_count"],
            "column_count": profile["column_count"],
            "profile": profile,
        }

    except Exception as exc:
        conn.rollback()

        finish_profiling_run(
            conn=conn,
            run_id=run_id,
            status="failed",
            error_message=str(exc)[:2000],
        )

        conn.commit()
        raise


def run_profiling_pipeline(
    contract_path: str | Path,
) -> list[dict[str, Any]]:
    """Profile every dataset in a contract from its latest Bronze asset."""
    load_environment_file()

    contract = load_contract(contract_path)
    s3 = create_s3_client()

    results: list[dict[str, Any]] = []

    with connect_postgres() as conn:
        for dataset in contract.datasets:
            results.append(
                execute_profiling_for_dataset(
                    contract=contract,
                    dataset_code=dataset.code,
                    s3=s3,
                    conn=conn,
                )
            )

    return results


def get_latest_profile(
    conn: psycopg.Connection,
    dataset_code: str,
    client_code: str | None = None,
    project_code: str | None = None,
    source_code: str | None = None,
) -> dict[str, Any] | None:
    """Return the latest persisted profile for one dataset.

    Optional scope fields disambiguate datasets that share the same code
    across clients, projects or sources. If more than one dataset matches the
    supplied scope, the caller must provide a more specific scope.
    """

    filters = ["dataset_code = %s"]
    params: list[Any] = [dataset_code]

    if client_code is not None:
        filters.append("client_code = %s")
        params.append(client_code)

    if project_code is not None:
        filters.append("project_code = %s")
        params.append(project_code)

    if source_code is not None:
        filters.append("source_code = %s")
        params.append(source_code)

    where_clause = " AND ".join(filters)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                profile_id,
                client_code,
                project_code,
                source_code,
                dataset_code,
                dataset_version_id,
                version_label,
                run_id,
                source_asset_id,
                source_storage_uri,
                row_count,
                column_count,
                generated_at,
                profile_json
            FROM dataset_latest_profile
            WHERE {where_clause}
            ORDER BY
                finished_at DESC NULLS LAST,
                run_id DESC
            LIMIT 2
            """,
            tuple(params),
        )

        rows = cur.fetchall()

    if not rows:
        return None

    if len(rows) > 1:
        raise ValueError(
            "Ambiguous dataset profiling lookup for "
            f"dataset='{dataset_code}'. "
            "Provide client_code, project_code and/or source_code "
            "to identify one dataset."
        )

    row = rows[0]

    return {
        "profile_id": int(row[0]),
        "client_code": row[1],
        "project_code": row[2],
        "source_code": row[3],
        "dataset_code": row[4],
        "dataset_version_id": int(row[5]),
        "version_label": row[6],
        "run_id": int(row[7]),
        "source_asset_id": int(row[8]),
        "source_storage_uri": row[9],
        "row_count": int(row[10]),
        "column_count": int(row[11]),
        "generated_at": row[12],
        "profile": row[13],
    }
