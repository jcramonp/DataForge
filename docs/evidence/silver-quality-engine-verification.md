# Generic Silver and Quality Gate Engine Verification

## Scope

This evidence verifies **Issue #22: Generic Silver transformation and quality engine** for Sprint 2.

The goal of this issue is to replace client-specific scripts (`src/transformations/silver_olist.py` and `src/quality/validate_olist.py`) with generic, declarative engines driven entirely by DataForge YAML/JSON contracts.

## Delivered capabilities

1. **Declarative Silver Transformations (`src/transformations/silver_generic.py`):**
   - Implements `apply_trim`, `apply_lower`, `apply_upper`, `apply_cast`, `apply_rename`.
   - Supports nullable types: `Int64`, `Float64`, `string`, `boolean`, `datetime` (with UTC normalization).
   - `transform_dataset(bronze_df, dataset_config)` applies sequential transformation steps declaratively.
2. **Generic Quality Gate (`src/quality/quality_generic.py`):**
   - Supports all contract rule types:
     - `not_null`: Identifies missing values.
     - `unique`: Identifies duplicates while respecting `allow_null`.
     - `greater_than` / `greater_than_or_equal`: Validates lower numeric/date bounds.
     - `less_than` / `less_than_or_equal`: Validates upper numeric/date bounds.
     - `between`: Validates inclusive range boundaries.
     - `allowed_values`: Validates membership in an allowed categorical set.
     - `regex`: Validates pattern compliance.
   - Integrates Great Expectations expectations with deterministic pandas boolean masks.
3. **Quarantine vs Validated Silver Routing:**
   - **Critical severity:** Rows failing any critical rule are partitioned into Quarantine (`quarantine_df`).
   - **Warning severity:** Rules are evaluated and recorded for auditability and observability, but matching rows remain in Validated Silver (`validated_df`).
4. **End-to-End Pipeline Execution (`src/transformations/silver_runner.py`):**
   - Downloads Bronze assets from MinIO/S3.
   - Transforms data to Silver and evaluates Quality rules.
   - Persists Validated Silver to `s3://dataforge-silver/...`.
   - Persists Quarantine (if failures exist) to `s3://dataforge-quarantine/...`.
   - Tracks `pipeline_run`, records individual `quality_result` rows, and registers `data_asset` records in PostgreSQL.

## Automated Test Verification

All 78 tests across the DataForge repository passed:

```text
============================= test session starts =============================
platform win32 -- Python 3.13.3, pytest-8.0.2, pluggy-1.6.0
rootdir: C:\Users\gabri\Desktop\universidad\pry_datos\dataforge\DataForge
collected 78 items

tests\contracts\test_loader.py ....                                      [  5%]
tests\contracts\test_models.py ......                                    [ 12%]
tests\test_bronze_ingestion.py .....                                     [ 19%]
tests\test_generic_bronze.py .....                                       [ 25%]
tests\test_generic_connectors.py ................                        [ 46%]
tests\test_generic_profiling.py ............                             [ 61%]
tests\test_generic_silver_quality.py .............                       [ 78%]
tests\test_gold_transformation.py ....                                   [ 83%]
tests\test_profile_olist.py ..                                           [ 85%]
tests\test_quality_gate.py ......                                        [ 93%]
tests\test_silver_transformation.py .....                                [100%]

============================= 78 passed in 14.25s =============================
```

## Regression & Compatibility

- Historical Sprint 1 Olist transformation and quality gate tests continue to pass without modifications.
- Seamlessly integrates with contracts (#19), generic Bronze ingestion (#20), and profiling (#21).
