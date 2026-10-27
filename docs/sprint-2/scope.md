# Sprint 2 Scope

## Product goal

Convert DataForge from an Olist-specific Alpha into an almost-final, reusable data-engineering platform capable of onboarding heterogeneous datasets through configuration and supported connectors.

## What Sprint 2 must prove

The central proof is not that another pipeline can be built. It is that **the same DataForge engine can process different sources and schemas without creating a new client-specific architecture**.

## In scope

### Generic source onboarding

- CSV files.
- JSON files.
- Parquet files.
- PostgreSQL tables/queries.
- REST APIs returning JSON.
- Connection testing and traceable source failures.

### Data discovery

- Schema inference.
- Row and column counts.
- Missing-value metrics.
- Duplicate metrics.
- Candidate key checks when configured.
- Numeric and string summaries where applicable.
- Persisted profiling metadata.

### Configurable data processing

- Bronze ingestion and source versioning.
- Silver type normalization and supported transformations.
- Declarative quality rules.
- Warning and critical severity.
- Validated Silver and Quarantine routing.
- Configurable Gold transformation plans.

### Governance

- Dataset/source/version metadata.
- Pipeline run metadata.
- Quality results.
- Data assets.
- Explicit asset-to-asset lineage.
- Certification states: Draft, Validated, Certified.

### User-facing platform

- FastAPI control plane.
- React/Vite web interface.
- Source onboarding.
- Profiling inspection.
- Quality configuration.
- Pipeline execution/status.
- Quality/Quarantine views.
- Lineage and certification views.

### LLM-assisted configuration

- Natural-language business requirements.
- Profiling-aware rule suggestions.
- Structured transformation/quality proposals.
- Schema validation of every proposal.
- Explicit user review before persistence/execution.

### Cloud reference deployment

- AWS as the primary Sprint 2 deployment target.
- S3 for the cloud data plane.
- RDS PostgreSQL for the control plane.
- Containerized API/orchestration services on AWS compute.
- Cloud-hosted web interface.
- End-to-end cloud execution evidence.

## Out of scope for Sprint 2

Unless explicitly required later by the course:

- True continuous Kafka streaming.
- Arbitrary source systems beyond the declared connector set.
- Arbitrary Python/code generation from the LLM.
- Distributed Spark cluster operations.
- Kubernetes production orchestration.
- Full enterprise data catalog/observability products.
- Production-scale multi-region high availability.

## Acceptance criteria

A Sprint 2 release is acceptable only if:

1. Olist completes through the generic architecture.
2. A second structurally different source completes through the same architecture.
3. No new client-specific DAG is required for that second source.
4. No new hardcoded quality-rule dictionary is required for that second source.
5. Generic profiling does not rely on Olist column names.
6. Gold can be created through a validated transformation plan.
7. Warnings and critical violations are traceable separately.
8. Quarantine contains only records rejected by configured critical rules.
9. The user can operate the main workflow through API/UI instead of direct SQL/manual script execution.
10. The LLM only proposes supported structured configuration.
11. Lineage and certification are queryable.
12. At least one end-to-end execution completes on AWS.
13. Sprint 1 behavior remains covered by regression tests.
14. Deployment and demo procedures are reproducible.
