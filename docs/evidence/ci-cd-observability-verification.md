# CI/CD, Observability and Deployment Hardening Verification

## Scope

This evidence verifies **Issue #32: Add CI/CD, observability and deployment hardening** for Sprint 2.

The goal is to make the near-final DataForge platform reproducible, testable and operable across local and AWS environments, without changing pipeline business behavior. The work is integrated with the Gold engine (#31, PR #41) and with lineage/certification (#23, PR #43), both merged into `develop` while this issue was in progress.

## Delivered capabilities

| Issue deliverable | Implementation |
|---|---|
| GitHub Actions pipeline for tests/lint/build | `.github/workflows/ci.yml`: ruff lint, unit/regression suite (Python 3.11 + 3.13), integration with PostgreSQL 16 + MinIO, frontend build, Compose validation, API image build + smoke test, aggregate `CI status` check |
| Automated regression tests for Sprint 1 and Sprint 2 | All existing Sprint 1/2 suites are discoverable and dependency-complete. New: unit tests for every #32 component, a guard on example contracts and the published JSON Schema, and 12 integration tests, including the generic pipeline Bronze → Silver → Quality Gate → Quarantine → Gold with certification bootstrap on a non-Olist fixture (`tests/fixtures/e2e/`) |
| Health/readiness endpoints | `GET /api/health` (liveness), `GET /api/ready` (configuration, PostgreSQL + pending migrations, buckets, contracts; `503` on failure), `python -m src.ops.health`, Docker `HEALTHCHECK`, Compose dependency ordering |
| Structured logging with run/dataset identifiers | `src/common/log.py`: JSON/text formatter, `run_context`/`bind_context` used by generic Bronze, Silver and Gold; request-ID middleware in the API; secret redaction |
| Operational metrics / status summaries | Migration `0004_operational_views.sql` (`pipeline_run_status_summary`, `pipeline_run_failures`, `dataset_latest_run`), `python -m src.ops.run_summary`, `GET /api/ops/summary` |
| Environment-specific configuration (local/test/cloud) | `src/common/settings.py` + `src/common/clients.py` (`DATAFORGE_ENV`), `.env.example`, `config/environments/test.env`, `config/environments/aws.env.example`. All 8 pipeline modules build clients through `src/common` |
| Database migration workflow | `database/migrations/NNNN_*.sql` + `python -m src.ops.migrate` (`schema_migrations`, checksums, advisory lock, `--status`, `--dry-run`), `migrate` Compose service |
| Runtime configuration and cloud permissions docs | `docs/operations/configuration.md`: variable reference, secrets handling, least-privilege IAM policies, network baseline |
| Deployment runbook, rollback and recovery | `docs/operations/runbook.md`, `docs/operations/migrations.md`, `docs/operations/observability.md` |

## Migration history consolidated

| Version | File | Origin |
|---|---|---|
| 0001 | `0001_control_plane_schema.sql` | `database/schema.sql` (unchanged) |
| 0002 | `0002_lineage_certification.sql` | `database/migrations/002_lineage_certification.sql` from #23. Renumbered to 4 digits; its `BEGIN;`/`COMMIT;` were removed because the runner owns the transaction. No other changes |
| 0003 | `0003_governance_views.sql` | `database/governance_views.sql`, including the #23 lineage/certification views (unchanged) |
| 0004 | `0004_operational_views.sql` | New (#32) |

The order follows the dependencies: the governance views reference the #23 tables.

## Fixes found while hardening

- `tests/__init__.py` was missing, so `python -m unittest discover -s tests` failed with *Start directory is not importable*.
- `httpx` was missing from `requirements.txt`. `fastapi.testclient` needs it, so the API tests could not import on a clean install.
- The new lint step reported 10 unused imports, including one in the #31 Gold test.
- `src/transformations/__init__.py` re-exported the runners. That made `python -m src.transformations.silver_runner` / `gold_runner` execute their module twice (runpy `RuntimeWarning`). The runners are now imported directly.
- The README referenced `src.ingestion.bronze_runner`, which does not exist. Generic Bronze now has a CLI (`python -m src.ingestion.bronze_generic --contract ...`).
- The README listed the frontend on `:5173`; Vite serves on `:3000`.
- Before this change, every stage built MinIO/PostgreSQL clients from hard-coded `MINIO_*` variables and could not target Amazon S3 with an IAM role.

## Verification

All commands were run locally on 2026-10-25, on Windows 11 with Python 3.13, Node 22 and Docker 28. Integration runs used disposable `postgres:16-alpine` (:55432) and `minio/minio` (:59000) containers.

### Lint and unit/regression suite

```text
$ ruff check .
All checks passed!

$ python -m unittest discover -s tests -t .
Ran 186 tests
OK (skipped=12)        # 174 unit tests; the 12 integration tests skip without services
```

### Integration suite (real PostgreSQL + MinIO)

```text
$ DATAFORGE_ENV_FILE=config/environments/test.env DATAFORGE_INTEGRATION=1 python -m unittest discover -s tests/integration -t . -v
test_failed_run_is_recorded_with_error ... ok
test_failure_view_links_run_to_dataset ... ok
test_bronze_ingests_every_source_row ... ok
test_control_plane_metadata_is_recorded ... ok
test_every_dataset_version_starts_as_draft ... ok
test_gold_plan_aggregates_validated_silver ... ok
test_operational_summary_reflects_runs ... ok
test_quality_gate_routes_only_critical_failures_to_quarantine ... ok
test_services_report_ready ... ok
test_database_bootstrapped_by_docker_init_is_adopted ... ok
test_edited_applied_migration_is_rejected ... ok
test_fresh_database_is_migrated_and_rerun_is_a_noop ... ok
Ran 12 tests
OK
```

### Migrations: Docker first-boot bootstrap, then adoption by the runner

```text
$ docker run ... -v ./database/migrations:/docker-entrypoint-initdb.d:ro postgres:16-alpine
running /docker-entrypoint-initdb.d/0001_control_plane_schema.sql
running /docker-entrypoint-initdb.d/0002_lineage_certification.sql
running /docker-entrypoint-initdb.d/0003_governance_views.sql
running /docker-entrypoint-initdb.d/0004_operational_views.sql

$ python -m src.ops.migrate
Applied migration 0001_control_plane_schema ... 0004_operational_views
Applied 4 migration(s); 0 already applied.
$ python -m src.ops.migrate
Applied 0 migration(s); 4 already applied.
```

### Readiness

```text
$ python -m src.ops.health
OK   configuration        0.0 ms  environment=test
OK   postgres            34.8 ms  connected; schema version 0004
OK   object_storage     466.2 ms  4 buckets reachable
OK   contracts           73.1 ms  2 contracts valid
READY
```

### Sprint 1 regression: Olist end-to-end through the generic path

```text
$ python -m src.ingestion.bronze_generic --contract config/examples/olist.yaml
- customers: 99441 rows   - orders: 99441 rows   - order_items: 112650 rows   - products: 32951 rows
$ python -m src.transformations.silver_runner --contract config/examples/olist.yaml
- customers: 99441 input, 99441 accepted, 0 quarantined
- orders: 99441 input, 99441 accepted, 0 quarantined
- order_items: 112650 input, 112650 accepted, 0 quarantined
- products: 32951 input, 32947 accepted, 4 quarantined
$ python -m src.transformations.gold_runner --contract config/examples/olist.yaml
- order_items_gold: 112650 input base rows, 112642 Gold rows, 8 excluded
$ python -m src.ops.run_summary
Runs: 9 total | 9 success | 0 failed | 0 running | failure rate 0.0% | rejected rows 12
dataset_certification: [('draft', 5)]
```

The `products` outcome (32,947 / 4) and the Gold outcome (112,642 rows / 8 excluded) match `quality-gate-verification.md` and `gold-transformation-verification.md`.

### A failed pipeline traced through logs to its run and dataset

The Bronze object was deleted on purpose and Silver was re-run:

```text
$ python -m src.transformations.silver_runner --contract tests/fixtures/e2e/retail_contract.yaml
{"level": "INFO",  "logger": "src.transformations.silver_runner", "message": "Silver + Quality Gate started", "stage": "silver_quality_gate", "client": "ci-retail", "project": "ci-retail-e2e", "dataset": "orders"}
{"level": "ERROR", "logger": "src.transformations.silver_runner", "message": "Silver + Quality Gate failed", "stage": "silver_quality_gate", "client": "ci-retail", "project": "ci-retail-e2e", "dataset": "orders", "run_id": 2, "exception": "..."}

$ python -m src.ops.run_summary
Runs: 2 total | 1 success | 1 failed | 0 running | failure rate 50.0% | rejected rows 0
Recent failures:
  run_id=2 ci-retail/orders silver_quality_gate at 2026-10-26T01:15:09Z: An error occurred (404) when calling the HeadObject operation: Not Found
```

Gold logs carry the same context:

```text
{"level": "INFO", "logger": "src.transformations.gold_runner", "message": "Gold transformation finished", "stage": "silver_to_gold", "client": "ci-retail", "dataset": "orders_by_status", "run_id": 3, "input_rows": 4, "output_rows": 3, ...}
```

### Container image (same artifact for local and AWS)

```text
$ docker build -t dataforge-api:verify .
$ docker run ... -e DATAFORGE_ENV=test ... dataforge-api:verify
GET /api/health -> {"status":"healthy","service":"DataForge Control Plane","version":"2.0.0","environment":"test",...}
GET /api/ready  -> HTTP 200
docker inspect -> health: healthy
{"level": "INFO", "logger": "dataforge.api", "message": "GET /api/ready -> 200", "request_id": "bd5a3fba...", "status_code": 200, "duration_ms": 249.22}

$ docker compose --env-file .env.example config -q        # OK
$ cd frontend && npm ci && npm run build                  # built in 5.33s
```

## Acceptance criteria

| Criterion | Status | Evidence |
|---|---|---|
| Pull requests run automated validation before merge | Met: the workflow runs on every PR to `develop`/`main`. Making it **blocking** requires enabling branch protection with the `CI status` check (admin setting, command in `docs/operations/README.md`) | `.github/workflows/ci.yml`, CI run on this PR |
| A failed pipeline can be traced through logs to a run and dataset | Met | Log + summary output above; `tests/test_pipeline_observability.py`; `FailedPipelineTraceabilityTests` |
| Local and AWS deployments use the same application code with environment-specific configuration | Met for code/configuration: one image and one code path, only `DATAFORGE_ENV` and variables differ; the `aws` configuration (no endpoint, IAM credential chain, TLS to RDS) is unit-tested. The physical AWS run is delivered in #28 | `src/common/settings.py`, `tests/test_common_settings.py`, `config/environments/aws.env.example` |
| Database schema changes are reproducible | Met | 4 versioned migrations + runner; Docker bootstrap and runner adoption verified; CI applies them twice on an empty database |
| Final demo can be rebuilt from documented steps | Met | `docs/operations/runbook.md`; its commands were executed for this evidence |

## Regression and compatibility

- Sprint 1 Olist unit tests and the #23/#31 suites (`test_certification`, `test_lineage`, `test_governance_metadata`, `test_generic_gold`) pass.
- Olist runs end-to-end through generic Bronze, Silver and Gold against real services with the shared clients. Results match Sprint 1.
- The Olist Alpha scripts and the Airflow DAG keep their entrypoints. Only their client construction goes through `src/common`, which reads the same `POSTGRES_*`/`MINIO_*` variables.
- Existing local volumes are adopted by `python -m src.ops.migrate`, because every migration is idempotent.
- No client-specific logic was added to generic engines, and no secrets were committed (`test.env` holds throwaway CI values only).

## Remaining work tracked outside this issue

- Pushing images to a registry and deploying to ECS, with RDS/S3 and AWS execution evidence: **#28**.
- Metadata-driven orchestration (**#24**) should call the instrumented stage functions so Airflow task logs inherit `run_context`.
