# Bronze ingestion runtime verification

## Scope

Sprint 1 checklist step 8: execute the Olist source-to-Bronze pipeline against the local Alpha infrastructure.

## Environment

- Host: Windows
- PostgreSQL: Docker Compose service `postgres`
- MinIO: Docker Compose service `minio`
- Python ingestion executed from the host
- Source location: `data/raw/olist/`
- Bronze bucket: `dataforge-bronze`

## Unit-test evidence

The repository test suite completed successfully before runtime ingestion:

```text
Ran 7 tests
OK
```

The tests covered the Olist Alpha contract, source-file existence and required columns, source checksum generation, and existing profiling behavior.

## Runtime ingestion evidence

The first runtime attempt correctly produced a failed `source_to_bronze` run because the host-executed Python client was still configured with the Docker-internal MinIO hostname (`http://minio:9000`). The local `.env` was corrected to use `http://localhost:9000` and PostgreSQL host `localhost`.

A subsequent run completed successfully:

| Table | Input rows | Bronze storage URI | Run ID |
|---|---:|---|---:|
| customers | 99,441 | `s3://dataforge-bronze/olist/customers/source_checksum=983a422239e1/customers.parquet` | 2 |
| orders | 99,441 | `s3://dataforge-bronze/olist/orders/source_checksum=8df58ef3d2d7/orders.parquet` | 3 |
| order_items | 112,650 | `s3://dataforge-bronze/olist/order_items/source_checksum=0bc4d068c4fe/order_items.parquet` | 4 |
| products | 32,951 | `s3://dataforge-bronze/olist/products/source_checksum=3e6569628a17/products.parquet` | 5 |

## PostgreSQL verification

The `pipeline_run` table confirmed one failed attempt followed by four successful source-to-Bronze runs:

| run_id | run_type | status | input_rows | accepted_rows | rejected_rows |
|---:|---|---|---:|---:|---:|
| 1 | source_to_bronze | failed | 99,441 | null | null |
| 2 | source_to_bronze | success | 99,441 | 99,441 | 0 |
| 3 | source_to_bronze | success | 99,441 | 99,441 | 0 |
| 4 | source_to_bronze | success | 112,650 | 112,650 | 0 |
| 5 | source_to_bronze | success | 32,951 | 32,951 | 0 |

The `data_asset` table confirmed four Bronze Parquet assets, one for each contracted Olist table, with row counts matching the source counts.

## Result

Checklist step 8 is verified end to end:

1. source CSVs were found and contract-checked;
2. each source was converted to Parquet without Silver cleaning or quality rejection;
3. each Parquet object was stored in the Bronze MinIO bucket;
4. dataset versions, runs, and physical assets were registered in PostgreSQL;
5. successful runs preserved the original row counts;
6. the failed first attempt remained traceable in metadata rather than being hidden.

This evidence is suitable for the Sprint 1 technical evidence section and demonstrates traceability, failure recording, reproducibility, and separation between Bronze ingestion and later quality-processing stages.
