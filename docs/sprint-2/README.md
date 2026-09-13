# DataForge Sprint 2 — Platform Generalization and Cloud Delivery

## Objective

Sprint 2 turns the Sprint 1 Olist Alpha into an almost-final DataForge platform: self-service, metadata-driven, multi-source, cloud-hosted and operable from a web interface.

Sprint 1 proved that the technical engine works end-to-end. Sprint 2 must prove that the same engine can be generalized beyond Olist without creating a new client-specific pipeline for every dataset.

## Product principle

DataForge is a data-engineering platform. Machine Learning is a downstream consumer, not the core of the platform.

The platform must separate:

- **Data plane:** physical datasets and analytical assets.
- **Control plane:** clients, projects, sources, datasets, versions, runs, quality, lineage and certification.
- **Orchestration:** execution order, dependencies, retries and run state.
- **User experience:** onboarding, configuration, monitoring and governance through API/UI.

## Sprint 2 target flow

```text
User
  |
  v
Web UI
  |
  v
FastAPI Control Plane <---- LLM Configuration Copilot
  |
  v
Metadata / validated configuration
  |
  v
Airflow
  |
  v
Generic Connector Layer
  |---- Files: CSV / JSON / Parquet
  |---- PostgreSQL
  `---- REST JSON
  |
  v
Bronze
  |
  v
Schema Discovery + Profiling
  |
  v
Generic Silver Transformation
  |
  v
Generic Quality Engine
  |---- Validated Silver
  `---- Quarantine
  |
  v
Configurable Gold Engine
  |
  v
Certification: Draft -> Validated -> Certified
```

Local development uses Docker Compose. The AWS reference deployment uses cloud-native equivalents such as S3 and RDS while preserving the same application code and logical architecture.

## GitHub execution backlog

The parent/epic issue is **#30 — Sprint 2: Final platform generalization and cloud delivery**.

Recommended execution order:

1. **#19** Generic dataset contracts and configuration model.
2. **#20** Generic source connectors.
3. **#21** Generic schema discovery and profiling.
4. **#22** Generic Silver transformation and quality engine.
5. **#31** Configurable Gold transformation and serving engine.
6. **#23** Lineage and dataset certification.
7. **#24** Metadata-driven Airflow orchestration.
8. **#25** FastAPI control plane and self-service onboarding.
9. **#26** LLM-assisted configuration copilot.
10. **#27** Web interface.
11. **#28** AWS reference deployment.
12. **#32** CI/CD, observability and deployment hardening.
13. **#29** Multi-source end-to-end validation and final evidence.

## Definition of Done

Sprint 2 is complete when all of the following are true:

- Olist runs through the generic engine and remains a regression case.
- At least one second, structurally different source runs through the same architecture.
- Supported source types and limitations are explicitly documented.
- Previously unknown datasets can be discovered and profiled without dataset-specific column names in the profiler.
- Silver transformations and quality rules are configuration/metadata driven.
- Critical violations are routed to Quarantine; warnings remain traceable without automatically blocking records.
- Gold outputs are described through a validated transformation plan rather than requiring a new client-specific production script.
- Airflow orchestrates reusable stages and can be triggered through the control plane.
- FastAPI exposes onboarding, profiling, runs, quality, assets, lineage and certification.
- The LLM proposes structured configuration; it never executes arbitrary generated code.
- A browser-based interface supports the main onboarding-to-run workflow.
- Asset lineage can be traversed from source/Bronze through Silver to Gold.
- Dataset certification states Draft, Validated and Certified are available.
- AWS hosts a reference deployment and completes at least one end-to-end run.
- Pull requests execute automated validation and regression checks.
- Failed runs are traceable through operational logs/status.
- The final demo and deployment are reproducible from documentation.

## Explicit Sprint 2 scope boundary

Sprint 2 targets:

- Batch files: CSV, JSON and Parquet.
- PostgreSQL sources.
- REST APIs returning JSON, polled/scheduled as batch ingestion.
- Generic profiling, transformation and quality configuration.
- Self-service onboarding through API/UI.
- LLM-assisted configuration with deterministic validation/execution.
- AWS reference deployment.

Not required for Sprint 2 unless the course explicitly requests them later:

- Continuous event streaming with Kafka.
- Distributed Spark clusters.
- Kubernetes.
- Full enterprise observability stack.
- Support for every possible database or file format.
- Arbitrary LLM-generated executable code.

## Core design rule

The challenge of heterogeneous data is handled by **contracts + connectors + schema discovery + configuration**, not by client-specific conditionals.

The LLM helps interpret business intent and suggests configuration, while the DataForge core remains deterministic and validates every operation before execution.

## Documentation

- [Scope and acceptance criteria](scope.md)
- [Target architecture](architecture.md)
- [Backlog and dependencies](backlog.md)
- [GitHub work management](work-management.md)
- [Team ownership plan](team-ownership.md)
- [GitHub Project and Milestone setup](project-board-setup.md)
- [Supported sources and boundaries](supported-sources.md)
- [Configuration contract design](configuration-contract.md)
- [LLM copilot design](llm-copilot.md)
- [AWS deployment strategy](aws-deployment.md)
- [Final demo and validation runbook](demo-runbook.md)
