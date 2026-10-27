# Operations runbook

Commands run from the repository root unless stated otherwise.

## Rebuilding the demo environment from scratch

Use this to reproduce the final demo on a clean machine. Prerequisites: Python 3.11+, Node.js 18+ (CI uses 20) and Docker with Compose v2.

```bash
git clone https://github.com/jcramonp/DataForge.git && cd DataForge
cp .env.example .env                         # then replace the change_me_* passwords
python -m pip install -r requirements-dev.txt

docker compose up -d postgres minio minio-init
python -m src.ops.migrate                    # schema at the latest version
python -m src.ops.health                     # expect READY

# Olist raw CSVs go in data/raw/olist/ (see data/README.md)
# Whole pipeline (Bronze -> profiling -> Silver + Quality Gate -> Gold -> certification):
python -m src.orchestration.pipeline --contract config/examples/olist.yaml
python -m src.ops.run_summary

# Same pipeline through Airflow (UI http://localhost:8080, login from .env):
docker compose up -d
python -m src.orchestration.airflow_client --contract config/examples/olist.yaml --wait

uvicorn src.api.main:app --host 0.0.0.0 --port 8000      # terminal 1
cd frontend && npm ci && npm run dev                     # terminal 2 -> http://localhost:3000
```

Containerized API instead of host uvicorn: `docker compose --profile api up -d --build`, then open `http://localhost:8000/api/ready`. The full stack including Airflow (UI on `:8080`) starts with `docker compose up -d`.

Verify the build the same way CI does: `ruff check .`, `python -m unittest discover -s tests -t .` and `cd frontend && npm run build`.

## Run the integration suite locally

Integration tests reset the database schema, so they only run with `DATAFORGE_ENV=test`. Use disposable containers on separate ports so local data is not touched:

```bash
docker run -d --rm --name dataforge-it-postgres -p 15432:5432 \
  -e POSTGRES_DB=dataforge_test -e POSTGRES_USER=dataforge -e POSTGRES_PASSWORD=dataforge_test postgres:16-alpine
docker run -d --rm --name dataforge-it-minio --user 0:0 -p 19000:9000 \
  -e MINIO_ROOT_USER=dataforge -e MINIO_ROOT_PASSWORD=dataforge_test cgr.dev/chainguard/minio:latest server /data

export DATAFORGE_ENV_FILE=config/environments/test.env DATAFORGE_INTEGRATION=1
python -m unittest discover -s tests/integration -t . -v

docker stop dataforge-it-postgres dataforge-it-minio     # --rm deletes them
```

PowerShell: `$env:DATAFORGE_ENV_FILE="config/environments/test.env"; $env:DATAFORGE_INTEGRATION="1"`.

## Deploying a release

Applies locally today and to AWS from #28.

1. Merge to `develop` only with a green **CI status**. The release PR `develop` → `main` must also be green.
2. Tag the release: `git tag -a vX.Y.Z -m "..." && git push origin vX.Y.Z`. Build the image as `dataforge-api:<git-sha>`, never a mutable `latest`.
3. Run migrations **before** starting the new application version: `docker compose run --rm migrate`, or the same image as a one-off ECS task with `python -m src.ops.migrate`.
4. Roll out the new image. On ECS, use rolling deployment with the load balancer checking `/api/ready`, so new tasks only receive traffic once ready.
5. Verify:
   - `GET /api/ready` returns `200`;
   - `python -m src.ops.migrate --status` shows nothing pending;
   - run a smoke pipeline, then check `python -m src.ops.run_summary` shows no new failures.

## Rollback

| What went wrong | Action |
|---|---|
| Bad application release | Redeploy the previous image tag (`docker compose up -d` with the previous checkout/tag; on ECS, update the service to the previous task definition revision). Schema changes are additive, so the previous version runs against the newer schema. |
| Bad commit on `develop`/`main` | `git revert <sha>` in a PR. Do not force-push shared branches. |
| Bad migration | Fix forward with a new migration that reverts it (see [`migrations.md`](migrations.md#rolling-back-schema-changes)). For destructive changes, restore the pre-deploy snapshot. |
| Broken frontend build | Redeploy the previous `frontend/dist` artifact; the frontend is static and independent of the API version. |

## Recovering a failed pipeline run

1. Identify it with `python -m src.ops.run_summary`; trace its logs by `run_id` ([`observability.md`](observability.md#tracing-a-failed-pipeline)).
2. Fix the cause: source unavailable, bad contract, missing bucket/object, or credentials.
3. Re-run the stage.
   - Bronze is content-addressed: re-ingesting identical source data writes to the same `source_checksum=` key and creates a new run.
   - Silver always reads the latest **successful** Bronze asset, so a failed run never poisons later runs.
   - Re-runs are safe; the failed run stays recorded for audit.
4. A run left in `running` (process killed) stays visible in `running_runs`. After confirming no process is active, mark it:

   ```sql
   UPDATE pipeline_run SET status = 'failed', finished_at = NOW(),
          error_message = 'Marked failed manually: process terminated'
   WHERE run_id = <id> AND status = 'running';
   ```

5. Quarantined rows are not failures. Inspect them in the quarantine bucket or UI, fix the source or the contract rule, and re-run.

## Backup and restore (local)

```bash
# Control plane
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > backup/dataforge.dump
docker compose exec -T postgres pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists < backup/dataforge.dump

# Data lake (MinIO volume)
docker run --rm -v dataforge_minio_data:/data -v "$PWD/backup":/backup alpine tar czf /backup/minio.tgz -C /data .
```

`docker compose down` keeps the data; `docker compose down -v` deletes **both** volumes (full reset). The next `up` re-bootstraps the schema from `database/migrations/`.

On AWS (#28): enable RDS automated backups and take a manual snapshot before each release with migrations; enable S3 versioning on the layer buckets.

## Common incidents

| Symptom | Likely cause | Check / fix |
|---|---|---|
| `pull access denied for minio/minio` | The official MinIO images were removed from Docker Hub/quay.io | Pull `cgr.dev/chainguard/minio` and `cgr.dev/chainguard/minio-client` (already used by `docker-compose.yml` and CI); remove old local tags with `docker rmi minio/minio minio/mc` |
| `/api/ready` 503 on `postgres: pending migrations` | New code deployed without migrating | `python -m src.ops.migrate` |
| `/api/ready` 503 on `object_storage` | Bucket missing or no permission | `docker compose up minio-init`; on AWS check the task role policy |
| `Migration ... was modified after being applied` | An applied migration file was edited | Revert the edit; put the change in a new migration |
| `SettingsError: Missing PostgreSQL configuration` | `.env`/environment incomplete | `python -m src.ops.health` lists every missing variable |
| Silver fails with `No successful Bronze asset found` | Bronze never ran or failed for that dataset | Run Bronze first; check `dataset_latest_run` |
