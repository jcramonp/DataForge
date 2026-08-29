# DataForge Alpha local runtime

This document covers checklist steps 6 and 7 for the Sprint 1 Alpha: the minimal Docker Compose runtime and the local PostgreSQL + MinIO services.

## Services

### PostgreSQL

Purpose: DataForge operational metadata/control plane. It stores clients, projects, sources, datasets, dataset versions, pipeline runs, quality results and produced data assets. Client business data is not stored here as the primary lake storage.

The container mounts `database/schema.sql` into PostgreSQL's initialization directory. On the first creation of the PostgreSQL volume, the schema is created automatically.

Default host access after configuring `.env`:

- host: `localhost`
- port: `POSTGRES_PORT` (default 5432)
- database/user/password: values from `.env`

### MinIO

Purpose: S3-compatible object storage for Parquet data produced by the Alpha pipeline.

The runtime exposes:

- S3 API: `http://localhost:9000` by default
- web console: `http://localhost:9001` by default

A one-shot `minio-init` container creates these buckets if they do not already exist:

- `dataforge-bronze`
- `dataforge-silver`
- `dataforge-quarantine`
- `dataforge-gold`

The exact names are configurable through `.env`.

## First local run

From the repository root:

```bash
cp .env.example .env
```

Edit `.env` and replace both `change_me_*` passwords before starting the stack. `.env` is excluded from Git and must never be committed.

Validate the Compose file:

```bash
docker compose config
```

Start the runtime:

```bash
docker compose up -d
```

Inspect services:

```bash
docker compose ps
```

Expected state:

- `dataforge-postgres`: running and healthy
- `dataforge-minio`: running and healthy
- `dataforge-minio-init`: exits with code 0 after creating/checking buckets

## Verification

### PostgreSQL

Run:

```bash
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dt"
```

If your shell does not load variables from `.env`, replace the values explicitly, for example:

```bash
docker compose exec postgres psql -U dataforge -d dataforge -c "\dt"
```

The output should include the operational metadata tables such as `client`, `project`, `data_source`, `dataset`, `dataset_version`, `pipeline_run`, `quality_result` and `data_asset`.

### MinIO

Open the MinIO console on `http://localhost:9001` and sign in using `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` from `.env`.

The four Alpha buckets should be visible. They should initially be empty; pipeline data is introduced only in later checklist steps.

You can also verify bucket creation from the initializer logs:

```bash
docker compose logs minio-init
```

## Persistence

Docker named volumes are used:

- `postgres_data`
- `minio_data`

Therefore `docker compose down` stops and removes containers but preserves local database/object-store data.

To deliberately reset the entire local Alpha state:

```bash
docker compose down -v
```

This deletes both volumes. The next `docker compose up -d` recreates PostgreSQL and reruns `database/schema.sql`.

## Scope boundary

This runtime intentionally does not include Airflow, Kafka, PySpark, OpenMetadata, Prometheus/Grafana, MLflow or Kubernetes. It also does not yet run ingestion or transformations.

Its responsibility is only to provide the minimum persistent services required before checklist step 8 (`Python -> Bronze`).
