# DataForge

DataForge is an automated and scalable data engineering platform designed to transform heterogeneous data sources into governed, validated, and analytics-ready datasets.

## Project context

DataForge is being developed as a data engineering solution for **AI Solutions LATAM**, a simulated consulting company that delivers data engineering, advanced analytics, and machine learning projects for multiple clients.

The platform addresses a recurring operational problem: each new client may provide data through different technologies and formats, forcing teams to repeatedly build custom ingestion, cleaning, validation, and transformation processes. DataForge aims to standardize and automate that lifecycle so new projects can be onboarded with greater reuse, traceability, quality, and scalability.

## Core data flow

`Source -> Ingestion -> Bronze -> Validation -> Silver -> Gold -> Certified Dataset -> Consumption`

Data that does not satisfy the defined quality rules is redirected to a quarantine area for analysis and possible reprocessing.

## Sprint 1 — Alpha Product

The current objective is to build the first end-to-end functional slice of DataForge. The Alpha Product should demonstrate:

- discovery and profiling of a pilot data source;
- automated ingestion into the raw/Bronze layer;
- validation and data-quality checks;
- separation of invalid records into quarantine;
- transformation into Silver and Gold datasets;
- initial metadata, governance, and traceability decisions;
- documented architecture and data model;
- evidence of the implemented flow.

## Initial technology stack

The Alpha Product will prioritize a minimal, demonstrable stack:

- Python
- PostgreSQL
- MinIO
- Apache Parquet
- pandas
- Great Expectations
- Docker / Docker Compose
- Apache Airflow (for pipeline orchestration as the Alpha flow stabilizes)

Additional technologies such as PySpark, Kafka, OpenMetadata, Prometheus, Grafana, and MLflow are part of the target architecture and will be incorporated progressively when justified by the project scope.

## Engineering principles

DataForge is designed around:

- automation;
- scalability;
- modularity;
- data quality;
- governance and traceability;
- resilience and idempotency;
- reproducibility;
- DataOps practices.

## Course

SI4002 — Proyecto de Ingeniería de Datos  
Universidad EAFIT
