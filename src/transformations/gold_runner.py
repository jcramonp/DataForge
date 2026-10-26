"""Generic, contract-driven Gold pipeline execution runner for DataForge.

Resolves validated Silver assets from metadata, executes declarative transformation
plans across multiple datasets, uploads Gold analytical Parquet assets to MinIO/S3,
and records run lineage and assets in PostgreSQL control plane.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import psycopg

from src.common.clients import connect_postgres, create_s3_client
from src.common.log import bind_context, configure_logging, run_context
from src.common.settings import load_environment_file
from src.contracts.loader import load_contract
from src.contracts.models import DataForgeContract, GoldConfig, GoldOperation
from src.transformations.gold_generic import build_gold_dataset_from_plan
from src.governance.certification import evaluate_certification
from src.governance.lineage import register_lineage_edges
from src.governance.metadata import dataframe_schema_hash

logger = logging.getLogger("src.transformations.gold_runner")
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
    return create_s3_client()


def postgres_connection():
    return connect_postgres()


def latest_validated_silver_asset(
    conn: psycopg.Connection,
    client_code: str,
    project_code: str,
    source_code: str,
    dataset_code: str,
) -> dict[str, Any]:
    """Retrieve the latest validated Silver asset for one exact dataset."""

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                da.asset_id,
                dv.dataset_version_id,
                dv.source_checksum,
                da.storage_uri,
                da.row_count,
                pr.run_id
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
              AND pr.run_type = 'silver_quality_gate'
              AND pr.status = 'success'
              AND da.layer = 'silver'
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
            "No successful validated Silver asset found for "
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
        "silver_run_id": int(row[5]),
    }


def ensure_gold_dataset_version(
    conn: psycopg.Connection,
    client_code: str,
    project_code: str,
    source_code: str,
    gold_config: GoldConfig,
    source_checksums: dict[str, str],
) -> int:
    """Create or retrieve metadata objects for the integrated Gold dataset."""
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
            WHERE c.client_code = %s
              AND p.project_code = %s
              AND ds.source_code = %s
            LIMIT 1
            """,
            (
                client_code,
                project_code,
                source_code,
            ),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError(
                "Data source metadata was not found for "
                f"client='{client_code}', "
                f"project='{project_code}', "
                f"source='{source_code}'"
            )
        source_id = row[0]

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
            VALUES (%s, %s, %s, %s, 'internal', 'DataForge')
            ON CONFLICT (source_id, dataset_code)
            DO UPDATE SET
                dataset_name = EXCLUDED.dataset_name,
                logical_entity = EXCLUDED.logical_entity
            RETURNING dataset_id
            """,
            (
                source_id,
                gold_config.code,
                gold_config.name,
                f"gold_{gold_config.code}",
            ),
        )
        dataset_id = cur.fetchone()[0]

        version_label = f"gold-{combined_checksum[:12]}"
        cur.execute(
            """
            INSERT INTO dataset_version (
                dataset_id,
                version_label,
                schema_hash,
                source_checksum
            )
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
) -> str:
    """Persist and return the actual schema hash of a Gold dataset."""

    schema_hash = dataframe_schema_hash(frame)

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE dataset_version
            SET schema_hash = %s
            WHERE dataset_version_id = %s
            """,
            (
                schema_hash,
                dataset_version_id,
            ),
        )

    return schema_hash


def start_gold_pipeline_run(
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
            VALUES (%s, 'silver_to_gold', 'running', %s)
            RETURNING run_id
            """,
            (dataset_version_id, input_rows),
        )
        return cur.fetchone()[0]


def register_gold_asset(
    conn: psycopg.Connection,
    run_id: int,
    client_code: str,
    gold_code: str,
    storage_uri: str,
    row_count: int,
    checksum: str,
) -> int:
    """Register a Gold asset and return its identifier."""

    asset_name = f"{client_code}_{gold_code}"

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
                %s,
                %s,
                'parquet',
                %s,
                %s
            )
            RETURNING asset_id
            """,
            (
                run_id,
                asset_name,
                storage_uri,
                row_count,
                checksum,
            ),
        )

        row = cur.fetchone()

    if row is None:
        raise RuntimeError(
            f"Gold asset '{asset_name}' could not be registered."
        )

    return int(row[0])


def finish_gold_pipeline_run(
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


def execute_gold_pipeline_for_dataset(
    contract: DataForgeContract,
    gold_config: GoldConfig,
    s3,
    conn: psycopg.Connection,
    gold_bucket: str,
) -> dict[str, Any]:
    """Execute declarative Gold transformation plan for one Gold dataset."""
    with run_context(
        stage="silver_to_gold",
        client=contract.client.code,
        project=contract.project.code,
        dataset=gold_config.code,
    ):
        logger.info("Gold transformation started")
        try:
            result = _execute_gold_pipeline_for_dataset(
                contract, gold_config, s3, conn, gold_bucket
            )
        except Exception:
            logger.exception("Gold transformation failed")
            raise
        logger.info(
            "Gold transformation finished",
            extra={
                "input_rows": result["input_rows"],
                "output_rows": result["output_rows"],
                "storage_uri": result["storage_uri"],
            },
        )
        return result


def _execute_gold_pipeline_for_dataset(
    contract: DataForgeContract,
    gold_config: GoldConfig,
    s3,
    conn: psycopg.Connection,
    gold_bucket: str,
) -> dict[str, Any]:
    client_code = contract.client.code
    project_code = contract.project.code
    source_code = contract.source.code

    # Identify all datasets required by base and joins
    required_datasets = [gold_config.base_dataset]
    for step in gold_config.plan:
        if step.operation == GoldOperation.JOIN and step.right_dataset:
            if step.right_dataset not in required_datasets:
                required_datasets.append(step.right_dataset)

    # Resolve latest validated Silver metadata for each required dataset
    sources = {
        ds_code: latest_validated_silver_asset(
            conn=conn,
            client_code=client_code,
            project_code=project_code,
            source_code=source_code,
            dataset_code=ds_code,
        )
        for ds_code in required_datasets
    }

    dataset_version_id = ensure_gold_dataset_version(
        conn,
        client_code=client_code,
        project_code=project_code,
        source_code=source_code,
        gold_config=gold_config,
        source_checksums={
            ds: meta["source_checksum"]
            for ds, meta in sources.items()
        },
    )

    base_rows = sources[gold_config.base_dataset]["row_count"]
    run_id = start_gold_pipeline_run(conn, dataset_version_id, input_rows=base_rows)
    conn.commit()
    bind_context(run_id=run_id)

    try:
        with tempfile.TemporaryDirectory(prefix="dataforge-gold-") as tmpdir:
            frames: dict[str, pd.DataFrame] = {}
            for ds_code, meta in sources.items():
                bucket, key = parse_s3_uri(meta["storage_uri"])
                local_path = Path(tmpdir) / f"{ds_code}_silver.parquet"
                s3.download_file(bucket, key, str(local_path))
                frames[ds_code] = pd.read_parquet(local_path, engine="pyarrow")

            # Execute contract transformation plan
            gold_df = build_gold_dataset_from_plan(
                gold_config=gold_config,
                datasets_by_code=frames,
            )
            schema_hash = update_dataset_version_schema(
                conn=conn,
                dataset_version_id=dataset_version_id,
                frame=gold_df,
            )

            # Save and upload Gold Parquet
            gold_filename = f"{gold_config.code}.parquet"
            gold_path = Path(tmpdir) / gold_filename
            gold_df.to_parquet(gold_path, index=False, engine="pyarrow")
            gold_checksum = sha256_file(gold_path)

            gold_key = f"{client_code}/{project_code}/{gold_config.code}/gold_v1/{gold_filename}"
            storage_uri = f"s3://{gold_bucket}/{gold_key}"
            s3.upload_file(str(gold_path), gold_bucket, gold_key)

            gold_asset_id = register_gold_asset(
                conn,
                run_id=run_id,
                client_code=client_code,
                gold_code=gold_config.code,
                storage_uri=storage_uri,
                row_count=len(gold_df),
                checksum=gold_checksum,
            )

            relation_type = (
                "joined_from"
                if len(sources) > 1
                else "derived_from"
            )

            register_lineage_edges(
                conn,
                [
                    {
                        "parent_asset_id": metadata["asset_id"],
                        "child_asset_id": gold_asset_id,
                        "relation_type": relation_type,
                        "created_by_run_id": run_id,
                        "metadata": {
                            "stage": "silver_to_gold",
                            "source_dataset": dataset_code,
                            "gold_dataset": gold_config.code,
                        },
                    }
                    for dataset_code, metadata in sources.items()
                ],
            )

            finish_gold_pipeline_run(
                conn,
                run_id=run_id,
                status="success",
                accepted_rows=len(gold_df),
                rejected_rows=base_rows - len(gold_df),
            )
            certification = evaluate_certification(
                conn=conn,
                dataset_version_id=dataset_version_id,
            )
            conn.commit()

            return {
                "gold_code": gold_config.code,
                "dataset_version_id": dataset_version_id,
                "run_id": run_id,
                "input_rows": base_rows,
                "output_rows": len(gold_df),
                "excluded_rows": base_rows - len(gold_df),
                "storage_uri": storage_uri,
                "checksum": gold_checksum,
                "schema_hash": schema_hash,
                "gold_asset_id": gold_asset_id,
                "parent_asset_ids": {
                    dataset_code: metadata["asset_id"]
                    for dataset_code, metadata in sources.items()
                },
                "certification": certification,
            }

    except Exception as exc:
        conn.rollback()
        finish_gold_pipeline_run(
            conn,
            run_id=run_id,
            status="failed",
            error_message=str(exc)[:2000],
        )
        conn.commit()
        raise


def run_gold_pipeline(
    contract_path: str | Path,
    gold_code: str | None = None,
) -> list[dict[str, Any]]:
    """Run Gold transformation pipeline for datasets defined in contract."""
    load_environment_file()
    gold_bucket = os.environ.get("MINIO_BUCKET_GOLD", "dataforge-gold")
    s3 = minio_client()

    contract = load_contract(contract_path)
    results: list[dict[str, Any]] = []

    targets = [
        g for g in contract.gold
        if g.enabled and (gold_code is None or g.code == gold_code)
    ]

    if not targets:
        logger.warning("No enabled Gold datasets found in contract to execute")
        return []

    with postgres_connection() as conn:
        for gold_config in targets:
            res = execute_gold_pipeline_for_dataset(
                contract=contract,
                gold_config=gold_config,
                s3=s3,
                conn=conn,
                gold_bucket=gold_bucket,
            )
            results.append(res)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run generic contract-driven Gold transformations"
    )
    parser.add_argument(
        "--contract",
        type=Path,
        required=True,
        help="Path to YAML/JSON contract file",
    )
    parser.add_argument(
        "--gold-code",
        type=str,
        default=None,
        help="Optional specific Gold dataset code to run",
    )
    args = parser.parse_args()

    configure_logging()
    results = run_gold_pipeline(args.contract, gold_code=args.gold_code)
    print("Generic Gold transformation completed:")
    for res in results:
        print(
            f"- {res['gold_code']}: {res['input_rows']} input base rows, "
            f"{res['output_rows']} Gold rows, {res['excluded_rows']} excluded "
            f"(run_id={res['run_id']})"
        )
        print(f"  Storage URI: {res['storage_uri']}")


if __name__ == "__main__":
    main()
