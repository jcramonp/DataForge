# Metadata-driven orchestration

Issue **#24**. One Airflow DAG, `dataforge_pipeline`, runs **any** DataForge contract. Which datasets, Gold outputs and stages execute is resolved at run time from the contract and the run parameters. Onboarding a new client, source or dataset means adding a contract file, never a DAG file.

## Architecture

```text
airflow/dags/dataforge_pipeline.py        task graph only (no business logic)
        │
        ▼
src/orchestration/
  plan.py        validate a request against its contract -> PipelinePlan (stages + targets)
  executor.py    run one stage attempt: run-state tracking, log context, retry classification
  stages.py      one function per stage, delegating to the existing generic runners
  state.py       orchestration_run / orchestration_task_run (migration 0005)
  pipeline.py    standalone runner: same plan, without Airflow
  airflow_client.py   trigger/monitor runs through the Airflow REST API
        │
        ▼
existing generic runners (unchanged)
  bronze_generic.ingest_dataset · discovery.engine.profile_dataframe ·
  silver_runner.execute_silver_pipeline_for_dataset (Quality Gate, Quarantine, lineage) ·
  gold_runner.execute_gold_pipeline_for_dataset (lineage, certification evaluation) ·
  governance.certification
```

| Stage | Runs per | Delegates to | Records |
|---|---|---|---|
| `bronze` | source dataset | `bronze_generic.ingest_dataset` | `pipeline_run` `source_to_bronze` |
| `profiling` | source dataset | `discovery.engine.profile_dataframe` on the latest Bronze asset | logs + task return value only (not persisted, see below) |
| `silver` | source dataset | `silver_runner.execute_silver_pipeline_for_dataset` | `pipeline_run` `silver_quality_gate`, quality results, lineage |
| `gold` | Gold code | `gold_runner.execute_gold_pipeline_for_dataset` | `pipeline_run` `silver_to_gold`, lineage, certification evaluation |
| `certification` | once | `governance.certification` | `evaluate`: readiness report; `validate`: also `draft → validated` for ready versions |

Notes:

- **Profiling** reads the Bronze Parquet that was actually ingested instead of hitting the source a second time, and uses the discovery engine unchanged. Its output is not stored in the control plane, because profiling persistence belongs to #21.
- **Certification** never moves a version to `certified`: that remains a human decision.

### DAG structure

```text
resolve_plan ─┬─ dataset_targets ─┐
              ├─ gold_targets ────┤
              └─ start_run ───────┴─> dataset[<code>] (mapped group) ──> gold[<code>] (mapped) ──> certification ──> finalize
                                       bronze -> profiling -> silver
```

- `dataset` is a **mapped task group**, one instance per source dataset. A failing dataset stops only its own chain; the other datasets keep running.
- `gold` waits for every dataset chain. `certification` waits for every Gold and every dataset chain.
- Stages left out of `stages` are **skipped**, not failed (trigger rule `none_failed`).
- `finalize` always runs (`all_done`). It closes the `orchestration_run` row from the recorded task states and fails the DAG run if any planned stage/target did not succeed.
- Mapped tasks show their target in the UI: `dataset.bronze[orders]`, `gold[order_items_gold]`.
- `max_active_runs=1`: runs queue instead of competing for the same metadata.

### Retries and error handling

| Error | Example | Behavior |
|---|---|---|
| Transient infrastructure | PostgreSQL connection lost, MinIO/S3 unreachable, source connection error, timeouts | Retried 2 times, exponential backoff from 20 s up to 5 min |
| Contract, configuration or data | invalid contract or parameters, missing credentials, missing table/file, no successful Bronze to read | Fails immediately (`AirflowFailException`); retrying cannot fix it |

Every attempt is recorded with its number, so retries are visible in PostgreSQL as well as in Airflow. Classification lives in `executor.is_retryable`.

## Run parameters

| Parameter | Default | Meaning |
|---|---|---|
| `contract` | `config/examples/olist.yaml` | Contract path, relative to the repository root |
| `datasets` | `[]` (all) | Source dataset codes to process |
| `gold` | `[]` (all enabled) | Gold codes to build |
| `stages` | all | Any of `bronze`, `profiling`, `silver`, `gold`, `certification`; always executed in that order |
| `certification` | `evaluate` | `evaluate` or `validate` |

Invalid parameters (unknown dataset, stage or Gold code, a disabled Gold, a missing or invalid contract) fail `resolve_plan` immediately, with the reason in its log.

## Running a pipeline

### Airflow UI

Open `http://localhost:8080` and log in with `AIRFLOW_ADMIN_USERNAME` / `AIRFLOW_ADMIN_PASSWORD` from `.env`. Then go to *dataforge_pipeline → Trigger*, edit the parameters and trigger the run.

### REST API (for the control-plane API, #25)

```bash
python -m src.orchestration.airflow_client --contract config/examples/olist.yaml --wait
python -m src.orchestration.airflow_client --contract config/examples/postgres_sales.yaml \
    --stages bronze,profiling,silver --certification validate --wait
```

From code:

```python
from src.orchestration.airflow_client import AirflowClient, build_conf

client = AirflowClient.from_env()
run = client.trigger(build_conf("config/examples/olist.yaml", datasets=["orders"]))
client.wait(run["dag_run_id"])
```

Raw HTTP equivalent: `POST /auth/token` with `{"username", "password"}`, then `POST /api/v2/dags/dataforge_pipeline/dagRuns` with `{"logical_date": null, "conf": {...}}` and the bearer token.

### Without Airflow

Same plan, stages and run-state tracking, executed sequentially in one process:

```bash
python -m src.orchestration.pipeline --contract config/examples/olist.yaml
python -m src.orchestration.pipeline --contract tests/fixtures/e2e/retail_contract.yaml --stages bronze,silver --json
```

The exit code is `0` on success, `1` if the run failed and `2` for an invalid request.

## Onboarding a new source

1. Write a contract (see `config/examples/` and `docs/sprint-2/configuration-contract.md`).
2. Put source credentials in `.env` as `DATAFORGE_CONNECTION_<REF>` (JSON). Compose loads `.env` into the Airflow services; restart the scheduler after changing it.
3. Make the contract visible to the workers. The repository is mounted at `/opt/dataforge`, so any path inside it works.
4. Trigger `dataforge_pipeline` with `{"contract": "<path>"}`.

No DAG, no code change.

## Run state in PostgreSQL

Migration `0005_orchestration_runs.sql` adds:

| Object | Content |
|---|---|
| `orchestration_run` | One row per Airflow DAG run (`external_run_id` = `dag_run_id`) or CLI run: contract, client/project, parameters, `running`/`success`/`failed`, timings, failure reason |
| `orchestration_task_run` | One row per stage/target **attempt**, linked to the `pipeline_run` it produced; failed attempts keep their error |
| `orchestration_task_latest` (view) | Latest attempt per stage/target |
| `orchestration_run_summary` (view) | Per-run task counts, failures, retried attempts, duration |

`python -m src.ops.run_summary` and `GET /api/ops/summary` list recent orchestration runs next to stage metrics.

```sql
-- Which pipeline runs did an Airflow run produce?
SELECT otr.stage, otr.target, otr.attempt, otr.status, pr.run_id, pr.accepted_rows, pr.rejected_rows
FROM orchestration_run o
JOIN orchestration_task_run otr USING (orchestration_run_id)
LEFT JOIN pipeline_run pr ON pr.run_id = otr.pipeline_run_id
WHERE o.external_run_id = 'manual__2026-10-26T05:20:21.598719+00:00'
ORDER BY otr.task_run_id;
```

Logs carry the same identifiers. Every line emitted by a stage includes `orchestration_run_id`, `external_run_id`, `attempt`, `orchestration_stage` and `target`, plus the runner's own `stage`, `dataset` and `run_id`.

## Legacy DAG

`olist_alpha_pipeline` (Sprint 1) is kept, tagged `legacy`, as the regression reference for the Olist-specific scripts. Olist now runs through `dataforge_pipeline` with `config/examples/olist.yaml`. Do not add datasets to the legacy DAG.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `resolve_plan` failed | Invalid parameters or contract; the task log has the reason |
| `dataset.bronze[x]` failed with `ConnectorConfigurationError` | `DATAFORGE_CONNECTION_<REF>` missing in `.env` / not loaded by the scheduler |
| `dataset.silver[x]` fails with `No successful Bronze asset` | Run `bronze` first (or include it in `stages`) |
| `certification` fails with `No successfully processed version` | Datasets/Gold in the plan were never processed successfully |
| DAG missing in the UI / `No module named 'src'` | `PYTHONPATH=/opt/dataforge` missing on the Airflow services (set in `docker-compose.yml`) |
| Runs stay `queued` | Another run is active (`max_active_runs=1`) or the scheduler is down (`docker compose ps`) |
