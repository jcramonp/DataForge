# Web Interface and FastAPI Control Plane Verification

## Scope

This evidence verifies **Issue #27: Web interface** for Sprint 2.

The goal of this issue is to deliver a user-facing web interface for the main DataForge lifecycle, allowing the platform to be fully operated without direct database queries or manual script execution, while communicating strictly through FastAPI.

## Delivered capabilities

1. **Studio-Grade Art Direction (`taste-skill`):**
   - Configured with `Leonxlnx/taste-skill` (`--kind devtools`).
   - Clean, neutral, anti-slop design system using Geist and Geist Mono typography with tabular figures.
   - Strict color semantics:
     - Positive/Green (`#166534`): Validated Silver, Certified, Passed.
     - Warning/Amber (`#92400e`): Warnings, Draft.
     - Negative/Red (`#991b1b`): Failed runs, Critical issues, Quarantined records.
     - Accent/Blue (`#1d5fbf`): Interactive actions and connectivity status.
2. **FastAPI Control Plane (`src/api/main.py`):**
   - Full RESTful surface exposing:
     - `/api/overview`: Global KPIs, platform health, recent pipeline runs.
     - `/api/sources`: Active sources and connector metadata.
     - `/api/sources/test-connection`: Live connector latency and reachability verification.
     - `/api/datasets`: Schema, DataForge types, primary keys, nullability, classification.
     - `/api/datasets/{dataset}/profiling`: Technical discovery facts from Issue #21.
     - `/api/datasets/{dataset}/quarantine`: Isolated critical failures and reason breakdown.
     - `/api/pipelines/trigger`: Pipeline execution dispatcher.
     - `/api/assets`: Multi-layer data asset explorer (`bronze`, `silver`, `quarantine`, `gold`).
     - `/api/lineage`: DAG graph topology from Source to Gold.
     - `/api/certification`: Governance transition from Draft to Validated to Certified.
     - `/api/copilot/suggest`: Semantic rule suggestion engine without arbitrary code execution.
3. **React + Vite Frontend (`frontend/`):**
   - **Overview / Dashboard:** High-level platform health, KPI strips, recent runs table.
   - **Source Onboarding & Connection Test:** Interactive form supporting File, PostgreSQL, and REST with live connection testing.
   - **Datasets & Schema Profiling:** Schema tables with DataForge types, nullability, and detailed profiling facts modal.
   - **Quality Gate & Quarantine Inspector:** Visibility into critical vs warning rules, and inspector table showing exact quarantined records and observed values.
   - **Pipeline Execution Observability:** Trigger runs across layers and monitor accepted vs quarantined counts.
   - **Data Assets:** Multi-layer Parquet inventory with S3 URIs and SHA-256 checksums.
   - **Lineage & Governance:** Interactive DAG visualization and dataset certification workflows.
   - **LLM Configuration Copilot:** Natural language rule authoring mapped to `QualityRuleConfig`.

## Automated Verification

### 1. Python Automated Test Suite (90 passed)

```text
============================= test session starts =============================
platform win32 -- Python 3.13.3, pytest-8.0.2, pluggy-1.6.0
rootdir: C:\Users\gabri\Desktop\universidad\pry_datos\dataforge\DataForge
collected 90 items

tests\contracts\test_loader.py ....                                      [  4%]
tests\contracts\test_models.py ......                                    [ 11%]
tests\test_api_control_plane.py ............                             [ 24%]
tests\test_bronze_ingestion.py .....                                     [ 30%]
tests\test_generic_bronze.py .....                                       [ 35%]
tests\test_generic_connectors.py ................                        [ 53%]
tests\test_generic_profiling.py ............                             [ 66%]
tests\test_generic_silver_quality.py .............                       [ 81%]
tests\test_gold_transformation.py ....                                   [ 85%]
tests\test_profile_olist.py ..                                           [ 87%]
tests\test_quality_gate.py ......                                        [ 94%]
tests\test_silver_transformation.py .....                                [100%]

============================= 90 passed in 14.83s =============================
```

### 2. Frontend Production Build

```text
> dataforge-web@2.0.0 build
> vite build

vite v6.4.5 building for production...
transforming...
✓ 1955 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.74 kB │ gzip:  0.42 kB
dist/assets/index-DX6xrfyY.css    5.65 kB │ gzip:  1.64 kB
dist/assets/index-BQ67fpNK.js   218.55 kB │ gzip: 62.53 kB
✓ built in 2.48s
```

## Acceptance Criteria Summary

- [x] A user can complete the main onboarding-to-run workflow from the browser.
- [x] The frontend communicates only through the API, not directly with PostgreSQL.
- [x] The interface clearly displays failed runs and quality warnings/critical issues.
- [x] Olist and a second source can be inspected through the same UI.
