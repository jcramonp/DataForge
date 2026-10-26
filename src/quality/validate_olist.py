"""Validate baseline Silver Olist assets with Great Expectations and route invalid rows.

This Sprint 1 quality gate reads the latest successful baseline Silver asset for each
Alpha table, evaluates explicit GX Expectations, records rule results in PostgreSQL,
and writes validated Silver plus row-level Quarantine Parquet outputs.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import great_expectations as gx
import pandas as pd
import psycopg
from src.common.clients import connect_postgres, create_s3_client
from src.common.settings import load_environment_file

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALPHA_TABLES = ("customers", "orders", "order_items", "products")
QUALITY_VERSION = "v1"


@dataclass(frozen=True)
class QualityRule:
    name: str
    rule_type: str
    expectation_factory: Callable[[], Any]
    invalid_mask: Callable[[pd.DataFrame], pd.Series]
    severity: str = "critical"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def minio_client():
    return create_s3_client()


def postgres_connection():
    return connect_postgres()


def parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        raise ValueError(f"Invalid S3 URI: {uri}")
    return parsed.netloc, parsed.path.lstrip("/")


def latest_baseline_silver_asset(conn: psycopg.Connection, table_code: str) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT dv.dataset_version_id, dv.source_checksum, da.storage_uri, da.row_count
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
              AND pr.run_type = 'bronze_to_silver'
              AND pr.status = 'success'
              AND da.layer = 'silver'
            ORDER BY pr.finished_at DESC NULLS LAST, pr.run_id DESC
            LIMIT 1
            """,
            (table_code,),
        )
        row = cur.fetchone()
    if row is None:
        raise RuntimeError(f"No successful baseline Silver asset found for '{table_code}'")
    return {
        "dataset_version_id": row[0],
        "source_checksum": row[1],
        "storage_uri": row[2],
        "row_count": row[3],
    }


def non_null_mask(column: str) -> Callable[[pd.DataFrame], pd.Series]:
    return lambda df: df[column].isna()


def between_mask(column: str, min_value: float | None = None, max_value: float | None = None, *, allow_null: bool = True) -> Callable[[pd.DataFrame], pd.Series]:
    def mask(df: pd.DataFrame) -> pd.Series:
        series = pd.to_numeric(df[column], errors="coerce")
        invalid = pd.Series(False, index=df.index)
        if min_value is not None:
            invalid |= series < min_value
        if max_value is not None:
            invalid |= series > max_value
        if not allow_null:
            invalid |= series.isna()
        return invalid.fillna(False)
    return mask


def in_set_mask(column: str, values: set[str]) -> Callable[[pd.DataFrame], pd.Series]:
    return lambda df: (~df[column].isin(values) & df[column].notna()).fillna(False)


def regex_mask(column: str, pattern: str) -> Callable[[pd.DataFrame], pd.Series]:
    return lambda df: (~df[column].astype("string").str.match(pattern, na=False) & df[column].notna()).fillna(False)


ORDER_STATUSES = {"approved", "canceled", "created", "delivered", "invoiced", "processing", "shipped", "unavailable"}

RULES: dict[str, list[QualityRule]] = {
    "customers": [
        QualityRule("customer_id_not_null", "completeness", lambda: gx.expectations.ExpectColumnValuesToNotBeNull(column="customer_id"), non_null_mask("customer_id")),
        QualityRule("customer_unique_id_not_null", "completeness", lambda: gx.expectations.ExpectColumnValuesToNotBeNull(column="customer_unique_id"), non_null_mask("customer_unique_id")),
        QualityRule("customer_state_format", "validity", lambda: gx.expectations.ExpectColumnValuesToMatchRegex(column="customer_state", regex=r"^[A-Z]{2}$"), regex_mask("customer_state", r"^[A-Z]{2}$")),
    ],
    "orders": [
        QualityRule("order_id_not_null", "completeness", lambda: gx.expectations.ExpectColumnValuesToNotBeNull(column="order_id"), non_null_mask("order_id")),
        QualityRule("order_customer_id_not_null", "completeness", lambda: gx.expectations.ExpectColumnValuesToNotBeNull(column="customer_id"), non_null_mask("customer_id")),
        QualityRule("purchase_timestamp_not_null", "completeness", lambda: gx.expectations.ExpectColumnValuesToNotBeNull(column="order_purchase_timestamp"), non_null_mask("order_purchase_timestamp")),
        QualityRule("order_status_allowed", "validity", lambda: gx.expectations.ExpectColumnValuesToBeInSet(column="order_status", value_set=sorted(ORDER_STATUSES)), in_set_mask("order_status", ORDER_STATUSES)),
    ],
    "order_items": [
        QualityRule("item_order_id_not_null", "completeness", lambda: gx.expectations.ExpectColumnValuesToNotBeNull(column="order_id"), non_null_mask("order_id")),
        QualityRule("item_product_id_not_null", "completeness", lambda: gx.expectations.ExpectColumnValuesToNotBeNull(column="product_id"), non_null_mask("product_id")),
        QualityRule("order_item_id_positive", "validity", lambda: gx.expectations.ExpectColumnValuesToBeBetween(column="order_item_id", min_value=1), between_mask("order_item_id", 1, allow_null=False)),
        QualityRule("price_positive", "validity", lambda: gx.expectations.ExpectColumnValuesToBeBetween(column="price", min_value=0.000001), between_mask("price", 0.000001, allow_null=False)),
        QualityRule("freight_nonnegative", "validity", lambda: gx.expectations.ExpectColumnValuesToBeBetween(column="freight_value", min_value=0), between_mask("freight_value", 0, allow_null=False)),
    ],
    "products": [
        QualityRule("product_id_not_null", "completeness", lambda: gx.expectations.ExpectColumnValuesToNotBeNull(column="product_id"), non_null_mask("product_id")),
        QualityRule("product_weight_positive_when_present", "validity", lambda: gx.expectations.ExpectColumnValuesToBeBetween(column="product_weight_g", min_value=1), between_mask("product_weight_g", 1, allow_null=True)),
        QualityRule("product_length_positive_when_present", "validity", lambda: gx.expectations.ExpectColumnValuesToBeBetween(column="product_length_cm", min_value=1), between_mask("product_length_cm", 1, allow_null=True)),
        QualityRule("product_height_positive_when_present", "validity", lambda: gx.expectations.ExpectColumnValuesToBeBetween(column="product_height_cm", min_value=1), between_mask("product_height_cm", 1, allow_null=True)),
        QualityRule("product_width_positive_when_present", "validity", lambda: gx.expectations.ExpectColumnValuesToBeBetween(column="product_width_cm", min_value=1), between_mask("product_width_cm", 1, allow_null=True)),
        QualityRule("product_category_present", "completeness", lambda: gx.expectations.ExpectColumnValuesToNotBeNull(column="product_category_name", mostly=0.98), non_null_mask("product_category_name"), severity="warning"),
    ],
}


def build_gx_batch(frame: pd.DataFrame, table_code: str):
    os.environ.setdefault("GX_ANALYTICS_ENABLED", "false")
    context = gx.get_context(mode="ephemeral")
    datasource = context.data_sources.add_pandas(f"olist_{table_code}_pandas")
    asset = datasource.add_dataframe_asset(name=f"olist_{table_code}_silver")
    definition = asset.add_batch_definition_whole_dataframe("whole_dataframe")
    return definition.get_batch(batch_parameters={"dataframe": frame})


def evaluate_rules(frame: pd.DataFrame, table_code: str) -> tuple[list[dict[str, Any]], pd.Series]:
    batch = build_gx_batch(frame, table_code)
    quarantine_mask = pd.Series(False, index=frame.index)
    results: list[dict[str, Any]] = []
    for rule in RULES[table_code]:
        validation = batch.validate(rule.expectation_factory())
        invalid = rule.invalid_mask(frame).astype(bool)
        failed_rows = int(invalid.sum())
        if rule.severity == "critical":
            quarantine_mask |= invalid
        results.append({
            "rule_name": rule.name,
            "rule_type": rule.rule_type,
            "severity": rule.severity,
            "status": "pass" if bool(validation.success) else "fail",
            "failed_rows": failed_rows,
            "failure_percentage": (failed_rows / len(frame) * 100.0) if len(frame) else 0.0,
            "gx_success": bool(validation.success),
        })
    return results, quarantine_mask


def start_run(conn: psycopg.Connection, dataset_version_id: int, row_count: int) -> int:
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO pipeline_run (dataset_version_id, run_type, status, input_rows)
            VALUES (%s, 'silver_quality_gate', 'running', %s)
            RETURNING run_id
        """, (dataset_version_id, row_count))
        return cur.fetchone()[0]


def record_quality_results(conn: psycopg.Connection, run_id: int, results: list[dict[str, Any]]) -> None:
    with conn.cursor() as cur:
        for item in results:
            cur.execute("""
                INSERT INTO quality_result (run_id, rule_name, rule_type, status, failed_rows, failure_percentage, details_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            """, (
                run_id, item["rule_name"], item["rule_type"], item["status"], item["failed_rows"],
                item["failure_percentage"], json.dumps({"severity": item["severity"], "gx_success": item["gx_success"]})
            ))


def register_asset(conn: psycopg.Connection, run_id: int, layer: str, asset_name: str, storage_uri: str, row_count: int, checksum: str) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO data_asset (run_id, layer, asset_name, storage_uri, format, row_count, checksum)
            VALUES (%s, %s, %s, %s, 'parquet', %s, %s)
        """, (run_id, layer, asset_name, storage_uri, row_count, checksum))


def finish_run(conn: psycopg.Connection, run_id: int, status: str, accepted_rows: int | None = None, rejected_rows: int | None = None, error_message: str | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE pipeline_run
            SET status=%s, finished_at=%s, accepted_rows=%s, rejected_rows=%s, error_message=%s
            WHERE run_id=%s
        """, (status, utc_now(), accepted_rows, rejected_rows, error_message, run_id))


def validate_table(table_code: str, s3, conn: psycopg.Connection, silver_bucket: str, quarantine_bucket: str) -> dict[str, Any]:
    source = latest_baseline_silver_asset(conn, table_code)
    source_bucket, source_key = parse_s3_uri(source["storage_uri"])
    run_id = start_run(conn, source["dataset_version_id"], int(source["row_count"]))
    conn.commit()
    checksum12 = source["source_checksum"][:12]

    try:
        with tempfile.TemporaryDirectory(prefix="dataforge-quality-") as tmpdir:
            source_path = Path(tmpdir) / f"{table_code}_silver.parquet"
            valid_path = Path(tmpdir) / f"{table_code}_validated.parquet"
            quarantine_path = Path(tmpdir) / f"{table_code}_quarantine.parquet"
            s3.download_file(source_bucket, source_key, str(source_path))
            frame = pd.read_parquet(source_path, engine="pyarrow")
            results, quarantine_mask = evaluate_rules(frame, table_code)
            valid_frame = frame.loc[~quarantine_mask].copy()
            quarantine_frame = frame.loc[quarantine_mask].copy()

            valid_key = f"olist/{table_code}/source_checksum={checksum12}/validated_{QUALITY_VERSION}/{table_code}.parquet"
            valid_uri = f"s3://{silver_bucket}/{valid_key}"
            valid_frame.to_parquet(valid_path, index=False, engine="pyarrow")
            valid_checksum = sha256_file(valid_path)
            s3.upload_file(str(valid_path), silver_bucket, valid_key)
            register_asset(conn, run_id, "silver", f"olist_{table_code}_silver_validated", valid_uri, len(valid_frame), valid_checksum)

            quarantine_uri = None
            if len(quarantine_frame):
                quarantine_key = f"olist/{table_code}/source_checksum={checksum12}/quality_{QUALITY_VERSION}/{table_code}.parquet"
                quarantine_uri = f"s3://{quarantine_bucket}/{quarantine_key}"
                quarantine_frame.to_parquet(quarantine_path, index=False, engine="pyarrow")
                quarantine_checksum = sha256_file(quarantine_path)
                s3.upload_file(str(quarantine_path), quarantine_bucket, quarantine_key)
                register_asset(conn, run_id, "quarantine", f"olist_{table_code}_quarantine", quarantine_uri, len(quarantine_frame), quarantine_checksum)

        record_quality_results(conn, run_id, results)
        finish_run(conn, run_id, "success", len(valid_frame), len(quarantine_frame))
        conn.commit()
        return {
            "table": table_code,
            "input_rows": len(frame),
            "accepted_rows": len(valid_frame),
            "rejected_rows": len(quarantine_frame),
            "validated_uri": valid_uri,
            "quarantine_uri": quarantine_uri,
            "run_id": run_id,
        }
    except Exception as exc:
        conn.rollback()
        finish_run(conn, run_id, "failed", error_message=str(exc)[:2000])
        conn.commit()
        raise


def run_quality_gate() -> list[dict[str, Any]]:
    load_environment_file()
    silver_bucket = os.environ.get("MINIO_BUCKET_SILVER", "dataforge-silver")
    quarantine_bucket = os.environ.get("MINIO_BUCKET_QUARANTINE", "dataforge-quarantine")
    s3 = minio_client()
    results: list[dict[str, Any]] = []
    with postgres_connection() as conn:
        for table_code in ALPHA_TABLES:
            results.append(validate_table(table_code, s3, conn, silver_bucket, quarantine_bucket))
    return results


def main() -> None:
    results = run_quality_gate()
    print("Quality gate completed")
    for item in results:
        print(
            f"- {item['table']}: {item['input_rows']} input, {item['accepted_rows']} accepted, "
            f"{item['rejected_rows']} quarantined (run_id={item['run_id']})"
        )


if __name__ == "__main__":
    main()
