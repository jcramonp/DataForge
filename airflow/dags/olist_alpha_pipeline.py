"""Airflow DAG for the Sprint 1 Alpha Olist pipeline.

Airflow orchestrates the existing DataForge scripts without duplicating business
logic. Each task invokes one already-tested stage in sequence.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta

from airflow.sdk import DAG
from airflow.providers.standard.operators.python import PythonOperator

PROJECT_ROOT = "/opt/dataforge"


def run_stage(script_path: str) -> None:
    subprocess.run(
        ["python", f"{PROJECT_ROOT}/{script_path}"],
        cwd=PROJECT_ROOT,
        check=True,
    )


with DAG(
    dag_id="olist_alpha_pipeline",
    description="DataForge Sprint 1 Alpha: Bronze to validated Silver to Gold",
    start_date=datetime(2026, 8, 1),
    schedule=None,
    catchup=False,
    default_args={
            "retries": 1,
            "retry_delay": timedelta(minutes=1),
    },
    tags=["dataforge", "olist", "alpha"],
) as dag:
    bronze = PythonOperator(
        task_id="source_to_bronze",
        python_callable=run_stage,
        op_kwargs={"script_path": "src/ingestion/bronze_olist.py"},
    )

    silver = PythonOperator(
        task_id="bronze_to_silver",
        python_callable=run_stage,
        op_kwargs={"script_path": "src/transformations/silver_olist.py"},
    )

    quality_gate = PythonOperator(
        task_id="silver_quality_gate",
        python_callable=run_stage,
        op_kwargs={"script_path": "src/quality/validate_olist.py"},
    )

    gold = PythonOperator(
        task_id="silver_to_gold",
        python_callable=run_stage,
        op_kwargs={"script_path": "src/transformations/gold_olist.py"},
    )

    bronze >> silver >> quality_gate >> gold
