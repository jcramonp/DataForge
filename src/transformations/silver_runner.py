"""Generic Silver transformation and Quality Gate execution runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from dotenv import load_dotenv
import pandas as pd
import psycopg

from src.contracts.loader import load_contract
from src.contracts.models import DataForgeContract, DatasetConfig
from src.quality.quality_generic import evaluate_quality_rules
from src.transformations.silver_generic import transform_dataset

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_s3_uri(storage_uri: str) -> tuple[str, str]:
    parsed = urlparse(storage_uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path.lstrip("/"):
        raise ValueError(f"Invalid S3 URI: {storage_uri}")
    return parsed.netloc, parsed.path.lstrip("/")


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


def latest_bronze_asset(
    conn: psycopg.Connection,
    client_code: str,
    dataset_code: str,
) -> dict[str, Any]:
    """Retrieve the most recent successful Bronze asset for a dataset."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                pr.dataset_version_id,
                da.checksum,
                da.storage_uri,
                da.row_count
            FROM client c
            JOIN project p ON p.client_id = c.client_id
            JOIN data_source ds ON ds.project_id = p.project_id
            JOIN dataset d ON d.source_id = ds.source_id
            JOIN dataset_version dv ON dv.dataset_id = d.dataset_id
            JOIN pipeline_run pr ON pr.dataset_version_id = dv.dataset_version_id
            JOIN data_asset da ON da.run_id = pr.run_id
            WHERE c.client_code = %s
              AND d.dataset_code = %s
              AND pr.run_type = 'source_to_bronze'
              AND pr.status = 'success'
              AND da.layer = 'bronze'
            ORDER BY pr.finished_at DESC NULLS LAST, pr.run_id DESC
            LIMIT 1
            """,
            (client_code, dataset_code),
        )
        row = cur.fetchone()

    if row is None:
        raise RuntimeError(
            f"No successful Bronze asset found for dataset '{dataset_code}' (client '{client_code}')"
        )

    return {
        "dataset_version_id": row[0],
        "source_checksum": row[1],
        "storage_uri": row[2],
        "row_count": row[3],
    }


def start_pipeline_run(
    conn: psycopg.Connection,
    dataset_version_id: int,
    input_rows: int,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO pipeline_run (
                dataset_version_id,
                run_type,
                status,
                input_rows
            )
            VALUES (%s, 'silver_quality_gate', 'running', %s)
            RETURNING run_id
            """,
            (dataset_version_id, input_rows),
        )
        return cur.fetchone()[0]


def record_quality_results(
    conn: psycopg.Connection,
    run_id: int,
    results: list[dict[str, Any]],
) -> None:
    with conn.cursor() as cur:
        for item in results:
            cur.execute(
                """
                INSERT INTO quality_result (
                    run_id,
                    rule_name,
                    rule_type,
                    status,
                    failed_rows,
                    failure_percentage,
                    details_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    run_id,
                    item["rule_name"],
                    item["rule_type"],
                    item["status"],
                    item["failed_rows"],
                    item["failure_percentage"],
                    json.dumps(
                        {
                            "column": item["column"],
                            "severity": item["severity"],
                            "gx_success": item.get("gx_success"),
                        }
                    ),
                ),
            )


def register_data_asset(
    conn: psycopg.Connection,
    run_id: int,
    layer: str,
    asset_name: str,
    storage_uri: str,
    row_count: int,
    checksum: str,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
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
            VALUES (%s, %s, %s, %s, 'parquet', %s, %s)
            """,
            (run_id, layer, asset_name, storage_uri, row_count, checksum),
        )


def finish_pipeline_run(
    conn: psycopg.Connection,
    run_id: int,
    status: str,
    accepted_rows: int | None = None,
    rejected_rows: int | None = None,
    error_message: str | None = None,
) -> None:
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


def execute_silver_pipeline_for_dataset(
    contract: DataForgeContract,
    dataset_code: str,
    s3,
    conn: psycopg.Connection,
    silver_bucket: str,
    quarantine_bucket: str,
) -> dict[str, Any]:
    """Execute Silver transformations and Quality Gate for one dataset."""
    dataset = next((d for d in contract.datasets if d.code == dataset_code), None)
    if dataset is None:
        raise ValueError(f"Dataset '{dataset_code}' not found in contract")

    client_code = contract.client.code
    project_code = contract.project.code

    bronze = latest_bronze_asset(conn, client_code, dataset.code)
    bronze_bucket, bronze_key = parse_s3_uri(bronze["storage_uri"])

    run_id = start_pipeline_run(
        conn,
        bronze["dataset_version_id"],
        int(bronze["row_count"]),
    )
    conn.commit()

    source_checksum = bronze["source_checksum"]
    checksum12 = source_checksum[:12]

    try:
        with tempfile.TemporaryDirectory(prefix="dataforge-silver-") as tmpdir:
            bronze_path = Path(tmpdir) / f"{dataset.code}_bronze.parquet"
            valid_path = Path(tmpdir) / f"{dataset.code}_validated.parquet"
            quarantine_path = Path(tmpdir) / f"{dataset.code}_quarantine.parquet"

            # 1. Download Bronze
            s3.download_file(bronze_bucket, bronze_key, str(bronze_path))
            bronze_frame = pd.read_parquet(bronze_path, engine="pyarrow")

            # 2. Apply Silver transformations
            silver_frame = transform_dataset(bronze_frame, dataset)

            # 3. Evaluate Quality rules & partition
            validated_frame, quarantine_frame, quality_results = evaluate_quality_rules(
                silver_frame,
                dataset.quality.rules,
                dataset_code=dataset.code,
            )

            # 4. Upload Validated Silver
            valid_key = (
                f"{client_code}/{project_code}/{dataset.code}/"
                f"source_checksum={checksum12}/validated_v1/{dataset.code}.parquet"
            )
            valid_uri = f"s3://{silver_bucket}/{valid_key}"
            validated_frame.to_parquet(valid_path, index=False, engine="pyarrow")
            valid_checksum = sha256_file(valid_path)
            s3.upload_file(str(valid_path), silver_bucket, valid_key)

            register_data_asset(
                conn,
                run_id=run_id,
                layer="silver",
                asset_name=f"{client_code}_{dataset.code}_silver_validated",
                storage_uri=valid_uri,
                row_count=len(validated_frame),
                checksum=valid_checksum,
            )

            # 5. Upload Quarantine if failing critical records exist
            quarantine_uri = None
            if len(quarantine_frame) > 0:
                quarantine_key = (
                    f"{client_code}/{project_code}/{dataset.code}/"
                    f"source_checksum={checksum12}/quality_v1/{dataset.code}.parquet"
                )
                quarantine_uri = f"s3://{quarantine_bucket}/{quarantine_key}"
                quarantine_frame.to_parquet(quarantine_path, index=False, engine="pyarrow")
                quarantine_checksum = sha256_file(quarantine_path)
                s3.upload_file(str(quarantine_path), quarantine_bucket, quarantine_key)

                register_data_asset(
                    conn,
                    run_id=run_id,
                    layer="quarantine",
                    asset_name=f"{client_code}_{dataset.code}_quarantine",
                    storage_uri=quarantine_uri,
                    row_count=len(quarantine_frame),
                    checksum=quarantine_checksum,
                )

        # 6. Record quality results & complete pipeline run
        record_quality_results(conn, run_id, quality_results)
        finish_pipeline_run(
            conn,
            run_id,
            status="success",
            accepted_rows=len(validated_frame),
            rejected_rows=len(quarantine_frame),
        )
        conn.commit()

        return {
            "dataset": dataset.code,
            "input_rows": len(bronze_frame),
            "accepted_rows": len(validated_frame),
            "rejected_rows": len(quarantine_frame),
            "validated_uri": valid_uri,
            "quarantine_uri": quarantine_uri,
            "run_id": run_id,
            "quality_results": quality_results,
        }

    except Exception as exc:
        conn.rollback()
        finish_pipeline_run(
            conn,
            run_id,
            status="failed",
            error_message=str(exc)[:2000],
        )
        conn.commit()
        raise


def run_silver_pipeline(contract_path: str | Path) -> list[dict[str, Any]]:
    """Run Silver transformation and Quality Gate for all datasets in a contract."""
    load_dotenv(PROJECT_ROOT / ".env")
    silver_bucket = os.environ.get("MINIO_BUCKET_SILVER", "dataforge-silver")
    quarantine_bucket = os.environ.get("MINIO_BUCKET_QUARANTINE", "dataforge-quarantine")
    s3 = minio_client()

    contract = load_contract(contract_path)
    results: list[dict[str, Any]] = []

    with postgres_connection() as conn:
        for dataset in contract.datasets:
            results.append(
                execute_silver_pipeline_for_dataset(
                    contract=contract,
                    dataset_code=dataset.code,
                    s3=s3,
                    conn=conn,
                    silver_bucket=silver_bucket,
                    quarantine_bucket=quarantine_bucket,
                )
            )

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run generic Silver transformation and Quality Gate"
    )
    parser.add_argument(
        "--contract",
        type=Path,
        required=True,
        help="Path to YAML/JSON contract file",
    )
    args = parser.parse_args()

    results = run_silver_pipeline(args.contract)
    print("Generic Silver + Quality Gate completed:")
    for res in results:
        print(
            f"- {res['dataset']}: {res['input_rows']} input, "
            f"{res['accepted_rows']} accepted, {res['rejected_rows']} quarantined "
            f"(run_id={res['run_id']})"
        )


if __name__ == "__main__":
    main()
