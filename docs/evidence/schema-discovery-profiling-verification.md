# Generic Schema Discovery and Profiling Verification

## Scope

This evidence verifies **Issue #21: Generic schema discovery and profiling** for Sprint 2.

The goal of this issue is to eliminate hardcoded Olist assumptions from the discovery layer, allowing DataForge to infer schema and compute technical profiling metrics across arbitrary datasets (CSV, Parquet, JSON, PostgreSQL, REST) driven by contracts or raw files.

## Delivered capabilities

1. **Deterministic Type Inference (`src/discovery/engine.py`):**
   - Automatically classifies Series values into standard DataForge `DataType` enums (`string`, `integer`, `float`, `boolean`, `date`, `datetime`, `json`).
   - Distinguishes native and string representations of booleans, timestamps, ISO dates, whole-number floats, and JSON strings.
   - Detects nullability.
2. **Generic Column Metrics:**
   - Null counts and percentage.
   - Cardinality (distinct count) and uniqueness ratios.
   - Type-specific statistics:
     - Numeric: `min`, `max`, `mean`, `median`, `std`, `zeros_count`, `negative_count`.
     - Text/String: `min_length`, `max_length`, `avg_length`, `empty_string_count`.
     - Temporal: `min_date`, `max_date`.
   - Sample values (JSON-serializable).
3. **Dataset-level Profiling & Candidate Keys:**
   - Total rows, columns, duplicate rows count, and duplicate row percentage.
   - Memory usage estimation.
   - Automatic candidate primary key detection (columns with 0 nulls and 100% uniqueness).
4. **Contract Schema Generation:**
   - `generate_contract_schema(df)` produces schema definitions conforming to `ColumnConfig` models in `src/contracts/models.py`.
5. **Reporting (`src/discovery/reporter.py` & `src/discovery/run_profiling.py`):**
   - Structured JSON output for API/Web UI/LLM consumption.
   - Clean, auditable Markdown report generation.
   - CLI runner for profiling via DataForge YAML/JSON contracts or ad-hoc files.

## Automated Test Verification

All 65 tests in the DataForge repository passed:

```text
============================= test session starts =============================
platform win32 -- Python 3.13.3, pytest-8.0.2, pluggy-1.6.0
rootdir: C:\Users\gabri\Desktop\universidad\pry_datos\dataforge\DataForge
collected 65 items

tests\contracts\test_loader.py ....                                      [  6%]
tests\contracts\test_models.py ......                                    [ 15%]
tests\test_bronze_ingestion.py .....                                     [ 23%]
tests\test_generic_bronze.py .....                                       [ 30%]
tests\test_generic_connectors.py ................                        [ 55%]
tests\test_generic_profiling.py ............                             [ 73%]
tests\test_gold_transformation.py ....                                   [ 80%]
tests\test_profile_olist.py ..                                           [ 83%]
tests\test_quality_gate.py ......                                        [ 92%]
tests\test_silver_transformation.py .....                                [100%]

============================= 65 passed in 8.50s ==============================
```

## Regression & Compatibility

- Historical Sprint 1 Olist profiling tests in `tests/test_profile_olist.py` continue to pass without changes.
- Inferred schemas validate against the Pydantic contracts from Issue #19 (`src/contracts/models.py`).
- Extractor integration connects seamlessly with generic connectors from Issue #20 (`src/connectors/registry.py`).
