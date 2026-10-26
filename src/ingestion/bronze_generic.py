"""Generic contract-driven source-to-Bronze ingestion for DataForge."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
import pandas as pd
import psycopg
from botocore.client import Config
from dotenv import load_dotenv

from src.connectors import get_dataset_connector
from src.contracts import load_contract
from src.contracts.models import DataForgeContract, DatasetConfig
from src.governance.metadata import dataframe_schema_hash


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def dataframe_checksum(frame: pd.DataFrame) -> str:
    """Create a deterministic checksum from extracted tabular content."""

    digest = hashlib.sha256()

    metadata = {
        "columns": [str(column) for column in frame.columns],
        "dtypes": [str(dtype) for dtype in frame.dtypes],
        "rows": len(frame),
    }

    digest.update(
        json.dumps(
            metadata,
            sort_keys=True,
        ).encode("utf-8")
    )

    payload = frame.to_json(
        orient="records",
        date_format="iso",
        default_handler=str,
    )

    digest.update(payload.encode("utf-8"))

    return digest.hexdigest()


def minio_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["MINIO_ENDPOINT"],
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        region_name="us-east-1",
        config=Config(signature_version="s3v4"),
    )


def postgres_connection():
    return psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def ensure_control_plane_records(
    conn: psycopg.Connection,
    contract: DataForgeContract,
    dataset: DatasetConfig,
) -> int:
    """Create or update generic control-plane metadata."""

    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO client (
                client_code,
                client_name
            )
            VALUES (%s, %s)
            ON CONFLICT (client_code)
            DO UPDATE SET
                client_name = EXCLUDED.client_name
            RETURNING client_id
            """,
            (
                contract.client.code,
                contract.client.name,
            ),
        )

        client_id = cursor.fetchone()[0]

        cursor.execute(
            """
            INSERT INTO project (
                client_id,
                project_code,
                project_name
            )
            VALUES (%s, %s, %s)
            ON CONFLICT (project_code)
            DO UPDATE SET
                project_name = EXCLUDED.project_name
            RETURNING project_id
            """,
            (
                client_id,
                contract.project.code,
                contract.project.name,
            ),
        )

        project_id = cursor.fetchone()[0]

        cursor.execute(
            """
            INSERT INTO data_source (
                project_id,
                source_code,
                source_type,
                source_name,
                connection_reference
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (
                project_id,
                source_code
            )
            DO UPDATE SET
                source_type = EXCLUDED.source_type,
                source_name = EXCLUDED.source_name,
                connection_reference = EXCLUDED.connection_reference
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

        source_id = cursor.fetchone()[0]

        cursor.execute(
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

        return cursor.fetchone()[0]


def register_dataset_version(
    conn: psycopg.Connection,
    dataset_id: int,
    frame: pd.DataFrame,
    source_checksum: str,
) -> int:
    version_label = source_checksum[:12]

    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO dataset_version (
                dataset_id,
                version_label,
                schema_hash,
                source_checksum
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (
                dataset_id,
                version_label
            )
            DO UPDATE SET
                schema_hash = EXCLUDED.schema_hash,
                source_checksum = EXCLUDED.source_checksum
            RETURNING dataset_version_id
            """,
            (
                dataset_id,
                version_label,
                dataframe_schema_hash(frame),
                source_checksum,
            ),
        )

        return cursor.fetchone()[0]


def start_pipeline_run(
    conn: psycopg.Connection,
    dataset_version_id: int,
    row_count: int,
) -> int:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO pipeline_run (
                dataset_version_id,
                run_type,
                status,
                input_rows
            )
            VALUES (
                %s,
                'source_to_bronze',
                'running',
                %s
            )
            RETURNING run_id
            """,
            (
                dataset_version_id,
                row_count,
            ),
        )

        return cursor.fetchone()[0]


def finish_pipeline_run(
    conn: psycopg.Connection,
    run_id: int,
    status: str,
    accepted_rows: int | None = None,
    error_message: str | None = None,
) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE pipeline_run
            SET status = %s,
                finished_at = %s,
                accepted_rows = %s,
                rejected_rows =
                    CASE
                        WHEN %s = 'success'
                        THEN 0
                        ELSE rejected_rows
                    END,
                error_message = %s
            WHERE run_id = %s
            """,
            (
                status,
                utc_now(),
                accepted_rows,
                status,
                error_message,
                run_id,
            ),
        )


def register_bronze_asset(
    conn: psycopg.Connection,
    run_id: int,
    asset_name: str,
    storage_uri: str,
    row_count: int,
    checksum: str,
) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO data_asset (
                run_id,
                layer,
                asset_name,
                storage_uri,
                format,
                row_count,
                checksum
            )
            VALUES (
                %s,
                'bronze',
                %s,
                %s,
                'parquet',
                %s,
                %s
            )
            """,
            (
                run_id,
                asset_name,
                storage_uri,
                row_count,
                checksum,
            ),
        )


def extract_dataset(
    contract: DataForgeContract,
    dataset_code: str,
    environ: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Extract any configured dataset through the connector registry."""

    connector = get_dataset_connector(
        contract,
        dataset_code,
        environ=environ,
    )

    return connector.extract()


def ingest_dataset(
    contract: DataForgeContract,
    dataset_code: str,
    s3,
    conn: psycopg.Connection,
    bucket: str,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run generic source-to-Bronze ingestion for one dataset."""

    dataset = next(
        (
            item
            for item in contract.datasets
            if item.code == dataset_code
        ),
        None,
    )

    if dataset is None:
        raise ValueError(
            f"Unknown dataset '{dataset_code}'"
        )

    frame = extract_dataset(
        contract,
        dataset_code,
        environ=environ,
    )

    source_checksum = dataframe_checksum(frame)

    dataset_id = ensure_control_plane_records(
        conn,
        contract,
        dataset,
    )

    dataset_version_id = register_dataset_version(
        conn,
        dataset_id,
        frame,
        source_checksum,
    )

    run_id = start_pipeline_run(
        conn,
        dataset_version_id,
        len(frame),
    )

    conn.commit()

    object_key = (
        f"{contract.client.code}/"
        f"{contract.project.code}/"
        f"{dataset.code}/"
        f"source_checksum={source_checksum[:12]}/"
        f"{dataset.code}.parquet"
    )

    storage_uri = f"s3://{bucket}/{object_key}"

    try:
        with tempfile.TemporaryDirectory(
            prefix="dataforge-bronze-"
        ) as temporary_directory:
            parquet_path = (
                Path(temporary_directory)
                / f"{dataset.code}.parquet"
            )

            frame.to_parquet(
                parquet_path,
                index=False,
                engine="pyarrow",
            )

            parquet_checksum = sha256_file(
                parquet_path
            )

            s3.upload_file(
                str(parquet_path),
                bucket,
                object_key,
            )

        register_bronze_asset(
            conn=conn,
            run_id=run_id,
            asset_name=(
                f"{contract.client.code}_"
                f"{dataset.code}_bronze"
            ),
            storage_uri=storage_uri,
            row_count=len(frame),
            checksum=parquet_checksum,
        )

        finish_pipeline_run(
            conn,
            run_id,
            "success",
            accepted_rows=len(frame),
        )

        conn.commit()

        return {
            "dataset": dataset.code,
            "source_type": contract.source.type.value,
            "rows": len(frame),
            "source_checksum": source_checksum,
            "storage_uri": storage_uri,
            "run_id": run_id,
        }

    except Exception as exc:
        conn.rollback()

        finish_pipeline_run(
            conn,
            run_id,
            "failed",
            error_message=str(exc)[:2000],
        )

        conn.commit()

        raise


def run_ingestion(
    contract_path: str | Path,
) -> list[dict[str, Any]]:
    """Run generic ingestion for every dataset in one contract."""

    load_dotenv(PROJECT_ROOT / ".env")

    contract = load_contract(
        contract_path
    )

    bucket = os.environ.get(
        "MINIO_BUCKET_BRONZE",
        "dataforge-bronze",
    )

    s3 = minio_client()

    results: list[dict[str, Any]] = []

    with postgres_connection() as conn:
        for dataset in contract.datasets:
            results.append(
                ingest_dataset(
                    contract=contract,
                    dataset_code=dataset.code,
                    s3=s3,
                    conn=conn,
                    bucket=bucket,
                )
            )

    return results