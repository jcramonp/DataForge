# Sprint 2 Demo and Validation Runbook

## Purpose

This file is the living checklist for the near-final DataForge demonstration. It will be completed as Sprint 2 capabilities are implemented.

The final demo must prove that DataForge is a reusable platform rather than an Olist-specific pipeline.

## Demo prerequisites

Before the final demo:

- [ ] `develop` is stable and all required Sprint 2 issues are merged.
- [ ] Automated tests/CI are passing.
- [ ] AWS reference environment is available.
- [ ] Web UI and FastAPI are reachable.
- [ ] Airflow is operational.
- [ ] S3/RDS connectivity is healthy.
- [ ] LLM provider configuration is available if the copilot is demonstrated.
- [ ] Olist regression case is ready.
- [ ] Second non-Olist source is ready.
- [ ] No credentials/secrets are visible in screenshots or terminal history.

## Required demonstration path

### 1. Platform entry

Show the DataForge web interface and explain:

- project/client context;
- datasets/sources;
- latest runs/status;
- control plane vs data plane.

### 2. Onboard a source

From the UI/API:

- create/select a project;
- register a supported source;
- test the connection;
- select/register a dataset.

Expected evidence:

- source metadata persisted;
- connection test succeeds or returns a clear traceable failure.

### 3. Schema discovery and profiling

Show:

- discovered columns/types;
- row/column counts;
- missing values;
- duplicate/cardinality/numeric summaries where applicable.

Explain that profiling reports technical facts and does not blindly define business errors.

### 4. LLM-assisted configuration

Provide a natural-language business requirement and show:

- profiling/schema context used for the suggestion;
- structured proposed rules/transformations;
- validation of the proposal;
- user review/approval.

Explicitly explain that the LLM proposes configuration and does not execute arbitrary generated code.

### 5. Trigger the pipeline

Trigger the configured dataset through the UI/API.

Show the generic Airflow execution path and explain:

```text
source -> Bronze -> profiling -> Silver -> Quality -> Validated/Quarantine -> Gold -> certification
```

### 6. Inspect quality results

Show:

- warning rules;
- critical rules;
- accepted/rejected row counts;
- Quarantine records when present.

### 7. Inspect assets and lineage

Show:

- Bronze/Silver/Quarantine/Gold assets in object storage;
- asset metadata in the control plane;
- upstream/downstream lineage;
- parent datasets for a multi-parent Gold where applicable.

### 8. Certification

Show the dataset certification state and why it is Draft, Validated or Certified.

### 9. Cloud evidence

Demonstrate that the reference execution is running against AWS:

- physical datasets in S3;
- operational metadata in RDS PostgreSQL;
- cloud-hosted API/UI;
- Airflow run connected to the cloud environment.

### 10. Generalization proof

Run/inspect both:

1. Olist as the regression case.
2. A structurally different source, preferably PostgreSQL or REST.

The key proof is that both use the same contracts, connector abstraction, profiling engine, quality engine and orchestration design without a separate client-specific DataForge implementation.

## Evidence to capture

Final evidence should include, at minimum:

- UI onboarding/configuration.
- Source connection success.
- Generic profiling output.
- LLM proposal + validated configuration.
- Airflow execution.
- Quality results and Quarantine.
- S3 data assets.
- RDS metadata/run/lineage data.
- Gold output.
- Certification state.
- CI/test results.
- Second-source execution.

## Known-limitations statement

The final demo must explicitly distinguish implemented capabilities from future extensions. Do not claim support for arbitrary sources, Kafka streaming, Spark clusters, Kubernetes or enterprise-scale production operations unless they are actually implemented and verified later.
