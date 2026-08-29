# Sprint 1 Alpha local infrastructure

The Alpha runtime is intentionally minimal and local. It provides PostgreSQL for DataForge operational metadata and MinIO for the Bronze, Silver, Quarantine and Gold data layers.

## Services

- `postgres`: PostgreSQL 16 metadata/control-plane database.
- `minio`: S3-compatible object storage.
- `minio-init`: one-shot initializer that creates the four DataForge buckets.

## Start

Linux/macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Then replace placeholder credentials in `.env` and run:

```bash
docker compose config
docker compose up -d
```

## Verify

```bash
docker compose ps
docker compose exec postgres psql -U dataforge -d dataforge -c "\dt"
docker compose logs minio-init
```

Expected PostgreSQL tables:

- `client`
- `project`
- `data_source`
- `dataset`
- `dataset_version`
- `pipeline_run`
- `quality_result`
- `data_asset`

Expected MinIO buckets:

- `dataforge-bronze`
- `dataforge-silver`
- `dataforge-quarantine`
- `dataforge-gold`

## Persistence

Docker named volumes persist state between container restarts:

- `dataforge_postgres_data`
- `dataforge_minio_data`

`docker compose down` stops/removes containers but preserves data. Use `docker compose down -v` only when a full local reset is intended.

## Verified result

Local verification on 2026-08-29 confirmed:

- PostgreSQL running and healthy on port 5432.
- MinIO running and healthy on ports 9000 and 9001.
- all eight DataForge metadata tables initialized successfully.
- all four DataForge layer buckets created successfully.

See `docs/evidence/infrastructure-verification.md` for the recorded evidence.

## Scope boundary

This infrastructure does not yet include Airflow, Kafka, PySpark, OpenMetadata, Prometheus/Grafana or MLflow. The next implementation step is the Python source-to-Bronze ingestion path.
