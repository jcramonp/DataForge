# DataForge operations

Operational documentation for issue **#32 — CI/CD, observability and deployment hardening**.

| Document | Covers |
|---|---|
| [`configuration.md`](configuration.md) | Environments (`local`/`test`/`aws`), every runtime variable, secrets handling and AWS IAM permissions |
| [`migrations.md`](migrations.md) | Versioned control-plane schema migrations and how to add one |
| [`orchestration.md`](orchestration.md) | Generic Airflow DAG `dataforge_pipeline`: parameters, triggering (UI, REST API, CLI), retries, run state, onboarding a source |
| [`observability.md`](observability.md) | Health/readiness, structured logs, run metrics, tracing a failed pipeline |
| [`runbook.md`](runbook.md) | Rebuilding the demo from scratch, deploying, rollback and recovery |

## Continuous integration

`.github/workflows/ci.yml` runs on every pull request to `develop`/`main`, on pushes to those branches and on demand.

| Job | What it validates |
|---|---|
| **Lint (ruff)** | Syntax errors, undefined names, unused imports/variables (`ruff.toml`) |
| **Unit & regression tests** | Full `unittest` suite on Python 3.11 and 3.13: Sprint 1 Olist modules, Sprint 2 contracts/connectors/profiling/Silver/quality, API, settings, logging, migrations, readiness |
| **Integration (PostgreSQL + MinIO)** | Applies migrations twice to an empty PostgreSQL 16 (idempotency), runs `tests/integration` — migration workflow, an end-to-end generic pipeline (Bronze → Silver → Quality Gate → Quarantine → Gold, with certification bootstrap) on a non-Olist fixture, and the standalone orchestration for a file source and a PostgreSQL source — and the readiness CLI |
| **Airflow DAG (end-to-end)** | Builds the Airflow image, checks DAG import/structure (`tests/test_airflow_dag.py`) and executes `dataforge_pipeline` for real with `airflow dags test` against PostgreSQL + MinIO (`.github/scripts/airflow_dag_e2e.sh`) |
| **Frontend build** | `npm ci` + `npm run build` |
| **Compose config & API image** | `docker compose config` (with and without the `api` profile), builds the API image and smoke-tests its liveness endpoint |
| **CI status** | Aggregates the jobs above; fails if any failed, was cancelled or skipped |

Run the same checks locally:

```bash
python -m pip install -r requirements-dev.txt
ruff check .
python -m unittest discover -s tests -t .
cd frontend && npm ci && npm run build
```

Integration tests locally: see [`runbook.md`](runbook.md#run-the-integration-suite-locally).

### Requiring CI before merge

The workflow runs on every PR automatically. To make a green run **mandatory** before merge, a repository admin enables branch protection on `develop` and `main` with the required status check **`CI status`**:

```bash
gh api -X PUT repos/jcramonp/DataForge/branches/develop/protection \
  -F required_status_checks[strict]=true \
  -F "required_status_checks[contexts][]=CI status" \
  -F enforce_admins=false \
  -F required_pull_request_reviews[required_approving_review_count]=1 \
  -F restrictions=
```

(GitHub UI: *Settings → Branches → Add rule → Require status checks to pass → `CI status`*.)

### Continuous delivery

Delivery artifacts are produced and validated by CI but not yet pushed to a registry: the cloud target is created in #28. The API image (`Dockerfile`) is the same artifact for local Compose (`--profile api`) and AWS compute; [`runbook.md`](runbook.md#deploying-a-release) describes the release/rollback flow the AWS pipeline must follow.
