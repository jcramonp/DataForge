# FastAPI control plane (#25)

The main workflow uses FastAPI exclusively. PostgreSQL stores executable contract revisions and metadata; MinIO/S3 stores Parquet assets. The browser has no database credentials or direct PostgreSQL connection.

## Start or reload the updated application

From the repository root, activate the project environment and run:

```powershell
python -m uvicorn src.api.main:app --reload --port 8000
```

If an older API process already owns port 8000, stop that process in its original terminal and restart it with the command above. Editing Python files does not update a server started without `--reload`. Do not launch a second server on the same port.

In another terminal:

```powershell
cd frontend
npm run dev
```

Reload the browser at `http://localhost:3000`. The global source list is read from registered PostgreSQL metadata. It filters Overview, Datasets/Profiling, Quality/Quarantine, Pipelines/Runs, Assets and Lineage/Governance by client, project and source. Onboarding creates a new scope and is not restricted by that filter.

For a separate verification instance, set `DATAFORGE_API_URL` before starting Vite. Its default remains `http://localhost:8000`.

## Main workflow

1. In Source Onboarding, supply the client/project/source/dataset configuration and a declared schema. Test the connector, then register. `POST /api/onboarding/contracts` atomically persists the metadata and executable contract. Identical submissions reuse the revision; changes create a new immutable revision. The UI displays the persisted contract ID.
2. Open Pipelines/Runs and select that source's active contract. Overview's **Choose Pipeline** button opens this selection; it does not launch a hardcoded demo dataset. The trigger sends `contract_id` to FastAPI; FastAPI validates the plan and submits it to the generic Airflow DAG. Live state comes from Airflow; durable history comes from PostgreSQL.
3. Inspect Datasets/Profiling and Quality/Quarantine. Dataset requests include client/project/source identity so matching codes in different scopes cannot collide. Missing profiling is reported explicitly; it is never replaced by synthetic facts.
4. Inspect Data Assets. The table reads `/api/assets`, filters layers on the server and shows the most recent 100 or 200 matching assets. Nullable metrics/checksums remain unknown instead of crashing the table. Assets from generated Gold outputs remain visible even if the output has no declared source schema.
5. Inspect Lineage/Governance. Each arrow represents an actual stored asset relationship. Promote `draft -> validated -> certified` explicitly; invalid transitions remain rejected.

Airflow workers must have the same source connection environment variables as the API. A missing `DATAFORGE_CONNECTION_ENV_DATA_RAW_DIR` belongs to that source configuration, not to a later successful revised contract. A Gold stage with no configured targets may be skipped while the pipeline succeeds.

## Metrics and unavailable services

Overview aggregates the complete scoped history, independently of the five recent rows displayed. Processed rows are cumulative input of successful Bronze runs; quarantined rows are cumulative rejections from successful Silver quality gates. Repeated ingestions count again. These metrics are not the row count of the latest materialized output. Certification counts use the latest dataset version.

Overview and `/api/ops/summary` return `503` when PostgreSQL is unavailable, including in local development. The header reports whether its most recent metadata request succeeded and rechecks every 30 seconds; it does not assert that every source connector or Airflow is healthy. `/api/ready` checks dependencies separately.

OpenAPI is available at `/openapi.json` and interactive documentation at `/docs`.

The deterministic copilot preview and its real LLM/configuration application workflow belong to the separate copilot issue; they are not acceptance evidence for #25.

## Validation

```powershell
python -m unittest discover -s tests -t .
ruff check .
git diff --check
cd frontend
npm test
npm run build
```

Integration tests require disposable services: follow `runbook.md`. Their normal reset helpers delete test schemas and prefixes; never point them at the application database/storage. The #25 verification used fresh databases and buckets on dedicated ports instead of deleting existing schemas or objects; see the evidence document.
