# Great Expectations + Quarantine verification

## Scope

This evidence verifies Sprint 1 Alpha step 10: quality validation of baseline Silver assets using Great Expectations, with critical failures routed to Quarantine and accepted rows written as validated Silver assets.

## Test verification

The local automated test suite completed successfully after the quality-rule correction:

```text
Ran 18 tests in 0.188s
OK
```

The suite includes ingestion, profiling, Silver transformation, and quality-gate tests. Quality-specific tests verify invalid masks, warning-only rules, and that zero product weight is treated as a critical failure.

## Runtime verification

The quality gate was executed with:

```text
py src\quality\validate_olist.py
```

Final verified runtime results:

| Table | Input rows | Accepted rows | Quarantined rows |
|---|---:|---:|---:|
| customers | 99,441 | 99,441 | 0 |
| orders | 99,441 | 99,441 | 0 |
| order_items | 112,650 | 112,650 | 0 |
| products | 32,951 | 32,947 | 4 |

The four quarantined `products` rows correspond to the critical rule `product_weight_positive_when_present`.

## Pipeline-run metadata

The final quality-gate executions were recorded in PostgreSQL as `silver_quality_gate` runs. The verified result for `products` was:

```text
input_rows     = 32951
accepted_rows  = 32947
rejected_rows  = 4
```

The validated outputs were registered as Silver data assets, and the rejected `products` rows were registered as a Quarantine data asset.

Validated Silver paths follow this pattern:

```text
s3://dataforge-silver/olist/<table>/source_checksum=<checksum>/validated_v1/<table>.parquet
```

The products Quarantine asset was written to:

```text
s3://dataforge-quarantine/olist/products/source_checksum=3e6569628a17/quality_v1/products.parquet
```

with `row_count = 4`.

## Quality-rule metadata

The final quality-rule results were persisted in PostgreSQL table `quality_result`.

Key verified rules include:

```text
product_weight_positive_when_present
rule_type           = validity
status              = fail
failed_rows         = 4
failure_percentage  = 0.0121
severity            = critical
gx_success          = false
```

This rule is strict: any present product weight below 1 gram fails the expectation and the corresponding row is routed to Quarantine.

A separate warning-level rule records missing product categories:

```text
product_category_present
rule_type           = completeness
status              = pass
failed_rows         = 610
failure_percentage  = 1.8512
severity            = warning
gx_success          = true
```

This expectation intentionally uses a 98% tolerance. Missing product categories therefore remain visible as a data-quality warning but do not cause row rejection.

## Design decision validated

The Alpha quality gate distinguishes between:

- **Critical rules**: row-level violations contribute to the Quarantine mask.
- **Warning rules**: issues are recorded in metadata but rows remain in validated Silver when the configured expectation threshold passes.

The gate therefore preserves valid data while isolating records that violate critical quality constraints, with rule-level traceability in PostgreSQL and physical separation in MinIO.

## Result

Step 10 is technically verified for the Alpha scope:

```text
baseline Silver
      |
      v
Great Expectations + row-level quality masks
      |----------------------|
      v                      v
validated Silver        Quarantine
      |                      |
accepted rows          critical failures
```

The validated Silver assets are now the intended inputs for the next Alpha step: Silver-to-Gold integration.
