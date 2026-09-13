# AWS Reference Deployment Strategy

## Purpose

AWS is the primary Sprint 2 cloud target. The AWS deployment is the reference operating environment for the near-final product, while Docker Compose remains the reproducible local development environment.

## Local-to-cloud mapping

```text
LOCAL DEVELOPMENT                  AWS REFERENCE DEPLOYMENT
-----------------                  ------------------------
MinIO                              Amazon S3
PostgreSQL container               Amazon RDS PostgreSQL
FastAPI container                  Containerized AWS compute
Airflow containers                 Cloud-accessible Airflow
React/Vite                         S3 + CloudFront or equivalent
Local environment variables        AWS environment/secrets configuration
```

## Why this mapping

### MinIO -> S3

Sprint 1 already treats object storage through an S3-compatible API. Keeping that abstraction allows local development against MinIO and cloud execution against Amazon S3 without redesigning the logical data plane.

### PostgreSQL -> RDS PostgreSQL

The Sprint 1 control plane is already relational and PostgreSQL-based. RDS preserves the data model while delegating database infrastructure concerns to a managed AWS service.

### FastAPI -> containerized AWS compute

FastAPI should remain containerized so the application artifact is consistent between local and cloud environments. The exact compute service should be selected during #28 based on complexity/cost, with ECS/Fargate as a strong candidate.

### React -> static cloud hosting

The built frontend can be hosted as static assets and served globally through CloudFront or an equivalent AWS hosting pattern.

### Airflow

Airflow must be reachable in the AWS reference environment and capable of executing the same reusable pipeline components against S3/RDS. The exact hosting choice is part of #28 and should balance course requirements, cost and operational complexity.

### LLM

The application uses an LLM-provider abstraction. For the AWS reference environment, Amazon Bedrock is a natural provider option, but LLM-provider details must not leak into the deterministic pipeline core.

## Environment strategy

At minimum, DataForge should distinguish:

- `local`: Docker Compose, MinIO, local PostgreSQL;
- `test`: automated/integration test configuration;
- `aws`: S3, RDS and cloud service endpoints.

The application code should not contain `if client == ...` or environment-specific business logic. Environment differences belong in configuration/adapters.

## Security baseline

Sprint 2 cloud deployment should include at least:

- no secrets committed to Git;
- least-privilege AWS permissions where practical;
- RDS not unnecessarily exposed publicly;
- controlled network access between services;
- secure application configuration/secrets handling;
- S3 access restricted to required application/service principals;
- separate configuration for local and cloud environments;
- logs that do not expose credentials/tokens.

This is a course project security baseline, not a claim of enterprise production hardening.

## Deployment phases

### Phase A — application readiness

- storage abstraction works with MinIO/S3;
- metadata connection is environment-configurable;
- API/frontend are container/build ready;
- Airflow pipeline uses generic services/configuration.

### Phase B — cloud infrastructure

- S3 buckets/data layout;
- RDS PostgreSQL;
- compute for API/Airflow;
- frontend hosting;
- network/IAM configuration.

### Phase C — cloud validation

- register a source/dataset;
- execute at least one complete pipeline;
- verify Bronze/Silver/Quarantine/Gold in S3;
- verify metadata/run/quality/lineage in RDS;
- operate the main workflow through cloud API/UI;
- capture evidence and document deployment steps.

## Cost/complexity rule

Prefer the simplest AWS deployment that demonstrates the architecture correctly and reproducibly. Do not introduce expensive/complex managed services solely to make the architecture look more sophisticated.

## Success criterion

At least one end-to-end DataForge pipeline must execute in the AWS reference environment, with physical assets stored in S3 and control-plane metadata stored in RDS PostgreSQL, while the same application remains usable locally through Docker Compose.
