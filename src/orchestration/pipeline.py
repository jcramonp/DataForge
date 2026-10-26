"""Standalone generic pipeline entrypoint (no Airflow required).

Runs the same plan, stages and run-state tracking as the ``dataforge_pipeline``
Airflow DAG, sequentially in one process:

- per dataset: Bronze -> profiling -> Silver + Quality Gate. A failing dataset
  stops its own chain but not the other datasets;
- then Gold, then certification, only if every dataset chain succeeded
  (same dependencies as the DAG).

Usage::

    python -m src.orchestration.pipeline --contract config/examples/olist.yaml
    python -m src.orchestration.pipeline --contract tests/fixtures/e2e/retail_contract.yaml \\
        --stages bronze,silver --datasets orders
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from typing import Any

from src.common.log import configure_logging
from src.common.settings import load_environment_file
from src.orchestration import executor
from src.orchestration.plan import CERTIFICATION_MODES, DATASET_STAGES, STAGES, PipelinePlan, PlanError, build_plan


def run_pipeline(plan: PipelinePlan, external_run_id: str | None = None) -> dict[str, Any]:
    external_run_id = external_run_id or f"cli__{uuid.uuid4().hex}"
    orchestration_run_id = executor.start_run(plan, "cli", external_run_id)

    results: dict[str, dict[str, Any]] = {stage: {} for stage in STAGES}
    failed = False

    for dataset in plan.datasets:
        for stage in DATASET_STAGES:
            if not plan.runs(stage):
                continue
            try:
                results[stage][dataset] = executor.execute_task(
                    plan, orchestration_run_id, stage, dataset, external_run_id=external_run_id
                )
            except Exception:
                failed = True
                break  # rest of this dataset's chain depends on the failed stage

    if not failed:
        for gold_code in plan.targets("gold"):
            try:
                results["gold"][gold_code] = executor.execute_task(
                    plan, orchestration_run_id, "gold", gold_code, external_run_id=external_run_id
                )
            except Exception:
                failed = True

    if not failed and plan.runs("certification"):
        try:
            results["certification"]["contract"] = executor.execute_task(
                plan, orchestration_run_id, "certification", "contract", external_run_id=external_run_id
            )
        except Exception:
            pass

    status, error = executor.finish_run(plan, orchestration_run_id)
    return {
        "orchestration_run_id": orchestration_run_id,
        "external_run_id": external_run_id,
        "status": status,
        "error": error,
        "results": {stage: values for stage, values in results.items() if values},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a DataForge contract through the generic pipeline")
    parser.add_argument("--contract", required=True, help="Contract path (relative to the repository root or absolute)")
    parser.add_argument("--datasets", default="", help="Comma-separated dataset codes (default: all)")
    parser.add_argument("--gold", default="", help="Comma-separated Gold codes (default: all enabled)")
    parser.add_argument("--stages", default="", help=f"Comma-separated stages (default: {','.join(STAGES)})")
    parser.add_argument("--certification", default="evaluate", choices=CERTIFICATION_MODES)
    parser.add_argument("--json", action="store_true", help="Print the run result as JSON")
    args = parser.parse_args(argv)

    load_environment_file()
    configure_logging()

    try:
        plan = build_plan(
            args.contract,
            datasets=args.datasets,
            gold=args.gold,
            stages=args.stages,
            certification=args.certification,
        )
    except PlanError as exc:
        print(f"Invalid request: {exc}", file=sys.stderr)
        return 2

    outcome = run_pipeline(plan)

    if args.json:
        print(json.dumps(outcome, indent=2, default=str))
    else:
        print(
            f"Orchestration run {outcome['orchestration_run_id']} ({outcome['external_run_id']}): "
            f"{outcome['status'].upper()}"
        )
        for stage, values in outcome["results"].items():
            for target, summary in values.items():
                run = f" run_id={summary['run_id']}" if summary.get("run_id") else ""
                print(f"  {stage:<13} {target:<20} ok{run}")
        if outcome["error"]:
            print(f"  error: {outcome['error']}")

    return 0 if outcome["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
