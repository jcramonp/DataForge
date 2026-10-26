#!/usr/bin/env bash
# Executes the real dataforge_pipeline DAG with `airflow dags test` inside the
# Airflow image, against the CI PostgreSQL/MinIO services (#24).
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
print("orchestration_run:", row)
assert row is not None and row[0] == "airflow", "DAG did not register an orchestration run"
assert row[1] == "success" and row[2] == row[3] == 5, f"DAG run did not succeed: {row}"
PY
