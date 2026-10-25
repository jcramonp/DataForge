# Configurable Gold Engine Verification

## Scope

This evidence verifies **Issue #31: Configurable Gold Engine** for Sprint 2.

The goal of this issue is to replace client-specific scripts (`src/transformations/gold_olist.py`) with a generic, declarative Gold analytical transformation engine driven entirely by DataForge YAML/JSON contracts.

## Delivered capabilities

1. **Declarative Gold Transformation Engine (`src/transformations/gold_generic.py`):**
   - Supports all contract-defined operations (`GoldOperation`):
     - `SELECT`: Column projection and ordered selection (`execute_select`).
     - `DROP`: Explicit removal of obsolete or unneeded columns (`execute_drop`).
     - `RENAME`: Column aliasing and renaming (`execute_rename`).
     - `FILTER`: Row filtering with all operators: `eq`, `ne`, `gt`, `ge`, `lt`, `le`, `in`, `not_in` (`execute_filter`).
     - `JOIN`: Multi-dataset joins with `inner`, `left`, `right`, and `full` semantics, automatically resolving overlapping column names and preserving parent columns (`execute_join`).
     - `DERIVE`: Arithmetic operations (`add`, `subtract`, `multiply`, `divide` with zero-division protection) across operand columns (`execute_derive`).
     - `GROUP_BY` and `AGGREGATE`: Dimensional grouping and aggregations supporting `sum`, `avg` / `mean`, `min`, `max`, `count`, and `nunique` (`execute_aggregate`).
   - `build_gold_dataset_from_plan(gold_config, datasets_by_code)` executes the multi-step declarative plan on input datasets.

2. **Generic Gold Pipeline Runner (`src/transformations/gold_runner.py`):**
   - Automatically determines base and join dependency datasets from the contract.
   - Queries PostgreSQL metadata to resolve the latest successful validated Silver Parquet assets (`latest_validated_silver_asset`).
   - Downloads required validated Silver Parquets from MinIO/S3 into a local working directory.
   - Executes `build_gold_dataset_from_plan` to assemble the Gold analytical model.
   - Persists the curated Gold dataset to `s3://dataforge-gold/{client}/{project}/{gold_code}/gold_v1/{gold_code}.parquet`.
   - Records lineage in the PostgreSQL control plane:
     - Upserts `dataset` and `dataset_version` with combined source checksum.
     - Logs `pipeline_run` with `run_type = 'silver_to_gold'`, `status = 'success'`, `accepted_rows`, and `rejected_rows`.
     - Registers `data_asset` with `layer = 'gold'` and SHA-256 checksum.
   - Provides CLI interface with `--contract` and `--gold-code` options.

3. **Package Integration & Exports (`src/transformations/__init__.py`):**
   - Cleanly exports the new generic functions: `build_gold_dataset_from_plan`, `execute_gold_step`, `run_gold_pipeline`, etc.

## Automated Test Verification

All 104 tests across the DataForge test suite passed:

```text
============================= test session starts =============================
platform win32 -- Python 3.13.3, pytest-8.0.2, pluggy-1.6.0
rootdir: C:\Users\gabri\Desktop\universidad\pry_datos\dataforge\DataForge
plugins: anyio-4.9.0
collected 104 items

tests\contracts\test_loader.py ....                                      [  3%]
tests\contracts\test_models.py ......                                    [  9%]
tests\test_api_control_plane.py ............                             [ 21%]
tests\test_bronze_ingestion.py .....                                     [ 25%]
tests\test_generic_bronze.py .....                                       [ 30%]
tests\test_generic_connectors.py ................                        [ 46%]
tests\test_generic_gold.py ..............                                [ 59%]
tests\test_generic_profiling.py ............                             [ 71%]
tests\test_generic_silver_quality.py ..............                       [ 83%]
tests\test_gold_transformation.py ....                                   [ 87%]
tests\test_profile_olist.py ..                                           [ 89%]
tests\test_quality_gate.py ......                                        [ 95%]
tests\test_silver_transformation.py .....                                [100%]

============================= 104 passed in 5.58s =============================
```

## Regression & Compatibility

- Declarative contract plan from `config/examples/olist.yaml` identically reproduces Sprint 1's `gold_olist.py` output (11 analytical columns, inner-join filtering, `item_total` derivation).
- Sprint 1 legacy tests (`tests/test_gold_transformation.py`) continue to pass unmodified.
