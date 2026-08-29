# Silver transformation verification

Sprint 1 checklist step 9 (`Bronze -> Silver`) was verified locally against the running DataForge Alpha infrastructure.

## Unit tests

Command:

```powershell
py -m unittest discover -s tests -p "test_*.py" -v
```

Result: **12 tests passed**.

Coverage includes the existing Bronze/profiling tests plus Silver tests for:

- S3 URI parsing;
- customer text normalization with row preservation;
- order timestamp parsing while preserving missing values;
- order-item numeric typing;
- product column-name correction (`lenght` -> `length`) while preserving nulls.

## Runtime execution

Command:

```powershell
py src\transformations\silver_olist.py
```

Observed result:

| Table | Rows | Silver asset | Run |
| --- | ---: | --- | ---: |
| customers | 99,441 | `s3://dataforge-silver/olist/customers/source_checksum=983a422239e1/silver_v1/customers.parquet` | 6 |
| orders | 99,441 | `s3://dataforge-silver/olist/orders/source_checksum=8df58ef3d2d7/silver_v1/orders.parquet` | 7 |
| order_items | 112,650 | `s3://dataforge-silver/olist/order_items/source_checksum=0bc4d068c4fe/silver_v1/order_items.parquet` | 8 |
| products | 32,951 | `s3://dataforge-silver/olist/products/source_checksum=3e6569628a17/silver_v1/products.parquet` | 9 |

All Silver row counts exactly match their Bronze inputs.

## PostgreSQL control-plane verification

`pipeline_run` records show runs 6-9 as:

- `run_type = bronze_to_silver`;
- `status = success`;
- `accepted_rows = input_rows`;
- `rejected_rows = 0`.

The successful counts are:

- customers: 99,441 input / 99,441 accepted;
- orders: 99,441 input / 99,441 accepted;
- order_items: 112,650 input / 112,650 accepted;
- products: 32,951 input / 32,951 accepted.

`data_asset` contains four additional assets with `layer = silver`, `format = parquet`, and matching row counts.

## Scope interpretation

This step performs deterministic structural standardization only. It intentionally preserves all rows, including nulls and potential anomalies. Formal quality-rule evaluation and routing of invalid records to Quarantine are deferred to checklist step 10 (Great Expectations + Quarantine).

## Conclusion

Checklist step 9 is **completed and verified end to end**: Bronze Parquet assets were read from MinIO, transformed deterministically, written to the Silver bucket, and registered successfully in PostgreSQL with preserved row counts and traceable run metadata.
