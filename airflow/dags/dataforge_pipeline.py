"""Generic, metadata-driven DataForge pipeline (#24).

One DAG runs **any** DataForge contract. Which source datasets, Gold datasets
and stages execute is resolved at run time from the contract and the run
parameters, so onboarding a new client/source/dataset never requires a new
DAG file.

Structure of every run::

    resolve_plan -> dataset_targets, gold_targets -> start_run -> dataset[<code>] x N -> gold[<code>] x M -> certification -> finalize
                                  (bronze -> profiling -> silver)

- ``dataset`` is a mapped task group, one instance per source dataset: a
  failing dataset stops only its own Bronze -> profiling -> Silver chain.
- Gold waits for every dataset chain; certification waits for every Gold.
- Stages left out of ``stages`` are skipped, not failed.
- Transient infrastructure errors are retried (exponential backoff); contract,
  configuration and data errors fail immediately without retries.
- ``finalize`` always runs, closes the ``orchestration_run`` row in PostgreSQL
  and fails the DAG run if any planned stage did not succeed.

All business logic lives in ``src/`` (``src.orchestration`` delegating to the
generic runners); this file only declares the task graph. The same plan runs
without Airflow via ``python -m src.orchestration.pipeline``.

Trigger with parameters (UI "Trigger DAG w/ config", REST API or
``python -m src.orchestration.airflow_client``)::

    {"contract": "config/examples/olist.yaml",
     "datasets": [], "gold": [],
     "stages": ["bronze", "profiling", "silver", "gold", "certification"],
     "certification": "evaluate"}
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from airflow.sdk import Param, TriggerRule, dag, get_current_context, task, task_group
from airflow.sdk.exceptions import AirflowFailException, AirflowSkipException

from src.orchestration.plan import CERTIFICATION_MODES, STAGES


DAG_ID = "dataforge_pipeline"


def _run_stage(stage: str, plan: dict[str, Any], orchestration_run_id: int, target: str) -> dict[str, Any]:
    """Execute one stage attempt; classify errors for Airflow's retry policy."""

    from src.orchestration import executor
    from src.orchestration.plan import PipelinePlan

    pipeline_plan = PipelinePlan.from_dict(plan)
    context = get_current_context()
    context["map_label"] = target

    if not pipeline_plan.runs(stage):
        raise AirflowSkipException(f"Stage '{stage}' not selected for this run")

    try:
        return executor.execute_task(
            pipeline_plan,
            orchestration_run_id,
            stage,
            target,
            attempt=context["ti"].try_number,
            external_run_id=context["dag_run"].run_id,
        )
    except Exception as exc:
        if executor.is_retryable(exc):
            raise
        raise AirflowFailException(f"{type(exc).__name__}: {exc}") from exc


@dag(
    dag_id=DAG_ID,
    description="Contract-driven DataForge pipeline: Bronze, profiling, Silver + Quality Gate, Gold, certification",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["dataforge", "generic", "sprint-2"],
    doc_md=__doc__,
    default_args={
        "owner": "dataforge",
        "retries": 2,
        "retry_delay": timedelta(seconds=20),
        "retry_exponential_backoff": True,
        "max_retry_delay": timedelta(minutes=5),
    },
    params={
        "contract": Param(
            None,
            type=["string", "null"],
            description=(
                "Legacy contract path. Use either contract "
                "or contract_id, never both."
            ),
        ),
        "contract_id": Param(
            None,
            type=["integer", "null"],
            minimum=1,
            description=(
                "Immutable configuration_contract id from "
                "the PostgreSQL control plane."
            ),
        ),
        "datasets": Param(
            [],
            type="array",
            items={"type": "string"},
            description="Source dataset codes to process (empty = every dataset in the contract)",
        ),
        "gold": Param(
            [],
            type="array",
            items={"type": "string"},
            description="Gold codes to build (empty = every enabled Gold dataset)",
        ),
        "stages": Param(
            list(STAGES),
            type="array",
            items={"type": "string", "enum": list(STAGES)},
            minItems=1,
            description="Stages to execute, always run in pipeline order",
        ),
        "certification": Param(
            "evaluate",
            type="string",
            enum=list(CERTIFICATION_MODES),
            description="evaluate = report readiness; validate = also promote ready versions to 'validated'",
        ),
    },
)
def dataforge_pipeline():
    @task(task_id="resolve_plan", retries=0)
    def resolve_plan() -> dict[str, Any]:
        from src.orchestration.plan import (
            PlanError,
            build_persisted_plan,
            build_plan,
        )

        params = get_current_context()["params"]

        contract = params.get("contract")
        contract_id = params.get("contract_id")

        has_contract = bool(
            contract
            and str(contract).strip()
        )
        has_contract_id = contract_id is not None

        if has_contract == has_contract_id:
            raise AirflowFailException(
                "Exactly one of contract or contract_id "
                "must be provided"
            )

        try:
            if has_contract_id:
                plan = build_persisted_plan(
                    int(contract_id),
                    datasets=params.get("datasets") or None,
                    gold=params.get("gold") or None,
                    stages=params.get("stages") or None,
                    certification=params.get(
                        "certification",
                        "evaluate",
                    ),
                )
            else:
                plan = build_plan(
                    str(contract),
                    datasets=params.get("datasets") or None,
                    gold=params.get("gold") or None,
                    stages=params.get("stages") or None,
                    certification=params.get(
                        "certification",
                        "evaluate",
                    ),
                )
        except PlanError as exc:
            raise AirflowFailException(str(exc)) from exc

        return plan.to_dict()

    @task(retries=0)
    def list_targets(plan: dict[str, Any], stage: str) -> list[str]:
        """Targets to fan out over (mapping requires a plain return value)."""
        from src.orchestration.plan import PipelinePlan

        pipeline_plan = PipelinePlan.from_dict(plan)
        # Dataset chains always fan out over the plan's datasets; skipped
        # stages inside a chain are skipped per task, not by an empty list.
        return pipeline_plan.datasets if stage == "dataset" else pipeline_plan.targets(stage)

    @task(task_id="start_run")
    def start_run(plan: dict[str, Any]) -> int:
        from src.orchestration import executor
        from src.orchestration.plan import PipelinePlan

        return executor.start_run(
            PipelinePlan.from_dict(plan),
            "airflow",
            get_current_context()["dag_run"].run_id,
        )

    @task_group(group_id="dataset")
    def dataset_chain(dataset: str, plan: dict[str, Any], orchestration_run_id: int):
        @task(task_id="bronze", trigger_rule=TriggerRule.NONE_FAILED, map_index_template="{{ map_label }}")
        def bronze(dataset: str, plan: dict[str, Any], orchestration_run_id: int) -> dict[str, Any]:
            return _run_stage("bronze", plan, orchestration_run_id, dataset)

        @task(task_id="profiling", trigger_rule=TriggerRule.NONE_FAILED, map_index_template="{{ map_label }}")
        def profiling(dataset: str, plan: dict[str, Any], orchestration_run_id: int) -> dict[str, Any]:
            return _run_stage("profiling", plan, orchestration_run_id, dataset)

        @task(task_id="silver", trigger_rule=TriggerRule.NONE_FAILED, map_index_template="{{ map_label }}")
        def silver(dataset: str, plan: dict[str, Any], orchestration_run_id: int) -> dict[str, Any]:
            return _run_stage("silver", plan, orchestration_run_id, dataset)

        bronze_task = bronze(dataset, plan, orchestration_run_id)
        profiling_task = profiling(dataset, plan, orchestration_run_id)
        silver_task = silver(dataset, plan, orchestration_run_id)
        bronze_task >> profiling_task >> silver_task

    @task(task_id="gold", trigger_rule=TriggerRule.NONE_FAILED, map_index_template="{{ map_label }}")
    def gold(gold_code: str, plan: dict[str, Any], orchestration_run_id: int) -> dict[str, Any]:
        return _run_stage("gold", plan, orchestration_run_id, gold_code)

    @task(task_id="certification", trigger_rule=TriggerRule.NONE_FAILED)
    def certification(plan: dict[str, Any], orchestration_run_id: int) -> dict[str, Any]:
        return _run_stage("certification", plan, orchestration_run_id, "contract")

    @task(task_id="finalize", trigger_rule=TriggerRule.ALL_DONE, retries=0)
    def finalize(plan: dict[str, Any], orchestration_run_id: int) -> dict[str, Any]:
        from src.orchestration import executor
        from src.orchestration.plan import PipelinePlan

        status, error = executor.finish_run(PipelinePlan.from_dict(plan), orchestration_run_id)
        if status != "success":
            raise AirflowFailException(f"Pipeline failed: {error}")
        return {"orchestration_run_id": orchestration_run_id, "status": status}

    plan = resolve_plan()
    dataset_targets = list_targets.override(task_id="dataset_targets")(plan, "dataset")
    gold_targets = list_targets.override(task_id="gold_targets")(plan, "gold")
    run_id = start_run(plan)

    datasets = dataset_chain.partial(plan=plan, orchestration_run_id=run_id).expand(dataset=dataset_targets)
    golds = gold.partial(plan=plan, orchestration_run_id=run_id).expand(gold_code=gold_targets)
    certified = certification(plan, run_id)
    closed = finalize(plan, run_id)

    run_id >> datasets >> golds >> certified >> closed
    # Certification also waits on the dataset chains directly: with no Gold
    # targets the (empty, skipped) gold task alone would not propagate a failure.
    datasets >> certified


dataforge_pipeline()
