# Changelog

## Sprint 2 - 2026-10-26

### Added
- Validated, versioned YAML/JSON contracts and persisted executable revisions.
- Generic CSV/file, PostgreSQL and REST connectors; schema discovery and profiling.
- Generic Silver transformations, critical/warning quality gates and quarantine.
- Configurable Gold joins, derivations and aggregations.
- Airflow orchestration of reusable stages from persisted contracts.
- FastAPI onboarding, metadata and lifecycle API; scoped React interface.
- Asset lineage, certification transitions and audited history.
- Bedrock copilot proposals with schema validation and explicit human approval.
- PostgreSQL latest-version index and explicitly refreshed materialized run report
  (migration 0008); reproducible before/after benchmark.
- Delivery evidence index, data dictionary, catalog guide, RACI and PDF presentation.

### Fixed
- Transient monitoring errors now retry the same accepted run without retriggering.
- Exhausted monitoring reports an unknown outcome; actual terminal states are preserved.
- Copilot validation failures return a safe explanation; invalid proposals cannot be approved.
- UI metrics and assets read persisted scoped data; unavailable services are explicit.

### Delivery boundary
- Local Docker Compose deployment is implemented. AWS deployment remains a reference
  design, not a verified deployed environment.
- Final-Sprint DataOps and downstream data consumption are outside this delivery.
- See docs/delivery/sprint2-requirements.md for evidence and remaining human checks.

## Sprint 1 - historical baseline
- Olist-specific Bronze/Silver/quality/Gold scripts, PostgreSQL operational metadata,
  Parquet in MinIO and the initial quality/governance model.
- See historical evidence under docs/evidence; historical results retain their original scope.
