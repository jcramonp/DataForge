# Gold transformation runtime verification

## Scope

This evidence verifies Sprint 1 Alpha step 11: transformation from the latest validated Silver Olist assets to the first integrated Gold dataset.

## Test verification

The local test suite completed successfully after adding Gold coverage:

```text
Ran 22 tests in 0.148s
OK
```

Gold-specific tests verify:

- the output keeps order-item grain;
- the Alpha Gold column contract is respected;
- order-items whose product is absent from validated Silver are excluded;
- S3 URI parsing works as expected.

## Runtime execution

Command:

```powershell
py src\transformations\gold_olist.py
```

Observed result:

```text
Gold transformation completed
- order_items_gold: 112650 input order-items, 112642 Gold rows, 8 excluded (run_id=18)
- s3://dataforge-gold/olist/order_items/v1/olist_order_items_gold.parquet
```

Interpretation:

- Input grain: 112,650 validated order-item candidates.
- Gold output: 112,642 order-item rows.
- 8 rows were excluded by the validated-dimension joins because their referenced product was not present in validated Silver.
- Gold therefore consumes quality-gated Silver rather than bypassing Quarantine.

## PostgreSQL pipeline metadata

Verification query:

```sql
SELECT run_id, run_type, status, input_rows, accepted_rows, rejected_rows, error_message
FROM pipeline_run
WHERE run_id = 18;
```

Observed metadata:

| run_id | run_type | status | input_rows | accepted_rows | rejected_rows |
|---:|---|---|---:|---:|---:|
| 18 | silver_to_gold | success | 112650 | 112642 | 8 |

## Gold asset metadata

Verification query:

```sql
SELECT asset_id, run_id, layer, asset_name, storage_uri, format, row_count, checksum
FROM data_asset
WHERE run_id = 18;
```

Observed asset:

| asset_id | run_id | layer | asset_name | row_count | format |
|---:|---:|---|---|---:|---|
| 19 | 18 | gold | olist_order_items_gold | 112642 | parquet |

Storage URI:

```text
s3://dataforge-gold/olist/order_items/v1/olist_order_items_gold.parquet
```

Checksum:

```text
bf9889b8359be44276206a3556d5331bc2943ea630f05c1f61352af83988dbbd
```

## Result

Step 11 is runtime-verified: DataForge resolves validated Silver inputs, integrates the Olist Alpha entities at order-item grain, excludes rows whose validated dimension record is unavailable, writes the Gold dataset as Parquet to MinIO, and registers the successful pipeline run and physical Gold asset in PostgreSQL.
