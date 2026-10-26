#!/usr/bin/env bash
# Executes the real dataforge_pipeline DAG with `airflow dags test` inside the
# Airflow image, against the CI PostgreSQL/MinIO services (#24), and checks
# Source -> Bronze -> persisted profiling (#21) -> Silver -> Gold -> certification.
set -euo pipefail

python -m src.ops.migrate
python - <<'PY'
from src.common import create_s3_client, get_settings
s3 = create_s3_client()
existing = {b["Name"] for b in s3.list_buckets().get("Buckets", [])}
for bucket in get_settings().storage.buckets.values():
    if bucket not in existing:
        s3.create_bucket(Bucket=bucket)
PY

python -m unittest tests.test_airflow_dag -v

airflow db migrate > /dev/null
airflow dags test dataforge_pipeline \
  -c '{"contract": "tests/fixtures/e2e/retail_contract.yaml", "certification": "validate"}'

python - <<'PY'
from src.common import connect_postgres
with connect_postgres() as conn:
    row = conn.execute(
        "SELECT orchestrator, status, task_count, successful_tasks, error_message "
        "FROM orchestration_run_summary ORDER BY orchestration_run_id DESC LIMIT 1"
    ).fetchone()
    stages = conn.execute(
        "SELECT otr.stage, pr.run_type, pr.status FROM orchestration_task_run otr "
        "JOIN orchestration_run o USING (orchestration_run_id) "
        "LEFT JOIN pipeline_run pr ON pr.run_id = otr.pipeline_run_id "
        "WHERE o.orchestrator = 'airflow' AND otr.status = 'success' ORDER BY otr.task_run_id"
    ).fetchall()
    profiling = conn.execute(
        "SELECT prf.profile_id, prf.row_count, prf.column_count, "
        "       prf.source_asset_id = bronze.asset_id AS same_bronze "
        "FROM orchestration_task_run otr "
        "JOIN pipeline_run pr ON pr.run_id = otr.pipeline_run_id AND pr.run_type = 'profiling' "
        "JOIN profiling_result prf ON prf.run_id = pr.run_id "
        "JOIN orchestration_task_run b ON b.orchestration_run_id = otr.orchestration_run_id AND b.stage = 'bronze' "
        "JOIN data_asset bronze ON bronze.run_id = b.pipeline_run_id AND bronze.layer = 'bronze' "
        "WHERE otr.stage = 'profiling'"
    ).fetchall()
print("orchestration_run:", row)
print("stage -> pipeline_run:", stages)
print("profiling_result:", profiling)
assert row is not None and row[0] == "airflow", "DAG did not register an orchestration run"
assert row[1] == "success" and row[2] == row[3] == 5, f"DAG run did not succeed: {row}"
assert [(s, rt) for s, rt, _ in stages] == [
    ("bronze", "source_to_bronze"),
    ("profiling", "profiling"),
    ("silver", "silver_quality_gate"),
    ("gold", "silver_to_gold"),
    ("certification", None),
], f"unexpected stage chain: {stages}"
assert profiling and profiling[0][1:] == (7, 5, True), f"profiling not persisted/linked: {profiling}"
PY
