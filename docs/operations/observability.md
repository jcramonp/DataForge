# Observability

## Health and readiness

| Endpoint / command | Purpose | Checks | Failure |
|---|---|---|---|
| `GET /api/health` | **Liveness**: the API process is up. Used by the Docker `HEALTHCHECK` | none (no dependencies) | — |
| `GET /api/ready` | **Readiness**: the API can do useful work. Use for load-balancer target health and deploy gates | configuration valid, PostgreSQL reachable with **no pending migrations**, all four buckets reachable, shipped contracts validate | HTTP `503` with per-check details |
| `python -m src.ops.health [--json]` | Same readiness checks from a shell, Airflow task or ECS one-off task | same | exit code `1` |

Infrastructure services keep their Compose health checks (`pg_isready`, MinIO `/minio/health/live`), and `api`/`migrate`/Airflow start only after their dependencies are healthy.

Example:

```text
$ python -m src.ops.health
OK   configuration        0.0 ms  environment=test
OK   postgres            34.4 ms  connected; schema version 0004
OK   object_storage     228.3 ms  4 buckets reachable
OK   contracts           33.8 ms  2 contracts valid
READY
```

## Structured logging

`src/common/log.py` configures one stdout handler, enabled by `configure_logging()` in every CLI entrypoint and in the API startup.

- `DATAFORGE_LOG_FORMAT=json` writes one JSON object per line. This is the default outside `local`, and CloudWatch, Airflow and `jq` can query it.
- `DATAFORGE_LOG_FORMAT=text` is human-readable: `... [run_id=2 dataset=orders] message`.
- **Run context:** each generic stage wraps its work in `run_context(stage, client, project, dataset)` and binds `run_id` as soon as its `pipeline_run` row exists. Every log line inside the stage carries those identifiers, including errors and stack traces.
- **API requests:** every request gets an `X-Request-ID`, either propagated from the caller or generated. It is returned in the response header and logged with method, path, status and `duration_ms`.
- Fields whose name contains `password`, `secret`, `token`, `authorization` or `api_key` are redacted; noisy AWS client loggers are kept at `WARNING`.

Instrumented entrypoints: `src.ingestion.bronze_generic`, `src.transformations.silver_runner`, `src.transformations.gold_runner`, `src.ops.*`, `src.api.main`. Orchestration (#24) should use the same `run_context` / `bind_context` pattern.

## Run metrics and status summaries

Migration `0004_operational_views.sql` adds three views:

- `pipeline_run_status_summary`: runs per stage and status, row totals, average duration and last start;
- `pipeline_run_failures`: each failed run with client, project, dataset, version, duration and error message;
- `dataset_latest_run`: current state (latest run) of every dataset per stage.

They are exposed through:

```bash
python -m src.ops.run_summary          # text
python -m src.ops.run_summary --json   # machine readable
curl localhost:8000/api/ops/summary    # API (source: "database")
```

Totals include `total_runs`, `successful_runs`, `failed_runs`, `running_runs`, `failure_rate` and `rejected_rows`. A run stuck in `running` shows up in `running_runs` and in `dataset_latest_run`.

In every environment, if PostgreSQL is offline the API returns `503`. Operational summaries and Overview never substitute demo runs for unavailable persisted data. Successful operational summaries identify `source: "database"`.

## Tracing a failed pipeline

1. **Find the failure.** Run `python -m src.ops.run_summary`, or query `pipeline_run_failures`:

   ```text
   Recent failures:
     run_id=2 ci-retail/orders silver_quality_gate at 2026-10-26T01:15:09Z: An error occurred (404) when calling the HeadObject operation: Not Found
   ```

2. **Find its logs** by `run_id` and `dataset`:

   ```bash
   docker compose logs airflow-scheduler | grep '"run_id": 2'
   # or locally / in CI
   python -m src.transformations.silver_runner --contract ... 2>&1 | jq 'select(.run_id == 2)'
   ```

   ```json
   {"level": "ERROR", "logger": "src.transformations.silver_runner", "message": "Silver + Quality Gate failed",
    "stage": "silver_quality_gate", "client": "ci-retail", "project": "ci-retail-e2e", "dataset": "orders",
    "run_id": 2, "exception": "Traceback ... botocore.exceptions.ClientError: ... (404) ... HeadObject ..."}
   ```

3. **Inspect what the run touched:** `SELECT * FROM data_asset WHERE run_id = 2;` and `SELECT * FROM quality_result WHERE run_id = 2;`.
4. **Recover** following [`runbook.md`](runbook.md#recovering-a-failed-pipeline-run).

This flow is covered by `tests/test_pipeline_observability.py` (logs carry `run_id`/`dataset` on failure) and `tests/integration/test_generic_pipeline_e2e.py` (failed run recorded and listed in `pipeline_run_failures`).
