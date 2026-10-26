"""Execute plan stages with run-state tracking; shared by Airflow and the CLI.

The executor wraps every stage/target attempt with:

- an ``orchestration_task_run`` row (running -> success/failed) linked to the
  stage's ``pipeline_run``;
- structured-log context (``orchestration_run_id``, ``external_run_id``,
  ``attempt``) on top of the runners' own ``stage``/``dataset``/``run_id``;
- error classification: only transient infrastructure errors are worth a
  retry; contract, configuration and data errors fail immediately.
"""

from __future__ import annotations

import logging
from typing import Any

import psycopg
from botocore.exceptions import (
    ConnectionClosedError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ReadTimeoutError,
)
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout as RequestsTimeout

from src.common.clients import connect_postgres
from src.common.log import run_context
from src.connectors.base import ConnectorConnectionError
from src.orchestration import state
from src.orchestration.plan import PipelinePlan
from src.orchestration.stages import STAGE_FUNCTIONS


logger = logging.getLogger("src.orchestration.executor")

TRANSIENT_ERRORS: tuple[type[BaseException], ...] = (
    psycopg.OperationalError,
    EndpointConnectionError,
    ConnectionClosedError,
    ConnectTimeoutError,
    ReadTimeoutError,
    ConnectorConnectionError,
    RequestsConnectionError,
    RequestsTimeout,
    ConnectionError,
    TimeoutError,
)


def is_retryable(exc: BaseException) -> bool:
    """Retry only infrastructure hiccups (database/storage/source unreachable)."""

    return isinstance(exc, TRANSIENT_ERRORS)


def start_run(plan: PipelinePlan, orchestrator: str, external_run_id: str) -> int:
    with connect_postgres() as conn:
        orchestration_run_id = state.start_orchestration_run(conn, plan, orchestrator, external_run_id)
        conn.commit()
    logger.info(
        "Orchestration run started",
        extra={
            "orchestration_run_id": orchestration_run_id,
            "external_run_id": external_run_id,
            "orchestrator": orchestrator,
            "contract": plan.contract_path,
            "stages": plan.stages,
            "datasets": plan.datasets,
            "gold": plan.gold,
        },
    )
    return orchestration_run_id


def execute_task(
    plan: PipelinePlan,
    orchestration_run_id: int,
    stage: str,
    target: str,
    *,
    attempt: int = 1,
    external_run_id: str | None = None,
) -> dict[str, Any]:
    """Run one stage for one target and record the attempt."""

    stage_function = STAGE_FUNCTIONS[stage]

    with run_context(
        orchestration_run_id=orchestration_run_id,
        external_run_id=external_run_id,
        attempt=attempt,
        client=plan.client_code,
        project=plan.project_code,
        target=target,
        orchestration_stage=stage,
    ):
        with connect_postgres() as conn:
            task_run_id = state.start_task_run(conn, orchestration_run_id, stage, target, attempt)
            conn.commit()

        logger.info("Orchestrated %s[%s] started", stage, target)
        try:
            if stage == "certification":
                summary = stage_function(plan)
            else:
                summary = stage_function(plan, target)
        except Exception as exc:
            with connect_postgres() as conn:
                state.finish_task_run(
                    conn,
                    task_run_id,
                    "failed",
                    error_message=f"{type(exc).__name__}: {exc}",
                )
                conn.commit()
            logger.exception(
                "Orchestrated %s[%s] failed",
                stage,
                target,
                extra={"retryable": is_retryable(exc)},
            )
            raise

        with connect_postgres() as conn:
            state.finish_task_run(
                conn,
                task_run_id,
                "success",
                pipeline_run_id=summary.get("run_id"),
                # Profiling output is deliberately not persisted (owned by #21).
                summary=None if stage == "profiling" else summary,
            )
            conn.commit()
        logger.info("Orchestrated %s[%s] finished", stage, target)
        return summary


def finish_run(plan: PipelinePlan, orchestration_run_id: int) -> tuple[str, str | None]:
    """Close the run from recorded task states; returns (status, error)."""

    with connect_postgres() as conn:
        states = state.latest_task_states(conn, orchestration_run_id)
        status, error = state.evaluate_run_outcome(plan, states)
        state.finish_orchestration_run(conn, orchestration_run_id, status, error)
        conn.commit()

    log = logger.info if status == "success" else logger.error
    log(
        "Orchestration run %s",
        status,
        extra={"orchestration_run_id": orchestration_run_id, "error": error},
    )
    return status, error
