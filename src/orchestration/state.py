"""Persist orchestration run state in the control plane (migration 0005)."""

from __future__ import annotations

import json
from typing import Any

import psycopg

from src.orchestration.plan import PipelinePlan


def start_orchestration_run(
    conn: psycopg.Connection,
    plan: PipelinePlan,
    orchestrator: str,
    external_run_id: str,
) -> int:
    """Create (or, on a retried start task, reuse) the run for one external run id."""

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO orchestration_run (
                orchestrator,
                external_run_id,
                contract_path,
                client_code,
                project_code,
                parameters_json
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (orchestrator, external_run_id)
            DO UPDATE SET status = 'running', finished_at = NULL, error_message = NULL
            RETURNING orchestration_run_id
            """,
            (
                orchestrator,
                external_run_id,
                plan.contract_path,
                plan.client_code,
                plan.project_code,
                json.dumps({**plan.parameters, "resolved": plan.to_dict()}, default=str),
            ),
        )
        return int(cur.fetchone()[0])


def start_task_run(
    conn: psycopg.Connection,
    orchestration_run_id: int,
    stage: str,
    target: str,
    attempt: int,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO orchestration_task_run (orchestration_run_id, stage, target, attempt)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (orchestration_run_id, stage, target, attempt)
            DO UPDATE SET status = 'running', started_at = NOW(), finished_at = NULL,
                          error_message = NULL, summary_json = NULL, pipeline_run_id = NULL
            RETURNING task_run_id
            """,
            (orchestration_run_id, stage, target, attempt),
        )
        return int(cur.fetchone()[0])


def finish_task_run(
    conn: psycopg.Connection,
    task_run_id: int,
    status: str,
    *,
    pipeline_run_id: int | None = None,
    summary: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE orchestration_task_run
            SET status = %s,
                finished_at = NOW(),
                pipeline_run_id = %s,
                summary_json = %s::jsonb,
                error_message = %s
            WHERE task_run_id = %s
            """,
            (
                status,
                pipeline_run_id,
                json.dumps(summary, default=str) if summary is not None else None,
                error_message[:2000] if error_message else None,
                task_run_id,
            ),
        )


def latest_task_states(conn: psycopg.Connection, orchestration_run_id: int) -> dict[tuple[str, str], dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT stage, target, status, attempt, error_message
            FROM orchestration_task_latest
            WHERE orchestration_run_id = %s
            """,
            (orchestration_run_id,),
        )
        return {
            (row[0], row[1]): {"status": row[2], "attempt": row[3], "error_message": row[4]}
            for row in cur.fetchall()
        }


def evaluate_run_outcome(
    plan: PipelinePlan,
    states: dict[tuple[str, str], dict[str, Any]],
) -> tuple[str, str | None]:
    """A run succeeds only if every planned stage/target has a successful latest attempt."""

    problems: list[str] = []
    for stage, target in plan.expected_tasks():
        state = states.get((stage, target))
        if state is None:
            problems.append(f"{stage}[{target}] did not run")
        elif state["status"] != "success":
            detail = f": {state['error_message']}" if state.get("error_message") else ""
            problems.append(f"{stage}[{target}] {state['status']}{detail}")

    if problems:
        return "failed", "; ".join(problems)[:2000]
    return "success", None


def finish_orchestration_run(
    conn: psycopg.Connection,
    orchestration_run_id: int,
    status: str,
    error_message: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE orchestration_run
            SET status = %s, finished_at = NOW(), error_message = %s
            WHERE orchestration_run_id = %s
            """,
            (status, error_message, orchestration_run_id),
        )
