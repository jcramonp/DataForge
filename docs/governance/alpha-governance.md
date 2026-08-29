# DataForge Alpha — Metadata and Governance

## 1. Scope

The Sprint 1 Alpha implements lightweight metadata and governance capabilities
without introducing a dedicated external catalog such as OpenMetadata.

PostgreSQL acts as the operational metadata and traceability store, while
MinIO stores the physical data assets in Parquet format.

The Alpha governance scope covers:

- dataset ownership;
- data classification;
- source identification;
- dataset versioning;
- pipeline execution traceability;
- data asset registration;
- quality result registration;
- storage location;
- checksums;
- basic lineage.

## 2. Metadata model

DataForge maintains the following metadata hierarchy:

Client
→ Project
→ Data Source
→ Dataset
→ Dataset Version
→ Pipeline Run
→ Data Asset

Quality results are associated with the pipeline run in which the corresponding
quality rules were evaluated.

## 3. Dataset ownership

The Olist pilot datasets are owned operationally by the DataForge Sprint 1 team.

Ownership identifies the team responsible for:

- maintaining the pipeline;
- defining transformation rules;
- reviewing quality failures;
- managing dataset versions;
- documenting changes.

The Gold dataset is managed by DataForge as a derived data product.

## 4. Data classification

The Alpha datasets use the classification `internal`.

Although the source Olist dataset is publicly available and anonymized, DataForge
treats customer-related identifiers and location attributes conservatively.

Identifiers such as `customer_id` and `customer_unique_id` must not be used for
attempts to re-identify individuals.

## 5. Versioning

Source datasets are versioned using source checksums.

For each source dataset DataForge stores:

- source checksum;
- schema hash;
- version label;
- discovery timestamp.

This allows the platform to identify whether the source contents or schema have
changed between executions.

The Gold dataset uses a derived version identifier calculated from its upstream
source versions.

## 6. Data quality governance

Great Expectations and explicit validation rules are used to evaluate the
validated Silver datasets.

Quality results are persisted in PostgreSQL and include:

- rule name;
- rule type;
- status;
- failed rows;
- failure percentage;
- rule details;
- evaluation timestamp.

Critical failures may route records to Quarantine.

Warning or tolerance-based rules may report unexpected records without rejecting
them.

For example, missing product categories are monitored but do not cause records
to be quarantined, while invalid positive physical measurements can cause
rejection.

## 7. Lineage and traceability

The `dataset_lineage_summary` view provides operational lineage from:

Client
→ Project
→ Source
→ Dataset
→ Version
→ Pipeline Run
→ Data Asset

The `data_quality_summary` view provides traceability between dataset versions,
pipeline executions and quality rules.

This allows operators to determine which execution generated an asset, where it
is stored, how many rows it contains and what quality controls were applied.

## 8. Alpha limitations

The Alpha does not implement explicit asset-to-asset lineage relationships.

For example, the Gold dataset depends on multiple validated Silver datasets, but
those parent-child asset relationships are currently inferred through dataset
versions and pipeline execution metadata rather than stored in a dedicated
lineage graph.

A future architecture may introduce OpenMetadata or an equivalent catalog and
explicit multi-parent lineage relationships.

The Alpha Gold dataset also does not currently persist a schema hash. This can be
added in a future iteration to improve derived dataset version control.

## 9. Customer identifier semantics

In the Olist dataset, `customer_id` identifies the customer record associated
with an individual order.

It should not be interpreted as the persistent identity of a recurring customer.

`customer_unique_id` provides the identifier used to recognize the same customer
across different orders.

This distinction must be preserved when designing customer-level analytics or
future Gold data products.