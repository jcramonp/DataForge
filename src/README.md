# Source code

Implementation of DataForge's data engineering components. Run modules from the repository root (`python -m src.<package>.<module>`).

- `contracts/`: Pydantic contract models, YAML/JSON loader and JSON Schema export.
- `connectors/`: file, PostgreSQL and REST connectors selected by contract source type.
- `discovery/`: generic schema discovery and profiling.
- `ingestion/`: source-to-Bronze ingestion (`bronze_generic` is the contract-driven path; `bronze_olist` is the Sprint 1 Alpha).
- `transformations/`: Silver (`silver_generic`, `silver_runner`) and Gold transformations.
- `quality/`: declarative quality rules and Quarantine routing (`quality_generic`).
- `api/`: FastAPI control plane.
- `common/`: environment-specific settings, S3/PostgreSQL clients and structured logging shared by every stage.
- `ops/`: operational tooling: migrations (`migrate`), readiness checks (`health`) and run metrics (`run_summary`).
- `performance/`: Gold partitioning benchmark.
