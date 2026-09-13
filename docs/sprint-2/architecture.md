# Sprint 2 Target Architecture

## Architectural principle

Sprint 2 keeps the responsibilities introduced in Sprint 1 but generalizes them so the platform can support multiple clients, schemas and source types.

The architecture is split into four concerns:

1. **User experience:** browser-based onboarding, configuration and monitoring.
2. **Control plane:** metadata, configuration, runs, quality, lineage and certification.
3. **Data plane:** Bronze, Silver, Quarantine and Gold assets.
4. **Execution plane:** connectors, transformations, quality engine and orchestration.

## Logical architecture

```text
                                USER
                                  |
                                  v
                           React Web UI
                                  |
                                  v
                         FastAPI Control Plane
                           /               \
                          /                 \
                         v                   v
                PostgreSQL Metadata     LLM Copilot
                         |                   |
                         |<-- validated -----|
                         |    suggestions
                         v
                    Airflow Orchestration
                         |
                         v
                  Generic Connector Layer
             /--------------|--------------\
            v               v               v
     Files Connector   PostgreSQL      REST Connector
     CSV/JSON/Parquet    Connector         JSON
            \               |               /
             \--------------|--------------/
                            v
                          Bronze
                            |
                            v
                 Schema Discovery + Profiling
                            |
                            v
                    Generic Silver Engine
                            |
                            v
                    Generic Quality Engine
                    /                    \
                   v                      v
          Validated Silver            Quarantine
                   |
                   v
               Gold Engine
                   |
                   v
          Certification / Serving
```

## Component responsibilities

### Web UI

The UI is the primary user-facing interface. It must allow users to:

- create/manage projects;
- register and test sources;
- inspect discovered schema and profiling;
- review/edit quality rules and LLM suggestions;
- trigger and monitor pipelines;
- inspect quality results, Quarantine and assets;
- inspect lineage and certification status.

The frontend must communicate through FastAPI and must not query PostgreSQL directly.

### FastAPI control plane

FastAPI exposes the platform capabilities through a stable API. It owns request validation and service orchestration for:

- clients/projects/sources/datasets;
- profiling metadata;
- configuration;
- pipeline triggers and run status;
- quality results;
- data assets;
- lineage;
- certification;
- LLM-assisted configuration.

### PostgreSQL control plane

PostgreSQL remains the authoritative store for operational metadata. Sprint 2 extends the Sprint 1 model rather than replacing it.

Core metadata areas:

- client and project identity;
- source and dataset registration;
- dataset versions;
- pipeline runs;
- quality results;
- data assets;
- profiling results/configuration;
- asset lineage;
- certification state.

### Generic connector layer

Connectors translate heterogeneous technical sources into a common DataForge ingestion contract.

Initial connector families:

- Files: CSV, JSON and Parquet.
- PostgreSQL.
- REST JSON.

Source-specific authentication/connection details belong to connector configuration, not dataset-specific processing code.

### Bronze

Bronze preserves an immutable or minimally modified representation of the source and records version/checksum metadata when applicable.

### Schema discovery and profiling

Discovery inspects unknown datasets and emits structured technical metadata. It does not make domain-specific business decisions by itself.

### Silver engine

Silver standardizes supported data types and applies declared transformations without embedding client-specific branching in the engine.

### Quality engine

Quality rules are declarative and mapped to supported deterministic validation logic. Great Expectations may evaluate formal expectations while row-level masks identify records that must be routed to Quarantine.

Severity semantics:

- **warning:** record remains usable but the issue is traceable;
- **critical:** record is excluded from validated output and routed to Quarantine.

### Gold engine

Gold is driven by a validated transformation plan rather than arbitrary generated code. Supported operations initially include selection, rename, filters, derived fields, joins, grouping and common aggregations.

### LLM copilot

The LLM is a semantic assistant, not an execution engine.

It can:

- interpret user requirements;
- use schema/profiling context;
- suggest rules and transformations;
- suggest a supported Gold transformation plan.

It cannot:

- execute free-form code;
- bypass schema validation;
- write directly to production metadata without review;
- decide unsupported operations.

### Airflow

Airflow orchestrates reusable stages and manages dependencies, retries and run state. Business/data logic stays in reusable Python/services outside the DAG definition.

## Local development vs AWS reference deployment

```text
LOCAL DEVELOPMENT                  AWS REFERENCE DEPLOYMENT
-----------------                  ------------------------
MinIO                              Amazon S3
PostgreSQL container               Amazon RDS PostgreSQL
FastAPI container                  Containerized AWS compute
Airflow containers                 Cloud-accessible Airflow
React/Vite dev server              S3 + CloudFront or equivalent
Docker Compose                     Cloud deployment configuration
```

The same application code should run in both environments. Environment-specific configuration selects the infrastructure endpoints and credentials.

## Why keep Docker Compose locally?

Docker Compose is the reproducible development laboratory for the team. It allows each contributor to run and test the platform without deploying every code change to AWS. AWS is the reference operating environment for the final product/demo, not the only development environment.

## Architecture success criterion

A second non-Olist source must complete through the same contracts, connectors, engines, control plane and UI without requiring a parallel client-specific DataForge implementation.
