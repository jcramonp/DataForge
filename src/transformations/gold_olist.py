"""Build the Sprint 1 Alpha Olist Gold dataset from validated Silver assets.

The Gold dataset is an integrated analytical table at order-item grain. The
transformation resolves the latest successful validated Silver asset for each
Alpha table from PostgreSQL metadata, downloads those Parquet files from MinIO,
joins them, derives item_total, writes the Gold Parquet asset, and registers the
result in the DataForge control-plane tables.
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

from src.governance.metadata import dataframe_schema_hash
from src.governance.lineage import register_lineage_edges

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALPHA_TABLES = ("customers", "orders", "order_items", "products")
GOLD_VERSION = "v1"
GOLD_DATASET_CODE = "order_items_gold"


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


def latest_validated_silver_asset(conn: psycopg.Connection, table_code: str) -> dict[str, Any]:
    """Resolve the latest successful validated Silver asset for one Alpha table."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT da.asset_id,
                   dv.dataset_version_id,
                   dv.source_checksum,
                   da.storage_uri,
                   da.row_count,
                   pr.run_id
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
              AND pr.run_type = 'silver_quality_gate'
              AND pr.status = 'success'
              AND da.layer = 'silver'
              AND da.asset_name = %s
            ORDER BY pr.finished_at DESC NULLS LAST, pr.run_id DESC
            LIMIT 1
            """,
            (table_code, f"olist_{table_code}_silver_validated"),
        )
        row = cur.fetchone()

    if row is None:
        raise RuntimeError(f"No successful validated Silver asset found for '{table_code}'")

    return {
        "asset_id": row[0],
        "dataset_version_id": row[1],
        "source_checksum": row[2],
        "storage_uri": row[3],
        "row_count": int(row[4]),
        "quality_run_id": row[5],
    }


def build_gold_dataset(
    customers: pd.DataFrame,
    orders: pd.DataFrame,
    order_items: pd.DataFrame,
    products: pd.DataFrame,
) -> pd.DataFrame:
    """Create the integrated order-item-grain Gold dataframe.

    Inner joins are intentional: Gold contains only records that can be resolved
    across the validated entities. Rows whose related product was quarantined do
    not enter Gold.
    """
    customers_projection = customers[["customer_id", "customer_state"]].copy()
    orders_projection = orders[[
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
    ]].copy()
    items_projection = order_items[[
        "order_id",
        "order_item_id",
        "product_id",
        "price",
        "freight_value",
    ]].copy()
    products_projection = products[["product_id", "product_category_name"]].copy()

    gold = items_projection.merge(
        orders_projection,
        on="order_id",
        how="inner",
        validate="many_to_one",
    )
    gold = gold.merge(
        customers_projection,
        on="customer_id",
        how="inner",
        validate="many_to_one",
    )
    gold = gold.merge(
        products_projection,
        on="product_id",
        how="inner",
        validate="many_to_one",
    )

    gold["item_total"] = (
        pd.to_numeric(gold["price"], errors="coerce")
        + pd.to_numeric(gold["freight_value"], errors="coerce")
    )

    ordered_columns = [
        "order_id",
        "order_item_id",
        "customer_id",
        "customer_state",
        "order_status",
        "order_purchase_timestamp",
        "product_id",
        "product_category_name",
        "price",
        "freight_value",
        "item_total",
    ]
    return gold[ordered_columns].copy()


def ensure_gold_dataset_version(conn: psycopg.Connection, source_checksums: dict[str, str]) -> int:
    """Create/reuse metadata objects for the integrated Gold logical dataset."""
    combined_checksum = hashlib.sha256(
        "|".join(f"{name}:{source_checksums[name]}" for name in sorted(source_checksums)).encode("utf-8")
    ).hexdigest()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ds.source_id
            FROM client c
            JOIN project p ON p.client_id = c.client_id
            JOIN data_source ds ON ds.project_id = p.project_id
            WHERE c.client_code = 'olist'
              AND p.project_code = 'olist-alpha'
              AND ds.source_code = 'olist-csv'
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("Olist Alpha data source metadata was not found")
        source_id = row[0]

        cur.execute(
            """
            INSERT INTO dataset (source_id, dataset_code, dataset_name, logical_entity, classification, owner_name)
            VALUES (%s, %s, %s, %s, 'internal', 'DataForge')
            ON CONFLICT (source_id, dataset_code)
            DO UPDATE SET dataset_name = EXCLUDED.dataset_name,
                          logical_entity = EXCLUDED.logical_entity
            RETURNING dataset_id
            """,
            (
                source_id,
                GOLD_DATASET_CODE,
                "Olist Gold Order Items",
                "integrated_order_item",
            ),
        )
        dataset_id = cur.fetchone()[0]

        version_label = f"gold-{combined_checksum[:12]}"
        cur.execute(
            """
            INSERT INTO dataset_version (dataset_id, version_label, schema_hash, source_checksum)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (dataset_id, version_label)
            DO UPDATE SET source_checksum = EXCLUDED.source_checksum
            RETURNING dataset_version_id
            """,
            (dataset_id, version_label, None, combined_checksum),
        )
        return cur.fetchone()[0]


def update_dataset_version_schema(
    conn: psycopg.Connection,
    dataset_version_id: int,
    frame: pd.DataFrame,
) -> None:
    """Persist the actual schema hash of a derived dataset."""

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE dataset_version
            SET schema_hash = %s
            WHERE dataset_version_id = %s
            """,
            (
                dataframe_schema_hash(
                    frame
                ),
                dataset_version_id,
            ),
        )


def start_run(conn: psycopg.Connection, dataset_version_id: int, input_rows: int) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO pipeline_run (dataset_version_id, run_type, status, input_rows)
            VALUES (%s, 'silver_to_gold', 'running', %s)
            RETURNING run_id
            """,
            (dataset_version_id, input_rows),
        )
        return cur.fetchone()[0]


def register_asset(
    conn: psycopg.Connection,
    run_id: int,
    storage_uri: str,
    row_count: int,
    checksum: str,
) -> int:
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
            VALUES (
                %s,
                'gold',
                'olist_order_items_gold',
                %s,
                'parquet',
                %s,
                %s
            )
            RETURNING asset_id
            """,
            (
                run_id,
                storage_uri,
                row_count,
                checksum,
            ),
        )

        return int(cur.fetchone()[0])


def finish_run(
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
            SET status=%s,
                finished_at=%s,
                accepted_rows=%s,
                rejected_rows=%s,
                error_message=%s
            WHERE run_id=%s
            """,
            (status, utc_now(), accepted_rows, rejected_rows, error_message, run_id),
        )


def run_gold_transformation() -> dict[str, Any]:
    load_dotenv(PROJECT_ROOT / ".env")
    gold_bucket = os.environ.get("MINIO_BUCKET_GOLD", "dataforge-gold")
    s3 = minio_client()

    with postgres_connection() as conn:
        sources = {
            table: latest_validated_silver_asset(conn, table)
            for table in ALPHA_TABLES
        }
        dataset_version_id = ensure_gold_dataset_version(
            conn,
            {table: metadata["source_checksum"] for table, metadata in sources.items()},
        )
        input_rows = sources["order_items"]["row_count"]
        run_id = start_run(conn, dataset_version_id, input_rows)
        conn.commit()

        try:
            with tempfile.TemporaryDirectory(prefix="dataforge-gold-") as tmpdir:
                frames: dict[str, pd.DataFrame] = {}
                for table, metadata in sources.items():
                    bucket, key = parse_s3_uri(metadata["storage_uri"])
                    local_path = Path(tmpdir) / f"{table}.parquet"
                    s3.download_file(bucket, key, str(local_path))
                    frames[table] = pd.read_parquet(local_path, engine="pyarrow")

                gold = build_gold_dataset(
                    frames["customers"],
                    frames["orders"],
                    frames["order_items"],
                    frames["products"],
                )

                update_dataset_version_schema(
                    conn,
                    dataset_version_id,
                    gold,
                )

                output_path = Path(tmpdir) / "olist_order_items_gold.parquet"
                gold.to_parquet(output_path, index=False, engine="pyarrow")
                checksum = sha256_file(output_path)
                key = f"olist/order_items/{GOLD_VERSION}/olist_order_items_gold.parquet"
                storage_uri = f"s3://{gold_bucket}/{key}"
                s3.upload_file(str(output_path), gold_bucket, key)

                gold_asset_id = register_asset(
                    conn,
                    run_id,
                    storage_uri,
                    len(gold),
                    checksum,
                )

                register_lineage_edges(
                    conn,
                    [
                        {
                            "parent_asset_id": int(
                                metadata["asset_id"]
                            ),
                            "child_asset_id": gold_asset_id,
                            "relation_type": "joined_from",
                            "created_by_run_id": run_id,
                            "metadata": {
                                "stage": "silver_to_gold",
                                "source_dataset": table_code,
                            },
                        }
                        for table_code, metadata
                        in sources.items()
                    ],
                )

                finish_run(
                    conn,
                    run_id,
                    "success",
                    accepted_rows=len(gold),
                    rejected_rows=input_rows - len(gold),
                )

                conn.commit()

                return {
                    "run_id": run_id,
                    "input_rows": input_rows,
                    "output_rows": len(gold),
                    "excluded_rows": input_rows - len(gold),
                    "storage_uri": storage_uri,
                }
        except Exception as exc:
            conn.rollback()
            finish_run(conn, run_id, "failed", error_message=str(exc)[:2000])
            conn.commit()
            raise


def main() -> None:
    result = run_gold_transformation()
    print("Gold transformation completed")
    print(
        f"- order_items_gold: {result['input_rows']} input order-items, "
        f"{result['output_rows']} Gold rows, {result['excluded_rows']} excluded "
        f"(run_id={result['run_id']})"
    )
    print(f"- {result['storage_uri']}")


if __name__ == "__main__":
    main()
