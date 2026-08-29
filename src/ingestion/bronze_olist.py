"""Ingest the four Sprint 1 Olist source CSVs into the Bronze layer.

The Bronze layer preserves source values and schema as closely as practical while
changing the persisted format from CSV to Parquet. No cleaning or quality-based
row rejection is performed here; those responsibilities belong to later Silver
and Quarantine steps.
"""

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


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = PROJECT_ROOT / "config" / "pilot_olist.json"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_contract(path: Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_source_file(path: Path, required_columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing Olist source file: {path}")

    frame = pd.read_csv(path, dtype_backend="numpy_nullable")
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{path.name} is missing required columns: {missing}")
    return frame


def minio_client():
    endpoint = os.environ["MINIO_ENDPOINT"]
    access_key = os.environ["MINIO_ROOT_USER"]
    secret_key = os.environ["MINIO_ROOT_PASSWORD"]
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
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


def ensure_control_plane_records(conn: psycopg.Connection, table_code: str) -> tuple[int, int]:
    """Create/reuse Alpha client/project/source/dataset metadata.

    Returns (dataset_id, dataset_version_id placeholder is created separately).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO client (client_code, client_name)
            VALUES (%s, %s)
            ON CONFLICT (client_code) DO UPDATE SET client_name = EXCLUDED.client_name
            RETURNING client_id
            """,
            ("olist", "Olist public e-commerce pilot"),
        )
        client_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO project (client_id, project_code, project_name)
            VALUES (%s, %s, %s)
            ON CONFLICT (project_code) DO UPDATE SET project_name = EXCLUDED.project_name
            RETURNING project_id
            """,
            (client_id, "olist-alpha", "DataForge Sprint 1 Alpha"),
        )
        project_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO data_source (project_id, source_code, source_type, source_name, connection_reference)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (project_id, source_code)
            DO UPDATE SET source_name = EXCLUDED.source_name, connection_reference = EXCLUDED.connection_reference
            RETURNING source_id
            """,
            (project_id, "olist-csv", "csv", "Olist Kaggle CSV export", "data/raw/olist"),
        )
        source_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO dataset (source_id, dataset_code, dataset_name, logical_entity, classification, owner_name)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_id, dataset_code)
            DO UPDATE SET dataset_name = EXCLUDED.dataset_name, logical_entity = EXCLUDED.logical_entity
            RETURNING dataset_id
            """,
            (
                source_id,
                table_code,
                f"Olist {table_code}",
                table_code,
                "internal",
                "DataForge Sprint 1 team",
            ),
        )
        dataset_id = cur.fetchone()[0]

    return dataset_id


def register_dataset_version(
    conn: psycopg.Connection,
    dataset_id: int,
    checksum: str,
    columns: list[str],
) -> int:
    schema_hash = hashlib.sha256("|".join(columns).encode("utf-8")).hexdigest()
    version_label = checksum[:12]
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO dataset_version (dataset_id, version_label, schema_hash, source_checksum)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (dataset_id, version_label)
            DO UPDATE SET schema_hash = EXCLUDED.schema_hash, source_checksum = EXCLUDED.source_checksum
            RETURNING dataset_version_id
            """,
            (dataset_id, version_label, schema_hash, checksum),
        )
        return cur.fetchone()[0]


def start_pipeline_run(conn: psycopg.Connection, dataset_version_id: int, row_count: int) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO pipeline_run (dataset_version_id, run_type, status, input_rows)
            VALUES (%s, %s, %s, %s)
            RETURNING run_id
            """,
            (dataset_version_id, "source_to_bronze", "running", row_count),
        )
        return cur.fetchone()[0]


def finish_pipeline_run(
    conn: psycopg.Connection,
    run_id: int,
    status: str,
    accepted_rows: int | None = None,
    error_message: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE pipeline_run
            SET status = %s,
                finished_at = %s,
                accepted_rows = %s,
                rejected_rows = CASE WHEN %s = 'success' THEN 0 ELSE rejected_rows END,
                error_message = %s
            WHERE run_id = %s
            """,
            (status, utc_now(), accepted_rows, status, error_message, run_id),
        )


def register_bronze_asset(
    conn: psycopg.Connection,
    run_id: int,
    asset_name: str,
    storage_uri: str,
    row_count: int,
    checksum: str,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO data_asset (run_id, layer, asset_name, storage_uri, format, row_count, checksum)
            VALUES (%s, 'bronze', %s, %s, 'parquet', %s, %s)
            """,
            (run_id, asset_name, storage_uri, row_count, checksum),
        )


def ingest_table(
    table_code: str,
    table_config: dict[str, Any],
    raw_directory: Path,
    s3,
    conn: psycopg.Connection,
    bucket: str,
) -> dict[str, Any]:
    source_path = raw_directory / table_config["file"]
    frame = validate_source_file(source_path, table_config["required_columns"])
    source_checksum = sha256_file(source_path)

    dataset_id = ensure_control_plane_records(conn, table_code)
    dataset_version_id = register_dataset_version(
        conn, dataset_id, source_checksum, [str(column) for column in frame.columns]
    )
    run_id = start_pipeline_run(conn, dataset_version_id, len(frame))
    conn.commit()

    object_key = f"olist/{table_code}/source_checksum={source_checksum[:12]}/{table_code}.parquet"
    storage_uri = f"s3://{bucket}/{object_key}"

    try:
        with tempfile.TemporaryDirectory(prefix="dataforge-bronze-") as tmpdir:
            parquet_path = Path(tmpdir) / f"{table_code}.parquet"
            frame.to_parquet(parquet_path, index=False, engine="pyarrow")
            parquet_checksum = sha256_file(parquet_path)
            s3.upload_file(str(parquet_path), bucket, object_key)

        register_bronze_asset(
            conn,
            run_id=run_id,
            asset_name=f"olist_{table_code}_bronze",
            storage_uri=storage_uri,
            row_count=len(frame),
            checksum=parquet_checksum,
        )
        finish_pipeline_run(conn, run_id, "success", accepted_rows=len(frame))
        conn.commit()
        return {
            "table": table_code,
            "rows": len(frame),
            "source_checksum": source_checksum,
            "storage_uri": storage_uri,
            "run_id": run_id,
        }
    except Exception as exc:
        conn.rollback()
        finish_pipeline_run(conn, run_id, "failed", error_message=str(exc)[:2000])
        conn.commit()
        raise


def run_ingestion(contract_path: Path = DEFAULT_CONTRACT) -> list[dict[str, Any]]:
    load_dotenv(PROJECT_ROOT / ".env")
    contract = load_contract(contract_path)
    raw_directory = PROJECT_ROOT / contract["raw_directory"]
    bucket = os.environ.get("MINIO_BUCKET_BRONZE", "dataforge-bronze")

    s3 = minio_client()
    results: list[dict[str, Any]] = []
    with postgres_connection() as conn:
        for table_code, table_config in contract["tables"].items():
            results.append(
                ingest_table(
                    table_code=table_code,
                    table_config=table_config,
                    raw_directory=raw_directory,
                    s3=s3,
                    conn=conn,
                    bucket=bucket,
                )
            )
    return results


def main() -> None:
    results = run_ingestion()
    print("Bronze ingestion completed")
    for item in results:
        print(f"- {item['table']}: {item['rows']} rows -> {item['storage_uri']} (run_id={item['run_id']})")


if __name__ == "__main__":
    main()
