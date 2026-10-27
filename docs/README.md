# Project documentation

This directory contains Sprint documentation and engineering evidence, including:

- architecture;
- data discovery and profiling;
- data model;
- governance decisions;
- quality rules;
- technical decisions;
- Sprint evidence.

## Sprint 2 planning

The Sprint 2 target is to generalize the Olist Alpha into an almost-final, self-service, metadata-driven DataForge platform with heterogeneous-source support, generic profiling/transformation/quality, governance, LLM-assisted configuration, a web UI and an AWS reference deployment.

Start here:

- `sprint-2/README.md`: master Sprint 2 plan, Definition of Done and scope boundary.
- `sprint-2/scope.md`: detailed in-scope/out-of-scope capabilities and acceptance criteria.
- `sprint-2/architecture.md`: target architecture, local/AWS mapping and component responsibilities.
- `sprint-2/backlog.md`: feature issues, execution order and dependency graph.
- `sprint-2/work-management.md`: branches, issues, pull requests, Project Board and Definition of Done workflow.
- `sprint-2/supported-sources.md`: source connector boundaries and heterogeneous-schema strategy.
- `sprint-2/configuration-contract.md`: metadata/configuration contract design.
- `sprint-2/llm-copilot.md`: role, inputs, outputs and guardrails for the LLM assistant.
- `sprint-2/aws-deployment.md`: AWS reference deployment strategy.
- `sprint-2/demo-runbook.md`: living final validation/demo checklist.

Operations (#32):

- `operations/README.md`: CI pipeline, required checks and delivery flow.
- `operations/configuration.md`, `operations/migrations.md`, `operations/observability.md`, `operations/runbook.md`.
- `operations/orchestration.md`: generic Airflow DAG `dataforge_pipeline` (#24).

GitHub tracking:

- Parent/Epic: issue `#30` — Sprint 2: Final platform generalization and cloud delivery.
- Feature issues: `#19` through `#29`, plus `#31` and `#32`.

## Current Sprint 1 documents

- `architecture/alpha-architecture.md`: frozen Sprint 1 Alpha architecture and target-architecture boundary.
- `data-model/alpha-data-model.md`: Olist source/domain model and DataForge operational metadata model.
- `profiling/olist_alpha_profile.md`: observed profiling results for the Olist pilot.
- `sprint-1/pilot-olist.md`: pilot selection and scope contract.
- `evidence/infrastructure-verification.md`: local verification of Docker Compose, PostgreSQL and MinIO for checklist steps 6 and 7.
