# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

DataForge is a contract-driven data engineering platform (EAFIT SI4002 course project). Declarative YAML/JSON contracts drive ingestion → Bronze → Silver + quality gate (failing rows → Quarantine) → Gold, with metadata in PostgreSQL and Parquet in MinIO (S3).

The Sprint 2 goal (`docs/sprint-2/scope.md`) is to prove that the *same* engine processes a second, structurally different source through configuration only:
- operable through the API and UI;
- with an LLM copilot that only proposes schema-validated configuration;
- with one end-to-end run on AWS.

Olist must keep working as the regression case.

## Commands

Run everything from the repo root; modules import as `src.*`.

- Setup: `cp .env.example .env`, `python -m pip install -r requirements-dev.txt`, `docker compose up -d postgres minio minio-init`, `python -m src.ops.migrate`, `python -m src.ops.health` (expect READY).
- Full stack incl. Airflow (UI :8080): `docker compose up -d`. Containerized API: `docker compose --profile api up -d --build`.
- API: `uvicorn src.api.main:app --reload --port 8000` (Swagger /docs, liveness `/api/health`, readiness `/api/ready`, metrics `/api/ops/summary`).
- Frontend (`frontend/`): `npm ci`, `npm run dev` (port **3000**, proxies `/api` → :8000), `npm run build`.
- Lint: `ruff check .` (config in `ruff.toml`).
- Tests use `unittest`; pytest is not a dependency.
  - all: `python -m unittest discover -s tests -t .`
  - one file: `python -m unittest tests.test_generic_silver_quality`
  - one test: `python -m unittest tests.test_generic_silver_quality.GenericSilverTransformationTests.test_apply_trim`
  - integration: needs disposable PostgreSQL :15432 and MinIO :19000 (see `docs/operations/runbook.md`), then `DATAFORGE_ENV_FILE=config/environments/test.env DATAFORGE_INTEGRATION=1 python -m unittest discover -s tests/integration -t .`. These tests drop the `public` schema and refuse to run unless `DATAFORGE_ENV=test`.
- Orchestrated pipeline (all stages of a contract):
  - Airflow (login `AIRFLOW_ADMIN_*` from `.env`): `python -m src.orchestration.airflow_client --contract config/examples/olist.yaml --wait`
  - without Airflow: `python -m src.orchestration.pipeline --contract ... [--datasets a,b] [--stages bronze,silver] [--certification validate]`
- Individual stages:
  - `python -m src.discovery.run_profiling --contract config/examples/olist.yaml`
  - `python -m src.ingestion.bronze_generic --contract ...`
  - `python -m src.transformations.silver_runner --contract ...`
  - `python -m src.transformations.gold_runner --contract ... [--gold-code X]`
- Ops: `python -m src.ops.migrate [--status|--dry-run]`, `python -m src.ops.health [--json]`, `python -m src.ops.run_summary [--json]`.

## Architecture

Two generations of pipeline code coexist:

1. **Sprint 1 "Alpha" Olist scripts** (`*_olist.py`): hard-coded for Olist tables, driven by `config/pilot_olist.json`. Orchestrated by the **legacy** `airflow/dags/olist_alpha_pipeline.py` (kept as a regression reference), which shells out to each script inside the container at `/opt/dataforge`.
2. **Sprint 2 generic engine** (`*_generic.py`, `silver_runner.py`, `gold_runner.py`, `connectors/`, `contracts/`, `discovery/engine.py`, `governance/`): driven by a `DataForgeContract`. New features go here. Per the PR template, no client-specific logic goes into generic engines.

Key pieces:
- `src/contracts/models.py`: Pydantic v2 contract.
  - `StrictModel` uses `extra="forbid"`, so unknown keys fail validation.
  - Validators check cross-references: PK/FK/quality/transformation columns must exist in the dataset schema, FKs and Gold joins must reference known datasets, and the required `source_object` fields depend on `source.type`.
  - Several fields use aliases: `schema`, `from`, `to`, `type`.
  - `config/schemas/dataforge-contract-v1.json` must match `model_json_schema(by_alias=True)`; `tests/test_contract_artifacts.py` enforces this.
- `src/connectors/`: `registry.get_connector` maps `SourceType` (file/postgresql/rest) to a connector. Credentials come from the env var `DATAFORGE_CONNECTION_<REF_UPPER_SNAKE>` (JSON), never from contracts.
- `src/common/`: shared runtime layer.
  - `settings.py`: `DATAFORGE_ENV` = local/test/aws. On aws, leave the storage endpoint and keys unset so boto3 uses the IAM role.
  - `clients.py`: `create_s3_client`, `connect_postgres`. Every stage's `minio_client()` / `postgres_connection()` delegates here; keep those module-level names, because tests patch them.
  - `log.py`: structured logging.
- Stage flow:
  1. `bronze_generic.ingest_dataset` extracts the source and writes Parquet to the bronze bucket.
  2. `silver_runner` reads the latest *successful* Bronze asset from Postgres, runs `silver_generic.transform_dataset`, then `quality_generic.evaluate_quality_rules` (Great Expectations).
  3. Rows failing `critical` rules go to Quarantine; `warning` rules are recorded but never reject rows.
  4. `gold_runner` executes the contract's declarative `gold[].plan` over the latest validated Silver assets.

  `src/governance/` owns asset lineage and Draft/Validated/Certified certification. Certification rows are created by a database trigger on `dataset_version`.
- Orchestration (`src/orchestration/`, `docs/operations/orchestration.md`):
  - One generic DAG, `airflow/dags/dataforge_pipeline.py`, is parameterized by `contract`/`datasets`/`gold`/`stages`/`certification`. The DAG file only declares tasks. A new source needs a contract, never a new DAG.
  - Flow: `plan.build_plan` validates the request against the contract, then `executor.execute_task` records each attempt in `orchestration_task_run`, then a `stages.run_*` function calls the existing runner.
  - `pipeline.py` runs the same plan without Airflow; `airflow_client.py` triggers it through the REST API.
  - Only transient infrastructure errors are retried (`executor.is_retryable`).
  - The profiling stage profiles the latest Bronze asset with the unchanged discovery engine and persists nothing; profiling persistence belongs to #21.
  - Certification `validate` mode only promotes `draft → validated`; `certified` is always a human step.
  - Airflow services need `PYTHONPATH=/opt/dataforge` (set in `docker-compose.yml`) and get source credentials via `env_file: .env`.
- Metadata pattern used by every stage:
  1. start a `pipeline_run`;
  2. write the Parquet output;
  3. register a `data_asset` with its SHA-256 checksum;
  4. finish the run as success. On error the stage rolls back, records the run as failed, and re-raises.
- Logging: generic stages (Bronze, Silver, Gold) wrap their work in `run_context(stage, client, project, dataset)` and call `bind_context(run_id=...)` once the run row exists, so every log line (JSON outside local) is traceable. New stages and orchestration should follow the same pattern. CLIs call `configure_logging()`.
- Runners are CLI entrypoints. Import them directly (`from src.transformations.gold_runner import ...`), never re-export them from a package `__init__`: that makes `python -m` execute them twice.
- Object key layout: `{client}/{project}/{dataset}/source_checksum={sha12}/[validated_v1/|quality_v1/]{dataset}.parquet`.
- Database: schema changes go in a **new** `database/migrations/NNNN_name.sql` (4 digits). It must be idempotent (`IF NOT EXISTS`, `CREATE OR REPLACE`) and must not contain `BEGIN`/`COMMIT`, because Docker init and the runner both apply files and the runner owns the transaction. Never edit an applied migration: the checksum check fails. Operational views (`pipeline_run_status_summary`, `pipeline_run_failures`, `dataset_latest_run`, `orchestration_run_summary`) back `src/ops/run_summary.py`.
- Local Docker on Windows: Hyper-V reserves blocks of ports ≥ 49152, so test ports stay below that (15432/19000). In Git Bash, prefix `docker run` that passes Linux paths with `MSYS_NO_PATHCONV=1`.
- `src/api/main.py`: FastAPI control plane.
  - Most UI endpoints serve **in-memory mock state** (`MOCK_RUNS`, …); `/api/pipelines/trigger` and `/api/copilot/suggest` are not wired to real runners or an LLM yet. #25 should wire the trigger to `src.orchestration.airflow_client`.
  - `/api/ready` and `/api/ops/summary` are real.
  - Request-ID middleware logs every request.
- `frontend/`: React 18 + Vite, plain CSS. All HTTP calls go through `src/services/api.js` (base `/api`).

## Workflow conventions

- Sprint 2 issue order and dependencies: `docs/sprint-2/backlog.md`. Owners: `docs/sprint-2/team-ownership.md`.
- Branches: `feature/<issue#>-<slug>`, `fix/…`, `docs/…`. PRs target `develop`; `main` only receives release merges.
- Commits use conventional prefixes (`feat(scope):`, `test(scope):`, `docs(scope):`).
- CI (`.github/workflows/ci.yml`) must be green; the aggregate check is **`CI status`**.
- Each feature PR adds `docs/evidence/<feature>-verification.md` and follows `.github/pull_request_template.md`, which requires rechecking Sprint 1/Olist behavior whenever shared pipeline code changes.
- Operations docs: `docs/operations/`.
