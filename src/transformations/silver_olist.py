"""Transform verified Olist Bronze Parquet assets into baseline Silver assets.

This Sprint 1 step standardizes types and selected textual fields while preserving
row counts. Formal data-quality acceptance/rejection and Quarantine routing are
implemented separately in the next checklist step with Great Expectations.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import boto3
import pandas as pd
import psycopg
from botocore.client import Config
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALPHA_TABLES = ("customers", "orders", "order_items", "products")
SILVER_TRANSFORMATION_VERSION = "v1"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
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


def parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        raise ValueError(f"Invalid S3 URI: {uri}")
    return parsed.netloc, parsed.path.lstrip("/")


def latest_bronze_asset(conn: psycopg.Connection, table_code: str) -> dict[str, Any]:
    """Return the newest successful Bronze asset for one contracted Olist table."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT dv.dataset_version_id,
                   dv.source_checksum,
                   da.storage_uri,
                   da.row_count
            FROM client c
            JOIN project p ON p.client_id = c.client_id
            JOIN data_source ds ON ds.project_id = p.project_id
            JOIN dataset d ON d.source_id = ds.source_id
            JOIN dataset_version dv ON dv.dataset_id = d.dataset_id
            JOIN pipeline_run pr ON pr.dataset_version_id = dv.dataset_version_id
            JOIN data_asset da ON da.run_id = pr.run_id
            WHERE c.client_code = 'olist'
              AND p.project_code = 'olist-alpha'
              AND ds.source_code = 'olist-csv'
              AND d.dataset_code = %s
              AND pr.run_type = 'source_to_bronze'
              AND pr.status = 'success'
              AND da.layer = 'bronze'
            ORDER BY pr.finished_at DESC NULLS LAST, pr.run_id DESC
            LIMIT 1
            """,
            (table_code,),
        )
        row = cur.fetchone()
    if row is None:
        raise RuntimeError(f"No successful Bronze asset found for table '{table_code}'")
    return {
        "dataset_version_id": row[0],
        "source_checksum": row[1],
        "storage_uri": row[2],
        "row_count": row[3],
    }


def normalize_string(series: pd.Series, case: str | None = None) -> pd.Series:
    result = series.astype("string").str.strip()
    if case == "lower":
        result = result.str.lower()
    elif case == "upper":
        result = result.str.upper()
    return result


def transform_customers(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in ("customer_id", "customer_unique_id"):
        result[column] = normalize_string(result[column])
    result["customer_zip_code_prefix"] = pd.to_numeric(
        result["customer_zip_code_prefix"], errors="coerce"
    ).astype("Int64")
    result["customer_city"] = normalize_string(result["customer_city"], "lower")
    result["customer_state"] = normalize_string(result["customer_state"], "upper")
    return result


def transform_orders(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in ("order_id", "customer_id"):
        result[column] = normalize_string(result[column])
    result["order_status"] = normalize_string(result["order_status"], "lower")
    timestamp_columns = (
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    )
    for column in timestamp_columns:
        result[column] = pd.to_datetime(result[column], errors="coerce")
    return result


def transform_order_items(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in ("order_id", "product_id", "seller_id"):
        result[column] = normalize_string(result[column])
    result["order_item_id"] = pd.to_numeric(result["order_item_id"], errors="coerce").astype("Int64")
    result["shipping_limit_date"] = pd.to_datetime(result["shipping_limit_date"], errors="coerce")
    for column in ("price", "freight_value"):
        result[column] = pd.to_numeric(result[column], errors="coerce").astype("Float64")
    return result


def transform_products(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result = result.rename(
        columns={
            "product_name_lenght": "product_name_length",
            "product_description_lenght": "product_description_length",
        }
    )
    result["product_id"] = normalize_string(result["product_id"])
    result["product_category_name"] = normalize_string(
        result["product_category_name"], "lower"
    )
    integer_columns = (
        "product_name_length",
        "product_description_length",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    )
    for column in integer_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce").astype("Int64")
    return result


TRANSFORMERS = {
    "customers": transform_customers,
    "orders": transform_orders,
    "order_items": transform_order_items,
    "products": transform_products,
}


def start_pipeline_run(conn: psycopg.Connection, dataset_version_id: int, row_count: int) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO pipeline_run (dataset_version_id, run_type, status, input_rows)
            VALUES (%s, 'bronze_to_silver', 'running', %s)
            RETURNING run_id
            """,
            (dataset_version_id, row_count),
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


def register_silver_asset(
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
            VALUES (%s, 'silver', %s, %s, 'parquet', %s, %s)
            """,
            (run_id, asset_name, storage_uri, row_count, checksum),
        )


def transform_table(
    table_code: str,
    s3,
    conn: psycopg.Connection,
    silver_bucket: str,
) -> dict[str, Any]:
    bronze = latest_bronze_asset(conn, table_code)
    bronze_bucket, bronze_key = parse_s3_uri(bronze["storage_uri"])

    run_id = start_pipeline_run(conn, bronze["dataset_version_id"], int(bronze["row_count"]))
    conn.commit()

    source_checksum = bronze["source_checksum"]
    silver_key = (
        f"olist/{table_code}/source_checksum={source_checksum[:12]}/"
        f"silver_{SILVER_TRANSFORMATION_VERSION}/{table_code}.parquet"
    )
    silver_uri = f"s3://{silver_bucket}/{silver_key}"

    try:
        with tempfile.TemporaryDirectory(prefix="dataforge-silver-") as tmpdir:
            bronze_path = Path(tmpdir) / f"{table_code}_bronze.parquet"
            silver_path = Path(tmpdir) / f"{table_code}_silver.parquet"
            s3.download_file(bronze_bucket, bronze_key, str(bronze_path))

            bronze_frame = pd.read_parquet(bronze_path, engine="pyarrow")
            silver_frame = TRANSFORMERS[table_code](bronze_frame)

            if len(silver_frame) != len(bronze_frame):
                raise RuntimeError(
                    f"Silver transformation changed row count for {table_code}: "
                    f"{len(bronze_frame)} -> {len(silver_frame)}"
                )

            silver_frame.to_parquet(silver_path, index=False, engine="pyarrow")
            silver_checksum = sha256_file(silver_path)
            s3.upload_file(str(silver_path), silver_bucket, silver_key)

        register_silver_asset(
            conn,
            run_id=run_id,
            asset_name=f"olist_{table_code}_silver",
            storage_uri=silver_uri,
            row_count=len(silver_frame),
            checksum=silver_checksum,
        )
        finish_pipeline_run(conn, run_id, "success", accepted_rows=len(silver_frame))
        conn.commit()
        return {
            "table": table_code,
            "rows": len(silver_frame),
            "storage_uri": silver_uri,
            "run_id": run_id,
        }
    except Exception as exc:
        conn.rollback()
        finish_pipeline_run(conn, run_id, "failed", error_message=str(exc)[:2000])
        conn.commit()
        raise


def run_transformation() -> list[dict[str, Any]]:
    load_dotenv(PROJECT_ROOT / ".env")
    silver_bucket = os.environ.get("MINIO_BUCKET_SILVER", "dataforge-silver")
    s3 = minio_client()
    results: list[dict[str, Any]] = []
    with postgres_connection() as conn:
        for table_code in ALPHA_TABLES:
            results.append(transform_table(table_code, s3, conn, silver_bucket))
    return results


def main() -> None:
    results = run_transformation()
    print("Silver transformation completed")
    for item in results:
        print(
            f"- {item['table']}: {item['rows']} rows -> "
            f"{item['storage_uri']} (run_id={item['run_id']})"
        )


if __name__ == "__main__":
    main()
