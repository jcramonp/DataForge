# CI/CD, Observability and Deployment Hardening Verification

## Scope

This evidence verifies **Issue #32: Add CI/CD, observability and deployment hardening** for Sprint 2.

The goal is to make the near-final DataForge platform reproducible, testable and operable across local and AWS environments, without changing pipeline business behavior.

## Delivered capabilities

| Issue deliverable | Implementation |
|---|---|
| GitHub Actions pipeline for tests/lint/build | `.github/workflows/ci.yml`: ruff lint, unit/regression suite (Python 3.11 + 3.13), integration with PostgreSQL 16 + MinIO, frontend build, Compose validation, API image build + smoke test, aggregate `CI status` check |
| Automated regression tests for Sprint 1 and Sprint 2 | Existing Sprint 1/2 suites now discoverable and dependency-complete, plus 46 new unit tests and 10 integration tests. Includes an end-to-end generic pipeline on a non-Olist fixture (`tests/fixtures/e2e/`) and a guard on contract examples and the published JSON Schema |
| Health/readiness endpoints | `GET /api/health` (liveness), `GET /api/ready` (configuration, PostgreSQL + pending migrations, buckets, contracts; `503` on failure), `python -m src.ops.health`, Docker `HEALTHCHECK`, Compose dependency ordering |
| Structured logging with run/dataset identifiers | `src/common/log.py`: JSON/text formatter, `run_context`/`bind_context` used by generic Bronze and Silver, request-ID middleware in the API, secret redaction |
| Operational metrics / status summaries | Migration `0003_operational_views.sql` (`pipeline_run_status_summary`, `pipeline_run_failures`, `dataset_latest_run`), `python -m src.ops.run_summary`, `GET /api/ops/summary` |
| Environment-specific configuration (local/test/cloud) | `src/common/settings.py` + `src/common/clients.py` (`DATAFORGE_ENV`), `.env.example`, `config/environments/test.env`, `config/environments/aws.env.example`. All 7 pipeline modules use the shared clients |
| Database migration workflow | `database/migrations/NNNN_*.sql` + `python -m src.ops.migrate` (`schema_migrations`, checksums, advisory lock, `--status`, `--dry-run`), `migrate` Compose service |
| Runtime configuration and cloud permissions docs | `docs/operations/configuration.md`: variable reference, secrets handling, least-privilege IAM policies, network baseline |
| Deployment runbook, rollback and recovery | `docs/operations/runbook.md`, `docs/operations/migrations.md`, `docs/operations/observability.md` |

## Fixes found while hardening

- `tests/__init__.py` was missing, so `python -m unittest discover -s tests` failed with *Start directory is not importable*.
- `httpx` was missing from `requirements.txt`. `fastapi.testclient` needs it, so the API tests could not even import on a clean install.
- 9 unused imports reported by the new lint step were removed.
- The README referenced `src.ingestion.bronze_runner`, which does not exist. Generic Bronze now has a CLI (`python -m src.ingestion.bronze_generic --contract ...`) and the README points to it.
- The README listed the frontend on `:5173`; Vite serves on `:3000`.
- Before this change, every stage built MinIO/PostgreSQL clients from hard-coded `MINIO_*` variables and could not target Amazon S3 with an IAM role.

## Verification

All commands below were run locally on 2026-10-25, on Windows 11 with Python 3.13, Node 22 and Docker 28. Integration runs used disposable `postgres:16-alpine` (:55432) and `minio/minio` (:59000) containers.

### Lint and unit/regression suite

```text
$ ruff check .
All checks passed!

$ python -m unittest discover -s tests -t .
Ran 136 tests
OK
```

### Integration suite (real PostgreSQL + MinIO)

```text
$ DATAFORGE_ENV_FILE=config/environments/test.env DATAFORGE_INTEGRATION=1 python -m unittest discover -s tests/integration -t . -v
test_failed_run_is_recorded_with_error ... ok
test_failure_view_links_run_to_dataset ... ok
test_bronze_ingests_every_source_row ... ok
test_control_plane_metadata_is_recorded ... ok
test_operational_summary_reflects_runs ... ok
test_quality_gate_routes_only_critical_failures_to_quarantine ... ok
test_services_report_ready ... ok
test_database_bootstrapped_by_docker_init_is_adopted ... ok
test_edited_applied_migration_is_rejected ... ok
test_fresh_database_is_migrated_and_rerun_is_a_noop ... ok
Ran 10 tests
OK
```

### Migrations and readiness

```text
$ python -m src.ops.migrate --status
applied  0001_control_plane_schema
applied  0002_governance_views
applied  0003_operational_views
$ python -m src.ops.migrate
Applied 0 migration(s); 3 already applied.
$ python -m src.ops.health
OK   configuration        0.0 ms  environment=test
OK   postgres            34.4 ms  connected; schema version 0003
OK   object_storage     228.3 ms  4 buckets reachable
OK   contracts           33.8 ms  2 contracts valid
READY
```

### Sprint 1 regression: Olist through the generic path with the refactored clients

```text
$ python -m src.ingestion.bronze_generic --contract config/examples/olist.yaml
- customers: 99441 rows -> s3://dataforge-bronze/olist/olist-alpha/customers/source_checksum=6e8371d6364d/customers.parquet (run_id=3)
- orders: 99441 rows -> ... (run_id=4)
- order_items: 112650 rows -> ... (run_id=5)
- products: 32951 rows -> ... (run_id=6)
$ python -m src.transformations.silver_runner --contract config/examples/olist.yaml
- customers: 99441 input, 99441 accepted, 0 quarantined (run_id=7)
- orders: 99441 input, 99441 accepted, 0 quarantined (run_id=8)
- order_items: 112650 input, 112650 accepted, 0 quarantined (run_id=9)
- products: 32951 input, 32947 accepted, 4 quarantined (run_id=10)
```

The `products` outcome (32,947 validated / 4 quarantined) matches the Sprint 1 quality-gate evidence.

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
| Database schema changes are reproducible | Met | Migrations + runner; CI applies them twice on an empty database |
| Final demo can be rebuilt from documented steps | Met | `docs/operations/runbook.md`; every command in it was executed for this evidence |

## Regression and compatibility

- Sprint 1 Olist unit tests (`test_bronze_ingestion`, `test_silver_transformation`, `test_quality_gate`, `test_gold_transformation`, `test_profile_olist`) pass unchanged.
- Olist runs end-to-end through the generic Bronze and Silver path against real services with the refactored clients (output above).
- The Olist Alpha scripts and Airflow DAG keep their entrypoints. Only their client construction now goes through `src/common`, which reads the same `POSTGRES_*`/`MINIO_*` variables.
- `database/schema.sql` and `database/governance_views.sql` moved to `database/migrations/0001_*.sql` and `0002_*.sql` without content changes. Existing local volumes are adopted by `python -m src.ops.migrate`.
- No client-specific logic was added to generic engines, and no secrets were committed (`test.env` holds throwaway CI values only).

## Remaining work tracked outside this issue

- Pushing images to a registry and deploying to ECS, with RDS/S3 and AWS execution evidence: **#28**.
- Using `run_context`/`bind_context` in the generic Gold runner (**#31**, PR #41) and in the metadata-driven orchestration (**#24**).
