# Metadata-Driven Airflow Orchestration Verification

## Scope

This evidence verifies **Issue #24: Build metadata-driven Airflow orchestration** for Sprint 2.

The Olist-specific DAG is replaced by one reusable DAG that executes DataForge stages from contract metadata. The orchestration consumes the existing generic services and does not reimplement any stage:

- Bronze ingestion;
- governed profiling (`src.discovery.service`, #21);
- Silver + Quality Gate;
- Gold;
- certification.

No runner, discovery or governance code was modified.

## Delivered capabilities

| Issue deliverable | Implementation |
|---|---|
| Generic pipeline entrypoint: ingest → Bronze → profiling → Silver → quality → Gold/certification as configured | `src/orchestration/` (`plan`, `stages`, `executor`); each stage delegates to its generic service (profiling → `discovery.service.execute_profiling_for_dataset`); stages selectable per run; certification `evaluate` or `validate` |
| Airflow DAG/task structure driven by dataset identifiers and metadata | `airflow/dags/dataforge_pipeline.py`: one DAG parameterized by `contract`, `datasets`, `gold`, `stages`, `certification`; mapped task group per source dataset and mapped Gold tasks, labeled by code (`dataset.bronze[orders]`) |
| Retry/error handling and run-state integration with PostgreSQL | Transient errors retried (2×, exponential backoff); contract/config/data errors fail fast; migration `0006_orchestration_runs.sql` (`orchestration_run`, `orchestration_task_run` per attempt — successful attempts linked to their `pipeline_run`, failed attempts keep attempt number and full error — plus summary views); `finalize` closes the run and fails the DAG run if any planned task did not succeed |
| API-triggerable runs with parameters | Airflow 3 REST API with known credentials (`AIRFLOW_ADMIN_*`); `src/orchestration/airflow_client.py` (library + CLI) for the control plane (#25) |
| Preserve standalone Python/service logic outside Airflow | `python -m src.orchestration.pipeline` runs the same plan/stages/run state without Airflow; the DAG file holds no business logic |
| Keep Olist working through the generic path | Olist runs through `dataforge_pipeline` with `config/examples/olist.yaml`; results identical to Sprint 1 |

Supporting changes:

- **Compose:**
  - Airflow services share one `x-airflow-common` definition with `PYTHONPATH=/opt/dataforge`.
  - Source credentials reach the workers through `env_file: .env`.
  - The UI/API login comes from `.env` (`airflow/write_auth_file.py`).
  - Airflow waits for migrations and buckets.
- **CI:** new job **Airflow DAG (end-to-end)** builds the Airflow image, checks DAG import and structure, and executes the DAG with `airflow dags test` against PostgreSQL and MinIO. The integration job also runs the orchestration tests.
- **Ops:** `run_summary` and `/api/ops/summary` list recent orchestration runs.

## Design decisions

- **Profiling is the governed #21 service.** The stage delegates to `src.discovery.service.execute_profiling_for_dataset`, which:
  - profiles the exact latest successful Bronze asset (checksum and row count verified), so sources are not extracted twice;
  - records a `pipeline_run` of type `profiling`;
  - redacts confidential/restricted samples;
  - persists `profiling_result`, linked to the dataset version and the source Bronze asset.

  The orchestration task links to that `pipeline_run` and stores only a compact summary; the full profile lives in `profiling_result.profile_json`.
- **Certification is never automatic past `validated`.** In `validate` mode, versions whose criteria are met move `draft → validated` (`changed_by = dataforge-orchestrator`). `certified` stays a human decision.
- **Failure isolation per dataset.** A failing dataset stops only its own chain. Gold and certification wait for every dataset.
- **`max_active_runs=1`.** Runs queue rather than compete for the same control-plane metadata.
- **Legacy DAG kept.** `olist_alpha_pipeline` is tagged `legacy` as the Sprint 1 regression reference.

## Fixes found while integrating

- **The legacy Sprint 1 DAG could not import `src.*`.** It executes scripts by path, so `/opt/dataforge` was not on `sys.path`, and since #32 those scripts import `src.common`. Setting `PYTHONPATH=/opt/dataforge` on the Airflow services fixes it. Verified: the legacy run succeeded (4/4 tasks).
- **Source credentials (`DATAFORGE_CONNECTION_*`) never reached Airflow workers.** Compose only passed fixed variables; `.env` is now loaded as `env_file`.
- **The Airflow login was a random generated password.** It is now configured from `.env`, which makes REST-triggered runs possible.
- **Test ports moved to 15432/19000.** Windows/Hyper-V had reserved 58914–59013, which broke the old MinIO test port 59000 locally. The disposable MinIO also runs as `--user 0:0` everywhere: the non-root image cannot initialize `/data`.

## Verification

The runs in sections 1–6 below were executed before #21 merged, with the earlier inline profiling stage. After merging `develop` (#21), the orchestration was re-verified with the governed profiling service; see **Re-verification after integrating #21**.

## Re-verification after integrating #21

Changes:
- merged `origin/develop` (#21, PR #47);
- orchestration migration renumbered to `0006_orchestration_runs.sql` (`0005_profiling_results.sql` untouched);
- profiling stage now delegates to `src.discovery.service`.

Verification ran on 2026-10-26 against disposable PostgreSQL 16 + MinIO.

### Migrations

```text
$ python -m src.ops.migrate      -> Applied 6 migration(s); 0 already applied.
$ python -m src.ops.migrate      -> Applied 0 migration(s); 6 already applied.
$ python -m src.ops.migrate --status
applied  0001_control_plane_schema / 0002_lineage_certification / 0003_governance_views
applied  0004_operational_views / 0005_profiling_results / 0006_orchestration_runs
```

### Airflow DAG end to end (`airflow dags test`, CI script `.github/scripts/airflow_dag_e2e.sh`)

```text
DagRun Finished: dag_id=dataforge_pipeline ... state=success
orchestration_run: ('airflow', 'success', 5, 5, None)
stage -> pipeline_run: [('bronze', 'source_to_bronze', 'success'), ('profiling', 'profiling', 'success'),
                        ('silver', 'silver_quality_gate', 'success'), ('gold', 'silver_to_gold', 'success'),
                        ('certification', None, None)]
profiling_result: [(1, 7, 5, True)]     # profile_id, row_count, column_count, source_asset_id == Bronze asset of this run
```

This proves `Source → Bronze → persistent profiling → Silver + Quality Gate → Gold → Certification` inside Airflow, with the trace chain `orchestration_run → orchestration_task_run(profiling) → pipeline_run(profiling) → profiling_result → Bronze asset`.

### Olist (Sprint 1 regression) through the orchestration

| Stage | customers | orders | order_items | products |
|---|---|---|---|---|
| Bronze rows | 99441 | 99441 | 112650 | 32951 |
| Profiling (`profiling_result` rows × columns) | 99441 × 5 | 99441 × 8 | 112650 × 7 | 32951 × 9 |
| Silver accepted / quarantined | 99441 / 0 | 99441 / 0 | 112650 / 0 | 32947 / 4 |

Gold `order_items_gold`: 112650 → 112642 (8 excluded). Identical to Sprint 1; all 13 data tasks are linked to their `pipeline_run`.

### Automated tests

```text
$ ruff check .                                   -> All checks passed!
$ python -m unittest discover -s tests -t .      -> Ran 263 tests, OK (skipped=26: integration + Airflow-only)
$ DATAFORGE_ENV_FILE=config/environments/test.env DATAFORGE_INTEGRATION=1     python -m unittest discover -s tests/integration -t .   -> Ran 22 tests, OK
```

Updated/new tests:

| Test | What it checks |
|---|---|
| `test_orchestration_stages.ProfilingStageTests` | `run_profiling` delegates to `discovery.service.execute_profiling_for_dataset` and returns the compact summary without the full profile |
| `test_orchestration_executor` | the profiling attempt is linked to its profiling `pipeline_run`, and the summary is persisted |
| `integration/test_orchestration` | profiling task is `success`; `pipeline_run.run_type = profiling`; `profiling_result` exists; `source_asset_id` is the run's Bronze asset; row/column counts; same for the PostgreSQL source |
| `integration/test_migrations_postgres` | `profiling_result` and its views exist next to the orchestration objects |

## Original verification (before #21 was merged)

All runs were executed on 2026-10-26 on Windows 11 (Docker 28, Compose 2.39), against an isolated Compose project (`dfaf`) containing the full stack: PostgreSQL, MinIO, `minio-init`, `migrate`, Airflow 3.3.1 DB/init/api-server/scheduler/dag-processor. Every run was triggered through the **Airflow REST API** with `python -m src.orchestration.airflow_client`.

### Stack health

```text
GET /api/v2/monitor/health -> metadatabase healthy, scheduler healthy, dag_processor healthy
```

### 1. Non-Olist CSV source (retail fixture)

```text
$ python -m src.orchestration.airflow_client --contract tests/fixtures/e2e/retail_contract.yaml --certification validate --wait
Run manual__2026-10-26T05:18:40.072299+00:00: SUCCESS
  resolve_plan / dataset_targets / gold_targets / start_run   success
  dataset.bronze[orders]           success          try=1
  dataset.profiling[orders]        success          try=1
  dataset.silver[orders]           success          try=1
  gold[orders_by_status]           success          try=1
  certification                    success          try=1
  finalize                         success          try=1
```

### 2. Olist through the generic DAG (Sprint 1 regression)

```text
$ python -m src.orchestration.airflow_client --contract config/examples/olist.yaml --certification validate --wait
Run manual__2026-10-26T05:20:21.598719+00:00: SUCCESS
  dataset.bronze/profiling/silver[customers|orders|order_items|products]   success (12 tasks)
  gold[order_items_gold]           success
  certification                    success
  finalize                         success
```

| Dataset | Stage | Input | Accepted | Rejected |
|---|---|---|---|---|
| customers / orders / order_items / products | source_to_bronze | 99441 / 99441 / 112650 / 32951 | same | 0 |
| products | silver_quality_gate | 32951 | 32947 | 4 |
| customers, orders, order_items | silver_quality_gate | as Bronze | all | 0 |
| order_items_gold | silver_to_gold | 112650 | 112642 | 8 |

These figures are identical to `quality-gate-verification.md` and `gold-transformation-verification.md`. In `validate` mode all 5 dataset versions (4 sources + Gold) moved to `validated`.

### 3. Structurally different source type: PostgreSQL (`config/examples/postgres_sales.yaml`)

The source was a throwaway `demo_sales` database seeded from the test fixture `tests/fixtures/postgres_sales/seed.sql`. The credentials were passed as `DATAFORGE_CONNECTION_DEMO_POSTGRES`. Same DAG, only the `contract` parameter changed:

```text
Run manual__2026-10-26T05:24:10.561261+00:00: SUCCESS
  dataset.bronze[sales]  dataset.profiling[sales]  dataset.silver[sales]  gold[sales_gold]  certification  finalize   success
sales       source_to_bronze      5 -> 5
sales       silver_quality_gate   5 -> 4 accepted, 1 quarantined (negative amount)
sales_gold  silver_to_gold        4 -> 4
```

### 4. Non-retryable failure (source table missing)

```text
Run manual__2026-10-26T05:25:22.177923+00:00: FAILED
  dataset.bronze[sales]            failed           try=1      <- no retries: data/config error
  dataset.profiling, dataset.silver, gold, certification   upstream_failed
  finalize                         failed

orchestration_run 4: failed | bronze[sales] failed: ConnectorExtractionError: PostgreSQL extraction failed
  for source 'sales-postgres': relation "public.sales" does not exist ...; profiling[sales] did not run;
  silver[sales] did not run; gold[sales_gold] did not run; certification[contract] did not run
```

### 5. Transient failure and retry (object storage down)

MinIO was stopped before triggering and restarted about 45 s later. The run used `stages = bronze, silver`:

```text
Run manual__2026-10-26T05:25:55.644550+00:00: SUCCESS
  dataset.bronze[sales]            success          try=2
  dataset.silver[sales]            success          try=1
  dataset.profiling[sales], gold, certification   skipped (not selected)

orchestration_task_run:
  bronze | sales | attempt 1 | failed  | EndpointConnectionError: Could not connect to the endpoint URL: "http://minio:9000/..."
  bronze | sales | attempt 2 | success
  silver | sales | attempt 1 | success
orchestration_run_summary: success | tasks 2 | retried_attempts 1
```

### 6. Legacy Sprint 1 DAG still works

```text
olist_alpha_pipeline: success  (source_to_bronze, bronze_to_silver, silver_quality_gate, silver_to_gold: success, try 1)
```

### Orchestration runs recorded in the control plane

```text
 id | orchestrator | client_code | status  | tasks | ok | failed | retries |  secs
  1 | airflow      | ci-retail   | success |     5 |  5 |      0 |       0 |  60.0
  2 | airflow      | olist       | success |    14 | 14 |      0 |       0 | 108.8
  3 | airflow      | demo-retail | success |     5 |  5 |      0 |       0 |  36.5
  4 | airflow      | demo-retail | failed  |     1 |  0 |      1 |       0 |   9.5
  5 | airflow      | demo-retail | success |     2 |  2 |      0 |       1 |  92.8
  6 | airflow      | ci-retail   | success |     4 |  4 |      0 |       0 |  16.3   (airflow dags test)
```

### `airflow dags test` (the CI job's execution path)

```text
$ bash .github/scripts/airflow_dag_e2e.sh      (inside the Airflow 3.3.1 image)
Applied 5 migration(s); 0 already applied.
tests.test_airflow_dag: 4 tests OK (import, params, task graph, retry/trigger policy)
DagRun Finished: dag_id=dataforge_pipeline ... state=success
orchestration_run: ('airflow', 'success', 5, 5, None)
```

### GitHub Actions

Run [40275535431](https://github.com/jcramonp/DataForge/actions/runs/40275535431) on PR #46: **all jobs green**.

```text
success  Lint (ruff)
success  Unit & regression tests (Python 3.11 / 3.13)
success  Integration (PostgreSQL + MinIO)   Applied 5 / then 0 migrations; Ran 20 tests
success  Airflow DAG (end-to-end)           Ran 4 DAG tests; DagRun dataforge_pipeline state=success;
                                            orchestration_run: ('airflow', 'success', 5, 5, None)
success  Frontend build
success  Compose config & API image
success  CI status
```

### Automated tests

```text
$ ruff check .                                   -> All checks passed!
$ python -m unittest discover -s tests -t .      -> Ran 249 tests, OK (skipped=24: 20 integration + 4 Airflow-only)
$ DATAFORGE_ENV_FILE=config/environments/test.env DATAFORGE_INTEGRATION=1 \
    python -m unittest discover -s tests/integration -t .   -> Ran 20 tests, OK
```

New tests:

| File | What it covers |
|---|---|
| `test_orchestration_plan.py` | Plan resolution and validation |
| `test_orchestration_executor.py` | Retry classification, run outcome, attempt recording, CLI runner semantics |
| `test_orchestration_stages.py` | Delegation to each runner (profiling to the #21 service after the merge); certification modes |
| `test_airflow_client.py` | REST auth, trigger, token renewal, polling |
| `test_airflow_dag.py` | DAG import, parameters, graph, retry/trigger policy |
| `integration/test_orchestration.py` | File source, PostgreSQL source and a failing run against real services |

## Acceptance criteria

| Criterion | Status | Evidence |
|---|---|---|
| A new configured dataset can run without creating a new DAG file named for that client/dataset | Met | Retail CSV, Olist and PostgreSQL sales ran through the same `dataforge_pipeline`; only the `contract` parameter changed |
| Airflow records success/failure and respects dependencies/retries | Met | Run 4: fail-fast, `upstream_failed` downstream, DAG and `orchestration_run` failed. Run 5: transient storage error retried (try 2) and succeeded. Per-dataset groups, Gold after all datasets, certification after Gold |
| Olist completes end-to-end through the generic orchestration path | Met | Run 2: 14/14 tasks, results identical to Sprint 1; re-verified after #21 with persisted profiling for all 4 tables |
| A second source completes through the same orchestration design | Met | Retail CSV (different schema) and PostgreSQL `sales` (different source type), both end to end including Gold and certification |

## Regression and compatibility

- The runners, the discovery/profiling service (#21), governance and contract code are unchanged. Orchestration only calls their public functions.
- The legacy `olist_alpha_pipeline` DAG still succeeds and now has a working `PYTHONPATH`.
- `migrate` adds migration `0006_orchestration_runs.sql` after #21's `0005_profiling_results.sql` (which this PR does not modify). It is additive and idempotent; existing databases are upgraded with `python -m src.ops.migrate`.
- No secrets were committed. The Airflow login and source credentials come from `.env`; `test.env` holds throwaway CI values only.

## Follow-ups outside this issue

- **#25:** wire `/api/pipelines/trigger` (and run status) to `src.orchestration.airflow_client` and the `orchestration_run_summary` view.
- **#28:** the same DAG and image run on AWS; provide `AIRFLOW_ADMIN_*` and `DATAFORGE_CONNECTION_*` from Secrets Manager.
