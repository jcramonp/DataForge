# Sprint 1 Alpha Evidence Summary

## 1. Pilot dataset and profiling

Pilot dataset: Brazilian E-Commerce Public Dataset by Olist.

Alpha tables:
- customers: 99,441 rows
- orders: 99,441 rows
- order_items: 112,650 rows
- products: 32,951 rows

Total source rows analyzed: 344,483.

Key profiling findings:
- no exact duplicate rows in the selected Alpha tables;
- referential integrity between selected tables is consistent;
- 610 products have missing `product_category_name`;
- 4 products have `product_weight_g = 0`;
- 775 orders do not have order items, mainly associated with canceled or unavailable statuses;
- missing delivery timestamps are status-dependent and are not treated as generic quality errors.

Detailed evidence:
`docs/profiling/olist_alpha_profile.md`

---

## 2. Alpha infrastructure

The Alpha runtime is reproducible with Docker Compose.

Implemented services:
- PostgreSQL for operational metadata and control-plane records;
- MinIO for Bronze, Silver, Quarantine and Gold storage;
- Airflow for orchestration;
- Python processing environment.

MinIO buckets:
- `dataforge-bronze`
- `dataforge-silver`
- `dataforge-quarantine`
- `dataforge-gold`

PostgreSQL operational model includes:
- client
- project
- data_source
- dataset
- dataset_version
- pipeline_run
- quality_result
- data_asset

Detailed evidence:
`docs/evidence/infrastructure-verification.md`

---

## 3. Source to Bronze ingestion

The ingestion process:
- reads the Olist source CSV files;
- validates required files and columns;
- calculates SHA-256 source checksums;
- registers dataset versions and pipeline runs;
- converts the source data to Parquet;
- uploads the resulting assets to the Bronze MinIO bucket;
- preserves source values without applying business transformations.

Successful Bronze ingestion:
- customers: 99,441 rows
- orders: 99,441 rows
- order_items: 112,650 rows
- products: 32,951 rows

Detailed evidence:
`docs/evidence/bronze-ingestion-verification.md`

---

## 4. Bronze to Silver standardization

Silver performs baseline standardization without removing rows.

Examples:
- ID normalization;
- timestamp parsing;
- numeric type normalization;
- state and status normalization;
- correction of source column-name spelling inconsistencies;
- preservation of null values for subsequent quality evaluation.

All source rows are preserved during this stage.

Detailed evidence:
`docs/evidence/silver-transformation-verification.md`

---

## 5. Data quality and Quarantine

Great Expectations is used as the Alpha quality engine.

The quality gate:
- evaluates critical and warning-level rules;
- sends accepted rows to validated Silver;
- sends records failing critical rules to Quarantine;
- records every rule evaluation in PostgreSQL.

Latest verified product result:
- input: 32,951 rows
- validated Silver: 32,947 rows
- Quarantine: 4 rows

The 4 quarantined records fail the rule requiring positive product weight when the value is present.

The 610 missing product categories are treated as a warning and do not trigger Quarantine.

Detailed evidence:
`docs/evidence/quality-gate-verification.md`

---

## 6. Silver to Gold integration

The Gold dataset is produced at order-item grain.

Inputs:
- validated customers
- validated orders
- validated order_items
- validated products

Gold fields include:
- order_id
- order_item_id
- customer_id
- customer_state
- order_status
- order_purchase_timestamp
- product_id
- product_category_name
- price
- freight_value
- item_total

Verified result:
- input order_items: 112,650
- Gold rows: 112,642
- excluded rows: 8

The Gold transformation uses inner joins so order items associated with quarantined related entities do not enter the curated dataset.

Detailed evidence:
`docs/evidence/gold-transformation-verification.md`

---

## 7. Airflow orchestration

The complete Alpha pipeline is orchestrated through the Airflow DAG:

`olist_alpha_pipeline`

Flow:

Source
→ Bronze
→ Silver
→ Quality Gate
→ Validated Silver / Quarantine
→ Gold

A complete end-to-end DAG execution finished successfully.

The execution generated 13 operational DataForge pipeline runs:
- 4 Source → Bronze
- 4 Bronze → Silver
- 4 Silver quality gates
- 1 Silver → Gold

Airflow provides task ordering and retry behavior while the processing logic remains in reusable Python components.

Detailed evidence:
`docs/evidence/airflow-orchestration-verification.md`

---

## 8. Metadata, governance and lineage

PostgreSQL acts as the Alpha metadata control plane.

Metadata includes:
- client
- project
- source
- datasets
- dataset versions
- pipeline executions
- quality results
- physical data assets

Traceability is supported using:
- source checksums;
- schema hashes where available;
- dataset versions;
- pipeline run identifiers;
- registered storage URIs.

Governance views:
- `dataset_lineage_summary`
- `data_quality_summary`

The current Alpha lineage model provides traceability through dataset versions, runs and checksums.

Explicit multi-parent asset lineage is considered a target-architecture improvement.

Detailed evidence:
`docs/evidence/metadata-governance-verification.md`

---

## 9. Performance and partitioning

A Gold Parquet benchmark compared:
1. full unpartitioned Parquet reads;
2. filtered reads on the unpartitioned Gold file;
3. filtered reads on a temporary dataset partitioned by `customer_state`.

Benchmark predicate:
`customer_state = SP`

Matching rows:
47,448

Two executions produced the following filtered-read improvement:

- execution 1: 6.158x
- execution 2: 5.185x

Storage:
- unpartitioned: 9.658 MB
- partitioned: 11.576 MB

This represents an approximate 20% storage increase in exchange for a substantial improvement for this partition-aligned query.

The partitioned copy was temporary and the official Gold asset was not modified.

PostgreSQL `EXPLAIN ANALYZE` also confirmed usage of existing indexes in the metadata control plane.

Representative execution time:
3.752 ms.

Detailed evidence:
`docs/evidence/performance-partitioning-verification.md`

---

## 10. Alpha technical result

Sprint 1 demonstrates a complete vertical DataForge pipeline:

Olist source
→ ingestion
→ Bronze
→ Silver
→ automated quality validation
→ Quarantine
→ Gold
→ metadata and lineage
→ orchestration
→ performance evaluation

The Alpha validates the main architectural components with one real pilot dataset.

The next project stage is to evolve these Olist-specific components into configurable and reusable platform components so that new clients and sources can be onboarded with progressively less custom code.