"""One function per orchestration stage, each delegating to an existing generic runner.

Orchestration adds no pipeline logic: Bronze, governed profiling, Silver +
Quality Gate, Gold, lineage and certification are executed by the same
functions the standalone CLIs use. Each stage function processes one target (a dataset or a Gold code)
and returns a small JSON-serializable summary, so it can run inside an
Airflow task, in the CLI runner, or in tests.

Client construction goes through each runner module's ``minio_client()`` /
``postgres_connection()`` (or, for the profiling service, the shared
``src.common.clients`` it uses itself) so behavior stays identical to running
the runners directly.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import psycopg

from src.common.clients import connect_postgres, create_s3_client
from src.common.settings import PROJECT_ROOT, get_settings
from src.contracts.loader import load_contract
from src.contracts.models import DataForgeContract
from src.discovery import service as profiling_service
from src.governance.certification import (
    evaluate_certification,
    get_certification,
    transition_certification,
)
from src.ingestion import bronze_generic
from src.orchestration.plan import PipelinePlan
from src.transformations import gold_runner, silver_runner


logger = logging.getLogger("src.orchestration.stages")

ORCHESTRATOR_ACTOR = "dataforge-orchestrator"


@contextmanager
def project_working_directory() -> Iterator[None]:
    """Run inside the repository root: contract source paths are relative to it."""

    previous = Path.cwd()
    os.chdir(PROJECT_ROOT)
    try:
        yield
    finally:
        os.chdir(previous)


def _contract(plan: PipelinePlan) -> DataForgeContract:
    return load_contract(plan.absolute_contract_path())


def run_bronze(plan: PipelinePlan, dataset_code: str) -> dict[str, Any]:
    """Source -> Bronze for one dataset (``bronze_generic.ingest_dataset``)."""

    with project_working_directory():
        contract = _contract(plan)
        bucket = get_settings().storage.bucket("bronze")
        s3 = bronze_generic.minio_client()
        with bronze_generic.postgres_connection() as conn:
            result = bronze_generic.ingest_dataset(
                contract=contract,
                dataset_code=dataset_code,
                s3=s3,
                conn=conn,
                bucket=bucket,
            )

    return {
        "dataset": result["dataset"],
        "run_id": result["run_id"],
        "rows": result["rows"],
        "storage_uri": result["storage_uri"],
        "source_checksum": result["source_checksum"],
    }


def run_profiling(plan: PipelinePlan, dataset_code: str) -> dict[str, Any]:
    """Governed profiling of the latest Bronze asset (``discovery.service``, #21).

    The discovery service profiles the exact latest successful Bronze asset
    (checksum and row count verified), records a ``pipeline_run`` of type
    ``profiling``, redacts samples of confidential/restricted columns and
    persists the profile in ``profiling_result``. Only a compact summary is
    returned here; the full profile stays in ``profiling_result.profile_json``.
    """

    with project_working_directory():
        contract = _contract(plan)
        s3 = create_s3_client()
        with connect_postgres() as conn:
            result = profiling_service.execute_profiling_for_dataset(
                contract=contract,
                dataset_code=dataset_code,
                s3=s3,
                conn=conn,
            )

    return {
        "dataset": result["dataset"],
        "run_id": result["run_id"],
        "profile_id": result["profile_id"],
        "dataset_version_id": result["dataset_version_id"],
        "source_asset_id": result["source_asset_id"],
        "row_count": result["row_count"],
        "column_count": result["column_count"],
    }


def run_silver(plan: PipelinePlan, dataset_code: str) -> dict[str, Any]:
    """Bronze -> Silver + Quality Gate (+ lineage) for one dataset."""

    settings = get_settings()
    with project_working_directory():
        contract = _contract(plan)
        s3 = silver_runner.minio_client()
        with silver_runner.postgres_connection() as conn:
            result = silver_runner.execute_silver_pipeline_for_dataset(
                contract=contract,
                dataset_code=dataset_code,
                s3=s3,
                conn=conn,
                silver_bucket=settings.storage.bucket("silver"),
                quarantine_bucket=settings.storage.bucket("quarantine"),
            )

    failed_rules = [
        {"rule": r["rule_name"], "severity": r["severity"], "failed_rows": r["failed_rows"]}
        for r in result["quality_results"]
        if r["status"] == "fail"
    ]
    return {
        "dataset": result["dataset"],
        "run_id": result["run_id"],
        "input_rows": result["input_rows"],
        "accepted_rows": result["accepted_rows"],
        "rejected_rows": result["rejected_rows"],
        "validated_uri": result["validated_uri"],
        "quarantine_uri": result["quarantine_uri"],
        "failed_rules": failed_rules,
    }


def run_gold(plan: PipelinePlan, gold_code: str) -> dict[str, Any]:
    """Validated Silver -> Gold (+ lineage and certification evaluation) for one Gold code."""

    with project_working_directory():
        contract = _contract(plan)
        gold_config = next((g for g in contract.gold if g.code == gold_code), None)
        if gold_config is None:
            raise ValueError(f"Gold dataset '{gold_code}' is not defined in the contract")

        s3 = gold_runner.minio_client()
        with gold_runner.postgres_connection() as conn:
            result = gold_runner.execute_gold_pipeline_for_dataset(
                contract=contract,
                gold_config=gold_config,
                s3=s3,
                conn=conn,
                gold_bucket=get_settings().storage.bucket("gold"),
            )

    certification = result.get("certification") or {}
    return {
        "gold": result["gold_code"],
        "run_id": result["run_id"],
        "dataset_version_id": result["dataset_version_id"],
        "input_rows": result["input_rows"],
        "output_rows": result["output_rows"],
        "excluded_rows": result["excluded_rows"],
        "storage_uri": result["storage_uri"],
        "validation_ready": certification.get("validation_ready"),
        "certification_ready": certification.get("certification_ready"),
    }


def latest_successful_version(
    conn: psycopg.Connection,
    plan: PipelinePlan,
    dataset_code: str,
    run_type: str,
) -> int | None:
    """dataset_version_id of the latest successful run of one stage for a dataset."""

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT pr.dataset_version_id
            FROM client c
            JOIN project p ON p.client_id = c.client_id
            JOIN data_source ds ON ds.project_id = p.project_id
            JOIN dataset d ON d.source_id = ds.source_id
            JOIN dataset_version dv ON dv.dataset_id = d.dataset_id
            JOIN pipeline_run pr ON pr.dataset_version_id = dv.dataset_version_id
            WHERE c.client_code = %s
              AND p.project_code = %s
              AND ds.source_code = %s
              AND d.dataset_code = %s
              AND pr.run_type = %s
              AND pr.status = 'success'
            ORDER BY pr.finished_at DESC NULLS LAST, pr.run_id DESC
            LIMIT 1
            """,
            (plan.client_code, plan.project_code, plan.source_code, dataset_code, run_type),
        )
        row = cur.fetchone()
    return int(row[0]) if row else None


def run_certification(plan: PipelinePlan, target: str = "contract") -> dict[str, Any]:
    """Evaluate certification for every dataset and Gold version in the plan.

    ``evaluate`` only reports readiness. ``validate`` also moves versions whose
    validation criteria are met from draft to validated. Moving to certified
    is a human decision and is never done here.
    """

    targets = [(code, "silver_quality_gate", "dataset") for code in plan.datasets]
    targets += [(code, "silver_to_gold", "gold") for code in plan.gold]

    results: list[dict[str, Any]] = []
    missing: list[str] = []

    with silver_runner.postgres_connection() as conn:
        for code, run_type, kind in targets:
            version_id = latest_successful_version(conn, plan, code, run_type)
            if version_id is None:
                missing.append(code)
                continue

            evaluation = evaluate_certification(conn, version_id)
            state_before = get_certification(conn, version_id)["state"]
            state_after = state_before

            if (
                plan.certification == "validate"
                and state_before == "draft"
                and evaluation["validation_ready"]
            ):
                transition_certification(
                    conn,
                    version_id,
                    "validated",
                    reason="Validation criteria met during orchestrated pipeline run",
                    changed_by=ORCHESTRATOR_ACTOR,
                )
                state_after = "validated"
            conn.commit()

            results.append(
                {
                    "target": code,
                    "kind": kind,
                    "dataset_version_id": version_id,
                    "state_before": state_before,
                    "state_after": state_after,
                    "validation_ready": evaluation["validation_ready"],
                    "certification_ready": evaluation["certification_ready"],
                    "criteria": evaluation["criteria"],
                }
            )

    if missing:
        raise RuntimeError(
            "No successfully processed version to certify for: " + ", ".join(missing)
        )

    logger.info(
        "Certification evaluated",
        extra={
            "mode": plan.certification,
            "validated": [r["target"] for r in results if r["state_after"] != r["state_before"]],
            "not_ready": [r["target"] for r in results if not r["validation_ready"]],
        },
    )
    return {"mode": plan.certification, "versions": results}


STAGE_FUNCTIONS = {
    "bronze": run_bronze,
    "profiling": run_profiling,
    "silver": run_silver,
    "gold": run_gold,
    "certification": run_certification,
}
